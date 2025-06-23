"""Analytics menu handler"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from src.database import get_session
from src.services.user import UserService
from src.utils.i18n import i18n

router = Router()
user_service = UserService()


@router.message(F.text.startswith("📊"))
async def analytics_menu(message: Message, state: FSMContext):
    """Show analytics menu with all report options"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            # User not found - silently return (should not happen with proper bot setup)
            return
        
        locale = user.language_code
        
        # Check if in company mode
        company_text = ""
        if user.active_company and user.active_company.name:
            company_text = f"\n💼 <b>{user.active_company.name}</b>\n"
    
    # Clear any existing state
    await state.clear()
    
    # Create inline keyboard with analytics options
    builder = InlineKeyboardBuilder()
    
    # Period-based reports (first row - most used)
    builder.button(
        text=f"📊 За день",
        callback_data="analytics:day"
    )
    builder.button(
        text=f"📈 За неделю",
        callback_data="analytics:week"
    )
    
    # More periods (second row)
    builder.button(
        text=f"📉 За месяц",
        callback_data="analytics:month"
    )
    builder.button(
        text=f"📋 За все время",
        callback_data="analytics:all_time"
    )
    
    # Analysis options (third row)
    builder.button(
        text=f"💰 По категориям",
        callback_data="analytics:categories"
    )
    builder.button(
        text=f"📤 Экспорт",
        callback_data="analytics:export"
    )
    
    # Custom period (fourth row, temporarily disabled)
    # builder.button(
    #     text="📅 Произвольный период",
    #     callback_data="analytics:custom"
    # )
    
    # Layout: 2 buttons per row
    builder.adjust(2, 2, 2)
    
    text = f"📊 <b>{i18n.get('keyboard.analytics', locale)}</b>{company_text}\n"
    text += "Выберите тип отчета:"
    
    await message.answer(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("analytics:"))
async def process_analytics_choice(callback: CallbackQuery, state: FSMContext):
    """Process analytics menu choice"""
    action = callback.data.split(":")[1]
    
    # Create a fake message with user info from callback
    class FakeMessage:
        def __init__(self, callback_query):
            self.from_user = callback_query.from_user
            self.bot = callback_query.bot
            self.answer = callback_query.message.answer
            self.answer_document = callback_query.message.answer_document
            self.answer_photo = callback_query.message.answer_photo
    
    fake_message = FakeMessage(callback)
    
    # Import handlers to avoid circular imports
    if action == "day":
        from .reports import report_day
        await report_day(fake_message)
    elif action == "week":
        from .reports import report_week
        await report_week(fake_message)
    elif action == "month":
        from .reports import report_month
        await report_month(fake_message)
    elif action == "categories":
        from .reports import report_by_category
        await report_by_category(fake_message)
    elif action == "all_time":
        from .reports import report_all_time
        await report_all_time(fake_message)
    elif action == "export":
        from .export import cmd_export
        await cmd_export(fake_message, state)
    elif action == "custom":
        await callback.answer("🚧 Эта функция в разработке", show_alert=True)
        return
    
    await callback.answer()