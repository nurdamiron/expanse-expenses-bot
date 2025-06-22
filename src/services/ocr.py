import re
import logging
from typing import Dict, Optional, Any
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import cv2
import numpy as np
import pytesseract
from PIL import Image
import io
import os

from src.core.config import settings
from .ocr_openai import OpenAIVisionService

logger = logging.getLogger(__name__)


class OCRService:
    """Service for OCR processing of receipts"""
    
    def __init__(self):
        # Configure pytesseract
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path
        
        # Set tessdata path if provided
        if settings.tessdata_prefix:
            os.environ['TESSDATA_PREFIX'] = settings.tessdata_prefix
            
        # Initialize OpenAI Vision service if configured
        self.openai_service = OpenAIVisionService() if settings.use_openai_vision else None
        # Currency patterns
        self.currency_patterns = {
            'KZT': [r'₸', r'тг', r'kzt', r'тенге'],
            'RUB': [r'₽', r'руб', r'rub', r'рубл'],
            'USD': [r'\$', r'usd', r'долл'],
            'EUR': [r'€', r'eur', r'евро'],
        }
        
        # Amount patterns
        self.amount_patterns = [
            r'(?:итого|total|сумма|барлығы)[:\s]*([0-9]+[.,]?[0-9]*)',
            r'(?:к оплате|to pay|төлеуге)[:\s]*([0-9]+[.,]?[0-9]*)',
            r'(?:всего|жалпы)[:\s]*([0-9]+[.,]?[0-9]*)',
            r'([0-9]+[.,]?[0-9]*)\s*(?:₸|₽|\$|€)',
        ]
        
        # Date patterns
        self.date_patterns = [
            r'(\d{2})[./](\d{2})[./](\d{4})',  # DD.MM.YYYY or DD/MM/YYYY
            r'(\d{2})[./](\d{2})[./](\d{2})',   # DD.MM.YY or DD/MM/YY
            r'(\d{4})-(\d{2})-(\d{2})',         # YYYY-MM-DD
        ]
        
    async def process_receipt(self, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Process receipt image and extract information
        
        Returns:
            Dict with extracted data or None if processing failed
        """
        logger.info(f"[OCR SERVICE] Starting receipt processing, image size: {len(image_bytes)} bytes")
        
        # Try OpenAI Vision first if configured
        if self.openai_service and settings.use_openai_vision:
            logger.info("Using OpenAI Vision for OCR")
            result = await self.openai_service.process_receipt(image_bytes)
            if result and result.get('amount'):
                return result
            logger.warning("OpenAI Vision failed, falling back to Tesseract")
        
        # Fallback to Tesseract
        logger.info("[OCR SERVICE] Using Tesseract for OCR")
        try:
            # Convert bytes to image
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            logger.info(f"[OCR SERVICE] Image decoded, shape: {image.shape if image is not None else 'None'}")
            
            # Preprocess image
            processed_image = self._preprocess_image(image)
            
            # Extract text using Tesseract
            # Try with available languages
            try:
                text = pytesseract.image_to_string(
                    processed_image,
                    lang='rus+eng',  # Russian and English
                    config='--psm 6'  # Assume uniform block of text
                )
            except Exception as e:
                logger.warning(f"Failed with rus+eng, trying eng only: {e}")
                text = pytesseract.image_to_string(
                    processed_image,
                    lang='eng',  # English only fallback
                    config='--psm 6'  # Assume uniform block of text
                )
            
            logger.info(f"[OCR SERVICE] Extracted text: {text[:200]}...")
            
            # Parse extracted text
            result = self._parse_receipt_text(text)
            logger.info(f"[OCR SERVICE] Parsed result: {result}")
            
            # Calculate confidence based on what was found
            confidence = self._calculate_confidence(result)
            result['confidence'] = confidence
            
            return result
            
        except Exception as e:
            logger.error(f"[OCR SERVICE] OCR processing error: {e}", exc_info=True)
            return None
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold to get black and white image
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh)
        
        # Resize if too small
        height, width = denoised.shape
        if width < 1000:
            scale = 1000 / width
            new_width = int(width * scale)
            new_height = int(height * scale)
            denoised = cv2.resize(denoised, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        
        return denoised
    
    def _parse_receipt_text(self, text: str) -> Dict[str, Any]:
        """Parse receipt text and extract structured data"""
        result = {
            'amount': None,
            'currency': 'KZT',  # Default currency
            'date': None,
            'merchant': None,
            'items': [],
            'category': None
        }
        
        # Clean text
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = ' '.join(text.split())  # Normalize spaces
        
        # Extract amount
        amount = self._extract_amount(text)
        if amount:
            result['amount'] = amount
        
        # Extract currency
        currency = self._extract_currency(text)
        if currency:
            result['currency'] = currency
        
        # Extract date
        receipt_date = self._extract_date(text)
        if receipt_date:
            result['date'] = receipt_date
        
        # Extract merchant
        merchant = self._extract_merchant(text)
        if merchant:
            result['merchant'] = merchant
        
        # Detect category based on merchant and text
        category = self._detect_category(text, merchant)
        if category:
            result['category'] = category
            logger.info(f"[OCR SERVICE] Detected category: {category}")
        else:
            result['category'] = 'other'
            logger.info(f"[OCR SERVICE] No category detected, defaulting to 'other'")
        
        return result
    
    def _extract_amount(self, text: str) -> Optional[Decimal]:
        """Extract amount from text"""
        amounts_found = []
        
        for pattern in self.amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    # Clean amount string
                    amount_str = match if isinstance(match, str) else match[0]
                    amount_str = amount_str.replace(',', '.').replace(' ', '')
                    
                    amount = Decimal(amount_str)
                    if amount > 0:
                        amounts_found.append(amount)
                except (InvalidOperation, ValueError):
                    continue
        
        if amounts_found:
            # Return the largest amount (usually the total)
            return max(amounts_found)
        
        # Try to find any number that looks like an amount
        all_numbers = re.findall(r'\d+[.,]?\d*', text)
        for num_str in all_numbers:
            try:
                num = Decimal(num_str.replace(',', '.'))
                if 10 <= num <= 10000000:  # Reasonable amount range
                    amounts_found.append(num)
            except (InvalidOperation, ValueError):
                continue
        
        return max(amounts_found) if amounts_found else None
    
    def _extract_currency(self, text: str) -> str:
        """Extract currency from text"""
        text_lower = text.lower()
        
        for currency, patterns in self.currency_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return currency
        
        return 'KZT'  # Default currency
    
    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract date from text"""
        for pattern in self.date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    groups = match.groups()
                    
                    if len(groups) == 3:
                        if len(groups[0]) == 4:  # YYYY-MM-DD
                            year, month, day = groups
                        else:  # DD.MM.YYYY or DD.MM.YY
                            day, month, year = groups
                            if len(year) == 2:
                                year = '20' + year
                        
                        receipt_date = datetime(int(year), int(month), int(day))
                        
                        # Validate date is not in future
                        if receipt_date.date() <= date.today():
                            return receipt_date
                            
                except ValueError:
                    continue
        
        return None
    
    def _extract_merchant(self, text: str) -> Optional[str]:
        """Extract merchant name from text"""
        # Common merchant indicators
        merchant_indicators = [
            r'(?:ооо|ип|тоо|жшс)\s+["\']?([а-яА-Яa-zA-Z0-9\s\-]+)',
            r'(?:магазин|супермаркет|market|shop)\s+["\']?([а-яА-Яa-zA-Z0-9\s\-]+)',
            r'^([а-яА-Яa-zA-Z0-9\s\-]+?)(?:\s+ооо|\s+ип|\s+тоо)',
        ]
        
        for pattern in merchant_indicators:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                merchant = match.group(1).strip()
                # Clean up merchant name
                merchant = ' '.join(merchant.split())
                if len(merchant) > 3:
                    return merchant[:100]  # Limit length
        
        # Try to find any capitalized phrase at the beginning
        lines = text.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if 5 < len(line) < 100 and line[0].isupper():
                return line
        
        return None
    
    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate confidence score based on extracted data"""
        confidence = 0.0
        
        if result.get('amount'):
            confidence += 0.5
        
        if result.get('date'):
            confidence += 0.2
        
        if result.get('merchant'):
            confidence += 0.2
        
        if result.get('currency') != 'KZT':  # Non-default currency found
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _detect_category(self, text: str, merchant: Optional[str] = None) -> Optional[str]:
        """Detect expense category based on text and merchant"""
        text_lower = text.lower()
        merchant_lower = merchant.lower() if merchant else ""
        
        logger.info(f"[CATEGORY DETECTION] Text: {text_lower[:100]}")
        logger.info(f"[CATEGORY DETECTION] Merchant: {merchant_lower}")
        
        # Category patterns
        category_patterns = {
            'food': [
                r'(?:ресторан|кафе|бар|пиццери|суши|кофе|coffee|restaurant|cafe|bar|pizza)',
                r'(?:продукт|магазин|супермаркет|гипермаркет|market|grocery)',
                r'(?:kfc|mcdonalds|burger king|subway|starbucks|costa)',
                r'(?:магнум|magnum|small|смолл|галамарт|galamart)',
            ],
            'transport': [
                r'(?:такси|taxi|uber|yandex|яндекс|indriver)',
                r'(?:автобус|метро|трамвай|bus|metro|subway)',
                r'(?:бензин|газ|заправка|азс|fuel|petrol|gas station)',
                r'(?:парковка|parking)',
            ],
            'shopping': [
                r'(?:одежда|обувь|clothes|shoes|zara|h&m|uniqlo)',
                r'(?:техника|электроника|electronics|technodom|sulpak)',
                r'(?:косметика|парфюм|cosmetics|perfume)',
                r'(?:спорт|sport|decathlon)',
            ],
            'utilities': [
                r'(?:мобильн|сотов|связь|mobile|beeline|activ|altel|tele2)',
                r'(?:интернет|internet|казахтелеком|kazakhtelecom)',
                r'(?:коммунальн|квартплата|жкх|utility)',
                r'(?:электричеств|свет|газ|вода|electricity|water|gas)',
            ],
            'health': [
                r'(?:аптека|pharmacy|europharma|садыхан|биосфера)',
                r'(?:клиника|больница|поликлиника|clinic|hospital)',
                r'(?:стоматолог|dentist|зуб)',
                r'(?:анализ|узи|мрт|analysis|ultrasound)',
            ],
            'entertainment': [
                r'(?:кино|cinema|kinopark|kinoplex)',
                r'(?:театр|концерт|theatre|concert)',
                r'(?:фитнес|спортзал|gym|fitness)',
                r'(?:боулинг|караоке|bowling|karaoke)',
            ],
            'donation': [
                r'(?:садака|садақа|садага|sadaka|sadaqa)',
                r'(?:пожертвование|donation|charity)',
                r'(?:благотворительность|charitable)',
                r'(?:мечеть|мешіт|mosque|masjid)',
                r'(?:мечети|мешітке)',  # Added variations for "to/in mosque"
                r'(?:церковь|church|храм)',
                r'(?:фонд|foundation|fund)',
                r'(?:помощь|көмек|help|aid)',
                r'(?:фитр|фітір|fitr|fitrah)',
                r'(?:закят|зекет|zakat)',
                r'(?:пітір|питир|питр)',
                r'садака\s+в\s+мечети',  # Specific pattern for "sadaka v mecheti"
            ],
        }
        
        # Check patterns
        for category, patterns in category_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower) or re.search(pattern, merchant_lower):
                    logger.info(f"[CATEGORY DETECTION] Matched category '{category}' with pattern '{pattern}'")
                    return category
        
        # Check for specific merchants
        merchant_categories = {
            'magnum': 'food',
            'small': 'food',
            'anvar': 'food',
            'galmart': 'food',
            'galamart': 'food',
            'carrefour': 'food',
            'yandex': 'transport',
            'uber': 'transport',
            'indriver': 'transport',
            'beeline': 'utilities',
            'activ': 'utilities',
            'altel': 'utilities',
            'tele2': 'utilities',
            'kazakhtelecom': 'utilities',
            'kaspi': 'other',  # Could be various categories
            'halyk': 'other',  # Could be various categories
        }
        
        for merchant_key, category in merchant_categories.items():
            if merchant_key in merchant_lower:
                logger.info(f"[CATEGORY DETECTION] Matched merchant '{merchant_key}' to category '{category}'")
                return category
        
        logger.info(f"[CATEGORY DETECTION] No category match found, returning 'other'")
        return 'other'