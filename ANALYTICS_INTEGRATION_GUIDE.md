"""
Analytics Integration Guide
Instructions for integrating the analytics toolkit with existing endpoints
"""

# ==================== INTEGRATION CHECKLIST ====================
"""

1. UPDATE main.py:
   - Import analytics_core and get_analytics_core()
   - Initialize analytics on startup
   
   from analytics_core import get_analytics_core
   
   @app.on_event("startup")
   async def startup_analytics():
       analytics = get_analytics_core()
       logger.info("Analytics initialized")

2. UPDATE api.py:
   - Import analytics modules
   - Create middleware for endpoint tracking
   - Update endpoints to log metrics
   
   from analytics_core import (
       get_analytics_core, QueryMetrics, QueryType, UserBehaviorEvent
   )
   
3. TRACK QUERIES:
   In /query and /chat endpoints:
   
   # Create query metrics
   metrics = QueryMetrics(
       query_id=str(uuid.uuid4()),
       session_id=session_id,
       user_id=username,
       role=role,
       question=request.question,
       answer_length=len(answer),
       model_type=model_type,
       query_type=QueryType.RAG_SEARCH,
       response_time_ms=int((time.time() - start) * 1000),
       source_document_count=len(source_docs),
       source_files=[doc.metadata.get('source') for doc in source_docs],
       humanized=request.humanize,
       security_filtered=security_filtered,
       ip_address=request_obj.client.host
   )
   
   analytics = get_analytics_core()
   analytics.log_query(metrics)

4. TRACK FILE ACCESS:
   In file upload/download endpoints:
   
   analytics.update_document_analytics(
       filename=file.filename,
       file_id=file_id,
       size_bytes=file_size,
       chunk_count=chunks,
       increment_access=1
   )

5. TRACK SECURITY EVENTS:
   In login/auth endpoints:
   
   if not verify_user(username, password):
       event = SecurityEvent(
           event_type=SecurityEventType.FAILED_LOGIN,
           user_id=username,
           ip_address=request_obj.client.host,
           severity="medium"
       )
       analytics.log_security_event(event)

6. TRACK ENDPOINT ACCESS:
   In metrics middleware:
   
   analytics.log_endpoint_access(
       endpoint=request.url.path,
       method=request.method,
       user_id=user_id,
       status_code=response.status_code,
       response_time_ms=int((time.time() - start) * 1000),
       ip_address=request.client.host
   )

7. TRACK ERRORS:
   In error handlers:
   
   analytics.log_error(
       error_type=type(e).__name__,
       message=str(e),
       stack=traceback.format_exc(),
       endpoint=request.url.path,
       user_id=user_id
   )

8. REGISTER ANALYTICS ROUTER:
   In api.py:
   
   from advanced_analytics_api import router as analytics_router
   app.include_router(analytics_router)

"""

# ==================== QUERY METRICS EXAMPLE ====================
"""

import uuid
import time
from datetime import datetime
from analytics_core import get_analytics_core, QueryMetrics, QueryType

async def track_query_endpoint(request, user):
    start_time = time.time()
    analytics = get_analytics_core()
    
    try:
        # Execute query
        result = await process_query(request.question)
        
        # Log metrics
        metrics = QueryMetrics(
            query_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            user_id=user[1],
            role=user[3],
            question=request.question,
            answer_length=len(result.get("answer", "")),
            model_type="local",  # from env
            query_type=QueryType.RAG_SEARCH,
            response_time_ms=int((time.time() - start_time) * 1000),
            token_input=result.get("tokens_input", 0),
            token_output=result.get("tokens_output", 0),
            source_document_count=len(result.get("source_docs", [])),
            source_files=result.get("source_files", []),
            humanized=True,
            security_filtered=result.get("filtered", False),
            ip_address="127.0.0.1"
        )
        
        analytics.log_query(metrics)
        return result
    
    except Exception as e:
        # Log error
        analytics.log_error(
            error_type=type(e).__name__,
            message=str(e),
            endpoint="/query"
        )
        raise

"""

# ==================== PERFORMANCE TRACKING EXAMPLE ====================
"""

from performance_analytics import PerformanceTracker

async def expensive_operation():
    analytics = get_analytics_core()
    tracker = PerformanceTracker(analytics)
    
    with tracker.track_operation("database_query", component="rag_api"):
        # Your expensive operation here
        result = await query_database()
    
    with tracker.track_operation("llm_inference", component="llm"):
        # LLM inference
        response = await llm_call(result)
    
    # Get performance summary
    slowest = tracker.get_slowest_operations(limit=5)
    bottlenecks = tracker.get_bottlenecks()
    
    return response

"""

