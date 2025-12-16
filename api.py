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
import aiosqlite

from rag_api.timing_utils import Timer, PerformanceTracker, time_block

from userdb import (
    create_user,
    verify_user,
    update_access_token,
    get_user,
    get_allowed_files,
    get_user_by_token,
    list_users,
    create_session,
    get_user_by_session_id,
    logout_session_by_id,
    cleanup_expired_sessions,
    check_file_access,
)
from orgdb import (
    init_org_db,
    create_organization,
    get_organization_by_slug,
    create_organization_membership,
)
from rag_security import SecureRAGRetriever, get_filtered_rag_context
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Import API key functionality
from api_keys import (
    init_api_keys_db,
    create_api_key,
    validate_api_key,
    check_api_key_permission,
    revoke_api_key,
    delete_api_key,
    list_api_keys,
    get_api_key_details,
    update_api_key,
    AVAILABLE_PERMISSIONS,
)

# Import plugin management
from plugin_manager import (
    init_plugins_db,
    enable_plugin,
    disable_plugin,
    is_plugin_enabled,
    list_enabled_plugins,
    create_plugin_token,
    validate_plugin_token,
    revoke_plugin_token,
    list_plugin_tokens,
    bind_plugin_resource,
    get_org_plugin_resources,
    get_organization_plugin_status,
)

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

# Import OpenCart catalog management
from opencart_catalog import (
    init_catalog_db,
    create_catalog,
    get_catalog,
    list_catalogs_by_user,
    list_catalogs_by_org,
    update_catalog_metadata,
    delete_catalog,
    upsert_catalog_products,
    get_catalog_products,
    mark_products_indexed,
    log_indexing_event,
)

# Import new advanced analytics
try:
    from analytics_core import get_analytics_core, QueryMetrics, QueryType, SecurityEventType, SecurityEvent
    from advanced_analytics_api import router as advanced_analytics_router
    from performance_analytics import PerformanceTracker
    from user_behavior_analytics import UserBehaviorAnalyzer
    from security_analytics import SecurityAnalyzer
    from analytics_middleware import AdvancedAnalyticsMiddleware
    ADVANCED_ANALYTICS_ENABLED = True
except ImportError as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"Advanced analytics not available: {e}")
    ADVANCED_ANALYTICS_ENABLED = False
    AdvancedAnalyticsMiddleware = None
    # Define stubs for type checking when analytics is not available
    get_analytics_core = None  # type: ignore
    QueryMetrics = None  # type: ignore
    QueryType = None  # type: ignore
    SecurityEventType = None  # type: ignore
    SecurityEvent = None  # type: ignore
    advanced_analytics_router = None  # type: ignore
    PerformanceTracker = None  # type: ignore
    UserBehaviorAnalyzer = None  # type: ignore
    SecurityAnalyzer = None  # type: ignore

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

# Include advanced analytics router if available
if ADVANCED_ANALYTICS_ENABLED and advanced_analytics_router:
    app.include_router(advanced_analytics_router)
    logger = logging.getLogger(__name__)
    logger.info("✅ Advanced analytics enabled")

# CORS setup for Vue.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "https://wikiai.by", "https://api.wikiai.by", "https://esell.by"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Add advanced analytics middleware if available (must be added before other middleware)
if ADVANCED_ANALYTICS_ENABLED and AdvancedAnalyticsMiddleware:
    app.add_middleware(AdvancedAnalyticsMiddleware)

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

# Initialize async resources on startup
@app.on_event("startup")
async def _startup_events():
    await init_quiz_db()
    await init_opencart_db()
    await init_catalog_db()  # Initialize OpenCart catalog management
    await init_org_db()
    await init_api_keys_db()
    await init_plugins_db()  # Initialize plugin management
    
    # Initialize advanced analytics
    if ADVANCED_ANALYTICS_ENABLED:
        try:
            analytics = get_analytics_core()
            if analytics:
                logger.info("✅ Advanced Analytics Engine Started")
                logger.info("   - 14 specialized analytics tables ready")
                logger.info("   - 40+ REST API endpoints available at /analytics/*")
                logger.info("   - Performance, user behavior, and security tracking enabled")
        except Exception as e:
            logger.error(f"Failed to initialize advanced analytics: {e}")


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
    session_id: Optional[str] = None
    model_type: Optional[str] = None
    catalog_ids: Optional[List[str]] = None  # For OpenCart searches: list of catalog IDs to filter by

class UserEditRequest(BaseModel):
    username: str
    new_username: str = ""
    password: str = ""
    role: str = ""
    allowed_files: Optional[List[str]] = None
    # Note: organization membership and roles are managed via org endpoints.


class OrganizationCreateRequest(BaseModel):
    organization_name: str
    admin_username: str
    admin_password: str


# API Key Models
class CreateAPIKeyRequest(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: List[str]
    expires_in_days: Optional[int] = None


class UpdateAPIKeyRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class APIKeyResponse(BaseModel):
    id: str
    key_prefix: str
    name: str
    description: Optional[str]
    permissions: List[str]
    created_at: str
    created_by: str
    last_used: Optional[str]
    is_active: bool
    expires_at: Optional[str]


def _slugify_org_name(name: str) -> str:
    """Generate a URL-safe slug from organization name."""
    import re

    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9\\s_-]", "", slug)
    slug = re.sub(r"[\\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug or "org-" + uuid.uuid4().hex[:8]


def _get_active_org_id(user_tuple):
    """Extract organization_id from the authenticated user session tuple."""
    try:
        if user_tuple and len(user_tuple) >= 11:
            return user_tuple[-1]
    except Exception:
        pass
    return None

# OpenCart ingest payloads
class OCProductPayload(BaseModel):
    product_id: str
    name: str
    sku: Optional[str] = None
    price: str
    special: Optional[str] = None
    description: Optional[str] = None
    url: str
    image: Optional[str] = None
    quantity: Optional[str] = None
    status: Optional[str] = None
    rating: Optional[int] = None


class OCProductsImport(BaseModel):
    success: bool
    total_products: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    products: List[OCProductPayload]

# OpenCart catalog management models
class CreateCatalogRequest(BaseModel):
    shop_name: str
    shop_url: Optional[str] = None
    description: Optional[str] = None

class CatalogResponse(BaseModel):
    catalog_id: str
    shop_name: str
    shop_url: Optional[str] = None
    total_products: int
    indexed_products: int
    is_active: bool
    created_at: str
    updated_at: str
    last_indexed_at: Optional[str] = None

class CatalogProductRequest(BaseModel):
    product_id: str
    name: str
    sku: Optional[str] = None
    price: float
    description: Optional[str] = None
    url: str
    image: Optional[str] = None
    quantity: Optional[int] = None
    status: Optional[int] = None
    rating: Optional[int] = None

class PluginIntegrationRequest(BaseModel):
    shop_name: str
    shop_url: str
    api_key: Optional[str] = None
    description: Optional[str] = None

class PluginStatus(BaseModel):
    plugin_id: str
    name: str
    is_enabled: bool
    version: str
    last_sync: Optional[str] = None
    catalog_count: int

# User authentication and authorization using session_id or API key
async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    
    # Try session_id authentication first (most secure)
    user = await get_user_by_session_id(credentials.credentials)
    if user:
        return user
    
    # Try API key authentication
    api_key_data = await validate_api_key(credentials.credentials)
    if api_key_data:
        # Return API key metadata as a special user tuple format
        # Format: (id, api_key_id, api_key_name, "api_key", permissions_list, created_at, last_used, organization_id)
        return (
            api_key_data["id"],  # id
            api_key_data["name"],  # name (not username)
            "api_key",  # type marker
            "api_key",  # role (api_key is a pseudo-role)
            api_key_data["permissions"],  # permissions list
            api_key_data["created_at"],  # created_at
            api_key_data["last_used"],  # last_used
            api_key_data["organization_id"],  # organization_id
        )
    
    # Fallback to token-based authentication for backward compatibility
    user = await get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired session_id, API key, or token.")
    return user

async def get_user_role(username: str):
    user = await get_user(username)
    if user:
        return user[3]  # role
    return None

async def check_api_key_operation_permission(current_user, operation: str) -> bool:
    """
    Check if the current user (API key or regular user) has permission for an operation.
    
    Args:
        current_user: The user tuple from get_current_user dependency
        operation: The operation to check (e.g., 'search', 'upload', 'edit_users')
    
    Returns:
        True if permitted, False otherwise
    """
    # Regular users (non-API-key) always have permission (role-based control still applies)
    if current_user[3] != "api_key":
        return True
    
    # API key users: check if the key has the required permission
    permissions = current_user[4]  # permissions list is at index 4
    return operation in permissions

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

# === OpenCart ingest helpers ===
OC_DB_PATH = os.path.join(os.path.dirname(__file__), "integration_toolkit", "OpenCart", "Backend", "opencart_products.db")


async def init_opencart_db():
    os.makedirs(os.path.dirname(OC_DB_PATH), exist_ok=True)
    async with aiosqlite.connect(OC_DB_PATH) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sku TEXT,
                price REAL,
                special TEXT,
                description TEXT,
                url TEXT,
                image TEXT,
                quantity INTEGER,
                status INTEGER,
                rating INTEGER,
                updated_at TEXT NOT NULL
            )
            """
        )
        await conn.commit()


def _oc_parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except Exception:
        return None


def _oc_parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


async def upsert_opencart_products(products: List[OCProductPayload]) -> Dict[str, int]:
    inserted = 0
    updated = 0
    now = datetime.datetime.utcnow().isoformat()

    async with aiosqlite.connect(OC_DB_PATH) as conn:
        for product in products:
            pid = _oc_parse_int(product.product_id)
            if pid is None:
                continue

            price = _oc_parse_float(product.price)
            qty = _oc_parse_int(product.quantity)
            status = _oc_parse_int(product.status)
            rating = _oc_parse_int(str(product.rating)) if product.rating is not None else None

            update_cursor = await conn.execute(
                """
                UPDATE products SET
                    name=?,
                    sku=?,
                    price=?,
                    special=?,
                    description=?,
                    url=?,
                    image=?,
                    quantity=?,
                    status=?,
                    rating=?,
                    updated_at=?
                WHERE product_id=?
                """,
                (
                    product.name,
                    product.sku,
                    price,
                    product.special,
                    product.description,
                    product.url,
                    product.image,
                    qty,
                    status,
                    rating,
                    now,
                    pid,
                ),
            )

            if update_cursor.rowcount:
                updated += 1
            else:
                await conn.execute(
                    """
                    INSERT INTO products (
                        product_id, name, sku, price, special, description, url,
                        image, quantity, status, rating, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pid,
                        product.name,
                        product.sku,
                        price,
                        product.special,
                        product.description,
                        product.url,
                        product.image,
                        qty,
                        status,
                        rating,
                        now,
                    ),
                )
                inserted += 1
        await conn.commit()

    return {"inserted": inserted, "updated": updated, "received": len(products)}

# ==================== API KEY MANAGEMENT ENDPOINTS ====================

