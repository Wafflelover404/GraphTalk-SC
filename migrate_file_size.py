#!/usr/bin/env python3
"""
Migration script to add file_size column to uploads database
"""

import asyncio
import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'uploads.db')

async def migrate_file_size_column():
    """Add file_size column to existing uploads table"""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Check if file_size column already exists
        cursor = await conn.execute("PRAGMA table_info(uploads)")
        columns = [row[1] for row in await cursor.fetchall()]
        
        if 'file_size' not in columns:
            print("Adding file_size column to uploads table...")
            await conn.execute("ALTER TABLE uploads ADD COLUMN file_size INTEGER")
            await conn.commit()
            print("✅ file_size column added successfully")
        else:
            print("✅ file_size column already exists")

if __name__ == "__main__":
    asyncio.run(migrate_file_size_column())
