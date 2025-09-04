import aiosqlite
import asyncio
import os
import datetime
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
                allowed_files TEXT,
                last_login TEXT
            )
        ''')
        
        # Create sessions table for session_id based authentication
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_activity TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (username) REFERENCES users (username)
            )
        ''')
        await conn.commit()

# Initialize database on import
try:
    try:
        loop = asyncio.get_running_loop()
        asyncio.create_task(init_db())
    except RuntimeError:
        # No event loop running, run in new loop
        asyncio.run(init_db())
except Exception as e:
    print(f"Warning: Could not initialize user database on import: {e}")

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

# Session management functions using session_id
async def create_session(username: str, session_id: str, expires_hours: int = 24):
    """Create a new user session with session_id"""
    import datetime
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(hours=expires_hours)
    
    async with aiosqlite.connect(DB_PATH) as conn:
        # Allow multiple active sessions per user (do not deactivate previous sessions)
        await conn.execute('''
            INSERT INTO user_sessions (session_id, username, created_at, last_activity, expires_at, is_active)
            VALUES (?, ?, ?, ?, ?, TRUE)
        ''', (session_id, username, now.isoformat(), now.isoformat(), expires_at.isoformat()))
        await conn.commit()

# Disrupt all sessions for a user (logout everywhere)
async def disrupt_sessions_for_user(username: str):
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'DELETE FROM user_sessions WHERE username = ?',
            (username,)
        )
        await conn.commit()
        return cursor.rowcount

async def get_user_by_session_id(session_id: str):
    """Get user by session_id, checking expiration and activity"""
    import datetime
    now = datetime.datetime.utcnow()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('''
            SELECT u.*, s.created_at, s.last_activity, s.expires_at
            FROM users u 
            JOIN user_sessions s ON u.username = s.username 
            WHERE s.session_id = ? AND s.is_active = TRUE AND s.expires_at > ?
        ''', (session_id, now.isoformat())) as cursor:
            result = await cursor.fetchone()
            
            if result:
                # Update last activity
                await conn.execute(
                    'UPDATE user_sessions SET last_activity = ? WHERE session_id = ?',
                    (now.isoformat(), session_id)
                )
                await conn.commit()
                return result
            return None

async def logout_session_by_id(session_id: str):
    """Deactivate a session by session_id (logout)"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'DELETE FROM user_sessions WHERE session_id = ?',  # Delete instead of deactivate for cleaner DB
            (session_id,)
        )
        await conn.commit()
        return cursor.rowcount > 0

async def delete_user(username: str) -> bool:
    """Delete a user and all their sessions from the database by username."""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Delete user sessions first
        await conn.execute('DELETE FROM user_sessions WHERE username = ?', (username,))
        # Delete user
        cursor = await conn.execute('DELETE FROM users WHERE username = ?', (username,))
        await conn.commit()
        return cursor.rowcount > 0

# Keep backward compatibility functions
async def update_username(old_username: str, new_username: str) -> bool:
    """Update a user's username in the database."""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Update username in users table
        cursor = await conn.execute(
            'UPDATE users SET username = ? WHERE username = ?',
            (new_username, old_username)
        )
        # Update username in user_sessions table as well
        await conn.execute(
            'UPDATE user_sessions SET username = ? WHERE username = ?',
            (new_username, old_username)
        )
        await conn.commit()
        return cursor.rowcount > 0
    
async def update_password(username: str, new_password: str) -> bool:
    """Update a user's password in the database."""
    new_password_hash = bcrypt.hash(new_password)
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'UPDATE users SET password_hash = ? WHERE username = ?',
            (new_password_hash, username)
        )
        await conn.commit()
        return cursor.rowcount > 0
    
async def update_role(username: str, new_role: str) -> bool:
    """Update a user's role in the database."""
    if new_role not in ('user', 'admin'):
        raise ValueError("Role must be 'user' or 'admin'")
    
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'UPDATE users SET role = ? WHERE username = ?',
            (new_role, username)
        )
        await conn.commit()
        return cursor.rowcount > 0
    
async def update_allowed_files(username: str, allowed_files: Optional[List[str]]) -> bool:
    """Update a user's allowed files in the database."""
    allowed_files_str = ','.join(allowed_files) if allowed_files else ''
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'UPDATE users SET allowed_files = ? WHERE username = ?',
            (allowed_files_str, username)
        )
        await conn.commit()
        return cursor.rowcount > 0

async def get_user_by_session(session_token: str):
    """Backward compatibility wrapper"""
    return await get_user_by_session_id(session_token)

async def logout_session(session_token: str):
    """Backward compatibility wrapper"""
    return await logout_session_by_id(session_token)

async def cleanup_expired_sessions():
    """Remove expired sessions from database"""
    import datetime
    now = datetime.datetime.utcnow()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            'DELETE FROM user_sessions WHERE expires_at < ? OR is_active = FALSE',
            (now.isoformat(),)
        )
        await conn.commit()
        return cursor.rowcount

async def get_user_allowed_filenames(username: str) -> Optional[List[str]]:
    """Get list of filenames user is allowed to access"""
    user = await get_user(username)
    if not user:
        return []
    
    # Admin can access all files
    if user[3] == 'admin':  # role
        return None  # None means all files allowed
    
    # Parse allowed files
    allowed_files_str = user[5]  # allowed_files column
    if not allowed_files_str:
        return []
    
    files = [f.strip() for f in allowed_files_str.split(',') if f.strip()]
    if 'all' in files:
        return None  # None means all files allowed
    
    return files

async def check_file_access(username: str, filename: str) -> bool:
    """Check if user has access to a specific file"""
    allowed_files = await get_user_allowed_filenames(username)
    
    # None means all files allowed (admin or 'all' permission)
    if allowed_files is None:
        return True
    
    # Check if filename is in allowed list
    return filename in allowed_files

async def get_active_sessions_count(username: str) -> int:
    """Get count of active sessions for a user"""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Get current time
        now = datetime.datetime.utcnow()
        
        # Count active non-expired sessions
        async with conn.execute('''
            SELECT COUNT(*) as count 
            FROM user_sessions 
            WHERE username = ? AND is_active = TRUE AND expires_at > ?
        ''', (username, now.isoformat())) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0
