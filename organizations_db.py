import sqlite3
import os
import asyncio
from datetime import datetime

ORG_DB_PATH = os.path.join(os.path.dirname(__file__), "organizations.db")

def get_org_db_connection():
    conn = sqlite3.connect(ORG_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_org_db():
    conn = get_org_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS organizations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        slug TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS organization_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        organization_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL DEFAULT 'member',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(organization_id, user_id)
    )''')
    conn.commit()
    conn.close()

def create_organization(name: str, admin_user_id: int):
    conn = get_org_db_connection()
    cursor = conn.cursor()
    slug = name.lower().replace(" ", "-").replace("_", "-")[:50]
    try:
        print(f"[DEBUG] Creating org: name={name}, slug={slug}, admin_user_id={admin_user_id}")
        cursor.execute('INSERT INTO organizations (name, slug) VALUES (?, ?)', (name, slug))
        org_id = cursor.lastrowid
        print(f"[DEBUG] Org created with id: {org_id}")
        cursor.execute('INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, ?)',
                      (org_id, admin_user_id, 'admin'))
        conn.commit()
        conn.close()
        return {"id": org_id, "name": name, "slug": slug}
    except sqlite3.IntegrityError as e:
        print(f"[DEBUG] IntegrityError: {e}")
        conn.close()
        return None

def get_organization_by_id(org_id: int):
    conn = get_org_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM organizations WHERE id = ?', (org_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_organizations(user_id: int):
    conn = get_org_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT o.*, om.role, om.joined_at
                     FROM organizations o
                     JOIN organization_members om ON o.id = om.organization_id
                     WHERE om.user_id = ?
                     ORDER BY om.joined_at DESC''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_user_to_organization(org_id: int, user_id: int, role: str = 'member'):
    conn = get_org_db_connection()
    try:
        conn.execute('INSERT INTO organization_members (organization_id, user_id, role) VALUES (?, ?, ?)',
                    (org_id, user_id, role))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

init_org_db()
