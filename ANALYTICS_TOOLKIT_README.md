# Advanced Analytics Toolkit for GraphTalk Backend

A comprehensive analytics engine that collects, analyzes, and provides insights on all backend operations, user behavior, performance, and security.

## 🎯 Features

### Core Analytics
- **Query Analytics**: Comprehensive tracking of all RAG queries, response times, success rates
- **Performance Metrics**: Operation timing, latency analysis, bottleneck identification
- **User Behavior**: Session tracking, engagement scoring, user segmentation, retention analysis
- **Security Tracking**: Threat detection, anomaly detection, compliance auditing
- **Error Tracking**: Error aggregation, frequency analysis, stack trace logging
- **Document Analytics**: File access patterns, popularity metrics, relevance scoring

### Advanced Analysis
- **Query Funnel Analysis**: Track query refinement patterns and user satisfaction
- **User Journey Mapping**: Complete session tracking from login to conversion
- **Conversion Funnel**: User path to conversion analysis
- **Threat Detection**: Brute force, credential stuffing, permission abuse detection
- **Compliance Reporting**: User access reports, audit logs, data retention tracking
- **Performance Insights**: Slow query identification, resource utilization patterns

## 📊 Database Schema

### 14 Specialized Tables

1. **query_analytics** - Comprehensive query metrics
   - Query ID, session, user, question, answer, response time
   - Token counts, source documents, model type, cache hits
   - Security filtering, RAG scores

2. **performance_metrics** - Operation performance data
   - Operation name, duration, CPU, memory, disk I/O
   - Component tracking, detailed metrics JSON

3. **user_behavior_events** - User interactions
   - Event types, subtypes, duration, interaction count
   - User satisfaction, success flags

4. **security_events** - Security-related events
   - Event type, severity, user, IP address
   - Blocked flag, detailed event data

5. **endpoint_access** - API endpoint tracking
   - Endpoint, method, status code, response time
   - Request/response sizes, per-user metrics

6. **error_tracking** - Centralized error logging
   - Error type, message, stack trace
   - Frequency tracking, first/last occurrence

7. **query_funnel** - Query refinement tracking
   - Session-based funnel steps
   - Document counts, user satisfaction

8. **document_analytics** - File usage metrics
   - Access count, RAG hit count, unique users
   - Relevance scores, chunk counts

9. **user_journey** - Complete session tracking
   - Session start/end, duration
   - Query count, file access count, conversion flag

### Indexes for Performance
All tables include strategic indexes on:
- User ID, session ID, timestamp
- Event types, components, status codes
- Filename, endpoint paths

## 🔌 API Endpoints

### Performance Analytics
```
GET /analytics/performance/overview
GET /analytics/performance/query-latency
GET /analytics/performance/bottlenecks
GET /analytics/performance/endpoints
```

### User Behavior
```
GET /analytics/users/engagement-score/{user_id}
GET /analytics/users/segments
GET /analytics/users/retention
GET /analytics/users/churned
GET /analytics/users/feature-adoption
GET /analytics/users/funnel/{user_id}
GET /analytics/users/high-value
GET /analytics/conversion/funnel
```

### Security & Compliance
```
GET /analytics/security/threats
GET /analytics/security/suspicious-ips
GET /analytics/security/suspicious-users
GET /analytics/security/brute-force
GET /analytics/security/credential-stuffing
GET /analytics/security/permission-abuse
GET /analytics/security/anomalies/{user_id}
GET /analytics/compliance/audit-log
GET /analytics/compliance/retention
GET /analytics/compliance/user-report/{user_id}
```

### Documents & Errors
```
GET /analytics/documents/top
GET /analytics/errors/summary
```

### Reports
```
GET /analytics/report/executive-summary
GET /analytics/report/daily-summary
```

## 🚀 Quick Start

### 1. Initialize Analytics

```python
from analytics_core import get_analytics_core

# Get analytics instance (singleton)
analytics = get_analytics_core()
```

### 2. Track Queries

```python
from analytics_core import QueryMetrics, QueryType
import uuid
import time

start = time.time()

metrics = QueryMetrics(
    query_id=str(uuid.uuid4()),
    session_id=session_id,
    user_id=username,
    role=user_role,
    question="What is RAG?",
    answer_length=len(answer),
    model_type="local",
    query_type=QueryType.RAG_SEARCH,
    response_time_ms=int((time.time() - start) * 1000),
    source_document_count=len(docs),
    source_files=["doc1.pdf", "doc2.pdf"],
    humanized=True,
    ip_address=client_ip
)

analytics.log_query(metrics)
```

### 3. Track Performance

```python
from performance_analytics import PerformanceTracker

tracker = PerformanceTracker(analytics)

with tracker.track_operation("rag_inference", component="llm"):
    # Your LLM inference code
    result = await llm_call(prompt)

# Get bottlenecks
bottlenecks = tracker.get_bottlenecks()
```

### 4. Track User Behavior

```python
from analytics_core import UserBehaviorEvent

event = UserBehaviorEvent(
    user_id=user_id,
    session_id=session_id,
    event_type="query_search",
    event_subtype="rag_humanized",
    duration_seconds=5,
    success=True,
    details={"documents_found": 3}
)

analytics.log_user_behavior(event)
```

### 5. Track Security Events

```python
from analytics_core import SecurityEvent, SecurityEventType

event = SecurityEvent(
    event_type=SecurityEventType.FAILED_LOGIN,
    user_id=username,
    ip_address=client_ip,
    severity="medium"
)

analytics.log_security_event(event)
```

## 📈 Accessing Analytics Data

### Query Statistics

```python
stats = analytics.get_query_statistics(since_hours=24)
print(f"Total queries: {stats['total_queries']}")
print(f"Success rate: {stats['successful_queries']} / {stats['total_queries']}")
print(f"Avg response time: {stats['avg_response_time_ms']}ms")
```

### User Engagement

```python
from user_behavior_analytics import UserBehaviorAnalyzer

analyzer = UserBehaviorAnalyzer(analytics)
engagement = analyzer.get_user_engagement_score("user123")
print(f"Engagement score: {engagement['overall_score']}/100")
```

### User Segments

```python
segments = analyzer.get_user_segments()
print(f"Power users: {segments['power_users']['count']}")
print(f"Active users: {segments['active_users']['count']}")
print(f"Casual users: {segments['casual_users']['count']}")
```

### Security Threats

```python
from security_analytics import SecurityAnalyzer

security = SecurityAnalyzer(analytics)
threats = security.get_threat_summary(since_hours=24)
print(f"Security events: {threats['total_events']}")
print(f"Blocked events: {threats['total_blocked']}")
```

### Slow Queries

```python
from performance_analytics import QueryPerformanceAnalyzer

perf = QueryPerformanceAnalyzer(analytics)
slow = perf.identify_slow_queries(threshold_ms=5000)
for query in slow:
    print(f"{query['question']}: {query['response_time_ms']}ms")
```

## 🔒 Integration Points

### In api.py

```python
from advanced_analytics_api import router as analytics_router

app.include_router(analytics_router)
```

### In query endpoint

```python
@app.post("/query")
async def process_query(request: RAGQueryRequest, user=Depends(get_current_user)):
    start = time.time()
    
    # Your query logic
    result = await rag_chain.invoke(request.question)
    
    # Log metrics
    metrics = QueryMetrics(
        query_id=str(uuid.uuid4()),
        session_id=session_id,
        user_id=user[1],
        role=user[3],
        question=request.question,
        answer_length=len(result['answer']),
        response_time_ms=int((time.time() - start) * 1000),
        source_documents=result['source_docs']
    )
    analytics.log_query(metrics)
```

### In middleware

```python
from analytics_middleware import AdvancedAnalyticsMiddleware

app.add_middleware(AdvancedAnalyticsMiddleware)
```

## 📊 Dashboard Examples

### Executive Summary
```python
summary = await analytics_api.get_executive_summary()
# Returns:
{
    "key_metrics": {
        "total_queries": 1500,
        "success_rate": 94.2,
        "avg_response_time_ms": 2340,
        "cache_hit_rate": 18.5,
        "unique_users": 45
    },
    "performance": { ... },
    "errors": { ... },
    "security": { ... }
}
```

### User Segments
```python
segments = analyzer.get_user_segments()
# Returns:
{
    "power_users": {"count": 5, "percent": 11.1},
    "active_users": {"count": 15, "percent": 33.3},
    "casual_users": {"count": 20, "percent": 44.4},
    "inactive_users": {"count": 5, "percent": 11.1}
}
```

### Security Threats
```python
threats = security.get_threat_summary()
# Returns:
{
    "total_events": 150,
    "critical_events": 5,
    "blocked_events": 42,
    "event_breakdown": [...]
}
```

## 🎯 Key Metrics

### Performance KPIs
- Average response time
- P50, P75, P90, P95, P99 latencies
- Cache hit rate
- Success rate
- Throughput (queries/min)

