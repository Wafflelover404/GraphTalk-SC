import aiosqlite
import asyncio
import os
from typing import List, Optional
from passlib.hash import bcrypt

DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')

async def init_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'admin')),
                access_token TEXT,
                allowed_files TEXT
                   , last_login TEXT
            )
        ''')
        await conn.commit()

# Initialize database on import
asyncio.create_task(init_db()) if asyncio.get_running_loop() else asyncio.run(init_db())

async def create_user(username: str, password: str, role: str, allowed_files: Optional[List[str]] = None):
    password_hash = bcrypt.hash(password)
    allowed_files_str = ','.join(allowed_files) if allowed_files else ''
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('INSERT INTO users (username, password_hash, role, allowed_files) VALUES (?, ?, ?, ?)',
                          (username, password_hash, role, allowed_files_str))
        await conn.commit()

async def get_user(username: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('SELECT * FROM users WHERE username = ?', (username,)) as cursor:
            user = await cursor.fetchone()
            return user

async def update_access_token(username: str, token: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('UPDATE users SET access_token = ? WHERE username = ?', (token, username))
        await conn.commit()

async def verify_user(username: str, password: str):
    user = await get_user(username)
    if user and bcrypt.verify(password, user[2]):
        # Update last_login timestamp
        import datetime
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute('UPDATE users SET last_login = ? WHERE username = ?',
                              (datetime.datetime.utcnow().isoformat(), username))
            await conn.commit()
        return True
    return False
async def list_users():
    """
    Returns a list of all users with username, role, and last_login.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('SELECT username, role, last_login FROM users') as cursor:
            users = await cursor.fetchall()
            return [
                {
                    'username': u[0],
                    'role': u[1],
                    'last_login': u[2]
                } for u in users
            ]

async def get_allowed_files(username: str):
    user = await get_user(username)
    if user:
        files = user[5].split(',') if user[5] else []
        if 'all' in files or user[3] == 'admin':
            return None  # None means all files allowed
        return files
    return []

async def get_user_by_token(token: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('SELECT * FROM users WHERE access_token = ?', (token,)) as cursor:
            user = await cursor.fetchone()
            return user
