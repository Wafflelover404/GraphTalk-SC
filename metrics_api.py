# metrics_api.py
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import sqlite3
import json
import os

router = APIRouter(prefix="/metrics", tags=["Analytics & Metrics"])

security_scheme = HTTPBearer(auto_error=False)

# ========================
# Security: Admin or Master Key
# ========================

async def require_admin_or_master(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
):
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")

    from userdb import get_user_by_token
    user = await get_user_by_token(credentials.credentials)
    if user and user[3] == "admin":
        return user

    # Check master key
    SECRETS_PATH = os.path.expanduser("~/secrets.toml")
    if os.path.exists(SECRETS_PATH):
        try:
            import toml
            import bcrypt
            with open(SECRETS_PATH, "r") as f:
                secrets_data = toml.load(f)
            stored_hash = secrets_data.get("access_token_hash")
            if stored_hash:
                if bcrypt.checkpw(credentials.credentials.encode("utf-8"), stored_hash.encode("utf-8")):
                    return ("system", "master", None, "admin")
        except Exception:
            pass

    raise HTTPException(status_code=403, detail="Admin or master key required.")


# ========================
# Database Connection Helper
# ========================

def get_db_connection():
    conn = sqlite3.connect("metrics.db")
    conn.row_factory = sqlite3.Row  # Access columns via .column_name
    return conn


# ========================
# Utility: Parse ISO or relative time
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
# Metrics Endpoints
# ========================

@router.get("/queries", summary="Get paginated RAG queries with filters")
async def get_query_metrics(
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    user_id: Optional[str] = Query(None),
    filename: Optional[str] = Query(None),
    model_type: Optional[str] = Query(None),
    humanize: Optional[bool] = Query(None),
    since: str = Query("24h"),
    search_question: Optional[str] = Query(None, description="Fuzzy search in question text"),
    admin_user=Depends(require_admin_or_master)
) -> dict:
    """
    Retrieve RAG queries for analytics. Supports filtering and pagination.
    Ideal for displaying in tables or building funnels.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    base_query = '''
        SELECT id, session_id, user_id, role, question, answer, model_type, humanize,
               source_document_count, security_filtered, source_filenames,
               response_time_ms, timestamp, ip_address
        FROM queries
    '''
    count_query = 'SELECT COUNT(*) AS total FROM queries'
    params = []
    where_clauses = []

    parsed_since = parse_since(since)
    where_clauses.append("timestamp >= ?")
    params.append(parsed_since)

    if user_id:
        where_clauses.append("user_id = ?")
        params.append(user_id)
    if model_type:
        where_clauses.append("model_type = ?")
        params.append(model_type)
    if humanize is not None:
        where_clauses.append("humanize = ?")
        params.append(1 if humanize else 0)
    if filename:
        where_clauses.append("source_filenames LIKE ?")
        params.append(f'%{filename}%')
    if search_question:
        where_clauses.append("question LIKE ?")
        params.append(f'%{search_question}%')

    if where_clauses:
        base_query += " WHERE " + " AND ".join(where_clauses)
        count_query += " WHERE " + " AND ".join(where_clauses)

    base_query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(count_query, params[:-2])
    total = cursor.fetchone()["total"]

    cursor.execute(base_query, params)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "queries": results
    }


@router.get("/aggregations/users", summary="User activity summary")
async def get_user_activity_summary(
    since: str = Query("24h"),
    admin_user=Depends(require_admin_or_master)
) -> dict:
    """
    Get top users by query count, with avg response time and model usage.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT
            user_id,
            role,
            COUNT(*) as query_count,
            AVG(response_time_ms) as avg_response_time_ms,
            GROUP_CONCAT(model_type) as model_types_used
        FROM queries
        WHERE timestamp >= ?
        GROUP BY user_id, role
        ORDER BY query_count DESC
    '''
    cursor.execute(query, (parse_since(since),))
    rows = cursor.fetchall()
    conn.close()

    data = []
    for r in rows:
        model_breakdown = {}
        for mt in (r["model_types_used"] or "").split(","):
            model_breakdown[mt] = model_breakdown.get(mt, 0) + 1

        data.append({
            "user_id": r["user_id"],
            "role": r["role"],
            "query_count": r["query_count"],
            "avg_response_time_ms": round(r["avg_response_time_ms"] or 0, 2),
            "model_breakdown": model_breakdown
        })

    return {"since": since, "users": data}


@router.get("/aggregations/files", summary="File popularity and access stats")
async def get_file_usage_stats(
    since: str = Query("24h"),
    admin_user=Depends(require_admin_or_master)
) -> dict:
    """
    Get most accessed files in RAG responses or direct views.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT filename, COUNT(*) as retrieval_count
        FROM file_access_logs
        WHERE access_type = 'retrieved_in_rag' AND timestamp >= ?
        GROUP BY filename
        ORDER BY retrieval_count DESC
        LIMIT 20
    '''
    cursor.execute(query, (parse_since(since),))
    rag_files = [{"filename": r["filename"], "count": r["retrieval_count"]} for r in cursor.fetchall()]

    query2 = '''
        SELECT filename, COUNT(*) as view_count
        FROM file_access_logs
        WHERE access_type = 'view' AND timestamp >= ?
        GROUP BY filename
        ORDER BY view_count DESC
        LIMIT 20
    '''
    cursor.execute(query2, (parse_since(since),))
    view_files = [{"filename": r["filename"], "count": r["view_count"]} for r in cursor.fetchall()]
    conn.close()

    return {
        "since": since,
        "top_files_in_rag": rag_files,
        "top_files_direct_view": view_files
    }


@router.get("/aggregations/timeseries", summary="Time-series data for graphs")
async def get_time_series(
    interval: str = Query("hour", description="hour, day"),
    metric: str = Query("queries", description="queries, users, response_time"),
    since: str = Query("7d"),
    admin_user=Depends(require_admin_or_master)
) -> dict:
    """
    Return time-series data suitable for line/bar charts.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    time_col = "strftime('%Y-%m-%d %H:00', timestamp)" if interval == "hour" else "strftime('%Y-%m-%d', timestamp)"
    since_dt = parse_since(since)

    if metric == "queries":
        query = f'''
            SELECT {time_col} AS period, COUNT(*) as value
            FROM queries
            WHERE timestamp >= ?
            GROUP BY period
            ORDER BY period
        '''
        cursor.execute(query, (since_dt,))
    elif metric == "users":
        query = f'''
            SELECT {time_col} AS period, COUNT(DISTINCT user_id) as value
            FROM queries
            WHERE timestamp >= ?
            GROUP BY period
            ORDER BY period
        '''
        cursor.execute(query, (since_dt,))
    elif metric == "response_time":
        query = f'''
            SELECT {time_col} AS period, AVG(response_time_ms) as value
            FROM queries
            WHERE timestamp >= ?
            GROUP BY period
            ORDER BY period
        '''
        cursor.execute(query, (since_dt,))
    else:
        raise HTTPException(status_code=400, detail="Invalid metric. Use: queries, users, response_time")

    data = [{"period": row["period"], "value": round(row["value"] or 0, 2)} for row in cursor.fetchall()]
    conn.close()

    return {
        "metric": metric,
        "interval": interval,
        "since": since,
        "data": data
    }


@router.get("/aggregations/models", summary="Model usage breakdown")
async def get_model_usage(
    since: str = Query("24h"),
    admin_user=Depends(require_admin_or_master)
) -> dict:
    """
    Get percentage and count of local vs server model usage.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT model_type, COUNT(*) as count
        FROM queries
        WHERE timestamp >= ?
        GROUP BY model_type
    '''
    cursor.execute(query, (parse_since(since),))
    rows = cursor.fetchall()
    conn.close()

    total = sum(r["count"] for r in rows)
    breakdown = []
    for r in rows:
        pct = round((r["count"] / total) * 100, 1) if total > 0 else 0
        breakdown.append({
            "model_type": r["model_type"],
            "count": r["count"],
            "percentage": pct
        })

    return {
        "since": since,
        "total_queries": total,
        "breakdown": breakdown
    }


@router.get("/summary", summary="Dashboard summary cards")
async def get_dashboard_summary(admin_user=Depends(require_admin_or_master)) -> dict:
    """
    High-level KPIs for admin dashboard cards.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.utcnow().isoformat()
    day_ago = (datetime.utcnow() - timedelta(hours=24)).isoformat()

    cursor.execute('SELECT COUNT(*) as c FROM queries WHERE timestamp > ?', (day_ago,))
    total_queries_24h = cursor.fetchone()["c"]

    cursor.execute('SELECT COUNT(DISTINCT user_id) as c FROM queries WHERE timestamp > ?', (day_ago,))
    active_users_24h = cursor.fetchone()["c"]

    cursor.execute('SELECT AVG(response_time_ms) as v FROM queries WHERE timestamp > ?', (day_ago,))
    avg_latency = round(cursor.fetchone()["v"] or 0, 2)

    cursor.execute('''
        SELECT filename, COUNT(*) as c FROM file_access_logs
        WHERE access_type = 'retrieved_in_rag'
        GROUP BY filename ORDER BY c DESC LIMIT 1
    ''')
    top_file_row = cursor.fetchone()
    top_file = top_file_row["filename"] if top_file_row else "N/A"

    conn.close()

    return {
        "timestamp": now,
        "total_queries_24h": total_queries_24h,
        "active_users_24h": active_users_24h,
        "avg_response_time_ms": avg_latency,
        "top_performing_file": top_file,
        "system_uptime": "N/A"  # Could be added later
    }