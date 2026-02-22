# CMS Endpoint Authentication & Database Fix

## Issues Resolved

### Issue 1: Authentication Mismatch (422 Unprocessable Entity)
The CMS endpoints were returning `422 Unprocessable Entity` errors when called from the wiki-ai-react frontend because of an authentication mismatch:

- **Backend** (`landing-pages-api/routers/cms.py`): Expected a custom header `x-cms-password`
- **Frontend** (`wiki-ai-react/components/cms-*.tsx`): Sending `Authorization: Bearer {token}` header

### Issue 2: Database Not Initialized (500 Internal Server Error)
After fixing authentication, the CMS endpoints returned `500 Internal Server Error` with `sqlite3.OperationalError: no such table: blog_posts`. This was caused by:

- Database path was hardcoded to relative path `"landing_pages.db"`
- When called from the main API (running from `/graphtalk/` directory), the path resolution was incorrect
- Database initialization was trying to connect to wrong location

## Solutions Implemented

### Fix 1: Backend Authentication (CMS Router)

**File:** `/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/routers/cms.py`

**Changes:**
- Added imports: `HTTPBearer`, `HTTPAuthorizationCredentials`
- Updated to support `MASTER_CMS_TOKEN` environment variable
- Rewrote `verify_cms_password` function to support both authentication methods

**New `verify_cms_password` function:**
```python
async def verify_cms_password(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_cms_password: Optional[str] = Header(None)
):
    """
    Verify CMS authentication via either:
    1. Bearer token (for main API integration)
    2. x-cms-password header (for direct CMS calls)
    """
    # Check Bearer token first (main API integration)
    if credentials:
        if credentials.credentials == CMS_TOKEN or credentials.credentials == CMS_PASSWORD:
            return True
        raise HTTPException(status_code=401, detail="Invalid CMS token")
    
    # Fall back to custom header for direct CMS calls
    if x_cms_password:
        if x_cms_password == CMS_PASSWORD:
            return True
        raise HTTPException(status_code=401, detail="Invalid CMS password")
    
    # No valid authentication provided
    raise HTTPException(status_code=401, detail="Missing authentication credentials")
```

**Authentication Priority:**
1. **Bearer Token** (main API) - Supports both `MASTER_CMS_TOKEN` and `CMS_PASSWORD`
2. **Custom Header** (backward compatibility) - Supports `x-cms-password` header
3. **Error** - Returns 401 Unauthorized if neither is provided

### Fix 2: Database Path Resolution

**File:** `/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/database.py`

**Changes:**
- Added `get_database_path()` function for dynamic path resolution
- Updated all database connection calls to use `get_database_path()` instead of hardcoded paths
- Database path is now resolved at runtime from `DATABASE_URL` environment variable

**New approach:**
```python
def get_database_path():
    """Get the database path from environment or use default"""
    return os.getenv("DATABASE_URL", 
        os.path.join(os.path.dirname(__file__), "landing_pages.db"))

async def init_database():
    """Initialize all database tables"""
    db_path = get_database_path()
    logger.info(f"Initializing database at {db_path}...")
    async with aiosqlite.connect(db_path) as db:
        # ... table creation code ...
```

### Fix 3: CMS Router Database Connections

**File:** `/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/routers/cms.py`

**Changes:**
- Added import for `get_database_path` from database module
- Replaced all 9 instances of `aiosqlite.connect("landing_pages.db")` with `aiosqlite.connect(get_database_path())`
- Now all CMS endpoints use the correct database path

## Frontend Configuration (Already Correct)

The frontend components are properly configured:

- **cms-dashboard.tsx**: Uses `getCmsEndpointUrl("/content/stats")` with Bearer token
- **cms-login.tsx**: Validates token with Bearer authentication
- **cms-content-manager.tsx**: Uses `getCmsEndpointUrl()` for all calls
- **config.ts**: `getCmsEndpointUrl()` helper constructs proper URLs with port 9001

All frontend calls correctly send: `Authorization: Bearer ${token}`

## Affected Endpoints - Now Working

All CMS endpoints now support Bearer token authentication and use correct database path:

### Content Management
- `GET /api/cms/content/stats` ✅
- `GET /api/cms/system/health` ✅
- `GET /api/cms/blog/posts` ✅
- `POST /api/cms/blog/posts` ✅
- `PUT /api/cms/blog/posts/{id}` ✅
- `DELETE /api/cms/blog/posts/{id}` ✅

### Help Articles
- `POST /api/cms/help/articles` ✅
- `PUT /api/cms/help/articles/{id}` ✅
- `DELETE /api/cms/help/articles/{id}` ✅

### Media Management
- `POST /api/cms/media/upload` ✅
- `GET /api/cms/media/{filename}` ✅
- `DELETE /api/cms/media/{filename}` ✅

## Environment Variables Required

Ensure these are set in `graphtalk/landing-pages-api/.env`:
```
CMS_PASSWORD=AdminTestPassword1423
MASTER_CMS_TOKEN=AdminTestPassword1423
DATABASE_URL=/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/landing_pages.db
```

The main `api.py` sets the `DATABASE_URL` environment variable before importing CMS modules:
```python
cms_db_path = os.path.join(os.path.dirname(__file__), 'landing-pages-api', 'landing_pages.db')
os.environ['DATABASE_URL'] = cms_db_path
```

## Testing

Use the provided test script:
```bash
cd /Users/wafflelover404/Documents/wikiai/graphtalk
python3 test_cms_fix.py
```

This tests:
1. ✅ Bearer token authentication
2. ✅ Custom header authentication (backward compatibility)
3. ✅ Multiple CMS endpoints

## Backward Compatibility

✅ **Maintained**:
- Direct CMS API calls using `x-cms-password` header still work
- Existing test scripts using custom headers unaffected
- External integrations unchanged

## Deployment Steps

1. **Verify environment variables are set correctly**
   ```bash
   echo $CMS_PASSWORD
   echo $MASTER_CMS_TOKEN
   echo $DATABASE_URL
   ```

2. **Restart the GraphTalk API server:**
   ```bash
   cd /Users/wafflelover404/Documents/wikiai/graphtalk
   python3 api.py
   ```

3. **Test the endpoint:**
   ```bash
   curl -H "Authorization: Bearer AdminTestPassword1423" \
     http://127.0.0.1:9001/api/cms/content/stats
   ```

4. **Verify frontend works:**
   - Open wiki-ai-react CMS dashboard
   - Should see content statistics without errors
   - No more 422 or 500 errors

## Files Modified

1. `landing-pages-api/routers/cms.py`
   - Updated authentication mechanism
   - Fixed database path resolution
   
2. `landing-pages-api/database.py`
   - Added `get_database_path()` function
   - Updated all connection calls to use dynamic paths

3. `api.py` (no changes needed - already correct)
   - Environment variable setup works properly
   - Startup initialization calls `init_cms_database()`

## Troubleshooting

### Still getting 500 error?
- Check database path: `ls -la graphtalk/landing-pages-api/landing_pages.db`
- Verify `DATABASE_URL` environment variable is set: `echo $DATABASE_URL`
- Check API logs for the exact error location

### Still getting 401 error?
- Verify token matches: `echo $MASTER_CMS_TOKEN`
- Check header format: `Authorization: Bearer {token}`
- Ensure CMS_PASSWORD and MASTER_CMS_TOKEN are set in `.env`

### Database tables still missing?
- Delete old database: `rm graphtalk/landing-pages-api/landing_pages.db`
- Restart API - will recreate with new path
- Check logs for initialization messages

## Related Documentation
- [CMS Integration Status](./CMS_INTEGRATION_STATUS.md)
- [Frontend-Backend Integration](../wiki-ai-react/HARDCODED_URLS_FIX.md)
- [GraphTalk Dashboard API Manifesto](./GRAPHTALK_DASHBOARD_API_MANIFESTO.md)
