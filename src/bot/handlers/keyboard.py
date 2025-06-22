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
    
    await state.set_state(ExpenseStates.waiting_for_amount)
    await message.answer(
        i18n.get("manual_input.add_expense", locale),
        parse_mode="HTML"
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


@router.message(F.text.startswith("⚙️"))
async def handle_settings(message: Message, state: FSMContext):
    """Handle settings button"""
    # Redirect to settings command
    from . import settings
    await settings.cmd_settings(message, state)