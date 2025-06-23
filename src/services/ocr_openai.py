import base64
import logging
from typing import Dict, Optional, Any
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import json
from openai import AsyncOpenAI

from src.core.config import settings

logger = logging.getLogger(__name__)


class OpenAIVisionService:
    """Service for OCR processing using OpenAI Vision API"""
    
    def __init__(self):
        if settings.openai_api_key:
            self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        else:
            self.client = None
            
    async def process_receipt(self, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Process receipt image using OpenAI Vision API
        
        Returns:
            Dict with extracted data or None if processing failed
        """
        if not self.client:
            logger.error("OpenAI API key not configured")
            return None
            
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # Create prompt for receipt analysis
            prompt = """You are analyzing a receipt/bill image. Extract ALL information carefully.

            Look for these key elements in ANY language (Russian, Kazakh, English):
            1. Total amount (look for: ИТОГО, ИТОГ, Барлығы, Жалпы, TOTAL, К ОПЛАТЕ, Төлеуге)
            2. Currency symbols: ₸ (tenge), ₽ (ruble), $ (dollar), € (euro)
            3. Date and time of purchase
            4. Merchant/store name (usually at the top)
            5. Individual items with prices
            
            For Kazakhstani receipts specifically:
            - Currency is usually ₸ or "тг" or "KZT"
            - Amounts might have spaces: "1 000" means 1000
            - Common stores: Magnum, Small, Anvar, etc.
            - Donation keywords: садака, садақа, пожертвование, мечеть, мешіт, закят, зекет, фитр
            
            Carefully read ALL text on the receipt, including small print.
            
            Also determine the category based on merchant and items:
            - "food": restaurants, cafes, grocery stores (Magnum, Small, etc.)
            - "transport": taxi, Uber, Yandex, gas stations, parking
            - "shopping": clothing stores, electronics, general retail
            - "utilities": mobile operators (Tele2, Beeline, Kcell), internet, utilities
            - "health": pharmacies, clinics, medical services
            - "entertainment": cinema, games, subscriptions
            - "donation": charity, donations, sadaka, mosque donations, church donations
            - "other": if unclear
            
            Return ONLY this JSON structure:
            {
                "amount": <total amount as number>,
                "currency": "<KZT/RUB/USD/EUR>",
                "date": "<YYYY-MM-DD>",
                "time": "<HH:MM:SS>",
                "merchant": "<store name>",
                "items": ["<item1>", "<item2>"],
                "category": "<category from above list>"
            }
            
            IMPORTANT: Extract exact time from receipt if visible (usually shown as "Время: HH:MM:SS" or similar)"""
            
            # Call OpenAI Vision API
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # or "gpt-4-vision-preview" for better accuracy
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            # Parse response
            content = response.choices[0].message.content
            logger.info(f"OpenAI response: {content}")
            
            try:
                # Extract JSON from response
                # Sometimes GPT wraps JSON in markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                data = json.loads(content.strip())
                
                # Process and validate extracted data
                result = {
                    'amount': None,
                    'currency': 'KZT',
                    'date': None,
                    'merchant': None,
                    'items': [],
                    'confidence': 0.9  # OpenAI Vision is generally very confident
                }
                
                # Extract amount
                if 'amount' in data and data['amount']:
                    try:
                        result['amount'] = Decimal(str(data['amount']))
                    except (InvalidOperation, ValueError):
                        logger.warning(f"Invalid amount: {data['amount']}")
                
                # Extract currency
                if 'currency' in data and data['currency']:
                    currency = data['currency'].upper()
                    if currency in settings.supported_currencies:
                        result['currency'] = currency
                
                # Extract date and time
                if 'date' in data and data['date']:
                    try:
                        # Parse date
                        parsed_date = datetime.strptime(data['date'], '%Y-%m-%d')
                        
                        # Check if time is provided
                        if 'time' in data and data['time']:
                            try:
                                # Parse time and combine with date
                                time_parts = data['time'].split(':')
                                if len(time_parts) >= 2:
                                    hour = int(time_parts[0])
                                    minute = int(time_parts[1])
                                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                                    result['date'] = parsed_date.replace(
                                        hour=hour,
                                        minute=minute,
                                        second=second
                                    )
                                else:
                                    # Use current time if time format is invalid
                                    now = datetime.now()
                                    result['date'] = parsed_date.replace(
                                        hour=now.hour,
                                        minute=now.minute,
                                        second=now.second,
                                        microsecond=now.microsecond
                                    )
                            except (ValueError, IndexError):
                                # Use current time if parsing fails
                                now = datetime.now()
                                result['date'] = parsed_date.replace(
                                    hour=now.hour,
                                    minute=now.minute,
                                    second=now.second,
                                    microsecond=now.microsecond
                                )
                        else:
                            # No time provided, use current time
                            now = datetime.now()
                            result['date'] = parsed_date.replace(
                                hour=now.hour,
                                minute=now.minute,
                                second=now.second,
                                microsecond=now.microsecond
                            )
                    except ValueError:
                        # Try other date formats
                        for fmt in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d']:
                            try:
                                parsed_date = datetime.strptime(data['date'], fmt)
                                # Use current time since we already tried to parse time above
                                now = datetime.now()
                                result['date'] = parsed_date.replace(
                                    hour=now.hour,
                                    minute=now.minute,
                                    second=now.second,
                                    microsecond=now.microsecond
                                )
                                break
                            except ValueError:
                                continue
                
                # Extract merchant
                if 'merchant' in data and data['merchant']:
                    result['merchant'] = data['merchant'][:100]
                
                # Extract items
                if 'items' in data and isinstance(data['items'], list):
                    result['items'] = data['items'][:10]  # Limit to 10 items
                
                # Extract category
                if 'category' in data and data['category']:
                    result['category'] = data['category']
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {content}")
                
                # Try to extract amount using regex as fallback
                import re
                amount_match = re.search(r'(\d+(?:[.,]\d+)?)', content)
                if amount_match:
                    try:
                        amount_str = amount_match.group(1).replace(',', '.')
                        return {
                            'amount': Decimal(amount_str),
                            'currency': 'KZT',
                            'date': None,
                            'merchant': None,
                            'items': [],
                            'confidence': 0.5
                        }
                    except (InvalidOperation, ValueError):
                        pass
                
                return None
            
        except Exception as e:
            logger.error(f"OpenAI Vision processing error: {e}")
            return None
    
    async def detect_category_from_description(self, description: str, merchant: Optional[str] = None) -> Optional[str]:
        """Detect expense category from description using AI"""
        try:
            context = f"Description: {description}"
            if merchant:
                context += f"\nMerchant: {merchant}"
            
            prompt = f"""Based on this expense description, determine the most appropriate category.
            
            {context}
            
            Categories:
            - food (restaurants, groceries, cafes)
            - transport (taxi, gas, parking, public transport)
            - shopping (clothes, electronics, household items)
            - utilities (phone, internet, electricity, water)
            - health (pharmacy, medical, wellness)
            - entertainment (movies, games, sports, leisure)
            - education (courses, books, training)
            - donation (charity, religious donations)
            - other (if doesn't fit any category)
            
            Reply with just the category name, nothing else."""
            
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that categorizes expenses. Reply with just the category name."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.3
            )
            
            category = response.choices[0].message.content.strip().lower()
            
            # Validate category
            valid_categories = ['food', 'transport', 'shopping', 'utilities', 'health', 
                              'entertainment', 'education', 'donation', 'other']
            
            if category in valid_categories:
                return category
            
            # Try to map similar responses
            if any(word in category for word in ['food', 'restaurant', 'cafe', 'grocery']):
                return 'food'
            elif any(word in category for word in ['transport', 'taxi', 'gas', 'uber']):
                return 'transport'
            elif any(word in category for word in ['shop', 'cloth', 'electronic']):
                return 'shopping'
            elif any(word in category for word in ['utilit', 'phone', 'internet']):
                return 'utilities'
            elif any(word in category for word in ['health', 'medical', 'pharmacy']):
                return 'health'
            elif any(word in category for word in ['entertain', 'movie', 'game']):
                return 'entertainment'
            elif any(word in category for word in ['educat', 'course', 'book']):
                return 'education'
            elif any(word in category for word in ['donat', 'charity']):
                return 'donation'
            
            return 'other'
            
        except Exception as e:
            logger.error(f"Error detecting category from description: {e}")
            return None