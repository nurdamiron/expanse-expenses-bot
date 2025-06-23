from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.database.models import User


class UserService:
    """Service for user operations"""
    
    async def get_user_by_telegram_id(
        self,
        session: AsyncSession,
        telegram_id: int
    ) -> Optional[User]:
        """Get user by telegram ID"""
        result = await session.execute(
            select(User)
            .options(joinedload(User.active_company))
            .where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def create_user(
        self,
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: str = 'ru'
    ) -> User:
        """Create new user"""
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code
        )
        session.add(user)
        await session.flush()
        return user
    
    async def update_user_language(
        self,
        session: AsyncSession,
        user_id: int,
        language_code: str
    ) -> None:
        """Update user language"""
        user = await session.get(User, user_id)
        if user:
            user.language_code = language_code
            await session.commit()
    
    async def update_user_currency(
        self,
        session: AsyncSession,
        user_id: int,
        currency: str
    ) -> None:
        """Update user primary currency"""
        user = await session.get(User, user_id)
        if user:
            user.primary_currency = currency
            await session.commit()
    
    async def update_user_timezone(
        self,
        session: AsyncSession,
        user_id: int,
        timezone: str
    ) -> None:
        """Update user timezone"""
        user = await session.get(User, user_id)
        if user:
            user.timezone = timezone
            await session.commit()
    
    async def get_or_create_user(
        self,
        session: AsyncSession,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """Get existing user or create new one"""
        user = await self.get_user_by_telegram_id(session, telegram_id)
        
        if not user:
            user = await self.create_user(
                session=session,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            await session.commit()
        
        return user