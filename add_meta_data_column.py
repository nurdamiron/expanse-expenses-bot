#!/usr/bin/env python3
"""
Add meta_data column to transactions table
"""
import asyncio
import sys
sys.path.append('.')

import aiomysql
from src.core.config import settings

async def add_column():
    """Add meta_data column if it doesn't exist"""
    conn = None
    try:
        conn = await aiomysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_username,
            password=settings.db_password,
            db=settings.db_name
        )
        
        async with conn.cursor() as cursor:
            # Check if column exists
            await cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'transactions' 
                AND COLUMN_NAME = 'meta_data'
            """, (settings.db_name,))
            
            result = await cursor.fetchone()
            
            if not result:
                print("Adding meta_data column...")
                await cursor.execute("""
                    ALTER TABLE transactions 
                    ADD COLUMN meta_data JSON 
                    COMMENT 'Дополнительная информация' 
                    AFTER ocr_confidence
                """)
                await conn.commit()
                print("✅ Column added successfully!")
            else:
                print("✅ Column meta_data already exists")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()
            await conn.ensure_closed()

if __name__ == "__main__":
    asyncio.run(add_column())