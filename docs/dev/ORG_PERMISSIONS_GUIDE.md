# Organization Permission Restrictions Guide

## Overview

This guide explains how GraphTalk implements organization-level permission restrictions to ensure complete data isolation between users and organizations. When a user performs search, file parsing, or any content access operation, the backend validates that the user belongs to the same organization as the requested resources.

## Architecture

### Key Components

1. **Organization Database** (`orgdb.py`)
   - Manages organizations and user-organization memberships
   - Provides verification functions for org access control

2. **Organization Security Module** (`org_security.py`)
   - Implements permission validation and enforcement
   - Provides helper functions for organization context management

3. **Vector Store (Chroma)** (`rag_api/chroma_utils.py`)
   - Stores documents with organization_id metadata
   - Filters search results by organization during retrieval

4. **Document Store** (`rag_api/db_utils.py`)
   - Stores file content with organization_id association
   - Retrieves files with organization filtering

## Permission Model

### Organization Structure

```
Organization (tenant)
├── Users (with roles: owner, admin, member)
└── Documents (with organization_id association)
```

### User Roles in Organization

- **Owner**: Full access to organization, can manage users and documents
- **Admin**: Can manage documents, upload files, manage users
- **Member**: Can access documents they have file-level permissions for

### Tenant Isolation

Users can only:
- Search documents from their organization
- Access file content from their organization
- Retrieve chat history from their organization
- View documents list from their organization

Cross-organization access attempts are blocked with:
- HTTP 403 Forbidden responses
- Security event logging
- Warning messages in application logs

## Implementation Details

### 1. User-Organization Context

Every authenticated user has an organization_id in their session:

```python
# User tuple structure:
# (id, username, password_hash, role, access_token, allowed_files, last_login, organization_id)

organization_id = user[-1]  # Last element in user tuple
```

### 2. Organization Validation

The `org_security.py` module provides key validation functions:

```python
# Verify user belongs to organization
await require_organization_access(username, organization_id)

# Check if user is admin in organization
await check_organization_admin(username, organization_id)

# Verify document belongs to user's organization
await check_document_organization_access(
    username, 
    user_org_id, 
    document_org_id
)
```

### 3. Search with Organization Filtering

When searching documents, only organization-specific embeddings are queried:

```python
# In search_documents():
if organization_id:
    all_docs = vectorstore.get(where={"organization_id": organization_id})
else:
    all_docs = vectorstore.get(where={"filename": {"$ne": ""}})
```

Every embedding in Chroma includes `organization_id` in metadata:

```python
# When indexing documents:
for split in splits:
    split.metadata['organization_id'] = organization_id
vectorstore.add_documents(splits)
```

### 4. File Content Retrieval

File access is gated by organization:

```python
# Retrieve file only if it belongs to user's organization
content = get_file_content_by_filename(
    filename, 
    organization_id=organization_id
)
```

## API Endpoints with Organization Enforcement

### Search Endpoints

#### `POST /query`
- **Requirement**: User must have organization_id in session
- **Behavior**: Only searches documents from user's organization
- **Error**: Returns 400 if no organization context

#### `POST /chat`
- **Requirement**: User must have organization_id in session
- **Behavior**: Chat history and search within organization only
- **Error**: Returns 400 if no organization context

#### `WebSocket /ws/query`
- **Requirement**: User must have organization_id in session
- **Behavior**: Real-time search within organization
- **Error**: Closes connection with code 1008 if no org context

### File Access Endpoints

#### `GET /files/content/{filename}`
- **Organization Filtering**: ✅ Enforced
- **Check**: Retrieves file only if it belongs to user's organization
- **Error**: Returns 404 if file not found in org

#### `GET /files/list`
- **Organization Filtering**: ✅ Enforced
- **Check**: Returns only documents from user's organization
- **Query**: `get_all_documents(organization_id=organization_id)`

#### `POST /upload`
- **Organization Tagging**: ✅ Enforced
- **Behavior**: Files uploaded tagged with current organization_id
- **Indexing**: Documents indexed with organization_id metadata

#### `DELETE /files/delete_by_fileid`
- **Organization Filtering**: ✅ Enforced
- **Check**: Deletes only from user's organization
- **Query**: `delete_doc_from_chroma(file_id, organization_id=organization_id)`

### Quiz Endpoints

#### `POST /quiz/{filename}`
- **Organization Filtering**: ✅ Enforced via filename lookup
- **Behavior**: Quiz generated for files in user's organization

## Database Schema

### Document Store

```sql
CREATE TABLE document_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT,
    content BLOB,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    organization_id TEXT  -- Associates file with organization
)
```

### Chroma Vector Store Metadata

Each document chunk includes:
```python
metadata = {
    'filename': str,
    'file_id': int,
    'organization_id': str,  # Critical for isolation
    'chunk_start': int,
    'chunk_end': int,
    'token_count': int,
    # ... other fields
}
```

