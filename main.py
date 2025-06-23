import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from redis.asyncio import Redis

# Add src to Python path
sys.path.append(str(Path(__file__).parent))

from src.core.config import settings
from src.database import init_db, close_db
from src.bot.handlers import setup_handlers

logger = logging.getLogger(__name__)


async def main():
    """Main bot function"""
    # Configure logging
    logging.basicConfig(
        level=settings.log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    # Initialize storage for FSM
    # Use MemoryStorage for local development (Redis not available)
    storage = MemoryStorage()
    redis = None  # Will be None when using MemoryStorage
    
    # Initialize bot
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Initialize dispatcher
    dp = Dispatcher(storage=storage)
    
    # Setup middlewares
    from src.bot.middlewares.throttling import ThrottlingMiddleware
    from src.bot.middlewares.bot_filter import BotFilterMiddleware
    
    # Add bot filter middleware first (to filter out bot messages)
    dp.message.middleware(BotFilterMiddleware())
    dp.callback_query.middleware(BotFilterMiddleware())
    
    # Add throttling middleware
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())
    
    # Setup handlers
    router = setup_handlers()
    dp.include_router(router)
    
    # Start bot
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Graceful shutdown
        logger.info("Shutting down bot...")
        
        # Close bot session
        await bot.session.close()
        
        # Close Redis connection if available
        if redis:
            await redis.aclose()
        
        # Wait a bit for any pending operations
        await asyncio.sleep(0.1)
        
        # Close database connections
        await close_db()
        
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")