# ==================== USER BEHAVIOR TRACKING EXAMPLE ====================
"""

from analytics_core import UserBehaviorEvent

async def track_user_query(user_id, session_id):
    analytics = get_analytics_core()
    
    event = UserBehaviorEvent(
        user_id=user_id,
        session_id=session_id,
        event_type="query_search",
        event_subtype="rag_humanized",
        duration_seconds=5,
        interaction_count=1,
        success=True,
        details={
            "query_length": 50,
            "documents_found": 3,
            "user_satisfied": True
        }
    )
    
    analytics.log_user_behavior(event)

"""

# ==================== SECURITY TRACKING EXAMPLE ====================
"""

from analytics_core import SecurityEvent, SecurityEventType

async def track_failed_login(username, ip_address):
    analytics = get_analytics_core()
    
    event = SecurityEvent(
        event_type=SecurityEventType.FAILED_LOGIN,
        user_id=username,
        ip_address=ip_address,
        severity="medium",
        details={"attempt": 1}
    )
    
    analytics.log_security_event(event)

"""

# ==================== ACCESSING ANALYTICS DATA ====================
"""

from analytics_core import get_analytics_core
from user_behavior_analytics import UserBehaviorAnalyzer
from performance_analytics import QueryPerformanceAnalyzer
from security_analytics import SecurityAnalyzer

# Get analytics core
analytics = get_analytics_core()

# Query statistics
stats = analytics.get_query_statistics(since_hours=24)
print(f"Total queries: {stats['total_queries']}")
print(f"Avg response time: {stats['avg_response_time_ms']}ms")

# User engagement
user_analyzer = UserBehaviorAnalyzer(analytics)
engagement = user_analyzer.get_user_engagement_score("user123")
print(f"User engagement: {engagement['overall_score']}")

# Performance analysis
perf_analyzer = QueryPerformanceAnalyzer(analytics)
slow_queries = perf_analyzer.identify_slow_queries(threshold_ms=5000)
print(f"Slow queries: {len(slow_queries)}")

# Security analysis
security_analyzer = SecurityAnalyzer(analytics)
threats = security_analyzer.get_threat_summary(since_hours=24)
print(f"Security events: {threats['total_events']}")

# Top documents
docs = analytics.get_top_documents(limit=10)
for doc in docs:
    print(f"{doc['filename']}: {doc['access_count']} accesses")

"""

# ==================== DATABASE MIGRATION ====================
"""

If you have existing metrics.db:

1. Backup: cp metrics.db metrics.db.backup

2. Create new analytics.db:
   from analytics_core import AnalyticsDB
   db = AnalyticsDB("analytics.db")

3. Migrate data (if needed):
   - Old metrics.db will continue to work
   - New analytics.db captures new data
   - Keep both for transition period

4. Update environment variables:
   export METRICS_DB_PATH=analytics.db

"""

# ==================== DASHBOARD ENDPOINTS ====================
"""

Available endpoints:

Performance:
  GET /analytics/performance/overview
  GET /analytics/performance/query-latency
  GET /analytics/performance/bottlenecks
  GET /analytics/performance/endpoints

Users:
  GET /analytics/users/engagement-score/{user_id}
  GET /analytics/users/segments
  GET /analytics/users/retention
  GET /analytics/users/churned
  GET /analytics/users/feature-adoption
  GET /analytics/users/funnel/{user_id}
  GET /analytics/users/high-value

Conversion:
  GET /analytics/conversion/funnel

Security:
  GET /analytics/security/threats
  GET /analytics/security/suspicious-ips
  GET /analytics/security/suspicious-users
  GET /analytics/security/brute-force
  GET /analytics/security/credential-stuffing
  GET /analytics/security/permission-abuse
  GET /analytics/security/anomalies/{user_id}

Compliance:
  GET /analytics/compliance/audit-log
  GET /analytics/compliance/retention
  GET /analytics/compliance/user-report/{user_id}

Documents:
  GET /analytics/documents/top

Errors:
  GET /analytics/errors/summary

Reports:
  GET /analytics/report/executive-summary
  GET /analytics/report/daily-summary

"""
