#!/usr/bin/env python3
"""
Temporary fix - drop and recreate meta_data column
"""
import asyncio
import sys
sys.path.append('.')

import aiomysql
from src.core.config import settings

async def fix_column():
    """Fix meta_data column"""
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
            # Check current columns
            await cursor.execute("SHOW COLUMNS FROM transactions")
            columns = await cursor.fetchall()
            
            has_metadata = False
            has_meta_data = False
            
            for col in columns:
                if col[0] == 'metadata':
                    has_metadata = True
                elif col[0] == 'meta_data':
                    has_meta_data = True
                    
            print(f"Has 'metadata': {has_metadata}")
            print(f"Has 'meta_data': {has_meta_data}")
            
            # If we have metadata but not meta_data, rename it
            if has_metadata and not has_meta_data:
                print("Renaming metadata to meta_data...")
                await cursor.execute("""
                    ALTER TABLE transactions 
                    CHANGE COLUMN metadata meta_data JSON 
                    COMMENT 'Дополнительная информация'
                """)
                await conn.commit()
                print("✅ Column renamed successfully!")
                
            # If we have both, drop metadata
            elif has_metadata and has_meta_data:
                print("Dropping duplicate metadata column...")
                await cursor.execute("ALTER TABLE transactions DROP COLUMN metadata")
                await conn.commit()
                print("✅ Duplicate column dropped!")
                
            # If we only have meta_data, all good
            elif has_meta_data and not has_metadata:
                print("✅ Column structure is correct!")
                
            # If we have neither, add meta_data
            else:
                print("Adding meta_data column...")
                await cursor.execute("""
                    ALTER TABLE transactions 
                    ADD COLUMN meta_data JSON 
                    COMMENT 'Дополнительная информация' 
                    AFTER ocr_confidence
                """)
                await conn.commit()
                print("✅ Column added successfully!")
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()
            await conn.ensure_closed()

if __name__ == "__main__":
    asyncio.run(fix_column())