#!/usr/bin/env python3
import asyncio
import sys
sys.path.append('.')

import aiomysql
from src.core.config import settings

async def migrate():
    try:
        conn = await aiomysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_username,
            password=settings.db_password,
            db=settings.db_name
        )
        
        async with conn.cursor() as cursor:
            # Check current column name
            await cursor.execute("SHOW COLUMNS FROM transactions LIKE 'meta%'")
            result = await cursor.fetchone()
            
            if result and result[0] == 'metadata':
                print("Renaming metadata to meta_data...")
                await cursor.execute("""
                    ALTER TABLE transactions 
                    CHANGE COLUMN metadata meta_data JSON
                """)
                await conn.commit()
                print("✅ Column renamed successfully!")
            elif result and result[0] == 'meta_data':
                print("✅ Column already has correct name (meta_data)")
            else:
                print("❌ No metadata/meta_data column found!")
                
        conn.close()
        await conn.ensure_closed()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate())