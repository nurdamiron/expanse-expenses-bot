from typing import List
from datetime import datetime, date, timedelta
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.services.user import UserService
from src.services.transaction import TransactionService
from src.utils.text_parser import ExpenseParser
from src.utils.i18n import i18n

router = Router()
user_service = UserService()
transaction_service = TransactionService()
expense_parser = ExpenseParser()


@router.message(F.text == "/stats")
async def cmd_stats(message: Message):
    """Show statistics"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Get different period statistics
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Get spending for different periods
        today_total, today_count = await transaction_service.get_today_spending(session, user.id)
        week_total, week_count = await transaction_service.get_period_spending(
            session, user.id, week_start, today
        )
        month_total, month_count = await transaction_service.get_period_spending(
            session, user.id, month_start, today
        )
        
        # Get top categories for current month
        top_categories = await transaction_service.get_category_spending(
            session, user.id, month_start, today, limit=3
        )
        
        # Format statistics message
        stats_text = f"<b>{i18n.get('stats.title', locale)}</b>\n\n"
        
        # Today
        stats_text += f"{i18n.get('stats.today', locale)}: "
        stats_text += expense_parser.format_amount(today_total, user.primary_currency)
        stats_text += f" ({today_count})\n"
        
        # Week
        stats_text += f"{i18n.get('stats.week', locale)}: "
        stats_text += expense_parser.format_amount(week_total, user.primary_currency)
        stats_text += f" ({week_count})\n"
        
        # Month
        stats_text += f"{i18n.get('stats.month', locale)}: "
        stats_text += expense_parser.format_amount(month_total, user.primary_currency)
        stats_text += f" ({month_count})\n"
        
        # Top categories
        if top_categories:
            stats_text += f"\n<b>{i18n.get('stats.top_categories', locale)}</b>\n"
            for cat_data in top_categories:
                category = cat_data['category']
                total = cat_data['total']
                count = cat_data['count']
                
                stats_text += f"{category.icon} {category.get_name(locale)}: "
                stats_text += expense_parser.format_amount(total, user.primary_currency)
                stats_text += f" ({count})\n"
        
        # Create inline keyboard for detailed reports
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text=i18n.get("stats.detailed_report", locale),
                callback_data="stats:detailed"
            )
        )
        
        builder.row(
            InlineKeyboardButton(
                text=i18n.get("stats.chart", locale),
                callback_data="stats:chart"
            ),
            InlineKeyboardButton(
                text=i18n.get("stats.export", locale),
                callback_data="stats:export"
            )
        )
        
        await message.answer(
            stats_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )


@router.message(F.text == "/today")
async def cmd_today(message: Message):
    """Show today's expenses"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Get today's transactions
        today = date.today()
        transactions = await transaction_service.get_user_transactions(
            session, user.id,
            start_date=today,
            end_date=today,
            limit=50
        )
        
        if not transactions:
            await message.answer(i18n.get("stats.no_data", locale))
            return
        
        # Format transactions list
        response = f"<b>{i18n.get('commands.today', locale)}</b>\n\n"
        
        total = Decimal('0')
        for tx in transactions:
            amount_str = expense_parser.format_amount(tx.amount, tx.currency)
            category_name = tx.category.get_name(locale) if tx.category else "?"
            
            response += f"{tx.category.icon if tx.category else '❓'} "
            response += f"{amount_str} - {category_name}"
            
            if tx.description:
                response += f" ({tx.description})"
            
            response += f"\n"
            total += tx.amount_primary
        
        response += f"\n<b>{i18n.get('stats.today', locale)}: "
        response += expense_parser.format_amount(total, user.primary_currency)
        response += "</b>"
        
        await message.answer(response, parse_mode="HTML")


