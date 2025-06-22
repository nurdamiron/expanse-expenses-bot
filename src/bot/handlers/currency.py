from typing import Optional
from datetime import datetime
from decimal import Decimal, InvalidOperation
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.services.user import UserService
from src.services.currency import currency_service
from src.utils.text_parser import ExpenseParser
from src.utils.i18n import i18n
from src.core.config import settings

router = Router()
user_service = UserService()
expense_parser = ExpenseParser()


@router.message(F.text == "/rates")
async def cmd_rates(message: Message):
    """Show current exchange rates"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        base_currency = user.primary_currency
        
        # Send loading message
        loading_msg = await message.answer("⏳ Загружаю актуальные курсы...")
        
        # Get all rates
        rates = await currency_service.get_all_rates(base_currency, session)
        
        if not rates:
            await loading_msg.edit_text(
                i18n.get("currency.error_fetch", locale)
            )
            return
        
        # Format rates message
        text = f"<b>{i18n.get('rates.title', locale)}</b>\n\n"
        
        # Currency emoji map
        currency_emoji = {
            'USD': '🇺🇸',
            'EUR': '🇪🇺',
            'RUB': '🇷🇺',
            'KZT': '🇰🇿',
            'CNY': '🇨🇳',
            'KRW': '🇰🇷',
            'TRY': '🇹🇷'
        }
        
        for currency, data in sorted(rates.items()):
            emoji = currency_emoji.get(currency, '💱')
            rate = data['rate']
            change = data['change_percent']
            direction = data['direction']
            
            # Format rate
            rate_str = f"{rate:.4f}".rstrip('0').rstrip('.')
            currency_symbol = expense_parser.CURRENCY_SYMBOLS.get(
                base_currency, base_currency
            )
            
            text += f"{emoji} {currency}: {rate_str}{currency_symbol}"
            
            # Add change indicator
            if direction == 'up':
                text += f" {i18n.get('rates.change_up', locale, percent=abs(change))}"
            elif direction == 'down':
                text += f" {i18n.get('rates.change_down', locale, percent=abs(change))}"
            
            text += "\n"
        
        # Add update time and source
        text += f"\n{i18n.get('rates.updated', locale)}: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        text += f"{i18n.get('rates.source', locale)}: Multiple APIs"
        
        # Create keyboard
        builder = InlineKeyboardBuilder()
        
        builder.row(
            InlineKeyboardButton(
                text=i18n.get("rates.history", locale),
                callback_data="rates:history"
            ),
            InlineKeyboardButton(
                text=i18n.get("rates.settings", locale),
                callback_data="rates:settings"
            )
        )
        
        await loading_msg.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )


@router.message(F.text.startswith("/convert"))
async def cmd_convert(message: Message):
    """Convert currency"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Parse command
        parts = message.text.split()
        
        if len(parts) < 4:
            # Show usage
            usage = "Использование: /convert 100 USD to KZT\n"
            usage += "Или: /convert 50 EUR KZT\n\n"
            usage += "Поддерживаемые валюты:\n"
            
            for currency in settings.supported_currencies:
                symbol = expense_parser.CURRENCY_SYMBOLS.get(currency, '')
                usage += f"{symbol} {currency}\n"
            
            await message.answer(usage)
            return
        
        try:
            # Parse amount and currencies
            amount = Decimal(parts[1])
            from_currency = parts[2].upper()
            
            # Handle "to" word
            if len(parts) == 5 and parts[3].lower() in ['to', 'в']:
                to_currency = parts[4].upper()
            else:
                to_currency = parts[3].upper()
            
            # Validate currencies
            if from_currency not in settings.supported_currencies:
                await message.answer(
                    f"❌ Неизвестная валюта: {from_currency}\n"
                    f"Используйте одну из: {', '.join(settings.supported_currencies)}"
                )
                return
            
            if to_currency not in settings.supported_currencies:
                await message.answer(
                    f"❌ Неизвестная валюта: {to_currency}\n"
                    f"Используйте одну из: {', '.join(settings.supported_currencies)}"
                )
                return
            
            # Convert
            converted, rate = await currency_service.convert_amount(
                amount, from_currency, to_currency, session
            )
            
            if converted is None:
                await message.answer(
                    i18n.get("currency.error_fetch", locale)
                )
                return
            
            # Format response
            from_str = expense_parser.format_amount(amount, from_currency)
            to_str = expense_parser.format_amount(converted, to_currency)
            
            response = f"💱 <b>Конвертация валют</b>\n\n"
            response += f"{from_str} = {to_str}\n\n"
            response += f"Курс {from_currency}/{to_currency}: {rate:.4f}\n"
            response += f"Обновлено: {datetime.now().strftime('%H:%M')}"
            
            # Add reverse conversion button
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text=f"🔄 {to_currency} → {from_currency}",
                    callback_data=f"convert:{amount}:{to_currency}:{from_currency}"
                )
            )
            
            await message.answer(
                response,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            
        except (InvalidOperation, ValueError, IndexError):
            await message.answer(
                "❌ Неверный формат команды\n"
                "Используйте: /convert 100 USD to KZT"
            )


@router.callback_query(F.data.startswith("convert:"))
async def process_convert_callback(callback: CallbackQuery):
    """Process reverse conversion callback"""
    parts = callback.data.split(":")
    
    if len(parts) != 4:
        await callback.answer("Ошибка данных")
        return
    
    try:
        amount = Decimal(parts[1])
        from_currency = parts[2]
        to_currency = parts[3]
        
        async with get_session() as session:
            user = await user_service.get_user_by_telegram_id(session, callback.from_user.id)
            locale = user.language_code if user else 'ru'
            
            # Convert
            converted, rate = await currency_service.convert_amount(
                amount, from_currency, to_currency, session
            )
            
            if converted is None:
                await callback.answer(
                    i18n.get("currency.error_fetch", locale),
                    show_alert=True
                )
                return
            
            # Update message
            from_str = expense_parser.format_amount(amount, from_currency)
            to_str = expense_parser.format_amount(converted, to_currency)
            
            response = f"💱 <b>Конвертация валют</b>\n\n"
            response += f"{from_str} = {to_str}\n\n"
            response += f"Курс {from_currency}/{to_currency}: {rate:.4f}\n"
            response += f"Обновлено: {datetime.now().strftime('%H:%M')}"
            
            # Add reverse button
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text=f"🔄 {to_currency} → {from_currency}",
                    callback_data=f"convert:{converted}:{to_currency}:{from_currency}"
                )
            )
            
            await callback.message.edit_text(
                response,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
            
    except Exception as e:
        await callback.answer("Ошибка конвертации", show_alert=True)


@router.callback_query(F.data == "rates:history")
async def show_rates_history(callback: CallbackQuery):
    """Show exchange rates history"""
    # TODO: Implement rates history chart
    await callback.answer("История курсов в разработке", show_alert=True)


@router.callback_query(F.data == "rates:settings")
async def show_rates_settings(callback: CallbackQuery):
    """Show currency settings"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code if user else 'ru'
        
        text = f"⚙️ <b>Настройки валют</b>\n\n"
        text += f"Основная валюта: {user.primary_currency}\n\n"
        text += "Выберите новую основную валюту:"
        
        # Create currency selection keyboard
        builder = InlineKeyboardBuilder()
        
        for currency in settings.supported_currencies:
            if currency != user.primary_currency:
                symbol = expense_parser.CURRENCY_SYMBOLS.get(currency, '')
                builder.add(
                    InlineKeyboardButton(
                        text=f"{symbol} {currency}",
                        callback_data=f"set_currency:{currency}"
                    )
                )
        
        builder.adjust(2)  # 2 buttons per row
        
        builder.row(
            InlineKeyboardButton(
                text=i18n.get_button("back", locale),
                callback_data="back_to_rates"
            )
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )


@router.callback_query(F.data.startswith("set_currency:"))
async def set_primary_currency(callback: CallbackQuery):
    """Set user's primary currency"""
    currency = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        await user_service.update_user_currency(session, telegram_id, currency)
        
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code if user else 'ru'
        
        await callback.answer(
            f"✅ Основная валюта изменена на {currency}"
        )
        
        # Return to rates
        await cmd_rates(callback.message)


@router.callback_query(F.data == "back_to_rates")
async def back_to_rates(callback: CallbackQuery):
    """Go back to rates display"""
    await cmd_rates(callback.message)


