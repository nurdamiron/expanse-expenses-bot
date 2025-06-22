from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional

from src.database.models import Category
from src.utils.i18n import i18n


def get_categories_keyboard(
    categories: List[Category],
    locale: str = 'ru',
    action: str = 'select',
    show_cancel: bool = True
) -> InlineKeyboardMarkup:
    """
    Create categories keyboard
    
    Args:
        categories: List of Category objects
        locale: User language
        action: Action prefix for callback data
        show_cancel: Whether to show cancel button
    """
    builder = InlineKeyboardBuilder()
    
    # Add category buttons
    for category in categories:
        name = category.get_name(locale)
        button = InlineKeyboardButton(
            text=f"{category.icon} {name}",
            callback_data=f"{action}_category:{category.id}"
        )
        builder.row(button)
    
    # Add management buttons if needed
    if action == 'select':
        builder.row(
            InlineKeyboardButton(
                text="➕ Новая категория",
                callback_data="new_category"
            )
        )
    
    # Add cancel button
    if show_cancel:
        builder.row(
            InlineKeyboardButton(
                text=i18n.get_button("cancel", locale),
                callback_data="cancel"
            )
        )
    
    return builder.as_markup()


def get_category_actions_keyboard(
    category_id: str,
    locale: str = 'ru'
) -> InlineKeyboardMarkup:
    """Get category action buttons"""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("edit", locale),
            callback_data=f"edit_category:{category_id}"
        ),
        InlineKeyboardButton(
            text=i18n.get_button("delete", locale),
            callback_data=f"delete_category:{category_id}"
        )
    )
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("back", locale),
            callback_data="back"
        )
    )
    
    return builder.as_markup()


def get_category_icons_keyboard(locale: str = 'ru') -> InlineKeyboardMarkup:
    """Get category icon selection keyboard"""
    builder = InlineKeyboardBuilder()
    
    icons = [
        "🍔", "🚗", "🛒", "🏠", "💊", "🎬", "📚", "💰",
        "✈️", "🎮", "🎨", "🏋️", "💄", "🎁", "📱", "🐾",
        "🔧", "💡", "🌱", "🎯", "🏖️", "🍺", "☕", "🚕"
    ]
    
    # Create rows of 6 icons each
    for i in range(0, len(icons), 6):
        row_icons = icons[i:i+6]
        buttons = [
            InlineKeyboardButton(
                text=icon,
                callback_data=f"icon:{icon}"
            )
            for icon in row_icons
        ]
        builder.row(*buttons)
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("cancel", locale),
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()


def get_default_categories_keyboard(locale: str = 'ru') -> InlineKeyboardMarkup:
    """Get default categories for quick selection"""
    builder = InlineKeyboardBuilder()
    
    # Default category keys
    default_categories = [
        ('food', '🍔'),
        ('transport', '🚗'),
        ('shopping', '🛒'),
        ('other', '💰')
    ]
    
    buttons = []
    for key, icon in default_categories:
        name = i18n.get_category(key, locale)
        buttons.append(
            InlineKeyboardButton(
                text=f"{icon} {name}",
                callback_data=f"quick_category:{key}"
            )
        )
    
    # Add buttons in rows of 2
    builder.row(*buttons[:2])
    builder.row(*buttons[2:])
    
    # Add more options button
    builder.row(
        InlineKeyboardButton(
            text="📋 Все категории",
            callback_data="all_categories"
        )
    )
    
    # Add edit and cancel buttons
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("edit", locale),
            callback_data="edit_transaction"
        ),
        InlineKeyboardButton(
            text=i18n.get_button("cancel", locale),
            callback_data="cancel"
        )
    )
    
    return builder.as_markup()