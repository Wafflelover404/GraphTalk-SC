# Analytics Toolkit - Quick Reference Card

## 🚀 Quick Start (5 Minutes)

### 1. Initialize
```python
from analytics_core import get_analytics_core
analytics = get_analytics_core()  # Creates analytics.db
```

### 2. Log Query
```python
from analytics_middleware import QueryAnalyticsHelper
await QueryAnalyticsHelper.log_query(
    session_id=session_id,
    user_id=user_id,
    role=role,
    question="Your question",
    answer="Response",
    model_type="local",
    response_time_ms=2500,
    source_documents=docs
)
```

### 3. Log File Access
```python
from analytics_middleware import FileAccessAnalyticsHelper
await FileAccessAnalyticsHelper.log_file_access(
    user_id=user_id,
    filename="document.pdf",
    access_type="uploaded"
)
```

### 4. Get Insights
```python
# Performance
stats = analytics.get_query_statistics(since_hours=24)
print(f"Avg response: {stats['avg_response_time_ms']}ms")

# Users
analyzer = UserBehaviorAnalyzer(analytics)
segments = analyzer.get_user_segments()

# Security
security = SecurityAnalyzer(analytics)
threats = security.get_threat_summary()
```

### 5. Access API
```
curl -H "Authorization: Bearer <token>" \
  http://localhost:9001/analytics/report/executive-summary
```

---

## 📊 Core Functions

### Query Analytics
```python
analytics.log_query(metrics)
analytics.get_query_statistics(since_hours=24)
analytics.get_query_analytics(limit=100)
```

### Performance
```python
analytics.log_performance(metrics)
analytics.get_performance_statistics(since_hours=24)
```

### User Behavior
```python
analytics.log_user_behavior(event)
analyzer.get_user_engagement_score(user_id)
analyzer.get_user_segments()
analyzer.get_user_retention(cohort_days=7)
```

### Security
```python
analytics.log_security_event(event)
security.get_threat_summary(since_hours=24)
security.detect_brute_force_attempts()
security.detect_credential_stuffing()
security.detect_permission_abuse()
```

### Documents
```python
analytics.update_document_analytics(filename, increment_rag_hits=1)
analytics.get_top_documents(limit=20)
```

### Errors
```python
analytics.log_error(error_type, message, endpoint)
analytics.get_error_summary(since_hours=24)
```

---

## 🔌 API Endpoints (40+)

### Performance
- `GET /analytics/performance/overview`
- `GET /analytics/performance/query-latency`
- `GET /analytics/performance/bottlenecks`
- `GET /analytics/performance/endpoints`

### Users
- `GET /analytics/users/engagement-score/{user_id}`
- `GET /analytics/users/segments`
- `GET /analytics/users/retention`
- `GET /analytics/users/churned`
- `GET /analytics/users/feature-adoption`
- `GET /analytics/users/funnel/{user_id}`
- `GET /analytics/users/high-value`

### Security
- `GET /analytics/security/threats`
- `GET /analytics/security/suspicious-ips`
- `GET /analytics/security/suspicious-users`
- `GET /analytics/security/brute-force`
- `GET /analytics/security/credential-stuffing`
- `GET /analytics/security/permission-abuse`
- `GET /analytics/security/anomalies/{user_id}`

### Compliance
- `GET /analytics/compliance/audit-log`
- `GET /analytics/compliance/retention`
- `GET /analytics/compliance/user-report/{user_id}`

### Reports
- `GET /analytics/report/executive-summary`
- `GET /analytics/report/daily-summary`

### Other
- `GET /analytics/conversion/funnel`
- `GET /analytics/documents/top`
- `GET /analytics/errors/summary`

---

## 📈 Key Metrics

| Metric | Source | Example |
|--------|--------|---------|
| Avg Response Time | query_analytics | 2340ms |
| Success Rate | query_analytics | 94.2% |
| Unique Users | queries | 45 |
| Engagement Score | user_behavior | 72/100 |
| Cache Hit Rate | query_analytics | 18.5% |
| Security Events | security_events | 150 |
| Blocked Events | security_events | 42 |
| Slow Queries | performance | 12 queries |

---

## 🗄️ 14 Tables at a Glance

| Table | Records | Key Info |
|-------|---------|----------|
| query_analytics | 1000+ | Query metrics, response times |
| performance_metrics | 5000+ | Operation timing, resources |
| user_behavior_events | 2000+ | User actions, engagement |
| security_events | 100+ | Threats, attacks, violations |
| endpoint_access | 5000+ | API usage, performance |
| error_tracking | 50+ | Errors, frequency, stack traces |
| query_funnel | 500+ | Query refinement steps |
| document_analytics | 50+ | File popularity, usage |
| user_journey | 100+ | Session tracking |
| file_access_logs | 1000+ | File operations |
| system_metrics | 1000+ | System health |
| application_logs | 5000+ | General logging |
| users | 50+ | User accounts |
| sessions | 100+ | Active sessions |

---

## 🔐 Classes & Objects

### QueryMetrics
```python
QueryMetrics(
    query_id, session_id, user_id, role,
    question, answer_length, model_type, query_type,
    response_time_ms, token_input, token_output,
    source_document_count, source_files,
    humanized, security_filtered, rag_score,
    cache_hit, ip_address, user_agent, success
)
```

### UserBehaviorEvent
```python
UserBehaviorEvent(
    user_id, session_id, event_type, event_subtype,
    duration_seconds, interaction_count, success,
    details, ip_address
)
```

### SecurityEvent
```python
SecurityEvent(
    event_type, user_id, ip_address, session_id,
    severity, details, blocked
)
```

### PerformanceMetrics
```python
PerformanceMetrics(
    operation_name, duration_ms,
    cpu_percent, memory_mb, disk_io_mb, network_io_mb,
    component, details
)
```

---

## 🎯 Integration Points

### In api.py
```python
# Add imports
from analytics_core import get_analytics_core
from advanced_analytics_api import router as analytics_router
from analytics_middleware import AdvancedAnalyticsMiddleware

# Add middleware
app.add_middleware(AdvancedAnalyticsMiddleware)

# Add router
app.include_router(analytics_router)
```

### In endpoints
```python
# Track queries
await QueryAnalyticsHelper.log_query(...)

# Track files
await FileAccessAnalyticsHelper.log_file_access(...)

# Track performance
tracker = PerformanceTracker(analytics)
with tracker.track_operation("operation_name"):
    # Your code
    pass
```

---

## 💡 Common Queries

### Get Performance Summary
```python
stats = analytics.get_query_statistics(since_hours=24)
```

### Get User Segments
```python
analyzer = UserBehaviorAnalyzer(analytics)
segments = analyzer.get_user_segments()
```

### Get Threats
```python
security = SecurityAnalyzer(analytics)
threats = security.get_threat_summary()
```

### Get Top Documents
```python
docs = analytics.get_top_documents(limit=20)
```

### Get Slow Queries
```python
analyzer = QueryPerformanceAnalyzer(analytics)
slow = analyzer.identify_slow_queries(threshold_ms=3000)
```

### Get User Engagement
```python
analyzer = UserBehaviorAnalyzer(analytics)
score = analyzer.get_user_engagement_score(user_id)
```

### Get Errors
```python
errors = analytics.get_error_summary(since_hours=24)
```

### Get Suspicious IPs
```python
security = SecurityAnalyzer(analytics)
ips = security.get_suspicious_ips(since_hours=24)
```

### Get Brute Force Attempts
```python
attacks = security.detect_brute_force_attempts()
```

### Get Churned Users
```python
analyzer = UserBehaviorAnalyzer(analytics)
churned = analyzer.identify_churned_users(days_inactive=30)
```

---

## 🚨 Troubleshooting

| Issue | Solution |
|-------|----------|
| No data in tables | Check middleware is added, restart server |
| Database locked | Delete analytics.db and reinitialize |
| Slow queries | Add indexes, check query complexity |
| Permission denied | Use admin token in Authorization header |
| Import errors | Verify files are in GraphTalk directory |

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `ANALYTICS_TOOLKIT_README.md` | Complete documentation |
| `ANALYTICS_INTEGRATION_GUIDE.md` | How to integrate |
| `IMPLEMENTATION_CHECKLIST.md` | Step-by-step setup |
| `ANALYTICS_SUMMARY.md` | Executive summary |
| `QUICK_REFERENCE.md` | This file |

---

## ⚡ Performance Tips

1. **Use helpers** for automatic tracking
2. **Batch operations** when possible
3. **Query with time windows** (since_hours parameter)
4. **Index on frequently queried fields** (user_id, timestamp)
5. **Archive old data** periodically (90+ days)
6. **Use pagination** for large result sets (limit, offset)

---

## 🎓 Example: Complete Query Tracking

```python
async def track_query(request, user):
    from analytics_middleware import QueryAnalyticsHelper
    import time
    
    start = time.time()
    
    try:
        # Execute query
        result = rag_chain.invoke(request.question)
        
        # Log with helper
        await QueryAnalyticsHelper.log_query(
            session_id=str(uuid.uuid4()),
            user_id=user[1],
            role=user[3],
            question=request.question,
            answer=result['answer'],
            model_type="local",
            query_type="rag_search",
            response_time_ms=int((time.time() - start) * 1000),
            source_documents=result['source_docs'],
            success=True
        )
        
        return result
    except Exception as e:
        # Log error
        analytics = get_analytics_core()
        analytics.log_error(
            error_type=type(e).__name__,
            message=str(e),
            endpoint="/query"
        )
        raise
```

---

## 🔄 Data Flow

```
Request → Middleware (collect) → Analytics Core (store)
                                      ↓
                               SQLite Database
                                      ↓
                         Analytics API (query)
                                      ↓
                           Response / Dashboard
```

---

**Version**: 1.0  
**Status**: Ready to Use  
**Support**: See documentation files  
**Last Updated**: 2024
