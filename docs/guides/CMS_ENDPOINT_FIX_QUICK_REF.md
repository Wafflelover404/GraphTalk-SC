# CMS Endpoint Fix - Quick Reference

## Problem Summary
❌ **422 Unprocessable Entity** → Authentication mismatch (fixed)
❌ **500 Internal Server Error** → Database not initialized (fixed)

## Root Causes
1. Backend expected `x-cms-password` header, frontend sent `Authorization: Bearer`
2. Database path was hardcoded relative path, resolved from wrong directory

## Quick Fix Checklist

### ✅ Done - What Was Fixed

**1. Authentication (landing-pages-api/routers/cms.py)**
- Added Bearer token support
- Maintained backward compatibility with custom header
- Now accepts both: Bearer tokens and x-cms-password header

**2. Database Path (landing-pages-api/database.py & routers/cms.py)**
- Added dynamic path resolution with `get_database_path()`
- Updated all 9 database connections in CMS router
- Database path resolved at runtime from DATABASE_URL env var

### 🚀 To Deploy

```bash
# 1. Verify environment variables
echo $CMS_PASSWORD
echo $MASTER_CMS_TOKEN

# 2. Restart API
cd /Users/wafflelover404/Documents/wikiai/graphtalk
python3 api.py

# 3. Test endpoint
curl -H "Authorization: Bearer AdminTestPassword1423" \
  http://127.0.0.1:9001/api/cms/content/stats

# 4. Check logs for:
#    - "Initializing database at /full/path/to/landing_pages.db"
#    - "Database initialized successfully"
```

### 📊 Expected Results After Fix

| Endpoint | Method | Status | Reason |
|----------|--------|--------|--------|
| /api/cms/content/stats | GET | 200 ✅ | Returns content statistics |
| /api/cms/system/health | GET | 200 ✅ | Returns system health |
| /api/cms/blog/posts | GET | 200 ✅ | Returns blog posts |
| (without auth) | GET | 401 ✅ | Unauthorized |

### 🔧 If Still Having Issues

**401 Unauthorized:**
```bash
# Check token is correct
echo $MASTER_CMS_TOKEN | head -c 20  # Should print: U4XjElktw2jFG5duv1Dp

# Check header format
curl -H "Authorization: Bearer YOUR_TOKEN" http://127.0.0.1:9001/api/cms/content/stats
```

**500 Error - Database not found:**
```bash
# Check database exists
ls -la graphtalk/landing-pages-api/landing_pages.db

# Check DATABASE_URL is set
echo $DATABASE_URL

# Delete old DB to force re-initialization
rm graphtalk/landing-pages-api/landing_pages.db
# Then restart API
```

**Still getting errors:**
```bash
# Check API logs for exact error
grep -i "error\|database\|init" /path/to/api/logs.txt

# Manually init database
python3 -c "
import asyncio
import sys
sys.path.insert(0, 'graphtalk/landing-pages-api')
from database import init_database
asyncio.run(init_database())
"
```

### 📝 Files Changed

| File | Changes |
|------|---------|
| landing-pages-api/routers/cms.py | +Bearer token support, +dynamic DB path |
| landing-pages-api/database.py | +get_database_path() function |
| api.py | (no changes - already correct) |

### 🧪 Test Script
```bash
python3 /Users/wafflelover404/Documents/wikiai/graphtalk/test_cms_fix.py
```

### 📚 Full Documentation
See: `/Users/wafflelover404/Documents/wikiai/graphtalk/CMS_ENDPOINT_FIX.md`

---

**Status:** ✅ All fixes applied and tested
**Last Updated:** Feb 8, 2026
