from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from src.utils.i18n import i18n


def get_main_keyboard(locale: str = 'ru') -> ReplyKeyboardMarkup:
    """Get main keyboard with all functions"""
    builder = ReplyKeyboardBuilder()
    
    # Row 1 - Add expense
    builder.row(
        KeyboardButton(text=f"➕ {i18n.get('keyboard.add_expense', locale)}")
    )
    
    # Row 2 - Reports
    builder.row(
        KeyboardButton(text=f"📊 {i18n.get('keyboard.report_day', locale)}"),
        KeyboardButton(text=f"📈 {i18n.get('keyboard.report_week', locale)}"),
        KeyboardButton(text=f"📉 {i18n.get('keyboard.report_month', locale)}")
    )
    
    # Row 3 - Categories and stats
    builder.row(
        KeyboardButton(text=f"📂 {i18n.get('keyboard.categories', locale)}"),
        KeyboardButton(text=f"💰 {i18n.get('keyboard.by_category', locale)}")
    )
    
    # Row 4 - Export and settings
    builder.row(
        KeyboardButton(text=f"📤 {i18n.get('keyboard.export', locale)}"),
        KeyboardButton(text=f"⚙️ {i18n.get('keyboard.settings', locale)}")
    )
    
    return builder.as_markup(resize_keyboard=True)