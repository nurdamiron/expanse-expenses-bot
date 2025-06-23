import logging
import random
import string
from typing import Optional
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session
from src.database.models import User, Company, CompanyMember
from src.services.user import UserService
from src.services.company import CompanyService
from src.utils.i18n import i18n
from src.bot.keyboards import get_main_keyboard

router = Router()
logger = logging.getLogger(__name__)

user_service = UserService()
company_service = CompanyService()


def generate_invite_code(company_id: str) -> str:
    """Generate simple 6-digit invite code"""
    # Use last 6 chars of company_id + random chars for uniqueness
    code_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    company_suffix = company_id[-3:].upper()
    return f"{company_suffix}{code_suffix}"


class CompanyStates(StatesGroup):
    """States for company management"""
    creating_company = State()
    entering_name = State()
    entering_description = State()
    
    inviting_member = State()
    selecting_role = State()
    
    joining_company = State()
    entering_invite_code = State()
    
    viewing_members = State()
    editing_member = State()


def get_company_menu_keyboard(locale: str) -> InlineKeyboardMarkup:
    """Get company management menu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ " + i18n.get("company.create", locale),
                callback_data="company_create"
            )
        ],
        [
            InlineKeyboardButton(
                text="🏢 " + i18n.get("company.my_companies", locale),
                callback_data="company_list"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔗 Присоединиться к компании",
                callback_data="company_join"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 " + i18n.get("company.switch", locale),
                callback_data="company_switch"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ " + i18n.get("buttons.close", locale),
                callback_data="close"
            )
        ]
    ])


def get_company_list_keyboard(companies: list, locale: str) -> InlineKeyboardMarkup:
    """Get keyboard with company list"""
    keyboard = []
    
    for company, member in companies:
        role_emoji = {
            'owner': '👑',
            'admin': '👮',
            'manager': '👔',
            'employee': '👤'
        }.get(member.role, '👤')
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{role_emoji} {company.name}",
                callback_data=f"company_view:{company.id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 " + i18n.get("buttons.back", locale),
            callback_data="company_menu"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_company_details_keyboard(company_id: str, role: str, locale: str) -> InlineKeyboardMarkup:
    """Get keyboard for company details"""
    keyboard = []
    
    # Add member management for owners/admins
    if role in ('owner', 'admin'):
        keyboard.append([
            InlineKeyboardButton(
                text="👥 " + i18n.get("company.members", locale),
                callback_data=f"company_members:{company_id}"
            )
        ])
        
        keyboard.append([
            InlineKeyboardButton(
                text="➕ " + i18n.get("company.invite", locale),
                callback_data=f"company_invite:{company_id}"
            )
        ])
    
    # Reports for all members
    keyboard.append([
        InlineKeyboardButton(
            text="📊 " + i18n.get("company.reports", locale),
            callback_data=f"company_reports:{company_id}"
        )
    ])
    
    # Switch to this company
    keyboard.append([
        InlineKeyboardButton(
            text="✅ " + i18n.get("company.activate", locale),
            callback_data=f"company_activate:{company_id}"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(
            text="🔙 " + i18n.get("buttons.back", locale),
            callback_data="company_list"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Command("company"))
@router.message(F.text.startswith("💼"))
async def cmd_company(message: Message):
    """Handle /company command"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Show company menu
        await message.answer(
            i18n.get("company.menu_title", locale),
            reply_markup=get_company_menu_keyboard(locale)
        )


@router.callback_query(F.data == "company_menu")
async def show_company_menu(callback: CallbackQuery):
    """Show company management menu"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        await callback.message.edit_text(
            i18n.get("company.menu_title", locale),
            reply_markup=get_company_menu_keyboard(locale)
        )


@router.callback_query(F.data == "company_create")
async def start_company_creation(callback: CallbackQuery, state: FSMContext):
    """Start company creation process"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        await callback.message.edit_text(
            i18n.get("company.enter_name", locale),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="❌ " + i18n.get("buttons.cancel", locale),
                    callback_data="company_menu"
                )
            ]])
        )
        
        await state.set_state(CompanyStates.entering_name)


