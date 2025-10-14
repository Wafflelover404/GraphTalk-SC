from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request, Depends, status, Body, WebSocket, WebSocketDisconnect
from typing import Optional, List, Union, Dict, Any
import datetime
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import os
import shutil
import uuid
from fastapi.concurrency import run_in_threadpool
import secrets
import toml
import bcrypt
import aiofiles
import aiofiles.os
import glob
import asyncio

from rag_api.timing_utils import Timer, PerformanceTracker, time_block

from userdb import (
    create_user, verify_user, update_access_token, get_user, get_allowed_files, 
    get_user_by_token, list_users, create_session, get_user_by_session_id, 
    logout_session_by_id, cleanup_expired_sessions, check_file_access
)
from rag_security import SecureRAGRetriever, get_filtered_rag_context
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Import LLM functionality
from llm import llm_call

# Import RAG functionality
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'rag_api'))
from rag_api.pydantic_models import QueryInput, QueryResponse, DocumentInfo, DeleteFileRequest, ModelName
from rag_api.langchain_utils import get_rag_chain
from rag_api.db_utils import insert_application_logs, get_chat_history, get_all_documents, insert_document_record, delete_document_record, get_file_content_by_filename
from rag_api.chroma_utils import index_document_to_chroma, delete_doc_from_chroma
import json
import datetime

# Import metrics functionality
from metricsdb import init_metrics_db, log_event, log_query, log_file_access, log_security_event
from metrics_middleware import MetricsMiddleware
from quizdb import init_quiz_db, create_quiz_for_filename, get_quiz_by_filename
from rag_api.db_utils import insert_application_logs

# Initialize metrics database
init_metrics_db()

# Initialize app with proper metadata
from reports_api import router as reports_router
from metrics_api import router as metrics_router
from metrics_user_api import router as metrics_user_router

