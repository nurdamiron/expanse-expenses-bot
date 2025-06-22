"""
Zero-downtime update mechanism for Telegram bot
"""
import asyncio
import os
import signal
import subprocess
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


class ZeroDowntimeUpdater:
    """Manages zero-downtime updates for the bot"""
    
    def __init__(self, bot: Bot, admin_ids: list[int]):
        self.bot = bot
        self.admin_ids = admin_ids
        self.update_in_progress = False
        self.pending_update = False
        
    async def check_for_updates(self) -> bool:
        """Check if updates are available"""
        try:
            # Check git for updates
            result = subprocess.run(
                ["git", "fetch", "origin", "main"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                return False
            
            # Compare local and remote
            local = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True
            ).stdout.strip()
            
            remote = subprocess.run(
                ["git", "rev-parse", "origin/main"],
                capture_output=True,
                text=True
            ).stdout.strip()
            
            return local != remote
            
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return False
    
    async def notify_admins(self, message: str):
        """Notify admins about update status"""
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, f"🔄 {message}")
            except TelegramAPIError:
                pass
    
    async def perform_update(self):
        """Perform the update with zero downtime"""
        if self.update_in_progress:
            return
        
        self.update_in_progress = True
        
        try:
            # Notify admins
            await self.notify_admins("Starting automatic update...")
            
            # Pull latest changes
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                await self.notify_admins(f"Update failed: {result.stderr}")
                return
            
            # Check if requirements changed
            if "requirements.txt" in result.stdout:
                await self.notify_admins("Installing new dependencies...")
                pip_result = subprocess.run(
                    ["pip", "install", "-r", "requirements.txt"],
                    capture_output=True,
                    text=True
                )
                
                if pip_result.returncode != 0:
                    await self.notify_admins(f"Dependency installation failed: {pip_result.stderr}")
                    return
            
            # Schedule graceful restart
            await self.notify_admins("Update completed. Scheduling graceful restart...")
            self.pending_update = True
            
            # Send SIGUSR1 to trigger graceful restart
            os.kill(os.getpid(), signal.SIGUSR1)
            
        except Exception as e:
            logger.error(f"Update error: {e}")
            await self.notify_admins(f"Update error: {str(e)}")
        finally:
            self.update_in_progress = False
    
    async def auto_update_loop(self, check_interval: int = 300):
        """Periodically check for updates"""
        while True:
            try:
                if await self.check_for_updates():
                    logger.info("Updates available, starting update process...")
                    await self.perform_update()
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-update error: {e}")
                await asyncio.sleep(check_interval)


class GracefulShutdownHandler:
    """Handles graceful shutdown and restart"""
    
    def __init__(self, bot: Bot, dp):
        self.bot = bot
        self.dp = dp
        self.should_restart = False
        
    def handle_restart_signal(self, signum, frame):
        """Handle restart signal"""
        logger.info("Received restart signal")
        self.should_restart = True
        
        # Stop polling gracefully
        asyncio.create_task(self.graceful_shutdown())
    
    async def graceful_shutdown(self):
        """Perform graceful shutdown"""
        try:
            # Notify active users
            # This is optional - you might not want to notify all users
            
            # Stop accepting new updates
            await self.dp.stop_polling()
            
            # Wait for ongoing updates to complete
            await asyncio.sleep(2)
            
            # Close bot session
            await self.bot.session.close()
            
            if self.should_restart:
                # Restart the bot process
                logger.info("Restarting bot...")
                os.execv(sys.executable, ['python'] + sys.argv)
                
        except Exception as e:
            logger.error(f"Graceful shutdown error: {e}")


def setup_auto_updates(bot: Bot, dp, admin_ids: list[int]) -> ZeroDowntimeUpdater:
    """Setup automatic update system"""
    updater = ZeroDowntimeUpdater(bot, admin_ids)
    
    # Setup signal handlers
    shutdown_handler = GracefulShutdownHandler(bot, dp)
    signal.signal(signal.SIGUSR1, shutdown_handler.handle_restart_signal)
    
    # Start auto-update loop
    asyncio.create_task(updater.auto_update_loop())
    
    return updater