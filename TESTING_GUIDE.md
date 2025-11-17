# Advanced Analytics - Testing Guide

## Quick Start

### Prerequisites
- FastAPI server running: `python3 api.py` 
- curl installed (pre-installed on macOS/Linux)
- Admin token: `29c63be0-06c1-4051-b3ef-034e46a6dfed`

### Option 1: Quick Python Test (Recommended)
```bash
cd GraphTalk
python3 test_analytics_quick.py
```
✅ Uses curl under the hood - no dependencies needed

### Option 2: Full Python Test Suite
```bash
cd GraphTalk
python3 test_analytics.py
```
⚠️ Requires `requests` library (already in requirements.txt)

### Option 3: Pure Bash/Curl Test
```bash
cd GraphTalk
bash test_analytics_curl.sh
```
✅ 100% bash/curl - works anywhere

### Option 4: Manual Curl Test
```bash
# Test health endpoint
curl -H "Authorization: Bearer 29c63be0-06c1-4051-b3ef-034e46a6dfed" \
     http://localhost:8000/metrics/health

# Test metrics summary
curl -H "Authorization: Bearer 29c63be0-06c1-4051-b3ef-034e46a6dfed" \
     "http://localhost:8000/metrics/summary?since=24h"
```

---

## Available Test Scripts

### 1. test_analytics_quick.py
**Best for**: Quick verification, single environment

**Features**:
- ✅ Uses curl commands (no dependencies)
- ✅ Pretty formatted output
- ✅ Shows data summaries
- ✅ Tests 25+ endpoints
- ✅ Pass/fail statistics

**Usage**:
```bash
python3 test_analytics_quick.py
```

**Output**:
```
✅ GET /metrics/health
   └─ health: healthy
✅ GET /metrics/summary (last 24 hours)
   └─ total_queries: 250
   └─ success_rate: 98.5
   └─ avg_response_time_ms: 450.2
...
📊 Test Results Summary
Total Endpoints Tested: 25
✅ Passed: 25
❌ Failed: 0
Pass Rate: 100.0%
```

### 2. test_analytics.py
**Best for**: CI/CD pipelines, comprehensive testing

**Features**:
- ✅ Full Python test framework
- ✅ Detailed response validation
- ✅ Request/response logging
- ✅ Structured test results
- ✅ JSON export capability
- ✅ Timeout handling

**Usage**:
```bash
python3 test_analytics.py
```

**Requirements**:
```bash
pip install requests
# OR
pip install -r requirements.txt
```

### 3. test_analytics_curl.sh
**Best for**: Shell environments, automation

**Features**:
- ✅ Pure bash/curl
- ✅ Colored output
- ✅ Response parsing
- ✅ Cross-platform
- ✅ Minimal dependencies

**Usage**:
```bash
bash test_analytics_curl.sh
chmod +x test_analytics_curl.sh
./test_analytics_curl.sh
```

---

## What Gets Tested

### 1. Basic Endpoints (6 tests)
```
✅ GET /metrics/health              - System health check
✅ GET /metrics/summary             - Dashboard KPIs
✅ GET /metrics/queries             - Query analytics
✅ GET /metrics/performance         - Performance metrics
✅ GET /metrics/errors              - Error tracking
✅ GET /metrics/documents           - Document usage
```

### 2. Performance Analytics (2 tests)
```
✅ GET /analytics/performance/latency-distribution
✅ GET /analytics/performance/endpoint-performance
```

### 3. User Analytics (3 tests)
```
✅ GET /analytics/users/engagement
✅ GET /analytics/users/segments
✅ GET /analytics/users/retention
```

### 4. Security Analytics (3 tests)
```
✅ GET /analytics/security/events
✅ GET /analytics/security/threat-summary
✅ GET /analytics/security/suspicious-ips
```

### 5. Compliance Analytics (2 tests)
```
✅ GET /analytics/compliance/audit-log
✅ GET /analytics/compliance/data-retention-status
```

### 6. Conversion Analytics (1 test)
```
✅ GET /analytics/conversion/funnel
```

**Total: 17+ core endpoints tested**

