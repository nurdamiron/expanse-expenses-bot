from typing import Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.bot.states import CategoryStates
from src.bot.keyboards import (
    get_categories_keyboard,
    get_category_actions_keyboard,
    get_category_icons_keyboard,
    get_confirm_keyboard,
    get_cancel_keyboard,
    get_back_keyboard
)
from src.services.user import UserService
from src.services.category import CategoryService
from src.utils.i18n import i18n

router = Router()
user_service = UserService()
category_service = CategoryService()


@router.message(F.text == "/categories")
async def cmd_categories(message: Message, state: FSMContext):
    """Show categories management menu"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Get user categories
        categories = await category_service.get_user_categories(session, user.id)
        
        if not categories:
            # Create default categories if none exist
            categories = await category_service.get_or_create_default_categories(session, user.id)
            await session.commit()
        
        # Format categories list
        response = f"<b>{i18n.get('commands.categories', locale)}</b>\n\n"
        
        for category in categories:
            response += f"{category.icon} {category.get_name(locale)}\n"
        
        await message.answer(
            response,
            parse_mode="HTML",
            reply_markup=get_categories_keyboard(
                categories, locale, action='manage', show_cancel=False
            )
        )
        
        await state.set_state(CategoryStates.viewing_categories)


@router.callback_query(F.data.startswith("manage_category:"), CategoryStates.viewing_categories)
async def manage_category(callback: CallbackQuery, state: FSMContext):
    """Show category management options"""
    category_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        category = await category_service.get_category_by_id(session, category_id, user.id)
        
        if not category:
            await callback.answer(i18n.get("errors.unknown", locale))
            return
        
        # Store category ID in state
        await state.update_data(category_id=category_id)
        
        text = f"{category.icon} {category.get_name(locale)}\n\n"
        
        if category.is_default:
            text += f"<i>({i18n.get('categories.default', locale) if 'categories.default' in i18n.translations[locale] else 'Стандартная категория'})</i>"
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_category_actions_keyboard(category_id, locale)
        )


@router.callback_query(F.data == "new_category")
async def start_new_category(callback: CallbackQuery, state: FSMContext):
    """Start creating new category"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
    
    await callback.message.edit_text(
        "Введите название категории на русском языке:",
        reply_markup=get_cancel_keyboard(locale)
    )
    
    await state.set_state(CategoryStates.entering_name_ru)


@router.message(CategoryStates.entering_name_ru)
async def process_category_name_ru(message: Message, state: FSMContext):
    """Process Russian category name"""
    telegram_id = message.from_user.id
    name_ru = message.text.strip()
    
    if len(name_ru) > 100:
        async with get_session() as session:
            user = await user_service.get_user_by_telegram_id(session, telegram_id)
            locale = user.language_code
        
        await message.answer(
            "Название слишком длинное. Максимум 100 символов.",
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    await state.update_data(name_ru=name_ru)
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
    
    await message.answer(
        "Введите название категории на казахском языке:",
        reply_markup=get_cancel_keyboard(locale)
    )
    
    await state.set_state(CategoryStates.entering_name_kz)


@router.message(CategoryStates.entering_name_kz)
async def process_category_name_kz(message: Message, state: FSMContext):
    """Process Kazakh category name"""
    telegram_id = message.from_user.id
    name_kz = message.text.strip()
    
    if len(name_kz) > 100:
        async with get_session() as session:
            user = await user_service.get_user_by_telegram_id(session, telegram_id)
            locale = user.language_code
        
        await message.answer(
            "Название слишком длинное. Максимум 100 символов.",
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    await state.update_data(name_kz=name_kz)
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
    
    await message.answer(
        "Выберите иконку для категории:",
        reply_markup=get_category_icons_keyboard(locale)
    )
    
    await state.set_state(CategoryStates.selecting_icon)


@router.callback_query(F.data.startswith("icon:"), CategoryStates.selecting_icon)
async def process_category_icon(callback: CallbackQuery, state: FSMContext):
    """Process category icon selection"""
    icon = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Get state data
        data = await state.get_data()
        
        # Create new category
        category = await category_service.create_category(
            session=session,
            user_id=user.id,
            name_ru=data['name_ru'],
            name_kz=data['name_kz'],
            icon=icon
        )
        
        await session.commit()
        
        await callback.message.edit_text(
            f"✅ Категория создана!\n\n{icon} {data['name_ru']} / {data['name_kz']}"
        )
        
        await state.clear()


@router.callback_query(F.data.startswith("edit_category:"))
async def edit_category(callback: CallbackQuery, state: FSMContext):
    """Edit category"""
    category_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
    
    # TODO: Implement category editing
    await callback.answer("Редактирование категорий в разработке", show_alert=True)


@router.callback_query(F.data.startswith("delete_category:"))
async def confirm_delete_category(callback: CallbackQuery, state: FSMContext):
    """Confirm category deletion"""
    category_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        category = await category_service.get_category_by_id(session, category_id, user.id)
        
        if not category:
            await callback.answer(i18n.get("errors.unknown", locale))
            return
        
        if category.is_default:
            await callback.answer(
                "Нельзя удалить стандартную категорию",
                show_alert=True
            )
            return
        
        await state.update_data(category_id=category_id)
        
        text = f"Вы уверены, что хотите удалить категорию?\n\n"
        text += f"{category.icon} {category.get_name(locale)}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_confirm_keyboard(locale)
        )
        
        await state.set_state(CategoryStates.confirming_delete)


@router.callback_query(F.data == "confirm", CategoryStates.confirming_delete)
async def delete_category(callback: CallbackQuery, state: FSMContext):
    """Delete category"""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    category_id = data.get('category_id')
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        success = await category_service.delete_category(session, category_id, user.id)
        
        if success:
            await session.commit()
            await callback.message.edit_text("✅ Категория удалена")
        else:
            await callback.message.edit_text("❌ Не удалось удалить категорию")
        
        await state.clear()


@router.callback_query(F.data == "back")
async def go_back(callback: CallbackQuery, state: FSMContext):
    """Go back to categories list"""
    await state.clear()
    await cmd_categories(callback.message, state)


@router.callback_query(F.data == "cancel", CategoryStates)
async def cancel_category_action(callback: CallbackQuery, state: FSMContext):
    """Cancel current category action"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code if user else 'ru'
    
    await callback.message.edit_text(i18n.get("buttons.cancel", locale))
    await state.clear()