### User KPIs
- Engagement score (0-100)
- Session duration
- Queries per session
- Feature adoption rate
- Retention rate

### Security KPIs
- Failed login attempts
- Unauthorized access attempts
- Brute force attacks
- Permission violations
- Events blocked

### Business KPIs
- Conversion rate
- User segmentation
- High-value user count
- Churn rate
- Document popularity

## 🔧 Advanced Features

### Anomaly Detection
- Unusual access patterns
- Geographic anomalies (with geo data)
- Access time anomalies
- Scanning behavior detection

### Trend Analysis
- Query volume trends
- Response time trends
- User engagement trends
- Error rate trends

### Funnel Analysis
- Query refinement funnels
- User conversion funnels
- Document access funnels

### Compliance
- Audit log generation
- Data retention tracking
- User access reports
- Deletion reports

## 📦 Dependencies

```
sqlite3 (built-in)
psutil (for resource monitoring)
```

## 🗂️ Files

- `analytics_core.py` - Core analytics engine (14 tables, 25+ queries)
- `performance_analytics.py` - Performance tracking and analysis
- `user_behavior_analytics.py` - User behavior and engagement analytics
- `security_analytics.py` - Security event and threat analysis
- `advanced_analytics_api.py` - FastAPI analytics endpoints (40+ endpoints)
- `analytics_middleware.py` - HTTP middleware for automatic collection
- `ANALYTICS_INTEGRATION_GUIDE.md` - Integration instructions

## 📝 Example: Complete Query Tracking

```python
async def track_rag_query(request, user):
    from analytics_core import QueryMetrics, QueryType, get_analytics_core
    from analytics_middleware import QueryAnalyticsHelper
    
    analytics = get_analytics_core()
    start = time.time()
    
    try:
        # Execute query
        result = rag_chain.invoke(request.question)
        
        # Log with helper
        await QueryAnalyticsHelper.log_query(
            session_id=session_id,
            user_id=user[1],
            role=user[3],
            question=request.question,
            answer=result['answer'],
            model_type="local",
            query_type=QueryType.RAG_SEARCH.value,
            response_time_ms=int((time.time() - start) * 1000),
            source_documents=result['source_docs'],
            success=True
        )
        
        return result
        
    except Exception as e:
        # Log error
        analytics.log_error(
            error_type=type(e).__name__,
            message=str(e),
            endpoint="/query"
        )
        raise
```

## 🎓 Best Practices

1. **Use Helpers**: `QueryAnalyticsHelper`, `FileAccessAnalyticsHelper`
2. **Batch Operations**: Group related metrics together
3. **Include Context**: Add relevant details in `details` dict
4. **Track Errors**: Always log exceptions with context
5. **Monitor Performance**: Use `PerformanceTracker` for expensive operations
6. **Regular Analysis**: Query analytics regularly to spot trends
7. **Clean Data**: Archive old records periodically

## 📊 Querying Directly

```python
# Get low-level database connection
conn = analytics.db.get_connection()
cursor = conn.cursor()

cursor.execute('''
    SELECT user_id, COUNT(*) as query_count
    FROM query_analytics
    WHERE timestamp > datetime('now', '-7 days')
    GROUP BY user_id
    ORDER BY query_count DESC
    LIMIT 10
''')

results = cursor.fetchall()
conn.close()
```

## 🚨 Common Scenarios

### Scenario 1: Slow Query Investigation
```python
perf = QueryPerformanceAnalyzer(analytics)
slow_queries = perf.identify_slow_queries(threshold_ms=3000)

# Group by question to find patterns
from itertools import groupby
for question, queries in groupby(slow_queries, key=lambda x: x['question']):
    print(f"Question: {question}")
    print(f"  Count: {len(list(queries))}")
```

### Scenario 2: Security Alert
```python
security = SecurityAnalyzer(analytics)

# Check for brute force
brute_force = security.detect_brute_force_attempts(since_hours=1, threshold=5)
if brute_force:
    # Alert admin
    for attack in brute_force:
        print(f"ALERT: Brute force from {attack['ip_address']}")
```

### Scenario 3: User Retention Campaign
```python
analyzer = UserBehaviorAnalyzer(analytics)

# Find churned users
churned = analyzer.identify_churned_users(days_inactive=30)

# Categorize for re-engagement campaign
high_value_churned = [
    u for u in churned
    if u['total_sessions'] > 10
]
```

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Status**: Production Ready