@app.post("/api-keys/create", response_model=APIResponse)
async def create_api_key_endpoint(
    request: CreateAPIKeyRequest,
    current_user=Depends(get_current_user)
):
    """Create a new API key for the user's organization (admin only)."""
    try:
        # Only admins can create API keys
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required to create API keys.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        username = current_user[1]
        
        # Create the API key
        full_key, key_id = await create_api_key(
            organization_id=organization_id,
            created_by=username,
            name=request.name,
            permissions=request.permissions,
            description=request.description,
            expires_in_days=request.expires_in_days,
        )
        
        logger.info(f"API key '{request.name}' created by {username} for org {organization_id}")
        
        # Return response with full key (only shown once!)
        return APIResponse(
            status="success",
            message="API key created successfully. Save the key now - it won't be shown again!",
            response={
                "key_id": key_id,
                "full_key": full_key,
                "name": request.name,
                "permissions": request.permissions,
                "created_by": username,
                "created_at": datetime.datetime.utcnow().isoformat(),
                "warning": "This is the only time the full key will be displayed. Store it securely."
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create API key")
        return APIResponse(status="error", message=str(e), response=None)


@app.get("/api-keys/list", response_model=APIResponse)
async def list_api_keys_endpoint(
    current_user=Depends(get_current_user)
):
    """List all API keys for the user's organization (admin only)."""
    try:
        # Only admins can list API keys
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required to list API keys.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        keys = await list_api_keys(organization_id)
        
        return APIResponse(
            status="success",
            message="API keys retrieved",
            response={
                "keys": keys,
                "total": len(keys)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list API keys")
        return APIResponse(status="error", message=str(e), response=None)


@app.get("/api-keys/{key_id}", response_model=APIResponse)
async def get_api_key_endpoint(
    key_id: str,
    current_user=Depends(get_current_user)
):
    """Get details of a specific API key (admin only)."""
    try:
        # Only admins can view API key details
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        key_details = await get_api_key_details(key_id)
        if not key_details:
            raise HTTPException(status_code=404, detail="API key not found.")
        
        # Verify ownership
        if key_details["organization_id"] != organization_id:
            raise HTTPException(status_code=403, detail="Cannot access API keys from other organizations.")
        
        return APIResponse(
            status="success",
            message="API key details retrieved",
            response=key_details
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get API key details")
        return APIResponse(status="error", message=str(e), response=None)


@app.put("/api-keys/{key_id}", response_model=APIResponse)
async def update_api_key_endpoint(
    key_id: str,
    request: UpdateAPIKeyRequest,
    current_user=Depends(get_current_user)
):
    """Update an API key's metadata (admin only)."""
    try:
        # Only admins can update API keys
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        # Verify ownership
        key_details = await get_api_key_details(key_id)
        if not key_details:
            raise HTTPException(status_code=404, detail="API key not found.")
        
        if key_details["organization_id"] != organization_id:
            raise HTTPException(status_code=403, detail="Cannot update API keys from other organizations.")
        
        # Update the key
        success = await update_api_key(
            key_id=key_id,
            name=request.name,
            description=request.description,
            permissions=request.permissions,
        )
        
        if not success:
            return APIResponse(status="success", message="No changes made", response=None)
        
        logger.info(f"API key {key_id} updated by {current_user[1]}")
        
        return APIResponse(
            status="success",
            message="API key updated successfully",
            response={"key_id": key_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update API key")
        return APIResponse(status="error", message=str(e), response=None)


@app.post("/api-keys/{key_id}/revoke", response_model=APIResponse)
async def revoke_api_key_endpoint(
    key_id: str,
    current_user=Depends(get_current_user)
):
    """Revoke (disable) an API key (admin only)."""
    try:
        # Only admins can revoke API keys
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        # Verify ownership
        key_details = await get_api_key_details(key_id)
        if not key_details:
            raise HTTPException(status_code=404, detail="API key not found.")
        
        if key_details["organization_id"] != organization_id:
            raise HTTPException(status_code=403, detail="Cannot revoke API keys from other organizations.")
        
        await revoke_api_key(key_id)
        
        logger.info(f"API key {key_id} revoked by {current_user[1]}")
        
        return APIResponse(
            status="success",
            message="API key revoked successfully",
            response={"key_id": key_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to revoke API key")
        return APIResponse(status="error", message=str(e), response=None)


@app.delete("/api-keys/{key_id}", response_model=APIResponse)
async def delete_api_key_endpoint(
    key_id: str,
    current_user=Depends(get_current_user)
):
    """Delete an API key permanently (admin only)."""
    try:
        # Only admins can delete API keys
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        # Verify ownership
        key_details = await get_api_key_details(key_id)
        if not key_details:
            raise HTTPException(status_code=404, detail="API key not found.")
        
        if key_details["organization_id"] != organization_id:
            raise HTTPException(status_code=403, detail="Cannot delete API keys from other organizations.")
        
        await delete_api_key(key_id)
        
        logger.info(f"API key {key_id} deleted by {current_user[1]}")
        
        return APIResponse(
            status="success",
            message="API key deleted successfully",
            response={"key_id": key_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete API key")
        return APIResponse(status="error", message=str(e), response=None)


@app.get("/api-keys/permissions/list", response_model=APIResponse)
async def get_available_permissions(
    current_user=Depends(get_current_user)
):
    """Get list of available API key permissions."""
    try:
        return APIResponse(
            status="success",
            message="Available permissions retrieved",
            response={
                "permissions": AVAILABLE_PERMISSIONS,
                "total": len(AVAILABLE_PERMISSIONS)
            }
        )
    except Exception as e:
        logger.exception("Failed to get available permissions")
        return APIResponse(status="error", message=str(e), response=None)

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
            "/opencart/products/import": {"method": "POST", "description": "Import OpenCart products JSON (auth required)"},
            "/docs": {"method": "GET", "description": "Interactive API documentation"}
        }
    }


async def _get_organization_id_from_request(
    current_user,
    plugin_token: Optional[str] = None
) -> str:
    """
    Extract organization_id from the current_user context using:
    1. Plugin token (highest priority for ingestion)
    2. API key from current_user
    3. Session user's organization
    
    Returns organization_id or raises HTTPException.
    """
    # If explicit plugin token provided, validate and use it
    if plugin_token:
        token_data = await validate_plugin_token(plugin_token)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid or expired plugin token")
        return token_data["organization_id"]
    
    # Check if current_user is API key auth (tuple form)
    if isinstance(current_user, tuple) and len(current_user) >= 8:
        return current_user[7]  # organization_id from API key auth
    
    # Fallback to session user's organization
    organization_id = _get_active_org_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=400, detail="Organization context required")
    
    return organization_id


@app.post("/opencart/products/import", response_model=APIResponse)
async def import_opencart_products(
    payload: OCProductsImport,
    current_user=Depends(get_current_user),
    plugin_token: Optional[str] = None,
):
    """
    Import OpenCart products with organization isolation.
    
    Supports plugin token for shop-specific ingestion.
    Organization is determined from:
    - plugin_token (if provided)
    - API key organization (if authenticated with API key)
    - Session user's organization
    """
    try:
        # Determine organization context
        organization_id = await _get_organization_id_from_request(
            current_user,
            plugin_token
        )
        
        # For legacy OpenCart endpoint, we only store in legacy DB, not new catalog system
        stats = await upsert_opencart_products(payload.products)
        
        logger.info(
            f"Imported {stats['received']} OpenCart products for org {organization_id}"
        )
        
        return APIResponse(
            status="success",
            message="Products imported",
            response={
                **stats,
                "organization_id": organization_id
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Backward-compatible alias if clients POST to /opencart directly
@app.post("/opencart", response_model=APIResponse, include_in_schema=False)
async def import_opencart_products_alias(
    payload: OCProductsImport,
    current_user=Depends(get_current_user),
    plugin_token: Optional[str] = None,
):
    """Backward-compatible alias for /opencart/products/import"""
    try:
        organization_id = await _get_organization_id_from_request(
            current_user,
            plugin_token
        )
        
        stats = await upsert_opencart_products(payload.products)
        
        logger.info(
            f"Imported {stats['received']} OpenCart products for org {organization_id}"
        )
        
        return APIResponse(
            status="success",
            message="Products imported",
            response={
                **stats,
                "organization_id": organization_id
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Additional alias for legacy clients calling /opencart/sync
@app.post("/opencart/sync", response_model=APIResponse, include_in_schema=False)
async def import_opencart_products_sync(
    payload: OCProductsImport,
    current_user=Depends(get_current_user),
    plugin_token: Optional[str] = None,
):
    """Backward-compatible alias for /opencart/products/import"""
    try:
        organization_id = await _get_organization_id_from_request(
            current_user,
            plugin_token
        )
        
        stats = await upsert_opencart_products(payload.products)
        
        logger.info(
            f"Imported {stats['received']} OpenCart products for org {organization_id}"
        )
        
        return APIResponse(
            status="success",
            message="Products imported",
            response={
                **stats,
                "organization_id": organization_id
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PLUGIN MANAGEMENT ====================

@app.get("/plugins/status", response_model=APIResponse, tags=["Plugins"])
async def get_plugins_status(current_user=Depends(get_current_user)):
    """Get enabled/disabled status of all plugins for the user's organization"""
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required")
        
        status = await get_organization_plugin_status(organization_id)
        return APIResponse(
            status="success",
            message="Plugin status retrieved",
            response=status,
        )
    except Exception as e:
        logger.error(f"Error getting plugin status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/plugins/enable", response_model=APIResponse, tags=["Plugins"])
async def enable_org_plugin(
    plugin_type: str = Query(...),
    current_user=Depends(get_current_user)
):
    """Enable a plugin for the organization"""
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required")
        
        await enable_plugin(organization_id, plugin_type)
        return APIResponse(
            status="success",
            message=f"Plugin {plugin_type} enabled",
        )
    except Exception as e:
        logger.error(f"Error enabling plugin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/plugins/disable", response_model=APIResponse, tags=["Plugins"])
async def disable_org_plugin(
    plugin_type: str = Query(...),
    current_user=Depends(get_current_user)
):
    """Disable a plugin for the organization"""
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required")
        
        await disable_plugin(organization_id, plugin_type)
        return APIResponse(
            status="success",
            message=f"Plugin {plugin_type} disabled",
        )
    except Exception as e:
        logger.error(f"Error disabling plugin: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/plugins/tokens", response_model=APIResponse, tags=["Plugins"])
async def get_plugin_tokens(
    plugin_type: Optional[str] = Query(None),
    current_user=Depends(get_current_user)
):
    """List plugin tokens for the organization"""
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required")
        
        tokens = await list_plugin_tokens(organization_id, plugin_type)
        return APIResponse(
            status="success",
            message="Plugin tokens retrieved",
            response=tokens,
        )
    except Exception as e:
        logger.error(f"Error getting plugin tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/plugins/tokens/create", response_model=APIResponse, tags=["Plugins"])
async def create_shop_token(
    plugin_type: str = Query(...),
    shop_name: Optional[str] = Query(None),
    shop_url: Optional[str] = Query(None),
    current_user=Depends(get_current_user)
):
    """Create a new API token for a shop/plugin resource"""
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required")
        
        token = await create_plugin_token(
            organization_id,
            plugin_type,
            shop_name=shop_name,
            shop_url=shop_url,
        )
        
        return APIResponse(
            status="success",
            message=f"API token created for {plugin_type}",
            response={"token": token},
        )
    except Exception as e:
        logger.error(f"Error creating plugin token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/plugins/tokens/revoke", response_model=APIResponse, tags=["Plugins"])
async def revoke_shop_token(
    token_id: str = Query(...),
    current_user=Depends(get_current_user)
):
    """Revoke a plugin token"""
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required")
        
        # TODO: Verify token belongs to the organization
        await revoke_plugin_token(token_id)
        
        return APIResponse(
            status="success",
            message="Plugin token revoked",
        )
    except Exception as e:
        logger.error(f"Error revoking plugin token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== OPENCART SHOP MANAGEMENT ====================

@app.post("/shops/register", response_model=APIResponse, tags=["OpenCart Shops"])
async def register_opencart_shop(
    request: CreateCatalogRequest,
    current_user=Depends(get_current_user),
):
    """
    Register an OpenCart shop without creating a catalog.
    
    This endpoint stores the shop connection information. Products are not
    loaded until the user creates a catalog from the shop.
    """
    try:
        user_id = current_user[0]
        organization_id = _get_active_org_id(current_user)
        
        from opencart_catalog import register_shop
        shop_id = await register_shop(
            shop_name=request.shop_name,
            shop_url=request.shop_url,
            user_id=user_id,
            organization_id=organization_id
        )
        
        logger.info(f"Registered shop {shop_id} for org {organization_id}")
        
        return APIResponse(
            status="success",
            message=f"Shop registered: {request.shop_name}",
            response={"shop_id": shop_id}
        )
    except Exception as e:
        logger.error(f"Error registering shop: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/shops", response_model=APIResponse, tags=["OpenCart Shops"])
async def list_shops(
    current_user=Depends(get_current_user),
):
    """
    List all registered OpenCart shops for the current user/organization.
    """
    try:
        user_id = current_user[0]
        organization_id = _get_active_org_id(current_user)
        
        from opencart_catalog import list_shops_by_user
        shops = await list_shops_by_user(user_id, organization_id)
        
        return APIResponse(
            status="success",
            message=f"Found {len(shops)} shops",
            response={"shops": shops}
        )
    except Exception as e:
        logger.error(f"Error listing shops: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/shops/{shop_id}", response_model=APIResponse, tags=["OpenCart Shops"])
async def delete_shop(
    shop_id: str,
    current_user=Depends(get_current_user),
):
    """
    Delete/unregister an OpenCart shop.
    """
    try:
        from opencart_catalog import get_shop, delete_shop
        
        shop = await get_shop(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Verify ownership
        if shop["user_id"] != current_user[0]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        await delete_shop(shop_id)
        
        return APIResponse(
            status="success",
            message="Shop deleted"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting shop: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/shops/{shop_id}/catalogs", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def create_catalog_from_shop(
    shop_id: str,
    current_user=Depends(get_current_user),
):
    """
    Create a catalog from a registered shop and load products.
    
    This is called when the user wants to import products from a shop.
    """
    try:
        user_id = current_user[0]
        organization_id = _get_active_org_id(current_user)
        
        from opencart_catalog import get_shop, create_catalog, load_opencart_products_from_db
        
        shop = await get_shop(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        # Verify ownership
        if shop["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Create catalog
        catalog_id = await create_catalog(
            shop_name=shop["shop_name"],
            shop_url=shop["shop_url"],
            user_id=user_id,
            organization_id=organization_id,
            description=None
        )
        
        # Load products from OpenCart database
        try:
            opencart_db_path = os.path.join(os.path.dirname(__file__), "integration_toolkit", "OpenCart", "Backend", "opencart_products.db")
            inserted, updated = await load_opencart_products_from_db(opencart_db_path, catalog_id, shop["shop_url"])
            logger.info(f"Loaded {inserted} new products from shop {shop_id}")
        except Exception as load_error:
            logger.warning(f"Failed to load products from OpenCart database: {load_error}")
            inserted = 0
        
        return APIResponse(
            status="success",
            message=f"Catalog created from shop. {inserted} products loaded.",
            response={
                "catalog_id": catalog_id,
                "products_loaded": inserted
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating catalog from shop: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ENHANCED OPENCART CATALOG MANAGEMENT ====================

@app.post("/catalogs/create", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def create_new_catalog(
    request: CreateCatalogRequest,
    current_user=Depends(get_current_user),
):
    """
    Create a new OpenCart catalog.
    
    This endpoint creates a new catalog entry that can store multiple products
    with their descriptions indexed for semantic search.
    Also auto-generates an API key and loads products from the OpenCart database.
    """
    try:
        user_id = current_user[0]
        organization_id = _get_active_org_id(current_user)
        
        catalog_id = await create_catalog(
            shop_name=request.shop_name,
            shop_url=request.shop_url,
            user_id=user_id,
            organization_id=organization_id,
            description=request.description
        )
        
        # Auto-generate API key for this catalog
        api_key = None
        try:
            from api_keys import create_api_key as create_api_key_func
            api_key = await create_api_key_func(
                user_id=user_id,
                organization_id=organization_id,
                name=f"{request.shop_name} API Key",
                permissions=["catalogs:read", "catalogs:write", "products:read", "products:write"]
            )
            logger.info(f"Created API key for catalog {catalog_id}")
        except Exception as api_key_error:
            logger.warning(f"Failed to create API key for catalog: {api_key_error}")
        
        # Load products from OpenCart database
        try:
            from opencart_catalog import load_opencart_products_from_db
            opencart_db_path = os.path.join(os.path.dirname(__file__), "integration_toolkit", "OpenCart", "Backend", "opencart_products.db")
            inserted, updated = await load_opencart_products_from_db(opencart_db_path, catalog_id, request.shop_url)
            logger.info(f"Loaded {inserted} new products and updated {updated} existing products")
        except Exception as load_error:
            logger.warning(f"Failed to load products from OpenCart database: {load_error}")
        
        return APIResponse(
            status="success",
            message=f"Catalog created: {request.shop_name}. {inserted if 'inserted' in locals() else 0} products loaded.",
            response={
                "catalog_id": catalog_id,
                "api_key": api_key if api_key else None,
                "products_loaded": inserted if 'inserted' in locals() else 0
            }
        )
    except Exception as e:
        logger.error(f"Error creating catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/catalogs/{catalog_id}", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def get_catalog_details(
    catalog_id: str,
    current_user=Depends(get_current_user),
):
    """
    Get catalog details and statistics.
    
    Returns metadata about the catalog including product counts and indexing status.
    """
    try:
        catalog = await get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        
        # Verify access
        if catalog["user_id"] != current_user[0]:
            org_id = _get_active_org_id(current_user)
            if not org_id or catalog["organization_id"] != org_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        return APIResponse(
            status="success",
            message="Catalog retrieved",
            response=catalog
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/catalogs", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def list_user_catalogs(
    current_user=Depends(get_current_user),
):
    """
    List all catalogs for the current user.
    
    Returns paginated list of all catalogs owned by or accessible to the user.
    """
    try:
        user_id = current_user[0]
        organization_id = _get_active_org_id(current_user)
        
        catalogs = await list_catalogs_by_user(user_id, organization_id)
        
        return APIResponse(
            status="success",
            message=f"Retrieved {len(catalogs)} catalogs",
            response={"catalogs": catalogs, "count": len(catalogs)}
        )
    except Exception as e:
        logger.error(f"Error listing catalogs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _index_products_with_metadata(products: List[Dict], catalog_id: str, catalog: Dict, organization_id: str) -> tuple:
    """
    Index products to Chroma with rich metadata.
    
    Creates vector embeddings for product descriptions and stores metadata
    (name, price, SKU, URL, rating) for retrieval and filtering.
    """
    indexed_ids = []
    failed_ids = []
    
    for product in products:
        try:
            # Create enriched document content for embedding
            doc_content = f"""
Product Name: {product['name']}
Description: {product['description']}
Price: ${product['price']}
SKU: {product['sku']}
Product URL: {product['url']}
Customer Rating: {product.get('rating', 0)}/5
Store: {catalog['shop_name']}
"""
            
            # Use product_id as document identifier
            doc_id = f"opencart_{catalog_id}_{product['product_id']}"
            
            # Prepare metadata for storage
            metadata = {
                "product_id": str(product['product_id']),
                "catalog_id": catalog_id,
                "name": product['name'],
                "sku": product['sku'],
                "price": str(product['price']),
                "special_price": str(product.get('special_price')) if product.get('special_price') else None,
                "description": product['description'][:500],  # First 500 chars
                "url": product['url'],
                "image": product.get('image', ''),
                "quantity": str(product.get('quantity', 0)),
                "rating": str(product.get('rating', 0)),
                "status": str(product.get('status', 1)),
                "shop_name": catalog['shop_name'],
                "organization_id": organization_id,
                "indexed_at": datetime.datetime.utcnow().isoformat()
            }
            
            # Index to Chroma with metadata
            from rag_api.chroma_utils import index_document_to_chroma
            import tempfile
            
            # Create temporary file for indexing
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(doc_content)
                temp_path = f.name
            
            try:
                # Index with metadata embedded in system
                index_document_to_chroma(
                    file_path=temp_path,
                    file_id=doc_id,
                    organization_id=organization_id,
                    metadata=metadata  # Pass metadata to store with embedding
                )
                indexed_ids.append(product['product_id'])
                logger.info(f"Indexed product {product['product_id']} ({product['name']})")
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            logger.error(f"Failed to index product {product['product_id']}: {e}")
            failed_ids.append(product['product_id'])
    
    return indexed_ids, failed_ids


@app.post("/catalogs/{catalog_id}/products/import", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def import_catalog_products(
    catalog_id: str,
    products: List[CatalogProductRequest],
    current_user=Depends(get_current_user),
    plugin_token: Optional[str] = None,
):
    """
    Import products into a catalog with automatic indexation.
    
    Enforces organization isolation using plugin token or API key.
    Stores products in database with vector embeddings for semantic search.
    Metadata (name, price, description, etc.) is stored with organization_id.
    """
    try:
        # Get organization context from plugin token or API key
        organization_id = await _get_organization_id_from_request(
            current_user,
            plugin_token
        )
        
        user_id = current_user[0] if not isinstance(current_user, tuple) or len(current_user) < 3 else current_user[0]
        
        # Verify catalog exists and belongs to the organization
        catalog = await get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        
        # Enforce organization isolation: catalog must belong to user's organization
        if catalog.get("organization_id") and catalog["organization_id"] != organization_id:
            raise HTTPException(status_code=403, detail="Catalog belongs to different organization")
        
        # For new catalogs, set the organization
        if not catalog.get("organization_id"):
            await update_catalog_metadata(
                catalog_id,
                organization_id=organization_id
            )
        
        # Convert to dict for insertion
        product_dicts = [p.dict() for p in products]
        
        # Store products in database with organization_id
        inserted, updated = await upsert_catalog_products(
            catalog_id=catalog_id,
            products=product_dicts,
            user_id=user_id,
            organization_id=organization_id
        )
        
        logger.info(f"Imported {inserted} new products, updated {updated} existing for catalog {catalog_id}")
        
        # Automatically index products with metadata
        indexed_ids, failed_ids = await _index_products_with_metadata(
            product_dicts,
            catalog_id,
            catalog,
            organization_id
        )
        
        # Update indexed status in database
        if indexed_ids:
            await mark_products_indexed(catalog_id, indexed_ids)
        
        # Log the indexing event
        await log_indexing_event(
            catalog_id=catalog_id,
            product_ids=list(set(indexed_ids + failed_ids)),
            indexed_count=len(indexed_ids),
            failed_count=len(failed_ids),
            status="completed" if len(failed_ids) == 0 else "partial",
            error_message=f"Failed to index {len(failed_ids)} products" if failed_ids else None
        )
        
        return APIResponse(
            status="success",
            message=f"Products imported and indexed: {len(indexed_ids)} indexed, {len(failed_ids)} failed",
            response={
                "catalog_id": catalog_id,
                "inserted": inserted,
                "updated": updated,
                "indexed": len(indexed_ids),
                "failed_to_index": len(failed_ids),
                "total": len(products)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/catalogs/{catalog_id}/products", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def list_catalog_products(
    catalog_id: str,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    indexed_only: bool = Query(False),
    current_user=Depends(get_current_user),
):
    """
    List products in a catalog.
    
    Supports pagination and filtering for indexed products.
    """
    try:
        # Verify access
        catalog = await get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        
        products, total = await get_catalog_products(
            catalog_id=catalog_id,
            limit=limit,
            offset=offset,
            indexed_only=indexed_only
        )
        
        return APIResponse(
            status="success",
            message=f"Retrieved {len(products)} products",
            response={
                "catalog_id": catalog_id,
                "products": products,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing products: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/catalogs/{catalog_id}/index", response_model=APIResponse, tags=["OpenCart Catalogs"])
@app.post("/catalogs/{catalog_id}/index", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def index_catalog_descriptions(
    catalog_id: str,
    current_user=Depends(get_current_user),
):
    """
    Index product descriptions from a catalog to Chroma vector database.
    
    This endpoint processes all unindexed products in the catalog and creates
    vector embeddings of their descriptions for semantic search.
    """
    try:
        # Verify access
        catalog = await get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        if catalog["user_id"] != current_user[0]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        organization_id = _get_active_org_id(current_user)
        
        # Get unindexed products
        products, _ = await get_catalog_products(
            catalog_id=catalog_id,
            limit=10000,
            indexed_only=False
        )
        
        unindexed = [p for p in products if not p.get("indexed", False)]
        
        if not unindexed:
            return APIResponse(
                status="success",
                message="No products to index",
                response={
                    "catalog_id": catalog_id,
                    "indexed_count": 0,
                    "failed_count": 0
                }
            )
        
        # Convert to proper dict format for indexing
        unindexed_dicts = [dict(p) for p in unindexed]
        
        # Index products using the same algorithm as file uploads
        indexed_ids, failed_ids = await _index_products_with_metadata(
            unindexed_dicts,
            catalog_id,
            catalog,
            organization_id
        )
        
        # Update indexed status in database
        if indexed_ids:
            await mark_products_indexed(catalog_id, indexed_ids)
        
        # Log the indexing event
        await log_indexing_event(
            catalog_id=catalog_id,
            product_ids=list(set(indexed_ids + failed_ids)),
            indexed_count=len(indexed_ids),
            failed_count=len(failed_ids),
            status="completed" if len(failed_ids) == 0 else "partial",
            error_message=f"Failed to index {len(failed_ids)} products" if failed_ids else None
        )
        
        return APIResponse(
            status="success",
            message=f"Indexed {len(indexed_ids)} products" + (f", {len(failed_ids)} failed" if failed_ids else ""),
            response={
                "catalog_id": catalog_id,
                "indexed_count": len(indexed_ids),
                "failed_count": len(failed_ids),
                "total": len(unindexed)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/catalogs/{catalog_id}", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def update_catalog(
    catalog_id: str,
    updates: Dict[str, Any] = Body(...),
    current_user=Depends(get_current_user),
):
    """
    Update catalog metadata.
    
    Allows updating shop_name, shop_url, description, and is_active status.
    """
    try:
        # Verify access
        catalog = await get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        if catalog["user_id"] != current_user[0]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await update_catalog_metadata(catalog_id, **updates)
        
        if success:
            return APIResponse(
                status="success",
                message="Catalog updated",
                response={"catalog_id": catalog_id}
            )
        else:
            return APIResponse(
                status="error",
                message="No changes made",
                response={}
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/catalogs/{catalog_id}", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def delete_catalog_endpoint(
    catalog_id: str,
    current_user=Depends(get_current_user),
):
    """
    Delete a catalog and all its products.
    
    This operation is irreversible.
    """
    try:
        # Verify access
        catalog = await get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        if catalog["user_id"] != current_user[0]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await delete_catalog(catalog_id)
        
        if success:
            logger.info(f"Deleted catalog {catalog_id}")
            return APIResponse(
                status="success",
                message="Catalog deleted",
                response={"catalog_id": catalog_id}
            )
        else:
            return APIResponse(
                status="error",
                message="Catalog not found",
                response={}
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/catalogs/{catalog_id}/search", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def search_catalog_products(
    catalog_id: str,
    query: str = Query(..., min_length=1),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    use_semantic: bool = Query(True, description="Use semantic search (default: True)"),
    min_relevance: float = Query(0.2, ge=0, le=1, description="Minimum relevance score (0-1)"),
    current_user=Depends(get_current_user),
):
    """
    Search products in a catalog using semantic search.
    
    Performs a hybrid semantic + keyword search across product data.
    """
    try:
        # Verify catalog access
        catalog = await get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        
        if use_semantic:
            # Use semantic search
            from opencart_semantic_search import search_products_semantic
            
            # Get organization ID from user token
            organization_id = None
            if hasattr(current_user, 'organization_id'):
                organization_id = current_user.organization_id
            
            # Search products using semantic search
            products = await search_products_semantic(
                query=query,
                catalog_ids=[catalog_id],
                organization_id=organization_id,
                limit=limit,
                min_relevance_score=min_relevance
            )
            
            # Format results for consistency
            results = []
            for product in products:
                results.append({
                    "content": f"{product.get('name', '')}\n{product.get('description', '')}",
                    "metadata": product,
                    "relevance": product.get('similarity_score', 0.5),  # Use similarity score as relevance
                    "score": product.get('similarity_score', 0.5)  # For backward compatibility
                })
        else:
            # Fallback to direct database search
            from opencart_catalog import search_products_in_catalogs
            
            products = await search_products_in_catalogs(
                catalog_ids=[catalog_id],
                search_term=query,
                limit=limit,
                offset=offset
            )
            
            # Format results
            results = []
            for product in products:
                results.append({
                    "content": f"{product.get('name', '')}\n{product.get('description', '')}",
                    "metadata": product,
                    "relevance": "high"
                })
        
        return APIResponse(
            status="success",
            message=f"Found {len(results)} matching products",
            response={
                "catalog_id": catalog_id,
                "query": query,
                "results": results,
                "count": len(results),
                "limit": limit,
                "offset": offset,
                "use_semantic": use_semantic,
                "min_relevance": min_relevance if use_semantic else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching catalog: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# User registration (requires master key)
@app.post("/register", response_model=APIResponse)
async def register_user(request: RegisterRequest, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    # Allow registration if admin is authenticated or valid master key is provided via Bearer
    is_admin = False
    is_master = False
    admin_user = None
    if credentials:
        admin_user = await get_user_by_token(credentials.credentials)
        if admin_user and admin_user[3] == "admin":
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
    
    # Get organization_id from the authenticated admin
    organization_id = None
    if is_admin and admin_user:
        org_id = _get_active_org_id(admin_user)
        organization_id = org_id
    
    await create_user(request.username, request.password, request.role, request.allowed_files, organization_id=organization_id)
    return APIResponse(status="success", message="User registered", response={})

# Handle CORS preflight requests for all endpoints
@app.options("/{full_path:path}")
async def preflight_handler(full_path: str, request: Request):
    """Handle CORS preflight OPTIONS requests"""
    origin = request.headers.get("origin", "*")
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://kb-sage.vercel.app",
        "https://meet-tadpole-resolved.ngrok-free.app"
    ]
    
    # Allow requests from known origins or wildcard
    allowed_origin = origin if origin in allowed_origins or origin == "*" else "*"
    
    return JSONResponse(
        status_code=200,
        content={},
        headers={
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, ngrok-skip-browser-warning",
            "Access-Control-Max-Age": "3600",
            "Access-Control-Allow-Credentials": "true"
        }
    )

# User login with session_id management
@app.post("/login", response_model=TokenRoleResponse)
async def login_user(request: LoginRequest, request_obj: Request):
    client_ip = request_obj.client.host if request_obj and request_obj.client else None
    
    if not await verify_user(request.username, request.password):
        # Log failed login attempt
        log_security_event(
            event_type="failed_login",
            ip_address=client_ip or "unknown",
            user_id=request.username,
            details={"reason": "Invalid credentials"},
            severity="medium"
        )
        
        # Log to advanced analytics if available
        if ADVANCED_ANALYTICS_ENABLED:
            try:
                analytics = get_analytics_core()
                if analytics:
                    security_event = SecurityEvent(
                        event_type=SecurityEventType.FAILED_LOGIN,
                        user_id=request.username,
                        ip_address=client_ip or "unknown",
                        severity="medium",
                        details={"reason": "Invalid credentials"},
                        timestamp=datetime.datetime.now().isoformat()
                    )
                    analytics.log_security_event(security_event)
            except Exception as e:
                logger.warning(f"Failed to log security event to advanced analytics: {e}")
        
        return TokenRoleResponse(status="error", message="Invalid username or password", token=None, role=None)
    
    # Generate new session_id (UUID-based for better security)
    session_id = str(uuid.uuid4())
    
    # Get user's organization_id from database
    user = await get_user(request.username)
    organization_id = user[7] if user and len(user) > 7 else None  # organization_id is at index 7
    
    # Create session in database with session_id as primary key.
    # Include organization_id from user's profile
    await create_session(request.username, session_id, expires_hours=24, organization_id=organization_id)
    
    # Also update legacy access token for backward compatibility
    if session_id:
        # Only pass token if available, don't pass None
        try:
            await update_access_token(request.username, session_id)
        except Exception as e:
            logger.warning(f"Failed to update access token: {e}")
    
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
    
    # Log to advanced analytics if available
    if ADVANCED_ANALYTICS_ENABLED:
        try:
            analytics = get_analytics_core()
            if analytics:
                security_event = SecurityEvent(
                    event_type=SecurityEventType.FAILED_LOGIN,
                    user_id=request.username,
                    ip_address=client_ip or "unknown",
                    severity="info",
                    details={"session_id": session_id[:8], "role": role},
                    timestamp=datetime.datetime.now().isoformat()
                )
                analytics.log_security_event(security_event)
        except Exception as e:
            logger.warning(f"Failed to log security event to advanced analytics: {e}")
    
    return TokenRoleResponse(
        status="success", 
        message="Login successful - session_id created", 
        token=session_id,  # Return session_id as token for compatibility
        role=role
    )


@app.post("/organizations/create_with_admin", response_model=TokenRoleResponse)
async def create_organization_with_admin(request: OrganizationCreateRequest, request_obj: Request):
    """
    Create a new organization and its initial admin (owner) account, then return a session token.

    This is the entry point for multi-tenant onboarding and is intended to replace
    the standalone user login/registration flow in the UI.
    """
    client_ip = request_obj.client.host if request_obj and request_obj.client else None

    # Normalize username/password similar to /register
    request.admin_username = request.admin_username.replace(" ", "_")
    request.admin_password = request.admin_password.replace(" ", "_")

    # Generate slug and ensure it is unique
    slug = _slugify_org_name(request.organization_name)
    existing_org = await get_organization_by_slug(slug)
    if existing_org:
        return TokenRoleResponse(
            status="error",
            message="Organization with this name/slug already exists",
            token=None,
            role=None,
        )

    # Ensure admin username is not taken yet (we can relax this later for shared users)
    if await get_user(request.admin_username):
        return TokenRoleResponse(
            status="error",
            message="Admin username already exists",
            token=None,
            role=None,
        )

    # Create admin user with full file access by default
    org_id = await create_organization(name=request.organization_name, slug=slug)
    
    await create_user(
        username=request.admin_username,
        password=request.admin_password,
        role="admin",
        allowed_files=["all"],
        organization_id=org_id,
    )

    # Create organization and membership
    await create_organization_membership(
        organization_id=org_id,
        username=request.admin_username,
        role="owner",
    )

    # Create an org-scoped session
    session_id = str(uuid.uuid4())
    await create_session(
        request.admin_username,
        session_id,
        expires_hours=24,
        organization_id=org_id,
    )
    await update_access_token(request.admin_username, session_id)

    # Log event into metrics
    log_event(
        event_type="organization_created",
        user_id=request.admin_username,
        session_id=session_id,
        ip_address=client_ip,
        role="owner",
        success=True,
        details={"organization_id": org_id, "slug": slug},
    )

    return TokenRoleResponse(
        status="success",
        message="Organization and admin created - session_id issued",
        token=session_id,
        role="owner",
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

# Lightweight token validation endpoint - used on page load/navigation
@app.get("/token/validate", response_model=APIResponse)
async def validate_token(user=Depends(get_current_user)):
    """
    Validate token and return minimal session info.
    Lightweight endpoint for checking token validity on page load/navigation.
    Returns: {status, created, expires}
    """
    try:
        # user is (id, username, password_hash, role, allowed_files, created_at, last_login)
        username = user[1]
        role = user[3]
        created_at = user[5] if len(user) > 5 else None
        
        logger.debug(f"Token validated for user: {username}")
        
        return APIResponse(
            status="success",
            message="Token is valid",
            response={
                "valid": True,
                "username": username,
                "role": role,
                "created_at": created_at
            }
        )
    except Exception as e:
        logger.warning(f"Token validation failed: {e}")
        return APIResponse(
            status="error",
            message="Token is invalid or expired",
            response={"valid": False}
        )

# Admin-only endpoint with role check
@app.get("/admin/access", response_model=APIResponse)
async def check_admin_access(user=Depends(get_current_user)):
    """
    Check if user has admin access.
    Only admin users can successfully call this endpoint.
    Returns: {status, is_admin, username, role}
    """
    try:
        username = user[1]
        role = user[3]
        
        # Check if user is admin
        if role != 'admin':
            logger.warning(f"Non-admin user {username} attempted to access admin panel")
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        logger.info(f"Admin access granted for user: {username}")
        
        return APIResponse(
            status="success",
            message="Admin access granted",
            response={
                "is_admin": True,
                "username": username,
                "role": role
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin access check failed: {e}")
        return APIResponse(
            status="error",
            message="Admin access denied",
            response={"is_admin": False}
        )

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
    """WebSocket endpoint for streaming RAG queries with real-time responses.
    Enforces organization isolation: users can only query documents from their organization."""
    logger = logging.getLogger(__name__)
    
    # Authenticate user
    user = await get_user_from_token(token) if token else None
    if not user:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    # Verify organization context
    organization_id = _get_active_org_id(user)
    if not organization_id:
        await websocket.close(code=1008, reason="Organization context required")
        return
    
    await websocket.accept()
    logger.info(f"WebSocket connection established for user {user[1]} in org {organization_id}")
    
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
                
                # Use secure RAG retriever with organization isolation and skip_llm=True for immediate results
                secure_retriever = SecureRAGRetriever(username=username, organization_id=organization_id)
                rag_result = await secure_retriever.invoke_secure_rag_chain(
                    rag_chain=rag_chain,
                    query=question,
                    model_type=model_type,
                    humanize=humanize,
                    skip_llm=True  # Skip LLM to return documents immediately
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
                            meta = doc.metadata if hasattr(doc, "metadata") else {}
                            source = meta.get("source", "unknown")
                            content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                        
                        if source not in immediate_response["files"]:
                            immediate_response["files"].append(source)
                        
                        # Build snippet with source information
                        snippet = {
                            "content": content,
                            "source": source
                        }
                        
                        # Check if this is from OpenCart (has catalog_id in metadata)
                        if isinstance(doc, dict):
                            meta = doc.get("metadata", {})
                        else:
                            meta = doc.metadata if hasattr(doc, "metadata") else {}
                        
                        if "catalog_id" in meta:
                            # This is an OpenCart product result
                            snippet["source_type"] = "opencart"
                            snippet["opencart"] = {
                                "catalog_id": meta.get("catalog_id"),
                                "product_id": meta.get("product_id"),
                                "name": meta.get("name"),
                                "sku": meta.get("sku"),
                                "price": meta.get("price"),
                                "special_price": meta.get("special_price"),
                                "description": meta.get("description"),
                                "url": meta.get("url"),
                                "image": meta.get("image"),
                                "quantity": meta.get("quantity"),
                                "rating": meta.get("rating"),
                                "shop_name": meta.get("shop_name"),
                                "indexed_at": meta.get("indexed_at")
                            }
                        else:
                            snippet["source_type"] = "document"
                        
                        immediate_response["snippets"].append(snippet)
                    except Exception as e:
                        logger.warning(f"Error processing document: {e}")
                
                # Send immediate results
                await websocket.send_json({
                    "type": "immediate",
                    "data": immediate_response
                })
                
                # Generate LLM overview if humanize is enabled (in background)
                if humanize:
                    try:
                        from llm import generate_llm_overview
                        # Generate overview asynchronously without blocking
                        overview = await generate_llm_overview(
                            question,
                            {"source_documents": source_docs, "answer": rag_result.get("answer", "")}
                        )
                        
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
                    ip_address=websocket.client.host if websocket.client else "unknown",
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
                        ip_address=websocket.client.host if websocket.client else "unknown",
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
    # Only initialize tracker if analytics is enabled and available
    tracker = None
    if ADVANCED_ANALYTICS_ENABLED and PerformanceTracker:
        try:
            tracker = PerformanceTracker(f"query_endpoint('{request.question[:50]}...')", logger)
        except Exception:
            tracker = None

    try:
        username = user[1]  # Extract username from user tuple
        role = user[3]  # Get user role
        organization_id = _get_active_org_id(user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required for queries.")
        session_id = str(uuid.uuid4())  # Generate session for this query
        client_ip = request_obj.client.host if request_obj and hasattr(request_obj, 'client') and request_obj.client else None
        # Get model type from environment variable (RAG_MODEL_TYPE: "local" or "server")
        model_type = "local" if os.getenv("RAG_MODEL_TYPE", "server").lower() == "local" else "server"

        # Start time for response time tracking
        if tracker:
            tracker.start_operation("query_start")
        start_time = datetime.datetime.now()

        # Clean up expired sessions periodically
        if tracker:
            tracker.start_operation("cleanup_sessions")
        await cleanup_expired_sessions()
        if tracker:
            tracker.end_operation("cleanup_sessions")

        # Initialize the RAG chain
        if tracker:
            tracker.start_operation("init_rag_chain")
        from rag_api.langchain_utils import get_rag_chain
        rag_chain = get_rag_chain()
        if tracker:
            tracker.end_operation("init_rag_chain")

        # Use secure RAG retriever that respects file permissions
        if tracker:
            tracker.start_operation("secure_retrieval")
        secure_retriever = SecureRAGRetriever(username=username, session_id=session_id, organization_id=organization_id)
        rag_result = await secure_retriever.invoke_secure_rag_chain(
            rag_chain=rag_chain,
            query=request.question,
            model_type=model_type,
            humanize=request.humanize if hasattr(request, 'humanize') and request.humanize is not None else True,
            skip_llm=True  # Skip LLM to return documents immediately
        )
        if tracker:
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
                    meta = doc.metadata if hasattr(doc, "metadata") else {}
                    source = meta.get("source", "unknown")
                    content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                
                if source not in immediate_response["files"]:
                    immediate_response["files"].append(source)
                
                # Build snippet with source information
                snippet = {
                    "content": content,
                    "source": source
                }
                
                # Check if this is from OpenCart (has catalog_id in metadata)
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {})
                else:
                    meta = doc.metadata if hasattr(doc, "metadata") else {}
                
                if "catalog_id" in meta:
                    # This is an OpenCart product result
                    snippet["source_type"] = "opencart"
                    snippet["opencart"] = {
                        "catalog_id": meta.get("catalog_id"),
                        "product_id": meta.get("product_id"),
                        "name": meta.get("name"),
                        "sku": meta.get("sku"),
                        "price": meta.get("price"),
                        "special_price": meta.get("special_price"),
                        "description": meta.get("description"),
                        "url": meta.get("url"),
                        "image": meta.get("image"),
                        "quantity": meta.get("quantity"),
                        "rating": meta.get("rating"),
                        "shop_name": meta.get("shop_name"),
                        "indexed_at": meta.get("indexed_at")
                    }
                else:
                    snippet["source_type"] = "document"
                
                immediate_response["snippets"].append(snippet)
            except Exception as e:
                logger.warning(f"Error processing document: {e}")
        
        # Generate LLM overview if humanize is enabled
        overview = None
        if request.humanize is None or request.humanize:
            try:
                from llm import generate_llm_overview
                overview = await generate_llm_overview(
                    request.question,
                    {"source_documents": source_docs, "answer": rag_result.get("answer", "")}
                )
            except Exception as e:
                logger.error(f"Error generating LLM overview: {e}")
                overview = "Error generating overview. Showing raw results."

        # Calculate response time
        if tracker:
            tracker.start_operation("calculate_response_time")
        response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
        if tracker:
            tracker.end_operation("calculate_response_time")

        # Get client IP
        if tracker:
            tracker.start_operation("get_client_ip")
        client_ip = request_obj.client.host if request_obj.client else "unknown"
        if tracker:
            tracker.end_operation("get_client_ip")

        # Extract source filenames (prefer raw docs if available)
        if tracker:
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
        if tracker:
            tracker.end_operation("extract_filenames", f"Found {len(source_filenames)} source files")

        # Log metrics
        if tracker:
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
            ip_address=client_ip or "unknown",
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
        
        # Log to advanced analytics if available
        if ADVANCED_ANALYTICS_ENABLED and QueryMetrics:
            try:
                analytics = get_analytics_core()
                if analytics and QueryMetrics:
                    query_metrics = QueryMetrics(
                        query_id=session_id,
                        session_id=session_id,
                        user_id=username,
                        role=role,
                        question=request.question,
                        answer_length=len(response_text),
                        model_type=model_type,
                        query_type=QueryType.RAG_SEARCH if QueryType else "rag_search",
                        response_time_ms=int(response_time),
                        source_document_count=len(source_docs),
                        success=True,
                        ip_address=client_ip or "unknown"
                    )
                    analytics.log_query(query_metrics)
            except Exception as e:
                logger.warning(f"Failed to log query to advanced analytics: {e}")
        
        if tracker:
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
            if tracker:
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

            if tracker:
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
        username_str = user[1] if user and len(user) > 1 else "unknown"
        logger.exception(f"Secure RAG query processing error for user {username_str}")
        if tracker:
            tracker.log_summary()
        return APIResponse(status="error", message=str(e), response=None)

# OPENCART-SPECIFIC SEARCH ENDPOINT
@app.post("/search/opencart", response_model=APIResponse)
async def search_opencart_products(
    request: RAGQueryRequest,
    request_obj: Request,
    user=Depends(get_current_user)
):
    """
    Search OpenCart products specifically. Returns only results that come from OpenCart catalogs.
    Uses RAG's semantic search with metadata filtering for better performance and accuracy.
    """
    username = user[1]
    role = user[2]
    organization_id = user[3]
    session_id = request.session_id or str(uuid.uuid4())
    start_time = datetime.datetime.now()
    
    try:
        # Check if OpenCart plugin is enabled
        opencart_enabled = await is_plugin_enabled(organization_id, "opencart")
        if not opencart_enabled:
            return APIResponse(
                status="error",
                message="OpenCart plugin is not enabled for your organization",
                response={
                    "files": [],
                    "snippets": [],
                    "model": "N/A",
                    "security_info": {
                        "user_filtered": True,
                        "username": username,
                        "source_documents_count": 0,
                        "security_filtered": False,
                        "search_type": "opencart",
                        "plugin_enabled": False
                    }
                }
            )
        
        # Get model type
        model_type = request.model_type or await get_default_model()
        
        # Initialize tracker
        tracker = PerformanceTracker(session_id=session_id)
        tracker.start_operation("opencart_search_start")
        
        # Get list of catalogs to search
        catalogs_to_search = []
        if request.catalog_ids and len(request.catalog_ids) > 0:
            # Use specified catalogs
            catalogs_to_search = request.catalog_ids
        else:
            # Use all org's catalogs
            try:
                all_catalogs = await list_catalogs_by_org(organization_id)
                catalogs_to_search = [c["catalog_id"] for c in all_catalogs]
            except Exception as e:
                logger.warning(f"Could not fetch catalogs for org {organization_id}: {e}")
                catalogs_to_search = []
        
        if not catalogs_to_search:
            return APIResponse(
                status="success",
                message="No catalogs available to search",
                response={
                    "files": [],
                    "snippets": [],
                    "model": model_type,
                    "security_info": {
                        "user_filtered": True,
                        "username": username,
                        "source_documents_count": 0,
                        "security_filtered": False,
                        "search_type": "opencart",
                        "catalogs_searched": []
                    }
                }
            )
        
        tracker.start_operation("opencart_search")
        from opencart_catalog import search_products_in_catalogs
        
        # Initialize empty results
        opencart_docs = []
        
        try:
            logger.info(f"Searching for products with query: {request.question}")
            
            # Get limit and offset from request with defaults
            limit = getattr(request, 'limit', 20)
            offset = getattr(request, 'offset', 0)
            
            # Perform the search using direct database query
            try:
                products = await search_products_in_catalogs(
                    catalog_ids=catalogs_to_search,
                    search_term=request.question,
                    limit=limit,
                    offset=offset
                )
                
                logger.info(f"Found {len(products)} products via direct search")
                
                # Convert products to document-like objects for consistent response format
                for product in products:
                    try:
                        doc = type('obj', (object,), {
                            'page_content': f"{product.get('name', '')}\n{product.get('description', '')}",
                            'metadata': product
                        })
                        opencart_docs.append(doc)
                    except Exception as e:
                        product_id = product.get('product_id', 'unknown')
                        logger.warning(f"Error formatting product {product_id}: {e}")
                        
            except Exception as e:
                logger.error(f"Error in search_products_in_catalogs: {e}", exc_info=True)
                raise
                
        except Exception as e:
            logger.error(f"Error in product search: {e}", exc_info=True)
            # Return empty results but don't fail the request
        
        tracker.end_operation("opencart_search")
        
        # Prepare response with the search results
        immediate_response = {
            "files": [],
            "snippets": [],
            "model": model_type,
            "security_info": {
                "user_filtered": True,
                "username": username,
                "source_documents_count": len(opencart_docs),
                "security_filtered": False,
                "search_type": "opencart",
                "catalogs_searched": catalogs_to_search
            }
        }
        
        # Extract OpenCart products and build snippets
        for doc in opencart_docs:
            try:
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {})
                    source = meta.get("name", "unknown")
                    content = doc.get("page_content", "") or ""
                else:
                    meta = doc.metadata if hasattr(doc, "metadata") else {}
                    source = meta.get("name", "unknown")
                    content = doc.page_content if hasattr(doc, "page_content") else str(doc)
                
                if source not in immediate_response["files"]:
                    immediate_response["files"].append(source)
                
                # Build snippet with OpenCart information
                snippet = {
                    "content": content,
                    "source": source,
                    "title": source,
                    "description": meta.get("description", ""),
                    "source_type": "opencart",
                    "metadata": {
                        "catalog_id": meta.get("catalog_id"),
                        "product_id": meta.get("product_id"),
                        "name": meta.get("name"),
                        "sku": meta.get("sku"),
                        "price": meta.get("price"),
                        "special_price": meta.get("special_price"),
                        "description": meta.get("description"),
                        "url": meta.get("url"),
                        "image": meta.get("image"),
                        "quantity": meta.get("quantity"),
                        "rating": meta.get("rating"),
                        "shop_name": meta.get("shop_name"),
                        "indexed_at": meta.get("indexed_at")
                    }
                }
                
                immediate_response["snippets"].append(snippet)
            except Exception as e:
                logger.warning(f"Error processing OpenCart product: {e}")
        
        # Calculate response time
        response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
        
        # Get client IP
        client_ip = request_obj.client.host if request_obj.client else None
        
        # Log metrics
        tracker.start_operation("log_metrics")
        
        # Create a response text for logging
        response_text = "\n".join([s["metadata"]["name"] for s in immediate_response["snippets"][:5] if s["metadata"].get("name")])
        
        # Ensure session_id is valid before logging
        if not session_id:
            logger.error("session_id is None or empty before log_query call in OpenCart search")
            session_id = str(uuid.uuid4())
        
        log_query(
            session_id=session_id,
            user_id=username,
            role=role,
            question=request.question,
            answer=response_text if response_text else "No OpenCart products found",
            model_type=model_type,
            humanize=False,
            source_document_count=len(opencart_docs),
            security_filtered=False,
            source_filenames=immediate_response["files"],
            ip_address=client_ip,
            response_time_ms=int(response_time)
        )
        
        # Log file access for each product
        for filename in immediate_response["files"]:
            log_file_access(
                user_id=username,
                role=role,
                filename=filename,
                access_type="retrieved_in_opencart_search",
                session_id=session_id,
                ip_address=client_ip,
                query_context=request.question[:100]
            )
        
        # Log the interaction
        insert_application_logs(
            session_id,
            request.question,
            f"OpenCart search: Found {len(opencart_docs)} products from catalogs {catalogs_to_search}",
            model_type
        )
        
        # Log to advanced analytics if available
        if ADVANCED_ANALYTICS_ENABLED:
            try:
                analytics = get_analytics_core()
                query_metrics = QueryMetrics(
                    query_id=session_id,
                    user_id=username,
                    query_text=request.question,
                    query_type=QueryType.PRODUCT_SEARCH,
                    num_documents_retrieved=len(opencart_docs),
                    response_time_ms=int(response_time),
                    success=True,
                    cache_hit=False,
                    tokens_input=0,
                    tokens_output=0
                )
                await analytics.log_query(query_metrics)
            except Exception as e:
                logger.warning(f"Failed to log OpenCart search to advanced analytics: {e}")
        
        tracker.end_operation("log_metrics")
        
        logger.info(f"OpenCart search for user {username}: {len(opencart_docs)} products found from {len(catalogs_to_search)} catalogs")
        
        # Return response
        return APIResponse(
            status="success",
            message=f"OpenCart product search completed - {len(opencart_docs)} products found",
            response=immediate_response
        )
    
    except Exception as e:
        logger.exception(f"OpenCart search processing error for user {username if 'username' in locals() else 'unknown'}")
        return APIResponse(status="error", message=str(e), response=None)

from fastapi.responses import PlainTextResponse, JSONResponse
from urllib.parse import unquote

# Endpoint to return file content by filename (from DB) or OpenCart product data
@app.get("/files/content/{filename}")
async def get_file_content(
    filename: str,
    request_obj: Request,
    user = Depends(get_current_user),
    include_quiz: bool = Query(False, description="If true, return JSON with file content and quiz"),
    catalog_id: str = Query(None, description="If provided, treat filename as product name and return OpenCart product data")
):
    """
    Return the content of a file by its name (if user has access) or fetch OpenCart product data.
    Supports percent-encoded (e.g. Russian) filenames. Reads from DB.
    Enforces organization-level access control: users can only access files from their organization.
    For OpenCart products (when catalog_id is provided), returns product details as JSON.
    """
    from org_security import enforce_organization_context
    
    decoded_filename = unquote(filename)
    organization_id = enforce_organization_context(user, required=True)
    
    # Get client IP for metrics
    client_ip = request_obj.client.host if request_obj and request_obj.client else None
    
    # Check if this is an OpenCart product request
    if catalog_id:
        logger.info(f"User {user[1]} from org {organization_id} requests OpenCart product: {decoded_filename} from catalog {catalog_id}")
        
        # Search for OpenCart product in Chroma
        try:
            from rag_api.chroma_utils import vectorstore
            
            # Query Chroma for the product
            results = vectorstore.get(
                where={
                    "$and": [
                        {"catalog_id": catalog_id},
                        {"name": decoded_filename},
                        {"organization_id": organization_id}
                    ]
                }
            )
            
            if results and results.get('ids') and len(results['ids']) > 0:
                # Get the first matching product
                metadata = results['metadatas'][0] if results['metadatas'] else {}
                
                # Log file access
                log_file_access(
                    user_id=user[1],
                    role=user[3],
                    filename=decoded_filename,
                    access_type="view_opencart",
                    session_id=None,
                    ip_address=client_ip
                )
                
                # Return product data as JSON
                return JSONResponse({
                    "status": "success",
                    "type": "opencart_product",
                    "data": {
                        "catalog_id": metadata.get("catalog_id"),
                        "product_id": metadata.get("product_id"),
                        "name": metadata.get("name"),
                        "sku": metadata.get("sku"),
                        "price": metadata.get("price"),
                        "special_price": metadata.get("special_price"),
                        "description": metadata.get("description"),
                        "url": metadata.get("url"),
                        "image": metadata.get("image"),
                        "quantity": metadata.get("quantity"),
                        "rating": metadata.get("rating"),
                        "shop_name": metadata.get("shop_name"),
                        "indexed_at": metadata.get("indexed_at")
                    }
                })
            else:
                logger.warning(f"OpenCart product not found: {decoded_filename} in catalog {catalog_id}")
                raise HTTPException(status_code=404, detail="Product not found in catalog.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching OpenCart product: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error fetching product data.")
    
    # Regular file access (document)
    resolved_filename = resolve_actual_filename_case_insensitive(decoded_filename)
    allowed_files = await get_allowed_files(user[1])
    
    logger.info(f"User {user[1]} from org {organization_id} requests file: {decoded_filename} (resolved: {resolved_filename}). Allowed files: {allowed_files}")
    
    # Admins can access any file; for users: allowed_files=None means all files allowed
    if user[3] != "admin":
        if allowed_files is not None and resolved_filename not in allowed_files:
            # Log security event for unauthorized access attempt
            log_security_event(
                event_type="unauthorized_file_access",
                ip_address=client_ip or "unknown",
                user_id=user[1],
                details={"filename": resolved_filename, "organization_id": organization_id},
                severity="medium"
            )
            raise HTTPException(status_code=403, detail="You do not have access to this file.")
    
    # Retrieve file with organization filtering
    content_bytes = get_file_content_by_filename(resolved_filename, organization_id=organization_id)
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
            ip_address=client_ip or "unknown"
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
                quiz_payload: Dict[str, Any] = {}

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
                ip_address=client_ip or "unknown",
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
            ip_address=client_ip or "unknown"
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
    """Secure chat using RAG with conversation history and file access control.
    Enforces organization-level access: users can only chat within their organization."""
    try:
        from org_security import enforce_organization_context
        
        username = user[1]  # Extract username from user tuple
        role = user[3]  # Get user role
        
        # Enforce organization context
        organization_id = enforce_organization_context(user, required=True)
        
        # Get model type from environment variable (RAG_MODEL_TYPE: "local" or "server")
        model_type = "local" if os.getenv("RAG_MODEL_TYPE", "server").lower() == "local" else "server"
        
        # Start time for response time tracking
        start_time = datetime.datetime.now()
        
        logger.info(f"Secure chat - Session ID: {session_id}, User: {username}, Org: {organization_id}, Query: {request.question}, Model: {model_type}")
        
        # Use secure RAG retriever that respects file permissions and organization isolation
        secure_retriever = SecureRAGRetriever(username=username, session_id=session_id, organization_id=organization_id or "")
        chat_history = get_chat_history(session_id)
        
        # Get secure RAG response with file access control and organization filtering
        from rag_api.langchain_utils import get_rag_chain
        rag_chain = get_rag_chain()
        rag_result = await secure_retriever.invoke_secure_rag_chain(
            rag_chain=rag_chain, 
            query=request.question, 
            model_type=model_type,
            humanize=request.humanize if request.humanize is not None else True,
            skip_llm=False
        )
        
        answer = rag_result.get("answer", "")
        source_docs = rag_result.get("source_documents", [])
        security_filtered = rag_result.get("security_filtered", False)

        # Calculate response time
        response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
        
        # Get client IP
        client_ip = request_obj.client.host if request_obj and request_obj.client else "unknown"
        
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
            ip_address=client_ip or "unknown"
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

    organization_id = _get_active_org_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=400, detail="Organization context required for upload.")

    # Extended support for PDF, DOCX, DOC, HTML, TXT, MD, and ZIP archives
    allowed_extensions = ['.pdf', '.docx', '.doc', '.html', '.txt', '.md', '.zip']
    file_extension = os.path.splitext(file.filename or "")[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed types are: {', '.join(allowed_extensions)}"
        )

    upload_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()
    original_filename = file.filename or "unknown"
    file_extension = os.path.splitext(original_filename)[1].lower()

    try:
        # Read file content as bytes
        content_bytes = await file.read()
        
        # Log upload information
        logger.info(f"Starting upload: {original_filename}")
        logger.info(f"  - Upload ID: {upload_id}")
        logger.info(f"  - User: {current_user[1]}")
        logger.info(f"  - File type: {file_extension}")
        logger.info(f"  - File size: {len(content_bytes)} bytes")
        logger.info(f"  - Timestamp: {timestamp}")
        
        # Handle ZIP files by extracting and uploading each file separately
        if file_extension == '.zip':
            logger.info(f"Archive detected. Extracting and processing contents as separate files...")
            import zipfile
            import tempfile
            
            extracted_files = []
            failed_files = []
            
            with tempfile.TemporaryDirectory() as temp_extract_dir:
                # Extract ZIP
                try:
                    # First, save the ZIP file to disk
                    temp_zip_path = f"temp_{original_filename}"
                    with open(temp_zip_path, 'wb') as buffer:
                        buffer.write(content_bytes)
                    
                    # Now extract it with proper UTF-8 filename handling
                    with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                        logger.info(f"Archive extracted with {len(zip_ref.filelist)} total files (UTF-8 filename support enabled)")
                        
                        # Extract files and fix filenames if needed
                        for member in zip_ref.filelist:
                            try:
                                # Access raw filename bytes to properly decode
                                # ZIP stores filename in the header as bytes
                                raw_filename = member.filename
                                filename_to_use = raw_filename
                                
                                # Check if filename appears to be mojibake (UTF-8 decoded as CP437)
                                # Try different decoding strategies
                                if isinstance(raw_filename, str) and any(ord(c) > 127 for c in raw_filename):
                                    # Contains non-ASCII characters
                                    try:
                                        # First try: Assume it's UTF-8 bytes misinterpreted as Latin-1 or CP437
                                        # Re-encode as latin-1 (to get back bytes) then decode as UTF-8
                                        attempt1 = raw_filename.encode('latin-1').decode('utf-8')
                                        filename_to_use = attempt1
                                        logger.debug(f"Successfully decoded via latin-1→utf-8: {raw_filename} -> {attempt1}")
                                    except (UnicodeDecodeError, UnicodeEncodeError):
                                        # If that fails, try CP437→UTF-8
                                        try:
                                            attempt2 = raw_filename.encode('cp437').decode('utf-8')
                                            filename_to_use = attempt2
                                            logger.debug(f"Successfully decoded via cp437→utf-8: {raw_filename} -> {attempt2}")
                                        except (UnicodeDecodeError, UnicodeEncodeError):
                                            # Keep original if both attempts fail
                                            logger.debug(f"Could not decode {raw_filename}, keeping original")
                                            filename_to_use = raw_filename
                                
                                # Now extract with the corrected filename
                                member.filename = filename_to_use
                                extracted_path = zip_ref.extract(member, temp_extract_dir)
                                
                            except Exception as e:
                                logger.warning(f"Could not extract {member.filename}: {str(e)}")
                                try:
                                    zip_ref.extract(member, temp_extract_dir)
                                except Exception as e2:
                                    logger.error(f"Failed to extract {member.filename}: {str(e2)}")
                    
                    # Clean up temp ZIP
                    if os.path.exists(temp_zip_path):
                        os.remove(temp_zip_path)
                    # Process each extracted file
                    allowed_archive_extensions = ['.pdf', '.docx', '.doc', '.html', '.txt', '.md']
                    
                    for root, dirs, files in os.walk(temp_extract_dir):
                        for extracted_filename in files:
                            extracted_file_path = os.path.join(root, extracted_filename)
                            extracted_ext = os.path.splitext(extracted_filename)[1].lower()
                            
                            # Only process supported file types from archive
                            if extracted_ext not in allowed_archive_extensions:
                                logger.info(f"Skipping unsupported file in archive: {extracted_filename} ({extracted_ext})")
                                continue
                            
                            try:
                                logger.info(f"Processing extracted file: {extracted_filename}")
                                
                                # Check if file already exists
                                if get_file_content_by_filename(extracted_filename, organization_id=organization_id) is not None:
                                    logger.warning(f"File {extracted_filename} already exists in DB, skipping")
                                    continue
                                
                                # Read extracted file content
                                with open(extracted_file_path, 'rb') as f:
                                    extracted_content = f.read()
                                
                                # Save each extracted file to database as separate file (with unicode support)
                                extracted_file_id = insert_document_record(extracted_filename, extracted_content, organization_id=organization_id)
                                logger.info(f"  Saved to database: {extracted_filename} (file_id: {extracted_file_id})")
                                
                                # Index to Chroma
                                temp_index_path = f"temp_{extracted_filename}"
                                with open(temp_index_path, 'wb') as buffer:
                                    buffer.write(extracted_content)
                                
                                if extracted_file_id and index_document_to_chroma(temp_index_path, extracted_file_id, organization_id=organization_id):
                                    logger.info(f"✓ Indexed {extracted_filename}")
                                    extracted_files.append({
                                        "filename": extracted_filename,
                                        "file_id": extracted_file_id,
                                        "size": len(extracted_content)
                                    })
                                    # Fire-and-forget: generate quiz for extracted file
                                    try:
                                        asyncio.create_task(create_quiz_for_filename(extracted_filename, organization_id=organization_id))
                                    except Exception:
                                        pass
                                else:
                                    logger.error(f"Failed to index {extracted_filename}")
                                    if extracted_file_id:
                                        delete_document_record(extracted_file_id)
                                    failed_files.append(extracted_filename)
                                
                                if os.path.exists(temp_index_path):
                                    os.remove(temp_index_path)
                                    
                            except Exception as e:
                                logger.error(f"Error processing {extracted_filename}: {str(e)}")
                                failed_files.append(extracted_filename)
                    
                    # Return results
                    logger.info(f"Archive processing complete: {len(extracted_files)} files processed, {len(failed_files)} failed")
                    
                    return APIResponse(
                        status="success",
                        message=f"Archive {original_filename} processed: {len(extracted_files)} files uploaded and indexed.",
                        response={
                            "upload_id": upload_id,
                            "archive_filename": original_filename,
                            "files_processed": len(extracted_files),
                            "files_failed": len(failed_files),
                            "extracted_files": extracted_files,
                            "timestamp": timestamp
                        }
                    )
                    
                except zipfile.BadZipFile as e:
                    logger.error(f"Invalid ZIP file: {str(e)}")
                    raise HTTPException(status_code=400, detail=f"Invalid ZIP file: {str(e)}")
                except Exception as e:
                    logger.error(f"Error extracting archive: {str(e)}")
                    raise HTTPException(status_code=400, detail=f"Error extracting archive: {str(e)}")
        
        else:
            # Handle regular (non-ZIP) files
            # Check if file with the same name already exists in DB
            if get_file_content_by_filename(original_filename, organization_id=organization_id) is not None:
                raise HTTPException(status_code=400, detail="A file with this name already exists.")
            
            # Insert document record and get file_id
            file_id = insert_document_record(original_filename, content_bytes, organization_id=organization_id)
            logger.info(f"  - Database file_id: {file_id}")

            # Index document to Chroma
            temp_file_path = f"temp_{original_filename}"
            with open(temp_file_path, "wb") as buffer:
                buffer.write(content_bytes)
            
            if file_id:
                success = index_document_to_chroma(temp_file_path, file_id, organization_id=organization_id)
            else:
                success = False
            
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

            if success:
                # Fire-and-forget: generate a quiz for this uploaded file in background
                try:
                    asyncio.create_task(create_quiz_for_filename(original_filename, organization_id=organization_id))
                except Exception:
                    pass
                
                # Log successful completion
                logger.info(f"✓ Upload completed successfully: {original_filename} (ID: {file_id}, Upload ID: {upload_id})")
                
                # Log to advanced analytics if available
                if ADVANCED_ANALYTICS_ENABLED:
                    try:
                        analytics = get_analytics_core()
                        if analytics and file_id:
                            # Only log if analytics methods are available
                            if hasattr(analytics, 'log_file_access'):
                                analytics.log_file_access(
                                    user_id=current_user[1],
                                    filename=original_filename,
                                    file_id=file_id,
                                    access_type="upload",
                                    ip_address="unknown",
                                    details={"file_size": len(content_bytes), "upload_id": upload_id}
                                )
                    except Exception as e:
                        logger.warning(f"Failed to log file access to advanced analytics: {e}")
                
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
                if file_id:
                    delete_document_record(file_id)
                logger.error(f"Failed to index {original_filename} (ID: {file_id})")
                raise HTTPException(status_code=500, detail=f"Failed to index {original_filename}.")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"File upload failed for {original_filename}: {str(e)}")
        logger.error(f"  - Upload ID: {upload_id}")
        logger.error(f"  - File type: {file_extension}")
        raise HTTPException(500, f"Failed to upload file: {e}")

# List documents endpoint
@app.get("/files/list", response_model=APIResponse)
async def list_documents(user=Depends(get_current_user)):
    """List all uploaded documents the user has access to"""
    try:
        organization_id = _get_active_org_id(user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        documents = get_all_documents(organization_id=organization_id)
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
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            organization_id = ""  # Default to empty string if not available
        chroma_delete_success = delete_doc_from_chroma(request.file_id, organization_id=organization_id or "")
        
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
        if os.path.exists(UPLOAD_DIR):
            for file in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, file)
                if os.path.isfile(file_path):
                    files.append(file)
        
        # Also get files from the database (org context not available here; return filesystem only)
        db_files = get_all_documents()  # Not async, remove await
        db_filenames = []
        for doc in db_files:
            if isinstance(doc, dict):
                db_filenames.append(doc.get("filename"))
            elif isinstance(doc, (list, tuple)) and len(doc) > 1:
                db_filenames.append(doc[1])
        
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
    organization_id = _get_active_org_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=400, detail="Organization context required.")

    # Find file_id by filename
    documents = get_all_documents(organization_id=organization_id)
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
    chroma_delete_success = delete_doc_from_chroma(file_id, organization_id=organization_id)
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


# Manual indexation endpoint (admin only)
@app.post("/files/index", response_model=APIResponse, tags=["Documents"])
async def index_files(
    current_user=Depends(get_current_user)
):
    """
    Manually index all unindexed files in the knowledge base (admin only).
    This endpoint scans the database for files that haven't been indexed to Chroma yet
    and creates vector embeddings for them.
    
    Also checks for existing embeddings and replaces them if they exist.
    """
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        from rag_api.db_utils import get_unindexed_documents
        from rag_api.chroma_utils import index_document_to_chroma, delete_doc_from_chroma
        
        logger.info(f"Starting manual indexation for organization {organization_id}")
        
        # Get all documents in the organization
        documents = get_all_documents(organization_id=organization_id)
        
        if not documents:
            return APIResponse(
                status="success",
                message="No documents found to index",
                response={"indexed_count": 0, "failed_count": 0, "replaced_count": 0, "documents": []}
            )
        
        indexed_count = 0
        failed_count = 0
        replaced_count = 0
        indexed_docs = []
        failed_docs = []
        replaced_docs = []
        
        for doc in documents:
            try:
                # Extract document info (handle dict or tuple format)
                if isinstance(doc, dict):
                    file_id = doc.get("id")
                    filename = doc.get("filename")
                    content = doc.get("content")
                elif isinstance(doc, (list, tuple)) and len(doc) >= 2:
                    file_id = doc[0]
                    filename = doc[1]
                    content = doc[2] if len(doc) > 2 else None
                else:
                    continue
                
                if not file_id or not filename:
                    continue
                
                # Try to index the file
                if content:
                    # Write content to temp file for indexing
                    temp_file_path = f"temp_{filename}"
                    try:
                        # Check if embeddings already exist and delete them first
                        try:
                            existing_deleted = delete_doc_from_chroma(file_id, organization_id=organization_id)
                            if existing_deleted:
                                replaced_count += 1
                                replaced_docs.append({
                                    "file_id": file_id,
                                    "filename": filename,
                                    "action": "Replaced existing embeddings"
                                })
                                logger.info(f"🔄 Deleted existing embeddings for {filename} (file_id: {file_id})")
                        except Exception as e:
                            logger.debug(f"No existing embeddings to delete for {filename}: {e}")
                        
                        with open(temp_file_path, "wb") as buffer:
                            if isinstance(content, bytes):
                                buffer.write(content)
                            else:
                                buffer.write(content.encode('utf-8'))
                        
                        # Index to Chroma with organization isolation
                        success = index_document_to_chroma(
                            temp_file_path, 
                            file_id, 
                            organization_id=organization_id
                        )
                        
                        if success:
                            indexed_count += 1
                            indexed_docs.append({
                                "file_id": file_id,
                                "filename": filename
                            })
                            logger.info(f"✓ Indexed {filename} (file_id: {file_id})")
                        else:
                            failed_count += 1
                            failed_docs.append({
                                "file_id": file_id,
                                "filename": filename,
                                "reason": "Indexing failed"
                            })
                            logger.warning(f"Failed to index {filename} (file_id: {file_id})")
                    finally:
                        # Clean up temp file
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                else:
                    failed_count += 1
                    failed_docs.append({
                        "file_id": file_id,
                        "filename": filename,
                        "reason": "No content found"
                    })
            
            except Exception as e:
                failed_count += 1
                failed_docs.append({
                    "file_id": doc.get("id") if isinstance(doc, dict) else (doc[0] if isinstance(doc, (list, tuple)) else None),
                    "filename": doc.get("filename") if isinstance(doc, dict) else (doc[1] if isinstance(doc, (list, tuple)) and len(doc) > 1 else None),
                    "reason": str(e)
                })
                logger.error(f"Error indexing document: {str(e)}")
        
        logger.info(f"Indexation complete: {indexed_count} indexed, {replaced_count} replaced, {failed_count} failed")
        
        return APIResponse(
            status="success",
            message=f"Indexation complete: {indexed_count} files indexed, {replaced_count} replaced, {failed_count} failed",
            response={
                "indexed_count": indexed_count,
                "replaced_count": replaced_count,
                "failed_count": failed_count,
                "indexed_documents": indexed_docs,
                "replaced_documents": replaced_docs,
                "failed_documents": failed_docs
            }
        )
    
    except Exception as e:
        logger.exception("Manual indexation failed")
        return APIResponse(
            status="error",
            message=f"Indexation failed: {str(e)}",
            response=None
        )


# Get user accounts (admin only)
@app.get("/accounts", response_model=List[dict])
async def get_accounts(current_user=Depends(get_current_user)):
    """
    List all accounts with their username, role, and last login.
    Requires admin authentication. Returns only users in the admin's organization.
    """
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    # Get organization_id from the authenticated admin user
    organization_id = _get_active_org_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=400, detail="Organization context required.")
    
    users = await list_users(organization_id=organization_id)
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
    Admin can only delete users in their own organization.
    """
    is_admin = False
    is_master = False
    admin_user = None
    if credentials:
        admin_user = await get_user_by_token(credentials.credentials)
        if admin_user and admin_user[3] == "admin":
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
    
    # Check organization isolation: admin can only delete users in their own organization
    if is_admin and admin_user:
        admin_org_id = _get_active_org_id(admin_user)
        user_org_id = user[7] if len(user) > 7 else None  # organization_id is at index 7
        if admin_org_id != user_org_id:
            raise HTTPException(status_code=403, detail="Cannot delete users from other organizations.")
    
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
    Admin can only edit users in their own organization.
    """
    is_admin = False
    is_master = False
    admin_user = None
    if credentials:
        admin_user = await get_user_by_token(credentials.credentials)
        if admin_user and admin_user[3] == "admin":
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
    
    # Check organization isolation: admin can only edit users in their own organization
    if is_admin and admin_user:
        admin_org_id = _get_active_org_id(admin_user)
        user_org_id = user[7] if len(user) > 7 else None  # organization_id is at index 7
        if admin_org_id != user_org_id:
            raise HTTPException(status_code=403, detail="Cannot edit users from other organizations.")
    
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

# PUT endpoint for user update (RESTful alternative)
@app.put("/user/{username}", response_model=APIResponse)
async def update_user_endpoint(
    username: str,
    request: UserEditRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
):
    """
    Update user fields using PUT method (RESTful). Only provided fields are changed. Requires admin or master key.
    """
    # Set the username from path parameter
    request.username = username
    
    # Reuse the existing edit_user_endpoint logic
    return await edit_user_endpoint(request, credentials)

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


class TimeRangeQuery(BaseModel):
    since: str = "24h"  # Default to 24 hours

# ==================== ADVANCED METRICS ENDPOINTS ====================

@app.get("/metrics/summary", tags=["Analytics"])
async def get_metrics_summary_endpoint(
    since: str = Query("24h", description="Time range: 1h, 24h, 7d, etc"),
    current_user=Depends(get_current_user)
):
    """
    Get summary metrics for the dashboard - NEW Advanced Analytics
    
    Requires authentication. Returns comprehensive performance and usage metrics.
    """
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")
    
    try:
        # Convert since to hours
        if since.endswith('h'):
            hours = int(since[:-1])
        elif since.endswith('d'):
            hours = int(since[:-1]) * 24
        else:
            hours = 24
            
        analytics = get_analytics_core()
        summary = analytics.get_query_statistics(since_hours=hours)
        
        return {
            "status": "success",
            "period": since,
            "data": {
                "total_queries": summary.get('total_queries', 0),
                "success_rate": round(
                    (summary.get('successful_queries', 0) / summary.get('total_queries', 1) * 100)
                    if summary.get('total_queries', 0) > 0 else 0, 2
                ),
                "avg_response_time_ms": round(summary.get('avg_response_time_ms', 0), 2),
                "min_response_time_ms": summary.get('min_response_time_ms', 0),
                "max_response_time_ms": summary.get('max_response_time_ms', 0),
                "unique_users": summary.get('unique_users', 0),
                "cache_hit_rate": round(
                    (summary.get('cache_hits', 0) / summary.get('total_queries', 1) * 100)
                    if summary.get('total_queries', 0) > 0 else 0, 2
                ),
                "total_tokens_input": summary.get('total_tokens_input', 0),
                "total_tokens_output": summary.get('total_tokens_output', 0),
                "avg_docs_per_query": round(summary.get('avg_docs_per_query', 0), 2),
            }
        }
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/queries", tags=["Analytics"])
async def get_metrics_queries(
    since: str = Query("24h", description="Time range"),
    limit: int = Query(10, le=100),
    offset: int = Query(0),
    current_user=Depends(get_current_user)
):
    """
    Get recent queries for analytics - NEW Advanced Analytics
    
    Returns paginated query metrics with filters support.
    """
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")
    
    try:
        # Convert since to hours
        if since.endswith('h'):
            hours = int(since[:-1])
        elif since.endswith('d'):
            hours = int(since[:-1]) * 24
        else:
            hours = 24
            
        analytics = get_analytics_core()
        queries = analytics.get_query_analytics(limit=limit, offset=offset)
        
        return {
            "status": "success",
            "period": since,
            "pagination": {
                "limit": limit,
                "offset": offset
            },
            "data": {
                "queries": queries
            }
        }
    except Exception as e:
        logger.error(f"Error getting metrics queries: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/performance", tags=["Analytics"])
async def get_metrics_performance(
    since: str = Query("24h"),
    limit: int = Query(20, le=100),
    admin_user=Depends(get_current_user)
):
    """
    Get performance metrics - NEW Advanced Analytics
    
    Shows operation performance, bottlenecks, and resource usage.
    """
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")
    
    try:
        if since.endswith('h'):
            hours = int(since[:-1])
        elif since.endswith('d'):
            hours = int(since[:-1]) * 24
        else:
            hours = 24
            
        analytics = get_analytics_core()
        performance = analytics.get_performance_statistics(since_hours=hours)
        
        return {
            "status": "success",
            "period": since,
            "data": {
                "operations": sorted(
                    performance,
                    key=lambda x: x.get('avg_duration_ms', 0),
                    reverse=True
                )[:limit]
            }
        }
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/errors", tags=["Analytics"])
async def get_metrics_errors(
    since: str = Query("24h"),
    limit: int = Query(50, le=100),
    admin_user=Depends(get_current_user)
):
    """
    Get error metrics - NEW Advanced Analytics
    
    Shows error frequency and aggregation.
    """
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")
    
    try:
        if since.endswith('h'):
            hours = int(since[:-1])
        elif since.endswith('d'):
            hours = int(since[:-1]) * 24
        else:
            hours = 24
            
        analytics = get_analytics_core()
        errors = analytics.get_error_summary(since_hours=hours, limit=limit)
        
        return {
            "status": "success",
            "period": since,
            "data": {
                "errors": errors,
                "total_unique_errors": len(errors)
            }
        }
    except Exception as e:
        logger.error(f"Error getting error metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/documents", tags=["Analytics"])
async def get_metrics_documents(
    limit: int = Query(20, le=100),
    admin_user=Depends(get_current_user)
):
    """
    Get document usage metrics - NEW Advanced Analytics
    
    Shows most accessed files and their usage patterns.
    """
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")
    
    try:
        analytics = get_analytics_core()
        docs = analytics.get_top_documents(limit=limit)
        
        return {
            "status": "success",
            "data": {
                "documents": docs,
                "total": len(docs)
            }
        }
    except Exception as e:
        logger.error(f"Error getting document metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/health", tags=["Analytics"])
async def get_metrics_health(
    current_user=Depends(get_current_user)
):
    """
    Get system health metrics - NEW Advanced Analytics
    
    Quick health check with current status.
    """
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")
    
    try:
        analytics = get_analytics_core()
        stats = analytics.get_query_statistics(since_hours=1)
        
        # Health status
        health = "healthy"
        if stats.get('total_queries', 0) == 0:
            health = "no_data"
        elif (stats.get('failed_queries', 0) / stats.get('total_queries', 1)) > 0.1:
            health = "warning"
        
        return {
            "status": "success",
            "health": health,
            "data": {
                "queries_last_hour": stats.get('total_queries', 0),
                "success_rate": round(
                    (stats.get('successful_queries', 0) / stats.get('total_queries', 1) * 100)
                    if stats.get('total_queries', 0) > 0 else 100, 2
                ),
                "avg_response_time_ms": round(stats.get('avg_response_time_ms', 0), 2),
                "active_users": stats.get('unique_users', 0),
                "analytics_enabled": ADVANCED_ANALYTICS_ENABLED
            }
        }
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        return {
            "status": "error",
            "health": "error",
            "detail": str(e),
            "analytics_enabled": ADVANCED_ANALYTICS_ENABLED
        }

# ==================== DEPRECATED ENDPOINTS (kept for backward compatibility) ====================

@app.get("/metrics/summary-legacy", tags=["Analytics (Deprecated)"], deprecated=True)
async def get_metrics_summary_legacy(
    since: str = "24h",
    current_user=Depends(get_current_user)
):
    """
    DEPRECATED: Use /metrics/summary instead.
    
    This endpoint is maintained for backward compatibility only.
    """
    return {
        "status": "deprecated",
        "message": "This endpoint is deprecated. Please use /metrics/summary instead.",
        "redirect": "/metrics/summary"
    }

@app.get("/metrics/queries-legacy", tags=["Analytics (Deprecated)"], deprecated=True)
async def get_metrics_queries_legacy(
    since: str = "24h",
    limit: int = 10,
    current_user=Depends(get_current_user)
):
    """
    DEPRECATED: Use /metrics/queries instead.
    
    This endpoint is maintained for backward compatibility only.
    """
    return {
        "status": "deprecated",
        "message": "This endpoint is deprecated. Please use /metrics/queries instead.",
        "redirect": "/metrics/queries"
    }