@router.message(F.text == "/last")
async def cmd_last(message: Message):
    """Show last 5 transactions"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Get last transactions
        transactions = await transaction_service.get_last_transactions(session, user.id, limit=5)
        
        if not transactions:
            await message.answer(i18n.get("stats.no_data", locale))
            return
        
        # Format transactions list
        response = f"<b>{i18n.get('commands.last', locale)}</b>\n\n"
        
        for i, tx in enumerate(transactions, 1):
            amount_str = expense_parser.format_amount(tx.amount, tx.currency)
            category_name = tx.category.get_name(locale) if tx.category else "?"
            date_str = tx.transaction_date.strftime('%d.%m %H:%M')
            
            response += f"{i}. {tx.category.icon if tx.category else '❓'} "
            response += f"{amount_str} - {category_name}"
            
            if tx.description:
                response += f" ({tx.description})"
            
            response += f"\n   <i>{date_str}</i>\n\n"
        
        # Add inline keyboard for actions
        builder = InlineKeyboardBuilder()
        
        for i, tx in enumerate(transactions[:3], 1):  # Show edit buttons for first 3
            builder.row(
                InlineKeyboardButton(
                    text=f"✏️ {i}",
                    callback_data=f"edit_tx:{tx.id}"
                ),
                InlineKeyboardButton(
                    text=f"🗑 {i}",
                    callback_data=f"delete_tx:{tx.id}"
                )
            )
        
        await message.answer(
            response, 
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data == "stats:detailed")
async def show_detailed_stats(callback: CallbackQuery):
    """Show detailed statistics menu"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
    
    # Create period selection keyboard
    builder = InlineKeyboardBuilder()
    
    periods = [
        ("📅 За сегодня", "period:today"),
        ("📅 За вчера", "period:yesterday"),
        ("📅 За 7 дней", "period:week"),
        ("📅 За 30 дней", "period:month"),
        ("📅 Текущий месяц", "period:current_month"),
        ("📅 Прошлый месяц", "period:last_month"),
    ]
    
    for text, callback_data in periods:
        builder.row(InlineKeyboardButton(text=text, callback_data=callback_data))
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("back", locale),
            callback_data="back_to_stats"
        )
    )
    
    await callback.message.edit_text(
        "Выберите период для детального отчета:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("period:"))
async def show_period_details(callback: CallbackQuery):
    """Show detailed statistics for selected period"""
    period = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Calculate date range based on period
        today = date.today()
        
        if period == "today":
            start_date = end_date = today
        elif period == "yesterday":
            start_date = end_date = today - timedelta(days=1)
        elif period == "week":
            start_date = today - timedelta(days=7)
            end_date = today
        elif period == "month":
            start_date = today - timedelta(days=30)
            end_date = today
        elif period == "current_month":
            start_date = today.replace(day=1)
            end_date = today
        elif period == "last_month":
            last_month = today.replace(day=1) - timedelta(days=1)
            start_date = last_month.replace(day=1)
            end_date = last_month
        
        # Get transactions for period
        transactions = await transaction_service.get_user_transactions(
            session, user.id,
            start_date=start_date,
            end_date=end_date,
            limit=100
        )
        
        # Get category breakdown
        category_spending = await transaction_service.get_category_spending(
            session, user.id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate totals
        total_amount = sum(tx.amount_primary for tx in transactions)
        
        # Format response
        response = f"<b>Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}</b>\n\n"
        response += f"Всего транзакций: {len(transactions)}\n"
        response += f"Общая сумма: {expense_parser.format_amount(total_amount, user.primary_currency)}\n"
        
        if transactions:
            avg_amount = total_amount / len(transactions)
            response += f"Средний чек: {expense_parser.format_amount(avg_amount, user.primary_currency)}\n"
        
        # Category breakdown
        if category_spending:
            response += f"\n<b>По категориям:</b>\n"
            for cat_data in category_spending:
                category = cat_data['category']
                cat_total = cat_data['total']
                cat_count = cat_data['count']
                percentage = (cat_total / total_amount * 100) if total_amount > 0 else 0
                
                response += f"\n{category.icon} {category.get_name(locale)}\n"
                response += f"  {expense_parser.format_amount(cat_total, user.primary_currency)}"
                response += f" ({percentage:.1f}%) - {cat_count} транз.\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("back", locale),
            callback_data="stats:detailed"
        )
    )
    
    await callback.message.edit_text(
        response,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )