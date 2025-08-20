from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Union
import uvicorn
import logging
import os
import zipfile
import shutil
import uuid
from fastapi.concurrency import run_in_threadpool
import secrets
import toml
import bcrypt
from userdb import create_user, verify_user, update_access_token, get_user, get_allowed_files, get_user_by_token
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sc_search import kb_search
from memloader import load_scs_directory


# Import LLM and JSON interpretation from dedicated modules
from json_llm import llm_json_interpret
from llm import llm_call
from json_interpreter import load_data_to_sc
import json

# Initialize app with proper metadata

app = FastAPI(
    title="SC-Machine API",
    description="Knowledge Base Query and Management System",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# CORS setup for Vue.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Add your frontend URL(s) here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

UPLOAD_DIR = "uploads"
SECRETS_PATH = os.path.expanduser("~/secrets.toml")
KB_BASE_DIR = "unpacked_kbs"

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(KB_BASE_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security setup
security_scheme = HTTPBearer(auto_error=False)


# Pydantic models
class QueryRequest(BaseModel):
    text: str

class APIResponse(BaseModel):
    status: str
    message: str
    response: Union[List[str], str, dict, None] = None

class TokenResponse(BaseModel):
    status: str
    message: str
    token: Optional[str] = None

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str
    allowed_files: Optional[List[str]] = None

class LoginRequest(BaseModel):
    username: str
    password: str



# User authentication and authorization
def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    user = get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired token.")
    return user

# Master key verification (legacy admin key)
def verify_master_key(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    # Use previous token_exists and hash check logic
    import toml
    if not os.path.exists(SECRETS_PATH):
        raise HTTPException(status_code=401, detail="No master key exists.")
    with open(SECRETS_PATH, "r") as f:
        secrets_data = toml.load(f)
    stored_hash = secrets_data.get("access_token_hash", "")
    if not stored_hash:
        raise HTTPException(status_code=500, detail="Master key file corrupted.")
    token = credentials.credentials
    try:
        if bcrypt.checkpw(token.encode('utf-8'), stored_hash.encode('utf-8')):
            return True
    except Exception as e:
        logger.error(f"Master key verification failed: {str(e)}")
    raise HTTPException(status_code=403, detail="Invalid or missing master key.")

# Endpoints

@app.get("/", include_in_schema=False)
async def landing_page():
    return {
        "app": "SC-Machine API",
        "version": app.version,
        "endpoints": {
            "/register": {"method": "POST", "description": "Register a new user"},
            "/login": {"method": "POST", "description": "Login and get access token"},
            "/query": {"method": "POST", "description": "Query the knowledge base (auth required)"},
            "/upload": {"method": "POST", "description": "Upload a .txt file to the KB (auth required)"},
            "/files/list": {"method": "GET", "description": "List uploaded files (auth required)"},
            "/files/file_content": {"method": "GET", "description": "Get file content (auth required)"},
            "/docs": {"method": "GET", "description": "Interactive API documentation"}
        }
    }


# User registration (requires master key)
@app.post("/register", response_model=APIResponse)
async def register_user(request: RegisterRequest, master=Depends(verify_master_key)):
    if get_user(request.username):
        return APIResponse(status="error", message="Username already exists", response=None)
    if request.role not in ["user", "admin"]:
        return APIResponse(status="error", message="Role must be 'user' or 'admin'", response=None)
    create_user(request.username, request.password, request.role, request.allowed_files)
    return APIResponse(status="success", message="User registered", response=None)

# User login
@app.post("/login", response_model=TokenResponse)
async def login_user(request: LoginRequest):
    if not verify_user(request.username, request.password):
        return TokenResponse(status="error", message="Invalid username or password", token=None)
    # Generate new token for session
    token = secrets.token_urlsafe(32)
    update_access_token(request.username, token)
    return TokenResponse(status="success", message="Login successful", token=token)

@app.post("/create_token", response_model=TokenResponse)
async def generate_token():
    """Create a new access token (only allowed once)"""
    if token_exists():
        return TokenResponse(
            status="error",
            message="Token already exists. Only one token can be created.",
            token=None
        )
    
    token = secrets.token_urlsafe(64)
    token_bytes = token.encode('utf-8')
    #print("token: ", token)
    
    # Hash and store the token
    salt = bcrypt.gensalt(rounds=12)
    hashed_token = bcrypt.hashpw(token_bytes, salt).decode('utf-8')
    
    create_secrets_file()
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

@app.post("/query", response_model=APIResponse)
async def process_query(
    request: QueryRequest,
    humanize: bool = Query(False),
    user=Depends(get_current_user)
):
    """Process a knowledge base query, restrict to allowed files"""
    try:
        allowed_files = get_allowed_files(user[1])
        # You should modify kb_search to accept allowed_files and restrict search
        kb_results = kb_search(request.text, allowed_files=allowed_files)
        if humanize:
            context = "\n".join(kb_results) if isinstance(kb_results, list) else kb_results
            response = llm_call(request.text, context)
        else:
            response = kb_results
        return APIResponse(status="success", message="Query processed", response=response)
    except Exception as e:
        logger.exception("Query processing error")
        return APIResponse(status="error", message=str(e), response=None)

import datetime

# Upload endpoint for .txt files
@app.post("/upload", response_model=APIResponse)
async def upload_txt_file(
    file: UploadFile = File(...),
    master=Depends(verify_master_key)
):
    if not file.filename.endswith('.txt'):
        raise HTTPException(400, "Only .txt files are accepted")
    upload_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()
    original_filename = file.filename
    file_path = os.path.join(UPLOAD_DIR, original_filename)
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
    except Exception as e:
        logger.exception("File upload failed")
        raise HTTPException(500, f"Failed to save file: {e}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text_data = f.read()
    except Exception as e:
        logger.exception("Failed to read uploaded file for semantic processing")
        raise HTTPException(500, f"Failed to read file: {e}")
    json_kb = None
    logs = None
    try:
        llm_json_result = await llm_json_interpret(text_data)
        if isinstance(llm_json_result, dict):
            json_kb = llm_json_result
        else:
            try:
                json_kb = json.loads(llm_json_result)
            except Exception as e:
                raise HTTPException(400, f"LLM did not return valid JSON: {e}\nRaw LLM output: {llm_json_result}")
        SERVER_URL = "ws://localhost:8090/ws_json"
        logs = await run_in_threadpool(load_data_to_sc, SERVER_URL, json_kb, upload_id)
    except Exception as e:
        logger.exception("Semantic KB compilation failed")
        logs = str(e)
        json_kb = None
    db_path = os.path.join(UPLOAD_DIR, "db.json")
    try:
        if os.path.exists(db_path):
            with open(db_path, "r") as db_file:
                db = json.load(db_file)
        else:
            db = {"uploads": []}
        db["uploads"].append({
            "id": upload_id,
            "filename": original_filename,
            "path": file_path,
            "timestamp": timestamp
        })
        with open(db_path, "w") as db_file:
            json.dump(db, db_file, indent=2)
    except Exception as e:
        logger.exception("DB update failed")
        raise HTTPException(500, f"Failed to update DB: {e}")
    return APIResponse(
        status="success",
        message="File uploaded and semantic structures processed",
        response={
            "id": upload_id,
            "filename": file.filename,
            "path": file_path,
            "timestamp": timestamp,
            "interpreted_json": json_kb,
            "load_log": logs
        }
    )


@app.get("/files/list", response_model=APIResponse)
async def list_uploaded_files(user=Depends(get_current_user)):
    db_path = os.path.join(UPLOAD_DIR, "db.json")
    try:
        if os.path.exists(db_path):
            with open(db_path, "r") as db_file:
                db = json.load(db_file)
            allowed = get_allowed_files(user[1])
            files = [
                {
                    "id": entry["id"],
                    "filename": entry["filename"],
                    "timestamp": entry["timestamp"]
                }
                for entry in db.get("uploads", []) if entry["filename"] in allowed or user[3] == "admin"
            ]
        else:
            files = []
        return APIResponse(status="success", message="List of uploaded files", response={"files": files})
    except Exception as e:
        logger.exception("Failed to list uploads")
        return APIResponse(status="error", message=str(e), response=None)

@app.get("/files/file_content", response_model=APIResponse)
async def get_file_content(file_id: str = None, filename: str = None, user=Depends(get_current_user)):
    db_path = os.path.join(UPLOAD_DIR, "db.json")
    try:
        if os.path.exists(db_path):
            with open(db_path, "r") as db_file:
                db = json.load(db_file)
            entry = None
            if file_id:
                entry = next((item for item in db.get("uploads", []) if item["id"] == file_id), None)
            if not entry and filename:
                entry = next((item for item in db.get("uploads", []) if item["filename"] == filename), None)
            if not entry and file_id and not filename:
                entry = next((item for item in db.get("uploads", []) if item["filename"] == file_id), None)
            if not entry:
                raise HTTPException(404, f"File not found for id: {file_id} or filename: {filename}")
            allowed = get_allowed_files(user[1])
            if entry["filename"] not in allowed and user[3] != "admin":
                raise HTTPException(403, "You are not allowed to access this file")
            file_path = entry["path"]
            if not os.path.exists(file_path):
                raise HTTPException(404, f"File found in DB but not on disk: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return APIResponse(status="success", message="File content returned", response={"id": entry["id"], "filename": entry["filename"], "content": content})
        else:
            raise HTTPException(404, "No uploads found")
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("Failed to get file content")
        return APIResponse(status="error", message=str(e), response=None)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9001, reload=True)