import io
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext

from src.database import get_session
from src.bot.states import ReceiptStates
from src.bot.keyboards import (
    get_default_categories_keyboard,
    get_confirm_keyboard,
    get_cancel_keyboard,
    get_currency_save_keyboard
)
from src.services.user import UserService
from src.services.category import CategoryService
from src.services.transaction import TransactionService
from src.services.ocr import OCRService
from src.services.duplicate_detector import duplicate_detector
from src.utils.text_parser import ExpenseParser
from src.utils.i18n import i18n
from src.core.config import settings
from src.services.currency import currency_service

router = Router()
logger = logging.getLogger(__name__)

user_service = UserService()
category_service = CategoryService()
transaction_service = TransactionService()
ocr_service = OCRService()
expense_parser = ExpenseParser()

# Log router registration
logger.info("Photo handler router initialized")


@router.message(F.photo)
async def process_receipt_photo(message: Message, state: FSMContext):
    """Process photo of receipt"""
    telegram_id = message.from_user.id
    logger.info(f"[PHOTO HANDLER] Received photo from user {telegram_id}")
    logger.info(f"[PHOTO HANDLER] Photo count: {len(message.photo)}, File ID: {message.photo[-1].file_id if message.photo else 'None'}")
    
    # Clear any existing state to ensure fresh processing
    await state.clear()
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
    
    # Check if OCR is enabled
    if not settings.enable_ocr:
        logger.warning(f"[PHOTO HANDLER] OCR is disabled in settings")
        await message.answer(
            i18n.get("errors.unknown", locale),
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    logger.info(f"[PHOTO HANDLER] OCR is enabled, proceeding with processing")
    
    # Send processing message
    processing_msg = await message.answer(
        i18n.get("receipt.processing", locale)
    )
    
    await state.set_state(ReceiptStates.processing_image)
    
    try:
        # Get the largest photo
        photo: PhotoSize = message.photo[-1]
        
        # Check file size
        if photo.file_size > settings.max_image_size_bytes:
            await processing_msg.edit_text(
                i18n.get_error("image_too_large", locale, max_size=settings.max_image_size_mb)
            )
            await state.clear()
            return
        
        # Download photo
        bot = message.bot
        file = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file.file_path, photo_bytes)
        photo_bytes.seek(0)
        
        # Process with OCR
        logger.info(f"[PHOTO HANDLER] Starting OCR processing for {photo.file_size} bytes")
        ocr_result = await ocr_service.process_receipt(photo_bytes.getvalue())
        logger.info(f"[PHOTO HANDLER] OCR result: {ocr_result}")
        
        if not ocr_result or not ocr_result.get('amount'):
            # OCR failed to find amount
            await processing_msg.edit_text(
                i18n.get("receipt.error_amount", locale),
                reply_markup=get_cancel_keyboard(locale)
            )
            await state.clear()
            return
        
        # Store OCR result in state
        transaction_date = ocr_result.get('date', datetime.now())
        if isinstance(transaction_date, datetime):
            transaction_date = transaction_date.isoformat()
        
        await state.update_data(
            amount=str(ocr_result['amount']),
            currency=ocr_result.get('currency', user.primary_currency),
            merchant=ocr_result.get('merchant'),
            transaction_date=transaction_date,
            ocr_confidence=ocr_result.get('confidence', 0),
            user_currency=user.primary_currency,
            photo_file_id=photo.file_id,
            detected_category=ocr_result.get('category', 'other')
        )
        
        # Format receipt info
        amount_formatted = expense_parser.format_amount(
            ocr_result['amount'], 
            ocr_result.get('currency', user.primary_currency)
        )
        
        receipt_info = f"{i18n.get('receipt.found', locale)}\n"
        receipt_info += f"{i18n.get('receipt.amount', locale)}: {amount_formatted}\n"
        receipt_info += f"{i18n.get('receipt.date', locale)}: {ocr_result.get('date', datetime.now()).strftime('%d.%m.%Y')}\n"
        
        if ocr_result.get('merchant'):
            receipt_info += f"{i18n.get('receipt.place', locale)}: {ocr_result['merchant']}\n"
        
        # Add confidence warning if low
        if ocr_result.get('confidence', 1) < 0.7:
            receipt_info += f"\n{i18n.get('receipt.confidence_low', locale)}\n"
        
        # Check if currency conversion needed
        detected_currency = ocr_result.get('currency', user.primary_currency)
        if detected_currency != user.primary_currency:
            logger.info(f"[CURRENCY] Detected different currency: {detected_currency} (user currency: {user.primary_currency})")
            
            if settings.enable_currency_conversion:
                logger.info(f"[CURRENCY] Converting {ocr_result['amount']} {detected_currency} to {user.primary_currency}")
                
                # Get conversion rate
                converted_amount, rate = await currency_service.convert_amount(
                    ocr_result['amount'],
                    detected_currency,
                    user.primary_currency,
                    session
                )
                
                if converted_amount:
                    logger.info(f"[CURRENCY] Conversion successful: {ocr_result['amount']} {detected_currency} = {converted_amount} {user.primary_currency} (rate: {rate})")
                    await state.update_data(
                        amount_primary=str(converted_amount),
                        exchange_rate=str(rate)
                    )
                    
                    # Show conversion info
                    receipt_info += f"\n💱 {amount_formatted} = "
                    receipt_info += f"{expense_parser.format_amount(converted_amount, user.primary_currency)} "
                    receipt_info += f"(курс {rate:.4f})\n"
                else:
                    logger.warning(f"[CURRENCY] Conversion failed for {detected_currency} to {user.primary_currency}")
                    await state.update_data(
                        amount_primary=str(ocr_result['amount']),
                        exchange_rate='1.0000'
                    )
            else:
                logger.info(f"[CURRENCY] Currency conversion disabled, saving in original currency")
                await state.update_data(
                    amount_primary=str(ocr_result['amount']),
                    exchange_rate='1.0000'
                )
        else:
            # Same currency, no conversion needed
            logger.info(f"[CURRENCY] Same currency detected: {detected_currency}")
            await state.update_data(
                amount_primary=str(ocr_result['amount']),
                exchange_rate='1.0000'
            )
        
        # Auto-save transaction with detected category
        detected_category = ocr_result.get('category', 'other')
        logger.info(f"Detected category: {detected_category}")
        
        # Map AI category to our default categories
        category_mapping = {
            'food': 'food',
            'transport': 'transport',
            'shopping': 'shopping',
            'utilities': 'home',  # Mobile operators go to home/utilities
            'health': 'health',
            'entertainment': 'entertainment',
            'donation': 'donation',
            'other': 'other'
        }
        
        category_key = category_mapping.get(detected_category, 'other')
        logger.info(f"Mapped category key: {category_key}")
        
        # Get default category
        category = await category_service.get_default_category(session, user.id, category_key)
        
        if not category:
            # Fallback to 'other' category
            category = await category_service.get_default_category(session, user.id, 'other')
            
        if not category:
            # Create default categories if they don't exist
            await category_service.get_or_create_default_categories(session, user.id)
            await session.commit()
            
            # Try again
            category = await category_service.get_default_category(session, user.id, category_key)
            if not category:
                category = await category_service.get_default_category(session, user.id, 'other')
        
        # Get state data
        data = await state.get_data()
        
        # Parse transaction date
        transaction_date = data['transaction_date']
        if isinstance(transaction_date, str):
            try:
                transaction_date = datetime.fromisoformat(transaction_date)
            except:
                transaction_date = datetime.now()
        
        # Check for duplicates
        potential_duplicates = await duplicate_detector.find_duplicates(
            session=session,
            user_id=user.id,
            amount=Decimal(data['amount']),
            merchant=data.get('merchant'),
            transaction_date=transaction_date,
            time_window_hours=1  # Check within 1 hour for exact duplicates
        )
        
        if potential_duplicates:
            # Found potential duplicate - ask for confirmation
            duplicate_info = i18n.get("duplicate.found", locale) + "\n\n"
            
            for dup in potential_duplicates[:3]:  # Show max 3 duplicates
                dup_amount = expense_parser.format_amount(dup.amount, dup.currency)
                dup_date = dup.transaction_date.strftime('%d.%m.%Y %H:%M')
                duplicate_info += f"• {dup_amount}"
                if dup.merchant:
                    duplicate_info += f" - {dup.merchant}"
                duplicate_info += f" ({dup_date})\n"
            
            duplicate_info += f"\n{i18n.get('duplicate.confirm_save', locale)}"
            
            # Save category_id to state for later use
            await state.update_data(category_id=category.id)
            
            # Create confirmation keyboard
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            yes_text = i18n.get("buttons.yes", locale)
            no_text = i18n.get("buttons.no", locale)
            logger.info(f"[DUPLICATE BUTTONS] Creating buttons with locale '{locale}': yes='{yes_text}', no='{no_text}'")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=yes_text,
                        callback_data="confirm_duplicate_photo"
                    ),
                    InlineKeyboardButton(
                        text=no_text,
                        callback_data="cancel_duplicate_photo"
                    )
                ]
            ])
            
            await processing_msg.edit_text(duplicate_info, reply_markup=keyboard)
            await state.set_state(ReceiptStates.confirming_duplicate)
            return
        
        # Create transaction immediately
        amount_primary = Decimal(data.get('amount_primary', data['amount']))
        exchange_rate = Decimal(data.get('exchange_rate', '1.0000'))
        
        transaction = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal(data['amount']),
            currency=data['currency'],
            category_id=category.id,
            merchant=data.get('merchant'),
            transaction_date=transaction_date,
            amount_primary=amount_primary,
            exchange_rate=exchange_rate,
            receipt_image_url=None,  # TODO: S3 upload
            ocr_confidence=Decimal(str(data.get('ocr_confidence', 0)))
        )
        
        await session.commit()
        
        # Get today's spending
        today_total, _ = await transaction_service.get_today_spending(session, user.id)
        
        # Format response
        amount_formatted = expense_parser.format_amount(Decimal(data['amount']), data['currency'])
        today_formatted = expense_parser.format_amount(today_total, user.primary_currency)
        
        response = f"✅ {i18n.get('receipt.saved', locale)} "
        response += f"{amount_formatted} → {category.icon} {category.get_name(locale)}"
        
        if data.get('merchant'):
            response += f" ({data['merchant']})"
        
        response += f"\n\n📊 {i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
        
        await processing_msg.edit_text(response)
        await state.clear()
        
    except Exception as e:
        logger.error(f"[PHOTO HANDLER] Error processing receipt photo: {e}", exc_info=True)
        await processing_msg.edit_text(
            i18n.get("receipt.error_quality", locale),
            reply_markup=get_cancel_keyboard(locale)
        )
        await state.clear()


