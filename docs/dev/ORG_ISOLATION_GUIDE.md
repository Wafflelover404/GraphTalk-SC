# Organization-Level Isolation Implementation Guide

## Overview
This document describes the multi-tenant organization isolation that has been implemented in the GraphTalk backend. Each admin user can now only see and manage users and files within their own organization.

## What Was Changed

### 1. Database Schema Updates (`userdb.py`)
- **Added `organization_id` column to `users` table**
  - This column stores the organization ID each user belongs to
  - Backfill migration runs automatically on startup
  
- **Updated `create_user()` function**
  - Now accepts `organization_id` parameter
  - All new users are created with their organization context

- **Updated `list_users()` function**
  - Now accepts optional `organization_id` parameter
  - If `organization_id` is provided, only returns users in that organization
  - If no `organization_id` is provided, returns all users (backward compatible)

### 2. API Endpoint Updates (`api.py`)

#### `/register` Endpoint (Admin-Only User Registration)
- **Before**: Registered users without organization context
- **After**: 
  - When admin registers a user, the new user is automatically assigned to the admin's organization
  - Admin can only register users in their own organization
  - Master key can register users without organization context

#### `/organizations/create_with_admin` Endpoint (Organization Setup)
- **Before**: Created org, then created admin separately
- **After**:
  - Creates organization first
  - Creates admin user with `organization_id` set to the new org
  - Admin is automatically part of the organization

#### `/accounts` Endpoint (List Users - Admin Only)
- **Before**: Returned ALL users in the system
- **After**: 
  - Returns ONLY users in the admin's organization
  - Raises 400 error if admin doesn't have organization context
  - Example: Admin from Org A cannot see users from Org B

#### `/user/delete` Endpoint (Delete User - Admin Only)
- **Before**: Could delete any user in the system
- **After**:
  - Admin can ONLY delete users in their own organization
  - Attempting to delete a user from another org raises 403 Forbidden
  - Master key retains ability to delete any user

#### `/user/edit` Endpoint (Edit User - Admin Only)
- **Before**: Could edit any user in the system
- **After**:
  - Admin can ONLY edit users in their own organization
  - Attempting to edit a user from another org raises 403 Forbidden
  - Master key retains ability to edit any user

### 3. File Access Controls (`rag_api/db_utils.py`)
- **`get_all_documents()` function already had `organization_id` filtering**
  - No changes needed here
  - When called with `organization_id`, returns only org's documents

- **`/files/list` endpoint already filters by organization**
  - Uses `get_all_documents(organization_id=organization_id)`
  - Admins can only see files in their organization

## Security Implementation

### Organization Context Extraction
The `_get_active_org_id()` helper function extracts organization context from the authenticated user:
```python
def _get_active_org_id(user_tuple):
    """Extract organization_id from the authenticated user session tuple."""
    try:
        if user_tuple and len(user_tuple) >= 11:
            return user_tuple[-1]  # organization_id is the last element
    except Exception:
        pass
    return None
```

### Authorization Checks
All admin-only endpoints now perform these checks:
1. Verify user is admin (`current_user[3] == "admin"`)
2. Extract organization_id from admin's session
3. Get organization_id of the target resource (user/file)
4. Compare: if they don't match, raise 403 Forbidden

### Master Key Exception
- Master key holders (via `secrets.toml`) can bypass organization checks
- This is intentional for system administration
- Used in `/register` and `/user/delete` endpoints

## Testing Checklist

### Scenario 1: Create Two Organizations
```bash
# Create Org A with Admin A
POST /organizations/create_with_admin
{
  "organization_name": "Company A",
  "admin_username": "admin_a",
  "admin_password": "password123"
}
# Returns: session_token_a

# Create Org B with Admin B
POST /organizations/create_with_admin
{
  "organization_name": "Company B",
  "admin_username": "admin_b",
  "admin_password": "password456"
}
# Returns: session_token_b
```

### Scenario 2: Isolation Test - User Management
```bash
# Admin A registers User A1 in their org
POST /register (Bearer: session_token_a)
{
  "username": "user_a1",
  "password": "pass1",
  "role": "user"
}
# Status: 201 (success)

# Admin B tries to see Admin A's users
GET /accounts (Bearer: session_token_b)
# Expected: Only shows users from Org B (empty or just admin_b)
# Does NOT show user_a1

# Admin B tries to delete user_a1
DELETE /user/delete?username=user_a1 (Bearer: session_token_b)
# Expected: 403 Forbidden - "Cannot delete users from other organizations."
```

