from decimal import Decimal
from datetime import datetime
from typing import Optional, Tuple, Dict
import re

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.services.user import UserService
from src.services.transaction import TransactionService
from src.services.currency import CurrencyService
from src.services.openai_service import OpenAIService
from src.utils.i18n import i18n
from src.bot.keyboards import get_main_keyboard
from src.bot.states import ExpenseStates
from src.core.config import settings

router = Router()
user_service = UserService()
transaction_service = TransactionService()
currency_service = CurrencyService()
openai_service = OpenAIService()


class TextExpenseParser:
    """Parse expense information from natural language text"""
    
    # Currency symbols and keywords
    CURRENCY_PATTERNS = {
        'тг': 'KZT', 'тенге': 'KZT', 'kzt': 'KZT',
        'руб': 'RUB', 'рубл': 'RUB', 'rub': 'RUB', '₽': 'RUB',
        'долл': 'USD', 'usd': 'USD', '$': 'USD',
        'евро': 'EUR', 'eur': 'EUR', '€': 'EUR',
        'юан': 'CNY', 'cny': 'CNY', '¥': 'CNY',
        'вон': 'KRW', 'krw': 'KRW', '₩': 'KRW',
        'лир': 'TRY', 'try': 'TRY', '₺': 'TRY',
        'рингит': 'MYR', 'myr': 'MYR', 'rm': 'MYR'
    }
    
    # Category keywords
    CATEGORY_KEYWORDS = {
        'food': ['еда', 'обед', 'ужин', 'завтрак', 'кафе', 'ресторан', 'продукты', 'магазин', 'тамақ', 'түскі ас', 'кешкі ас', 'таңғы ас'],
        'transport': ['такси', 'автобус', 'метро', 'бензин', 'транспорт', 'поездка', 'көлік', 'жол'],
        'home': ['квартира', 'дом', 'коммуналка', 'свет', 'газ', 'вода', 'интернет', 'үй', 'пәтер'],
        'health': ['аптека', 'лекарство', 'врач', 'больница', 'здоровье', 'дәріхана', 'дәрі', 'дәрігер'],
        'entertainment': ['кино', 'развлечение', 'игра', 'концерт', 'театр', 'ойын-сауық'],
        'shopping': ['одежда', 'обувь', 'покупка', 'шоппинг', 'киім', 'аяқ киім', 'сатып алу'],
        'education': ['книга', 'курс', 'обучение', 'учеба', 'кітап', 'оқу'],
        'other': ['другое', 'прочее', 'разное', 'басқа']
    }
    
    @staticmethod
    def extract_amount(text: str) -> Optional[Tuple[Decimal, str]]:
        """Extract amount and currency from text"""
        # Remove spaces between digits
        text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)
        
        # Pattern to find numbers with optional decimal places
        amount_pattern = r'(\d+(?:[.,]\d+)?)'
        
        # Find all numbers in text
        numbers = re.findall(amount_pattern, text)
        if not numbers:
            return None
        
        # Take the first number as amount
        amount_str = numbers[0].replace(',', '.')
        amount = Decimal(amount_str)
        
        # Detect currency
        text_lower = text.lower()
        detected_currency = None
        
        # Check for currency symbols and keywords
        for keyword, currency in TextExpenseParser.CURRENCY_PATTERNS.items():
            if keyword in text_lower:
                detected_currency = currency
                break
        
        # Default to user's primary currency if not detected
        if not detected_currency:
            detected_currency = 'KZT'  # Will be replaced with user's currency
        
        return amount, detected_currency
    
    @staticmethod
    def detect_category(text: str) -> str:
        """Detect category from text keywords"""
        text_lower = text.lower()
        
        for category, keywords in TextExpenseParser.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return category
        
        return 'other'
    
    @staticmethod
    async def parse_with_ai(text: str, user_currency: str) -> Optional[Dict]:
        """Use AI to parse expense from natural language"""
        try:
            prompt = f"""Analyze this expense message and extract information.
Message: "{text}"
User's default currency: {user_currency}

Extract:
1. Amount (number only)
2. Currency (if mentioned, otherwise use {user_currency})
3. Category (food/transport/home/health/entertainment/shopping/education/other)
4. Description/merchant (if mentioned)

Respond in JSON format:
{{
    "amount": 0.0,
    "currency": "KZT",
    "category": "other",
    "description": "text"
}}

If this is not an expense message, return null."""

            result = await openai_service.parse_expense_text(prompt)
            if result and result.get('amount'):
                return result
        except Exception as e:
            print(f"AI parsing error: {e}")
        
        return None


