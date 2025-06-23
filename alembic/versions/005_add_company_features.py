"""Add company features

Revision ID: 005
Revises: 
Create Date: 2025-06-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create companies table
    op.create_table('companies',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('logo_url', sa.Text(), nullable=True),
        sa.Column('primary_currency', 
            sa.Enum('KZT', 'RUB', 'USD', 'EUR', 'CNY', 'KRW', 'TRY', name='currency_enum'), 
            nullable=False, server_default='KZT'
        ),
        sa.Column('timezone', sa.String(50), nullable=False, server_default='Asia/Almaty'),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_company_owner', 'companies', ['owner_id'])
    op.create_index('idx_company_active', 'companies', ['is_active'])

    # Create company_members table
    op.create_table('company_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Enum('owner', 'admin', 'manager', 'employee', name='company_role_enum'), nullable=False),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('position', sa.String(100), nullable=True),
        sa.Column('can_approve', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('spending_limit', sa.DECIMAL(12, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('invited_by', sa.Integer(), nullable=True),
        sa.Column('joined_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'user_id', name='uq_company_member')
    )
    op.create_index('idx_company_member_user', 'company_members', ['user_id'])
    op.create_index('idx_company_member_company', 'company_members', ['company_id'])
    op.create_index('idx_company_member_active', 'company_members', ['is_active'])

    # Create company_categories table
    op.create_table('company_categories',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('name_ru', sa.String(100), nullable=False),
        sa.Column('name_kz', sa.String(100), nullable=False),
        sa.Column('icon', sa.String(10), nullable=False),
        sa.Column('color', sa.String(7), nullable=False, server_default='#000000'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('order_position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_company_category_company', 'company_categories', ['company_id'])
    op.create_index('idx_company_category_active', 'company_categories', ['is_active'])

    # Create company_transactions table
    op.create_table('company_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('transaction_id', sa.String(36), nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='approval_status_enum'), 
                  nullable=False, server_default='approved'),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('transaction_id', name='uq_company_transaction')
    )
    op.create_index('idx_company_transaction_company', 'company_transactions', ['company_id'])
    op.create_index('idx_company_transaction_status', 'company_transactions', ['status'])

    # Create approval_rules table
    op.create_table('approval_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('company_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('min_amount', sa.DECIMAL(12, 2), nullable=True),
        sa.Column('max_amount', sa.DECIMAL(12, 2), nullable=True),
        sa.Column('category_id', sa.String(36), nullable=True),
        sa.Column('required_role', sa.Enum('owner', 'admin', 'manager', 'employee', name='company_role_enum'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['company_categories.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_approval_rule_company', 'approval_rules', ['company_id'])

    # Add columns to existing tables
    # For SQLite, we need to use batch operations
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('active_company_id', sa.String(36), nullable=True))
        # SQLite doesn't support foreign keys in batch mode properly, so we skip them
    
    with op.batch_alter_table('transactions') as batch_op:
        batch_op.add_column(sa.Column('company_id', sa.String(36), nullable=True))


def downgrade():
    # Drop columns from existing tables using batch operations for SQLite
    with op.batch_alter_table('transactions') as batch_op:
        batch_op.drop_column('company_id')
    
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('active_company_id')
    
    # Drop new tables
    op.drop_table('approval_rules')
    op.drop_table('company_transactions')
    op.drop_table('company_categories')
    op.drop_table('company_members')
    op.drop_table('companies')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS company_role_enum")
    op.execute("DROP TYPE IF EXISTS approval_status_enum")