---

## Expected Results

### Successful Test Output
```
✅ GET /metrics/health
   └─ health: healthy
   └─ analytics_enabled: true

✅ GET /metrics/summary (last 24 hours)
   └─ total_queries: 250
   └─ success_rate: 98.5
   └─ unique_users: 45

📊 Test Results Summary
Total Endpoints Tested: 25
✅ Passed: 25
❌ Failed: 0
Pass Rate: 100.0%

🎉 ALL TESTS PASSED!
✨ Advanced Analytics System is working correctly.
```

### What Each Endpoint Should Return

#### GET /metrics/health
```json
{
  "status": "success",
  "health": "healthy",
  "data": {
    "queries_last_hour": 50,
    "success_rate": 98.5,
    "avg_response_time_ms": 450,
    "active_users": 15,
    "analytics_enabled": true
  }
}
```

#### GET /metrics/summary?since=24h
```json
{
  "status": "success",
  "period": "24h",
  "data": {
    "total_queries": 1250,
    "success_rate": 98.5,
    "avg_response_time_ms": 450.2,
    "unique_users": 45,
    "cache_hit_rate": 35.2
  }
}
```

#### GET /metrics/queries?since=24h&limit=10
```json
{
  "status": "success",
  "period": "24h",
  "pagination": {
    "limit": 10,
    "offset": 0
  },
  "data": {
    "queries": [
      {
        "query_id": "...",
        "user_id": "user1",
        "question": "...",
        "response_time_ms": 450,
        "success": true
      }
    ]
  }
}
```

---

## Troubleshooting

### Problem: Connection Error
```
❌ GET /metrics/health
   Error: Cannot reach http://localhost:8000
```

**Solution**:
```bash
# Make sure API server is running
python3 api.py

# Check if port 8000 is available
lsof -i :8000

# If port is in use, kill the process
kill -9 <PID>
```

### Problem: Authentication Error
```
❌ GET /metrics/health
   Error: Invalid token
```

**Solution**:
- Verify token: `29c63be0-06c1-4051-b3ef-034e46a6dfed`
- Token should be valid admin token in database
- Check token format in header: `Authorization: Bearer <token>`

### Problem: No Data Returned
```
✅ GET /metrics/health
   But: All counters are 0
```

**Solution**:
- Queries haven't been executed yet
- Run some queries first: `POST /query`
- Wait a few seconds for data to be collected
- Check database exists: `ls -la chroma_db/analytics.db`

### Problem: Database Error
```
❌ Tests failing with database errors
```

**Solution**:
```bash
# Check database file
ls -lh GraphTalk/analytics.db

# Reset database
rm GraphTalk/analytics.db

# Restart API - database will be recreated
python3 api.py
```

### Problem: Module Not Found
```
ModuleNotFoundError: No module named 'analytics_core'
```

**Solution**:
```bash
# Make sure all analytics files exist
ls GraphTalk/analytics_*.py GraphTalk/advanced_*.py

# Check they're in the right directory
pwd  # Should be in GraphTalk or parent directory
```

---

## Interpreting Results

### Success Indicators
✅ All endpoints return HTTP 200  
✅ `"status": "success"` in responses  
✅ Data fields contain reasonable values  
✅ No error messages in responses  

### Warning Signs
⚠️ All metrics are 0 (no data collected yet)  
⚠️ Response times > 5000ms (performance issue)  
⚠️ Missing fields in response  
⚠️ Empty arrays for analytics data  

### Error Signs
❌ Connection refused  
❌ 401/403 authentication errors  
❌ 500 internal server errors  
❌ "analytics not available" message  

---

## Performance Baseline

