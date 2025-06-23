import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from src.database import get_session
from src.services.transaction import TransactionService
from src.services.user import UserService
from src.services.category import CategoryService

async def create_test_transactions():
    transaction_service = TransactionService()
    user_service = UserService()
    category_service = CategoryService()
    
    async with get_session() as session:
        # Get user
        user = await user_service.get_user_by_telegram_id(session, 515851185)
        if not user:
            print("User not found!")
            return
            
        print(f"Creating transactions for user {user.username} (id={user.id})")
        
        # Get categories
        food_cat = await category_service.get_default_category(session, user.id, 'food')
        transport_cat = await category_service.get_default_category(session, user.id, 'transport')
        home_cat = await category_service.get_default_category(session, user.id, 'home')
        
        # Create transactions for different periods
        # Today
        today = datetime.now()
        tx1 = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal('2500'),
            currency='KZT',
            category_id=food_cat.id,
            merchant='Magnum',
            transaction_date=today,
            amount_primary=Decimal('2500'),
            exchange_rate=Decimal('1.0'),
            description='Продукты на неделю'
        )
        print(f"Created: {tx1.amount} {tx1.currency} - Today")
        
        # Yesterday
        yesterday = today - timedelta(days=1)
        tx2 = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal('800'),
            currency='KZT',
            category_id=transport_cat.id,
            merchant='Yandex Taxi',
            transaction_date=yesterday,
            amount_primary=Decimal('800'),
            exchange_rate=Decimal('1.0'),
            description='Поездка домой'
        )
        print(f"Created: {tx2.amount} {tx2.currency} - Yesterday")
        
        # 3 days ago (this week)
        three_days_ago = today - timedelta(days=3)
        tx3 = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal('3500'),
            currency='KZT',
            category_id=home_cat.id,
            merchant='Beeline',
            transaction_date=three_days_ago,
            amount_primary=Decimal('3500'),
            exchange_rate=Decimal('1.0'),
            description='Оплата интернета'
        )
        print(f"Created: {tx3.amount} {tx3.currency} - 3 days ago")
        
        # Last week
        last_week = today - timedelta(days=8)
        tx4 = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal('5000'),
            currency='KZT',
            category_id=food_cat.id,
            merchant='Arbat Restaurant',
            transaction_date=last_week,
            amount_primary=Decimal('5000'),
            exchange_rate=Decimal('1.0'),
            description='Ужин с друзьями'
        )
        print(f"Created: {tx4.amount} {tx4.currency} - Last week")
        
        await session.commit()
        
        # Now check statistics
        print("\n=== Checking Statistics ===")
        
        # Today
        today_total, today_count = await transaction_service.get_today_spending(session, user.id)
        print(f"Today: {today_total} KZT ({today_count} transactions)")
        
        # This week
        week_start = date.today() - timedelta(days=date.today().weekday())
        week_total, week_count = await transaction_service.get_period_spending(
            session, user.id, week_start, date.today()
        )
        print(f"This week (from {week_start}): {week_total} KZT ({week_count} transactions)")
        
        # This month
        month_start = date.today().replace(day=1)
        month_total, month_count = await transaction_service.get_period_spending(
            session, user.id, month_start, date.today()
        )
        print(f"This month (from {month_start}): {month_total} KZT ({month_count} transactions)")

if __name__ == "__main__":
    asyncio.run(create_test_transactions())