@router.message(StateFilter(CompanyStates.entering_name), F.text)
async def process_company_name(message: Message, state: FSMContext):
    """Process company name"""
    telegram_id = message.from_user.id
    company_name = message.text.strip()
    
    if len(company_name) < 3 or len(company_name) > 100:
        async with get_session() as session:
            user = await user_service.get_user_by_telegram_id(session, telegram_id)
            locale = user.language_code
            
            await message.answer(
                i18n.get("company.invalid_name", locale),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text="❌ " + i18n.get("buttons.cancel", locale),
                        callback_data="company_menu"
                    )
                ]])
            )
            return
    
    await state.update_data(company_name=company_name)
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        await message.answer(
            i18n.get("company.enter_description", locale),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⏭️ " + i18n.get("buttons.skip", locale),
                        callback_data="company_skip_description"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ " + i18n.get("buttons.cancel", locale),
                        callback_data="company_menu"
                    )
                ]
            ])
        )
        
        await state.set_state(CompanyStates.entering_description)


@router.message(StateFilter(CompanyStates.entering_description), F.text)
async def process_company_description(message: Message, state: FSMContext):
    """Process company description"""
    await finalize_company_creation(message.from_user.id, state, message.text.strip())


@router.callback_query(F.data == "company_skip_description", StateFilter(CompanyStates.entering_description))
async def skip_company_description(callback: CallbackQuery, state: FSMContext):
    """Skip company description"""
    await finalize_company_creation(callback.from_user.id, state, None, callback)


async def finalize_company_creation(
    telegram_id: int,
    state: FSMContext,
    description: Optional[str] = None,
    callback: Optional[CallbackQuery] = None
):
    """Finalize company creation"""
    data = await state.get_data()
    company_name = data.get('company_name')
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Create company
        company = await company_service.create_company(
            session=session,
            owner_id=user.id,
            name=company_name,
            description=description,
            primary_currency=user.primary_currency,
            timezone=user.timezone
        )
        
        # Set as active company
        user.active_company_id = company.id
        
        await session.commit()
        
        success_msg = i18n.get("company.created_success", locale, name=company_name)
        
        if callback:
            await callback.message.edit_text(
                success_msg,
                reply_markup=get_company_details_keyboard(company.id, 'owner', locale)
            )
        else:
            # From regular message
            from aiogram import Bot
            from main import bot as telegram_bot
            await telegram_bot.send_message(
                telegram_id,
                success_msg,
                reply_markup=get_company_details_keyboard(company.id, 'owner', locale)
            )
        
        await state.clear()