@router.callback_query(F.data.startswith("currency:"), ReceiptStates.selecting_currency)
async def process_currency_selection(callback: CallbackQuery, state: FSMContext):
    """Process currency save option selection"""
    option = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        data = await state.get_data()
        
        # TODO: Implement currency conversion logic
        # For now, just save in original currency
        
        await callback.message.edit_text(
            i18n.get("receipt.choose_category", locale),
            reply_markup=get_default_categories_keyboard(locale)
        )
        
        await state.set_state(ReceiptStates.selecting_category)


@router.callback_query(F.data.startswith("quick_category:"), ReceiptStates.selecting_category)
async def process_receipt_category(callback: CallbackQuery, state: FSMContext):
    """Process category selection for receipt"""
    category_key = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Get default category
        category = await category_service.get_default_category(session, user.id, category_key)
        
        if not category:
            await callback.answer(i18n.get("errors.unknown", locale))
            return
        
        # Get state data
        data = await state.get_data()
        
        # TODO: Upload photo to S3 and get URL
        receipt_image_url = None
        
        # Create transaction
        amount_primary = Decimal(data.get('amount_primary', data['amount']))
        exchange_rate = Decimal(data.get('exchange_rate', '1.0000'))
        
        # Parse transaction date
        transaction_date = data['transaction_date']
        if isinstance(transaction_date, str):
            try:
                transaction_date = datetime.fromisoformat(transaction_date)
            except:
                transaction_date = datetime.now()
        
        transaction = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal(data['amount']),
            currency=data['currency'],
            category_id=category.id,
            merchant=data.get('merchant'),
            transaction_date=transaction_date,
            amount_primary=amount_primary,
            exchange_rate=exchange_rate,
            receipt_image_url=receipt_image_url,
            ocr_confidence=Decimal(str(data.get('ocr_confidence', 0)))
        )
        
        await session.commit()
        
        # Get today's spending
        today_total, _ = await transaction_service.get_today_spending(session, user.id)
        
        # Format response
        amount_formatted = expense_parser.format_amount(Decimal(data['amount']), data['currency'])
        today_formatted = expense_parser.format_amount(today_total, user.primary_currency)
        
        response = f"{i18n.get('receipt.saved', locale)} "
        response += f"{amount_formatted} {i18n.get(f'categories.{category_key}', locale)}"
        
        if data.get('merchant'):
            response += f" ({data['merchant']})"
        
        response += f"\n\n{i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
        
        await callback.message.edit_text(response)
        await state.clear()


