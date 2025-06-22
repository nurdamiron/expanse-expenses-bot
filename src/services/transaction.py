from typing import List, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc
from uuid import uuid4

from src.database.models import Transaction, Category, User


class TransactionService:
    """Service for transaction operations"""
    
    async def create_transaction(
        self,
        session: AsyncSession,
        user_id: int,
        amount: Decimal,
        currency: str,
        category_id: str,
        description: Optional[str] = None,
        merchant: Optional[str] = None,
        transaction_date: Optional[datetime] = None,
        amount_primary: Optional[Decimal] = None,
        exchange_rate: Optional[Decimal] = None,
        receipt_image_url: Optional[str] = None,
        ocr_confidence: Optional[Decimal] = None,
        metadata: Optional[dict] = None
    ) -> Transaction:
        """Create new transaction"""
        if transaction_date is None:
            transaction_date = datetime.now()
        
        if amount_primary is None:
            amount_primary = amount
        
        if exchange_rate is None:
            exchange_rate = Decimal('1.0000')
        
        transaction = Transaction(
            id=str(uuid4()),
            user_id=user_id,
            category_id=category_id,
            amount=amount,
            currency=currency,
            amount_primary=amount_primary,
            exchange_rate=exchange_rate,
            description=description,
            merchant=merchant,
            transaction_date=transaction_date,
            receipt_image_url=receipt_image_url,
            ocr_confidence=ocr_confidence,
            metadata=metadata
        )
        
        session.add(transaction)
        await session.flush()
        return transaction
    
    async def get_transaction_by_id(
        self,
        session: AsyncSession,
        transaction_id: str,
        user_id: int
    ) -> Optional[Transaction]:
        """Get transaction by ID"""
        result = await session.execute(
            select(Transaction).where(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id,
                    Transaction.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_user_transactions(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        category_id: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None
    ) -> List[Transaction]:
        """Get user transactions with filters"""
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.is_deleted == False
            )
        )
        
        if start_date:
            query = query.where(Transaction.transaction_date >= start_date)
        
        if end_date:
            query = query.where(Transaction.transaction_date <= end_date)
        
        if category_id:
            query = query.where(Transaction.category_id == category_id)
        
        if min_amount:
            query = query.where(Transaction.amount_primary >= min_amount)
        
        if max_amount:
            query = query.where(Transaction.amount_primary <= max_amount)
        
        query = query.order_by(desc(Transaction.transaction_date))
        query = query.limit(limit).offset(offset)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_today_spending(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Tuple[Decimal, int]:
        """Get today's total spending and transaction count"""
        today = date.today()
        
        result = await session.execute(
            select(
                func.sum(Transaction.amount_primary),
                func.count(Transaction.id)
            ).where(
                and_(
                    Transaction.user_id == user_id,
                    func.date(Transaction.transaction_date) == today,
                    Transaction.is_deleted == False
                )
            )
        )
        
        total, count = result.first()
        return total or Decimal('0'), count or 0
    
    async def get_period_spending(
        self,
        session: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> Tuple[Decimal, int]:
        """Get spending for a specific period"""
        result = await session.execute(
            select(
                func.sum(Transaction.amount_primary),
                func.count(Transaction.id)
            ).where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                    Transaction.is_deleted == False
                )
            )
        )
        
        total, count = result.first()
        return total or Decimal('0'), count or 0
    
    async def get_category_spending(
        self,
        session: AsyncSession,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10
    ) -> List[dict]:
        """Get spending by categories"""
        query = select(
            Transaction.category_id,
            func.sum(Transaction.amount_primary).label('total'),
            func.count(Transaction.id).label('count')
        ).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.is_deleted == False
            )
        )
        
        if start_date:
            query = query.where(Transaction.transaction_date >= start_date)
        
        if end_date:
            query = query.where(Transaction.transaction_date <= end_date)
        
        query = query.group_by(Transaction.category_id)
        query = query.order_by(desc('total'))
        query = query.limit(limit)
        
        result = await session.execute(query)
        
        category_spending = []
        for row in result:
            category_id, total, count = row
            
            # Get category details
            category = await session.get(Category, category_id)
            if category:
                category_spending.append({
                    'category_id': category_id,
                    'category': category,
                    'total': total,
                    'count': count
                })
        
        return category_spending
    
    async def update_transaction(
        self,
        session: AsyncSession,
        transaction_id: str,
        user_id: int,
        **kwargs
    ) -> Optional[Transaction]:
        """Update transaction"""
        transaction = await self.get_transaction_by_id(session, transaction_id, user_id)
        
        if not transaction:
            return None
        
        for key, value in kwargs.items():
            if hasattr(transaction, key) and value is not None:
                setattr(transaction, key, value)
        
        await session.flush()
        return transaction
    
    async def delete_transaction(
        self,
        session: AsyncSession,
        transaction_id: str,
        user_id: int
    ) -> bool:
        """Soft delete transaction"""
        transaction = await self.get_transaction_by_id(session, transaction_id, user_id)
        
        if not transaction:
            return False
        
        transaction.is_deleted = True
        await session.flush()
        return True
    
    async def search_transactions(
        self,
        session: AsyncSession,
        user_id: int,
        query: str,
        limit: int = 50
    ) -> List[Transaction]:
        """Search transactions by description or merchant"""
        search_query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.is_deleted == False,
                or_(
                    Transaction.description.ilike(f'%{query}%'),
                    Transaction.merchant.ilike(f'%{query}%')
                )
            )
        )
        
        search_query = search_query.order_by(desc(Transaction.transaction_date))
        search_query = search_query.limit(limit)
        
        result = await session.execute(search_query)
        return result.scalars().all()
    
    async def get_last_transactions(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 5
    ) -> List[Transaction]:
        """Get last N transactions"""
        query = select(Transaction).where(
            and_(
                Transaction.user_id == user_id,
                Transaction.is_deleted == False
            )
        )
        
        query = query.order_by(desc(Transaction.created_at))
        query = query.limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()