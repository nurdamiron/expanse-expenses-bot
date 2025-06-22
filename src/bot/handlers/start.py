from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from src.database import get_session, User, Category
from src.bot.keyboards import get_language_keyboard, get_confirm_keyboard
from src.bot.keyboards.main import get_main_keyboard
from src.bot.states import RegistrationStates
from src.utils.i18n import i18n
from src.services.user import UserService

router = Router()
user_service = UserService()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        # Check if user exists
        user = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user.scalar_one_or_none()
        
        if user:
            # Existing user
            locale = user.language_code
            await message.answer(
                i18n.get("welcome.greeting", locale),
                parse_mode="HTML",
                reply_markup=get_main_keyboard(locale)
            )
        else:
            # New user - show language selection
            await state.set_state(RegistrationStates.choosing_language)
            await message.answer(
                i18n.get("welcome.choose_language"),
                reply_markup=get_language_keyboard()
            )


@router.callback_query(F.data.startswith("lang:"), StateFilter(RegistrationStates.choosing_language))
async def process_language_selection(callback: CallbackQuery, state: FSMContext):
    """Process language selection for new users"""
    language = callback.data.split(":")[1]
    telegram_user = callback.from_user
    
    async with get_session() as session:
        # Create new user
        user = await user_service.create_user(
            session=session,
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=language
        )
        
        # Create default categories (handled by trigger in DB)
        await session.commit()
    
    # Send welcome message and tutorial
    await callback.message.edit_text(
        i18n.get("welcome.language_set", language)
    )
    
    await callback.message.answer(
        i18n.get("welcome.greeting", language),
        parse_mode="HTML"
    )
    
    await callback.message.answer(
        i18n.get("welcome.tutorial", language),
        parse_mode="HTML",
        reply_markup=get_main_keyboard(language)
    )
    
    await state.clear()


@router.message(F.text == "/help")
async def cmd_help(message: Message):
    """Handle /help command"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code if user else 'ru'
    
    help_text = f"""
{i18n.get("welcome.tutorial", locale)}

📝 <b>Команды:</b>
/start - {i18n.get_command_description("start", locale)}
/help - {i18n.get_command_description("help", locale)}
/stats - {i18n.get_command_description("stats", locale)}
/categories - {i18n.get_command_description("categories", locale)}
/export - {i18n.get_command_description("export", locale)}
/settings - {i18n.get_command_description("settings", locale)}
/last - {i18n.get_command_description("last", locale)}
/today - {i18n.get_command_description("today", locale)}
/rates - {i18n.get_command_description("rates", locale)}
/convert - {i18n.get_command_description("convert", locale)}
"""
    
    await message.answer(help_text, parse_mode="HTML")