@router.callback_query(F.data == "confirm_duplicate_photo", ReceiptStates.confirming_duplicate)
async def confirm_duplicate_photo(callback: CallbackQuery, state: FSMContext):
    """Confirm saving duplicate transaction from photo"""
    telegram_id = callback.from_user.id
    data = await state.get_data()
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Parse transaction date
        transaction_date = data['transaction_date']
        if isinstance(transaction_date, str):
            try:
                transaction_date = datetime.fromisoformat(transaction_date)
            except:
                transaction_date = datetime.now()
        
        # Create transaction
        amount_primary = Decimal(data.get('amount_primary', data['amount']))
        exchange_rate = Decimal(data.get('exchange_rate', '1.0000'))
        
        transaction = await transaction_service.create_transaction(
            session=session,
            user_id=user.id,
            amount=Decimal(data['amount']),
            currency=data['currency'],
            category_id=data['category_id'],
            merchant=data.get('merchant'),
            transaction_date=transaction_date,
            amount_primary=amount_primary,
            exchange_rate=exchange_rate,
            receipt_image_url=None,
            ocr_confidence=Decimal(str(data.get('ocr_confidence', 0)))
        )
        
        await session.commit()
        
        # Get today's spending
        today_total, _ = await transaction_service.get_today_spending(session, user.id)
        
        # Format response
        amount_formatted = expense_parser.format_amount(Decimal(data['amount']), data['currency'])
        today_formatted = expense_parser.format_amount(today_total, user.primary_currency)
        
        response = f"✅ {i18n.get('receipt.saved', locale)} "
        response += f"{amount_formatted}"
        
        if data.get('merchant'):
            response += f" ({data['merchant']})"
        
        response += f"\n\n📊 {i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
        
        await callback.message.edit_text(response)
        await state.clear()


@router.callback_query(F.data == "cancel_duplicate_photo", ReceiptStates.confirming_duplicate)
async def cancel_duplicate_photo(callback: CallbackQuery, state: FSMContext):
    """Cancel saving duplicate transaction from photo"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        await callback.message.edit_text(
            "❌ " + i18n.get("duplicate.cancelled", locale)
        )
        await state.clear()