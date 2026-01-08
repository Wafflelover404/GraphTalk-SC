# Organization Isolation - Quick Start Guide

## What Was Done
✅ Your backend now enforces strict organization boundaries  
✅ Admins can ONLY see/manage their own organization's users and files  
✅ Cross-organization access attempts return 403 Forbidden  
✅ Automatic database migration (safe, no data loss)

## How to Test (5 minutes)

### Step 1: Start the Backend
```bash
cd /Users/wafflelover404/Documents/wikiai/graphtalk
python api.py
```
Wait for it to say "Uvicorn running on" - you should see migration messages in logs.

### Step 2: Run the Test Suite
In a new terminal:
```bash
cd /Users/wafflelover404/Documents/wikiai/graphtalk
python test_org_isolation.py
```

### Expected Output
```
[TEST] ORGANIZATION ISOLATION TEST SUITE
[TEST] --- Test 1: Create Organization A ---
[PASS] ✓ Organization A created
[PASS] ✓ User A1 registered in Org A
[PASS] ✓ Admin A sees only Org A users
[PASS] ✓ Admin B does NOT see user_a1 (isolation working)
[PASS] ✓ Admin B cannot delete user_a1 (403 Forbidden)
[SUMMARY] PASSED: 11
[SUMMARY] FAILED: 0
[SUMMARY] Success Rate: 100.0%
```

## What Changed in the Code

### User Management
```
Before: Admin sees ALL users in system
After:  Admin sees ONLY their organization's users
```

### User Deletion
```
Before: Admin can delete ANY user
After:  Admin can delete ONLY users in their organization
        (403 Forbidden if trying to delete from other org)
```

### User Editing
```
Before: Admin can edit ANY user
After:  Admin can edit ONLY users in their organization
        (403 Forbidden if trying to edit from other org)
```

### User Registration
```
Before: Admin registers user (org context unclear)
After:  Admin registers user → automatically assigned to admin's org
```

## Database Changes

The following tables were modified:

### users table
```
Added column: organization_id (TEXT)
- Links each user to their organization
- Auto-migration runs on startup (safe)
- Existing data preserved (NULL values)
```

### user_sessions table
Already had organization_id - now used correctly for context

## Security Features

✅ **Organization Isolation**
- Each user belongs to exactly one organization
- Admin can only manage their organization

✅ **Authorization Checks**
- Every admin action verifies organization match
- Returns 403 if user from different organization

✅ **Session Context**
- Organization ID carried in authenticated session
- Available at every API endpoint

✅ **Master Key Exception**
- System admin (master key) can still access everything
- For emergency administration only

## Verification

### Test Scenario 1: Admin A registers users
```bash
# Create org A with admin
POST /organizations/create_with_admin
  → admin_a created in org_a

# Admin A registers user
POST /register (as admin_a)
  → user_a1 created in org_a (same org as admin)
```

### Test Scenario 2: Admin B cannot see Admin A's users
```bash
# Admin B lists accounts
GET /accounts (as admin_b)
  → Returns only admin_b and their users
  → Does NOT return admin_a or their users ✓
```

### Test Scenario 3: Admin B cannot delete Admin A's users
```bash
# Admin B tries to delete user_a1
DELETE /user/delete?username=user_a1 (as admin_b)
  → Returns 403 Forbidden ✓
  → user_a1 is protected (different organization)
```

## Files Modified

| File | Change | Impact |
|------|--------|--------|
| `userdb.py` | Added organization_id column | Users now org-scoped |
| `api.py` | Updated 5 endpoints | Org isolation enforced |

## Files Created

| File | Purpose |
|------|---------|
| `ORG_ISOLATION_GUIDE.md` | Detailed technical docs |
| `ORG_ISOLATION_SUMMARY.md` | Executive summary |
| `IMPLEMENTATION_CHANGELOG.md` | Complete change log |
| `test_org_isolation.py` | Automated test suite |

## Common Questions

### Q: Will this break my existing users?
**A:** No. Auto-migration adds the new column safely. Existing users get NULL org_id (you can assign later if needed).

### Q: Can I still use the master key?
**A:** Yes. Master key access unchanged - it bypasses org checks for system admin purposes.

### Q: How do I assign users to organizations?
**A:** 
- **New users**: Via `/register` endpoint (auto-assigned to admin's org)
- **Existing users**: Via SQL: `UPDATE users SET organization_id = 'org_id' WHERE username = 'name'`

### Q: What if an admin doesn't have organization context?
**A:** They'll get 400 error "Organization context required" when trying to use org-dependent endpoints. Re-login via `/login` endpoint to fix.

### Q: Are files also organization-scoped?
**A:** Yes. Files already had org filtering in the code. Now properly enforced alongside users.

## Troubleshooting

### Admin sees no users in /accounts
```sql
-- Check if organization_id is set
SELECT username, organization_id FROM users WHERE username = 'admin_name';

-- If NULL, assign it
UPDATE users SET organization_id = 'correct_org_id' WHERE username = 'admin_name';
```

### Test fails with connection errors
- Make sure backend is running (`python api.py`)
- Check that port 9001 is available
- Look for migration errors in backend logs

### Database errors during startup
- Backup your database
- Delete the databases and start fresh
- Restore from backup if needed

## Next Steps

1. ✅ Run the test suite
2. ✅ Verify all tests pass
3. ✅ Check logs for any errors
4. ✅ Test in your UI (create orgs, register users)
5. ✅ Monitor for issues
6. ✅ Deploy with confidence

## Need More Details?

- **Technical Details**: Read `ORG_ISOLATION_GUIDE.md`
- **Change Summary**: Read `ORG_ISOLATION_SUMMARY.md`
- **All Changes**: Read `IMPLEMENTATION_CHANGELOG.md`
- **Run Tests**: `python test_org_isolation.py`

---

## Quick API Reference

### Create Organization with Admin
```bash
curl -X POST http://localhost:9001/organizations/create_with_admin \
  -H "Content-Type: application/json" \
  -d '{
    "organization_name": "My Company",
    "admin_username": "admin",
    "admin_password": "secure_password"
  }'
```

### List Users (Admin Only)
```bash
curl -X GET http://localhost:9001/accounts \
  -H "Authorization: Bearer $SESSION_TOKEN"
```
Returns only users in admin's organization.

### Register User (Admin Only)
```bash
curl -X POST http://localhost:9001/register \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "password123",
    "role": "user"
  }'
```
User is automatically assigned to admin's organization.

### Delete User (Admin Only)
```bash
curl -X DELETE "http://localhost:9001/user/delete?username=username" \
  -H "Authorization: Bearer $SESSION_TOKEN"
```
Returns 403 if user is from different organization.

---

**Status**: ✅ Ready to use  
**Last Updated**: December 11, 2025
