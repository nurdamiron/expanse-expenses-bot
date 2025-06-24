from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from src.core.config import settings

# Create base class for models
Base = declarative_base()

# Create async engine
if settings.is_development():
    # SQLite configuration for better concurrency
    connect_args = {}
    if "sqlite" in settings.get_database_url:
        connect_args = {
            "timeout": 20,
            "check_same_thread": False,
        }
    
    engine = create_async_engine(
        settings.get_database_url,
        echo=True,
        pool_pre_ping=True,
        poolclass=NullPool,
        connect_args=connect_args
    )
else:
    connect_args = {}
    if "sqlite" in settings.get_database_url:
        connect_args = {
            "timeout": 20,
            "check_same_thread": False,
        }
    
    engine = create_async_engine(
        settings.get_database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args
    )

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Initialize database (create tables)"""
    async with engine.begin() as conn:
        # Import all models to register them with Base
        from . import models
        
        # Configure database-specific optimizations
        database_url = settings.get_database_url
        if "sqlite" in database_url:
            # SQLite optimizations
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
            await conn.exec_driver_sql("PRAGMA timeout=20000")
            await conn.exec_driver_sql("PRAGMA busy_timeout=20000")
            await conn.exec_driver_sql("PRAGMA cache_size=10000")
            await conn.exec_driver_sql("PRAGMA temp_store=memory")
            await conn.exec_driver_sql("PRAGMA mmap_size=268435456")  # 256MB
        elif "mysql" in database_url:
            # MySQL optimizations
            await conn.exec_driver_sql("SET SESSION innodb_lock_wait_timeout = 20")
            await conn.exec_driver_sql("SET SESSION lock_wait_timeout = 20")
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose(close=True)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session with retry logic for SQLite locks"""
    import asyncio
    from sqlalchemy.exc import OperationalError
    
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries + 1):
        session = None
        try:
            session = async_session_maker()
            yield session
            await session.commit()
            return  # Success, exit retry loop
        except OperationalError as e:
            if session:
                await session.rollback()
            # Check for retryable database errors
            error_str = str(e).lower()
            is_retryable = any(err in error_str for err in [
                "database is locked",  # SQLite
                "lock wait timeout",   # MySQL
                "deadlock found",      # MySQL
                "connection reset",    # Network issues
                "connection lost"      # Network issues
            ])
            
            if is_retryable and attempt < max_retries:
                if session:
                    await session.close()
                await asyncio.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                continue
            raise
        except Exception:
            if session:
                await session.rollback()
            raise
        finally:
            if session:
                await session.close()