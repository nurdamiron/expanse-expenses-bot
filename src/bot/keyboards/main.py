from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from src.utils.i18n import i18n


def get_main_keyboard(locale: str = 'ru', company_name: str = None) -> ReplyKeyboardMarkup:
    """Get simplified main keyboard"""
    builder = ReplyKeyboardBuilder()
    
    # Add company mode indicator at the top if active
    if company_name:
        builder.row(
            KeyboardButton(text=f"🏢 {company_name}")
        )
    
    # Row 1/2 - Add expense
    expense_text = f"➕ {i18n.get('keyboard.add_expense', locale)}"
    
    # Row 1/2 - Main actions (2 buttons)
    builder.row(
        KeyboardButton(text=expense_text),
        KeyboardButton(text=f"📊 {i18n.get('keyboard.analytics', locale)}")
    )
    
    # Row 2/3 - Settings and Company (2 buttons)
    builder.row(
        KeyboardButton(text=f"⚙️ {i18n.get('keyboard.settings', locale)}"),
        KeyboardButton(text=f"💼 {i18n.get('keyboard.company', locale)}")
    )
    
    return builder.as_markup(resize_keyboard=True)