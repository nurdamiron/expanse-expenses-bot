import asyncio
from datetime import datetime, date
from decimal import Decimal
from src.database import get_session
from src.services.transaction import TransactionService
from src.services.user import UserService
from src.services.category import CategoryService

async def add_test_transaction():
    transaction_service = TransactionService()
    user_service = UserService()
    category_service = CategoryService()
    
    async with get_session() as session:
        # Get test user
        user = await user_service.get_user_by_telegram_id(session, 515851185)
        if not user:
            print("User not found!")
            return
            
        # Get food category
        category = await category_service.get_default_category(session, user.id, 'food')
        if not category:
            print("Category not found!")
            return
            
        # Add transaction for today
        today = datetime.now()
        transaction = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal('1500'),
            currency='KZT',
            category_id=category.id,
            merchant='Test Cafe',
            transaction_date=today,
            amount_primary=Decimal('1500'),
            exchange_rate=Decimal('1.0'),
            description='Тестовая транзакция за сегодня'
        )
        
        await session.commit()
        print(f"Created test transaction for today: {transaction.amount} {transaction.currency}")
        
        # Check stats
        today_total, today_count = await transaction_service.get_today_spending(session, user.id)
        print(f"Today's spending: {today_total} ({today_count} transactions)")
        
        # Week
        from datetime import timedelta
        week_start = date.today() - timedelta(days=date.today().weekday())
        week_total, week_count = await transaction_service.get_period_spending(
            session, user.id, week_start, date.today()
        )
        print(f"This week's spending: {week_total} ({week_count} transactions)")

if __name__ == "__main__":
    asyncio.run(add_test_transaction())