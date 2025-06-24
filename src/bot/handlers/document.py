import io
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, Document, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.database import get_session
from src.bot.states import ReceiptStates
from src.bot.keyboards import get_cancel_keyboard
from src.services.user import UserService
from src.services.category import CategoryService
from src.services.transaction import TransactionService
# Try to import OCRService
try:
    from src.services.ocr import OCRService
    OCR_AVAILABLE = True
except ImportError:
    OCRService = None
    OCR_AVAILABLE = False
from src.services.duplicate_detector import duplicate_detector
from src.utils.text_parser import ExpenseParser
from src.utils.caption_parser import CaptionParser
from src.utils.i18n import i18n
from src.core.config import settings
from src.services.currency import currency_service

router = Router()
logger = logging.getLogger(__name__)

user_service = UserService()
category_service = CategoryService()
transaction_service = TransactionService()
ocr_service = OCRService() if OCR_AVAILABLE else None
expense_parser = ExpenseParser()
caption_parser = CaptionParser()

# Supported document types
SUPPORTED_DOCUMENT_TYPES = {
    'application/pdf': '.pdf',
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/bmp': '.bmp',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/msword': '.doc',
}

# Maximum file sizes (in bytes)
MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20MB for documents
MAX_IMAGE_SIZE = 10 * 1024 * 1024     # 10MB for images


