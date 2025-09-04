from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import sqlite3

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

    user_id = user[0]  # Assuming user tuple structure from userdb
    parsed_since = parse_since(since)

    # Get user's queries
    query = '''
        SELECT id, question, answer, model_type, humanize,
               source_document_count, security_filtered, source_filenames,
               response_time_ms, timestamp
        FROM queries
        WHERE user_id = ? AND timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    '''
    
    cursor.execute(query, (user_id, parsed_since, limit, offset))
    activity = [dict(row) for row in cursor.fetchall()]

    # Get total count
    cursor.execute(
        'SELECT COUNT(*) as count FROM queries WHERE user_id = ? AND timestamp >= ?',
        (user_id, parsed_since)
    )
    total = cursor.fetchone()["count"]

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

    user_id = user[0]
    parsed_since = parse_since(since)

    # Get total queries in period
    cursor.execute(
        'SELECT COUNT(*) as count FROM queries WHERE user_id = ? AND timestamp >= ?',
        (user_id, parsed_since)
    )
    query_count = cursor.fetchone()["count"]

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

@router.get("/files", summary="Get user's file interactions")
async def get_user_file_stats(
    since: str = Query("24h"),
    user=Depends(require_auth)
) -> dict:
    """Get statistics about files the user has interacted with."""
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = user[0]
    parsed_since = parse_since(since)

    # Get files used in RAG responses
    query = '''
        SELECT filename, COUNT(*) as retrieval_count
        FROM file_access_logs
        WHERE user_id = ? AND access_type = 'retrieved_in_rag' 
        AND timestamp >= ?
        GROUP BY filename
        ORDER BY retrieval_count DESC
        LIMIT 10
    '''
    cursor.execute(query, (user_id, parsed_since))
    rag_files = [dict(row) for row in cursor.fetchall()]

    # Get directly viewed files
    query2 = '''
        SELECT filename, COUNT(*) as view_count
        FROM file_access_logs
        WHERE user_id = ? AND access_type = 'view' 
        AND timestamp >= ?
        GROUP BY filename
        ORDER BY view_count DESC
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
