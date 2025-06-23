from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from src.database import get_session
from src.services.user import UserService
from src.bot.states import ExpenseStates
from src.utils.i18n import i18n

router = Router()
user_service = UserService()


@router.message(F.text.startswith("➕"))
async def handle_add_expense(message: Message, state: FSMContext):
    """Handle add expense button"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Show company mode if active
        company_text = ""
        if user.active_company_id:
            from src.database.models import Company
            from sqlalchemy import select
            
            result = await session.execute(
                select(Company).where(Company.id == user.active_company_id)
            )
            company = result.scalar_one_or_none()
            if company:
                company_text = f"\n💼 <b>{i18n.get('company.mode_indicator', locale, name=company.name)}</b>\n"
    
    # Clear any existing state
    await state.clear()
    
    # Create inline keyboard for quick actions
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text=f"📷 {i18n.get('keyboard.add_photo', locale)}",
        callback_data="expense:photo"
    )
    builder.button(
        text=f"✏️ {i18n.get('buttons.enter_manually', locale)}",
        callback_data="expense:manual"
    )
    
    # Layout: 2 buttons in one row
    builder.adjust(2)
    
    text = f"➕ <b>{i18n.get('manual_input.add_expense', locale)}</b>{company_text}\n\n"
    text += "Выберите способ добавления:"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )




@router.message(F.text.startswith("📂"))
async def handle_categories(message: Message, state: FSMContext):
    """Handle categories button"""
    # Redirect to categories command
    from . import categories
    await categories.cmd_categories(message, state)


@router.message(F.text.startswith("📤"))
async def handle_export(message: Message, state: FSMContext):
    """Handle export button"""
    # Redirect to export command
    from . import export
    await export.cmd_export(message, state)




@router.message(F.text.startswith("💼"))
async def handle_company(message: Message, state: FSMContext):
    """Handle company button"""
    # Redirect to company command
    from . import company
    await company.cmd_company(message)