app = FastAPI(
    title="RAG API",
    description="Knowledge Base Query and Management System with RAG",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

app.include_router(reports_router)
app.include_router(metrics_router)
app.include_router(metrics_user_router)

# CORS setup for Vue.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://kb-sage.vercel.app", "wikiai","https://meet-tadpole-resolved.ngrok-free.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

# Initialize async resources on startup
@app.on_event("startup")
async def _startup_events():
    await init_quiz_db()

UPLOAD_DIR = "uploads"
SECRETS_PATH = os.path.expanduser("~/secrets.toml")

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security setup
security_scheme = HTTPBearer(auto_error=False)

# Pydantic models
class APIResponse(BaseModel):
    status: str
    message: str
    response: Union[List[str], str, dict, None] = None

class TokenResponse(BaseModel):
    status: str
    message: str
    token: Optional[str] = None

class TokenRoleResponse(BaseModel):
    status: str
    message: str
    token: Optional[str] = None  # This is session_id for backward compatibility
    role: Optional[str] = None

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str
    allowed_files: Optional[List[str]] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class RAGQueryRequest(BaseModel):
    question: str
    humanize: Optional[bool] = True  # True = return LLM response, False = return raw RAG chunks

class UserEditRequest(BaseModel):
    username: str
    new_username: str = ""
    password: str = ""
    role: str = ""
    allowed_files: Optional[List[str]] = None

# User authentication and authorization using session_id
async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    
    # Try session_id authentication first (most secure)
    user = await get_user_by_session_id(credentials.credentials)
    if user:
        return user
    
    # Fallback to token-based authentication for backward compatibility
    user = await get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired session_id or token.")
    return user

async def get_user_role(username: str):
    user = await get_user(username)
    if user:
        return user[3]  # role
    return None

# Helper: resolve actual stored filename by case-insensitive match against DB documents
def resolve_actual_filename_case_insensitive(requested_filename: str) -> str:
    try:
        documents = get_all_documents()
        req_lower = requested_filename.lower()
        for doc in documents:
            fname = doc.get("filename")
            if isinstance(fname, str) and fname.lower() == req_lower:
                return fname
    except Exception:
        pass
    return requested_filename

# Endpoints
@app.get("/", include_in_schema=False)
async def landing_page():
    return {
        "app": "Secure RAG API",
        "version": app.version,
        "security": "Session-based authentication with file access control",
        "endpoints": {
            "/register": {"method": "POST", "description": "Register a new user (admin/master key required)"},
            "/login": {"method": "POST", "description": "Login and get session token"},
            "/logout": {"method": "POST", "description": "Logout and invalidate session (auth required)"},
            "/query": {"method": "POST", "description": "Secure RAG query with file access control (auth required)"},
            "/chat": {"method": "POST", "description": "Secure RAG chat with history and file access control (auth required)"},
            "/upload": {"method": "POST", "description": "Upload document to RAG (admin only)"},
            "/files/list": {"method": "GET", "description": "List accessible documents (auth required)"},
            "/files/delete": {"method": "DELETE", "description": "Delete document from RAG (admin only)"},
            "/accounts": {"method": "GET", "description": "List user accounts (admin only)"},
            "/docs": {"method": "GET", "description": "Interactive API documentation"}
        }
    }

# User registration (requires master key)
@app.post("/register", response_model=APIResponse)
async def register_user(request: RegisterRequest, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    # Allow registration if admin is authenticated or valid master key is provided via Bearer
    is_admin = False
    is_master = False
    if credentials:
        user = await get_user_by_token(credentials.credentials)
        if user and user[3] == "admin":
            is_admin = True
        # If not admin, check if Bearer token is master key
        if not is_admin:
            if os.path.exists(SECRETS_PATH):
                with open(SECRETS_PATH, "r") as f:
                    secrets_data = toml.load(f)
                stored_hash = secrets_data.get("access_token_hash", "")
                if stored_hash:
                    try:
                        if bcrypt.checkpw(credentials.credentials.encode("utf-8"), stored_hash.encode("utf-8")):
                            is_master = True
                    except Exception:
                        pass

    request.username = request.username.replace(" ", "_")
    request.password = request.password.replace(" ", "_")
    if not (is_admin or is_master):
        raise HTTPException(status_code=403, detail="Admin or valid master key required.")
    if await get_user(request.username):
        return APIResponse(status="error", message="Username already exists", response={})
    if request.role not in ["user", "admin"]:
        return APIResponse(status="error", message="Role must be 'user' or 'admin'", response={})
    await create_user(request.username, request.password, request.role, request.allowed_files)
    return APIResponse(status="success", message="User registered", response={})

# User login with session_id management
@app.post("/login", response_model=TokenRoleResponse)
async def login_user(request: LoginRequest, request_obj: Request):
    client_ip = request_obj.client.host if request_obj and request_obj.client else None
    
    if not await verify_user(request.username, request.password):
        # Log failed login attempt
        log_security_event(
            event_type="failed_login",
            ip_address=client_ip,
            user_id=request.username,
            details={"reason": "Invalid credentials"},
            severity="medium"
        )
        return TokenRoleResponse(status="error", message="Invalid username or password", token=None, role=None)
    
    # Generate new session_id (UUID-based for better security)
    session_id = str(uuid.uuid4())
    
    # Create session in database with session_id as primary key
    await create_session(request.username, session_id, expires_hours=24)
    
    # Also update legacy access token for backward compatibility
    await update_access_token(request.username, session_id)
    
    role = await get_user_role(request.username)
    logger.info(f"User {request.username} logged in successfully with session_id: {session_id[:8]}...")
    
    # Log successful login
    log_event(
        event_type="login",
        user_id=request.username,
        session_id=session_id,
        ip_address=client_ip,
        role=role,
        success=True,
        details={"session_type": "new"}
    )
    
    return TokenRoleResponse(
        status="success", 
        message="Login successful - session_id created", 
        token=session_id,  # Return session_id as token for compatibility
        role=role
    )

# User logout using session_id
@app.post("/logout", response_model=APIResponse)
async def logout_user(
    request_obj: Request,
    user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
):
    """Logout user and invalidate session_id"""
    try:
        session_id = credentials.credentials
        client_ip = request_obj.client.host if request_obj and request_obj.client else None
        
        # Logout from session by deleting session_id from database
        success = await logout_session_by_id(session_id)
        
        # Also clear legacy access token
        await update_access_token(user[1], None)  # user[1] is username
        
        # Log logout event
        log_event(
            event_type="logout",
            user_id=user[1],
            session_id=session_id,
            ip_address=client_ip,
            role=user[3],
            success=success,
            details={"method": "user_initiated"}
        )
        
        logger.info(f"User {user[1]} logged out successfully, session_id {session_id[:8]}... removed")
        
        return APIResponse(
            status="success",
            message="Session terminated successfully",
            response={
                "logged_out": True,
                "session_id_removed": session_id[:8] + "..."
            }
        )
    except Exception as e:
        logger.exception("Logout error")
        return APIResponse(status="error", message=str(e), response=None)

@app.post("/create_token", response_model=TokenResponse)
async def generate_token():
    """Create a new access token (only allowed once)"""
    # Check if master key already exists
    if os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH, "r") as f:
            secrets_data = toml.load(f)
        stored_hash = secrets_data.get("access_token_hash", "")
        if stored_hash:
            return TokenResponse(
                status="error",
                message="Token already exists. Only one token can be created.",
                token=None
            )
    token = secrets.token_urlsafe(64)
    token_bytes = token.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hashed_token = bcrypt.hashpw(token_bytes, salt).decode('utf-8')
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    with open(SECRETS_PATH, "w") as f:
        toml.dump({"access_token_hash": hashed_token}, f)
    return TokenResponse(
        status="success",
        message="Token created successfully. Save this token as it won't be shown again.",
        token=token
    )

# Whitelist /docs endpoint (no authentication required)
@app.get("/docs", include_in_schema=False)
async def get_documentation():
    """Serve Swagger UI without authentication"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - Swagger UI"
    )

# Whitelist /openapi.json endpoint (no authentication required)
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_schema():
    return app.openapi()

async def get_available_filenames(username: str) -> List[str]:
    """Helper function to get all available filenames from uploads and database,
    filtered by the user's allowed files (unless None meaning all files allowed)."""
    # Get all files from the uploads directory
    files = []
    if os.path.exists(UPLOAD_DIR):
        for file in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, file)
            if os.path.isfile(file_path):
                files.append(file)
    
    # Also get files from the database
    db_files = get_all_documents()
    db_filenames = [doc["filename"] for doc in db_files]
    
    # Combine and deduplicate
    all_files = list(set(files + db_filenames))

    # Filter by user's allowed files
    allowed = await get_allowed_files(username)
    if allowed is None:
        return all_files
    allowed_set = set(allowed)
    return [f for f in all_files if f in allowed_set]

async def get_possible_files_by_title(username: str) -> Dict[str, List[str]]:
    """Return a mapping from base title (filename without extension) to list of possible filenames (with extensions),
    filtered by the user's allowed files."""
    all_files = await get_available_filenames(username)
    mapping: Dict[str, List[str]] = {}
    for fname in all_files:
        base, _ext = os.path.splitext(fname)
        mapping.setdefault(base, []).append(fname)
    return mapping

def extract_title_from_chunk(chunk_text: str) -> Optional[str]:
    """Best-effort extraction of a 'title' field from the chunk text.
    Supports dict-like strings with single quotes and JSON-like strings with double quotes.
    """
    try:
        # Try naive JSON conversion from single quotes to double quotes safely
        candidate = chunk_text
        if "'title'" in candidate and '"title"' not in candidate:
            candidate = candidate.replace("'", '"')
        # Try to locate a JSON object prefix
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            obj_str = candidate[start:end+1]
            data = json.loads(obj_str)
            title = data.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()
    except Exception:
        pass
    # Fallback regex for 'title': '...'
    import re
    m = re.search(r"['\"]title['\"]\s*:\s*['\"]([^'\"]+)['\"]", chunk_text)
    if m:
        return m.group(1).strip()
    return None

# WebSocket authentication helper
async def get_user_from_token(token: str):
    """Authenticate user from WebSocket token parameter"""
    if not token:
        return None
    
    # Try session_id authentication first
    user = await get_user_by_session_id(token)
    if user:
        return user
    
    # Fallback to token-based authentication
    user = await get_user_by_token(token)
    return user

