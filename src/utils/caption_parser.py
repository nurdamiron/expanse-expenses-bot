import re
import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class CaptionParser:
    """Parser for extracting amount and category from photo/document captions"""
    
    def __init__(self):
        # Category keywords in different languages
        self.category_keywords = {
            'food': ['еда', 'продукты', 'food', 'groceries', 'тамақ', 'азық-түлік', 
                    'обед', 'завтрак', 'ужин', 'кафе', 'ресторан', 'магазин', 'супермаркет',
                    'түскі ас', 'таңғы ас', 'кешкі ас', 'дүкен', 'pizza', 'бургер', 'кофе',
                    'small', 'magnum', 'anvar', 'galmart', 'metro', 'ашан', 'перекресток',
                    'пицца', 'суши', 'шаурма', 'столовая', 'буфет', 'кулинария', 'выпечка',
                    'хлеб', 'молоко', 'мясо', 'овощи', 'фрукты', 'напитки', 'алкоголь'],
            'transport': ['транспорт', 'такси', 'transport', 'taxi', 'көлік', 'такси',
                         'автобус', 'метро', 'бензин', 'газ', 'парковка', 'uber', 'яндекс',
                         'indriver', 'поездка', 'проезд', 'жол', 'билет', 'qazaq', 'helios',
                         'sinooil', 'kмg', 'поезд', 'самолет', 'аэропорт', 'вокзал'],
            'health': ['здоровье', 'аптека', 'лекарства', 'health', 'pharmacy', 'medicine', 
                      'денсаулық', 'дәріхана', 'дәрі', 'врач', 'больница', 'клиника',
                      'дәрігер', 'аурухана', 'емхана', 'анализ', 'таблетки', 'europharma',
                      'биосфера', 'садыхан', 'зерде', 'витамины', 'бады', 'маска', 'тест'],
            'entertainment': ['развлечения', 'entertainment', 'fun', 'ойын-сауық',
                            'кино', 'театр', 'концерт', 'игры', 'спорт', 'фитнес',
                            'боулинг', 'караоке', 'бар', 'клуб', 'отдых', 'kinopark',
                            'kinoplex', 'marwin', 'ps5', 'steam', 'spotify', 'netflix'],
            'shopping': ['покупки', 'shopping', 'shop', 'сатып алу', 'одежда', 'обувь',
                        'киім', 'аяқ киім', 'техника', 'электроника', 'косметика',
                        'zara', 'lcwaikiki', 'sulpak', 'technodom', 'мебель', 'hm',
                        'kaspi', 'wildberries', 'ozon', 'aliexpress', 'механа', 'dns'],
            'utilities': ['коммуналка', 'utilities', 'bills', 'коммуналдық', 'интернет',
                         'телефон', 'связь', 'электричество', 'вода', 'газ', 'свет',
                         'байланыс', 'жарық', 'су', 'beeline', 'activ', 'tele2', 'kcell',
                         'алматыэнергосбыт', 'алсеко', 'отбасы', 'кск', 'осмд'],
            'donation': ['садака', 'садақа', 'пожертвование', 'donation', 'charity',
                        'мечеть', 'мешіт', 'церковь', 'храм', 'фонд', 'помощь', 'көмек',
                        'қайырымдылық', 'благотворительность', 'зекет', 'закят'],
            'education': ['образование', 'учеба', 'education', 'study', 'білім', 'оқу',
                         'курсы', 'книги', 'кітап', 'школа', 'мектеп', 'университет',
                         'marwin', 'меломан', 'coursera', 'udemy', 'skillbox'],
            'other': ['другое', 'перевод', 'other', 'transfer', 'басқа', 'аудару']
        }
        
        # Amount patterns
        self.amount_patterns = [
            r'(\d+[.,]?\d*)\s*(?:₸|тг|kzt|тенге|tenge)',  # KZT
            r'(\d+[.,]?\d*)\s*(?:₽|руб|rub|рубл)',  # RUB
            r'(\d+[.,]?\d*)\s*(?:\$|usd|долл)',  # USD
            r'(\d+[.,]?\d*)\s*(?:€|eur|евро)',  # EUR
            r'^(\d+[.,]?\d*)$',  # Just number at the beginning
        ]
    
    def parse(self, caption: str) -> Dict[str, Optional[str]]:
        """
        Parse caption to extract amount and category
        
        Returns:
            Dict with 'amount', 'currency', and 'category' keys
        """
        if not caption:
            return {'amount': None, 'currency': None, 'category': None}
        
        caption_lower = caption.lower().strip()
        
        # Extract amount
        amount, currency = self._extract_amount(caption_lower)
        
        # Extract category
        category = self._extract_category(caption_lower)
        
        logger.info(f"Parsed caption: amount={amount}, currency={currency}, category={category}")
        
        return {
            'amount': amount,
            'currency': currency,
            'category': category
        }
    
    def _extract_amount(self, text: str) -> Tuple[Optional[Decimal], Optional[str]]:
        """Extract amount and currency from text"""
        for pattern in self.amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '.')
                    amount = Decimal(amount_str)
                    
                    # Determine currency
                    currency = None
                    if any(c in text for c in ['₸', 'тг', 'kzt', 'тенге', 'tenge']):
                        currency = 'KZT'
                    elif any(c in text for c in ['₽', 'руб', 'rub', 'рубл']):
                        currency = 'RUB'
                    elif any(c in text for c in ['$', 'usd', 'долл']):
                        currency = 'USD'
                    elif any(c in text for c in ['€', 'eur', 'евро']):
                        currency = 'EUR'
                    
                    return amount, currency
                except (InvalidOperation, ValueError):
                    continue
        
        return None, None
    
    def _extract_category(self, text: str) -> Optional[str]:
        """Extract category from text based on keywords"""
        # Remove amount patterns first to avoid false matches
        clean_text = text.lower()
        for pattern in self.amount_patterns:
            clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE).strip()
        
        # Track category scores
        category_scores = {}
        
        # Check each category's keywords
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                # Check for whole word match or partial match for longer words
                if len(keyword) <= 3:
                    # For short keywords, require word boundary
                    if re.search(r'\b' + re.escape(keyword) + r'\b', clean_text, re.IGNORECASE):
                        score += 2
                else:
                    # For longer keywords, allow partial match
                    if keyword.lower() in clean_text:
                        score += 1
            
            if score > 0:
                category_scores[category] = score
        
        # Return category with highest score, or None if no matches
        if category_scores:
            # Don't return 'other' if there are better matches
            filtered_scores = {k: v for k, v in category_scores.items() if k != 'other'}
            if filtered_scores:
                return max(filtered_scores, key=filtered_scores.get)
            return max(category_scores, key=category_scores.get)
        
        return None
    
    def suggest_description(self, caption: str, category: Optional[str] = None) -> str:
        """Generate a transaction description from caption"""
        if not caption:
            return ""
        
        # Remove amount patterns
        description = caption
        for pattern in self.amount_patterns:
            description = re.sub(pattern, '', description, flags=re.IGNORECASE).strip()
        
        # Remove category keywords if category was found
        if category and category in self.category_keywords:
            for keyword in self.category_keywords[category]:
                description = description.replace(keyword, '').strip()
        
        # Clean up multiple spaces
        description = ' '.join(description.split())
        
        return description or caption