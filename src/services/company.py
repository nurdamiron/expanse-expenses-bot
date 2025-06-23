import logging
from typing import List, Optional, Tuple
from decimal import Decimal
from datetime import datetime, date
from uuid import uuid4
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from src.database.models import (
    Company, CompanyMember, CompanyCategory, CompanyTransaction, 
    ApprovalRule, User, Transaction
)

logger = logging.getLogger(__name__)


class CompanyService:
    """Service for managing companies and company-related operations"""
    
    async def create_company(
        self,
        session: AsyncSession,
        owner_id: int,
        name: str,
        description: Optional[str] = None,
        primary_currency: str = 'KZT',
        timezone: str = 'Asia/Almaty'
    ) -> Company:
        """Create a new company"""
        company = Company(
            id=str(uuid4()),
            name=name,
            description=description,
            owner_id=owner_id,
            primary_currency=primary_currency,
            timezone=timezone,
            settings={
                'auto_approve_limit': '50000',  # Auto-approve transactions below this amount
                'require_receipts': True,
                'allow_personal_expenses': False,
            }
        )
        session.add(company)
        
        # Add owner as first member
        owner_member = CompanyMember(
            company_id=company.id,
            user_id=owner_id,
            role='owner',
            can_approve=True,
            is_active=True
        )
        session.add(owner_member)
        
        # Create default categories
        await self._create_default_company_categories(session, company.id)
        
        await session.flush()
        return company
    
    async def _create_default_company_categories(self, session: AsyncSession, company_id: str):
        """Create default categories for company"""
        default_categories = [
            {'key': 'office', 'name_ru': 'Офис', 'name_kz': 'Кеңсе', 'icon': '🏢'},
            {'key': 'transport', 'name_ru': 'Транспорт', 'name_kz': 'Көлік', 'icon': '🚗'},
            {'key': 'business_meals', 'name_ru': 'Деловые обеды', 'name_kz': 'Іскерлік түскі ас', 'icon': '🍽️'},
            {'key': 'equipment', 'name_ru': 'Оборудование', 'name_kz': 'Жабдық', 'icon': '💻'},
            {'key': 'marketing', 'name_ru': 'Маркетинг', 'name_kz': 'Маркетинг', 'icon': '📢'},
            {'key': 'travel', 'name_ru': 'Командировки', 'name_kz': 'Іссапар', 'icon': '✈️'},
            {'key': 'services', 'name_ru': 'Услуги', 'name_kz': 'Қызметтер', 'icon': '🔧'},
            {'key': 'other', 'name_ru': 'Прочее', 'name_kz': 'Басқа', 'icon': '📌'},
        ]
        
        for idx, cat_data in enumerate(default_categories):
            category = CompanyCategory(
                id=str(uuid4()),
                company_id=company_id,
                name_ru=cat_data['name_ru'],
                name_kz=cat_data['name_kz'],
                icon=cat_data['icon'],
                order_position=idx
            )
            session.add(category)
    
    async def get_user_companies(
        self,
        session: AsyncSession,
        user_id: int,
        active_only: bool = True
    ) -> List[Tuple[Company, CompanyMember]]:
        """Get all companies where user is a member"""
        query = (
            select(Company, CompanyMember)
            .join(CompanyMember, CompanyMember.company_id == Company.id)
            .where(CompanyMember.user_id == user_id)
        )
        
        if active_only:
            query = query.where(
                and_(
                    Company.is_active == True,
                    CompanyMember.is_active == True
                )
            )
        
        result = await session.execute(query)
        return result.all()
    
    async def get_all_companies(
        self,
        session: AsyncSession,
        active_only: bool = True
    ) -> List[Company]:
        """Get all companies (for invite code search)"""
        query = select(Company)
        
        if active_only:
            query = query.where(Company.is_active == True)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_company_by_id(
        self,
        session: AsyncSession,
        company_id: str,
        load_members: bool = False
    ) -> Optional[Company]:
        """Get company by ID"""
        query = select(Company).where(Company.id == company_id)
        
        if load_members:
            query = query.options(
                selectinload(Company.members).selectinload(CompanyMember.user)
            )
        
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    async def add_member(
        self,
        session: AsyncSession,
        company_id: str,
        user_id: int,
        role: str = 'employee',
        department: Optional[str] = None,
        position: Optional[str] = None,
        can_approve: bool = False,
        spending_limit: Optional[Decimal] = None,
        invited_by: Optional[int] = None
    ) -> CompanyMember:
        """Add a member to company"""
        # Check if already a member
        existing = await session.execute(
            select(CompanyMember).where(
                and_(
                    CompanyMember.company_id == company_id,
                    CompanyMember.user_id == user_id
                )
            )
        )
        
        if existing.scalar_one_or_none():
            raise ValueError("User is already a member of this company")
        
        member = CompanyMember(
            company_id=company_id,
            user_id=user_id,
            role=role,
            department=department,
            position=position,
            can_approve=can_approve,
            spending_limit=spending_limit,
            invited_by=invited_by
        )
        
        session.add(member)
        await session.flush()
        
        return member
    
    async def update_member_role(
        self,
        session: AsyncSession,
        company_id: str,
        user_id: int,
        role: str,
        can_approve: Optional[bool] = None,
        spending_limit: Optional[Decimal] = None
    ) -> bool:
        """Update member role and permissions"""
        result = await session.execute(
            select(CompanyMember).where(
                and_(
                    CompanyMember.company_id == company_id,
                    CompanyMember.user_id == user_id
                )
            )
        )
        
        member = result.scalar_one_or_none()
        if not member:
            return False
        
        member.role = role
        if can_approve is not None:
            member.can_approve = can_approve
        if spending_limit is not None:
            member.spending_limit = spending_limit
        
        member.updated_at = datetime.now()
        await session.flush()
        
        return True
    
    async def get_company_members(
        self,
        session: AsyncSession,
        company_id: str,
        active_only: bool = True
    ) -> List[CompanyMember]:
        """Get all company members"""
        query = (
            select(CompanyMember)
            .options(selectinload(CompanyMember.user))
            .where(CompanyMember.company_id == company_id)
        )
        
        if active_only:
            query = query.where(CompanyMember.is_active == True)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def create_company_transaction(
        self,
        session: AsyncSession,
        transaction_id: str,
        company_id: str,
        requires_approval: bool = False,
        auto_approved_by: Optional[int] = None
    ) -> CompanyTransaction:
        """Create company transaction record"""
        company_tx = CompanyTransaction(
            transaction_id=transaction_id,
            company_id=company_id,
            status='pending' if requires_approval else 'approved',
            approved_by=auto_approved_by if not requires_approval else None,
            approved_at=datetime.now() if not requires_approval else None
        )
        
        session.add(company_tx)
        await session.flush()
        
        return company_tx
    
    async def approve_transaction(
        self,
        session: AsyncSession,
        transaction_id: str,
        approved_by: int
    ) -> bool:
        """Approve a company transaction"""
        result = await session.execute(
            select(CompanyTransaction).where(
                CompanyTransaction.transaction_id == transaction_id
            )
        )
        
        company_tx = result.scalar_one_or_none()
        if not company_tx or company_tx.status != 'pending':
            return False
        
        company_tx.status = 'approved'
        company_tx.approved_by = approved_by
        company_tx.approved_at = datetime.now()
        
        await session.flush()
        return True
    
    async def reject_transaction(
        self,
        session: AsyncSession,
        transaction_id: str,
        rejected_by: int,
        reason: str
    ) -> bool:
        """Reject a company transaction"""
        result = await session.execute(
            select(CompanyTransaction).where(
                CompanyTransaction.transaction_id == transaction_id
            )
        )
        
        company_tx = result.scalar_one_or_none()
        if not company_tx or company_tx.status != 'pending':
            return False
        
        company_tx.status = 'rejected'
        company_tx.approved_by = rejected_by  # Store who rejected
        company_tx.approved_at = datetime.now()
        company_tx.rejection_reason = reason
        
        await session.flush()
        return True
    
    async def get_pending_approvals(
        self,
        session: AsyncSession,
        company_id: str,
        approver_id: Optional[int] = None
    ) -> List[Transaction]:
        """Get pending transactions for approval"""
        query = (
            select(Transaction)
            .join(CompanyTransaction, CompanyTransaction.transaction_id == Transaction.id)
            .options(
                joinedload(Transaction.user),
                joinedload(Transaction.category),
                joinedload(Transaction.company_transaction)
            )
            .where(
                and_(
                    CompanyTransaction.company_id == company_id,
                    CompanyTransaction.status == 'pending',
                    Transaction.is_deleted == False
                )
            )
            .order_by(Transaction.created_at.desc())
        )
        
        # If approver specified, check if they can approve
        if approver_id:
            # TODO: Add logic to check if approver has permission
            pass
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_company_spending(
        self,
        session: AsyncSession,
        company_id: str,
        start_date: date,
        end_date: date,
        by_member: bool = False,
        by_category: bool = False
    ) -> dict:
        """Get company spending statistics"""
        # Base query for company transactions
        base_query = (
            select(Transaction)
            .join(CompanyTransaction, CompanyTransaction.transaction_id == Transaction.id)
            .where(
                and_(
                    CompanyTransaction.company_id == company_id,
                    CompanyTransaction.status == 'approved',
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                    Transaction.is_deleted == False
                )
            )
        )
        
        # Total spending
        total_query = select(func.sum(Transaction.amount_primary)).select_from(
            base_query.subquery()
        )
        total_result = await session.execute(total_query)
        total = total_result.scalar() or Decimal('0')
        
        result = {
            'total': total,
            'start_date': start_date,
            'end_date': end_date
        }
        
        # By member
        if by_member:
            member_query = (
                select(
                    Transaction.user_id,
                    User.first_name,
                    User.last_name,
                    func.sum(Transaction.amount_primary).label('total'),
                    func.count(Transaction.id).label('count')
                )
                .join(CompanyTransaction, CompanyTransaction.transaction_id == Transaction.id)
                .join(User, User.id == Transaction.user_id)
                .where(
                    and_(
                        CompanyTransaction.company_id == company_id,
                        CompanyTransaction.status == 'approved',
                        Transaction.transaction_date >= start_date,
                        Transaction.transaction_date <= end_date,
                        Transaction.is_deleted == False
                    )
                )
                .group_by(Transaction.user_id, User.first_name, User.last_name)
                .order_by(func.sum(Transaction.amount_primary).desc())
            )
            
            member_result = await session.execute(member_query)
            result['by_member'] = [
                {
                    'user_id': row.user_id,
                    'name': f"{row.first_name or ''} {row.last_name or ''}".strip() or 'Unknown',
                    'total': row.total,
                    'count': row.count
                }
                for row in member_result
            ]
        
        # By category
        if by_category:
            # TODO: Implement by_category statistics
            result['by_category'] = []
        
        return result
    
    async def check_approval_required(
        self,
        session: AsyncSession,
        company_id: str,
        amount: Decimal,
        category_id: Optional[str] = None
    ) -> bool:
        """Check if transaction requires approval based on rules"""
        # Get company settings
        company = await self.get_company_by_id(session, company_id)
        if not company:
            return False
        
        # Check auto-approve limit
        auto_approve_limit = Decimal(company.settings.get('auto_approve_limit', '0'))
        if auto_approve_limit > 0 and amount <= auto_approve_limit:
            return False
        
        # Check approval rules
        query = (
            select(ApprovalRule)
            .where(
                and_(
                    ApprovalRule.company_id == company_id,
                    ApprovalRule.is_active == True
                )
            )
        )
        
        result = await session.execute(query)
        rules = result.scalars().all()
        
        for rule in rules:
            # Check amount range
            if rule.min_amount and amount < rule.min_amount:
                continue
            if rule.max_amount and amount > rule.max_amount:
                continue
            
            # Check category
            if rule.category_id and rule.category_id != category_id:
                continue
            
            # Rule matches - approval required
            return True
        
        # No specific rules - use default (require approval for large amounts)
        return amount > auto_approve_limit