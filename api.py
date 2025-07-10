from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request, Depends, status
from fastapi.responses import JSONResponse, HTMLResponse
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
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sc_search import kb_search


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

# Constants and configurations
UPLOAD_DIR = "uploaded_kbs"
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

# Token management functions
def create_secrets_file():
    """Initialize secrets file if it doesn't exist"""
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    if not os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH, "w") as f:
            toml.dump({"access_token_hash": ""}, f)

def token_exists() -> bool:
    """Check if a token already exists"""
    if not os.path.exists(SECRETS_PATH):
        return False
    
    with open(SECRETS_PATH, "r") as f:
        secrets_data = toml.load(f)
    
    stored_hash = secrets_data.get("access_token_hash", "")
    return bool(stored_hash)

def verify_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    """Token verification dependency"""
    # Skip authentication for open endpoints
    if not credentials:
        return
    
    # Check if token exists in system
    if not token_exists():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No token exists. Please create one first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Read token hash
    with open(SECRETS_PATH, "r") as f:
        secrets_data = toml.load(f)
    
    stored_hash = secrets_data.get("access_token_hash", "")
    if not stored_hash:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token file corrupted",
        )
    
    # Verify token
    token = credentials.credentials
    try:
        if bcrypt.checkpw(token.encode('utf-8'), stored_hash.encode('utf-8')):
            return True
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or missing token",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Endpoints
@app.get("/", include_in_schema=False)
async def landing_page():
    return {
        "app": "SC-Machine API",
        "version": app.version,
        "endpoints": {
            "/query": {"method": "POST", "description": "Query the knowledge base"},
            "/upload/kb_zip": {"method": "POST", "description": "Upload a knowledge base zip file"},
            "/create_token": {"method": "POST", "description": "Generate a new access token (only once)"},
            "/docs": {"method": "GET", "description": "Interactive API documentation"}
        }
    }

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

@app.get("/docs", include_in_schema=False)
async def get_documentation(_: bool = Depends(verify_token)):
    """Serve Swagger UI with authentication"""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - Swagger UI"
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_schema(_: bool = Depends(verify_token)):
    return app.openapi()

@app.post("/query", response_model=APIResponse)
async def process_query(
    request: QueryRequest,
    humanize: bool = Query(False),
    _: bool = Depends(verify_token)
):
    """Process a knowledge base query"""
    try:
        # Perform knowledge base search
        kb_results = kb_search(request.text)
        
        # Humanize response if requested
        if humanize:
            context = "\n".join(kb_results) if isinstance(kb_results, list) else kb_results
            response = llm_call(request.text, context)
        else:
            response = kb_results
            
        return APIResponse(
            status="success",
            message="Query processed",
            response=response
        )
        
    except Exception as e:
        logger.exception("Query processing error")
        return APIResponse(
            status="error",
            message=str(e),
            response=None
        )

