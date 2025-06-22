from typing import Optional
from decimal import Decimal
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.bot.states import ExpenseStates
from src.bot.keyboards import (
    get_default_categories_keyboard,
    get_categories_keyboard,
    get_confirm_keyboard,
    get_cancel_keyboard
)
from src.services.user import UserService
from src.services.category import CategoryService
from src.services.transaction import TransactionService
from src.utils.text_parser import ExpenseParser
from src.utils.i18n import i18n
from src.core.config import settings

router = Router()
user_service = UserService()
category_service = CategoryService()
transaction_service = TransactionService()
expense_parser = ExpenseParser()


@router.message(ExpenseStates.waiting_for_amount, F.text & ~F.text.startswith('/'))
async def process_expense_input(message: Message, state: FSMContext):
    """Process expense input when waiting for expense"""
    telegram_id = message.from_user.id
    text = message.text.strip()
    
    # Try to parse expense
    parsed = expense_parser.parse_expense(text)
    
    if not parsed:
        # Not recognized as expense format
        async with get_session() as session:
            user = await user_service.get_user_by_telegram_id(session, telegram_id)
            locale = user.language_code if user else 'ru'
        
        await message.answer(
            i18n.get("manual_input.error_format", locale),
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Store parsed data in state
        await state.update_data(
            amount=str(parsed['amount']),
            currency=parsed['currency'],
            description=parsed['description'],
            transaction_date=parsed['date'] or datetime.now(),
            user_currency=user.primary_currency
        )
        
        # Format message
        amount_formatted = expense_parser.format_amount(parsed['amount'], parsed['currency'])
        
        expense_info = f"{i18n.get('manual_input.add_expense', locale)}\n"
        expense_info += f"{i18n.get('receipt.amount', locale)}: {amount_formatted}\n"
        
        if parsed['description']:
            expense_info += f"{i18n.get('manual_input.description', locale)} {parsed['description']}\n"
        
        expense_info += f"{i18n.get('receipt.date', locale)}: {parsed['date'] or datetime.now().strftime('%d.%m.%Y')}\n"
        
        # Check if currency conversion needed
        if parsed['currency'] != user.primary_currency and settings.enable_currency_conversion:
            from src.services.currency import currency_service
            
            # Get conversion rate
            converted_amount, rate = await currency_service.convert_amount(
                parsed['amount'],
                parsed['currency'],
                user.primary_currency,
                session
            )
            
            if converted_amount:
                await state.update_data(
                    amount_primary=str(converted_amount),
                    exchange_rate=str(rate)
                )
                
                # Show conversion info
                expense_info += f"\n💱 {expense_parser.format_amount(parsed['amount'], parsed['currency'])} = "
                expense_info += f"{expense_parser.format_amount(converted_amount, user.primary_currency)} "
                expense_info += f"({i18n.get('currency.conversion', locale, from_currency=parsed['currency'], to_currency=user.primary_currency, rate=rate)})\n"
        
        expense_info += f"\n{i18n.get('receipt.choose_category', locale)}"
        
        await message.answer(
            expense_info,
            reply_markup=get_default_categories_keyboard(locale)
        )
        
        await state.set_state(ExpenseStates.waiting_for_category)


@router.callback_query(F.data.startswith("quick_category:"), ExpenseStates.waiting_for_category)
async def process_quick_category(callback: CallbackQuery, state: FSMContext):
    """Process quick category selection"""
    category_key = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Get default category
        category = await category_service.get_default_category(session, user.id, category_key)
        
        if not category:
            await callback.answer(i18n.get("errors.unknown", locale))
            return
        
        # Get state data
        data = await state.get_data()
        
        # Create transaction
        amount_primary = Decimal(data.get('amount_primary', data['amount']))
        exchange_rate = Decimal(data.get('exchange_rate', '1.0000'))
        
        transaction = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal(data['amount']),
            currency=data['currency'],
            category_id=category.id,
            description=data.get('description'),
            transaction_date=data['transaction_date'],
            amount_primary=amount_primary,
            exchange_rate=exchange_rate
        )
        
        await session.commit()
        
        # Get today's spending
        today_total, _ = await transaction_service.get_today_spending(session, user.id)
        
        # Format response
        amount_formatted = expense_parser.format_amount(Decimal(data['amount']), data['currency'])
        today_formatted = expense_parser.format_amount(today_total, user.primary_currency)
        
        response = f"{i18n.get('receipt.saved', locale)} "
        response += f"{amount_formatted} {i18n.get(f'categories.{category_key}', locale)}"
        
        if data.get('description'):
            response += f" ({data['description']})"
        
        response += f"\n\n{i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
        
        await callback.message.edit_text(response)
        await state.clear()


