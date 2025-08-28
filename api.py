
# Debug/test endpoint: delete SC elements by address (no DB/file changes)
from fastapi import APIRouter
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
import aiofiles
import aiofiles.os
from userdb import create_user, verify_user, update_access_token, get_user, get_allowed_files, get_user_by_token, list_users
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from sc_search import kb_search
from memloader import load_scs_directory


# Import LLM and JSON interpretation from dedicated modules
from json_llm import llm_json_interpret
from llm import llm_call
from json_interpreter import load_data_to_sc
import json
import re
from uploadsdb import init_uploads_db, add_upload, list_uploads, get_upload_by_id, get_upload_by_filename, update_upload_logs_and_addresses
from sc_remove import remove_by_identifier
import aiofiles.os
from fastapi import Body

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
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://kb-sage.vercel.app"],  # Add your frontend URL(s) here
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
from userdb import init_db

@app.post("/register", response_model=APIResponse)
async def register_user(request: RegisterRequest, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    await init_db()
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
    await init_db()
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

@app.post("/query", response_model=APIResponse)
async def process_query(
    request: QueryRequest,
    humanize: bool = Query(False),
    user=Depends(get_current_user)
):
    """Process a knowledge base query, restrict to allowed files"""
    try:
        allowed_files = await get_allowed_files(user[1])
        kb_results = await kb_search(request.text, allowed_files=allowed_files)
        if humanize:
            context = "\n".join(kb_results) if isinstance(kb_results, list) else kb_results
            response = await llm_call(request.text, context)
        else:
            response = kb_results
        return APIResponse(status="success", message="Query processed", response=response)
    except Exception as e:
        logger.exception("Query processing error")
        return APIResponse(status="error", message=str(e), response=None)

import datetime


# Upload endpoint for .txt files (SQLite version)
@app.post("/upload", response_model=APIResponse)
async def upload_txt_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    # if not file.filename.endswith('.txt'):
    #     raise HTTPException(400, "Only .txt files are accepted")
    upload_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()
    original_filename = file.filename
    file_path = os.path.join(UPLOAD_DIR, original_filename)
    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                await buffer.write(chunk)
    except Exception as e:
        logger.exception("File upload failed")
        raise HTTPException(500, f"Failed to save file: {e}")

    # Step 1: Insert DB entry immediately (empty logs, sc_addresses)
    try:
        await init_uploads_db()
        await add_upload(upload_id, original_filename, file_path, timestamp, None, None)
    except Exception as e:
        logger.exception("DB insert failed")
        raise HTTPException(500, f"Failed to insert DB entry: {e}")

    # Step 2: Process file with AI, update logs and sc_addresses
    logs = None
    sc_addresses = None
    json_kb = None
    try:
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            text_data = await f.read()
    except Exception as e:
        logger.exception("Failed to read uploaded file for semantic processing")
        await update_upload_logs_and_addresses(upload_id, logs=str(e), sc_addresses=None)
        raise HTTPException(500, f"Failed to read file: {e}")
    try:
        llm_json_result = await llm_json_interpret(text_data)
        if isinstance(llm_json_result, dict):
            json_kb = llm_json_result
        else:
            try:
                json_kb = json.loads(llm_json_result)
            except Exception as e:
                await update_upload_logs_and_addresses(upload_id, logs=f"LLM did not return valid JSON: {e}\nRaw LLM output: {llm_json_result}", sc_addresses=None)
                raise HTTPException(400, f"LLM did not return valid JSON: {e}\nRaw LLM output: {llm_json_result}")
        SERVER_URL = "ws://localhost:8090/ws_json"
        result = await run_in_threadpool(load_data_to_sc, SERVER_URL, json_kb, upload_id)
        if isinstance(result, tuple) and len(result) == 2:
            logs, sc_addresses = result
        else:
            logs = result
            sc_addresses = None
        # Convert logs to JSON string if needed
        if logs is not None and not isinstance(logs, str):
            logs = json.dumps(logs, ensure_ascii=False)
        # Extract SC addresses from logs if not provided
        from fix_sc_addresses import extract_sc_addrs_from_logs
        if sc_addresses is None and logs:
            sc_addresses = extract_sc_addrs_from_logs(json.loads(logs) if isinstance(logs, str) else logs)
        if sc_addresses is not None:
            try:
                sc_addresses = json.dumps(sc_addresses, ensure_ascii=False)
            except Exception:
                sc_addresses = str(sc_addresses)
        await update_upload_logs_and_addresses(upload_id, logs=logs, sc_addresses=sc_addresses)
    except Exception as e:
        logger.exception("Semantic KB compilation failed")
        logs = str(e)
        await update_upload_logs_and_addresses(upload_id, logs=logs, sc_addresses=None)
        json_kb = None
    return APIResponse(
        status="success",
        message="File uploaded and semantic structures processed",
        response={
            "id": upload_id,
            "filename": file.filename,
            "path": file_path,
            "timestamp": timestamp,
            "interpreted_json": json_kb,
            "load_log": logs,
            "sc_addresses": sc_addresses
        }
    )



@app.get("/files/list", response_model=APIResponse)
async def list_uploaded_files(user=Depends(get_current_user)):
    try:
        await init_uploads_db()
        uploads = await list_uploads()
        allowed = await get_allowed_files(user[1])
        if allowed is None:
            files = [
                {"id": row[0], "filename": row[1], "timestamp": row[3]} for row in uploads
            ]
        else:
            files = [
                {"id": row[0], "filename": row[1], "timestamp": row[3]} for row in uploads if row[1] in allowed or user[3] == "admin"
            ]
        return APIResponse(status="success", message="List of uploaded files", response={"files": files})
    except Exception as e:
        logger.exception("Failed to list uploads")
        return APIResponse(status="error", message=str(e), response=None)


@app.get("/files/file_content", response_model=APIResponse)
async def get_file_content(file_id: str = None, filename: str = None, user=Depends(get_current_user)):
    try:
        await init_uploads_db()
        entry = None
        if file_id:
            entry = await get_upload_by_id(file_id)
        if not entry and filename:
            entry = await get_upload_by_filename(filename)
        if not entry and file_id and not filename:
            entry = await get_upload_by_filename(file_id)
        if not entry:
            raise HTTPException(404, f"File not found for id: {file_id} or filename: {filename}")
        allowed = await get_allowed_files(user[1])
        if allowed is not None and entry[1] not in allowed and user[3] != "admin":
            raise HTTPException(403, "You are not allowed to access this file")
        file_path = entry[2]
        if not await aiofiles.os.path.exists(file_path):
            raise HTTPException(404, f"File found in DB but not on disk: {file_path}")
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()
        return APIResponse(status="success", message="File content returned", response={"id": entry[0], "filename": entry[1], "content": content})
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("Failed to get file content")
        return APIResponse(status="error", message=str(e), response=None)

@app.get("/accounts", response_model=List[dict])
async def get_accounts(current_user=Depends(get_current_user)):
    await init_db()
    """
    List all accounts with their username, role, and last login.
    Requires admin authentication.
    """
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    users = await list_users()
    return users

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9001, reload=True)


