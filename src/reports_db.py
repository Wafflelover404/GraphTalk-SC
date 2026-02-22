import sqlite3
from typing import List, Dict, Any, Optional
import datetime


REPORTS_DB_PATH = 'reports.db'

REPORT_TYPE_MANUAL = 'manual'
REPORT_TYPE_AUTO = 'auto'

def init_reports_db():
    conn = sqlite3.connect(REPORTS_DB_PATH)
    with conn:
        # Create table if not exists
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT NOT NULL,
                permitted_files TEXT NOT NULL,
                date TEXT NOT NULL,
                issue TEXT
            )
        ''')
        # Try to add 'type' column if it does not exist
        try:
            conn.execute("ALTER TABLE reports ADD COLUMN type TEXT NOT NULL DEFAULT 'auto'")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' not in str(e):
                raise
    conn.close()

def submit_report(user: str, permitted_files: List[str], issue: str, date: Optional[str] = None, report_type: str = REPORT_TYPE_AUTO):
    if date is None:
        date = datetime.datetime.utcnow().isoformat()
    conn = sqlite3.connect(REPORTS_DB_PATH)
    with conn:
        conn.execute(
            'INSERT INTO reports (user, permitted_files, date, issue, type) VALUES (?, ?, ?, ?, ?)',
            (user, ','.join(permitted_files), date, issue, report_type)
        )
    conn.close()

def get_reports(report_type: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(REPORTS_DB_PATH)
    with conn:
        if report_type:
            cursor = conn.execute('SELECT user, permitted_files, date, issue, type FROM reports WHERE type = ? ORDER BY date DESC', (report_type,))
        else:
            cursor = conn.execute('SELECT user, permitted_files, date, issue, type FROM reports ORDER BY date DESC')
        rows = cursor.fetchall()
    conn.close()
    return [
        {
            'user': row[0],
            'permitted_files': row[1].split(',') if row[1] else [],
            'date': row[2],
            'issue': row[3],
            'type': row[4]
        }
        for row in rows
    ]

def delete_reports(report_type: Optional[str] = None) -> str:
    conn = sqlite3.connect(REPORTS_DB_PATH)
    if report_type:
        conn.execute('DELETE FROM reports WHERE type = ?', (report_type,))
    else:
        conn.execute('DROP TABLE reports')
    conn.commit()
    conn.close()
    return "Succesfully deleted selected reports"
            


init_reports_db()
deletion_status = delete_reports("auto")