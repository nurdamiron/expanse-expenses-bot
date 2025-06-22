import logging
import asyncio
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from src.database.models import ExchangeRate
from src.core.config import settings

logger = logging.getLogger(__name__)


class CurrencyService:
    """Service for currency exchange rates"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.cache_ttl = 1800  # 30 minutes
        self.supported_currencies = settings.supported_currencies
        
        # API endpoints
        self.api_endpoints = {
            'fixer': {
                'url': 'http://data.fixer.io/api/latest',
                'params': {'access_key': settings.fixer_api_key},
                'enabled': bool(settings.fixer_api_key)
            },
            'exchangerate': {
                'url': 'https://v6.exchangerate-api.com/v6/{api_key}/latest/{base}',
                'enabled': bool(settings.exchangerate_api_key)
            },
            'nbkz': {
                'url': 'https://nationalbank.kz/rss/get_rates.cfm',
                'params': {'fdate': datetime.now().strftime('%d.%m.%Y')},
                'enabled': True
            }
        }
    
    async def init_redis(self):
        """Initialize Redis connection"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.redis_url)
    
    async def close_redis(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
    
    async def get_exchange_rate(
        self,
        from_currency: str,
        to_currency: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[Decimal]:
        """Get exchange rate from cache or API"""
        logger.info(f"[EXCHANGE RATE] Getting rate for {from_currency} -> {to_currency}")
        
        if from_currency == to_currency:
            logger.info(f"[EXCHANGE RATE] Same currency, returning 1.0000")
            return Decimal('1.0000')
        
        # Try to get from cache
        await self.init_redis()
        cache_key = f"rate:{from_currency}:{to_currency}"
        
        if self.redis_client:
            cached_rate = await self.redis_client.get(cache_key)
            if cached_rate:
                logger.info(f"[EXCHANGE RATE] Found in cache: {from_currency}/{to_currency} = {cached_rate}")
                return Decimal(cached_rate)
        
        # Try to get from database (recent rates)
        if session:
            rate = await self._get_rate_from_db(session, from_currency, to_currency)
            if rate:
                logger.info(f"[EXCHANGE RATE] Found in DB: {from_currency}/{to_currency} = {rate}")
                # Cache the rate
                if self.redis_client:
                    await self.redis_client.set(cache_key, str(rate), ex=self.cache_ttl)
                return rate
            else:
                logger.info(f"[EXCHANGE RATE] Not found in recent DB rates")
        
        # Fetch from API
        logger.info(f"[EXCHANGE RATE] Fetching rates from API")
        rates = await self._fetch_rates_from_api()
        if rates:
            # Calculate rate
            rate = self._calculate_rate(rates, from_currency, to_currency)
            if rate:
                logger.info(f"[EXCHANGE RATE] Got from API: {from_currency}/{to_currency} = {rate}")
                # Save to cache
                if self.redis_client:
                    await self.redis_client.set(cache_key, str(rate), ex=self.cache_ttl)
                
                # Save to database
                if session:
                    await self._save_rate_to_db(
                        session, from_currency, to_currency, rate, 'api'
                    )
                
                return rate
            else:
                logger.warning(f"[EXCHANGE RATE] Could not calculate rate from API data")
        else:
            logger.warning(f"[EXCHANGE RATE] No rates fetched from API")
        
        # Fallback to last known rate from DB
        if session:
            logger.info(f"[EXCHANGE RATE] Trying to get last known rate from DB")
            last_rate = await self._get_last_known_rate(session, from_currency, to_currency)
            if last_rate:
                logger.info(f"[EXCHANGE RATE] Found last known rate: {from_currency}/{to_currency} = {last_rate}")
                return last_rate
        
        logger.error(f"[EXCHANGE RATE] Could not get rate for {from_currency}/{to_currency}")
        return None
    
    async def get_all_rates(
        self,
        base_currency: str = 'KZT',
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Dict[str, any]]:
        """Get all exchange rates for base currency"""
        rates = {}
        
        # Fetch fresh rates
        api_rates = await self._fetch_rates_from_api()
        
        for currency in self.supported_currencies:
            if currency == base_currency:
                continue
            
            # Get rate
            if api_rates:
                rate = self._calculate_rate(api_rates, currency, base_currency)
            else:
                # Try from DB
                rate = await self._get_rate_from_db(session, currency, base_currency) if session else None
            
            if rate:
                # Get historical rate for comparison
                yesterday_rate = None
                if session:
                    yesterday_rate = await self._get_historical_rate(
                        session, currency, base_currency,
                        datetime.now() - timedelta(days=1)
                    )
                
                # Calculate change
                change_percent = 0
                if yesterday_rate and yesterday_rate > 0:
                    change_percent = float((rate - yesterday_rate) / yesterday_rate * 100)
                
                rates[currency] = {
                    'rate': rate,
                    'change_percent': round(change_percent, 2),
                    'direction': 'up' if change_percent > 0 else 'down' if change_percent < 0 else 'stable'
                }
        
        return rates
    
    async def convert_amount(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        session: Optional[AsyncSession] = None
    ) -> Optional[Tuple[Decimal, Decimal]]:
        """Convert amount between currencies. Returns (converted_amount, exchange_rate)"""
        logger.info(f"[CURRENCY SERVICE] Converting {amount} from {from_currency} to {to_currency}")
        
        if from_currency == to_currency:
            logger.info(f"[CURRENCY SERVICE] Same currency, no conversion needed")
            return amount, Decimal('1.0000')
        
        rate = await self.get_exchange_rate(from_currency, to_currency, session)
        if rate:
            converted = amount * rate
            logger.info(f"[CURRENCY SERVICE] Conversion rate: {rate}, converted amount: {converted}")
            return converted, rate
        
        logger.warning(f"[CURRENCY SERVICE] Could not get exchange rate for {from_currency} to {to_currency}")
        return None, None
    
    async def _fetch_rates_from_api(self) -> Optional[Dict[str, Decimal]]:
        """Fetch rates from available APIs"""
        all_rates = {}
        
        # Try NBKZ first for KZT rates
        logger.info("[FETCH RATES] Trying NBKZ API")
        nbkz_rates = await self._fetch_from_nbkz()
        if nbkz_rates:
            all_rates.update(nbkz_rates)
            logger.info(f"[FETCH RATES] Got {len(nbkz_rates)} rates from NBKZ")
        
        # Try ExchangeRate-API for missing currencies
        if self.api_endpoints['exchangerate']['enabled']:
            logger.info("[FETCH RATES] Trying ExchangeRate-API")
            exchange_rates = await self._fetch_from_exchangerate()
            if exchange_rates:
                all_rates.update(exchange_rates)
                logger.info(f"[FETCH RATES] Got {len(exchange_rates)} rates from ExchangeRate-API")
        
        # Try Fixer.io as last resort
        if self.api_endpoints['fixer']['enabled'] and not all_rates:
            logger.info("[FETCH RATES] Trying Fixer.io")
            fixer_rates = await self._fetch_from_fixer()
            if fixer_rates:
                all_rates.update(fixer_rates)
                logger.info(f"[FETCH RATES] Got {len(fixer_rates)} rates from Fixer.io")
        
        if all_rates:
            logger.info(f"[FETCH RATES] Total rates collected: {len(all_rates)}")
            return all_rates
        
        logger.error("[FETCH RATES] Failed to fetch rates from all APIs")
        return None
    
    async def _fetch_from_fixer(self) -> Optional[Dict[str, Decimal]]:
        """Fetch rates from Fixer.io"""
        try:
            retry_options = ExponentialRetry(attempts=3)
            async with RetryClient(retry_options=retry_options) as client:
                async with client.get(
                    self.api_endpoints['fixer']['url'],
                    params=self.api_endpoints['fixer']['params']
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            rates = {}
                            base = data['base']  # Usually EUR
                            
                            for currency, rate in data['rates'].items():
                                if currency in self.supported_currencies:
                                    rates[f"{base}:{currency}"] = Decimal(str(rate))
                            
                            logger.info(f"Fetched {len(rates)} rates from Fixer.io")
                            return rates
        except Exception as e:
            logger.error(f"Error fetching from Fixer.io: {e}")
        
        return None
    
    async def _fetch_from_exchangerate(self) -> Optional[Dict[str, Decimal]]:
        """Fetch rates from ExchangeRate-API"""
        try:
            rates = {}
            retry_options = ExponentialRetry(attempts=3)
            
            async with RetryClient(retry_options=retry_options) as client:
                # Fetch KZT as base
                url = self.api_endpoints['exchangerate']['url'].format(
                    api_key=settings.exchangerate_api_key,
                    base='KZT'
                )
                
                async with client.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('result') == 'success':
                            kzt_rates = data['conversion_rates']
                            
                            # Add all rates from/to KZT
                            for currency, rate in kzt_rates.items():
                                if currency in self.supported_currencies:
                                    rates[f"KZT:{currency}"] = Decimal(str(rate))
                                    if rate > 0:
                                        rates[f"{currency}:KZT"] = Decimal('1') / Decimal(str(rate))
                            
                            # Generate cross rates for all currency pairs
                            for from_curr in self.supported_currencies:
                                for to_curr in self.supported_currencies:
                                    if from_curr != to_curr and from_curr != 'KZT' and to_curr != 'KZT':
                                        key = f"{from_curr}:{to_curr}"
                                        if key not in rates:
                                            from_rate = kzt_rates.get(from_curr)
                                            to_rate = kzt_rates.get(to_curr)
                                            if from_rate and to_rate and from_rate != 0:
                                                # Cross rate: from_curr -> KZT -> to_curr
                                                rates[key] = Decimal(str(to_rate)) / Decimal(str(from_rate))
                            
                            logger.info(f"Fetched {len(rates)} rates from ExchangeRate-API")
                            return rates
        except Exception as e:
            logger.error(f"Error fetching from ExchangeRate-API: {e}")
        
        return None
    
    async def _fetch_from_nbkz(self) -> Optional[Dict[str, Decimal]]:
        """Fetch rates from National Bank of Kazakhstan"""
        try:
            import xml.etree.ElementTree as ET
            
            retry_options = ExponentialRetry(attempts=3)
            async with RetryClient(retry_options=retry_options) as client:
                async with client.get(
                    self.api_endpoints['nbkz']['url'],
                    params=self.api_endpoints['nbkz']['params']
                ) as response:
                    if response.status == 200:
                        xml_data = await response.text()
                        root = ET.fromstring(xml_data)
                        
                        rates = {}
                        currency_map = {
                            'USD': 'USD',
                            'EUR': 'EUR',
                            'RUB': 'RUB',
                            'CNY': 'CNY',
                            'KRW': 'KRW',
                            'TRY': 'TRY',
                            'SGD': 'SGD',
                            'GBP': 'GBP',
                            'JPY': 'JPY',
                            'AED': 'AED',
                            'THB': 'THB',
                            'MYR': 'MYR'
                        }
                        
                        for item in root.findall('.//item'):
                            code = item.find('title').text
                            if code in currency_map:
                                description = item.find('description').text
                                # Extract rate from description
                                rate_value = float(description.strip())
                                
                                # NBKZ gives how much KZT for 1 unit of currency
                                rates[f"{currency_map[code]}:KZT"] = Decimal(str(rate_value))
                                rates[f"KZT:{currency_map[code]}"] = Decimal('1') / Decimal(str(rate_value))
                        
                        logger.info(f"Fetched {len(rates)} rates from NBKZ")
                        return rates
        except Exception as e:
            logger.error(f"Error fetching from NBKZ: {e}")
        
        return None
    
    def _calculate_rate(
        self,
        rates: Dict[str, Decimal],
        from_currency: str,
        to_currency: str
    ) -> Optional[Decimal]:
        """Calculate exchange rate from available rates"""
        # Direct rate
        direct_key = f"{from_currency}:{to_currency}"
        if direct_key in rates:
            return rates[direct_key]
        
        # Reverse rate
        reverse_key = f"{to_currency}:{from_currency}"
        if reverse_key in rates:
            return Decimal('1') / rates[reverse_key]
        
        # Cross rate through common currency (usually USD or EUR)
        for base in ['USD', 'EUR', 'KZT']:
            from_base = f"{from_currency}:{base}"
            base_to = f"{base}:{to_currency}"
            
            if from_base in rates and base_to in rates:
                return rates[from_base] * rates[base_to]
            
            # Try reverse
            base_from = f"{base}:{from_currency}"
            to_base = f"{to_currency}:{base}"
            
            if base_from in rates and to_base in rates:
                return Decimal('1') / (rates[base_from] * rates[to_base])
        
        return None
    
    async def _get_rate_from_db(
        self,
        session: AsyncSession,
        from_currency: str,
        to_currency: str
    ) -> Optional[Decimal]:
        """Get recent rate from database"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        result = await session.execute(
            select(ExchangeRate)
            .where(
                and_(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                    ExchangeRate.fetched_at >= cutoff_time,
                    ExchangeRate.is_active == True
                )
            )
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        )
        
        rate = result.scalar_one_or_none()
        return rate.rate if rate else None
    
    async def _get_last_known_rate(
        self,
        session: AsyncSession,
        from_currency: str,
        to_currency: str
    ) -> Optional[Decimal]:
        """Get last known rate from database (no time limit)"""
        result = await session.execute(
            select(ExchangeRate)
            .where(
                and_(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                    ExchangeRate.is_active == True
                )
            )
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        )
        
        rate = result.scalar_one_or_none()
        return rate.rate if rate else None
    
    async def _get_historical_rate(
        self,
        session: AsyncSession,
        from_currency: str,
        to_currency: str,
        date: datetime
    ) -> Optional[Decimal]:
        """Get historical rate for specific date"""
        result = await session.execute(
            select(ExchangeRate)
            .where(
                and_(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                    ExchangeRate.fetched_at <= date,
                    ExchangeRate.is_active == True
                )
            )
            .order_by(ExchangeRate.fetched_at.desc())
            .limit(1)
        )
        
        rate = result.scalar_one_or_none()
        return rate.rate if rate else None
    
    async def _save_rate_to_db(
        self,
        session: AsyncSession,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        source: str
    ):
        """Save exchange rate to database"""
        exchange_rate = ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=rate,
            source=source
        )
        
        session.add(exchange_rate)
        await session.flush()


# Create global instance
currency_service = CurrencyService()