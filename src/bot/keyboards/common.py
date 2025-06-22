from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List, Tuple, Optional

from src.utils.i18n import i18n


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Get language selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("language_ru"),
            callback_data="lang:ru"
        ),
        InlineKeyboardButton(
            text=i18n.get_button("language_kz"),
            callback_data="lang:kz"
        )
    )
    
    return builder.as_markup()


def get_cancel_keyboard(locale: str = 'ru') -> InlineKeyboardMarkup:
    """Get cancel button keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("cancel", locale),
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_confirm_keyboard(locale: str = 'ru') -> InlineKeyboardMarkup:
    """Get confirm/cancel keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("confirm", locale),
            callback_data="confirm"
        ),
        InlineKeyboardButton(
            text=i18n.get_button("cancel", locale),
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_back_keyboard(locale: str = 'ru') -> InlineKeyboardMarkup:
    """Get back button keyboard"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("back", locale),
            callback_data="back"
        )
    )
    
    return builder.as_markup()


def get_currency_save_keyboard(locale: str = 'ru', show_both: bool = True) -> InlineKeyboardMarkup:
    """Get currency save options keyboard"""
    builder = InlineKeyboardBuilder()
    
    buttons = [
        InlineKeyboardButton(
            text=i18n.get_button("save_tenge", locale),
            callback_data="currency:tenge"
        ),
        InlineKeyboardButton(
            text=i18n.get_button("save_original", locale),
            callback_data="currency:original"
        )
    ]
    
    if show_both:
        buttons.append(
            InlineKeyboardButton(
                text=i18n.get_button("save_both", locale),
                callback_data="currency:both"
            )
        )
    
    builder.row(*buttons[:2])
    if show_both:
        builder.row(buttons[2])
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("cancel", locale),
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def create_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
    locale: str = 'ru'
) -> InlineKeyboardMarkup:
    """Create pagination keyboard"""
    builder = InlineKeyboardBuilder()
    
    buttons = []
    
    # Previous button
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=f"{callback_prefix}:{current_page - 1}"
            )
        )
    
    # Page indicator
    buttons.append(
        InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="noop"
        )
    )
    
    # Next button
    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=f"{callback_prefix}:{current_page + 1}"
            )
        )
    
    builder.row(*buttons)
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("back", locale),
            callback_data="back"
        )
    )
    
    return builder.as_markup()


def create_inline_keyboard(
    buttons: List[Tuple[str, str]],
    row_width: int = 2
) -> InlineKeyboardMarkup:
    """
    Create inline keyboard from button list
    
    Args:
        buttons: List of (text, callback_data) tuples
        row_width: Number of buttons per row
    """
    builder = InlineKeyboardBuilder()
    
    for i in range(0, len(buttons), row_width):
        row_buttons = []
        for j in range(row_width):
            if i + j < len(buttons):
                text, callback_data = buttons[i + j]
                row_buttons.append(
                    InlineKeyboardButton(text=text, callback_data=callback_data)
                )
        builder.row(*row_buttons)
    
    return builder.as_markup()