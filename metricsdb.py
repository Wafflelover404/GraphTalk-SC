# metricsdb.py
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

METRICS_DB_PATH = os.getenv("METRICS_DB_PATH", "metrics.db")

def init_metrics_db():
    conn = sqlite3.connect("metrics.db")
    cursor = conn.cursor()

    # user_events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            user_id TEXT,
            role TEXT,
            event_type TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            details JSON,
            success BOOLEAN
        )
    ''')

    # queries
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT,
            question TEXT NOT NULL,
            answer TEXT,
            model_type TEXT,
            humanize BOOLEAN,
            source_document_count INTEGER,
            security_filtered BOOLEAN,
            source_filenames JSON,
            response_time_ms INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT
        )
    ''')

    # file_access_logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            role TEXT,
            filename TEXT NOT NULL,
            file_id TEXT,
            access_type TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT,
            ip_address TEXT,
            query_context TEXT
        )
    ''')

    # system_metrics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_type TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # security_events
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            user_id TEXT,
            ip_address TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            details JSON,
            severity TEXT DEFAULT 'medium'
        )
    ''')

    conn.commit()
    conn.close()


# === Logging Functions ===

def log_event(
    event_type: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    success: bool = True,
    role: Optional[str] = None,
    details: Optional[dict] = None
):
    """Log general user actions."""
    conn = sqlite3.connect(METRICS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_events 
        (event_type, user_id, session_id, ip_address, user_agent, success, role, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event_type,
        user_id,
        session_id,
        ip_address,
        user_agent,
        success,
        role,
        json.dumps(details) if details else None
    ))
    conn.commit()
    conn.close()


def log_query(
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
    model_type: str,
    humanize: bool,
    source_document_count: int,
    security_filtered: bool,
    source_filenames: list,
    ip_address: str,
    role: str = None,
    response_time_ms: Optional[int] = None
):
    """Log detailed RAG query."""
    import uuid
    import logging
    
    # Validate session_id is not None or empty
    if not session_id:
        logger = logging.getLogger(__name__)
        logger.error(f"log_query called with invalid session_id: {session_id}. Generating new UUID.")
        session_id = str(uuid.uuid4())
    
    conn = sqlite3.connect(METRICS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO queries 
        (session_id, user_id, role, question, answer, model_type, humanize,
         source_document_count, security_filtered, source_filenames, response_time_ms, ip_address)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        session_id, user_id, role, question, answer, model_type, humanize,
        source_document_count, security_filtered, json.dumps(source_filenames),
        response_time_ms, ip_address
    ))
    conn.commit()
    conn.close()


def log_file_access(
    user_id: str,
    filename: str,
    access_type: str,
    file_id: Optional[str] = None,
    session_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    role: Optional[str] = None,
    query_context: Optional[str] = None
):
    """Log file access events."""
    conn = sqlite3.connect(METRICS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO file_access_logs
        (user_id, role, filename, file_id, access_type, session_id, ip_address, query_context)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, role, filename, file_id, access_type, session_id, ip_address, query_context))
    conn.commit()
    conn.close()


def log_security_event(
    event_type: str,
    ip_address: str,
    user_id: Optional[str] = None,
    details: Optional[dict] = None,
    severity: str = "medium"
):
    """Log failed or suspicious actions."""
    conn = sqlite3.connect(METRICS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO security_events (event_type, user_id, ip_address, details, severity)
        VALUES (?, ?, ?, ?, ?)
    ''', (event_type, user_id, ip_address, json.dumps(details), severity))
    conn.commit()
    conn.close()


def log_system_metric(metric_type: str, value: float, unit: Optional[str] = None):
    """Log periodic system health (e.g., every 5 mins)."""
    conn = sqlite3.connect(METRICS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO system_metrics (metric_type, value, unit)
        VALUES (?, ?, ?)
    ''', (metric_type, value, unit))
    conn.commit()
    conn.close()
def get_metrics_summary(hours: int = 24) -> dict:
    """Get summary metrics for the dashboard."""
    conn = sqlite3.connect(METRICS_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get total queries
    cursor.execute('''
        SELECT COUNT(*) as total_queries,
               COUNT(DISTINCT user_id) as unique_users
        FROM queries 
        WHERE timestamp >= datetime('now', ? || ' hours')
    ''', (-hours,))
    query_stats = dict(cursor.fetchone())
    
    # Get average response time
    cursor.execute('''
        SELECT AVG(response_time_ms) as avg_response_time
        FROM queries 
        WHERE timestamp >= datetime('now', ? || ' hours')
    ''', (-hours,))
    time_stats = dict(cursor.fetchone())
    
    # Get most active file
    cursor.execute('''
        SELECT source_filenames, COUNT(*) as count
        FROM queries 
        WHERE timestamp >= datetime('now', ? || ' hours')
        GROUP BY source_filenames
        ORDER BY count DESC
        LIMIT 1
    ''', (-hours,))
    file_row = cursor.fetchone()
    
    # Calculate trends (simplified - in a real app, compare with previous period)
    trends = {
        'query_trend': 0,
        'user_trend': 0,
        'response_trend': 0
    }
    
    conn.close()
    
    return {
        'total_queries': query_stats.get('total_queries', 0),
        'unique_users': query_stats.get('unique_users', 0),
        'avg_response_time': round(time_stats.get('avg_response_time', 0), 2) if time_stats.get('avg_response_time') else 0,
        'popular_files': [{
            'filename': file_row[0].split('/')[-1] if file_row and file_row[0] else 'N/A',
            'count': file_row[1] if file_row else 0
        }] if file_row else [],
        'query_trend': trends['query_trend'],
        'user_trend': trends['user_trend'],
        'response_trend': trends['response_trend']
    }

def get_recent_queries(hours: int = 24, limit: int = 10) -> list:
    """Get recent queries for the analytics page."""
    conn = sqlite3.connect(METRICS_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT q.id, q.user_id, q.question, q.answer, q.timestamp, 
               q.response_time_ms, q.model_type, q.source_document_count,
               u.role
        FROM queries q
        LEFT JOIN users u ON q.user_id = u.username
        WHERE q.timestamp >= datetime('now', ? || ' hours')
        ORDER BY q.timestamp DESC
        LIMIT ?
    ''', (-hours, limit))
    
    queries = []
    for row in cursor.fetchall():
        queries.append({
            'id': row['id'],
            'user_id': row['user_id'],
            'role': row['role'],
            'question': row['question'],
            'answer': row['answer'],
            'timestamp': row['timestamp'],
            'response_time_ms': row['response_time_ms'],
            'model_type': row['model_type'],
            'source_document_count': row['source_document_count']
        })
    
    conn.close()
    return queries