@router.callback_query(F.data == "company_list")
async def show_company_list(callback: CallbackQuery):
    """Show user's companies"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        companies = await company_service.get_user_companies(session, user.id)
        
        if not companies:
            await callback.message.edit_text(
                i18n.get("company.no_companies", locale),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="➕ " + i18n.get("company.create", locale),
                            callback_data="company_create"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🔙 " + i18n.get("buttons.back", locale),
                            callback_data="company_menu"
                        )
                    ]
                ])
            )
            return
        
        text = i18n.get("company.your_companies", locale) + "\n\n"
        
        for company, member in companies:
            is_active = company.id == user.active_company_id
            status = "✅" if is_active else "⭕"
            text += f"{status} <b>{company.name}</b>\n"
            text += f"   {i18n.get(f'company.role_{member.role}', locale)}\n\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_company_list_keyboard(companies, locale),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("company_view:"))
async def view_company_details(callback: CallbackQuery):
    """View company details"""
    company_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        company = await company_service.get_company_by_id(session, company_id, load_members=True)
        if not company:
            await callback.answer(i18n.get("company.not_found", locale))
            return
        
        # Get user's role
        member = next((m for m in company.members if m.user_id == user.id), None)
        if not member:
            await callback.answer(i18n.get("company.not_member", locale))
            return
        
        # Format company info
        text = f"<b>{company.name}</b>\n\n"
        
        if company.description:
            text += f"{company.description}\n\n"
        
        text += f"👥 {i18n.get('company.members_count', locale)}: {len(company.members)}\n"
        text += f"💰 {i18n.get('company.currency', locale)}: {company.primary_currency}\n"
        text += f"🕐 {i18n.get('company.timezone', locale)}: {company.timezone}\n\n"
        
        text += f"{i18n.get('company.your_role', locale)}: {i18n.get(f'company.role_{member.role}', locale)}"
        
        if member.department:
            text += f"\n{i18n.get('company.department', locale)}: {member.department}"
        
        if member.position:
            text += f"\n{i18n.get('company.position', locale)}: {member.position}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_company_details_keyboard(company_id, member.role, locale),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("company_activate:"))
async def activate_company(callback: CallbackQuery):
    """Activate company for user"""
    company_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Check membership
        companies = await company_service.get_user_companies(session, user.id)
        company_member = next(
            ((c, m) for c, m in companies if c.id == company_id),
            (None, None)
        )
        
        if not company_member[0]:
            await callback.answer(i18n.get("company.not_member", locale))
            return
        
        company, member = company_member
        
        # Update active company
        user.active_company_id = company_id
        await session.commit()
        
        await callback.answer(
            i18n.get("company.activated", locale, name=company.name)
        )
        
        # Update message with main keyboard
        await callback.message.delete()
        await callback.message.answer(
            i18n.get("company.mode_switched", locale, name=company.name),
            reply_markup=get_main_keyboard(locale, company.name)
        )


@router.callback_query(F.data == "company_switch")
async def switch_company_mode(callback: CallbackQuery):
    """Switch between personal and company mode"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        if user.active_company_id:
            # Switch to personal mode
            user.active_company_id = None
            await session.commit()
            
            await callback.answer(i18n.get("company.switched_to_personal", locale))
            
            await callback.message.delete()
            await callback.message.answer(
                i18n.get("company.personal_mode", locale),
                reply_markup=get_main_keyboard(locale)
            )
        else:
            # Show company list to switch to
            companies = await company_service.get_user_companies(session, user.id)
            
            if not companies:
                await callback.answer(i18n.get("company.no_companies", locale))
                return
            
            # Show company list
            await show_company_list(callback)


@router.callback_query(F.data.startswith("company_members:"))
async def show_company_members(callback: CallbackQuery):
    """Show company members"""
    company_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        company = await company_service.get_company_by_id(session, company_id, load_members=True)
        if not company:
            await callback.answer(i18n.get("company.not_found", locale))
            return
        
        # Check user's role
        member = next((m for m in company.members if m.user_id == user.id), None)
        if not member or member.role not in ('owner', 'admin'):
            await callback.answer("У вас нет прав для просмотра участников")
            return
        
        text = f"<b>{company.name}</b>\n"
        text += f"👥 Участники ({len(company.members)}):\n\n"
        
        for m in company.members:
            role_emoji = {
                'owner': '👑',
                'admin': '👮',
                'manager': '👔',
                'employee': '👤'
            }.get(m.role, '👤')
            
            text += f"{role_emoji} <b>{m.user.first_name or 'User'}</b>"
            if m.user.username:
                text += f" (@{m.user.username})"
            text += f"\n   Роль: {i18n.get(f'company.role_{m.role}', locale)}\n"
            if m.department:
                text += f"   Отдел: {m.department}\n"
            if m.position:
                text += f"   Должность: {m.position}\n"
            text += "\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"company_view:{company_id}"
                )
            ]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("company_invite:"))
async def show_invite_code(callback: CallbackQuery):
    """Show simple invite code"""
    company_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        company = await company_service.get_company_by_id(session, company_id)
        if not company:
            await callback.answer("Компания не найдена")
            return
        
        # Generate simple invite code
        invite_code = generate_invite_code(company_id)
        
        text = f"<b>🔗 Код приглашения</b>\n\n"
        text += f"Компания: <b>{company.name}</b>\n\n"
        text += f"Код приглашения:\n<code>{invite_code}</code>\n\n"
        text += "📤 Отправьте этот код тому, кого хотите пригласить.\n"
        text += "🏢 Он должен зайти в раздел <b>💼 Компания → 🔗 Присоединиться</b> и ввести код."
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data=f"company_view:{company_id}"
                )
            ]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@router.callback_query(F.data == "company_join")
