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
        
        # Execute query
        result = await session.execute(query)
        duplicates = result.scalars().all()
        
        # Filter by exact time match if we have exact duplicates
        exact_duplicates = []
        for dup in duplicates:
            # Check if transaction is within seconds of each other
            time_diff = abs((dup.transaction_date - transaction_date).total_seconds())
            if time_diff <= 1:  # Within 1 second - exact duplicate
                exact_duplicates.append(dup)
        
        # Return exact duplicates if found, otherwise all potential duplicates
        return exact_duplicates if exact_duplicates else duplicates
    
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