import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import aiohttp
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)


class DynamicContentManager:
    """Manages dynamic content updates without bot restart"""
    
    def __init__(self, bot: Bot, config_url: Optional[str] = None):
        self.bot = bot
        self.config_url = config_url
        self.current_config: Dict[str, Any] = {}
        self.update_interval = 60  # Check for updates every minute
        self._update_task = None
        
    async def start(self):
        """Start periodic config updates"""
        self._update_task = asyncio.create_task(self._update_loop())
        
    async def stop(self):
        """Stop periodic updates"""
        if self._update_task:
            self._update_task.cancel()
            
    async def _update_loop(self):
        """Periodically check for config updates"""
        while True:
            try:
                await self.fetch_config()
                await asyncio.sleep(self.update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Config update error: {e}")
                await asyncio.sleep(self.update_interval)
                
    async def fetch_config(self):
        """Fetch configuration from remote source"""
        if not self.config_url:
            return
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.config_url) as response:
                    if response.status == 200:
                        new_config = await response.json()
                        if new_config != self.current_config:
                            self.current_config = new_config
                            logger.info("Configuration updated dynamically")
        except Exception as e:
            logger.error(f"Failed to fetch config: {e}")
            
    def get_keyboard(self, keyboard_name: str) -> Optional[InlineKeyboardMarkup]:
        """Get dynamic keyboard configuration"""
        keyboard_config = self.current_config.get('keyboards', {}).get(keyboard_name)
        if not keyboard_config:
            return None
            
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for row in keyboard_config.get('rows', []):
            buttons = []
            for btn in row:
                if btn.get('callback_data'):
                    buttons.append(InlineKeyboardButton(
                        text=btn['text'],
                        callback_data=btn['callback_data']
                    ))
                elif btn.get('url'):
                    buttons.append(InlineKeyboardButton(
                        text=btn['text'],
                        url=btn['url']
                    ))
            if buttons:
                keyboard.inline_keyboard.append(buttons)
                
        return keyboard
        
    def get_text(self, text_key: str, **kwargs) -> str:
        """Get dynamic text content"""
        text = self.current_config.get('texts', {}).get(text_key, '')
        try:
            return text.format(**kwargs)
        except:
            return text


class RemoteCommandHandler:
    """Handles remote commands without restart"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.command_queue = asyncio.Queue()
        self._worker_task = None
        
    async def start(self):
        """Start command worker"""
        self._worker_task = asyncio.create_task(self._process_commands())
        
    async def stop(self):
        """Stop command worker"""
        if self._worker_task:
            self._worker_task.cancel()
            
    async def add_command(self, command: Dict[str, Any]):
        """Add command to queue"""
        await self.command_queue.put(command)
        
    async def _process_commands(self):
        """Process queued commands"""
        while True:
            try:
                command = await self.command_queue.get()
                await self._execute_command(command)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Command execution error: {e}")
                
    async def _execute_command(self, command: Dict[str, Any]):
        """Execute a remote command"""
        cmd_type = command.get('type')
        
        if cmd_type == 'broadcast':
            # Send message to all users
            text = command.get('text')
            user_ids = command.get('user_ids', [])
            for user_id in user_ids:
                try:
                    await self.bot.send_message(user_id, text)
                except Exception:
                    pass
                    
        elif cmd_type == 'update_keyboard':
            # Update keyboard for active users
            message_id = command.get('message_id')
            chat_id = command.get('chat_id')
            keyboard = command.get('keyboard')
            
            try:
                await self.bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=keyboard
                )
            except Exception:
                pass