@router.message(F.text & ~F.text.startswith('/'))
async def process_text_expense(message: Message, state: FSMContext):
    """Process text message as potential expense"""
    text = message.text.strip()
    telegram_id = message.from_user.id
    
    # Skip if text is too short or looks like a command
    if len(text) < 3 or text.startswith('/'):
        return
    
    # Skip keyboard button texts
    keyboard_buttons = ['📊 Аналитика', '📝 История', '⚙️ Настройки', 
                       '💼 Компания', '💳 Категории', '📤 Экспорт', '❓ Помощь']
    if any(text.startswith(btn) for btn in keyboard_buttons):
        return
    
    # Check if already processing another expense
    current_state = await state.get_state()
    if current_state:
        # User is in the middle of another operation
        return
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            return
        
        locale = user.language_code
        user_currency = user.primary_currency
        
        # First try simple parsing
        parsed = TextExpenseParser.extract_amount(text)
        
        if parsed:
            amount, detected_currency = parsed
            
            # Use user's currency if not detected
            if detected_currency == 'KZT' and user_currency != 'KZT':
                detected_currency = user_currency
            
            # Detect category
            category = TextExpenseParser.detect_category(text)
            
            # Create description from text
            description = text
            
        else:
            # Try AI parsing if simple parsing failed
            ai_result = await TextExpenseParser.parse_with_ai(text, user_currency)
            if not ai_result:
                return  # Not an expense message
            
            amount = Decimal(str(ai_result['amount']))
            detected_currency = ai_result.get('currency', user_currency)
            category = ai_result.get('category', 'other')
            description = ai_result.get('description', text)
        
        # Map category to actual category name
        category_map = {
            'food': 'Еда и рестораны',
            'transport': 'Транспорт',
            'home': 'Дом и коммунальные',
            'health': 'Здоровье и медицина',
            'entertainment': 'Развлечения',
            'shopping': 'Покупки',
            'education': 'Образование',
            'other': 'Другое'
        }
        
        category_name = category_map.get(category, 'Другое')
        
        # Get category from database
        from sqlalchemy import select
        from src.database.models import Category
        
        result = await session.execute(
            select(Category).where(
                Category.user_id == user.id,
                Category.name_ru == category_name,
                Category.is_default == True
            ).limit(1)
        )
        category_obj = result.scalar_one_or_none()
        
        if not category_obj:
            # Use default "Other" category
            result = await session.execute(
                select(Category).where(
                    Category.user_id == user.id,
                    Category.name_ru == 'Другое',
                    Category.is_default == True
                ).limit(1)
            )
            category_obj = result.scalar_one_or_none()
        
        if not category_obj:
            return  # No categories found
        
        # Convert currency if needed
        amount_primary = amount
        exchange_rate = Decimal('1.0000')
        
        if detected_currency != user_currency:
            converted_amount, rate = await currency_service.convert_amount(
                amount, detected_currency, user_currency, session
            )
            amount_primary = converted_amount
            exchange_rate = rate
        
        # Create transaction
        transaction = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=amount,
            currency=detected_currency,
            category_id=category_obj.id,
            description=description,
            merchant=None,
            transaction_date=datetime.now(),
            amount_primary=amount_primary,
            exchange_rate=exchange_rate
        )
        
        await session.commit()
        
        # Get today's spending for summary
        today_total, _ = await transaction_service.get_today_spending(session, user.id)
        from src.utils.text_parser import ExpenseParser
        expense_parser = ExpenseParser()
        today_formatted = expense_parser.format_amount(today_total, user_currency)
        
        # Send confirmation
        if detected_currency != user_currency:
            confirmation_text = f"✅ {category_obj.icon} {description}\n"
            confirmation_text += f"💰 {amount} {detected_currency} = {amount_primary:.2f} {user_currency}\n"
            confirmation_text += f"💱 {i18n.get('currency.rate', locale)}: {exchange_rate}\n\n"
            confirmation_text += f"📊 {i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
        else:
            confirmation_text = f"✅ {category_obj.icon} {description}\n"
            confirmation_text += f"💰 {amount} {detected_currency}\n\n"
            confirmation_text += f"📊 {i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
        
        await message.answer(
            confirmation_text,
            reply_markup=get_main_keyboard(locale, user.active_company.name if user.active_company else None)
        )