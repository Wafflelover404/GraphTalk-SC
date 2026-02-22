from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import sqlite3
import json
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/metrics/user", tags=["User Metrics"])

security_scheme = HTTPBearer(auto_error=False)

# ========================
# Security: Any authenticated user
# ========================

async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
):
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")

    from userdb import get_user_by_token
    user = await get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# ========================
# Database Connection Helper
# ========================

def get_db_connection():
    conn = sqlite3.connect("metrics.db")
    conn.row_factory = sqlite3.Row
    return conn

# ========================
# Utility Functions
# ========================

def parse_since(since: str) -> str:
    """Convert '1h', '24h', '7d' or ISO date to SQL datetime string."""
    now = datetime.utcnow()
    if since.endswith("h"):
        hours = int(since[:-1])
        return (now - timedelta(hours=hours)).isoformat()
    elif since.endswith("d"):
        days = int(since[:-1])
        return (now - timedelta(days=days)).isoformat()
    elif since:
        return since  # Assume ISO format
    else:
        return (now - timedelta(hours=24)).isoformat()  # default: last 24h

# ========================
# User Metrics Endpoints
# ========================

@router.get("/activity", summary="Get user's own activity")
async def get_user_activity(
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    since: str = Query("24h"),
    user=Depends(require_auth)
) -> dict:
    """Get the authenticated user's recent activity."""
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = user[1]  # Using username as user_id
    parsed_since = parse_since(since)

    # Get user's queries and file views combined for a complete activity log
    query = '''
        SELECT 'query' as activity_type,
               q.id,
               q.question as content,
               q.answer,
               q.model_type,
               q.source_document_count,
               q.security_filtered,
               q.source_filenames,
               q.response_time_ms,
               q.timestamp,
               NULL as access_type
        FROM queries q
        WHERE q.user_id = ? AND q.timestamp >= ?
        
        UNION ALL
        
        SELECT 'file_access' as activity_type,
               f.id,
               f.filename as content,
               NULL as answer,
               NULL as model_type,
               NULL as source_document_count,
               NULL as security_filtered,
               NULL as source_filenames,
               NULL as response_time_ms,
               f.timestamp,
               f.access_type
        FROM file_access_logs f
        WHERE f.user_id = ? AND f.timestamp >= ?
        
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    '''
    
    cursor.execute(query, (user_id, parsed_since, user_id, parsed_since, limit, offset))
    raw_activity = [dict(row) for row in cursor.fetchall()]
    
    # Process activity items to add more context
    activity = []
    for item in raw_activity:
        processed_item = {
            'id': item['id'],
            'timestamp': item['timestamp'],
            'activity_type': item['activity_type']
        }
        
        if item['activity_type'] == 'query':
            # Process query activity
            processed_item.update({
                'content': item['content'],
                'success': item['source_document_count'] > 0,
                'response_time': item['response_time_ms'],
                'found_docs': item['source_document_count'],
                'source_files': item['source_filenames'].split(',') if item['source_filenames'] else [],
                'answer': item['answer']
            })
        else:
            # Process file access activity
            processed_item.update({
                'filename': item['content'],
                'action_type': item['action']
            })
        
        activity.append(processed_item)

    # Get total count for pagination
    cursor.execute('''
        SELECT 
            (SELECT COUNT(*) FROM queries WHERE user_id = ? AND timestamp >= ?) +
            (SELECT COUNT(*) FROM file_access_logs WHERE user_id = ? AND timestamp >= ?)
        as total_count
    ''', (user_id, parsed_since, user_id, parsed_since))
    total = cursor.fetchone()["total_count"]

    conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "activities": activity
    }

@router.get("/summary", summary="Get user's metrics summary")
async def get_user_metrics_summary(
    since: str = Query("24h"),
    user=Depends(require_auth)
) -> dict:
    """Get summary metrics for the authenticated user."""
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = user[1]  # Using username as user_id
    parsed_since = parse_since(since)

    # Get total queries in period
    query_sql = 'SELECT COUNT(*) as count FROM queries WHERE user_id = ? AND timestamp >= ?'
    logger.info(f"Executing query: {query_sql} with params: user_id={user_id}, since={parsed_since}")
    cursor.execute(query_sql, (user_id, parsed_since))
    result = cursor.fetchone()
    query_count = result["count"] if result else 0
    logger.info(f"Query count result: {query_count}")

    # Get average response time
    cursor.execute(
        'SELECT AVG(response_time_ms) as avg_time FROM queries WHERE user_id = ? AND timestamp >= ?',
        (user_id, parsed_since)
    )
    avg_response_time = cursor.fetchone()["avg_time"] or 0

    # Get most used files in RAG
    cursor.execute('''
        SELECT filename, COUNT(*) as count 
        FROM file_access_logs 
        WHERE user_id = ? AND timestamp >= ? AND access_type = 'retrieved_in_rag'
        GROUP BY filename 
        ORDER BY count DESC 
        LIMIT 5
    ''', (user_id, parsed_since))
    top_files = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "total_queries": query_count,
        "avg_response_time_ms": round(avg_response_time, 2),
        "top_files": top_files,
        "since": since
    }

@router.get("/sessions", summary="Get user's active sessions")
async def get_user_sessions(user=Depends(require_auth)) -> dict:
    """Get count of active sessions for the current user."""
    from userdb import get_active_sessions_count
    session_count = await get_active_sessions_count(user[1])  # Pass username
    
    return {
        "active_sessions": session_count,
        "username": user[1]
    }

@router.get("/files", summary="Get user's file interactions")
async def get_user_file_stats(
    since: str = Query("24h"),
    user=Depends(require_auth)
) -> dict:
    """Get statistics about files the user has interacted with."""
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = user[1]  # Using username as user_id
    parsed_since = parse_since(since)

    # Get files used in RAG responses
    query = '''
        SELECT 
            filename,
            COUNT(*) as retrieval_count,
            MAX(timestamp) as last_accessed
        FROM file_access_logs
        WHERE user_id = ? 
        AND access_type = 'retrieved_in_rag' 
        AND timestamp >= ?
        GROUP BY filename
        ORDER BY retrieval_count DESC, last_accessed DESC
        LIMIT 10
    '''
    cursor.execute(query, (user_id, parsed_since))
    rag_files = [dict(row) for row in cursor.fetchall()]

    # Get directly viewed files
    query2 = '''
        SELECT 
            filename,
            COUNT(*) as view_count,
            MAX(timestamp) as last_accessed
        FROM file_access_logs
        WHERE user_id = ? 
        AND access_type = 'view' 
        AND timestamp >= ?
        GROUP BY filename
        ORDER BY view_count DESC, last_accessed DESC
        LIMIT 10
    '''
    cursor.execute(query2, (user_id, parsed_since))
    view_files = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "since": since,
        "rag_files": rag_files,
        "viewed_files": view_files
    }
