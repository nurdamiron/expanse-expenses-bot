#!/usr/bin/env python3
"""
Script to initialize database with schema
"""

import mysql.connector
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USERNAME'),
    'password': os.getenv('DB_PASSWORD')
}

# Schema file path
SCHEMA_FILE = Path(__file__).parent.parent / 'database' / 'schema.sql'


def init_database():
    """Initialize database with schema"""
    print("Connecting to MySQL server...")
    
    try:
        # Connect without database first
        connection = mysql.connector.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        print("Connected successfully!")
        
        # Read schema file
        print(f"Reading schema from {SCHEMA_FILE}...")
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Split by statement delimiter
        statements = []
        current_statement = []
        delimiter = ';'
        
        for line in schema_sql.split('\n'):
            line = line.strip()
            
            # Handle DELIMITER command
            if line.upper().startswith('DELIMITER'):
                new_delimiter = line.split()[1]
                if current_statement:
                    statements.append('\n'.join(current_statement))
                    current_statement = []
                delimiter = new_delimiter
                continue
            
            # Add line to current statement
            if line:
                current_statement.append(line)
            
            # Check if statement ends with delimiter
            if line.endswith(delimiter):
                if delimiter != ';':
                    # Remove the delimiter from the end
                    current_statement[-1] = current_statement[-1][:-len(delimiter)]
                statements.append('\n'.join(current_statement))
                current_statement = []
        
        # Execute statements
        print("Executing schema...")
        success_count = 0
        
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if not statement or statement.upper() == 'DELIMITER':
                continue
            
            try:
                # For multi-statement execution (like triggers)
                if 'CREATE TRIGGER' in statement.upper():
                    # Execute as multi-statement
                    for result in cursor.execute(statement, multi=True):
                        pass
                else:
                    cursor.execute(statement)
                
                success_count += 1
                
                # Show progress for important statements
                if any(keyword in statement.upper() for keyword in ['CREATE DATABASE', 'CREATE TABLE', 'CREATE VIEW', 'CREATE TRIGGER']):
                    # Extract object name
                    if 'CREATE DATABASE' in statement.upper():
                        print(f"✓ Created database")
                    elif 'CREATE TABLE' in statement.upper():
                        table_name = statement.split('CREATE TABLE')[1].split('(')[0].strip()
                        print(f"✓ Created table {table_name}")
                    elif 'CREATE VIEW' in statement.upper():
                        view_name = statement.split('CREATE VIEW')[1].split('AS')[0].strip()
                        print(f"✓ Created view {view_name}")
                    elif 'CREATE TRIGGER' in statement.upper():
                        trigger_name = statement.split('CREATE TRIGGER')[1].split()[0].strip()
                        print(f"✓ Created trigger {trigger_name}")
                
            except mysql.connector.Error as e:
                if 'already exists' in str(e).lower():
                    print(f"⚠️  Skipping (already exists): Statement {i}")
                else:
                    print(f"❌ Error executing statement {i}: {e}")
                    print(f"Statement: {statement[:100]}...")
        
        connection.commit()
        print(f"\n✅ Database initialized successfully! ({success_count} statements executed)")
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return False
    
    except FileNotFoundError:
        print(f"❌ Schema file not found: {SCHEMA_FILE}")
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals():
            connection.close()
    
    return True


def check_database():
    """Check if database and tables exist"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG, database='expanse_bot')
        cursor = connection.cursor()
        
        # Check tables
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]
        
        expected_tables = [
            'users', 'categories', 'transactions', 'exchange_rates',
            'user_limits', 'notifications', 'bot_states', 'search_history',
            'export_history'
        ]
        
        print("\n📊 Database check:")
        for table in expected_tables:
            if table in tables:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
        
        # Check views
        cursor.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
        views = [view[0] for view in cursor.fetchall()]
        
        expected_views = ['daily_spending', 'category_spending']
        
        print("\n📊 Views check:")
        for view in expected_views:
            if view in views:
                print(f"✓ View '{view}' exists")
            else:
                print(f"❌ View '{view}' missing")
        
        cursor.close()
        connection.close()
        
        return len(tables) >= len(expected_tables)
        
    except mysql.connector.Error as e:
        print(f"❌ Cannot check database: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Expanse Bot Database Initialization")
    print("=" * 50)
    
    # Check if database already exists
    if check_database():
        print("\n✅ Database already initialized!")
    else:
        # Initialize database
        if init_database():
            print("\n✅ Setup complete!")
            check_database()
        else:
            print("\n❌ Setup failed!")
            exit(1)