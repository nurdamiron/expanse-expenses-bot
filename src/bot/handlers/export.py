from datetime import date, datetime, timedelta
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session, ExportHistory
from src.bot.states import ExportStates
from src.services.user import UserService
from src.services.category import CategoryService
from src.services.export import ExportService
from src.utils.i18n import i18n
from src.bot.keyboards import get_back_keyboard, create_inline_keyboard

router = Router()
user_service = UserService()
category_service = CategoryService()
export_service = ExportService()


@router.message(F.text == "/export")
async def cmd_export(message: Message, state: FSMContext):
    """Start export process"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
    
    # Show period selection
    text = f"<b>{i18n.get('commands.export', locale)}</b>\n\n"
    text += "Выберите период для экспорта:"
    
    builder = InlineKeyboardBuilder()
    
    periods = [
        ("📅 Текущий месяц", "export_period:current_month"),
        ("📅 Прошлый месяц", "export_period:last_month"),
        ("📅 Последние 30 дней", "export_period:30_days"),
        ("📅 Последние 90 дней", "export_period:90_days"),
        ("📅 Текущий год", "export_period:current_year"),
        ("📅 Произвольный период", "export_period:custom"),
    ]
    
    for text_btn, callback_data in periods:
        builder.row(
            InlineKeyboardButton(text=text_btn, callback_data=callback_data)
        )
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("cancel", locale),
            callback_data="cancel"
        )
    )
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    
    await state.set_state(ExportStates.selecting_period)


@router.callback_query(F.data.startswith("export_period:"), StateFilter(ExportStates.selecting_period))
async def process_period_selection(callback: CallbackQuery, state: FSMContext):
    """Process period selection"""
    period = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
    
    # Calculate date range
    today = date.today()
    
    if period == "current_month":
        start_date = today.replace(day=1)
        end_date = today
    elif period == "last_month":
        last_month = today.replace(day=1) - timedelta(days=1)
        start_date = last_month.replace(day=1)
        end_date = last_month
    elif period == "30_days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif period == "90_days":
        start_date = today - timedelta(days=90)
        end_date = today
    elif period == "current_year":
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif period == "custom":
        # TODO: Implement custom period selection
        await callback.answer("Произвольный период в разработке", show_alert=True)
        return
    
    # Store period in state
    await state.update_data(
        start_date=start_date,
        end_date=end_date
    )
    
    # Show format selection
    text = f"Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
    text += "Выберите формат экспорта:"
    
    builder = InlineKeyboardBuilder()
    
    formats = [
        ("📊 Excel (.xlsx)", "export_format:xlsx"),
        ("📄 CSV (.csv)", "export_format:csv"),
        ("📑 PDF (.pdf)", "export_format:pdf"),
    ]
    
    for text_btn, callback_data in formats:
        builder.row(
            InlineKeyboardButton(text=text_btn, callback_data=callback_data)
        )
    
    builder.row(
        InlineKeyboardButton(
            text=i18n.get_button("back", locale),
            callback_data="back_to_period"
        )
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup()
    )
    
    await state.set_state(ExportStates.selecting_format)


@router.callback_query(F.data.startswith("export_format:"), StateFilter(ExportStates.selecting_format))
async def process_format_selection(callback: CallbackQuery, state: FSMContext):
    """Process format selection"""
    format_type = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Get categories for selection
        categories = await category_service.get_user_categories(session, user.id)
    
    # Store format in state
    await state.update_data(format=format_type)
    
    # Show category selection
    text = "Выберите категории для экспорта:\n"
    text += "(или экспортировать все категории)"
    
    builder = InlineKeyboardBuilder()
    
    # Add "All categories" button
    builder.row(
        InlineKeyboardButton(
            text="📋 Все категории",
            callback_data="export_categories:all"
        )
    )
    
    # Add category buttons
    for category in categories:
        name = category.get_name(locale)
        builder.row(
            InlineKeyboardButton(
                text=f"{category.icon} {name}",
                callback_data=f"export_category:{category.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(
            text="✅ Готово",
            callback_data="export_categories:done"
        ),
        InlineKeyboardButton(
            text=i18n.get_button("back", locale),
            callback_data="back_to_format"
        )
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup()
    )
    
    await state.set_state(ExportStates.selecting_categories)
    await state.update_data(selected_categories=[])


@router.callback_query(F.data.startswith("export_category:"), StateFilter(ExportStates.selecting_categories))
async def toggle_category_selection(callback: CallbackQuery, state: FSMContext):
    """Toggle category selection"""
    category_id = callback.data.split(":")[1]
    
    data = await state.get_data()
    selected = data.get('selected_categories', [])
    
    if category_id in selected:
        selected.remove(category_id)
        await callback.answer("❌ Категория удалена из выбора")
    else:
        selected.append(category_id)
        await callback.answer("✅ Категория добавлена")
    
    await state.update_data(selected_categories=selected)


@router.callback_query(F.data == "export_categories:all", StateFilter(ExportStates.selecting_categories))
async def select_all_categories(callback: CallbackQuery, state: FSMContext):
    """Select all categories for export"""
    await state.update_data(selected_categories=None)  # None means all
    await generate_export(callback, state)


@router.callback_query(F.data == "export_categories:done", StateFilter(ExportStates.selecting_categories))
async def finish_category_selection(callback: CallbackQuery, state: FSMContext):
    """Finish category selection and generate export"""
    data = await state.get_data()
    
    if not data.get('selected_categories'):
        await callback.answer("Выберите хотя бы одну категорию", show_alert=True)
        return
    
    await generate_export(callback, state)


async def generate_export(callback: CallbackQuery, state: FSMContext):
    """Generate export file"""
    telegram_id = callback.from_user.id
    
    # Show loading message
    await callback.message.edit_text("⏳ Генерирую файл экспорта...")
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Get state data
        data = await state.get_data()
        start_date = data['start_date']
        end_date = data['end_date']
        format_type = data['format']
        category_ids = data.get('selected_categories')  # None means all
        
        try:
            # Generate export
            file_data = await export_service.export_transactions(
                session, user, format_type,
                start_date, end_date,
                category_ids
            )
            
            if not file_data:
                await callback.message.edit_text(
                    "📭 Нет данных для экспорта за выбранный период"
                )
                await state.clear()
                return
            
            # Prepare filename
            date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"expenses_{date_str}.{format_type}"
            
            # Send file
            document = BufferedInputFile(
                file_data.read(),
                filename=filename
            )
            
            caption = f"📊 Экспорт расходов\n"
            caption += f"Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n"
            caption += f"Формат: {format_type.upper()}"
            
            await callback.message.answer_document(
                document,
                caption=caption
            )
            
            # Save export history
            export_record = ExportHistory(
                user_id=user.id,
                format=format_type,
                period_start=start_date,
                period_end=end_date,
                file_size=len(file_data.getvalue()) if hasattr(file_data, 'getvalue') else 0
            )
            session.add(export_record)
            await session.commit()
            
            # Delete loading message
            await callback.message.delete()
            
        except Exception as e:
            logger.error(f"Export error: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при создании экспорта. Попробуйте позже."
            )
        
        await state.clear()


@router.callback_query(F.data == "back_to_period")
async def back_to_period_selection(callback: CallbackQuery, state: FSMContext):
    """Go back to period selection"""
    await state.set_state(ExportStates.selecting_period)
    await cmd_export(callback.message, state)


@router.callback_query(F.data == "back_to_format")
async def back_to_format_selection(callback: CallbackQuery, state: FSMContext):
    """Go back to format selection"""
    data = await state.get_data()
    await state.set_state(ExportStates.selecting_format)
    
    # Recreate the callback with period data
    period_callback = CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        message=callback.message,
        data=f"export_period:custom"  # This will be overridden by state data
    )
    
    await process_period_selection(period_callback, state)


# Add logger import
import logging
logger = logging.getLogger(__name__)