### Expected Response Times
| Endpoint | Time | Notes |
|----------|------|-------|
| /metrics/health | <50ms | Fastest - cache |
| /metrics/summary | <100ms | Aggregated data |
| /metrics/queries | <200ms | Paginated |
| /analytics/users/engagement | <150ms | User data |
| /analytics/security/events | <200ms | Large dataset |
| /analytics/compliance/* | <300ms | Complex queries |

### Expected Data Sizes
| Metric | Size | After |
|--------|------|-------|
| Database | ~184KB | Initialization |
| Single query log | ~500B | Per query |
| Daily data | ~5-10MB | 1 day, 1000 QPS |

---

## Running in CI/CD

### GitHub Actions Example
```yaml
- name: Test Analytics System
  run: |
    cd GraphTalk
    python3 test_analytics_quick.py
```

### Jenkins Example
```groovy
stage('Test Analytics') {
    steps {
        dir('GraphTalk') {
            sh 'python3 test_analytics_quick.py'
        }
    }
}
```

### GitLab CI Example
```yaml
test_analytics:
  script:
    - cd GraphTalk
    - python3 test_analytics_quick.py
```

---

## Manual Testing Workflow

### 1. Start Fresh
```bash
# Kill existing server
pkill -f "python3 api.py"

# Remove old database
rm GraphTalk/analytics.db

# Start API server
cd GraphTalk
python3 api.py
```

### 2. Generate Test Data
```bash
# Make a test query (from another terminal)
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "test query"}'
```

### 3. Run Tests
```bash
# Test analytics
python3 test_analytics_quick.py
```

### 4. Verify Results
```bash
# Check database
ls -lh chroma_db/analytics.db

# Inspect data (optional)
sqlite3 chroma_db/analytics.db "SELECT COUNT(*) FROM query_analytics;"
```

---

## Advanced Testing

### Testing Specific Endpoint
```bash
curl -H "Authorization: Bearer 29c63be0-06c1-4051-b3ef-034e46a6dfed" \
     "http://localhost:8000/metrics/summary?since=24h" | python3 -m json.tool
```

### Testing with Different Time Ranges
```bash
# Last hour
curl -H "Authorization: Bearer 29c63be0-06c1-4051-b3ef-034e46a6dfed" \
     "http://localhost:8000/metrics/summary?since=1h"

# Last 7 days
curl -H "Authorization: Bearer 29c63be0-06c1-4051-b3ef-034e46a6dfed" \
     "http://localhost:8000/metrics/summary?since=7d"
```

### Testing Pagination
```bash
# Get first 10
curl -H "Authorization: Bearer 29c63be0-06c1-4051-b3ef-034e46a6dfed" \
     "http://localhost:8000/metrics/queries?limit=10&offset=0"

# Get next 10
curl -H "Authorization: Bearer 29c63be0-06c1-4051-b3ef-034e46a6dfed" \
     "http://localhost:8000/metrics/queries?limit=10&offset=10"
```

---

## Documentation

- `ANALYTICS_INTEGRATION_COMPLETE.md` - Full technical guide
- `ANALYTICS_QUICK_REFERENCE.md` - Quick API reference
- `REQUIREMENTS_ANALYSIS.md` - Dependencies info
- `DEPLOYMENT_READY.md` - Production checklist

---

## Support

**Issue**: Tests won't run  
**Check**:
1. `cd GraphTalk` directory
2. `python3 --version` (3.8+)
3. `curl --version` (any recent version)
4. `pip list | grep requests` (if using test_analytics.py)

**Issue**: Getting 401/403 errors  
**Check**:
1. Token in database: `SELECT COUNT(*) FROM users WHERE token='...'`
2. Token format correct in header
3. User is admin role

**Issue**: No data in analytics  
**Check**:
1. Run a test query first
2. Wait 2-3 seconds for collection
3. Check database file exists and has size > 184KB
4. Look at application logs for errors

---

## Success Criteria

You know the analytics system is working when:

1. ✅ `python3 test_analytics_quick.py` shows 100% pass rate
2. ✅ `/metrics/health` returns `"health": "healthy"`
3. ✅ `/metrics/summary` shows non-zero query counts
4. ✅ `/analytics/users/engagement` returns user data
5. ✅ `/analytics/security/events` tracks login attempts
6. ✅ Database file grows over time (ls -lh analytics.db)
7. ✅ Response times < 500ms for most endpoints
8. ✅ All authentication working with admin token

---

**Ready to test?** Run: `python3 test_analytics_quick.py`
