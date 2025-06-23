"""Settings callback handlers"""
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from src.database import get_session
from src.bot.states import SettingsStates
from src.services.user import UserService
from src.utils.i18n import i18n

router = Router()
user_service = UserService()


@router.callback_query(F.data == "settings:categories", StateFilter(SettingsStates.main_menu))
async def handle_categories_from_settings(callback: CallbackQuery, state: FSMContext):
    """Handle categories button from settings"""
    # Import to avoid circular imports
    from .categories import cmd_categories
    
    # Clear settings state
    await state.clear()
    
    # Call categories handler
    await cmd_categories(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "settings:export", StateFilter(SettingsStates.main_menu))
async def handle_export_from_settings(callback: CallbackQuery, state: FSMContext):
    """Handle export button from settings"""
    # Import to avoid circular imports
    from .export import cmd_export
    
    # Clear settings state
    await state.clear()
    
    # Call export handler
    await cmd_export(callback.message, state)
    await callback.answer()


@router.callback_query(F.data.startswith("settings:"), StateFilter(SettingsStates.main_menu))
async def handle_other_settings(callback: CallbackQuery, state: FSMContext):
    """Handle other settings callbacks"""
    action = callback.data.split(":")[1]
    
    # For now, show "in development" for other settings
    if action in ["timezone", "limits", "clear_data"]:
        await callback.answer("🚧 Эта функция в разработке", show_alert=True)
    else:
        await callback.answer()