## Security Features

### 1. Cross-Organization Access Prevention

Any attempt to access a document from a different organization:
- Logs security event with `severity: "medium"`
- Returns HTTP 403 Forbidden
- Records user ID, IP address, and attempted access details

### 2. Query Embedding Isolation

Search queries only match embeddings from the user's organization:
- Query embedding is generated from preprocessed search text
- Similarity matching only occurs within organization_id filtered results
- Prevents data leakage across tenant boundaries

### 3. File Content Isolation

File retrieval enforces organization association:
- Database query includes organization_id condition
- Returns None if file doesn't belong to organization
- Returns 404 error to client

### 4. Session-Based Organization Context

Organization context is embedded in user session:
- Cannot be bypassed without proper authentication
- Persists across requests
- Verified on every protected endpoint

## Implementation Checklist

The following have been implemented:

- [x] Organization creation and membership management
- [x] Organization database schema with user roles
- [x] User-organization association in authentication
- [x] Organization ID extraction from user sessions
- [x] Organization validation middleware (`org_security.py`)
- [x] Search filtering by organization_id
- [x] File content retrieval with org filtering
- [x] Document upload with organization tagging
- [x] Chroma vectorstore filtering by organization
- [x] WebSocket endpoint organization enforcement
- [x] Security event logging for unauthorized access
- [x] File listing with organization filtering
- [x] File deletion with organization verification

## Testing Organization Isolation

### Test Scenarios

1. **User from Org A tries to access Org B's documents**
   - Expected: 403 Forbidden or 404 Not Found
   - Logged: Security event

2. **User from Org A searches with Org B's document context**
   - Expected: No results from Org B
   - Verified: Only Org A embeddings compared

3. **Multiple users from same org access documents**
   - Expected: All can access organization's files
   - File access: Governed by individual file permissions

4. **Document upload assigns correct organization**
   - Expected: File stored with org_id
   - Verified: File not accessible from other orgs

5. **Organization admin can manage org documents**
   - Expected: Full access to org documents
   - Deletion: Only org documents deleted

## Configuration

### Environment Variables

```bash
# No special configuration needed - organization context is determined by user session
# Organization ID flows through all operations via user authentication
```

### Default Behavior

- **New users**: Must be explicitly added to organization via `create_organization_membership()`
- **File upload**: Automatically tagged with user's current organization
- **Search queries**: Automatically filtered by organization context
- **Legacy documents**: May have NULL organization_id; consider migration if needed

## Migration Guide

For existing systems without organization_id:

### Step 1: Backfill Organization IDs

```python
# For each organization, update all its documents:
async def migrate_documents_to_org(org_id: str, document_ids: List[int]):
    conn = get_db_connection()
    for doc_id in document_ids:
        conn.execute(
            'UPDATE document_store SET organization_id = ? WHERE id = ?',
            (org_id, doc_id)
        )
    conn.commit()
```

### Step 2: Reindex Chroma with Organization Metadata

```python
# Reindex all documents with organization_id:
from rag_api.chroma_utils import reindex_documents

await reindex_documents(documents_dir, file_paths)
```

### Step 3: Verify Organization Assignments

```python
# Ensure all documents have organization_id:
documents = get_all_documents()
unassigned = [d for d in documents if not d.get('organization_id')]
# Assign to appropriate organization
```

## Troubleshooting

### Issue: Users can't find documents after org restriction

**Solution**: Verify organization_id is set in both:
1. Database document_store table
2. Chroma vector store metadata

### Issue: 404 on file retrieval for existing files

**Solution**: Check that file's organization_id matches user's org:
```sql
SELECT organization_id FROM document_store WHERE filename = ?
```

### Issue: Search returns no results in organization

**Solution**: 
1. Verify documents are indexed with organization_id metadata
2. Check organization_id is correctly passed to search_documents()
3. Ensure user's organization_id is set in session

### Issue: Cross-organization access not blocked

**Solution**: Verify `enforce_organization_context()` is called in all endpoints

## Related Files

- **Organization Management**: `orgdb.py`
- **Security Utilities**: `org_security.py`
- **Vector Search**: `rag_api/chroma_utils.py`
- **File Storage**: `rag_api/db_utils.py`
- **API Endpoints**: `api.py`
- **RAG Security**: `rag_security.py`

## Summary

GraphTalk implements complete organization-level isolation through:

1. **Tenant Association**: Every document tagged with organization_id
2. **Query Filtering**: Only search organization-specific embeddings
3. **Access Control**: Every API endpoint validates organization membership
4. **Permission Enforcement**: Users cannot access cross-organization data
5. **Logging**: Security events logged for unauthorized access attempts

This ensures that data from different organizations is completely isolated and users cannot access content outside their organization's scope.
