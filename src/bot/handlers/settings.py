from typing import Optional
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.bot.states import SettingsStates
from src.services.user import UserService
from src.utils.i18n import i18n
from src.utils.text_parser import ExpenseParser
from src.core.config import settings

router = Router()
user_service = UserService()
expense_parser = ExpenseParser()


@router.message(F.text == "/settings")
@router.message(F.text.startswith("⚙️"))
async def cmd_settings(message: Message, state: FSMContext):
    """Show settings menu"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            # User not found - silently return (should not happen with proper bot setup)
            return
        
        locale = user.language_code
        
        # Clear any existing state
        await state.clear()
        
        # Create menu text
        text = f"<b>⚙️ {i18n.get('settings.title', locale)}</b>\n\n"
        text += "Выберите настройку:"
        
        # Create inline keyboard with all settings options
        builder = InlineKeyboardBuilder()
        
        # Categories management
        builder.button(
            text=f"📂 {i18n.get('keyboard.categories', locale)}",
            callback_data="settings:categories"
        )
        
        # Export data
        builder.button(
            text=f"📤 {i18n.get('keyboard.export', locale)}",
            callback_data="settings:export"
        )
        
        # Language
        lang_text = "🇷🇺 Русский" if locale == 'ru' else "🇰🇿 Қазақша"
        builder.button(
            text=f"🌐 Язык: {lang_text}",
            callback_data="settings:language"
        )
        
        # Currency
        currency_symbol = expense_parser.CURRENCY_SYMBOLS.get(user.primary_currency, '')
        builder.button(
            text=f"💱 Валюта: {currency_symbol} {user.primary_currency}",
            callback_data="settings:currency"
        )
        
        # Timezone
        builder.button(
            text=f"🕐 Часовой пояс: {user.timezone}",
            callback_data="settings:timezone"
        )
        
        # Get notifications setting from user settings
        user_settings = user.settings or {}
        notifications_enabled = user_settings.get('notifications', True)
        notif_icon = "✅" if notifications_enabled else "❌"
        builder.button(
            text=f"🔔 Уведомления: {notif_icon}",
            callback_data="settings:notifications"
        )
        
        # Limits
        builder.button(
            text=f"🎯 {i18n.get('settings.limits', locale)}",
            callback_data="settings:limits"
        )
        
        # Clear data
        builder.button(
            text=f"🗑 {i18n.get('settings.clear_data', locale)}",
            callback_data="settings:clear_data"
        )
        
        # Layout: 1 button per row (single column)
        builder.adjust(1)
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        
        await state.set_state(SettingsStates.main_menu)


@router.callback_query(F.data == "settings:language", StateFilter(SettingsStates.main_menu))
async def show_language_settings(callback: CallbackQuery, state: FSMContext):
    """Show language selection"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        text = f"<b>{i18n.get('settings.language', locale)}</b>\n\n"
        current_lang_text = "Текущий язык" if locale == 'ru' else "Ағымдағы тіл"
        text += f"{current_lang_text}: {'🇷🇺 Русский' if locale == 'ru' else '🇰🇿 Қазақша'}\n\n"
        choose_lang_text = "Выберите язык" if locale == 'ru' else "Тілді таңдаңыз"
        text += f"{choose_lang_text}:"
        
        builder = InlineKeyboardBuilder()
        
        if locale != 'ru':
            builder.row(
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="set_language:ru"
                )
            )
        
        if locale != 'kz':
            builder.row(
                InlineKeyboardButton(
                    text="🇰🇿 Қазақша",
                    callback_data="set_language:kz"
                )
            )
        
        builder.row(
            InlineKeyboardButton(
                text=i18n.get_button("back", locale),
                callback_data="back_to_settings"
            )
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        
        await state.set_state(SettingsStates.changing_language)


@router.callback_query(F.data.startswith("set_language:"), StateFilter(SettingsStates.changing_language))
async def set_language(callback: CallbackQuery, state: FSMContext):
    """Set new language"""
    new_language = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        await user_service.update_user_language(session, user.id, new_language)
        
        await callback.answer(
            i18n.get("welcome.language_set", new_language)
        )
        
        # Update keyboard with new language
        from src.bot.keyboards.main import get_main_keyboard
        await callback.message.answer(
            "✅",  # Simple confirmation
            reply_markup=get_main_keyboard(new_language)
        )
        
        # Return to settings with new language
        await state.set_state(SettingsStates.main_menu)
        await cmd_settings(callback.message, state)


@router.callback_query(F.data == "settings:currency", StateFilter(SettingsStates.main_menu))
async def show_currency_settings(callback: CallbackQuery, state: FSMContext):
    """Show currency selection"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        text = f"<b>{i18n.get('settings.currency', locale)}</b>\n\n"
        current_currency_text = "Текущая валюта" if locale == 'ru' else "Ағымдағы валюта"
        text += f"{current_currency_text}: {user.primary_currency}\n\n"
        choose_currency_text = "Выберите основную валюту" if locale == 'ru' else "Негізгі валютаны таңдаңыз"
        text += f"{choose_currency_text}:"
        
        builder = InlineKeyboardBuilder()
        
        for currency in settings.supported_currencies:
            if currency != user.primary_currency:
                symbol = expense_parser.CURRENCY_SYMBOLS.get(currency, '')
                builder.add(
                    InlineKeyboardButton(
                        text=f"{symbol} {currency}",
                        callback_data=f"set_primary_currency:{currency}"
                    )
                )
        
        builder.adjust(2)  # 2 buttons per row
        
        builder.row(
            InlineKeyboardButton(
                text=i18n.get_button("back", locale),
                callback_data="back_to_settings"
            )
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        
        await state.set_state(SettingsStates.changing_currency)


@router.callback_query(F.data.startswith("set_primary_currency:"), StateFilter(SettingsStates.changing_currency))
async def set_primary_currency(callback: CallbackQuery, state: FSMContext):
    """Set user's primary currency"""
    currency = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        await user_service.update_user_currency(session, user.id, currency)
        
        locale = user.language_code
        success_text = f"✅ Основная валюта изменена на {currency}" if locale == 'ru' else f"✅ Негізгі валюта {currency} болып өзгертілді"
        await callback.answer(success_text)
        
        # Return to settings
        await state.set_state(SettingsStates.main_menu)
        await cmd_settings(callback.message, state)


@router.callback_query(F.data == "settings:notifications", StateFilter(SettingsStates.main_menu))
async def toggle_notifications(callback: CallbackQuery, state: FSMContext):
    """Toggle notifications on/off"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Get current state
        current_settings = user.settings or {}
        notifications_enabled = current_settings.get('notifications_enabled', True)
        
        # Toggle
        current_settings['notifications_enabled'] = not notifications_enabled
        user.settings = current_settings
        
        await session.commit()
        
        if locale == 'ru':
            new_state = "включены" if not notifications_enabled else "выключены"
            answer_text = f"✅ Уведомления {new_state}"
        else:
            new_state = "қосылды" if not notifications_enabled else "өшірілді"
            answer_text = f"✅ Хабарландырулар {new_state}"
        await callback.answer(answer_text)
        
        # Refresh settings
        await cmd_settings(callback.message, state)


@router.callback_query(F.data == "settings:limits", StateFilter(SettingsStates.main_menu))
async def show_limits_settings(callback: CallbackQuery, state: FSMContext):
    """Show spending limits settings"""
    telegram_id = callback.from_user.id
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
    message_text = "Управление лимитами в разработке" if locale == 'ru' else "Лимиттерді басқару әзірленуде"
    await callback.answer(message_text, show_alert=True)


@router.callback_query(F.data == "settings:timezone", StateFilter(SettingsStates.main_menu))
async def show_timezone_settings(callback: CallbackQuery, state: FSMContext):
    """Show timezone selection"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        text = f"<b>{i18n.get('settings.timezone', locale)}</b>\n\n"
        current_tz_text = "Текущий часовой пояс" if locale == 'ru' else "Ағымдағы уақыт белдеуі"
        text += f"{current_tz_text}: {user.timezone}\n\n"
        choose_tz_text = "Выберите часовой пояс" if locale == 'ru' else "Уақыт белдеуін таңдаңыз"
        text += f"{choose_tz_text}:"
        
        builder = InlineKeyboardBuilder()
        
        timezones = [
            ("🇰🇿 Алматы (UTC+6)", "Asia/Almaty"),
            ("🇰🇿 Астана (UTC+6)", "Asia/Qostanay"),
            ("🇷🇺 Москва (UTC+3)", "Europe/Moscow"),
            ("🇷🇺 Екатеринбург (UTC+5)", "Asia/Yekaterinburg"),
            ("🇷🇺 Новосибирск (UTC+7)", "Asia/Novosibirsk"),
            ("🇷🇺 Владивосток (UTC+10)", "Asia/Vladivostok"),
        ]
        
        for tz_name, tz_value in timezones:
            if tz_value != user.timezone:
                builder.row(
                    InlineKeyboardButton(
                        text=tz_name,
                        callback_data=f"set_timezone:{tz_value}"
                    )
                )
        
        builder.row(
            InlineKeyboardButton(
                text=i18n.get_button("back", locale),
                callback_data="back_to_settings"
            )
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        
        await state.set_state(SettingsStates.changing_timezone)


@router.callback_query(F.data.startswith("set_timezone:"), StateFilter(SettingsStates.changing_timezone))
async def set_timezone(callback: CallbackQuery, state: FSMContext):
    """Set new timezone"""
    timezone = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        await user_service.update_user_timezone(session, user.id, timezone)
        
        locale = user.language_code
        success_text = f"✅ Часовой пояс изменен на {timezone}" if locale == 'ru' else f"✅ Уақыт белдеуі {timezone} болып өзгертілді"
        await callback.answer(success_text)
        
        # Return to settings
        await state.set_state(SettingsStates.main_menu)
        await cmd_settings(callback.message, state)


@router.callback_query(F.data == "settings:clear_data", StateFilter(SettingsStates.main_menu))
async def show_clear_data_confirmation(callback: CallbackQuery, state: FSMContext):
    """Show clear data confirmation dialog"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Get transaction count
        from src.services.transaction import TransactionService
        transaction_service = TransactionService()
        transactions = await transaction_service.get_user_transactions(
            session, user.id, limit=None
        )
        transaction_count = len(transactions)
        
        if transaction_count == 0:
            no_data_text = "У вас нет данных для удаления" if locale == 'ru' else "Сізде жою үшін деректер жоқ"
            await callback.answer(no_data_text, show_alert=True)
            return
        
        # Warning text
        if locale == 'ru':
            text = f"<b>⚠️ Удаление всех данных</b>\n\n"
            text += f"Вы уверены, что хотите удалить все ваши данные?\n\n"
            text += f"Будет удалено:\n"
            text += f"• {transaction_count} транзакций\n"
            text += f"• Вся история расходов\n"
            text += f"• Все настройки категорий\n\n"
            text += f"<b>Это действие необратимо!</b>"
        else:
            text = f"<b>⚠️ Барлық деректерді жою</b>\n\n"
            text += f"Барлық деректеріңізді жойғыңыз келетініне сенімдісіз бе?\n\n"
            text += f"Жойылады:\n"
            text += f"• {transaction_count} транзакция\n"
            text += f"• Барлық шығыстар тарихы\n"
            text += f"• Барлық санат параметрлері\n\n"
            text += f"<b>Бұл әрекетті қайтару мүмкін емес!</b>"
        
        builder = InlineKeyboardBuilder()
        
        # Confirmation buttons
        confirm_text = "🗑 Да, удалить всё" if locale == 'ru' else "🗑 Иә, барлығын жою"
        cancel_text = "❌ Отмена" if locale == 'ru' else "❌ Бас тарту"
        
        builder.row(
            InlineKeyboardButton(
                text=confirm_text,
                callback_data="confirm_clear_data"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=cancel_text,
                callback_data="back_to_settings"
            )
        )
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        
        await state.set_state(SettingsStates.confirming_clear_data)


@router.callback_query(F.data == "confirm_clear_data", StateFilter(SettingsStates.confirming_clear_data))
async def confirm_clear_data(callback: CallbackQuery, state: FSMContext):
    """Clear all user data after confirmation"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Show processing message
        processing_text = "🔄 Удаляю данные..." if locale == 'ru' else "🔄 Деректерді жою..."
        await callback.message.edit_text(processing_text)
        
        try:
            # Delete all transactions
            from src.services.transaction import TransactionService
            from src.services.category import CategoryService
            from sqlalchemy import delete
            from src.database.models import Transaction, Category
            
            # Delete all user transactions
            await session.execute(
                delete(Transaction).where(Transaction.user_id == user.id)
            )
            
            # Delete all non-default categories
            await session.execute(
                delete(Category).where(
                    Category.user_id == user.id,
                    Category.is_default == False
                )
            )
            
            # Reset user settings to defaults
            user.settings = {}
            
            await session.commit()
            
            # Recreate default categories
            category_service = CategoryService()
            await category_service.create_default_categories(session, user.id)
            await session.commit()
            
            # Success message
            success_text = "✅ Все данные успешно удалены" if locale == 'ru' else "✅ Барлық деректер сәтті жойылды"
            await callback.message.edit_text(success_text)
            
            # Return to main menu after 2 seconds
            import asyncio
            await asyncio.sleep(2)
            
            # Send welcome message
            welcome_text = i18n.get("welcome.tutorial", locale)
            await callback.message.answer(welcome_text)
            
        except Exception as e:
            error_text = "❌ Ошибка при удалении данных" if locale == 'ru' else "❌ Деректерді жою кезінде қате"
            await callback.message.edit_text(error_text)
            
        await state.clear()


@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: CallbackQuery, state: FSMContext):
    """Return to main settings menu"""
    await state.set_state(SettingsStates.main_menu)
    await cmd_settings(callback.message, state)