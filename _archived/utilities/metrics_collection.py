"""
Module for collecting and tracking API usage metrics
"""
import sqlite3
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

METRICS_DB_PATH = os.getenv("METRICS_DB_PATH", "metrics.db")

def init_metrics_tables():
    """Initialize metrics database tables"""
    conn = sqlite3.connect(METRICS_DB_PATH)
    cursor = conn.cursor()

    # Queries tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS query_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT NOT NULL,
            session_id TEXT,
            query_text TEXT,
            response_time_ms INTEGER,
            model_type TEXT,
            source_docs_count INTEGER,
            was_successful BOOLEAN
        )
    ''')

    # File operations tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS file_operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            filename TEXT,
            file_size INTEGER,
            mime_type TEXT,
            processing_time_ms INTEGER,
            was_successful BOOLEAN
        )
    ''')

    # User activity tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            endpoint TEXT,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT
        )
    ''')

    # API response time tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS api_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            endpoint TEXT NOT NULL,
            response_time_ms INTEGER,
            success BOOLEAN,
            error_type TEXT
        )
    ''')

    # Trending searches
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trending_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            query_text TEXT NOT NULL UNIQUE,
            frequency INTEGER DEFAULT 1,
            last_user_id TEXT
        )
    ''')

    conn.commit()
    conn.close()

@contextmanager
def get_db():
    """Context manager for database connections"""
    conn = sqlite3.connect(METRICS_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

def log_query_metrics(
    user_id: str,
    session_id: str,
    query_text: str,
    response_time_ms: int,
    model_type: str,
    source_docs_count: int,
    was_successful: bool
):
    """Log metrics for a query operation"""
    with get_db() as conn:
        cursor = conn.cursor()
        # Log the query metrics
        cursor.execute('''
            INSERT INTO query_metrics 
            (user_id, session_id, query_text, response_time_ms, model_type, source_docs_count, was_successful)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, session_id, query_text, response_time_ms, model_type, source_docs_count, was_successful))
        
        # Update trending searches - first try to update existing
        cursor.execute('''
            UPDATE trending_searches 
            SET frequency = frequency + 1,
                last_user_id = ?,
                timestamp = CURRENT_TIMESTAMP
            WHERE query_text = ?
        ''', (user_id, query_text))
        
        # If no rows were updated, insert new record
        if cursor.rowcount == 0:
            cursor.execute('''
                INSERT INTO trending_searches (query_text, last_user_id, frequency)
                VALUES (?, ?, 1)
            ''', (query_text, user_id))
        
        conn.commit()

def log_file_operation(
    user_id: str,
    operation_type: str,
    filename: str,
    file_size: Optional[int] = None,
    mime_type: Optional[str] = None,
    processing_time_ms: Optional[int] = None,
    was_successful: bool = True
):
    """Log metrics for file operations"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO file_operations 
            (user_id, operation_type, filename, file_size, mime_type, processing_time_ms, was_successful)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, operation_type, filename, file_size, mime_type, processing_time_ms, was_successful))
        conn.commit()

def log_user_activity(
    user_id: str,
    action_type: str,
    endpoint: str,
    details: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """Log user activity"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_activity 
            (user_id, action_type, endpoint, details, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, action_type, endpoint, details, ip_address, user_agent))
        conn.commit()

def log_api_performance(
    endpoint: str,
    response_time_ms: int,
    success: bool,
    error_type: Optional[str] = None
):
    """Log API endpoint performance"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO api_performance 
            (endpoint, response_time_ms, success, error_type)
            VALUES (?, ?, ?, ?)
        ''', (endpoint, response_time_ms, success, error_type))
        conn.commit()

def get_trending_searches(limit: int = 10, hours: int = 24) -> List[Dict[str, Any]]:
    """Get trending searches from the last X hours"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT query_text, COUNT(*) as frequency
            FROM query_metrics
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY query_text
            ORDER BY frequency DESC
            LIMIT ?
        ''', (-hours, limit))
        return [{"query": row[0], "frequency": row[1]} for row in cursor.fetchall()]

def get_user_recent_activity(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent activity for a specific user"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT action_type, endpoint, details, timestamp
            FROM user_activity
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        return [{
            "action": row[0],
            "endpoint": row[1],
            "details": row[2],
            "timestamp": row[3]
        } for row in cursor.fetchall()]

def get_api_performance_stats(hours: int = 24) -> Dict[str, Any]:
    """Get API performance statistics"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                endpoint,
                AVG(response_time_ms) as avg_response_time,
                COUNT(*) as total_requests,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_requests
            FROM api_performance
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY endpoint
        ''', (-hours,))
        return [{
            "endpoint": row[0],
            "avg_response_time": row[1],
            "total_requests": row[2],
            "success_rate": (row[3] / row[2]) * 100 if row[2] > 0 else 0
        } for row in cursor.fetchall()]

