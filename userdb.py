import aiosqlite
import asyncio
import os
import datetime
from typing import List, Optional
import bcrypt
import logging

logger = logging.getLogger(__name__)


def _truncate_password_for_bcrypt(password: str) -> bytes:
    """Ensure password does not exceed 72 bytes (bcrypt limit).

    Returns a bytes object containing at most 72 bytes of the UTF-8
    encoding of the password. Any partial trailing UTF-8 sequence is
    dropped to ensure valid encoding when decoding is needed.
    """
    if password is None:
        return b''
    try:
        pw_bytes = password.encode('utf-8')
    except Exception:
        pw_bytes = str(password).encode('utf-8', errors='ignore')
    original_len = len(pw_bytes)
    if original_len <= 72:
        return pw_bytes
    truncated = pw_bytes[:72]
    logger.warning('Password too long for bcrypt; truncated from %d to 72 bytes', original_len)
    return truncated

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
                last_login TEXT,
                organization_id TEXT
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
                organization_id TEXT,
                FOREIGN KEY (username) REFERENCES users (username)
            )
        ''')

        # Backfill/upgrade: ensure organization_id column exists in existing DBs
        try:
            async with conn.execute("PRAGMA table_info(user_sessions)") as cursor:
                cols = await cursor.fetchall()
                col_names = {c[1] for c in cols}
            if "organization_id" not in col_names:
                await conn.execute("ALTER TABLE user_sessions ADD COLUMN organization_id TEXT")
        except Exception:
            # If this fails (e.g., older SQLite), fallback is to drop users.db manually.
            pass
        
        # Backfill/upgrade: ensure organization_id column exists in users table
        try:
            async with conn.execute("PRAGMA table_info(users)") as cursor:
                cols = await cursor.fetchall()
                col_names = {c[1] for c in cols}
            if "organization_id" not in col_names:
                await conn.execute("ALTER TABLE users ADD COLUMN organization_id TEXT")
        except Exception:
            pass

        # Create invites table for one-time use invite codes
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                email TEXT,
                role TEXT NOT NULL CHECK(role IN ('user', 'admin')),
                allowed_files TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                used_at TEXT,
                used_by TEXT,
                message TEXT,
                organization_id TEXT
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

async def create_user(username: str, password: str, role: str, allowed_files: Optional[List[str]] = None, organization_id: Optional[str] = None):
    safe_password = _truncate_password_for_bcrypt(password)
    password_hash = bcrypt.hashpw(safe_password, bcrypt.gensalt()).decode('utf-8')
    # Ensure allowed_files is a list and not None
    if allowed_files is None:
        allowed_files = ['all']  # Default to 'all' for new users
    # Convert list to comma-separated string
    allowed_files_str = ','.join(allowed_files)
    
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute('''
            INSERT INTO users (username, password_hash, role, allowed_files, last_login, organization_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, password_hash, role, allowed_files_str, None, organization_id))
        await conn.commit()
        return cursor.lastrowid

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
    if user:
        safe_password = _truncate_password_for_bcrypt(password)
        try:
            stored_hash = user[2]
            if isinstance(stored_hash, str):
                stored_hash = stored_hash.encode('utf-8')
            verified = bcrypt.checkpw(safe_password, stored_hash)
        except Exception:
            return False
        if verified:
            # Update last_login timestamp
            import datetime
            async with aiosqlite.connect(DB_PATH) as conn:
                await conn.execute('UPDATE users SET last_login = ? WHERE username = ?',
                                  (datetime.datetime.utcnow().isoformat(), username))
                await conn.commit()
            return True
    return False
