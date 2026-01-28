import aiosqlite
import os
import uuid
import datetime
from typing import Optional, List, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "messages.db")

async def init_messages_db():
    """Initialize the messages database"""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS organization_messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                organization_id TEXT NOT NULL,
                sender_type TEXT NOT NULL CHECK(sender_type IN ('user', 'admin')),
                sender_name TEXT NOT NULL,
                sender_email TEXT,
                message TEXT NOT NULL,
                message_type TEXT NOT NULL CHECK(message_type IN ('inquiry', 'response', 'approval_request', 'approval_status')),
                status TEXT NOT NULL DEFAULT 'unread' CHECK(status IN ('unread', 'read')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations (id),
                FOREIGN KEY (thread_id) REFERENCES message_threads (id)
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS message_threads (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_message_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations (id)
            )
        ''')
        
        await conn.commit()

async def create_message_thread(
    organization_id: str,
    subject: str,
    sender_name: str,
    sender_email: str,
    message: str,
    message_type: str = "inquiry"
) -> str:
    """Create a new message thread"""
    thread_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        # Create thread
        await conn.execute('''
            INSERT INTO message_threads (
                id, organization_id, subject, status, created_at, updated_at, last_message_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (thread_id, organization_id, subject, 'open', now, now, now))
        
        # Create initial message
        await conn.execute('''
            INSERT INTO organization_messages (
                id, thread_id, organization_id, sender_type, sender_name, sender_email, message, message_type, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, thread_id, organization_id, 'user', sender_name, sender_email, message, message_type, 'unread', now, now))
        
        await conn.commit()
    
    return thread_id

async def add_message_to_thread(
    thread_id: str,
    sender_type: str,
    sender_name: str,
    sender_email: Optional[str],
    message: str,
    message_type: str = "response"
) -> str:
    """Add a message to an existing thread"""
    message_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        # Get organization_id from thread
        cursor = await conn.execute('SELECT organization_id FROM message_threads WHERE id = ?', (thread_id,))
        thread = await cursor.fetchone()
        if not thread:
            raise ValueError("Thread not found")
        
        organization_id = thread[0]
        
        # Add message
        await conn.execute('''
            INSERT INTO organization_messages (
                id, thread_id, organization_id, sender_type, sender_name, sender_email, message, message_type, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (message_id, thread_id, organization_id, sender_type, sender_name, sender_email, message, message_type, 'unread', now, now))
        
        # Update thread timestamp
        await conn.execute('''
            UPDATE message_threads SET updated_at = ?, last_message_at = ? WHERE id = ?
        ''', (now, now, thread_id))
        
        await conn.commit()
    
    return message_id

async def get_threads_for_organization(organization_id: str) -> List[Tuple]:
    """Get all message threads for an organization"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute('''
            SELECT * FROM message_threads 
            WHERE organization_id = ? 
            ORDER BY last_message_at DESC
        ''', (organization_id,))
        return await cursor.fetchall()

async def get_all_threads() -> List[Tuple]:
    """Get all message threads (for admin)"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute('''
            SELECT mt.*, o.name as organization_name, o.slug as organization_slug
            FROM message_threads mt
            JOIN organizations o ON mt.organization_id = o.id
            ORDER BY mt.last_message_at DESC
        ''')
        return await cursor.fetchall()

async def get_messages_for_thread(thread_id: str) -> List[Tuple]:
    """Get all messages for a thread"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute('''
            SELECT * FROM organization_messages 
            WHERE thread_id = ? 
            ORDER BY created_at ASC
        ''', (thread_id,))
        return await cursor.fetchall()

async def mark_message_as_read(message_id: str) -> bool:
    """Mark a message as read"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute('''
            UPDATE organization_messages 
            SET status = 'read', updated_at = ? 
            WHERE id = ?
        ''', (datetime.datetime.utcnow().isoformat(), message_id))
        await conn.commit()
        return cursor.rowcount > 0

async def get_unread_message_count() -> int:
    """Get count of unread messages"""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute('''
            SELECT COUNT(*) FROM organization_messages WHERE status = 'unread'
        ''')
        result = await cursor.fetchone()
        return result[0] if result else 0

# Initialize database on import
try:
    import asyncio
    asyncio.run(init_messages_db())
except Exception as e:
    print(f"Warning: Could not initialize messages database on import: {e}")