async def start_company_join(callback: CallbackQuery, state: FSMContext):
    """Start joining company process"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        text = "<b>🔗 Присоединиться к компании</b>\n\n"
        text += "Введите код приглашения, который вам прислали:"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="company_menu"
                )
            ]
        ])
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(CompanyStates.entering_invite_code)


@router.message(StateFilter(CompanyStates.entering_invite_code), F.text)
async def process_invite_code(message: Message, state: FSMContext):
    """Process invite code and join company"""
    telegram_id = message.from_user.id
    invite_code = message.text.strip().upper()
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Find company by invite code pattern
        # For now, we'll search through companies (in production, use proper invite table)
        companies = await company_service.get_all_companies(session)
        target_company = None
        
        for company in companies:
            # Check if invite code matches pattern for this company
            expected_prefix = company.id[-3:].upper()
            if invite_code.startswith(expected_prefix) and len(invite_code) == 6:
                target_company = company
                break
        
        if not target_company:
            await message.answer(
                "❌ Неверный код приглашения. Проверьте код и попробуйте снова.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 Назад",
                            callback_data="company_menu"
                        )
                    ]
                ])
            )
            return
        
        # Check if already member
        existing = await company_service.get_member(session, target_company.id, user.id)
        if existing:
            await message.answer(
                f"Вы уже являетесь участником компании <b>{target_company.name}</b>",
                parse_mode="HTML",
                reply_markup=get_main_keyboard(locale)
            )
            await state.clear()
            return
        
        # Add as employee
        member = await company_service.add_member(
            session=session,
            company_id=target_company.id,
            user_id=user.id,
            role='employee'
        )
        
        # Set as active company
        user.active_company_id = target_company.id
        
        await session.commit()
        await state.clear()
        
        await message.answer(
            f"✅ Вы успешно присоединились к компании <b>{target_company.name}</b>!\n\n"
            f"Ваша роль: Сотрудник\n"
            f"Компания активирована для ведения расходов.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(locale, target_company.name)
        )


@router.callback_query(F.data.startswith("company_reports:"))
async def show_company_reports_menu(callback: CallbackQuery):
    """Show company reports menu"""
    company_id = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        company = await company_service.get_company_by_id(session, company_id, load_members=True)
        if not company:
            await callback.answer(i18n.get("company.not_found", locale))
            return
        
        # Check if user is member
        member = next((m for m in company.members if m.user_id == user.id), None)
        if not member:
            await callback.answer(i18n.get("company.not_member", locale))
            return
        
        # Temporarily set company as active to generate reports
        original_company_id = user.active_company_id
        user.active_company_id = company_id
        await session.commit()
        
        # Show analytics menu for this company
        from .analytics import analytics_menu
        await analytics_menu(callback.message, FSMContext())
        
        # Restore original active company
        user.active_company_id = original_company_id
        await session.commit()


@router.message(Command("join"))
async def join_company(message: Message):
    """Join company by invitation code"""
    telegram_id = message.from_user.id
    parts = message.text.split()
    
    if len(parts) != 2:
        await message.answer("Использование: /join КОД_КОМПАНИИ")
        return
    
    company_id = parts[1]
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
        
        # Get company
        company = await company_service.get_company_by_id(session, company_id)
        if not company:
            await message.answer("❌ Компания не найдена")
            return
        
        # Check if already member
        existing = await company_service.get_member(session, company_id, user.id)
        if existing:
            await message.answer(f"Вы уже являетесь участником компании {company.name}")
            return
        
        # Add as employee
        member = await company_service.add_member(
            session=session,
            company_id=company_id,
            user_id=user.id,
            role='employee',
            invited_by=None
        )
        
        await session.commit()
        
        await message.answer(
            f"✅ Вы успешно присоединились к компании <b>{company.name}</b>!\n\n"
            f"Ваша роль: {i18n.get('company.role_employee', locale)}",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(locale)
        )


@router.callback_query(F.data == "close")
async def close_message(callback: CallbackQuery):
    """Close/delete message"""
    await callback.message.delete()
    await callback.answer()