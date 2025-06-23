"""Middleware to filter out bot messages"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class BotFilterMiddleware(BaseMiddleware):
    """Filter out messages from bots"""
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Skip processing if message/callback is from a bot
        if isinstance(event, Message):
            if event.from_user and event.from_user.is_bot:
                return
        elif isinstance(event, CallbackQuery):
            if event.from_user and event.from_user.is_bot:
                return
        
        return await handler(event, data)