@app.post("/upload/kb_zip", response_model=APIResponse)
async def upload_knowledge_base(
    file: UploadFile = File(...),
    _: bool = Depends(verify_token)
):
    """Upload and process a knowledge base zip file"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(400, "Only zip files are accepted")
    
    # Create unique extraction directory
    extract_dir = os.path.join(KB_BASE_DIR, f"kb_{uuid.uuid4().hex}")
    os.makedirs(extract_dir, exist_ok=True)
    
    try:
        # Save uploaded file
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
        
        # Extract and process
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Load SCS files
        await run_in_threadpool(load_scs_directory, extract_dir)
        
        return APIResponse(
            status="success",
            message="Knowledge base processed",
            response={"extract_dir": extract_dir}
        )
        
    except Exception as e:
        logger.exception("KB upload failed")
        return APIResponse(
            status="error",
            message=str(e),
            response=None
        )
        
    finally:
        # Cleanup extracted files
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)

@app.post("/upload/kb_nlp", response_model=APIResponse)
async def upload_kb_nlp(
    file: UploadFile = File(...),
    _: bool = Depends(verify_token)
):
    """
    Upload and process a knowledge base using NLP.
    Accepts plain text or JSON, processes it with LLM, and loads into the system.
    """

    try:
        content = await file.read()
        filename = file.filename.lower()
        text_data = content.decode('utf-8')

        # Always process with LLM to get JSON, regardless of file type
        llm_json_str = await run_in_threadpool(llm_json_interpret, text_data)

        # Accept both dict and str from llm_json_interpret
        if isinstance(llm_json_str, dict):
            json_kb = llm_json_str
        else:
            try:
                json_kb = json.loads(llm_json_str)
            except Exception as e:
                raise HTTPException(400, f"LLM did not return valid JSON: {e}\nRaw LLM output: {llm_json_str}")

        # Load JSON into KB using your interpreter
        SERVER_URL = "ws://localhost:8090/ws_json"
        logs = await run_in_threadpool(load_data_to_sc, SERVER_URL, json_kb)

        return APIResponse(
            status="success",
            message="NLP knowledge base processed and loaded",
            response={
                "interpreted_json": json_kb,
                "llm_raw_json": llm_json_str,
                "load_log": logs
            }
        )
    except Exception as e:
        logger.exception("NLP KB upload failed")
        return APIResponse(
            status="error",
            message=str(e),
            response=None
        )

from fastapi import Body

@app.post("/upload/kb_nlp_text", response_model=APIResponse)
async def upload_kb_nlp_text(
    request: QueryRequest,
    _: bool = Depends(verify_token)
):
    """
    Accepts plain text (in JSON body as {"text": ...}), processes it with LLM to JSON, and loads into SC-memory.
    """
    try:
        text_data = request.text
        llm_json_str = await run_in_threadpool(llm_json_interpret, text_data)

        # Accept both dict and str from llm_json_interpret
        if isinstance(llm_json_str, dict):
            json_kb = llm_json_str
        else:
            try:
                json_kb = json.loads(llm_json_str)
            except Exception as e:
                raise HTTPException(400, f"LLM did not return valid JSON: {e}\nRaw LLM output: {llm_json_str}")

        SERVER_URL = "ws://localhost:8090/ws_json"
        logs = await run_in_threadpool(load_data_to_sc, SERVER_URL, json_kb)

        return APIResponse(
            status="success",
            message="NLP knowledge base processed and loaded from text",
            response={
                "interpreted_json": json_kb,
                "llm_raw_json": llm_json_str,
                "load_log": logs
            }
        )
    except Exception as e:
        logger.exception("NLP KB upload (text) failed")
        return APIResponse(
            status="error",
            message=str(e),
            response=None
        )

@app.post("/upload/kb_nlp_json", response_model=APIResponse)
async def upload_kb_nlp_json(
    file: UploadFile = File(...),
    _: bool = Depends(verify_token)
):
    """
    Accepts a JSON file and loads it directly into SC-memory.
    """
    try:
        content = await file.read()
        try:
            json_kb = json.loads(content.decode('utf-8'))
        except Exception as e:
            raise HTTPException(400, f"Invalid JSON: {e}")

        SERVER_URL = "ws://localhost:8090/ws_json"
        logs = await run_in_threadpool(load_data_to_sc, SERVER_URL, json_kb)

        return APIResponse(
            status="success",
            message="NLP knowledge base processed and loaded from JSON",
            response={
                "interpreted_json": json_kb,
                "load_log": logs
            }
        )
    except Exception as e:
        logger.exception("NLP KB upload (json) failed")
        return APIResponse(
            status="error",
            message=str(e),
            response=None
        )


def load_data_to_sc(server_url: str, json_data: dict) -> list[str]:
    """
    Loads the provided JSON knowledge base into SC-memory using the py-sc-kpm stack.
    Returns a list of log strings describing what was loaded.
    """
    from sc_kpm.utils.common_utils import generate_node
    from sc_kpm.utils import generate_link, generate_binary_relation, generate_role_relation
    from sc_client.constants import sc_type
    from sc_kpm import ScKeynodes, ScServer
    import re
    import unicodedata

    def normalize_identifier(identifier: str) -> str:
        try:
            from unidecode import unidecode
            identifier = unidecode(identifier)
        except ImportError:
            identifier = unicodedata.normalize('NFKD', identifier).encode('ascii', 'ignore').decode('ascii')
        identifier = identifier.lower()
        identifier = re.sub(r'\s+', '_', identifier)
        identifier = re.sub(r'[^a-z0-9_]', '', identifier)
        return identifier

    def create_node_with_label(original_text: str):
        norm_id = normalize_identifier(original_text)
        try:
            addr = ScKeynodes[norm_id]
            log = f"Node exists: {norm_id} (from '{original_text}') -> {addr}"
        except Exception:
            try:
                addr = generate_node(sc_type.CONST_NODE)
                log = f"Node created: {norm_id} (from '{original_text}') -> {addr}"
            except Exception as e2:
                log = f"Failed to create node: {norm_id} (from '{original_text}') | {e2}"
                return None, log
        # Attach the original text as a link
        try:
            label_link = generate_link(original_text)
            generate_binary_relation(sc_type.CONST_PERM_POS_ARC, addr, label_link)
            log += f" | Label attached"
        except Exception as e:
            log += f" | Label attach failed: {e}"
        return addr, log

    logs = []
    server = ScServer(server_url)
    try:
        with server.start():
            # Add Source content as a link node
            content_id = 'Source content'
            content_addr, log = create_node_with_label(content_id)
            logs.append(log)
            try:
                content_link = generate_link(json_data[content_id])
                generate_binary_relation(sc_type.CONST_PERM_POS_ARC, content_addr, content_link)
                logs.append(f"Source content link attached: {json_data[content_id]}")
            except Exception as e:
                logs.append(f"Source content link attach failed: {e}")

            # Process all relations except membership and Source content
            for rel, subjects in json_data.items():
                if rel in ('membership', 'Source content'):
                    continue
                rel_addr, log = create_node_with_label(rel)
                logs.append(log)
                for subj, objects in subjects.items():
                    subj_addr, log = create_node_with_label(subj)
                    logs.append(log)
                    if isinstance(objects, list):
                        for obj in objects:
                            obj_addr, log = create_node_with_label(obj)
                            logs.append(log)
                            try:
                                generate_role_relation(subj_addr, obj_addr, rel_addr)
                                logs.append(f"Relation created: {subj} -[{rel}]-> {obj}")
                            except Exception as e:
                                logs.append(f"Relation failed: {subj} -[{rel}]-> {obj} | {e}")
                    else:
                        obj_addr, log = create_node_with_label(objects)
                        logs.append(log)
                        try:
                            generate_role_relation(subj_addr, obj_addr, rel_addr)
                            logs.append(f"Relation created: {subj} -[{rel}]-> {objects}")
                        except Exception as e:
                            logs.append(f"Relation failed: {subj} -[{rel}]-> {objects} | {e}")

            # Ensure all membership nodes exist
            for item in json_data.get('membership', {}):
                addr, log = create_node_with_label(item)
                logs.append(log)

    except Exception as e:
        logs.append(f"Error loading data: {e}")
    return logs


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9001, reload=True)