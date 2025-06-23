from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from src.database.models import Transaction


class DuplicateDetector:
    """Service for detecting duplicate transactions"""
    
    async def find_duplicates(
        self,
        session: AsyncSession,
        user_id: int,
        amount: Decimal,
        merchant: Optional[str] = None,
        description: Optional[str] = None,
        transaction_date: Optional[datetime] = None,
        time_window_hours: int = 24
    ) -> List[Transaction]:
        """
        Find potential duplicate transactions
        
        Args:
            session: Database session
            user_id: User ID
            amount: Transaction amount
            merchant: Merchant name
            description: Transaction description
            transaction_date: Transaction date
            time_window_hours: Time window to check for duplicates
            
        Returns:
            List of potential duplicate transactions
        """
        if transaction_date is None:
            transaction_date = datetime.now()
        
        # Define time window
        start_date = transaction_date - timedelta(hours=time_window_hours)
        end_date = transaction_date + timedelta(hours=time_window_hours)
        
        # Build query
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.amount == amount,
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.is_deleted == False
            )
        )
        
        # Add merchant filter if provided
        if merchant:
            # Check for exact match or similar merchant names
            merchant_lower = merchant.lower()
            query = query.where(
                or_(
                    Transaction.merchant == merchant,
                    Transaction.merchant.ilike(f"%{merchant}%")
                )
            )
        
        # Don't filter by description - it can vary for same transaction
        
        # Execute query
        result = await session.execute(query)
        duplicates = result.scalars().all()
        
        # Filter by exact time match for true duplicates
        exact_duplicates = []
        near_duplicates = []
        
        for dup in duplicates:
            # Check time difference
            time_diff = abs((dup.transaction_date - transaction_date).total_seconds())
            
            if time_diff <= 5:  # Within 5 seconds - exact duplicate
                exact_duplicates.append(dup)
            elif time_diff <= 60:  # Within 1 minute - likely duplicate
                near_duplicates.append(dup)
        
        # Return exact duplicates first, then near duplicates
        if exact_duplicates:
            return exact_duplicates
        elif near_duplicates and not merchant:  # For receipts without merchant, be more strict
            return near_duplicates
        
        return []  # Don't return far time matches as duplicates
    
    def is_likely_duplicate(
        self,
        trans1: Transaction,
        trans2: Transaction,
        time_threshold_seconds: int = 1
    ) -> bool:
        """
        Check if two transactions are likely duplicates
        
        Args:
            trans1: First transaction
            trans2: Second transaction
            time_threshold_seconds: Time threshold for duplicate detection
            
        Returns:
            True if transactions are likely duplicates
        """
        # Check amount
        if trans1.amount != trans2.amount:
            return False
        
        # Check time difference
        time_diff = abs((trans1.transaction_date - trans2.transaction_date).total_seconds())
        if time_diff > time_threshold_seconds:
            return False
        
        # Check merchant (if both have merchants)
        if trans1.merchant and trans2.merchant:
            # Case-insensitive comparison
            if trans1.merchant.lower() != trans2.merchant.lower():
                return False
        
        return True


# Singleton instance
duplicate_detector = DuplicateDetector()