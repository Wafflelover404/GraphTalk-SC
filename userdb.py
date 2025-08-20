import sqlite3
import os
from typing import List, Optional
from passlib.hash import bcrypt

DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'admin')),
            access_token TEXT,
            allowed_files TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def create_user(username: str, password: str, role: str, allowed_files: Optional[List[str]] = None):
    password_hash = bcrypt.hash(password)
    allowed_files_str = ','.join(allowed_files) if allowed_files else ''
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO users (username, password_hash, role, allowed_files) VALUES (?, ?, ?, ?)',
              (username, password_hash, role, allowed_files_str))
    conn.commit()
    conn.close()

def get_user(username: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    return user

def update_access_token(username: str, token: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE users SET access_token = ? WHERE username = ?', (token, username))
    conn.commit()
    conn.close()

def verify_user(username: str, password: str):
    user = get_user(username)
    if user and bcrypt.verify(password, user[2]):
        return True
    return False

def get_allowed_files(username: str):
    user = get_user(username)
    if user:
        files = user[5].split(',') if user[5] else []
        if 'all' in files or user[3] == 'admin':
            return None  # None means all files allowed
        return files
    return []

def get_user_by_token(token: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE access_token = ?', (token,))
    user = c.fetchone()
    conn.close()
    return user
