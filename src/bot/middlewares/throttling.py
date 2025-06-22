from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from cachetools import TTLCache

from src.core.config import settings


class ThrottlingMiddleware(BaseMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, rate_limit: int = None):
        self.rate_limit = rate_limit or settings.rate_limit_requests_per_minute
        self.user_cache = TTLCache(maxsize=10000, ttl=60)  # 1 minute TTL
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        current_time = datetime.now()
        
        # Get user's request history
        user_requests = self.user_cache.get(user_id, [])
        
        # Remove old requests (older than 1 minute)
        cutoff_time = current_time - timedelta(minutes=1)
        user_requests = [req_time for req_time in user_requests if req_time > cutoff_time]
        
        # Check rate limit
        if len(user_requests) >= self.rate_limit:
            # User exceeded rate limit
            if isinstance(event, Message):
                await event.answer("⚠️ Слишком много запросов. Подождите немного.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ Слишком много запросов", show_alert=True)
            return
        
        # Add current request
        user_requests.append(current_time)
        self.user_cache[user_id] = user_requests
        
        # Process request
        return await handler(event, data)