def get_user_public_data(username: str, hours: int = 24) -> Dict[str, Any]:
    """Get public metrics and user-specific data"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get user stats
        cursor.execute('''
            SELECT 
                COUNT(*) as total_queries,
                SUM(CASE WHEN was_successful = 1 THEN 1 ELSE 0 END) as successful_queries,
                AVG(response_time_ms) as avg_response_time,
                MAX(timestamp) as last_activity
            FROM query_metrics
            WHERE user_id = ? AND timestamp >= datetime('now', ? || ' hours')
        ''', (username, -hours))
        user_query_stats = cursor.fetchone()
        
        # Get user's frequent searches
        cursor.execute('''
            SELECT query_text, COUNT(*) as frequency
            FROM query_metrics
            WHERE user_id = ? AND timestamp >= datetime('now', ? || ' hours')
            GROUP BY query_text
            ORDER BY frequency DESC
            LIMIT 5
        ''', (username, -hours))
        frequent_searches = [row[0] for row in cursor.fetchall()]
        
        # Get user's file stats
        cursor.execute('''
            SELECT 
                COUNT(*) as files_uploaded,
                SUM(file_size) as total_size
            FROM file_operations
            WHERE user_id = ? AND timestamp >= datetime('now', ? || ' hours')
        ''', (username, -hours))
        file_stats = cursor.fetchone()
        
        # Get recent activity
        cursor.execute('''
            SELECT action_type, endpoint, details, timestamp, ip_address, user_agent
            FROM user_activity
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 10
        ''', (username,))
        recent_activity = [{
            "action": row[0],
            "endpoint": row[1],
            "details": row[2],
            "timestamp": row[3],
            "ip_address": row[4],
            "user_agent": row[5]
        } for row in cursor.fetchall()]
        
        # Get public stats
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT user_id) as active_users,
                COUNT(*) as total_queries,
                AVG(response_time_ms) as avg_response_time
            FROM query_metrics
            WHERE timestamp >= datetime('now', ? || ' hours')
        ''', (-hours,))
        public_stats = cursor.fetchone()
        
        # Get popular files (public)
        cursor.execute('''
            SELECT filename, COUNT(*) as access_count
            FROM file_operations
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY filename
            ORDER BY access_count DESC
            LIMIT 5
        ''', (-hours,))
        popular_files = [{"filename": row[0], "access_count": row[1]} for row in cursor.fetchall()]
        
        # Get system health
        cursor.execute('''
            SELECT 
                endpoint,
                AVG(response_time_ms) as avg_time,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
            FROM api_performance
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY endpoint
        ''', (-hours,))
        system_health = {row[0]: {
            "avg_response_time": row[1],
            "success_rate": row[2]
        } for row in cursor.fetchall()}

        # Get allowed files for user
        from userdb import get_allowed_files
        import asyncio
        allowed_files = asyncio.run(get_allowed_files(username)) or []
        
        return {
            "user_stats": {
                "total_queries": user_query_stats[0],
                "successful_queries": user_query_stats[1],
                "avg_response_time": user_query_stats[2],
                "frequent_searches": frequent_searches,
                "last_activity": user_query_stats[3],
                "files_uploaded": file_stats[0],
                "total_upload_size": file_stats[1] or 0,
                "recent_activity": recent_activity,
                "allowed_files": allowed_files
            },
            "public_stats": {
                "total_users_active": public_stats[0],
                "total_queries_24h": public_stats[1],
                "global_avg_response_time": public_stats[2],
                "trending_searches": get_trending_searches(limit=5, hours=hours),
                "popular_files": popular_files,
                "system_health": system_health
            }
        }

def get_admin_private_data(hours: int = 24) -> Dict[str, Any]:
    """Get complete private metrics data for admins"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get detailed user statistics
        cursor.execute('''
            SELECT 
                user_id,
                COUNT(*) as total_actions,
                COUNT(DISTINCT endpoint) as unique_endpoints,
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen,
                GROUP_CONCAT(DISTINCT ip_address) as ip_addresses
            FROM user_activity
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY user_id
        ''', (-hours,))
        users_detailed = {}
        for row in cursor.fetchall():
            users_detailed[row[0]] = {
                "total_actions": row[1],
                "unique_endpoints": row[2],
                "first_seen": row[3],
                "last_seen": row[4],
                "ip_addresses": row[5].split(',') if row[5] else []
            }
        
        # Get IP activity
        cursor.execute('''
            SELECT 
                ip_address,
                user_id,
                action_type,
                timestamp
            FROM user_activity
            WHERE ip_address IS NOT NULL 
            AND timestamp >= datetime('now', ? || ' hours')
            ORDER BY timestamp DESC
        ''', (-hours,))
        ip_activity = {}
        for row in cursor.fetchall():
            if row[0] not in ip_activity:
                ip_activity[row[0]] = []
            ip_activity[row[0]].append({
                "user": row[1],
                "action": row[2],
                "timestamp": row[3]
            })
        
        # Get security events
        cursor.execute('''
            SELECT *
            FROM api_performance
            WHERE success = 0 
            AND timestamp >= datetime('now', ? || ' hours')
            ORDER BY timestamp DESC
        ''', (-hours,))
        security_events = [{
            "endpoint": row[1],
            "error_type": row[4],
            "timestamp": row[0]
        } for row in cursor.fetchall()]
        
        # Get user agents
        cursor.execute('''
            SELECT user_agent, COUNT(*) as count
            FROM user_activity
            WHERE user_agent IS NOT NULL 
            AND timestamp >= datetime('now', ? || ' hours')
            GROUP BY user_agent
        ''', (-hours,))
        user_agents = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get error rates by endpoint
        cursor.execute('''
            SELECT 
                endpoint,
                COUNT(*) as total,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
            FROM api_performance
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY endpoint
        ''', (-hours,))
        error_rates = {
            row[0]: (row[2] / row[1] * 100) if row[1] > 0 else 0 
            for row in cursor.fetchall()
        }
        
        return {
            "users_detailed": users_detailed,
            "ip_activity": ip_activity,
            "security_events": security_events,
            "user_agents": user_agents,
            "error_rates": error_rates,
            "file_access_logs": get_file_access_logs(hours),
            "queries_by_model": get_model_distribution(hours),
            "sensitive_operations": get_sensitive_operations(hours)
        }

