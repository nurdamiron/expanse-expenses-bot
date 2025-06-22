from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import uuid4

from src.database.models import Category, User


class CategoryService:
    """Service for category operations"""
    
    async def get_user_categories(
        self,
        session: AsyncSession,
        user_id: int,
        active_only: bool = True
    ) -> List[Category]:
        """Get all categories for user"""
        query = select(Category).where(Category.user_id == user_id)
        
        if active_only:
            query = query.where(Category.is_active == True)
        
        query = query.order_by(Category.order_position, Category.created_at)
        
        result = await session.execute(query)
        return result.scalars().all()
    
    async def get_category_by_id(
        self,
        session: AsyncSession,
        category_id: str,
        user_id: int
    ) -> Optional[Category]:
        """Get category by ID for specific user"""
        result = await session.execute(
            select(Category).where(
                and_(
                    Category.id == category_id,
                    Category.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def create_category(
        self,
        session: AsyncSession,
        user_id: int,
        name_ru: str,
        name_kz: str,
        icon: str,
        color: str = '#000000',
        is_default: bool = False
    ) -> Category:
        """Create new category"""
        # Get max order position
        result = await session.execute(
            select(Category.order_position)
            .where(Category.user_id == user_id)
            .order_by(Category.order_position.desc())
            .limit(1)
        )
        max_position = result.scalar() or 0
        
        category = Category(
            id=str(uuid4()),
            user_id=user_id,
            name_ru=name_ru,
            name_kz=name_kz,
            icon=icon,
            color=color,
            is_default=is_default,
            order_position=max_position + 1
        )
        
        session.add(category)
        await session.flush()
        return category
    
    async def update_category(
        self,
        session: AsyncSession,
        category_id: str,
        user_id: int,
        **kwargs
    ) -> Optional[Category]:
        """Update category"""
        category = await self.get_category_by_id(session, category_id, user_id)
        
        if not category:
            return None
        
        for key, value in kwargs.items():
            if hasattr(category, key) and value is not None:
                setattr(category, key, value)
        
        await session.flush()
        return category
    
    async def delete_category(
        self,
        session: AsyncSession,
        category_id: str,
        user_id: int
    ) -> bool:
        """Soft delete category"""
        category = await self.get_category_by_id(session, category_id, user_id)
        
        if not category or category.is_default:
            return False
        
        category.is_active = False
        await session.flush()
        return True
    
    async def get_default_category(
        self,
        session: AsyncSession,
        user_id: int,
        key: str = 'other'
    ) -> Optional[Category]:
        """Get default category by key"""
        # Map keys to Russian names
        default_names = {
            'food': 'Еда и рестораны',
            'transport': 'Транспорт',
            'shopping': 'Покупки и одежда',
            'home': 'Дом и коммунальные',
            'health': 'Здоровье',
            'entertainment': 'Развлечения',
            'education': 'Образование',
            'donation': 'Пожертвования',
            'other': 'Прочее'
        }
        
        name_ru = default_names.get(key, 'Прочее')
        
        result = await session.execute(
            select(Category).where(
                and_(
                    Category.user_id == user_id,
                    Category.name_ru == name_ru,
                    Category.is_default == True
                )
            ).limit(1)  # Take only the first one if duplicates exist
        )
        return result.scalar_one_or_none()
    
    async def get_or_create_default_categories(
        self,
        session: AsyncSession,
        user_id: int
    ) -> List[Category]:
        """Get or create default categories for user"""
        categories = await self.get_user_categories(session, user_id)
        
        if not categories:
            # Create default categories
            default_categories = [
                ('Еда и рестораны', 'Тамақ және мейрамханалар', '🍔', 1),
                ('Транспорт', 'Көлік', '🚗', 2),
                ('Покупки и одежда', 'Сатып алулар мен киім', '🛒', 3),
                ('Дом и коммунальные', 'Үй және коммуналдық', '🏠', 4),
                ('Здоровье', 'Денсаулық', '💊', 5),
                ('Развлечения', 'Ойын-сауық', '🎬', 6),
                ('Образование', 'Білім беру', '📚', 7),
                ('Пожертвования', 'Садақа', '🤲', 8),
                ('Прочее', 'Басқа', '💰', 9)
            ]
            
            for name_ru, name_kz, icon, position in default_categories:
                category = Category(
                    id=str(uuid4()),
                    user_id=user_id,
                    name_ru=name_ru,
                    name_kz=name_kz,
                    icon=icon,
                    is_default=True,
                    order_position=position
                )
                session.add(category)
            
            await session.flush()
            categories = await self.get_user_categories(session, user_id)
        
        return categories
    
    async def create_default_categories(
        self,
        session: AsyncSession,
        user_id: int
    ) -> List[Category]:
        """Create default categories for user"""
        default_categories = [
            ('Еда и рестораны', 'Тамақ және мейрамханалар', '🍔', 1),
            ('Транспорт', 'Көлік', '🚗', 2),
            ('Покупки и одежда', 'Сатып алулар мен киім', '🛒', 3),
            ('Дом и коммунальные', 'Үй және коммуналдық', '🏠', 4),
            ('Здоровье', 'Денсаулық', '💊', 5),
            ('Развлечения', 'Ойын-сауық', '🎬', 6),
            ('Образование', 'Білім беру', '📚', 7),
            ('Пожертвования', 'Садақа', '🤲', 8),
            ('Прочее', 'Басқа', '💰', 9)
        ]
        
        categories = []
        for name_ru, name_kz, icon, position in default_categories:
            # Check if category already exists
            existing = await session.execute(
                select(Category).where(
                    and_(
                        Category.user_id == user_id,
                        Category.name_ru == name_ru,
                        Category.is_default == True
                    )
                ).limit(1)
            )
            existing_category = existing.scalar_one_or_none()
            
            if not existing_category:
                category = Category(
                    id=str(uuid4()),
                    user_id=user_id,
                    name_ru=name_ru,
                    name_kz=name_kz,
                    icon=icon,
                    is_default=True,
                    order_position=position
                )
                session.add(category)
                categories.append(category)
            else:
                categories.append(existing_category)
        
        await session.flush()
        return categories