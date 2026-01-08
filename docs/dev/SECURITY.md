# 🔒 Secure RAG API - Security Features

## 🛡️ **Enhanced Security Implementation**

The RAG API has been upgraded with enterprise-grade security features that match the safety standards of `api_sc.py` while adding file-level access control for RAG operations.

## 🔐 **Session-ID Based Authentication**

### **Session Management**
- **Session IDs**: UUID-based session identifiers (more secure than random tokens)
- **Database Primary Key**: Session IDs are stored as primary keys in SQLite database
- **Session Tracking**: Each session includes username, creation time, last activity, and expiration
- **Automatic Cleanup**: Expired sessions are automatically cleaned up during queries
- **Secure Logout**: Sessions are completely removed from database on logout (not just deactivated)

### **Authentication Flow**
1. **Login** → Creates unique UUID session_id + database entry
2. **Each Request** → Validates session_id, checks expiration, updates last activity
3. **Logout** → Completely removes session_id from database

## 🔒 **File Access Control System**

### **User Permissions**
- **Admin Users**: Can access all files (unrestricted access)
- **Regular Users**: Can only access files specified in their `allowed_files` list
- **Special Permission**: Users with `"all"` in allowed_files get unrestricted access

### **RAG Security Filtering**
- **Document Filtering**: RAG responses only include content from files the user can access
- **Source Verification**: Every document chunk is verified against user permissions before inclusion
- **Security Logging**: All access attempts are logged with security information
- **Fallback Protection**: If user has no access to any relevant documents, returns safe error message

## 🚨 **Security Features**

### **Session-ID Authentication**
```python
# Primary: Session-ID authentication (UUID-based)
user = await get_user_by_session_id(session_id)

# Fallback: Legacy token authentication for compatibility
if not user:
    user = await get_user_by_token(token)

# Session creation (login)
session_id = str(uuid.uuid4())  # UUID for maximum security
await create_session(username, session_id, expires_hours=24)

# Session termination (logout)
await logout_session_by_id(session_id)  # Complete removal from DB
```

### **File Access Verification**
```python
# Check if user can access specific file
has_access = await check_file_access(username, filename)

# Get user's allowed files
allowed_files = await get_user_allowed_filenames(username)
```

### **RAG Security Implementation**
```python
# Filter documents by user permissions
filtered_docs = await filter_documents_by_user_access(documents, username)

# Use secure RAG retriever
secure_retriever = SecureRAGRetriever(username)
```

## 📊 **API Endpoints Security**

### **🔓 Public Endpoints**
- `GET /` - Landing page
- `GET /docs` - API documentation
- `GET /openapi.json` - OpenAPI schema
- `POST /login` - User login
- `POST /create_token` - Master token creation (one-time only)

### **🔒 Authenticated Endpoints**
- `POST /logout` - Session invalidation
- `POST /query` - **Secure RAG query with file access control**
- `POST /chat` - **Secure RAG chat with file access control**
- `GET /files/list` - List documents (filtered by user access)

### **🛡️ Admin-Only Endpoints**
- `POST /register` - User registration (admin or master key required)
- `POST /upload` - Document upload and indexing
- `DELETE /files/delete` - Document deletion
- `GET /accounts` - List user accounts

## 🔍 **Security Monitoring**

### **Comprehensive Logging**
```python
# Security events logged
- Login/logout attempts
- File access denials
- RAG query filtering results
- Session creation/expiration
- Admin operations
```

### **Access Control Logging**
```python
# Example log entries
INFO: User alice denied access to document from file: secret_doc.pdf
INFO: Secure RAG query for user bob: 3 source docs, filtered: True
WARNING: User charlie denied access to all source documents for query
```

## ⚠️ **Security Safeguards**

### **RAG Response Security**
- **Access Denied**: Returns safe message when user has no access to relevant documents
- **Partial Access**: Notifies user when some documents were filtered from response
- **Source Tracking**: Tracks which documents contributed to each response
- **Metadata Filtering**: Strips sensitive metadata from responses

### **Session Security**
- **Automatic Expiration**: Sessions expire after 24 hours of inactivity
- **Concurrent Session Limits**: New login invalidates previous sessions
- **Activity Tracking**: Last activity timestamp updated on each request
- **Secure Token Generation**: Uses `secrets.token_urlsafe()` for cryptographic security

## 🔧 **Configuration**

### **User File Permissions**
```python
# Grant access to specific files
allowed_files = ["document1.pdf", "document2.txt"]

# Grant access to all files
allowed_files = ["all"]

# Admin role automatically gets all access
role = "admin"  # Can access everything
```

### **Session Configuration**
```python
# Session expiration (configurable)
await create_session(username, token, expires_hours=24)

# Cleanup frequency (automatic)
await cleanup_expired_sessions()
```

## 🛡️ **Security Comparison with api_sc.py**

| Feature | api_sc.py | Secure RAG API | Enhancement |
|---------|-----------|----------------|-------------|
| Authentication | Bearer tokens | Session-based + fallback | ✅ Enhanced |
| User roles | Admin/User | Admin/User | ✅ Same |
| Master key | ✅ | ✅ | ✅ Same |
| File access | ✅ | ✅ + RAG filtering | 🚀 **Enhanced** |
| Session management | ❌ | ✅ | 🚀 **New** |
| Logout | ❌ | ✅ | 🚀 **New** |
| RAG security | ❌ | ✅ | 🚀 **New** |
| Access logging | Basic | Comprehensive | 🚀 **Enhanced** |

## 🚀 **Usage Examples**

### **1. Admin User (Full Access)**
```bash
# Login
curl -X POST http://localhost:9001/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# Query (accesses all documents)
curl -X POST http://localhost:9001/query \
  -H "Authorization: Bearer <session_token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the security features?"}'
```

### **2. Regular User (Restricted Access)**
```bash
# Login
curl -X POST http://localhost:9001/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "password"}'

# Query (only accesses allowed files)
curl -X POST http://localhost:9001/query \
  -H "Authorization: Bearer <session_token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What information is available to me?"}'
```

### **3. Logout (Secure Session Invalidation)**
```bash
curl -X POST http://localhost:9001/logout \
  -H "Authorization: Bearer <session_token>"
```

## 🎯 **Security Benefits**

1. **🔐 Data Isolation**: Users only see content from files they're authorized to access
2. **🕒 Session Security**: Automatic session expiration and cleanup prevents token hijacking
3. **📝 Audit Trail**: Comprehensive logging of all security events and access attempts
4. **🛡️ Defense in Depth**: Multiple layers of security (authentication, authorization, filtering)
5. **🚪 Proper Logout**: Users can securely terminate their sessions
6. **⚡ Performance**: Efficient filtering that doesn't impact query speed
7. **🔍 Transparency**: Users are informed when content is filtered due to access restrictions

## 🔒 **Production Deployment**

For production deployment, ensure:
- [ ] Set strong passwords for admin accounts
- [ ] Configure appropriate session timeouts
- [ ] Monitor security logs regularly
- [ ] Set up proper HTTPS/TLS
- [ ] Implement rate limiting
- [ ] Regular security audits of user permissions
- [ ] Backup user database regularly

The Secure RAG API provides enterprise-grade security while maintaining the powerful RAG capabilities, ensuring that sensitive information remains protected while still delivering valuable AI-powered insights to authorized users.