@app.delete("/files/delete", response_model=APIResponse)
async def delete_file_and_semantics(
    filename: str = Body(..., embed=True),
    current_user=Depends(get_current_user)
):
    """
    Delete file, all semantic data (recursively), and DB entry. Maximally robust.
    """
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    await init_uploads_db()
    entry = await get_upload_by_filename(filename)
    if not entry:
        raise HTTPException(404, f"File not found: {filename}")
    upload_id = entry[0]
    file_path = entry[2]
    sc_addresses = entry[5]
    semantic_deleted = []
    semantic_errors = []
    # 1. Remove all semantic structures (root addresses)
    if sc_addresses:
        try:
            addresses = json.loads(sc_addresses)
            if isinstance(addresses, dict):
                addresses = list(addresses.values())
            elif not isinstance(addresses, list):
                addresses = [addresses]
        except Exception as e:
            semantic_errors.append({"error": f"Failed to parse sc_addresses: {e}"})
            addresses = []
        # Remove each root address (erase_elements is recursive)
        for addr in addresses:
            try:
                remove_by_identifier(str(addr))
                semantic_deleted.append(addr)
            except Exception as e:
                semantic_errors.append({"addr": addr, "error": str(e)})
        # Optionally: verify deletion (best effort)
        try:
            from sc_client.client import connect, is_connected, disconnect
            from sc_client.models import ScAddr
            url = "ws://localhost:8090/ws_json"
            connect(url)
            if is_connected():
                from sc_client.client import check_element
                for addr in addresses:
                    try:
                        exists = check_element(ScAddr(int(addr)))
                        if exists:
                            semantic_errors.append({"addr": addr, "error": "Address still exists after deletion!"})
                    except Exception as e:
                        semantic_errors.append({"addr": addr, "error": f"Verification error: {e}"})
                disconnect()
        except Exception as e:
            semantic_errors.append({"error": f"Post-delete verification failed: {e}"})
    # 2. Remove file from disk
    file_deleted = False
    if await aiofiles.os.path.exists(file_path):
        try:
            await aiofiles.os.remove(file_path)
            file_deleted = True
        except Exception as e:
            file_deleted = False
            semantic_errors.append({"error": f"Failed to delete file: {e}"})
    # 3. Remove DB entry
    import aiosqlite
    from uploadsdb import DB_PATH
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('DELETE FROM uploads WHERE id = ?', (upload_id,))
        await conn.commit()
    return APIResponse(
        status="success",
        message=f"Deleted file '{filename}', semantic data, and DB entry.",
        response={
            "file_deleted": file_deleted,
            "semantic_deleted": semantic_deleted,
            "semantic_errors": semantic_errors
        }
    )



