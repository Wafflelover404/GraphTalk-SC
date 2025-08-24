import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    cursor.execute('ALTER TABLE users ADD COLUMN last_login TEXT;')
    print('last_login column added.')
except sqlite3.OperationalError as e:
    if 'duplicate column name' in str(e) or 'already exists' in str(e):
        print('last_login column already exists.')
    else:
        print('Error:', e)
finally:
    conn.commit()
    conn.close()

# Use this file if u used depreceated userdb.py without last_login column (UPD: 24 AUG 2025s)