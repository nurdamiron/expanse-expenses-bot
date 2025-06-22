import asyncio
import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

logger = logging.getLogger(__name__)


class BotReloadHandler(FileSystemEventHandler):
    """Handles file changes and triggers bot reload"""
    
    def __init__(self, reload_callback):
        self.reload_callback = reload_callback
        self.last_reload = 0
        self.reload_delay = 1.0  # Delay to batch multiple changes
        
    def on_modified(self, event):
        if isinstance(event, FileModifiedEvent) and event.src_path.endswith('.py'):
            current_time = asyncio.get_event_loop().time()
            if current_time - self.last_reload > self.reload_delay:
                self.last_reload = current_time
                asyncio.create_task(self.reload_callback())


class HotReloadManager:
    """Manages hot reload functionality for the bot"""
    
    def __init__(self, bot, dp, watch_paths: list[str]):
        self.bot = bot
        self.dp = dp
        self.watch_paths = watch_paths
        self.observer = None
        self._reload_lock = asyncio.Lock()
        
    async def start_watching(self):
        """Start watching for file changes"""
        self.observer = Observer()
        handler = BotReloadHandler(self.reload_bot)
        
        for path in self.watch_paths:
            self.observer.schedule(handler, path, recursive=True)
            
        self.observer.start()
        logger.info(f"Started watching paths: {self.watch_paths}")
        
    async def stop_watching(self):
        """Stop watching for file changes"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            
    async def reload_bot(self):
        """Reload bot handlers without full restart"""
        async with self._reload_lock:
            try:
                logger.info("Hot reload triggered...")
                
                # Clear all modules from cache
                modules_to_reload = [
                    name for name in sys.modules 
                    if name.startswith('src.bot.handlers') or 
                       name.startswith('src.bot.keyboards')
                ]
                
                for module_name in modules_to_reload:
                    if module_name in sys.modules:
                        del sys.modules[module_name]
                
                # Re-import and setup handlers
                from src.bot.handlers import setup_handlers
                
                # Clear existing handlers
                self.dp._routers.clear()
                
                # Re-setup handlers
                router = setup_handlers()
                self.dp.include_router(router)
                
                # Re-setup middlewares
                from src.bot.middlewares.throttling import ThrottlingMiddleware
                self.dp.message.middleware(ThrottlingMiddleware())
                self.dp.callback_query.middleware(ThrottlingMiddleware())
                
                logger.info("Hot reload completed successfully!")
                
                # Notify admins about reload
                if hasattr(self.bot, 'admin_ids'):
                    for admin_id in self.bot.admin_ids:
                        try:
                            await self.bot.send_message(
                                admin_id, 
                                "🔄 Bot handlers reloaded successfully!"
                            )
                        except Exception:
                            pass
                            
            except Exception as e:
                logger.error(f"Hot reload failed: {e}")