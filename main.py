import asyncio
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
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
    
    # Initialize Redis for FSM storage
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    storage = RedisStorage(redis=redis)
    
    # Initialize bot
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Initialize dispatcher
    dp = Dispatcher(storage=storage)
    
    # Setup middlewares
    from src.bot.middlewares.throttling import ThrottlingMiddleware
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
        
        # Close Redis connection
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