#!/usr/bin/env python3
"""
Script to check and fix database structure
"""
import asyncio
import aiomysql
from src.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_and_fix_database():
    """Check database structure and fix if needed"""
    
    # Connect to database
    conn = await aiomysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_username,
        password=settings.db_password,
        db=settings.db_name
    )
    
    try:
        async with conn.cursor() as cursor:
            # Check if transactions table exists
            await cursor.execute("SHOW TABLES LIKE 'transactions'")
            result = await cursor.fetchone()
            
            if not result:
                logger.error("Transactions table does not exist!")
                return
            
            # Check table structure
            await cursor.execute("DESCRIBE transactions")
            columns = await cursor.fetchall()
            
            column_names = [col[0] for col in columns]
            logger.info(f"Current columns: {column_names}")
            
            # Check if meta_data column exists
            if 'meta_data' not in column_names and 'metadata' in column_names:
                logger.warning("Found 'metadata' column instead of 'meta_data', renaming...")
                await cursor.execute("""
                    ALTER TABLE transactions 
                    CHANGE COLUMN metadata meta_data JSON 
                    COMMENT 'Дополнительная информация'
                """)
                await conn.commit()
                logger.info("Column renamed successfully!")
                
            elif 'meta_data' not in column_names and 'metadata' not in column_names:
                logger.warning("Neither 'meta_data' nor 'metadata' column exists, adding...")
                await cursor.execute("""
                    ALTER TABLE transactions 
                    ADD COLUMN meta_data JSON 
                    COMMENT 'Дополнительная информация' 
                    AFTER ocr_confidence
                """)
                await conn.commit()
                logger.info("Column added successfully!")
                
            else:
                logger.info("Database structure is correct!")
            
            # Show final structure
            await cursor.execute("DESCRIBE transactions")
            columns = await cursor.fetchall()
            logger.info("\nFinal table structure:")
            for col in columns:
                logger.info(f"  {col[0]} - {col[1]}")
                
    finally:
        conn.close()
        await conn.ensure_closed()


if __name__ == "__main__":
    asyncio.run(check_and_fix_database())