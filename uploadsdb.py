import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'uploads.db')


async def init_uploads_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS uploads (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                logs TEXT,
                sc_addresses TEXT
            )
        ''')
        await conn.commit()


async def add_upload(upload_id, filename, path, timestamp, logs=None, sc_addresses=None):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            'INSERT INTO uploads (id, filename, path, timestamp, logs, sc_addresses) VALUES (?, ?, ?, ?, ?, ?)',
            (upload_id, filename, path, timestamp, logs, sc_addresses)
        )
        await conn.commit()

async def update_upload_logs_and_addresses(upload_id, logs=None, sc_addresses=None):
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            'UPDATE uploads SET logs = ?, sc_addresses = ? WHERE id = ?',
            (logs, sc_addresses, upload_id)
        )
        await conn.commit()


async def list_uploads():
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('SELECT id, filename, path, timestamp, logs, sc_addresses FROM uploads') as cursor:
            return await cursor.fetchall()


async def get_upload_by_id(upload_id):
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('SELECT id, filename, path, timestamp, logs, sc_addresses FROM uploads WHERE id = ?', (upload_id,)) as cursor:
            return await cursor.fetchone()


async def get_upload_by_filename(filename):
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute('SELECT id, filename, path, timestamp, logs, sc_addresses FROM uploads WHERE filename = ?', (filename,)) as cursor:
            return await cursor.fetchone()