# WebSocket endpoint for streaming query responses
@app.websocket("/ws/query")
async def websocket_query_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket endpoint for streaming RAG queries with real-time responses"""
    logger = logging.getLogger(__name__)
    
    # Authenticate user
    user = await get_user_from_token(token) if token else None
    if not user:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    await websocket.accept()
    logger.info(f"WebSocket connection established for user {user[1]}")
    
    try:
        while True:
            # Receive query message
            data = await websocket.receive_json()
            
            question = data.get("question")
            humanize = data.get("humanize", True)
            session_id = data.get("session_id", str(uuid.uuid4()))
            
            if not question:
                await websocket.send_json({
                    "type": "error",
                    "message": "Question is required"
                })
                continue
            
            username = user[1]
            role = user[3]
            model_type = "local" if os.getenv("RAG_MODEL_TYPE", "server").lower() == "local" else "server"
            
            # Send acknowledgment
            await websocket.send_json({
                "type": "status",
                "message": "Processing query...",
                "status": "processing"
            })
            
            start_time = datetime.datetime.now()
            
            try:
                # Cleanup expired sessions
                await cleanup_expired_sessions()
                
                # Initialize RAG chain
                from rag_api.langchain_utils import get_rag_chain
                rag_chain = get_rag_chain()
                
                # Use secure RAG retriever
                secure_retriever = SecureRAGRetriever(username)
                rag_result = await secure_retriever.invoke_secure_rag_chain(
                    rag_chain=rag_chain,
                    query=question,
                    model_type=model_type,
                    humanize=humanize
                )
                
                # Get source documents
                source_docs = rag_result.get("source_documents", [])
                source_docs_raw = rag_result.get("source_documents_raw", [])
                security_filtered = rag_result.get("security_filtered", False)
                
                # Prepare response data
                immediate_response = {
                    "files": [],
                    "snippets": [],
                    "model": model_type,
                    "security_info": {
                        "user_filtered": True,
                        "username": username,
                        "source_documents_count": len(source_docs),
                        "security_filtered": security_filtered
                    }
                }
                
                # Extract file information and snippets
                filenames_docs = source_docs_raw if source_docs_raw else source_docs
                for doc in filenames_docs:
                    try:
                        if isinstance(doc, dict):
                            meta = doc.get("metadata", {})
                            source = meta.get("source", "unknown")
                            content = doc.get("page_content", "") or ""
                        else:
                            source = doc.metadata.get("source", "unknown") if hasattr(doc, "metadata") else "unknown"
                            content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                        
                        if source not in immediate_response["files"]:
                            immediate_response["files"].append(source)
                        
                        immediate_response["snippets"].append({
                            "content": content,
                            "source": source
                        })
                    except Exception as e:
                        logger.warning(f"Error processing document: {e}")
                
                # Send immediate results
                await websocket.send_json({
                    "type": "immediate",
                    "data": immediate_response
                })
                
                # Generate LLM overview if humanize is enabled
                if humanize:
                    try:
                        from llm import llm_call
                        llm_response = await llm_call(
                            question,
                            {"source_documents": source_docs, "answer": rag_result.get("answer", "")},
                            get_overview=True
                        )
                        overview = llm_response.get("overview")
                        
                        if overview:
                            await websocket.send_json({
                                "type": "overview",
                                "data": overview
                            })
                    except Exception as e:
                        logger.error(f"Error generating LLM overview: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Error generating overview"
                        })
                
                # Handle non-humanized response (raw chunks)
                if not humanize:
                    available_files = await get_available_filenames(username)
                    possible_files_by_title = await get_possible_files_by_title(username)
                    
                    rag_chunks = []
                    chunk_docs = source_docs_raw if source_docs_raw else source_docs
                    for doc in chunk_docs:
                        if isinstance(doc, dict):
                            meta = doc.get("metadata", {})
                            fname = meta.get("source", "unknown")
                            chunk = doc.get("page_content", "") or ""
                        else:
                            fname = doc.metadata["source"] if hasattr(doc, "metadata") and "source" in doc.metadata else "unknown"
                            chunk = doc.page_content if hasattr(doc, "page_content") else str(doc)
                        
                        base_title = extract_title_from_chunk(chunk)
                        possible_files = possible_files_by_title.get(base_title, []) if base_title else []
                        rag_chunks.append(
                            f"{chunk}\n<filename>{fname}</filename>\n<possible_files>{json.dumps(possible_files, ensure_ascii=False)}</possible_files>"
                        )
                    
                    await websocket.send_json({
                        "type": "chunks",
                        "data": {
                            "chunks": rag_chunks,
                            "available_files": available_files,
                            "possible_files_by_title": possible_files_by_title
                        }
                    })
                
                # Calculate response time
                response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
                
                # Extract source filenames for logging
                source_filenames = []
                for doc in filenames_docs:
                    try:
                        if isinstance(doc, dict):
                            meta = doc.get("metadata", {})
                            source_filenames.append(meta.get("source", "unknown"))
                        elif hasattr(doc, "metadata"):
                            source_filenames.append(doc.metadata.get("source", "unknown"))
                    except Exception:
                        source_filenames.append("unknown")
                
                # Log metrics
                response_text = rag_result.get("answer", "") if humanize else "\n".join([s["content"][:100] + "..." for s in immediate_response["snippets"][:3]])
                
                # Ensure session_id is valid before logging
                if not session_id:
                    logger.error("session_id is None or empty before log_query call in websocket")
                    session_id = str(uuid.uuid4())
                
                log_query(
                    session_id=session_id,
                    user_id=username,
                    role=role,
                    question=question,
                    answer=response_text,
                    model_type=model_type,
                    humanize=humanize,
                    source_document_count=len(source_docs),
                    security_filtered=security_filtered,
                    source_filenames=immediate_response["files"],
                    ip_address=websocket.client.host if websocket.client else None,
                    response_time_ms=int(response_time)
                )
                
                # Log file access
                for filename in immediate_response["files"]:
                    log_file_access(
                        user_id=username,
                        role=role,
                        filename=filename,
                        access_type="retrieved_in_rag",
                        session_id=session_id,
                        ip_address=websocket.client.host if websocket.client else None,
                        query_context=question[:100]
                    )
                
                # Send completion
                await websocket.send_json({
                    "type": "complete",
                    "message": "Query processed successfully",
                    "response_time_ms": int(response_time)
                })
                
            except Exception as e:
                logger.exception(f"Error processing WebSocket query for user {username}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user[1] if user else 'unknown'}")
    except Exception as e:
        logger.exception(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass

# SECURE RAG Query endpoint with file access control (HTTP fallback)
@app.post("/query", response_model=APIResponse)
async def process_secure_rag_query(
    request: RAGQueryRequest,
    request_obj: Request,
    user=Depends(get_current_user)
):
    """Process a query using RAG with file access security (HTTP fallback for compatibility)"""
    logger = logging.getLogger(__name__)
    tracker = PerformanceTracker(f"query_endpoint('{request.question[:50]}...')", logger)

    try:
        username = user[1]  # Extract username from user tuple
        role = user[3]  # Get user role
        session_id = str(uuid.uuid4())  # Generate session for this query
        client_ip = request_obj.client.host if request_obj and hasattr(request_obj, 'client') and request_obj.client else None
        # Get model type from environment variable (RAG_MODEL_TYPE: "local" or "server")
        model_type = "local" if os.getenv("RAG_MODEL_TYPE", "server").lower() == "local" else "server"

        # Start time for response time tracking
        tracker.start_operation("query_start")
        start_time = datetime.datetime.now()

        # Clean up expired sessions periodically
        tracker.start_operation("cleanup_sessions")
        await cleanup_expired_sessions()
        tracker.end_operation("cleanup_sessions")

        # Initialize the RAG chain
        tracker.start_operation("init_rag_chain")
        from rag_api.langchain_utils import get_rag_chain
        rag_chain = get_rag_chain()
        tracker.end_operation("init_rag_chain")

        # Use secure RAG retriever that respects file permissions
        tracker.start_operation("secure_retrieval")
        secure_retriever = SecureRAGRetriever(username=username, session_id=session_id)
        rag_result = await secure_retriever.invoke_secure_rag_chain(
            rag_chain=rag_chain,
            query=request.question,
            model_type=model_type,
            humanize=request.humanize if hasattr(request, 'humanize') else True
        )
        tracker.end_operation("secure_retrieval")

        # Get the immediate response with source documents
        source_docs = rag_result.get("source_documents", [])
        source_docs_raw = rag_result.get("source_documents_raw", [])
        security_filtered = rag_result.get("security_filtered", False)
        
        # Prepare immediate response data
        immediate_response = {
            "files": [],
            "snippets": [],
            "model": model_type,
            "security_info": {
                "user_filtered": True,
                "username": username,
                "source_documents_count": len(source_docs),
                "security_filtered": security_filtered
            }
        }
        
        # Extract file information and snippets
        filenames_docs = source_docs_raw if source_docs_raw else source_docs
        for doc in filenames_docs:
            try:
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {})
                    source = meta.get("source", "unknown")
                    content = doc.get("page_content", "") or ""
                else:
                    source = doc.metadata.get("source", "unknown") if hasattr(doc, "metadata") else "unknown"
                    content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                
                if source not in immediate_response["files"]:
                    immediate_response["files"].append(source)
                
                immediate_response["snippets"].append({
                    "content": content,
                    "source": source
                })
            except Exception as e:
                logger.warning(f"Error processing document: {e}")
        
        # Generate LLM overview if humanize is enabled
        overview = None
        if request.humanize is None or request.humanize:
            try:
                from llm import llm_call
                llm_response = await llm_call(
                    request.question,
                    {"source_documents": source_docs, "answer": rag_result.get("answer", "")},
                    get_overview=True
                )
                overview = llm_response.get("overview")
            except Exception as e:
                logger.error(f"Error generating LLM overview: {e}")
                overview = "Error generating overview. Showing raw results."

        # Calculate response time
        tracker.start_operation("calculate_response_time")
        response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
        tracker.end_operation("calculate_response_time")

        # Get client IP
        tracker.start_operation("get_client_ip")
        client_ip = request_obj.client.host if request_obj.client else None
        tracker.end_operation("get_client_ip")

        # Extract source filenames (prefer raw docs if available)
        tracker.start_operation("extract_filenames")
        filenames_docs = source_docs_raw if source_docs_raw else source_docs
        source_filenames = []
        for doc in filenames_docs:
            try:
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {})
                    source_filenames.append(meta.get("source", "unknown"))
                elif hasattr(doc, "metadata"):
                    source_filenames.append(doc.metadata.get("source", "unknown"))
            except Exception:
                source_filenames.append("unknown")
        tracker.end_operation("extract_filenames", f"Found {len(source_filenames)} source files")

        # Log metrics
        tracker.start_operation("log_metrics")
        
        # Create a response text for logging
        response_text = overview if overview else "\n".join([s["content"][:100] + "..." for s in immediate_response["snippets"][:3]])
        
        # Ensure session_id is valid before logging
        if not session_id:
            logger.error("session_id is None or empty before log_query call")
            session_id = str(uuid.uuid4())
        
        log_query(
            session_id=session_id,
            user_id=username,
            role=role,
            question=request.question,
            answer=response_text,
            model_type=model_type,
            humanize=request.humanize if request.humanize is not None else True,
            source_document_count=len(source_docs),
            security_filtered=security_filtered,
            source_filenames=immediate_response["files"],
            ip_address=client_ip,
            response_time_ms=int(response_time)
        )

        # Log file access for each source document
        for filename in immediate_response["files"]:
            log_file_access(
                user_id=username,
                role=role,
                filename=filename,
                access_type="retrieved_in_rag",
                session_id=session_id,
                ip_address=client_ip,
                query_context=request.question[:100]  # First 100 chars of query
            )

        # Log the interaction with security info
        insert_application_logs(
            session_id,
            request.question,
            f"Found {len(source_docs)} source documents [Security filtered: {security_filtered}]",
            model_type
        )
        tracker.end_operation("log_metrics")

        logger.info(f"Secure RAG query for user {username}: {len(source_docs)} source docs, filtered: {security_filtered}, model: {model_type}")

        # If no documents found, auto-submit report
        if not source_docs and not source_docs_raw:
            from reports_db import submit_report
            permitted_files = await get_allowed_files(username)
            if permitted_files is None:
                permitted_files = []
            submit_report(
                user=username,
                permitted_files=permitted_files,
                issue=f"No documents found for query: {request.question}"
            )
            return APIResponse(
                status="success",
                message="No matching documents found",
                response={
                    "immediate": {
                        "files": [],
                        "snippets": [],
                        "model": model_type,
                        "security_info": {
                            "user_filtered": True,
                            "username": username,
                            "source_documents_count": 0,
                            "security_filtered": security_filtered
                        }
                    },
                    "model": model_type
                }
            )

        # If humanize is True (default): return response with immediate data and optional overview
        if request.humanize is None or request.humanize:
            tracker.end_operation("query_start")
            tracker.log_summary()
            
            response_data = {
                "immediate": immediate_response,
                "model": model_type,
                "security_info": immediate_response["security_info"]
            }
            
            if overview is not None:
                response_data["overview"] = overview
            
            return APIResponse(
                status="success",
                message=f"Query processed with secure RAG using {model_type} model",
                response=response_data
            )
        else:
            # If humanize is False: return array of RAG chunks with <filename></filename> tag
            # Get available filenames and mapping by title, filtered by user permissions
            available_files = await get_available_filenames(username)
            possible_files_by_title = await get_possible_files_by_title(username)

            rag_chunks = []
            chunk_docs = source_docs_raw if source_docs_raw else source_docs
            for doc in chunk_docs:
                # Try to get filename from doc metadata, fallback to 'unknown'
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {})
                    fname = meta.get("source", "unknown")
                    chunk = doc.get("page_content", "") or ""
                else:
                    fname = doc.metadata["source"] if hasattr(doc, "metadata") and "source" in doc.metadata else "unknown"
                    chunk = doc.page_content if hasattr(doc, "page_content") else str(doc)
                # Try to extract a base title from the chunk and map to possible filenames
                base_title = extract_title_from_chunk(chunk)
                possible_files = possible_files_by_title.get(base_title, []) if base_title else []
                rag_chunks.append(
                    f"{chunk}\n<filename>{fname}</filename>\n<possible_files>{json.dumps(possible_files, ensure_ascii=False)}</possible_files>"
                )

            tracker.end_operation("query_start")
            tracker.log_summary()
            return APIResponse(
                status="success",
                message="Query processed with secure RAG (raw chunks)",
                response={
                    "chunks": rag_chunks,
                    "model": model_type,
                    "available_files": available_files,
                    "possible_files_by_title": possible_files_by_title,
                    "security_info": {
                        "user_filtered": True,
                        "username": username,
                        "source_documents_count": len(source_docs),
                        "security_filtered": security_filtered
                    }
                }
            )
    except Exception as e:
        logger.exception(f"Secure RAG query processing error for user {username if 'username' in locals() else 'unknown'}")
        tracker.log_summary()
        return APIResponse(status="error", message=str(e), response=None)
from fastapi.responses import PlainTextResponse
from urllib.parse import unquote

# Endpoint to return file content by filename (from DB)
@app.get("/files/content/{filename}")
async def get_file_content(
    filename: str,
    request_obj: Request,
    user = Depends(get_current_user),
    include_quiz: bool = Query(False, description="If true, return JSON with file content and quiz")
):
    """
    Return the content of a file by its name (if user has access). Supports percent-encoded (e.g. Russian) filenames. Reads from DB.
    """
    decoded_filename = unquote(filename)
    resolved_filename = resolve_actual_filename_case_insensitive(decoded_filename)
    allowed_files = await get_allowed_files(user[1])
    logger.info(f"User {user[1]} requests file: {decoded_filename} (resolved: {resolved_filename}). Allowed files: {allowed_files}")
    
    # Get client IP for metrics
    client_ip = request_obj.client.host if request_obj and request_obj.client else None
    
    # Admins can access any file; for users: allowed_files=None means all files allowed
    if user[3] != "admin":
        if allowed_files is not None and resolved_filename not in allowed_files:
            # Log security event for unauthorized access attempt
            log_security_event(
                event_type="unauthorized_file_access",
                ip_address=client_ip,
                user_id=user[1],
                details={"filename": resolved_filename},
                severity="medium"
            )
            raise HTTPException(status_code=403, detail="You do not have access to this file.")
    content_bytes = get_file_content_by_filename(resolved_filename)
    if content_bytes is None:
        logger.warning(f"File not found in DB: {decoded_filename}")
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        # Try decode as utf-8, fallback to latin1 if needed
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = content_bytes.decode("latin1")
        
        # Log successful file view
        log_file_access(
            user_id=user[1],
            role=user[3],
            filename=resolved_filename,
            access_type="view",
            session_id=None,
            ip_address=client_ip
        )

        if include_quiz:
            # Fetch the latest quiz for this file, if any
            quiz_row = await get_quiz_by_filename(resolved_filename)
            quiz_payload: Dict[str, Any]
            if quiz_row:
                # quiz_row: (id, source_filename, timestamp, quiz_json, logs)
                try:
                    quiz_dict = json.loads(quiz_row[3]) if quiz_row[3] else None
                except Exception:
                    quiz_dict = {"questions": [], "raw": quiz_row[3]}
                quiz_payload = {
                    "id": quiz_row[0],
                    "filename": quiz_row[1],
                    "timestamp": quiz_row[2],
                    "quiz": quiz_dict,
                    "logs": quiz_row[4]
                }
            else:
                quiz_payload = None

            return JSONResponse(
                content={
                    "filename": resolved_filename,
                    "content": content,
                    "quiz": quiz_payload
                }
            )

        # Default behavior: return plain text content
        return PlainTextResponse(content)
    except Exception as e:
        logger.exception(f"Failed to decode file {resolved_filename}")
        raise HTTPException(status_code=500, detail=f"Failed to decode file: {e}")

# Create or fetch quiz for a given file
@app.post("/quiz/{filename}", response_model=APIResponse)
async def create_or_get_quiz(
    filename: str,
    request_obj: Request,
    user = Depends(get_current_user),
    regenerate: bool = Query(False, description="If true, re-generate a new quiz for the file")
):
    """
    Return a quiz for the given file. If `regenerate=true`, create a new quiz. Otherwise,
    return the latest existing quiz, generating one if missing.
    """
    decoded_filename = unquote(filename)
    resolved_filename = resolve_actual_filename_case_insensitive(decoded_filename)
    allowed_files = await get_allowed_files(user[1])
    logger.info(f"User {user[1]} requests quiz for file: {decoded_filename} (resolved: {resolved_filename}). Allowed files: {allowed_files}")

    # Access control (same as file content). allowed_files=None => allow all
    if user[3] != "admin":
        if allowed_files is not None and resolved_filename not in allowed_files:
            client_ip = request_obj.client.host if request_obj and request_obj.client else None
            log_security_event(
                event_type="unauthorized_file_access",
                ip_address=client_ip,
                user_id=user[1],
                details={"filename": resolved_filename, "action": "quiz_access"},
                severity="medium"
            )
            raise HTTPException(status_code=403, detail="You do not have access to this file.")

    try:
        quiz_row = None
        if not regenerate:
            quiz_row = await get_quiz_by_filename(resolved_filename)

        # If no quiz exists or regeneration requested, create a new one
        if regenerate or not quiz_row:
            new_quiz_id = await create_quiz_for_filename(resolved_filename)
            if not new_quiz_id:
                return APIResponse(status="error", message="Failed to generate quiz", response=None)
            quiz_row = await get_quiz_by_filename(resolved_filename)

        if not quiz_row:
            return APIResponse(status="error", message="Quiz not found", response=None)

        # Parse quiz JSON safely
        try:
            quiz_dict = json.loads(quiz_row[3]) if quiz_row[3] else None
        except Exception:
            quiz_dict = {"questions": [], "raw": quiz_row[3]}

        payload = {
            "id": quiz_row[0],
            "filename": quiz_row[1],
            "timestamp": quiz_row[2],
            "quiz": quiz_dict,
            "logs": quiz_row[4]
        }

        # Log file access as a "quiz_view" event
        client_ip = request_obj.client.host if request_obj and request_obj.client else None
        log_file_access(
            user_id=user[1],
            role=user[3],
            filename=resolved_filename,
            access_type="quiz_view" if not regenerate else "quiz_regenerate",
            session_id=None,
            ip_address=client_ip
        )

        return APIResponse(status="success", message="Quiz ready", response=payload)
    except Exception as e:
        logger.exception("Quiz endpoint error")
        return APIResponse(status="error", message=str(e), response=None)

# SECURE Chat endpoint with history and file access control
@app.post("/chat", response_model=APIResponse)
async def secure_chat(
    request: RAGQueryRequest,
    request_obj: Request,
    session_id: str = Query(..., description="Session ID for chat history"),
    user=Depends(get_current_user)
):
    """Secure chat using RAG with conversation history and file access control"""
    try:
        username = user[1]  # Extract username from user tuple
        role = user[3]  # Get user role
        # Get model type from environment variable (RAG_MODEL_TYPE: "local" or "server")
        model_type = "local" if os.getenv("RAG_MODEL_TYPE", "server").lower() == "local" else "server"
        
        # Start time for response time tracking
        start_time = datetime.datetime.now()
        
        logger.info(f"Secure chat - Session ID: {session_id}, User: {username}, Query: {request.question}, Model: {model_type}")
        
        # Use secure RAG retriever that respects file permissions
        secure_retriever = SecureRAGRetriever(username)
        chat_history = get_chat_history(session_id)
        
        # Get secure RAG response with file access control
        rag_result = await secure_retriever.invoke_secure_rag_chain(
            None, request.question, chat_history, model_type
        )
        
        answer = rag_result["answer"]
        source_docs = rag_result.get("source_documents", [])
        security_filtered = rag_result.get("security_filtered", False)

        # Calculate response time
        response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
        
        # Get client IP
        client_ip = request_obj.client.host if request_obj and request_obj.client else None
        
        # Extract source filenames
        source_filenames = [
            doc.metadata.get("source", "unknown") 
            for doc in source_docs 
            if hasattr(doc, "metadata")
        ]

        # Log metrics
        # Ensure session_id is valid before logging
        if not session_id:
            logger.error("session_id is None or empty before log_query call in secure_chat")
            session_id = str(uuid.uuid4())
        
        log_query(
            session_id=session_id,
            user_id=username,
            role=role,
            question=request.question,
            answer=answer,
            model_type=model_type,
            humanize=getattr(request, 'humanize', True),
            source_document_count=len(source_docs),
            security_filtered=security_filtered,
            source_filenames=source_filenames,
            response_time_ms=int(response_time),
            ip_address=request_obj.client.host if request_obj and hasattr(request_obj, 'client') and request_obj.client else None
        )

        # Log file access for each source document
        for filename in source_filenames:
            log_file_access(
                user_id=username,
                role=role,
                filename=filename,
                access_type="retrieved_in_rag",
                session_id=session_id,
                ip_address=client_ip,
                query_context=request.question[:100]  # First 100 chars of query
            )
        
        # Log the secure interaction
        insert_application_logs(
            session_id, 
            request.question, 
            f"{answer} [Secure chat - Security filtered: {security_filtered}, Source docs: {len(source_docs)}]",
            model_type
        )
        
        logger.info(f"Secure chat for user {username}: {len(source_docs)} source docs, filtered: {security_filtered}, model: {model_type}")
        
        return APIResponse(
            status="success",
            message=f"Secure chat response generated using {model_type} model",
            response={
                "answer": answer,
                "session_id": session_id,
                "model": model_type,
                "security_info": {
                    "user_filtered": True,
                    "username": username,
                    "source_documents_count": len(source_docs),
                    "security_filtered": security_filtered
                }
            }
        )
    except Exception as e:
        username = user[1] if user and len(user) > 1 else "unknown"
        logger.exception(f"Secure chat processing error for user {username}")
        return APIResponse(status="error", message=str(e), response=None)

# Upload endpoint for documents (using RAG indexing) (admin only, stores in DB)
@app.post("/upload", response_model=APIResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    """Upload and index document in RAG (stores file in DB)"""
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    allowed_extensions = ['.pdf', '.docx', '.html', '.txt', '.md']
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types are: {', '.join(allowed_extensions)}"
        )

    # Check if file with the same name already exists in DB
    from rag_api.db_utils import get_file_content_by_filename
    if get_file_content_by_filename(file.filename) is not None:
        raise HTTPException(status_code=400, detail="A file with this name already exists.")

    upload_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()
    original_filename = file.filename

    try:
        # Read file content as bytes
        content_bytes = await file.read()
        # Insert document record and get file_id
        file_id = insert_document_record(original_filename, content_bytes)

        # Optionally, index document to Chroma (if needed, save to temp file)
        temp_file_path = f"temp_{original_filename}"
        with open(temp_file_path, "wb") as buffer:
            buffer.write(content_bytes)
        success = index_document_to_chroma(temp_file_path, file_id)
        os.remove(temp_file_path)

        if success:
            # Fire-and-forget: generate a quiz for this uploaded file in background
            try:
                asyncio.create_task(create_quiz_for_filename(original_filename))
            except Exception:
                pass
            return APIResponse(
                status="success",
                message=f"File {original_filename} has been successfully uploaded and indexed.",
                response={
                    "file_id": file_id,
                    "filename": original_filename,
                    "upload_id": upload_id,
                    "timestamp": timestamp
                }
            )
        else:
            delete_document_record(file_id)
            raise HTTPException(status_code=500, detail=f"Failed to index {original_filename}.")

    except Exception as e:
        logger.exception("File upload failed")
        if 'file_id' in locals():
            delete_document_record(file_id)
        raise HTTPException(500, f"Failed to upload file: {e}")

# List documents endpoint
@app.get("/files/list", response_model=APIResponse)
async def list_documents(user=Depends(get_current_user)):
    """List all uploaded documents the user has access to"""
    try:
        documents = get_all_documents()
        allowed_files = await get_allowed_files(user[1])
        logger.info(f"User {user[1]} role {user[3]} allowed files: {allowed_files}")
        # Admins see all files, others only their allowed
        if user[3] == "admin" or allowed_files is None:
            filtered_docs = documents
        else:
            filtered_docs = [doc for doc in documents if doc.get('filename') in allowed_files]
        return APIResponse(
            status="success",
            message="List of uploaded documents",
            response={"documents": filtered_docs}
        )
    except Exception as e:
        logger.exception("Failed to list documents")
        return APIResponse(status="error", message=str(e), response=None)

# Delete document endpoint (admin only)
@app.delete("/files/delete_by_fileid", response_model=APIResponse)
async def delete_document(
    request: DeleteFileRequest,
    current_user=Depends(get_current_user)
):
    """Delete document from RAG system"""
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    try:
        chroma_delete_success = delete_doc_from_chroma(request.file_id)
        
        if chroma_delete_success:
            db_delete_success = delete_document_record(request.file_id)
            if db_delete_success:
                return APIResponse(
                    status="success",
                    message=f"Successfully deleted document with file_id {request.file_id}",
                    response={"file_id": request.file_id}
                )
            else:
                return APIResponse(
                    status="error",
                    message=f"Deleted from Chroma but failed to delete document with file_id {request.file_id} from database",
                    response=None
                )
        else:
            return APIResponse(
                status="error",
                message=f"Failed to delete document with file_id {request.file_id} from Chroma",
                response=None
            )
    except Exception as e:
        logger.exception("Document deletion failed")
        return APIResponse(status="error", message=str(e), response=None)

# Endpoint to list all available filenames
@app.get("/files/available")
async def list_available_filenames():
    """
    List all available filenames in the uploads directory.
    Returns a list of filenames with their extensions.
    """
    try:
        # Get all files from the uploads directory
        files = []
        for file in os.listdir(UPLOAD_DIR):
            file_path = os.path.join(UPLOAD_DIR, file)
            if os.path.isfile(file_path):
                files.append(file)
        
        # Also get files from the database
        db_files = await get_all_documents()
        db_filenames = [doc[1] for doc in db_files]  # doc[1] is filename in DB
        
        # Combine and deduplicate
        all_files = list(set(files + db_filenames))
        
        return {
            "status": "success",
            "files": all_files,
            "count": len(all_files)
        }
    except Exception as e:
        logger.error(f"Error listing available files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing available files: {str(e)}")

# Endpoint to delete a file by its filename (admin only)
@app.delete("/files/delete_by_filename", response_model=APIResponse)
async def delete_file_by_filename(filename: str, current_user=Depends(get_current_user)):
    """
    Delete a file by its filename (admin only). Removes from uploads, Chroma, and DB.
    """
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    # Decode percent-encoded filename
    filename = unquote(filename) 
    print(f"Deleting file by filename: {filename}")
    # Find file_id by filename
    documents = get_all_documents()
    file_id = None
    for doc in documents:
        # doc is a dict with keys: id, filename, upload_timestamp
        if isinstance(doc, dict) and doc.get("filename") == filename:
            file_id = doc.get("id")
            break
        elif isinstance(doc, (list, tuple)) and len(doc) > 1 and doc[1] == filename:
            file_id = doc[0]
            break
    if not file_id:
        raise HTTPException(status_code=404, detail="File not found in database.")
    # Delete from Chroma
    chroma_delete_success = delete_doc_from_chroma(file_id)
    # Delete from DB
    db_delete_success = delete_document_record(file_id)
    # Delete from uploads directory
    file_path = os.path.join(UPLOAD_DIR, filename)
    file_deleted = False
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            file_deleted = True
        except Exception as e:
            logger.warning(f"Failed to delete file from uploads: {e}")
    if chroma_delete_success and db_delete_success:
        return APIResponse(
            status="success",
            message=f"Successfully deleted file {filename} (file_id {file_id}) from system.",
            response={"file_id": file_id, "filename": filename, "file_deleted": file_deleted}
        )
    else:
        return APIResponse(
            status="error",
            message=f"Failed to fully delete file {filename}. Chroma: {chroma_delete_success}, DB: {db_delete_success}",
            response={"file_id": file_id, "filename": filename, "file_deleted": file_deleted}
        )


# Get user accounts (admin only)
@app.get("/accounts", response_model=List[dict])
async def get_accounts(current_user=Depends(get_current_user)):
    """
    List all accounts with their username, role, and last login.
    Requires admin authentication.
    """
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    users = await list_users()
    return users

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=9001, reload=True)

@app.delete("/user/delete", response_model=APIResponse)
async def delete_user_endpoint(
    username: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
):
    """
    Delete a user by username. Requires admin or master key.
    """
    is_admin = False
    is_master = False
    if credentials:
        user = await get_user_by_token(credentials.credentials)
        if user and user[3] == "admin":
            is_admin = True
        if not is_admin:
            if os.path.exists(SECRETS_PATH):
                with open(SECRETS_PATH, "r") as f:
                    secrets_data = toml.load(f)
                stored_hash = secrets_data.get("access_token_hash", "")
                if stored_hash:
                    try:
                        if bcrypt.checkpw(credentials.credentials.encode("utf-8"), stored_hash.encode("utf-8")):
                            is_master = True
                    except Exception:
                        pass
    if not (is_admin or is_master):
        raise HTTPException(status_code=403, detail="Admin or valid master key required.")
    user = await get_user(username)
    if not user:
        return APIResponse(status="error", message="User not found", response={})
    # Remove user from DB
    import userdb
    await userdb.delete_user(username)
    return APIResponse(status="success", message=f"User {username} deleted", response={})

# User edit endpoint (admin or master key required)
@app.post("/user/edit", response_model=APIResponse)
async def edit_user_endpoint(
    request: UserEditRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
):
    """
    Edit user fields. Only provided fields are changed. Requires admin or master key.
    """
    is_admin = False
    is_master = False
    if credentials:
        user = await get_user_by_token(credentials.credentials)
        if user and user[3] == "admin":
            is_admin = True
        if not is_admin:
            if os.path.exists(SECRETS_PATH):
                with open(SECRETS_PATH, "r") as f:
                    secrets_data = toml.load(f)
                stored_hash = secrets_data.get("access_token_hash", "")
                if stored_hash:
                    try:
                        if bcrypt.checkpw(credentials.credentials.encode("utf-8"), stored_hash.encode("utf-8")):
                            is_master = True
                    except Exception:
                        pass
    if not (is_admin or is_master):
        raise HTTPException(status_code=403, detail="Admin or valid master key required.")
    user = await get_user(request.username)
    if not user:
        return APIResponse(status="error", message="User not found", response={})
    logs = []
    import userdb
    # Change username
    if request.new_username:
        await userdb.update_username(request.username, request.new_username)
        logs.append(f"Username changed to {request.new_username}")
        request.username = request.new_username
    # Change password
    if request.password:
        await userdb.update_password(request.username, request.password)
        logs.append("Password updated")
    # Change role
    if request.role:
        await userdb.update_role(request.username, request.role)
        logs.append(f"Role changed to {request.role}")
    # Change allowed files
    if request.allowed_files is not None:
        previous_files = await userdb.get_allowed_files(request.username)
        await userdb.update_allowed_files(request.username, request.allowed_files)
        logs.append(f"Allowed files updated to {request.allowed_files}")

        # Reindex any newly accessible files in Chroma to ensure they're searchable
        if previous_files and request.allowed_files:
            new_files = set(request.allowed_files) - set(previous_files if previous_files else [])
            if new_files:
                from rag_api.db_utils import get_file_content_by_filename
                from rag_api.chroma_utils import index_document_to_chroma
                import tempfile
                import os

                for filename in new_files:
                    try:
                        content = get_file_content_by_filename(filename)
                        if content:
                            # Create temporary file for indexing
                            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                                temp_file.write(content)
                                temp_path = temp_file.name

                            # Index the file in Chroma
                            index_document_to_chroma(temp_path, filename)
                            os.unlink(temp_path)  # Clean up temp file
                    except Exception as e:
                        logger.error(f"Error reindexing file {filename} after permission update: {e}")

    if not logs:
        return APIResponse(status="success", message="No changes made", response={})
    return APIResponse(status="success", message="; ".join(logs), response={})



# Disrupt all sessions for a user by access token (user self-service)
class DisruptSessionsRequest(BaseModel):
    access_token: str

@app.post("/user/disrupt_sessions", response_model=APIResponse)
async def disrupt_sessions_endpoint(request: DisruptSessionsRequest):
    """
    Remove all active sessions for the user that owns the provided access token (logout everywhere for that user).
    """
    user = await get_user_by_token(request.access_token)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid access token.")
    from userdb import disrupt_sessions_for_user
    username = user[1]
    count = await disrupt_sessions_for_user(username)
    return APIResponse(status="success", message=f"Disrupted {count} sessions for user {username}", response={"sessions_removed": count})

# Edit file content and reindex endpoint (admin only)
@app.post("/files/edit", response_model=APIResponse)
async def edit_file_content(
    filename: str = Body(..., embed=True),
    new_content: str = Body(..., embed=True),
    user=Depends(get_current_user)
):
    """Edit a file's content and reindex it (admin only)."""
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    try:
        from rag_api.db_utils import update_document_record
        from rag_api.chroma_utils import index_document_to_chroma, delete_doc_from_chroma
        import os
        # Update DB
        file_ids = update_document_record(filename, new_content.encode("utf-8"))
        if not file_ids:
            return APIResponse(status="error", message="File not found in DB", response=None)
        # Write new content to a temp file for reindexing (like upload)
        temp_file_path = f"temp_{filename}"
        with open(temp_file_path, "w", encoding="utf-8") as buffer:
            buffer.write(new_content)
        # Remove old Chroma indexes and reindex for each file_id
        for file_id in file_ids:
            delete_doc_from_chroma(file_id)
            index_document_to_chroma(temp_file_path, file_id)
        os.remove(temp_file_path)
        return APIResponse(status="success", message="File updated and reindexed", response={"file_ids": file_ids, "filename": filename})
    except Exception as e:
        return APIResponse(status="error", message=str(e), response=None)