@router.callback_query(F.data == "all_categories", ExpenseStates.waiting_for_category)
async def show_all_categories(callback: CallbackQuery, state: FSMContext):
    """Show all user categories"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        categories = await category_service.get_user_categories(session, user.id)
        
        if not categories:
            # Create default categories if none exist
            categories = await category_service.get_or_create_default_categories(session, user.id)
            await session.commit()
        
        await callback.message.edit_text(
            i18n.get("receipt.choose_category", locale),
            reply_markup=get_categories_keyboard(categories, locale, action='select')
        )


@router.callback_query(F.data.startswith("select_category:"), ExpenseStates.waiting_for_category)
async def process_category_selection(callback: CallbackQuery, state: FSMContext):
    """Process category selection"""
    category_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Get category
        category = await category_service.get_category_by_id(session, category_id, user.id)
        
        if not category:
            await callback.answer(i18n.get("errors.unknown", locale))
            return
        
        # Get state data
        data = await state.get_data()
        
        # Create transaction
        amount_primary = Decimal(data.get('amount_primary', data['amount']))
        exchange_rate = Decimal(data.get('exchange_rate', '1.0000'))
        
        transaction = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal(data['amount']),
            currency=data['currency'],
            category_id=category.id,
            description=data.get('description'),
            transaction_date=data['transaction_date'],
            amount_primary=amount_primary,
            exchange_rate=exchange_rate
        )
        
        await session.commit()
        
        # Get today's spending
        today_total, _ = await transaction_service.get_today_spending(session, user.id)
        
        # Format response
        amount_formatted = expense_parser.format_amount(Decimal(data['amount']), data['currency'])
        today_formatted = expense_parser.format_amount(today_total, user.primary_currency)
        category_name = category.get_name(locale)
        
        response = f"{i18n.get('receipt.saved', locale)} "
        response += f"{amount_formatted} {category.icon} {category_name}"
        
        if data.get('description'):
            response += f" ({data['description']})"
        
        response += f"\n\n{i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
        
        await callback.message.edit_text(response)
        await state.clear()


@router.callback_query(F.data == "edit_transaction", ExpenseStates.waiting_for_category)
async def edit_transaction(callback: CallbackQuery, state: FSMContext):
    """Edit transaction before saving"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
    
    # TODO: Implement transaction editing
    await callback.answer("Редактирование в разработке", show_alert=True)


@router.callback_query(F.data == "cancel")
async def cancel_expense(callback: CallbackQuery, state: FSMContext):
    """Cancel expense creation"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code if user else 'ru'
    
    await callback.message.edit_text(i18n.get("buttons.cancel", locale))
    await state.clear()


@router.message(F.text & ~F.text.startswith('/'))
async def process_text_expense(message: Message, state: FSMContext):
    """Process text message as potential expense input (general handler)"""
    telegram_id = message.from_user.id
    text = message.text.strip()
    
    # Skip if text starts with emoji (likely a keyboard button)
    if text and any(text.startswith(emoji) for emoji in ['➕', '📷', '📊', '📈', '📉', '📂', '💰', '📤', '⚙️']):
        return
    
    # Try to parse expense
    parsed = expense_parser.parse_expense(text)
    
    if not parsed:
        # Not recognized as expense format
        async with get_session() as session:
            user = await user_service.get_user_by_telegram_id(session, telegram_id)
            locale = user.language_code if user else 'ru'
        
        await message.answer(
            i18n.get("manual_input.error_format", locale),
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    # Continue with expense processing (same as process_expense_input)
    await state.set_state(ExpenseStates.waiting_for_amount)
    await process_expense_input(message, state)