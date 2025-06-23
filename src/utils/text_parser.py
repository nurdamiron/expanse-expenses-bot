import re
from typing import Optional, Tuple, Dict
from datetime import datetime, date
from decimal import Decimal, InvalidOperation


class ExpenseParser:
    """Parser for manual expense input"""
    
    # Patterns for amount detection
    AMOUNT_PATTERNS = [
        r'^(\d+(?:\.\d{1,2})?)\s+(.+)$',  # "500 coffee"
        r'^(\d+(?:\.\d{1,2})?)\s*(.*)$',   # "500" or "500coffee"
        r'^потратил\s+(\d+(?:\.\d{1,2})?)\s+на\s+(.+)$',  # "потратил 500 на кофе"
        r'^жұмсадым\s+(\d+(?:\.\d{1,2})?)\s+(.+)$',  # "жұмсадым 500 кофе"
    ]
    
    # Currency symbols and their codes
    CURRENCY_SYMBOLS = {
        '₸': 'KZT',
        '₽': 'RUB', 
        '$': 'USD',
        '€': 'EUR',
        '¥': 'CNY',
        '₩': 'KRW',
        '₺': 'TRY',
        'RM': 'MYR'  # Malaysian Ringgit
    }
    
    # Currency words
    CURRENCY_WORDS = {
        'тенге': 'KZT',
        'теңге': 'KZT',
        'рубль': 'RUB',
        'рублей': 'RUB',
        'руб': 'RUB',
        'доллар': 'USD',
        'долларов': 'USD',
        'евро': 'EUR',
        'юань': 'CNY',
        'юаней': 'CNY',
        'вон': 'KRW',
        'лира': 'TRY',
        'лир': 'TRY',
        'ринггит': 'MYR',
        'myr': 'MYR'
    }
    
    def parse_expense(self, text: str) -> Optional[Dict[str, any]]:
        """
        Parse expense from text message
        
        Returns dict with:
        - amount: Decimal
        - currency: str
        - description: str
        - date: Optional[date]
        """
        if not text:
            return None
        
        text = text.strip()
        
        # Try to extract currency first
        currency, text_without_currency = self._extract_currency(text)
        
        # Try each pattern
        for pattern in self.AMOUNT_PATTERNS:
            match = re.match(pattern, text_without_currency, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1)
                    description = match.group(2).strip() if len(match.groups()) > 1 else ""
                    
                    # Parse amount
                    amount = Decimal(amount_str)
                    if amount <= 0:
                        continue
                    
                    # Extract date from description if present
                    expense_date, description = self._extract_date(description)
                    
                    return {
                        'amount': amount,
                        'currency': currency,
                        'description': description or None,
                        'date': expense_date
                    }
                    
                except (InvalidOperation, ValueError):
                    continue
        
        return None
    
    def _extract_currency(self, text: str) -> Tuple[str, str]:
        """Extract currency from text and return (currency_code, text_without_currency)"""
        # Check for currency symbols
        for symbol, code in self.CURRENCY_SYMBOLS.items():
            if symbol in text:
                text = text.replace(symbol, '').strip()
                return code, text
        
        # Check for currency words
        text_lower = text.lower()
        for word, code in self.CURRENCY_WORDS.items():
            if word in text_lower:
                # Remove currency word using regex to handle word boundaries
                pattern = r'\b' + re.escape(word) + r'\b'
                text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()
                return code, text
        
        # Default currency
        return 'KZT', text
    
    def _extract_date(self, text: str) -> Tuple[Optional[date], str]:
        """Extract date from text if present"""
        if not text:
            return None, text
        
        # Common date keywords
        today_keywords = ['сегодня', 'бүгін']
        yesterday_keywords = ['вчера', 'кеше']
        
        text_lower = text.lower()
        
        # Check for today
        for keyword in today_keywords:
            if keyword in text_lower:
                text = re.sub(r'\b' + keyword + r'\b', '', text, flags=re.IGNORECASE).strip()
                return date.today(), text
        
        # Check for yesterday
        for keyword in yesterday_keywords:
            if keyword in text_lower:
                text = re.sub(r'\b' + keyword + r'\b', '', text, flags=re.IGNORECASE).strip()
                yesterday = date.today() - timedelta(days=1)
                return yesterday, text
        
        # Try to parse date formats
        date_patterns = [
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', '%d.%m.%Y'),
            (r'(\d{1,2})\.(\d{1,2})', '%d.%m'),
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', '%d/%m/%Y'),
            (r'(\d{1,2})/(\d{1,2})', '%d/%m'),
        ]
        
        for pattern, date_format in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    date_str = match.group(0)
                    
                    # Add current year if not specified
                    if len(match.groups()) == 2:
                        date_str += f'.{date.today().year}'
                        date_format += '.%Y'
                    
                    parsed_date = datetime.strptime(date_str, date_format).date()
                    
                    # Remove date from text
                    text = text.replace(match.group(0), '').strip()
                    
                    return parsed_date, text
                    
                except ValueError:
                    continue
        
        return None, text
    
    def format_amount(self, amount: Decimal, currency: str = 'KZT') -> str:
        """Format amount with currency symbol"""
        currency_symbols = {v: k for k, v in self.CURRENCY_SYMBOLS.items()}
        symbol = currency_symbols.get(currency, currency)
        
        # Format with thousands separator
        formatted = f"{amount:,.2f}".rstrip('0').rstrip('.')
        
        # Place symbol based on currency
        if currency in ['USD', 'EUR', 'CNY']:
            return f"{symbol}{formatted}"
        else:
            return f"{formatted}{symbol}"