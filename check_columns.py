#!/usr/bin/env python3
"""
Check exact column names in transactions table
"""
import asyncio
import sys
sys.path.append('.')

import aiomysql
from src.core.config import settings

async def check_columns():
    """Check column names in transactions table"""
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
            # Get all columns
            await cursor.execute("SHOW COLUMNS FROM transactions")
            columns = await cursor.fetchall()
            
            print("Columns in transactions table:")
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")
                
            # Check specifically for meta columns
            await cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = %s 
                AND TABLE_NAME = 'transactions' 
                AND COLUMN_NAME LIKE 'meta%'
            """, (settings.db_name,))
            
            meta_cols = await cursor.fetchall()
            print("\nMeta columns found:")
            for col in meta_cols:
                print(f"  - {col[0]}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()
            await conn.ensure_closed()

if __name__ == "__main__":
    asyncio.run(check_columns())