import io
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import StateFilter
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
# Import OCRService
from src.services.ocr import OCRService
from src.services.duplicate_detector import duplicate_detector
from src.services.s3_storage import S3StorageService
from src.utils.text_parser import ExpenseParser
from src.utils.caption_parser import CaptionParser
from src.utils.clarification import ClarificationHelper
from src.utils.i18n import i18n
from src.core.config import settings
from src.services.currency import currency_service

router = Router()
logger = logging.getLogger(__name__)

user_service = UserService()
category_service = CategoryService()
transaction_service = TransactionService()
# Always create OCRService - it will use OpenAI Vision if configured
ocr_service = OCRService()
s3_service = S3StorageService()
expense_parser = ExpenseParser()
caption_parser = CaptionParser()
clarification_helper = ClarificationHelper()

# Log router registration
logger.info("Photo handler router initialized")


@router.message(F.photo)
async def process_receipt_photo(message: Message, state: FSMContext):
    """Process photo of receipt"""
    telegram_id = message.from_user.id
    caption = message.caption or ""
    logger.info(f"[PHOTO HANDLER] Received photo from user {telegram_id}")
    logger.info(f"[PHOTO HANDLER] Photo count: {len(message.photo)}, File ID: {message.photo[-1].file_id if message.photo else 'None'}")
    logger.info(f"[PHOTO HANDLER] Caption: {caption}")
    
    # Check if already processing
    current_state = await state.get_state()
    if current_state and "receipt" in str(current_state):
        await message.answer("⏳ Пожалуйста, дождитесь завершения обработки предыдущего чека.")
        return
    
    # Clear any existing state to ensure fresh processing
    await state.clear()
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
    
    # Check if we have caption with amount
    caption_data = caption_parser.parse(caption)
    
    # Check if OCR is enabled
    if not settings.enable_ocr or not ocr_service:
        # Download and upload photo even without OCR
        photo: PhotoSize = message.photo[-1]
        bot = message.bot
        file = await bot.get_file(photo.file_id)
        photo_bytes = io.BytesIO()
        await bot.download_file(file.file_path, photo_bytes)
        photo_bytes.seek(0)
        
        # Upload photo to S3 for storage
        receipt_image_url = None
        if s3_service.enabled:
            try:
                receipt_image_url = await s3_service.upload_receipt(
                    user_id=user.id,
                    file_data=photo_bytes.getvalue(),
                    content_type='image/jpeg'
                )
                if receipt_image_url:
                    logger.info(f"[S3] Receipt uploaded (no OCR): {receipt_image_url}")
                else:
                    logger.warning(f"[S3] Receipt upload failed (no OCR), continuing without S3 URL")
            except Exception as e:
                logger.error(f"[S3] Receipt upload error (no OCR): {e}")
                # Continue processing even if S3 upload fails
        
        # Try to process with caption only
        if caption_data['amount']:
            logger.info(f"[PHOTO HANDLER] OCR disabled, using caption data")
            await state.update_data(
                amount=str(caption_data['amount']),
                currency=caption_data['currency'] or user.primary_currency,
                merchant=None,
                transaction_date=datetime.now().isoformat(),
                ocr_confidence=1.0,
                user_currency=user.primary_currency,
                photo_file_id=message.photo[-1].file_id,
                receipt_image_url=receipt_image_url,  # Save S3 URL
                detected_category=caption_data['category'] or 'other',
                description=caption_parser.suggest_description(caption, caption_data['category'])
            )
            
            # Show category selection
            await processing_msg.delete()
            await state.set_state(ReceiptStates.choosing_category)
            
            amount_formatted = expense_parser.format_amount(
                caption_data['amount'], 
                caption_data['currency'] or user.primary_currency
            )
            
            await message.answer(
                f"{i18n.get('receipt.found_from_caption', locale)}\n"
                f"{i18n.get('receipt.amount', locale)}: {amount_formatted}\n\n"
                f"{i18n.get('expense.choose_category', locale)}",
                reply_markup=get_default_categories_keyboard(locale)
            )
            return
        else:
            logger.info(f"[PHOTO HANDLER] OCR disabled and no amount in caption, asking for amount")
            # Save photo file ID and ask for amount
            await state.update_data(
                photo_file_id=message.photo[-1].file_id,
                receipt_image_url=receipt_image_url,  # Save S3 URL
                user_currency=user.primary_currency
            )
            await state.set_state(ReceiptStates.editing_amount)
            
            await message.answer(
                i18n.get("receipt.enter_amount", locale),
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
        
        # Upload photo to S3 for storage
        receipt_image_url = None
        if s3_service.enabled:
            try:
                receipt_image_url = await s3_service.upload_receipt(
                    user_id=user.id,
                    file_data=photo_bytes.getvalue(),
                    content_type='image/jpeg'
                )
                if receipt_image_url:
                    logger.info(f"[S3] Receipt uploaded: {receipt_image_url}")
                else:
                    logger.warning(f"[S3] Receipt upload failed, continuing without S3 URL")
            except Exception as e:
                logger.error(f"[S3] Receipt upload error: {e}")
                # Continue processing even if S3 upload fails
        
        # Reset BytesIO for OCR processing
        photo_bytes.seek(0)
        
        # Parse caption first if available
        caption_data = caption_parser.parse(caption)
        
        # Process with OCR
        logger.info(f"[PHOTO HANDLER] Starting OCR processing for {photo.file_size} bytes")
        ocr_result = await ocr_service.process_receipt(photo_bytes.getvalue())
        logger.info(f"[PHOTO HANDLER] OCR result: {ocr_result}")
        
        # Merge caption data with OCR result
        if caption_data['amount'] and not ocr_result.get('amount'):
            ocr_result['amount'] = caption_data['amount']
        if caption_data['currency']:
            ocr_result['currency'] = caption_data['currency']
        if caption_data['category']:
            ocr_result['category'] = caption_data['category']
        
        if not ocr_result or not ocr_result.get('amount'):
            # Both OCR and caption failed to find amount
            await processing_msg.edit_text(
                i18n.get("receipt.error_amount", locale),
                reply_markup=get_cancel_keyboard(locale)
            )
            await state.clear()
            return
        
        # Check if clarification is needed
        needs_amount_clarification = clarification_helper.needs_amount_clarification(ocr_result, caption_data)
        needs_category_clarification = clarification_helper.needs_category_clarification(
            ocr_result.get('category'), 
            ocr_result.get('confidence', 1)
        )
        
        # Store OCR result in state
        # Use exact date/time from receipt for accurate duplicate detection
        transaction_date = ocr_result.get('date', datetime.now())
        if not isinstance(transaction_date, datetime):
            transaction_date = datetime.now()
        
        # Check if the date is too old (more than 30 days)
        days_difference = (datetime.now() - transaction_date).days
        if days_difference > 30:
            logger.info(f"Receipt date {transaction_date} is {days_difference} days old, using current date instead")
            transaction_date = datetime.now()
        
        await state.update_data(
            amount=str(ocr_result['amount']) if ocr_result.get('amount') else None,
            currency=ocr_result.get('currency', user.primary_currency),
            merchant=ocr_result.get('merchant'),
            transaction_date=transaction_date.isoformat(),
            ocr_confidence=ocr_result.get('confidence', 0),
            user_currency=user.primary_currency,
            photo_file_id=photo.file_id,
            receipt_image_url=receipt_image_url,  # Save S3 URL
            detected_category=ocr_result.get('category', 'other'),
            description=caption_parser.suggest_description(caption, ocr_result.get('category')),
            caption_amount=str(caption_data['amount']) if caption_data.get('amount') else None,
            needs_amount_clarification=needs_amount_clarification,
            needs_category_clarification=needs_category_clarification
        )
        
        # Handle case when amount needs clarification
        if needs_amount_clarification:
            await processing_msg.delete()
            await state.set_state(ReceiptStates.clarifying_amount)
            
            # Build context for clarification
            context = {
                'low_confidence': ocr_result.get('confidence', 1) < 0.5
            }
            
            if ocr_result.get('amount') and caption_data.get('amount'):
                context['ocr_amount'] = expense_parser.format_amount(
                    ocr_result['amount'], 
                    ocr_result.get('currency', user.primary_currency)
                )
                context['caption_amount'] = expense_parser.format_amount(
                    caption_data['amount'], 
                    caption_data.get('currency', user.primary_currency)
                )
            
            # Prepare suggestions
            suggestions = []
            if ocr_result.get('amount'):
                suggestions.append(ocr_result['amount'])
            if caption_data.get('amount') and caption_data['amount'] != ocr_result.get('amount'):
                suggestions.append(caption_data['amount'])
            
            message_text = clarification_helper.format_clarification_message(
                locale, 'amount', context
            )
            
            keyboard = clarification_helper.get_amount_clarification_keyboard(locale, suggestions)
            
            await message.answer(
                message_text,
                reply_markup=keyboard
            )
            return
        
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
                logger.info(f"[CURRENCY] Currency conversion disabled, will prompt user")
                # Don't set amount_primary here - let user choose
                await state.update_data(
                    needs_currency_choice=True
                )
        else:
            # Same currency, no conversion needed
            logger.info(f"[CURRENCY] Same currency detected: {detected_currency}")
            await state.update_data(
                amount_primary=str(ocr_result['amount']),
                exchange_rate='1.0000'
            )
        
        # Get state data
        data = await state.get_data()
        
        # Check if we need to show currency selection
        if data.get('needs_currency_choice'):
            # Show currency selection first
            await processing_msg.edit_text(
                receipt_info + f"\n{i18n.get('currency.save_question', locale)}",
                reply_markup=get_currency_save_keyboard(locale)
            )
            await state.set_state(ReceiptStates.selecting_currency)
            return
        
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
        
        # Check confidence for automatic saving
        ocr_confidence = ocr_result.get('confidence', 0)
        
        # If category is 'other', ask for description first
        if category_key == 'other':
            await processing_msg.edit_text(
                receipt_info + f"\n\n{i18n.get('receipt.ask_description', locale)}\n{i18n.get('receipt.description_hint', locale)}",
                reply_markup=get_cancel_keyboard(locale)
            )
            await state.set_state(ReceiptStates.asking_description)
            return
        
        # If confidence is low, ask user to choose category
        if ocr_confidence < 0.7:
            await processing_msg.edit_text(
                receipt_info + f"\n{i18n.get('expense.choose_category', locale)}",
                reply_markup=get_default_categories_keyboard(locale)
            )
            await state.set_state(ReceiptStates.choosing_category)
            return
        
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
        
        # Parse transaction date for duplicate check
        transaction_date = data.get('transaction_date')
        if transaction_date:
            try:
                transaction_date = datetime.fromisoformat(transaction_date)
            except:
                transaction_date = datetime.now()
        else:
            transaction_date = datetime.now()
        
        # Check if the date is too old (more than 30 days)
        days_difference = (datetime.now() - transaction_date).days
        if days_difference > 30:
            logger.info(f"Receipt date {transaction_date} is {days_difference} days old, using current date instead")
            transaction_date = datetime.now()
        
        # Check for duplicates using exact transaction date/time
        potential_duplicates = await duplicate_detector.find_duplicates(
            session=session,
            user_id=user.id,
            amount=Decimal(data['amount']),
            merchant=data.get('merchant'),
            transaction_date=transaction_date,
            time_window_hours=2  # Check within 2 hours window
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
        
        # Check if user is in company mode
        company_id = user.active_company_id if user else None
        
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
            company_id=company_id,
            receipt_image_url=data.get('receipt_image_url'),  # Use S3 URL from state
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


@router.callback_query(F.data.startswith("currency:"), StateFilter(ReceiptStates.selecting_currency))
async def process_currency_selection(callback: CallbackQuery, state: FSMContext):
    """Process currency save option selection"""
    option = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        data = await state.get_data()
        
        # Handle currency conversion based on user selection
        if option == "tenge":
            # Convert to tenge
            detected_currency = data.get('currency', user.primary_currency)
            if detected_currency != 'KZT':
                converted_amount, rate = await currency_service.convert_amount(
                    Decimal(data['amount']),
                    detected_currency,
                    'KZT',
                    session
                )
                
                if converted_amount:
                    await state.update_data(
                        amount_primary=str(converted_amount),
                        exchange_rate=str(rate),
                        save_in_tenge=True
                    )
                else:
                    # Conversion failed, save in original
                    await state.update_data(
                        amount_primary=str(data['amount']),
                        exchange_rate='1.0000'
                    )
            else:
                # Already in tenge
                await state.update_data(
                    amount_primary=str(data['amount']),
                    exchange_rate='1.0000'
                )
        elif option == "original":
            # Save in original currency
            await state.update_data(
                amount_primary=str(data['amount']),
                exchange_rate='1.0000'
            )
        else:  # both
            # Save both - primary amount in user currency
            detected_currency = data.get('currency', user.primary_currency)
            if detected_currency != user.primary_currency:
                converted_amount, rate = await currency_service.convert_amount(
                    Decimal(data['amount']),
                    detected_currency,
                    user.primary_currency,
                    session
                )
                
                if converted_amount:
                    await state.update_data(
                        amount_primary=str(converted_amount),
                        exchange_rate=str(rate)
                    )
                else:
                    await state.update_data(
                        amount_primary=str(data['amount']),
                        exchange_rate='1.0000'
                    )
            else:
                await state.update_data(
                    amount_primary=str(data['amount']),
                    exchange_rate='1.0000'
                )
        
        await callback.message.edit_text(
            i18n.get("receipt.choose_category", locale),
            reply_markup=get_default_categories_keyboard(locale)
        )
        
        await state.set_state(ReceiptStates.selecting_category)


@router.callback_query(F.data.startswith("quick_category:"), StateFilter(ReceiptStates.selecting_category))
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
        
        # Get receipt image URL from state (uploaded earlier in OCR processing)
        receipt_image_url = data.get('receipt_image_url')
        
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
            company_id=user.active_company_id,  # Add company_id support
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


@router.callback_query(F.data == "confirm_duplicate_photo", StateFilter(ReceiptStates.confirming_duplicate))
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
            company_id=user.active_company_id,  # Add company_id support
            receipt_image_url=data.get('receipt_image_url'),  # Use S3 URL from state
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


@router.callback_query(F.data == "cancel_duplicate_photo", StateFilter(ReceiptStates.confirming_duplicate))
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


@router.callback_query(F.data.startswith("clarify_amount:"), StateFilter(ReceiptStates.clarifying_amount))
async def process_amount_clarification(callback: CallbackQuery, state: FSMContext):
    """Process amount clarification selection"""
    action = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        if action == "manual":
            # Ask user to enter amount manually
            await callback.message.edit_text(
                i18n.get("clarification.enter_amount_hint", locale),
                reply_markup=get_cancel_keyboard(locale)
            )
            await state.set_state(ReceiptStates.editing_amount)
        else:
            # User selected a suggested amount
            amount = Decimal(action)
            data = await state.get_data()
            
            # Update amount in state
            await state.update_data(
                amount=str(amount),
                amount_confirmed=True
            )
            
            # Check if category also needs clarification
            if data.get('needs_category_clarification'):
                await state.set_state(ReceiptStates.choosing_category)
                await callback.message.edit_text(
                    i18n.get("clarification.category_unclear", locale) + "\n\n" +
                    i18n.get("expense.choose_category", locale),
                    reply_markup=get_default_categories_keyboard(locale)
                )
            else:
                # Proceed to category selection
                await state.set_state(ReceiptStates.choosing_category)
                
                amount_formatted = expense_parser.format_amount(
                    amount, 
                    data.get('currency', user.primary_currency)
                )
                
                await callback.message.edit_text(
                    f"{i18n.get('clarification.amount_confirmed', locale, amount=amount_formatted)}\n\n"
                    f"{i18n.get('expense.choose_category', locale)}",
                    reply_markup=get_default_categories_keyboard(locale)
                )


@router.message(StateFilter(ReceiptStates.editing_amount))
async def process_manual_amount_input(message: Message, state: FSMContext):
    """Process manual amount input during clarification"""
    telegram_id = message.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Parse the text - it might contain amount and category/description
        text = message.text.strip()
        parsed = expense_parser.parse_expense(text)
        
        if not parsed or not parsed['amount']:
            # Try to parse as simple number
            try:
                amount_text = text.replace(',', '.')
                amount = Decimal(amount_text)
                
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                
                currency = user.primary_currency
                category = None
                description = None
            except (ValueError, InvalidOperation):
                await message.answer(
                    i18n.get("clarification.invalid_amount_format", locale),
                    reply_markup=get_cancel_keyboard(locale)
                )
                return
        else:
            # Use parsed data
            amount = parsed['amount']
            currency = parsed['currency'] or user.primary_currency
            category = None
            description = parsed['description']
            
            # Try to detect category from description
            if description:
                caption_data = caption_parser.parse(text)
                if caption_data['category']:
                    category = caption_data['category']
        
        data = await state.get_data()
        
        # Update amount and other data in state
        await state.update_data(
            amount=str(amount),
            currency=currency,
            amount_confirmed=True,
            description=description,
            detected_category=category or 'other'
        )
        
        amount_formatted = expense_parser.format_amount(amount, currency)
        
        # If we detected a category from the text, save transaction immediately
        if category and category != 'other':
            # Get the category object
            category_obj = await category_service.get_default_category(session, user.id, category)
            
            if category_obj:
                # Create transaction immediately
                transaction = await transaction_service.create_transaction(
                    session=session,
                    user_id=user.id,
                    amount=amount,
                    currency=currency,
                    category_id=category_obj.id,
                    description=description,
                    transaction_date=datetime.now(),
                    amount_primary=amount,
                    exchange_rate=Decimal('1.0000'),
                    company_id=user.active_company_id,  # Add company_id support
                    receipt_image_url=data.get('receipt_image_url'),  # Use S3 URL from state
                    ocr_confidence=Decimal('1.0')
                )
                
                await session.commit()
                
                # Get today's spending
                today_total, _ = await transaction_service.get_today_spending(session, user.id)
                
                # Format response
                today_formatted = expense_parser.format_amount(today_total, user.primary_currency)
                
                response = f"✅ {i18n.get('receipt.saved', locale)} "
                response += f"{amount_formatted} → {category_obj.icon} {category_obj.get_name(locale)}"
                
                if description:
                    response += f" ({description})"
                
                response += f"\n\n📊 {i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
                
                await message.answer(response)
                await state.clear()
                return
        
        # Otherwise, ask for category selection
        await state.set_state(ReceiptStates.choosing_category)
        message_text = f"{i18n.get('clarification.amount_confirmed', locale, amount=amount_formatted)}\n\n"
        
        if description:
            message_text += f"📝 {description}\n\n"
            
        message_text += i18n.get('expense.choose_category', locale)
        
        await message.answer(
            message_text,
            reply_markup=get_default_categories_keyboard(locale)
        )


@router.message(StateFilter(ReceiptStates.asking_description))
async def process_description_request(message: Message, state: FSMContext):
    """Process description input when AI can't determine category"""
    telegram_id = message.from_user.id
    description = message.text.strip()
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        # Update state with description
        await state.update_data(description=description)
        
        # Get state data
        data = await state.get_data()
        
        # Try to detect category from description using AI if available
        category_key = None
        
        # First try caption parser
        caption_data = caption_parser.parse(description)
        if caption_data.get('category') and caption_data['category'] != 'other':
            category_key = caption_data['category']
        
        # If no category found and OpenAI is available, use AI
        if not category_key and settings.use_openai_vision and settings.openai_api_key:
            try:
                from src.services.ocr_openai import OpenAIVisionService
                openai_service = OpenAIVisionService()
                ai_category = await openai_service.detect_category_from_description(
                    description, 
                    data.get('merchant')
                )
                if ai_category and ai_category != 'other':
                    category_key = ai_category
                    logger.info(f"AI detected category '{category_key}' from description: {description}")
            except Exception as e:
                logger.error(f"Error using AI for category detection: {e}")
        
        if category_key:
            # We found a category, save transaction automatically
            category = await category_service.get_default_category(session, user.id, category_key)
            
            if category:
                # Parse transaction date for duplicate check
                transaction_date = data.get('transaction_date')
                if transaction_date:
                    try:
                        transaction_date = datetime.fromisoformat(transaction_date)
                    except:
                        transaction_date = datetime.now()
                else:
                    transaction_date = datetime.now()
                
                # Check for duplicates using exact transaction date/time
                potential_duplicates = await duplicate_detector.find_duplicates(
                    session=session,
                    user_id=user.id,
                    amount=Decimal(data['amount']),
                    merchant=data.get('merchant'),
                    transaction_date=transaction_date,
                    time_window_hours=2  # Check within 2 hours window
                )
                
                if potential_duplicates:
                    # Found exact duplicate - show warning
                    duplicate_info = "⚠️ " + i18n.get("duplicate.found", locale) + "\n\n"
                    
                    for dup in potential_duplicates[:1]:  # Show only the most recent
                        dup_amount = expense_parser.format_amount(dup.amount, dup.currency)
                        dup_date = dup.transaction_date.strftime('%d.%m.%Y %H:%M')
                        dup_cat = dup.category.get_name(locale) if dup.category else "?"
                        
                        duplicate_info += f"💰 {dup_amount}\n"
                        duplicate_info += f"📅 {dup_date}\n"
                        duplicate_info += f"📂 {dup_cat}\n"
                        if dup.description:
                            duplicate_info += f"📝 {dup.description}\n"
                        if dup.merchant:
                            duplicate_info += f"📍 {dup.merchant}\n"
                    
                    duplicate_info += f"\n{i18n.get('duplicate.skip_info', locale)}"
                    
                    await message.answer(duplicate_info)
                    await state.clear()
                    return
                
                # Parse original transaction date for saving
                transaction_date = data.get('transaction_date')
                if transaction_date:
                    try:
                        transaction_date = datetime.fromisoformat(transaction_date)
                    except:
                        transaction_date = datetime.now()
                else:
                    transaction_date = datetime.now()
                
                # Create transaction
                amount_primary = Decimal(data.get('amount_primary', data['amount']))
                exchange_rate = Decimal(data.get('exchange_rate', '1.0000'))
                
                transaction = await transaction_service.create_transaction(
                    session=session,
                    user_id=user.id,
                    amount=Decimal(data['amount']),
                    currency=data['currency'],
                    category_id=category.id,
                    description=description,
                    merchant=data.get('merchant'),
                    transaction_date=transaction_date,
                    amount_primary=amount_primary,
                    exchange_rate=exchange_rate,
                    company_id=user.active_company_id,  # Add company_id support
                    receipt_image_url=data.get('receipt_image_url'),  # Use S3 URL from state
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
                
                response += f"\n📝 {description}"
                response += f"\n\n📊 {i18n.get('manual_input.today_spent', locale)}: {today_formatted}"
                
                await message.answer(response)
                await state.clear()
                return
        
        # Still can't determine category, ask user to choose
        await state.set_state(ReceiptStates.choosing_category)
        
        # Validate required data exists
        if not data or 'amount' not in data:
            await message.answer(
                i18n.get("errors.invalid_state", locale, 
                         default="❌ Произошла ошибка. Пожалуйста, попробуйте снова.")
            )
            await state.clear()
            return
        
        # Show receipt info with description
        amount_formatted = expense_parser.format_amount(
            Decimal(data['amount']), 
            data['currency']
        )
        
        message_text = f"💰 {i18n.get('receipt.amount', locale)}: {amount_formatted}\n"
        if data.get('merchant'):
            message_text += f"📍 {i18n.get('receipt.place', locale)}: {data['merchant']}\n"
        message_text += f"📝 {description}\n\n"
        message_text += i18n.get('expense.choose_category', locale)
        
        await message.answer(
            message_text,
            reply_markup=get_default_categories_keyboard(locale)
        )