# Test endpoint: delete SC addresses for a file by filename (no DB or file changes)
# @app.post("/test/delete_file_semantics", response_model=APIResponse)
# async def test_delete_file_semantics(
#     filename: str = Body(..., embed=True),
#     current_user=Depends(get_current_user)
# ):
#     if current_user[3] != "admin":
#         raise HTTPException(status_code=403, detail="Admin privileges required.")
#     await init_uploads_db()
#     entry = await get_upload_by_filename(filename)
#     if not entry:
#         raise HTTPException(404, f"File not found: {filename}")
#     sc_addresses = entry[5]
#     semantic_deleted = []
#     semantic_errors = []
#     if sc_addresses:
#         # Parse addresses first, then connect
#         try:
#             addresses = json.loads(sc_addresses)
#             if isinstance(addresses, dict):
#                 addresses = list(addresses.values())
#         except Exception as e:
#             semantic_errors.append({"error": f"Failed to parse sc_addresses: {e}"})
#             addresses = []
#         if addresses:
#             def delete_addrs():
#                 for addr in addresses:
#                     try:
#                         remove_by_identifier(str(addr))  # This will now use erase_elements under the hood
#                         semantic_deleted.append(addr)
#                     except Exception as e:
#                         semantic_errors.append({"addr": addr, "error": str(e)})
#             for addr in addresses:
#                 try:
#                     remove_by_identifier(str(addr))
#                     semantic_deleted.append(addr)
#                 except Exception as e:
#                     semantic_errors.append({"addr": addr, "error": str(e)})
#     return APIResponse(
#         status="success",
#         message=f"Tried to delete semantics for file '{filename}'.",
#         response={
#             "semantic_deleted": semantic_deleted,
#             "semantic_errors": semantic_errors
#         }
#     )