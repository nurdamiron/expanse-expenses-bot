from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import (
    Column, BigInteger, String, Boolean, DateTime, 
    ForeignKey, Enum, Text, JSON, Date, Integer,
    DECIMAL, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    language_code = Column(Enum('ru', 'kz', name='language_enum'), default='ru')
    primary_currency = Column(
        Enum('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY', 'MYR', name='currency_enum'), 
        default='KZT'
    )
    timezone = Column(String(50), default='Asia/Almaty')
    is_active = Column(Boolean, default=True, index=True)
    settings = Column(JSON)
    active_company_id = Column(String(36), ForeignKey('companies.id', ondelete='SET NULL'), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    limits = relationship("UserLimit", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    bot_state = relationship("BotState", back_populates="user", uselist=False, cascade="all, delete-orphan")
    active_company = relationship("Company", foreign_keys=[active_company_id], back_populates="active_users")
    owned_companies = relationship("Company", foreign_keys="Company.owner_id", back_populates="owner")
    company_memberships = relationship("CompanyMember", foreign_keys="CompanyMember.user_id", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Category(Base):
    __tablename__ = "categories"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name_ru = Column(String(100), nullable=False)
    name_kz = Column(String(100), nullable=False)
    icon = Column(String(10), nullable=False)
    color = Column(String(7), default='#000000')
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    order_position = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="categories")
    transactions = relationship("Transaction", back_populates="category")
    limits = relationship("UserLimit", back_populates="category")
    
    def get_name(self, language: str = 'ru') -> str:
        """Get category name in specified language"""
        return self.name_ru if language == 'ru' else self.name_kz
    
    def __repr__(self):
        return f"<Category(id={self.id}, name_ru={self.name_ru}, icon={self.icon})>"


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'transaction_date'),
        Index('idx_user_month', 'user_id', 'transaction_date', 'is_deleted'),
        Index('idx_amount_search', 'user_id', 'amount_primary', 'is_deleted'),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category_id = Column(String(36), ForeignKey('categories.id', ondelete='SET NULL'))
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(
        Enum('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY', 'MYR', name='currency_enum'), 
        nullable=False
    )
    amount_primary = Column(DECIMAL(12, 2), nullable=False)
    exchange_rate = Column(DECIMAL(10, 4), default=Decimal('1.0000'))
    description = Column(Text)
    merchant = Column(String(255))
    transaction_date = Column(DateTime, nullable=False, index=True)
    receipt_image_url = Column(Text)
    ocr_confidence = Column(DECIMAL(3, 2))
    # meta_data = Column('meta_data', JSON, nullable=True)  # Temporarily disabled due to SQLAlchemy caching issue
    company_id = Column(String(36), ForeignKey('companies.id', ondelete='SET NULL'), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    company = relationship("Company", back_populates="transactions")
    company_transaction = relationship("CompanyTransaction", back_populates="transaction", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, amount={self.amount} {self.currency}, date={self.transaction_date})>"


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint('from_currency', 'to_currency', 'fetched_at', name='unique_currency_pair'),
        Index('idx_latest_rate', 'from_currency', 'to_currency', 'fetched_at'),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    from_currency = Column(
        Enum('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY', 'MYR', name='currency_enum'), 
        nullable=False
    )
    to_currency = Column(
        Enum('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY', 'MYR', name='currency_enum'), 
        nullable=False
    )
    rate = Column(DECIMAL(10, 4), nullable=False)
    source = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)
    fetched_at = Column(DateTime, server_default=func.now(), index=True)
    
    def __repr__(self):
        return f"<ExchangeRate({self.from_currency}->{self.to_currency}={self.rate}, source={self.source})>"


class UserLimit(Base):
    __tablename__ = "user_limits"
    __table_args__ = (
        Index('idx_user_limits', 'user_id', 'is_active'),
        Index('idx_date_range', 'start_date', 'end_date'),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    limit_type = Column(Enum('daily', 'weekly', 'monthly', name='limit_type_enum'), nullable=False)
    category_id = Column(String(36), ForeignKey('categories.id', ondelete='CASCADE'))
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(
        Enum('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY', 'MYR', name='currency_enum'), 
        nullable=False
    )
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="limits")
    category = relationship("Category", back_populates="limits")
    
    def __repr__(self):
        return f"<UserLimit(type={self.limit_type}, amount={self.amount} {self.currency})>"


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index('idx_status_scheduled', 'status', 'scheduled_at'),
        Index('idx_user_status', 'user_id', 'status'),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type = Column(
        Enum('limit_exceeded', 'weekly_report', 'monthly_report', 'reminder', name='notification_type_enum'), 
        nullable=False
    )
    status = Column(Enum('pending', 'sent', 'failed', name='notification_status_enum'), default='pending')
    scheduled_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime)
    content = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(type={self.type}, status={self.status})>"


class BotState(Base):
    __tablename__ = "bot_states"
    __table_args__ = (
        UniqueConstraint('user_id', name='unique_user_state'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    state = Column(String(100), index=True)
    state_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="bot_state")
    
    def __repr__(self):
        return f"<BotState(user_id={self.user_id}, state={self.state})>"


class SearchHistory(Base):
    __tablename__ = "search_history"
    __table_args__ = (
        Index('idx_search_user_created', 'user_id', 'created_at'),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    search_type = Column(Enum('text', 'amount', 'category', 'date_range', name='search_type_enum'), nullable=False)
    search_query = Column(Text)
    results_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<SearchHistory(type={self.search_type}, query={self.search_query})>"


class ExportHistory(Base):
    __tablename__ = "export_history"
    __table_args__ = (
        Index('idx_export_user_created', 'user_id', 'created_at'),
    )
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    format = Column(Enum('xlsx', 'csv', 'pdf', name='export_format_enum'), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    file_url = Column(Text)
    file_size = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<ExportHistory(format={self.format}, period={self.period_start} to {self.period_end})>"


class Company(Base):
    __tablename__ = "companies"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    owner_id = Column(Integer, ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    logo_url = Column(Text)
    primary_currency = Column(
        Enum('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY', 'MYR', name='currency_enum'), 
        default='KZT'
    )
    timezone = Column(String(50), default='Asia/Almaty')
    settings = Column(JSON)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", foreign_keys=[owner_id], back_populates="owned_companies")
    active_users = relationship("User", foreign_keys="User.active_company_id", back_populates="active_company")
    members = relationship("CompanyMember", back_populates="company", cascade="all, delete-orphan")
    categories = relationship("CompanyCategory", back_populates="company", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="company")
    company_transactions = relationship("CompanyTransaction", back_populates="company", cascade="all, delete-orphan")
    approval_rules = relationship("ApprovalRule", back_populates="company", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Company(id={self.id}, name={self.name})>"


class CompanyMember(Base):
    __tablename__ = "company_members"
    __table_args__ = (
        UniqueConstraint('company_id', 'user_id', name='uq_company_member'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(String(36), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = Column(Enum('owner', 'admin', 'manager', 'employee', name='company_role_enum'), nullable=False)
    department = Column(String(100))
    position = Column(String(100))
    can_approve = Column(Boolean, default=False)
    spending_limit = Column(DECIMAL(12, 2))
    is_active = Column(Boolean, default=True, index=True)
    invited_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    joined_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="members")
    user = relationship("User", foreign_keys=[user_id], back_populates="company_memberships")
    inviter = relationship("User", foreign_keys=[invited_by])
    
    def __repr__(self):
        return f"<CompanyMember(company_id={self.company_id}, user_id={self.user_id}, role={self.role})>"


class CompanyCategory(Base):
    __tablename__ = "company_categories"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    company_id = Column(String(36), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    name_ru = Column(String(100), nullable=False)
    name_kz = Column(String(100), nullable=False)
    icon = Column(String(10), nullable=False)
    color = Column(String(7), default='#000000')
    is_active = Column(Boolean, default=True, index=True)
    order_position = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="categories")
    
    def get_name(self, language: str = 'ru') -> str:
        """Get category name in specified language"""
        return self.name_ru if language == 'ru' else self.name_kz
    
    def __repr__(self):
        return f"<CompanyCategory(id={self.id}, name_ru={self.name_ru})>"


class CompanyTransaction(Base):
    __tablename__ = "company_transactions"
    __table_args__ = (
        UniqueConstraint('transaction_id', name='uq_company_transaction'),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(36), ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False)
    company_id = Column(String(36), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    status = Column(Enum('pending', 'approved', 'rejected', name='approval_status_enum'), default='approved')
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    transaction = relationship("Transaction", back_populates="company_transaction")
    company = relationship("Company", back_populates="company_transactions")
    approver = relationship("User", foreign_keys=[approved_by])
    
    def __repr__(self):
        return f"<CompanyTransaction(transaction_id={self.transaction_id}, status={self.status})>"


class ApprovalRule(Base):
    __tablename__ = "approval_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(String(36), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    min_amount = Column(DECIMAL(12, 2))
    max_amount = Column(DECIMAL(12, 2))
    category_id = Column(String(36), ForeignKey('company_categories.id', ondelete='SET NULL'))
    required_role = Column(Enum('owner', 'admin', 'manager', 'employee', name='company_role_enum'))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    company = relationship("Company", back_populates="approval_rules")
    category = relationship("CompanyCategory")
    
    def __repr__(self):
        return f"<ApprovalRule(id={self.id}, name={self.name}, company_id={self.company_id})>"