async def list_users(organization_id: Optional[str] = None):
    """
    Returns a list of users with username, role, last_login, allowed_files, and organization_id.
    If organization_id is provided, returns only users in that organization.
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        if organization_id:
            async with conn.execute(
                'SELECT username, role, last_login, allowed_files, organization_id FROM users WHERE organization_id = ?',
                (organization_id,),
            ) as cursor:
                users = await cursor.fetchall()
        else:
            async with conn.execute('SELECT username, role, last_login, allowed_files, organization_id FROM users') as cursor:
                users = await cursor.fetchall()
        return [
            {
                'username': u[0],
                'role': u[1],
                'last_login': u[2],
                'allowed_files': (u[3].split(',') if u[3] else []),
                'organization_id': u[4]
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
async def create_session(username: str, session_id: str, expires_hours: int = 24, organization_id: Optional[str] = None):
    """Create a new user session with session_id"""
    import datetime
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(hours=expires_hours)
    
    async with aiosqlite.connect(DB_PATH) as conn:
        # Allow multiple active sessions per user (do not deactivate previous sessions)
        await conn.execute('''
            INSERT INTO user_sessions (session_id, username, created_at, last_activity, expires_at, is_active, organization_id)
            VALUES (?, ?, ?, ?, ?, TRUE, ?)
        ''', (session_id, username, now.isoformat(), now.isoformat(), expires_at.isoformat(), organization_id))
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
            SELECT u.*, s.created_at, s.last_activity, s.expires_at, s.organization_id
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
    safe_password = _truncate_password_for_bcrypt(new_password)
    new_password_hash = bcrypt.hashpw(safe_password, bcrypt.gensalt()).decode('utf-8')
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
    allowed_files_str = user[5] if len(user) > 5 else ''  # allowed_files column with safe access
    if not allowed_files_str or allowed_files_str.strip() == '':
        return []
    
    files = [f.strip() for f in allowed_files_str.split(',') if f.strip()]
    if 'all' in files:
        return None  # None means all files allowed
    
    return files

async def check_file_access(username: str, filename: str) -> bool:
    """Check if user has access to a specific file"""
    allowed_files = await get_user_allowed_filenames(username)
    if allowed_files is None:  # Admin or has 'all' access
        return True
    if not allowed_files:  # No access to any files
        return False
    # Check if filename is in allowed_files (case-insensitive)
    import os
    filename_lower = os.path.basename(filename).lower()
    return any(f.lower() == filename_lower for f in allowed_files)

async def get_active_sessions_count(username: str) -> int:
    """Get count of active sessions for a user"""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Get current time
        import datetime
        now = datetime.datetime.utcnow()
        
        # Count active non-expired sessions
        async with conn.execute('''
            SELECT COUNT(*) as count 
            FROM user_sessions 
            WHERE username = ? AND is_active = TRUE AND expires_at > ?
        ''', (username, now.isoformat())) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

# Invite management functions
async def create_invite(token: str, email: str = None, role: str = "user", allowed_files: List[str] = None, 
                      expires_in_days: int = 7, created_by: str = "admin", message: str = None, 
                      organization_id: str = None):
    """Create a new invite token"""
    import datetime
    now = datetime.datetime.utcnow()
    expires_at = now + datetime.timedelta(days=expires_in_days)
    
    allowed_files_str = ','.join(allowed_files) if allowed_files else ""
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            INSERT INTO invites (token, email, role, allowed_files, expires_at, created_at, created_by, message, organization_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (token, email, role, allowed_files_str, expires_at.isoformat(), now.isoformat(), created_by, message, organization_id))
        await conn.commit()

async def get_invite_info(token: str):
    """Get invite information by token"""
    import datetime
    now = datetime.datetime.utcnow()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('SELECT * FROM invites WHERE token = ?', (token,)) as cursor:
            invite = await cursor.fetchone()
            
        if not invite:
            return None
            
        # Parse the invite data
        invite_data = {
            'id': invite[0],
            'token': invite[1],
            'email': invite[2],
            'role': invite[3],
            'allowed_files': invite[4].split(',') if invite[4] else [],
            'expires_at': invite[5],
            'created_at': invite[6],
            'created_by': invite[7],
            'is_used': bool(invite[8]),
            'used_at': invite[9],
            'used_by': invite[10],
            'message': invite[11],
            'organization_id': invite[12]
        }
        
        # Check if invite is expired
        expires_at = datetime.datetime.fromisoformat(invite_data['expires_at'])
        if expires_at < now:
            invite_data['valid'] = False
            invite_data['reason'] = 'expired'
        elif invite_data['is_used']:
            invite_data['valid'] = False
            invite_data['reason'] = 'used'
        else:
            invite_data['valid'] = True
            
        return invite_data

async def mark_invite_used(token: str, used_by: str):
    """Mark an invite as used"""
    import datetime
    now = datetime.datetime.utcnow()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute('''
            UPDATE invites 
            SET is_used = TRUE, used_at = ?, used_by = ? 
            WHERE token = ? AND is_used = FALSE
        ''', (now.isoformat(), used_by, token))
        await conn.commit()
        return cursor.rowcount > 0

async def list_invites(organization_id: str = None):
    """List all invites, optionally filtered by organization"""
    async with aiosqlite.connect(DB_PATH) as conn:
        if organization_id:
            async with conn.execute('SELECT * FROM invites WHERE organization_id = ? ORDER BY created_at DESC', (organization_id,)) as cursor:
                invites = await cursor.fetchall()
        else:
            async with conn.execute('SELECT * FROM invites ORDER BY created_at DESC') as cursor:
                invites = await cursor.fetchall()
        
        return [
            {
                'id': invite[0],
                'token': invite[1],
                'email': invite[2],
                'role': invite[3],
                'allowed_files': invite[4].split(',') if invite[4] else [],
                'expires_at': invite[5],
                'created_at': invite[6],
                'created_by': invite[7],
                'is_used': bool(invite[8]),
                'used_at': invite[9],
                'used_by': invite[10],
                'message': invite[11],
                'organization_id': invite[12]
            }
            for invite in invites
        ]

async def revoke_invite(token: str):
    """Delete an invite token"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute('DELETE FROM invites WHERE token = ?', (token,))
        await conn.commit()
        return cursor.rowcount > 0
