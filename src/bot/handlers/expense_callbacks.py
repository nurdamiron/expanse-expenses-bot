"""Expense callback handlers"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from src.database import get_session
from src.bot.states import ExpenseStates
from src.services.user import UserService
from src.utils.i18n import i18n

router = Router()
user_service = UserService()


@router.callback_query(F.data == "expense:photo")
async def handle_expense_photo(callback: CallbackQuery, state: FSMContext):
    """Handle photo expense option"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await callback.answer()
            return
        
        locale = user.language_code
    
    await state.set_state(ExpenseStates.waiting_for_photo)
    
    text = f"📷 {i18n.get('receipt.send_photo', locale)}"
    if not user.settings or not user.settings.get('ocr_enabled', True):
        text += f"\n\n💡 {i18n.get('receipt.ocr_disabled_hint', locale)}"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "expense:manual")
async def handle_expense_manual(callback: CallbackQuery, state: FSMContext):
    """Handle manual expense option"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await callback.answer()
            return
        
        locale = user.language_code
    
    await state.set_state(ExpenseStates.waiting_for_amount)
    
    text = i18n.get("receipt.enter_amount", locale)
    await callback.message.edit_text(text)
    await callback.answer()