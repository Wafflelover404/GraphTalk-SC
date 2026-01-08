# Organization Permission Restrictions - Quick Reference

## What Was Implemented

✅ **Complete Organization-Level Data Isolation** - Users can only access documents and perform searches within their organization.

## Key Changes

### 1. New Organization Security Module (`org_security.py`)

Functions for validating organization access:

```python
# Verify user belongs to organization
await require_organization_access(username, organization_id)

# Enforce org context (raises exception if missing)
organization_id = enforce_organization_context(user_tuple, required=True)

# Check if user is admin in org
await check_organization_admin(username, org_id)

# Verify document belongs to user's organization
await check_document_organization_access(username, user_org_id, doc_org_id)
```

### 2. Enhanced Organization Database (`orgdb.py`)

New verification functions:

```python
# Check if user is member of organization
await verify_user_in_organization(username, organization_id)

# Get organization by ID
await get_organization_by_id(org_id)

# Get user's role in organization
await get_user_organization_role(username, org_id)
```

### 3. API Endpoints Updated with Organization Enforcement

| Endpoint | Organization Check | Type |
|----------|-------------------|------|
| POST /query | ✅ Required org_id | Search |
| POST /chat | ✅ Required org_id | Chat |
| WebSocket /ws/query | ✅ Required org_id | Real-time |
| GET /files/content/{filename} | ✅ Filter by org_id | File Access |
| GET /files/list | ✅ Filter by org_id | Document List |
| POST /upload | ✅ Tag with org_id | File Upload |
| DELETE /files/delete_by_fileid | ✅ Filter by org_id | File Delete |

### 4. Vector Store Organization Filtering (`chroma_utils.py`)

Search now filters by organization:

```python
# Before (would search all docs):
all_docs = vectorstore.get(where={"filename": {"$ne": ""}})

# After (filters by organization):
if organization_id:
    all_docs = vectorstore.get(where={"organization_id": organization_id})
```

### 5. Document Metadata Tagging

All documents indexed include organization_id:

```python
split.metadata['organization_id'] = organization_id
vectorstore.add_documents(splits)  # Filters applied on retrieval
```

## How It Works

### User Session Flow

1. User authenticates → Session created with organization_id
2. User makes API request → Organization_id extracted from session
3. Operation validated → User must belong to organization
4. Data queried → Only organization-specific data returned

### Search Process

1. User submits query → Organization_id verified
2. Query embedded → Creates semantic vector
3. Chroma filtered → Only searches organization's documents
4. Results returned → Only from user's organization

### File Access Process

1. User requests file → Organization_id extracted
2. Database queried → `SELECT ... WHERE org_id = user_org_id`
3. File found → Content returned only if org_id matches
4. File not found → 404 error (blocks info leakage)

## Security Features

✅ **Cross-Organization Access Prevention**
- Any cross-org access attempt returns 403 Forbidden
- Security events logged with user ID, IP, details

✅ **Query Embedding Isolation**
- Search queries only match embeddings from same organization
- Prevents data leakage across tenant boundaries

✅ **File Content Isolation**
- Database query includes organization_id condition
- Returns None if file doesn't belong to organization

✅ **Session-Based Context**
- Organization context embedded in user session
- Cannot be bypassed without proper authentication

## Example Usage

### Checking Organization Access

```python
from org_security import enforce_organization_context, require_organization_access

@app.post("/my-endpoint")
async def my_endpoint(user = Depends(get_current_user)):
    # Get and enforce organization context
    organization_id = enforce_organization_context(user, required=True)
    
    # Verify user has access
    await require_organization_access(user[1], organization_id)
    
    # Now safely use organization_id in queries
    documents = get_all_documents(organization_id=organization_id)
    return documents
```

### Searching with Organization Filtering

```python
from rag_security import get_relevant_files_for_query

# Search automatically filters by organization
files = await get_relevant_files_for_query(
    username=user_id,
    query=search_query,
    organization_id=organization_id  # Only searches this org's docs
)
```

### Retrieving File Content

```python
from rag_api.db_utils import get_file_content_by_filename

# File retrieved only if it belongs to organization
content = get_file_content_by_filename(
    filename=filename,
    organization_id=organization_id  # Filters by organization
)

if content is None:
    # File either doesn't exist or belongs to different org
    raise HTTPException(status_code=404, detail="File not found")
```

## Database Queries

### Get organization documents

```sql
-- All documents in organization
SELECT * FROM document_store 
WHERE organization_id = ?

-- Single file in organization
SELECT content FROM document_store 
WHERE filename = ? AND organization_id = ?
```

### Get user's organizations

```sql
-- All organizations user belongs to
SELECT o.* FROM organizations o
JOIN organization_users ou ON o.id = ou.organization_id
WHERE ou.username = ? AND ou.status = 'active'
```

### Verify organization membership

```sql
-- Check if user is in organization
SELECT 1 FROM organization_users
WHERE username = ? AND organization_id = ? AND status = 'active'
```

## Testing the Implementation

### Test 1: Same organization access ✅

```python
# User A and User B both in Organization 1
# Both should access same documents
documents = get_all_documents(organization_id=org1_id)
assert user_a_can_access(documents)
assert user_b_can_access(documents)
```

### Test 2: Cross-organization blocking ✅

```python
# User A in Org 1, trying to access Org 2 document
try:
    await require_organization_access(user_a, org_2_id)
    assert False, "Should have raised exception"
except OrganizationPermissionError:
    pass  # Expected
```

### Test 3: Search isolation ✅

```python
# User in Org 1 searches
results = search_documents(query, organization_id=org_1_id)
# Verify no Org 2 documents in results
for doc in results:
    assert doc.metadata['organization_id'] == org_1_id
```

### Test 4: File content isolation ✅

```python
# User in Org A tries to get file from Org B
content = get_file_content_by_filename(
    "file.pdf",
    organization_id=org_a_id  # User's org
)
# File stored in Org B is not found
assert content is None  # Returns None, not content
```

## Troubleshooting

### "Organization context required" Error

**Cause**: User session doesn't have organization_id

**Fix**: Ensure user was created with organization membership:
```python
await create_organization_membership(org_id, username, role='member')
```

### "User does not have access to this organization" Error

**Cause**: User trying to access org they don't belong to

**Fix**: Add user to organization:
```python
await create_organization_membership(target_org_id, username)
```

### Files not found in organization

**Cause**: Files may not have organization_id tagged

**Fix**: Verify file organization assignment:
```sql
SELECT id, filename, organization_id FROM document_store WHERE filename = ?
```

### Search returns no results

**Cause**: Documents not indexed with organization_id

**Fix**: Reindex documents with organization:
```python
index_document_to_chroma(file_path, file_id, organization_id=org_id)
```

## Documentation Files

- **Full Guide**: `ORG_PERMISSIONS_GUIDE.md`
- **Quick Reference**: This file
- **Security Module**: `org_security.py`
- **Organization DB**: `orgdb.py`
- **RAG Security**: `rag_security.py`

## Summary

Organization-level permissions are now enforced across all user-facing operations:

- ✅ Search filtered by organization
- ✅ File access controlled by organization
- ✅ Document upload tagged with organization
- ✅ Chat isolated to organization
- ✅ Cross-organization access blocked
- ✅ Security events logged

Users can only access documents from their own organization. Complete data isolation is maintained between organizations.
