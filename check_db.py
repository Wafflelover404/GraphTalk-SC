import asyncio
import aiosqlite

async def check_db():
    try:
        conn = await aiosqlite.connect('organizations.db')
        cursor = await conn.execute('PRAGMA table_info(organizations)')
        columns = await cursor.fetchall()
        print("Organizations table columns:")
        for col in columns:
            print(col)
        
        # Check if status column exists
        cursor = await conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='organizations'")
        table_info = await cursor.fetchone()
        if table_info:
            print(f"\nTable SQL: {table_info[0]}")
        
        # Try to select data to see structure
        cursor = await conn.execute("SELECT * FROM organizations LIMIT 1")
        row = await cursor.fetchone()
        if row:
            print(f"\nSample row: {row}")
        
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(check_db())