def get_file_access_logs(hours: int) -> List[Dict[str, Any]]:
    """Get detailed file access logs"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT *
            FROM file_operations
            WHERE timestamp >= datetime('now', ? || ' hours')
            ORDER BY timestamp DESC
        ''', (-hours,))
        return [{
            "user_id": row[2],
            "operation": row[3],
            "filename": row[4],
            "timestamp": row[1]
        } for row in cursor.fetchall()]

def get_model_distribution(hours: int) -> Dict[str, int]:
    """Get distribution of queries by model type"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT model_type, COUNT(*) as count
            FROM query_metrics
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY model_type
        ''', (-hours,))
        return {row[0]: row[1] for row in cursor.fetchall()}

def get_sensitive_operations(hours: int) -> List[Dict[str, Any]]:
    """Get logs of sensitive operations"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT *
            FROM user_activity
            WHERE action_type IN ('login', 'logout', 'file_upload', 'file_delete', 'user_edit')
            AND timestamp >= datetime('now', ? || ' hours')
            ORDER BY timestamp DESC
        ''', (-hours,))
        return [{
            "action": row[3],
            "user_id": row[2],
            "timestamp": row[1],
            "ip_address": row[5],
            "details": row[4]
        } for row in cursor.fetchall()]

def get_complete_metrics_data(hours: int = 24) -> Dict[str, Any]:
    """Get comprehensive metrics data"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Query metrics
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                AVG(response_time_ms) as avg_time,
                SUM(CASE WHEN was_successful = 1 THEN 1 ELSE 0 END) as successful,
                GROUP_CONCAT(model_type) as models
            FROM query_metrics
            WHERE timestamp >= datetime('now', ? || ' hours')
        ''', (-hours,))
        query_row = cursor.fetchone()
        
        # Model distribution
        model_distribution = {}
        if query_row[3]:  # models string
            for model in query_row[3].split(','):
                model_distribution[model] = model_distribution.get(model, 0) + 1
        
        # File metrics
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(file_size) as total_size,
                SUM(CASE WHEN was_successful = 1 THEN 1 ELSE 0 END) as successful,
                GROUP_CONCAT(mime_type) as mime_types
            FROM file_operations
            WHERE timestamp >= datetime('now', ? || ' hours')
        ''', (-hours,))
        file_row = cursor.fetchone()
        
        # Mime type distribution
        mime_distribution = {}
        if file_row[3]:  # mime_types string
            for mime in file_row[3].split(','):
                if mime:
                    mime_distribution[mime] = mime_distribution.get(mime, 0) + 1
        
        # User metrics
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT user_id) as total_users,
                user_id,
                COUNT(*) as action_count
            FROM user_activity
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY user_id
            ORDER BY action_count DESC
            LIMIT 10
        ''', (-hours,))
        user_rows = cursor.fetchall()
        
        # Trending searches
        trending = get_trending_searches(limit=10, hours=hours)
        
        # API performance
        api_stats = get_api_performance_stats(hours=hours)
        
        return {
            "queries": {
                "total_queries": query_row[0],
                "avg_response_time": query_row[1],
                "successful_queries": query_row[2],
                "model_type_distribution": model_distribution
            },
            "files": {
                "total_uploads": file_row[0],
                "total_size_bytes": file_row[1],
                "mime_type_distribution": mime_distribution,
                "successful_uploads": file_row[2]
            },
            "users": {
                "total_users": len(user_rows),
                "active_users_24h": len([r for r in user_rows if r[2] > 0]),
                "queries_per_user": {r[1]: r[2] for r in user_rows},
                "top_users": [{"user_id": r[1], "action_count": r[2]} for r in user_rows]
            },
            "trending_searches": trending,
            "api_performance": api_stats
        }

# Initialize tables when module is imported
init_metrics_tables()