### Scenario 3: Isolation Test - File Management
```bash
# Admin A uploads file_a.pdf
POST /upload (Bearer: session_token_a)
# File gets organization_id = org_a_id

# Admin B lists files
GET /files/list (Bearer: session_token_b)
# Expected: Does NOT show file_a.pdf (only shows org B's files)

# Admin B tries to delete file_a.pdf
DELETE /files/delete_by_filename?filename=file_a.pdf (Bearer: session_token_b)
# Expected: File not found (because it doesn't exist in org B's scope)
```

### Scenario 4: Backward Compatibility
```bash
# Master key can still see all users
GET /accounts (with no auth or master key)
# If master key provided, might show all users depending on implementation

# Master key can delete any user
DELETE /user/delete?username=user_a1 (with master key)
# Status: 204 (success) - deletes even though it's from Org A
```

## Database State After Implementation

### User Table Structure
```
users:
├── id (PK)
├── username (UNIQUE)
├── password_hash
├── role (user|admin)
├── access_token
├── allowed_files (comma-separated)
├── last_login
└── organization_id ← NEW FIELD (points to organizations.id)
```

### User Sessions Table Structure
```
user_sessions:
├── session_id (PK)
├── username (FK to users)
├── created_at
├── last_activity
├── expires_at
├── is_active
└── organization_id ← Already existed (used for context)
```

## Migration Instructions

If you have an existing database:

1. **Backup your database files**:
   ```bash
   cp users.db users.db.backup
   cp organizations.db organizations.db.backup
   cp rag_app.db rag_app.db.backup
   ```

2. **Restart the backend**:
   - The `init_db()` function in `userdb.py` will automatically add the `organization_id` column
   - No data loss occurs (backfill/upgrade is safe)

3. **Assign existing users to organizations** (if you have multiple orgs):
   ```python
   # This must be done manually or via a migration script
   # Example: UPDATE users SET organization_id = 'org_id_here' WHERE username = 'admin_a'
   ```

4. **Test thoroughly** before deployment

## Monitoring & Logging

All changes are logged with:
- User ID involved
- Admin ID performing the action
- Organization context
- Timestamps
- Success/failure status

Check logs for:
```
- "User {username} logged in successfully with session_id"
- "Cannot delete users from other organizations" (403 errors)
- "/accounts endpoint called by admin {username}"
```

## Known Limitations

1. **Existing users without organization_id**: 
   - Users created before this update won't have `organization_id`
   - They need to be manually assigned or migrated
   - Consider running a migration script to assign them to a default org

2. **Master key bypass**: 
   - Master key holders can still access all organizations
   - This is intentional but should be secured properly in `secrets.toml`

3. **File-user relationship**:
   - Users can be assigned files via `allowed_files`
   - These files must belong to the same organization as the user
   - No explicit check prevents assigning files from other orgs (TODO)

## Future Improvements

1. **User invitations**: Implement org-level user invitations
2. **Role-based access control**: Expand beyond admin/user to member/viewer roles
3. **Audit logging**: Track all admin actions for compliance
4. **File quotas**: Limit org storage and file count
5. **API keys**: Create org-scoped API keys for service-to-service auth
6. **Workspace management**: Allow admins to create workspace within orgs

## Support & Troubleshooting

### Issue: Admin A can see all users
- **Cause**: Admin was created before migration or `organization_id` is NULL
- **Fix**: `UPDATE users SET organization_id = 'org_a_id' WHERE username = 'admin_a'`

### Issue: Files are missing after migration
- **Cause**: File `organization_id` is NULL in document_store
- **Fix**: `UPDATE document_store SET organization_id = 'org_id' WHERE organization_id IS NULL`

### Issue: Registration fails with "Organization context required"
- **Cause**: Admin's session doesn't have `organization_id` (old token)
- **Fix**: Re-login with new session (use `/login` endpoint)

---
**Document Version**: 1.0  
**Last Updated**: 2025-12-11  
**Author**: AI Assistant (GitHub Copilot)
