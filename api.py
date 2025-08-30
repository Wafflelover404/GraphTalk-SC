
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request, Depends, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Union
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
from userdb import create_user, verify_user, update_access_token, get_user, get_allowed_files, get_user_by_token, list_users
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Import LLM functionality
from llm import llm_call

# Import RAG functionality
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'rag_api'))
from rag_api.pydantic_models import QueryInput, QueryResponse, DocumentInfo, DeleteFileRequest, ModelName
from rag_api.langchain_utils import get_rag_chain
from rag_api.db_utils import insert_application_logs, get_chat_history, get_all_documents, insert_document_record, delete_document_record
from rag_api.chroma_utils import index_document_to_chroma, delete_doc_from_chroma
import json
import datetime

# Initialize app with proper metadata
app = FastAPI(
    title="RAG API",
    description="Knowledge Base Query and Management System with RAG",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# CORS setup for Vue.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://kb-sage.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

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
class QueryRequest(BaseModel):
    text: str
    model: Optional[str] = "llama3.2"
    session_id: Optional[str] = None

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
    token: Optional[str] = None
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
    model: Optional[str] = "llama3.2"
    session_id: Optional[str] = None

# User authentication and authorization
async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    user = await get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired token.")
    return user

async def get_user_role(username: str):
    user = await get_user(username)
    if user:
        return user[3]  # role
    return None

# Endpoints
@app.get("/", include_in_schema=False)
async def landing_page():
    return {
        "app": "RAG API",
        "version": app.version,
        "endpoints": {
            "/register": {"method": "POST", "description": "Register a new user"},
            "/login": {"method": "POST", "description": "Login and get access token"},
            "/query": {"method": "POST", "description": "Query using RAG (auth required)"},
            "/chat": {"method": "POST", "description": "Chat using RAG with history (auth required)"},
            "/upload": {"method": "POST", "description": "Upload a document to RAG (auth required)"},
            "/files/list": {"method": "GET", "description": "List uploaded documents (auth required)"},
            "/files/delete": {"method": "DELETE", "description": "Delete document from RAG (auth required)"},
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

    if not (is_admin or is_master):
        raise HTTPException(status_code=403, detail="Admin or valid master key required.")
    if await get_user(request.username):
        return APIResponse(status="error", message="Username already exists", response={})
    if request.role not in ["user", "admin"]:
        return APIResponse(status="error", message="Role must be 'user' or 'admin'", response={})
    await create_user(request.username, request.password, request.role, request.allowed_files)
    return APIResponse(status="success", message="User registered", response={})

# User login
@app.post("/login", response_model=TokenRoleResponse)
async def login_user(request: LoginRequest):
    if not await verify_user(request.username, request.password):
        return TokenRoleResponse(status="error", message="Invalid username or password", token=None, role=None)
    # Generate new token for session
    token = secrets.token_urlsafe(32)
    await update_access_token(request.username, token)
    role = await get_user_role(request.username)
    return TokenRoleResponse(status="success", message="Login successful", token=token, role=role)

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

# RAG Query endpoint (simple, like the original /query but with RAG)
@app.post("/query", response_model=APIResponse)
async def process_rag_query(
    request: RAGQueryRequest,
    humanize: bool = Query(True),
    user=Depends(get_current_user)
):
    """Process a query using RAG"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        if humanize:
            # Use RAG chain for contextualized response
            try:
                chat_history = get_chat_history(session_id)
                rag_chain = get_rag_chain(request.model)
                response = rag_chain.invoke({
                    "input": request.question,
                    "chat_history": chat_history
                })['answer']
                
                # Log the interaction
                insert_application_logs(session_id, request.question, response, request.model)
            except Exception as e:
                logger.error(f"RAG chain error: {e}")
                # Fallback to basic LLM call
                response = await llm_call(request.question, "No context available from RAG")
        else:
            # Just return raw context without LLM processing
            from rag_api.chroma_utils import vectorstore
            retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
            docs = retriever.get_relevant_documents(request.question)
            response = [doc.page_content for doc in docs]
        
        return APIResponse(
            status="success", 
            message="Query processed with RAG", 
            response={
                "answer": response,
                "session_id": session_id,
                "model": request.model
            }
        )
    except Exception as e:
        logger.exception("RAG query processing error")
        return APIResponse(status="error", message=str(e), response=None)

# Chat endpoint with history (from RAG API)
@app.post("/chat", response_model=APIResponse)
async def chat(
    request: RAGQueryRequest,
    user=Depends(get_current_user)
):
    """Chat using RAG with conversation history"""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        logger.info(f"Session ID: {session_id}, User Query: {request.question}, Model: {request.model}")
        
        chat_history = get_chat_history(session_id)
        rag_chain = get_rag_chain(request.model)
        answer = rag_chain.invoke({
            "input": request.question,
            "chat_history": chat_history
        })['answer']

        insert_application_logs(session_id, request.question, answer, request.model)
        logger.info(f"Session ID: {session_id}, AI Response: {answer}")
        
        return APIResponse(
            status="success",
            message="Chat response generated",
            response={
                "answer": answer,
                "session_id": session_id,
                "model": request.model
            }
        )
    except Exception as e:
        logger.exception("Chat processing error")
        return APIResponse(status="error", message=str(e), response=None)

# Upload endpoint for documents (using RAG indexing)
@app.post("/upload", response_model=APIResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    """Upload and index document in RAG"""
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    allowed_extensions = ['.pdf', '.docx', '.html', '.txt']
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed types are: {', '.join(allowed_extensions)}"
        )
    
    upload_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()
    original_filename = file.filename
    temp_file_path = f"temp_{original_filename}"
    
    try:
        # Save uploaded file temporarily
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Insert document record and get file_id
        file_id = insert_document_record(original_filename)
        
        # Index document to Chroma
        success = index_document_to_chroma(temp_file_path, file_id)
        
        if success:
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
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# List documents endpoint
@app.get("/files/list", response_model=APIResponse)
async def list_documents(user=Depends(get_current_user)):
    """List all uploaded documents"""
    try:
        documents = get_all_documents()
        return APIResponse(
            status="success", 
            message="List of uploaded documents", 
            response={"documents": documents}
        )
    except Exception as e:
        logger.exception("Failed to list documents")
        return APIResponse(status="error", message=str(e), response=None)

# Delete document endpoint
@app.delete("/files/delete", response_model=APIResponse)
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