@router.message(F.document)
async def process_receipt_document(message: Message, state: FSMContext):
    """Process document containing receipt"""
    telegram_id = message.from_user.id
    document: Document = message.document
    caption = message.caption or ""
    
    logger.info(f"[DOCUMENT HANDLER] Received document from user {telegram_id}")
    logger.info(f"[DOCUMENT HANDLER] Document: {document.file_name}, MIME: {document.mime_type}, Size: {document.file_size}")
    
    # Check if already processing
    current_state = await state.get_state()
    if current_state:
        logger.info(f"[DOCUMENT HANDLER] User {telegram_id} is already in state: {current_state}")
        await message.answer("⏳ Пожалуйста, дождитесь завершения обработки предыдущего действия.")
        return
    
    # Set state immediately to prevent concurrent processing
    await state.set_state(ReceiptStates.processing_image)
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("/start")
            return
        
        locale = user.language_code
    
    # Check if OCR is enabled and available
    if not settings.enable_ocr:
        logger.warning(f"[DOCUMENT HANDLER] OCR is disabled in settings")
        await message.answer(
            i18n.get("errors.unknown", locale),
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    if not OCR_AVAILABLE or not ocr_service:
        logger.error(f"[DOCUMENT HANDLER] OCR dependencies are not installed")
        await message.answer(
            "OCR functionality is not available. Please install cv2 and pytesseract dependencies.",
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    # Check document type
    if document.mime_type not in SUPPORTED_DOCUMENT_TYPES:
        await message.answer(
            i18n.get("document.unsupported_format", locale),
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    # Check file size
    if document.file_size > MAX_DOCUMENT_SIZE:
        await message.answer(
            i18n.get("document.file_too_large", locale, max_size=MAX_DOCUMENT_SIZE // (1024 * 1024)),
            reply_markup=get_cancel_keyboard(locale)
        )
        return
    
    # Send processing message
    processing_msg = await message.answer(
        i18n.get("document.processing", locale)
    )
    
    await state.set_state(ReceiptStates.processing_image)
    
    try:
        # Download document
        bot = message.bot
        file = await bot.get_file(document.file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file.file_path, file_bytes)
        file_bytes.seek(0)
        
        # Process based on document type
        if document.mime_type == 'application/pdf':
            # Process PDF
            logger.info(f"[DOCUMENT HANDLER] Processing PDF document")
            try:
                from src.services.document_processor import DocumentProcessor
                doc_processor = DocumentProcessor()
                image_bytes = await doc_processor.pdf_to_image(file_bytes.getvalue())
            except ImportError:
                logger.error("DocumentProcessor dependencies not installed (pypdf, pdf2image)")
                await processing_msg.edit_text(
                    "PDF processing is not available. Please install pypdf and pdf2image dependencies.",
                    reply_markup=get_cancel_keyboard(locale)
                )
                await state.clear()
                return
            
            if not image_bytes:
                await processing_msg.edit_text(
                    i18n.get("document.pdf_conversion_error", locale),
                    reply_markup=get_cancel_keyboard(locale)
                )
                await state.clear()
                return
        
        elif document.mime_type.startswith('image/'):
            # Direct image processing
            image_bytes = file_bytes.getvalue()
        
        elif document.mime_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
            # Process Word document
            logger.info(f"[DOCUMENT HANDLER] Processing Word document")
            try:
                from src.services.document_processor import DocumentProcessor
                doc_processor = DocumentProcessor()
                image_bytes = await doc_processor.extract_images_from_docx(file_bytes.getvalue())
            except ImportError:
                logger.error("DocumentProcessor dependencies not installed (python-docx)")
                await processing_msg.edit_text(
                    "Word document processing is not available. Please install python-docx dependency.",
                    reply_markup=get_cancel_keyboard(locale)
                )
                await state.clear()
                return
            
            if not image_bytes:
                await processing_msg.edit_text(
                    i18n.get("document.no_images_found", locale),
                    reply_markup=get_cancel_keyboard(locale)
                )
                await state.clear()
                return
        
        else:
            # Fallback - try as image
            image_bytes = file_bytes.getvalue()
        
        # Process with OCR
        logger.info(f"[DOCUMENT HANDLER] Starting OCR processing")
        ocr_result = await ocr_service.process_receipt(image_bytes)
        logger.info(f"[DOCUMENT HANDLER] OCR result: {ocr_result}")
        
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
            document_file_id=document.file_id,
            document_name=document.file_name,
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
        
        receipt_info += f"\n{i18n.get('document.from_file', locale)}: {document.file_name}\n"
        
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
            'utilities': 'home',
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
            
            # Save category_id and document info to state for later use
            await state.update_data(
                category_id=category.id,
                document_name=document.file_name,
                document_type=document.mime_type
            )
            
            # Create confirmation keyboard
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            yes_text = i18n.get("buttons.yes", locale)
            no_text = i18n.get("buttons.no", locale)
            logger.info(f"[DUPLICATE BUTTONS] Creating buttons with locale '{locale}': yes='{yes_text}', no='{no_text}'")
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=yes_text,
                        callback_data="confirm_duplicate_document"
                    ),
                    InlineKeyboardButton(
                        text=no_text,
                        callback_data="cancel_duplicate_document"
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
            ocr_confidence=Decimal(str(data.get('ocr_confidence', 0))),
            metadata={
                'source': 'document',
                'document_name': document.file_name,
                'document_type': document.mime_type
            }
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
        logger.error(f"[DOCUMENT HANDLER] Error processing document: {e}", exc_info=True)
        await processing_msg.edit_text(
            i18n.get("document.processing_error", locale),
            reply_markup=get_cancel_keyboard(locale)
        )
        await state.clear()


@router.callback_query(F.data == "confirm_duplicate_document", StateFilter(ReceiptStates.confirming_duplicate))
async def confirm_duplicate_document(callback: CallbackQuery, state: FSMContext):
    """Confirm saving duplicate transaction from document"""
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
            ocr_confidence=Decimal(str(data.get('ocr_confidence', 0))),
            metadata={
                'source': 'document',
                'document_name': data.get('document_name', 'unknown'),
                'document_type': data.get('document_type', 'unknown')
            }
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


@router.callback_query(F.data == "cancel_duplicate_document", StateFilter(ReceiptStates.confirming_duplicate))
async def cancel_duplicate_document(callback: CallbackQuery, state: FSMContext):
    """Cancel saving duplicate transaction from document"""
    telegram_id = callback.from_user.id
    
    async with get_session() as session:
        user = await user_service.get_user_by_telegram_id(session, telegram_id)
        locale = user.language_code
        
        await callback.message.edit_text(
            "❌ " + (i18n.get("duplicate.cancelled", locale))
        )
        await state.clear()