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
from quiz_management import (
    init_quiz_management_db,
    create_manual_quiz,
    get_all_quizzes,
    get_quiz_by_id,
    update_quiz,
    delete_quiz,
    submit_quiz_result,
    get_quiz_submissions,
    get_quiz_statistics,
    Quiz,
    QuizQuestion,
    QuizSubmission
)
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
    get_organization_by_id,
    create_organization_membership,
)
from rag_security import SecureRAGRetriever, get_filtered_rag_context
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


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


from llm import llm_call


import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'rag_api'))
from rag_api.pydantic_models import QueryInput, QueryResponse, DocumentInfo, DeleteFileRequest, ModelName
from rag_api.langchain_utils import get_rag_chain
from rag_api.db_utils import insert_application_logs, get_chat_history, get_all_documents, insert_document_record, delete_document_record, get_file_content_by_filename
from rag_api.chroma_utils import index_document_to_chroma, delete_doc_from_chroma
import json
import datetime


from metricsdb import init_metrics_db, log_event, log_query, log_file_access, log_security_event
from metrics_middleware import MetricsMiddleware
from quizdb import init_quiz_db, create_quiz_for_filename, get_quiz_by_filename
from rag_api.db_utils import insert_application_logs


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
    
    get_analytics_core = None  
    QueryMetrics = None  
    QueryType = None  
    SecurityEventType = None  
    SecurityEvent = None  
    advanced_analytics_router = None  
    PerformanceTracker = None  
    UserBehaviorAnalyzer = None  
    SecurityAnalyzer = None  


init_metrics_db()


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


app.include_router(metrics_user_router)


if ADVANCED_ANALYTICS_ENABLED and advanced_analytics_router:
    app.include_router(advanced_analytics_router)
    logger = logging.getLogger(__name__)
    logger.info("✅ Advanced analytics enabled")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "https://wikiai.by", "https://api.wikiai.by", "https://esell.by"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


if ADVANCED_ANALYTICS_ENABLED and AdvancedAnalyticsMiddleware:
    app.add_middleware(AdvancedAnalyticsMiddleware)


app.add_middleware(MetricsMiddleware)


@app.on_event("startup")
async def _startup_events():
    await init_quiz_db()
    await init_quiz_management_db()  
    await init_opencart_db()
    await init_catalog_db()  
    await init_org_db()
    await init_api_keys_db()
    await init_plugins_db()  
    
    
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


os.makedirs(UPLOAD_DIR, exist_ok=True)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


security_scheme = HTTPBearer(auto_error=False)


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
    humanize: Optional[bool] = True  
    session_id: Optional[str] = None
    model_type: Optional[str] = None
    catalog_ids: Optional[List[str]] = None  

class UserEditRequest(BaseModel):
    username: str
    new_username: str = ""
    password: str = ""
    role: str = ""
    allowed_files: Optional[List[str]] = None
    


class OrganizationCreateRequest(BaseModel):
    organization_name: str
    admin_username: str
    admin_password: str



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
    import re

    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9\\s_-]", "", slug)
    slug = re.sub(r"[\\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug or "org-" + uuid.uuid4().hex[:8]


def _get_active_org_id(user_tuple):
    try:
        if not user_tuple:
            return None

        
        
        if len(user_tuple) >= 8 and user_tuple[3] == "api_key":
            return user_tuple[7]

        
        
        if len(user_tuple) >= 12:
            return user_tuple[-1]

        
        
        if len(user_tuple) >= 8:
            return user_tuple[7]
    except Exception:
        pass
    return None


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


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authentication credentials.")
    
    
    user = await get_user_by_session_id(credentials.credentials)
    if user:
        return user
    
    
    api_key_data = await validate_api_key(credentials.credentials)
    if api_key_data:
        
        
        return (
            api_key_data["id"],  
            api_key_data["name"],  
            "api_key",  
            "api_key",  
            api_key_data["permissions"],  
            api_key_data["created_at"],  
            api_key_data["last_used"],  
            api_key_data["organization_id"],  
        )
    
    
    user = await get_user_by_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid or expired session_id, API key, or token.")
    return user

async def get_user_role(username: str):
    user = await get_user(username)
    if user:
        return user[3]  
    return None

async def check_api_key_operation_permission(current_user, operation: str) -> bool:
    
    if current_user[3] != "api_key":
        return True
    
    
    permissions = current_user[4]  
    return operation in permissions


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


OC_DB_PATH = os.path.join(os.path.dirname(__file__), "integration_toolkit", "OpenCart", "Backend", "opencart_products.db")


async def init_opencart_db():
    os.makedirs(os.path.dirname(OC_DB_PATH), exist_ok=True)
    async with aiosqlite.connect(OC_DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                sku TEXT,
                price REAL,
                special REAL,
                description TEXT,
                url TEXT,
                image TEXT,
                quantity INTEGER,
                status INTEGER,
                rating INTEGER,
                updated_at TIMESTAMP
            )
        """)
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
                """INSERT INTO products (
                    product_id, name, sku, price, special, description, url,
                    image, quantity, status, rating, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, product.name, product.sku, price, product.special, 
                 product.description, product.url, product.image, qty, status, 
                 rating, datetime.utcnow())
            )
    try:
        
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required to create API keys.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        username = current_user[1]
        
        
        full_key, key_id = await create_api_key(
            organization_id=organization_id,
            created_by=username,
            name=request.name,
            permissions=request.permissions,
            description=request.description,
            expires_in_days=request.expires_in_days,
        )
        
        logger.info(f"API key '{request.name}' created by {username} for org {organization_id}")
        
        
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
    try:
        
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
    try:
        
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        key_details = await get_api_key_details(key_id)
        if not key_details:
            raise HTTPException(status_code=404, detail="API key not found.")
        
        
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
    try:
        
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        
        key_details = await get_api_key_details(key_id)
        if not key_details:
            raise HTTPException(status_code=404, detail="API key not found.")
        
        if key_details["organization_id"] != organization_id:
            raise HTTPException(status_code=403, detail="Cannot update API keys from other organizations.")
        
        
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
    try:
        
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        
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
    try:
        
        if current_user[3] not in ["admin"]:
            raise HTTPException(status_code=403, detail="Admin access required.")
        
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        
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
    
    if plugin_token:
        token_data = await validate_plugin_token(plugin_token)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid or expired plugin token")
        return token_data["organization_id"]
    
    
    if isinstance(current_user, tuple) and len(current_user) >= 8:
        return current_user[7]  
    
    
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



@app.post("/opencart", response_model=APIResponse, include_in_schema=False)
async def import_opencart_products_alias(
    payload: OCProductsImport,
    current_user=Depends(get_current_user),
    plugin_token: Optional[str] = None,
):
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



@app.post("/opencart/sync", response_model=APIResponse, include_in_schema=False)
async def import_opencart_products_sync(
    payload: OCProductsImport,
    current_user=Depends(get_current_user),
    plugin_token: Optional[str] = None,
):
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



@app.get("/plugins/status", response_model=APIResponse, tags=["Plugins"])
async def get_plugins_status(current_user=Depends(get_current_user)):
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
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required")
        
        
        await revoke_plugin_token(token_id)
        
        return APIResponse(
            status="success",
            message="Plugin token revoked",
        )
    except Exception as e:
        logger.error(f"Error revoking plugin token: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/shops/register", response_model=APIResponse, tags=["OpenCart Shops"])
async def register_opencart_shop(
    request: CreateCatalogRequest,
    current_user=Depends(get_current_user),
):
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
    try:
        from opencart_catalog import get_shop, delete_shop
        
        shop = await get_shop(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        
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
    try:
        user_id = current_user[0]
        organization_id = _get_active_org_id(current_user)
        
        from opencart_catalog import get_shop, create_catalog, load_opencart_products_from_db
        
        shop = await get_shop(shop_id)
        if not shop:
            raise HTTPException(status_code=404, detail="Shop not found")
        
        
        if shop["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        
        catalog_id = await create_catalog(
            shop_name=shop["shop_name"],
            shop_url=shop["shop_url"],
            user_id=user_id,
            organization_id=organization_id,
            description=None
        )
        
        
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



@app.post("/catalogs/create", response_model=APIResponse, tags=["OpenCart Catalogs"])
async def create_new_catalog(
    request: CreateCatalogRequest,
    current_user=Depends(get_current_user),
):
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
    try:
        catalog = await get_catalog(catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Catalog not found")
        
        
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
    indexed_ids = []
    failed_ids = []
    
    for product in products:
        try:
            
            doc_content = f"""
Product Name: {product['name']}
Description: {product['description']}
Price: ${product['price']}
SKU: {product['sku']}
Product URL: {product['url']}
Customer Rating: {product.get('rating', 0)}/5
Store: {catalog['shop_name']}
"""
            
            # Add document to vector database
            indexed_ids.append(product['id'])
            
        except Exception as e:
            failed_ids.append(product['id'])
            continue
    
    return indexed_ids, failed_ids


@app.post("/login", response_model=TokenRoleResponse)
async def login_user(request: LoginRequest, request_obj: Request):
    client_ip = request_obj.client.host if request_obj and request_obj.client else None
    
    if not await verify_user(request.username, request.password):
        
        log_security_event(
            event_type="failed_login",
            ip_address=client_ip or "unknown",
            user_id=request.username,
            details={"reason": "Invalid credentials"},
            severity="medium"
        )
        
        
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
    
    
    session_id = str(uuid.uuid4())
    
    
    user = await get_user(request.username)
    organization_id = user[7] if user and len(user) > 7 else None  
    
    
    
    await create_session(request.username, session_id, expires_hours=24, organization_id=organization_id)
    
    
    if session_id:
        
        try:
            await update_access_token(request.username, session_id)
        except Exception as e:
            logger.warning(f"Failed to update access token: {e}")
    
    role = await get_user_role(request.username)
    logger.info(f"User {request.username} logged in successfully with session_id: {session_id[:8]}...")
    
    
    log_event(
        event_type="login",
        user_id=request.username,
        session_id=session_id,
        ip_address=client_ip,
        role=role,
        success=True,
        details={"session_type": "new"}
    )
    
    
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
        token=session_id,  
        role=role
    )


@app.post("/organizations/create_with_admin", response_model=TokenRoleResponse)
async def create_organization_with_admin(request: OrganizationCreateRequest, request_obj: Request):
    client_ip = request_obj.client.host if request_obj and request_obj.client else None

    
    request.admin_username = request.admin_username.replace(" ", "_")
    request.admin_password = request.admin_password.replace(" ", "_")

    
    slug = _slugify_org_name(request.organization_name)
    existing_org = await get_organization_by_slug(slug)
    if existing_org:
        return TokenRoleResponse(
            status="error",
            message="Organization with this name/slug already exists",
            token=None,
            role=None,
        )

    
    if await get_user(request.admin_username):
        return TokenRoleResponse(
            status="error",
            message="Admin username already exists",
            token=None,
            role=None,
        )

    
    org_id = await create_organization(name=request.organization_name, slug=slug)
    
    await create_user(
        username=request.admin_username,
        password=request.admin_password,
        role="admin",
        allowed_files=["all"],
        organization_id=org_id,
    )

    
    await create_organization_membership(
        organization_id=org_id,
        username=request.admin_username,
        role="owner",
    )

    
    session_id = str(uuid.uuid4())
    await create_session(
        request.admin_username,
        session_id,
        expires_hours=24,
        organization_id=org_id,
    )
    await update_access_token(request.admin_username, session_id)

    
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


@app.post("/logout", response_model=APIResponse)
async def logout_user(
    request_obj: Request,
    user=Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
):
    try:
        session_id = credentials.credentials
        client_ip = request_obj.client.host if request_obj and request_obj.client else None
        
        
        success = await logout_session_by_id(session_id)
        
        
        await update_access_token(user[1], None)  
        
        
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


@app.get("/token/validate", response_model=APIResponse)
async def validate_token(user=Depends(get_current_user)):
    try:
        username = user[1]
        role = user[3]
        created_at = user[5] if len(user) > 5 else None

        organization_id = _get_active_org_id(user)
        organization_name = None
        if organization_id:
            org_row = await get_organization_by_id(organization_id)
            if org_row and len(org_row) > 1:
                organization_name = org_row[1]
        
        logger.debug(f"Token validated for user: {username}")
        
        return APIResponse(
            status="success",
            message="Token is valid",
            response={
                "valid": True,
                "username": username,
                "role": role,
                "created_at": created_at,
                "organization_id": organization_id,
                "organization_name": organization_name,
                "organization": organization_name,
            }
        )
    except Exception as e:
        logger.warning(f"Token validation failed: {e}")
        return APIResponse(
            status="error",
            message="Token is invalid or expired",
            response={"valid": False}
        )


@app.get("/admin/access", response_model=APIResponse)
async def check_admin_access(user=Depends(get_current_user)):
    try:
        username = user[1]
        role = user[3]
        
        
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


@app.get("/docs", include_in_schema=False)
async def get_documentation():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - Swagger UI"
    )


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_schema():
    return app.openapi()

async def get_available_filenames(username: str) -> List[str]:
    try:
        
        candidate = chunk_text
        if "'title'" in candidate and '"title"' not in candidate:
            candidate = candidate.replace("'", '"')
        
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
    
    import re
    m = re.search(r"['\"]title['\"]\s*:\s*['\"]([^'\"]+)['\"]", chunk_text)
    if m:
        return m.group(1).strip()
    return None


async def get_user_from_token(token: str):
    if not token:
        return None
    
    
    user = await get_user_by_session_id(token)
    if user:
        return user
    
    
    user = await get_user_by_token(token)
    return user


@app.websocket("/ws/query")
async def websocket_query_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    logger = logging.getLogger(__name__)
    
    tracker = None
    if ADVANCED_ANALYTICS_ENABLED and PerformanceTracker:
        try:
            tracker = PerformanceTracker(f"query_endpoint('{request.question[:50]}...')", logger)
        except Exception:
            tracker = None

    try:
        username = user[1]  
        role = user[3]  
        organization_id = _get_active_org_id(user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required for queries.")
        session_id = str(uuid.uuid4())  
        client_ip = request_obj.client.host if request_obj and hasattr(request_obj, 'client') and request_obj.client else None
        
        model_type = "local" if os.getenv("RAG_MODEL_TYPE", "server").lower() == "local" else "server"

        
        if tracker:
            tracker.start_operation("query_start")
        start_time = datetime.datetime.now()

        
        if tracker:
            tracker.start_operation("cleanup_sessions")
        await cleanup_expired_sessions()
        if tracker:
            tracker.end_operation("cleanup_sessions")

        
        if tracker:
            tracker.start_operation("init_rag_chain")
        from rag_api.langchain_utils import get_rag_chain
        rag_chain = get_rag_chain()
        if tracker:
            tracker.end_operation("init_rag_chain")

        
        if tracker:
            tracker.start_operation("secure_retrieval")
        secure_retriever = SecureRAGRetriever(username=username, session_id=session_id, organization_id=organization_id)
        rag_result = await secure_retriever.invoke_secure_rag_chain(
            rag_chain=rag_chain,
            query=request.question,
            model_type=model_type,
            humanize=request.humanize if hasattr(request, 'humanize') and request.humanize is not None else True,
            skip_llm=True  
        )
        if tracker:
            tracker.end_operation("secure_retrieval")

        
        source_docs = rag_result.get("source_documents", [])
        source_docs_raw = rag_result.get("source_documents_raw", [])
        security_filtered = rag_result.get("security_filtered", False)
        
        
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
                
                
                snippet = {
                    "content": content,
                    "source": source
                }
                
                
                if isinstance(doc, dict):
                    meta = doc.get("metadata", {})
                else:
                    meta = doc.metadata if hasattr(doc, "metadata") else {}
                
                if "catalog_id" in meta:
                    
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

        
        if tracker:
            tracker.start_operation("calculate_response_time")
        response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
        if tracker:
            tracker.end_operation("calculate_response_time")

        
        if tracker:
            tracker.start_operation("get_client_ip")
        client_ip = request_obj.client.host if request_obj.client else "unknown"
        if tracker:
            tracker.end_operation("get_client_ip")

        
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

        
        if tracker:
            tracker.start_operation("log_metrics")
        
        
        response_text = overview if overview else "\n".join([s["content"][:100] + "..." for s in immediate_response["snippets"][:3]])
        
        
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

        
        for filename in immediate_response["files"]:
            log_file_access(
                user_id=username,
                role=role,
                filename=filename,
                access_type="retrieved_in_rag",
                session_id=session_id,
                ip_address=client_ip,
                query_context=request.question[:100]  
            )

        
        insert_application_logs(
            session_id,
            request.question,
            f"Found {len(source_docs)} source documents [Security filtered: {security_filtered}]",
            model_type
        )
        
        
        if ADVANCED_ANALYTICS_ENABLED and QueryMetrics:
            try:
                analytics = get_analytics_core()
                if analytics and QueryMetrics:
                    query_metrics = QueryMetrics(
                        query_id=session_id,
                        session_id=session_id,
                        user_id=username,
                        role=role,
                        organization_id=organization_id,
                        question=request.question,
                        answer_preview=(response_text[:500] if response_text else None),
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


@app.post("/search/opencart", response_model=APIResponse)
async def search_opencart_products(
    request: RAGQueryRequest,
    request_obj: Request,
    user=Depends(get_current_user)
):
    username = user[1]
    role = user[2]
    organization_id = user[3]
    session_id = request.session_id or str(uuid.uuid4())
    start_time = datetime.datetime.now()
    
    try:
        
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
        
        
        model_type = request.model_type or await get_default_model()
        
        
        tracker = PerformanceTracker(session_id=session_id)
        tracker.start_operation("opencart_search_start")
        
        
        catalogs_to_search = []
        if request.catalog_ids and len(request.catalog_ids) > 0:
            
            catalogs_to_search = request.catalog_ids
        else:
            
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
        
        
        opencart_docs = []
        
        try:
            logger.info(f"Searching for products with query: {request.question}")
            
            
            limit = getattr(request, 'limit', 20)
            offset = getattr(request, 'offset', 0)
            
            
            try:
                products = await search_products_in_catalogs(
                    catalog_ids=catalogs_to_search,
                    search_term=request.question,
                    limit=limit,
                    offset=offset
                )
                
                logger.info(f"Found {len(products)} products via direct search")
                
                
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
            
        
        tracker.end_operation("opencart_search")
        
        
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
        
        
        response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
        
        
        client_ip = request_obj.client.host if request_obj.client else None
        
        
        tracker.start_operation("log_metrics")
        
        
        response_text = "\n".join([s["metadata"]["name"] for s in immediate_response["snippets"][:5] if s["metadata"].get("name")])
        
        
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
        
        
        insert_application_logs(
            session_id,
            request.question,
            f"OpenCart search: Found {len(opencart_docs)} products from catalogs {catalogs_to_search}",
            model_type
        )
        
        
        if ADVANCED_ANALYTICS_ENABLED:
            try:
                analytics = get_analytics_core()
                query_metrics = QueryMetrics(
                    query_id=session_id,
                    session_id=session_id,
                    user_id=username,
                    role=role,
                    organization_id=organization_id,
                    question=request.question,
                    answer_preview=(response_text[:500] if response_text else None),
                    answer_length=len(response_text or ""),
                    model_type=model_type,
                    query_type=QueryType.DIRECT if QueryType else "direct",
                    response_time_ms=int(response_time),
                    source_document_count=len(opencart_docs),
                    source_files=immediate_response.get("files") or [],
                    humanized=False,
                    success=True,
                    ip_address=client_ip or "unknown",
                )
                analytics.log_query(query_metrics)
            except Exception as e:
                logger.warning(f"Failed to log OpenCart search to advanced analytics: {e}")
        
        tracker.end_operation("log_metrics")
        
        logger.info(f"OpenCart search for user {username}: {len(opencart_docs)} products found from {len(catalogs_to_search)} catalogs")
        
        
        return APIResponse(
            status="success",
            message=f"OpenCart product search completed - {len(opencart_docs)} products found",
            response=immediate_response
        )
    
    except Exception as e:
        logger.exception(f"OpenCart search processing error for user {username if 'username' in locals() else 'unknown'}")
        return APIResponse(status="error", message=str(e), response=None)

from fastapi.responses import PlainTextResponse, JSONResponse, Response
from urllib.parse import unquote


@app.get("/files/content/{filename}")
async def get_file_content(
    filename: str,
    request_obj: Request,
    user = Depends(get_current_user),
    include_quiz: bool = Query(False, description="If true, return JSON with file content and quiz"),
    catalog_id: str = Query(None, description="If provided, treat filename as product name and return OpenCart product data")
):
    from org_security import enforce_organization_context
    
    decoded_filename = unquote(filename)
    organization_id = enforce_organization_context(user, required=True)
    
    
    client_ip = request_obj.client.host if request_obj and request_obj.client else None
    
    
    if catalog_id:
        logger.info(f"User {user[1]} from org {organization_id} requests OpenCart product: {decoded_filename} from catalog {catalog_id}")
        
        
        try:
            from rag_api.chroma_utils import vectorstore
            
            
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
                
                metadata = results['metadatas'][0] if results['metadatas'] else {}
                
                
                log_file_access(
                    user_id=user[1],
                    role=user[3],
                    filename=decoded_filename,
                    access_type="view_opencart",
                    session_id=None,
                    ip_address=client_ip
                )
                
                
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
    
    
    resolved_filename = resolve_actual_filename_case_insensitive(decoded_filename)
    allowed_files = await get_allowed_files(user[1])
    
    logger.info(f"User {user[1]} from org {organization_id} requests file: {decoded_filename} (resolved: {resolved_filename}). Allowed files: {allowed_files}")
    
    
    if user[3] != "admin":
        if allowed_files is not None and resolved_filename not in allowed_files:
            
            log_security_event(
                event_type="unauthorized_file_access",
                ip_address=client_ip or "unknown",
                user_id=user[1],
                details={"filename": resolved_filename, "organization_id": organization_id},
                severity="medium"
            )
            raise HTTPException(status_code=403, detail="You do not have access to this file.")
    
    
    content_bytes = get_file_content_by_filename(resolved_filename, organization_id=organization_id)
    if content_bytes is None:
        logger.warning(f"File not found in DB: {decoded_filename}")
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        
        
        ext = os.path.splitext(resolved_filename)[1].lower()
        binary_mime_types = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }
        binary_mime = binary_mime_types.get(ext)

        if binary_mime:
            if include_quiz:
                import base64 as _base64

                
                quiz_row = await get_quiz_by_filename(resolved_filename)
                quiz_payload: Dict[str, Any]
                if quiz_row:
                    try:
                        quiz_dict = json.loads(quiz_row[3]) if quiz_row[3] else None
                    except Exception:
                        quiz_dict = {"questions": [], "raw": quiz_row[3]}
                    quiz_payload = {
                        "id": quiz_row[0],
                        "filename": quiz_row[1],
                        "timestamp": quiz_row[2],
                        "quiz": quiz_dict,
                        "logs": quiz_row[4],
                    }
                else:
                    quiz_payload = {}

                return JSONResponse(
                    content={
                        "filename": resolved_filename,
                        "content": _base64.b64encode(content_bytes).decode("ascii"),
                        "isBinary": True,
                        "mimeType": binary_mime,
                        "quiz": quiz_payload,
                    }
                )

            return Response(content=content_bytes, media_type=binary_mime)

        
        try:
            content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = content_bytes.decode("latin1")
        
        
        log_file_access(
            user_id=user[1],
            role=user[3],
            filename=resolved_filename,
            access_type="view",
            session_id=None,
            ip_address=client_ip or "unknown"
        )

        if include_quiz:
            
            quiz_row = await get_quiz_by_filename(resolved_filename)
            quiz_payload: Dict[str, Any]
            if quiz_row:
                
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

        
        return PlainTextResponse(content)
    except Exception as e:
        logger.exception(f"Failed to decode file {resolved_filename}")
        raise HTTPException(status_code=500, detail=f"Failed to decode file: {e}")


@app.post("/quiz/{filename}", response_model=APIResponse)
async def create_or_get_quiz(
    filename: str,
    request_obj: Request,
    user = Depends(get_current_user),
    regenerate: bool = Query(False, description="If true, re-generate a new quiz for the file")
):
    decoded_filename = unquote(filename)
    resolved_filename = resolve_actual_filename_case_insensitive(decoded_filename)
    allowed_files = await get_allowed_files(user[1])
    logger.info(f"User {user[1]} requests quiz for file: {decoded_filename} (resolved: {resolved_filename}). Allowed files: {allowed_files}")

    
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

        
        if regenerate or not quiz_row:
            new_quiz_id = await create_quiz_for_filename(resolved_filename)
            if not new_quiz_id:
                return APIResponse(status="error", message="Failed to generate quiz", response=None)
            quiz_row = await get_quiz_by_filename(resolved_filename)

        if not quiz_row:
            return APIResponse(status="error", message="Quiz not found", response=None)

        
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


@app.post("/chat", response_model=APIResponse)
async def secure_chat(
    request: RAGQueryRequest,
    request_obj: Request,
    session_id: str = Query(..., description="Session ID for chat history"),
    user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")

    organization_id = _get_active_org_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=400, detail="Organization context required for upload.")

    
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
        
        content_bytes = await file.read()
        
        
        logger.info(f"Starting upload: {original_filename}")
        logger.info(f"  - Upload ID: {upload_id}")
        logger.info(f"  - User: {current_user[1]}")
        logger.info(f"  - File type: {file_extension}")
        logger.info(f"  - File size: {len(content_bytes)} bytes")
        logger.info(f"  - Timestamp: {timestamp}")
        
        
        if file_extension == '.zip':
            logger.info(f"Archive detected. Extracting and processing contents as separate files...")
            import zipfile
            import tempfile
            
            extracted_files = []
            failed_files = []
            
            with tempfile.TemporaryDirectory() as temp_extract_dir:
                
                try:
                    
                    temp_zip_path = f"temp_{original_filename}"
                    with open(temp_zip_path, 'wb') as buffer:
                        buffer.write(content_bytes)
                    
                    
                    with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                        logger.info(f"Archive extracted with {len(zip_ref.filelist)} total files (UTF-8 filename support enabled)")
                        
                        
                        for member in zip_ref.filelist:
                            try:
                                
                                
                                raw_filename = member.filename
                                filename_to_use = raw_filename
                                
                                
                                
                                if isinstance(raw_filename, str) and any(ord(c) > 127 for c in raw_filename):
                                    
                                    try:
                                        
                                        
                                        attempt1 = raw_filename.encode('latin-1').decode('utf-8')
                                        filename_to_use = attempt1
                                        logger.debug(f"Successfully decoded via latin-1→utf-8: {raw_filename} -> {attempt1}")
                                    except (UnicodeDecodeError, UnicodeEncodeError):
                                        
                                        try:
                                            attempt2 = raw_filename.encode('cp437').decode('utf-8')
                                            filename_to_use = attempt2
                                            logger.debug(f"Successfully decoded via cp437→utf-8: {raw_filename} -> {attempt2}")
                                        except (UnicodeDecodeError, UnicodeEncodeError):
                                            
                                            logger.debug(f"Could not decode {raw_filename}, keeping original")
                                            filename_to_use = raw_filename
                                
                                
                                member.filename = filename_to_use
                                extracted_path = zip_ref.extract(member, temp_extract_dir)
                                
                            except Exception as e:
                                logger.warning(f"Could not extract {member.filename}: {str(e)}")
                                try:
                                    zip_ref.extract(member, temp_extract_dir)
                                except Exception as e2:
                                    logger.error(f"Failed to extract {member.filename}: {str(e2)}")
                    
                    
                    if os.path.exists(temp_zip_path):
                        os.remove(temp_zip_path)
                    
                    allowed_archive_extensions = ['.pdf', '.docx', '.doc', '.html', '.txt', '.md']
                    
                    for root, dirs, files in os.walk(temp_extract_dir):
                        for extracted_filename in files:
                            extracted_file_path = os.path.join(root, extracted_filename)
                            extracted_ext = os.path.splitext(extracted_filename)[1].lower()
                            
                            
                            if extracted_ext not in allowed_archive_extensions:
                                logger.info(f"Skipping unsupported file in archive: {extracted_filename} ({extracted_ext})")
                                continue
                            
                            try:
                                logger.info(f"Processing extracted file: {extracted_filename}")
                                
                                
                                if get_file_content_by_filename(extracted_filename, organization_id=organization_id) is not None:
                                    logger.warning(f"File {extracted_filename} already exists in DB, skipping")
                                    continue
                                
                                
                                with open(extracted_file_path, 'rb') as f:
                                    extracted_content = f.read()
                                
                                
                                extracted_file_id = insert_document_record(extracted_filename, extracted_content, organization_id=organization_id)
                                logger.info(f"  Saved to database: {extracted_filename} (file_id: {extracted_file_id})")
                                
                                
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
            
            
            if get_file_content_by_filename(original_filename, organization_id=organization_id) is not None:
                raise HTTPException(status_code=400, detail="A file with this name already exists.")
            
            
            file_id = insert_document_record(original_filename, content_bytes, organization_id=organization_id)
            logger.info(f"  - Database file_id: {file_id}")

            
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
                
                try:
                    asyncio.create_task(create_quiz_for_filename(original_filename, organization_id=organization_id))
                except Exception:
                    pass
                
                
                logger.info(f"✓ Upload completed successfully: {original_filename} (ID: {file_id}, Upload ID: {upload_id})")
                
                
                if ADVANCED_ANALYTICS_ENABLED:
                    try:
                        analytics = get_analytics_core()
                        if analytics and file_id:
                            
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


@app.get("/files/list", response_model=APIResponse)
async def list_documents(user=Depends(get_current_user)):
    try:
        organization_id = _get_active_org_id(user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        documents = get_all_documents(organization_id=organization_id)
        allowed_files = await get_allowed_files(user[1])
        logger.info(f"User {user[1]} role {user[3]} allowed files: {allowed_files}")
        
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


@app.delete("/files/delete_by_fileid", response_model=APIResponse)
async def delete_document(
    request: DeleteFileRequest,
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            organization_id = ""  
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


@app.get("/files/available")
async def list_available_filenames():
    try:
        
        files = []
        if os.path.exists(UPLOAD_DIR):
            for file in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, file)
                if os.path.isfile(file_path):
                    files.append(file)
        
        
        db_files = get_all_documents()  
        db_filenames = []
        for doc in db_files:
            if isinstance(doc, dict):
                db_filenames.append(doc.get("filename"))
            elif isinstance(doc, (list, tuple)) and len(doc) > 1:
                db_filenames.append(doc[1])
        
        
        all_files = list(set(files + db_filenames))
        
        return {
            "status": "success",
            "files": all_files,
            "count": len(all_files)
        }
    except Exception as e:
        logger.error(f"Error listing available files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing available files: {str(e)}")


@app.delete("/files/delete_by_filename", response_model=APIResponse)
async def delete_file_by_filename(filename: str, current_user=Depends(get_current_user)):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    
    filename = unquote(filename) 
    print(f"Deleting file by filename: {filename}")
    organization_id = _get_active_org_id(current_user)
    if not organization_id:
        raise HTTPException(status_code=400, detail="Organization context required.")

    
    documents = get_all_documents(organization_id=organization_id)
    file_id = None
    for doc in documents:
        
        if isinstance(doc, dict) and doc.get("filename") == filename:
            file_id = doc.get("id")
            break
        elif isinstance(doc, (list, tuple)) and len(doc) > 1 and doc[1] == filename:
            file_id = doc[0]
            break
    if not file_id:
        raise HTTPException(status_code=404, detail="File not found in database.")
    
    chroma_delete_success = delete_doc_from_chroma(file_id, organization_id=organization_id)
    
    db_delete_success = delete_document_record(file_id)
    
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



@app.post("/files/index", response_model=APIResponse, tags=["Documents"])
async def index_files(
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    try:
        organization_id = _get_active_org_id(current_user)
        if not organization_id:
            raise HTTPException(status_code=400, detail="Organization context required.")
        
        from rag_api.db_utils import get_unindexed_documents
        from rag_api.chroma_utils import index_document_to_chroma, delete_doc_from_chroma
        
        logger.info(f"Starting manual indexation for organization {organization_id}")
        
        
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
                
                
                if content:
                    
                    temp_file_path = f"temp_{filename}"
                    try:
                        
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



@app.get("/accounts", response_model=List[dict])
async def get_accounts(current_user=Depends(get_current_user)):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    
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
    
    
    if is_admin and admin_user:
        admin_org_id = _get_active_org_id(admin_user)
        user_org_id = user[7] if len(user) > 7 else None  
        if admin_org_id != user_org_id:
            raise HTTPException(status_code=403, detail="Cannot delete users from other organizations.")
    
    
    import userdb
    await userdb.delete_user(username)
    return APIResponse(status="success", message=f"User {username} deleted", response={})


@app.post("/user/edit", response_model=APIResponse)
async def edit_user_endpoint(
    request: UserEditRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
):
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
    
    
    if is_admin and admin_user:
        admin_org_id = _get_active_org_id(admin_user)
        user_org_id = user[7] if len(user) > 7 else None  
        if admin_org_id != user_org_id:
            raise HTTPException(status_code=403, detail="Cannot edit users from other organizations.")
    
    logs = []
    import userdb
    
    if request.new_username:
        await userdb.update_username(request.username, request.new_username)
        logs.append(f"Username changed to {request.new_username}")
        request.username = request.new_username
    
    if request.password:
        await userdb.update_password(request.username, request.password)
        logs.append("Password updated")
    
    if request.role:
        await userdb.update_role(request.username, request.role)
        logs.append(f"Role changed to {request.role}")
    
    if request.allowed_files is not None:
        previous_files = await userdb.get_allowed_files(request.username)
        await userdb.update_allowed_files(request.username, request.allowed_files)
        logs.append(f"Allowed files updated to {request.allowed_files}")

        
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
                            
                            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                                temp_file.write(content)
                                temp_path = temp_file.name

                            
                            index_document_to_chroma(temp_path, filename)
                            os.unlink(temp_path)  
                    except Exception as e:
                        logger.error(f"Error reindexing file {filename} after permission update: {e}")

    if not logs:
        return APIResponse(status="success", message="No changes made", response={})
    return APIResponse(status="success", message="; ".join(logs), response={})


@app.put("/user/{username}", response_model=APIResponse)
async def update_user_endpoint(
    username: str,
    request: UserEditRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
):
    
    request.username = username
    
    
    return await edit_user_endpoint(request, credentials)


class DisruptSessionsRequest(BaseModel):
    access_token: str

@app.post("/user/disrupt_sessions", response_model=APIResponse)
async def disrupt_sessions_endpoint(request: DisruptSessionsRequest):
    user = await get_user_by_token(request.access_token)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid access token.")
    from userdb import disrupt_sessions_for_user
    username = user[1]
    count = await disrupt_sessions_for_user(username)
    return APIResponse(status="success", message=f"Disrupted {count} sessions for user {username}", response={"sessions_removed": count})


@app.post("/files/edit", response_model=APIResponse)
async def edit_file_content(
    filename: str = Body(..., embed=True),
    new_content: str = Body(..., embed=True),
    user=Depends(get_current_user)
):
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    try:
        from rag_api.db_utils import update_document_record
        from rag_api.chroma_utils import index_document_to_chroma, delete_doc_from_chroma
        import os
        
        file_ids = update_document_record(filename, new_content.encode("utf-8"))
        if not file_ids:
            return APIResponse(status="error", message="File not found in DB", response=None)
        
        temp_file_path = f"temp_{filename}"
        with open(temp_file_path, "w", encoding="utf-8") as buffer:
            buffer.write(new_content)
        
        for file_id in file_ids:
            delete_doc_from_chroma(file_id)
            index_document_to_chroma(temp_file_path, file_id)
        os.remove(temp_file_path)
        return APIResponse(status="success", message="File updated and reindexed", response={"file_ids": file_ids, "filename": filename})
    except Exception as e:
        return APIResponse(status="error", message=str(e), response=None)


class TimeRangeQuery(BaseModel):
    since: str = "24h"  



@app.get("/metrics/summary", tags=["Analytics"])
async def get_metrics_summary_endpoint(
    since: str = Query("24h", description="Time range: 1h, 24h, 7d, etc"),
    scope: str = Query("org", description="user|org|global"),
    current_user=Depends(get_current_user)
):
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

        
        user_id = None
        organization_id = None
        if scope == "user":
            user_id = current_user[1]
            organization_id = _get_active_org_id(current_user)
        elif scope == "org":
            organization_id = _get_active_org_id(current_user)
        elif scope == "global":
            if current_user[3] != "admin":
                raise HTTPException(status_code=403, detail="Admin required for global metrics")
        else:
            raise HTTPException(status_code=400, detail="Invalid scope. Use: user|org|global")

        summary = analytics.get_query_statistics(
            since_hours=hours,
            user_id=user_id,
            organization_id=organization_id,
        )
        
        
        return {
            "status": "success",
            "message": "ok",
            "response": {
                "total_queries": int(summary.get('total_queries', 0) or 0),
                "successful_queries": int(summary.get('successful_queries', 0) or 0),
                "failed_queries": int(summary.get('failed_queries', 0) or 0),
                "avg_response_time": round(summary.get('avg_response_time_ms', 0) or 0, 2),
                "period": since,
                "scope": scope,
                "organization_id": organization_id,
                "user_id": user_id,
            },
        }
    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metrics/queries", tags=["Analytics"])
async def get_metrics_queries(
    since: str = Query("24h", description="Time range"),
    limit: int = Query(10, le=100),
    offset: int = Query(0),
    scope: str = Query("org", description="user|org|global"),
    current_user=Depends(get_current_user)
):
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

        
        user_id = None
        organization_id = None
        if scope == "user":
            user_id = current_user[1]
            organization_id = _get_active_org_id(current_user)
        elif scope == "org":
            organization_id = _get_active_org_id(current_user)
        elif scope == "global":
            if current_user[3] != "admin":
                raise HTTPException(status_code=403, detail="Admin required for global metrics")
        else:
            raise HTTPException(status_code=400, detail="Invalid scope. Use: user|org|global")

        queries = analytics.get_query_analytics(
            limit=limit,
            offset=offset,
            since_hours=hours,
            user_id=user_id,
            organization_id=organization_id,
        )

        
        simplified = []
        for q in queries:
            simplified.append({
                "question": q.get("question"),
                "answer": q.get("answer_preview") or "",
                "timestamp": q.get("timestamp"),
            })
        
        return {
            "status": "success",
            "message": "ok",
            "response": {
                "queries": simplified,
                "period": since,
                "scope": scope,
                "organization_id": organization_id,
                "user_id": user_id,
                "limit": limit,
                "offset": offset,
            },
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
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")
    
    try:
        analytics = get_analytics_core()
        stats = analytics.get_query_statistics(since_hours=1)
        
        
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
                "avg_response_time_ms": round(float(stats.get('avg_response_time_ms') or 0), 2),
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


@app.get("/dashboard/employee", tags=["Dashboard"])
async def get_employee_dashboard_data(
    current_user=Depends(get_current_user),
    since: str = Query("24h", description="Time range: 1h, 24h, 7d, etc"),
):
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")

    if since.endswith('h'):
        hours = int(since[:-1])
    elif since.endswith('d'):
        hours = int(since[:-1]) * 24
    else:
        hours = 24

    username = current_user[1]
    organization_id = _get_active_org_id(current_user)
    
    if not organization_id:
        logger.warning(f"User {username} accessing employee dashboard without organization context")

    analytics = get_analytics_core()
    user_stats = analytics.get_query_statistics(
        since_hours=hours,
        user_id=username,
        organization_id=organization_id,
    )
    org_stats_24h = analytics.get_query_statistics(
        since_hours=24,
        organization_id=organization_id,
    )

    recent = analytics.get_query_analytics(
        limit=10,
        offset=0,
        since_hours=hours,
        user_id=username,
        organization_id=organization_id,
    )
    recent_queries = []
    unique_files = set()
    for q in recent:
        try:
            src = q.get("source_files")
            if isinstance(src, str):
                import json as _json
                src = _json.loads(src) if src else []
            if isinstance(src, list):
                for f in src:
                    if isinstance(f, str) and f:
                        unique_files.add(f)
        except Exception:
            pass

        recent_queries.append({
            "question": q.get("question"),
            "answer": q.get("answer_preview") or "",
            "timestamp": q.get("timestamp"),
            "success": bool(q.get("success")),
        })

    try:
        from rag_api.db_utils import get_all_documents
        documents = get_all_documents(organization_id=organization_id)
    except Exception:
        documents = []

    new_docs_week = 0
    try:
        import datetime as _dt
        cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=7)
        for d in documents:
            ts = d.get("upload_timestamp") if isinstance(d, dict) else None
            if not ts:
                continue
            try:
                if isinstance(ts, str):
                    dt = _dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
                else:
                    dt = ts
                if dt.replace(tzinfo=None) >= cutoff:
                    new_docs_week += 1
            except Exception:
                continue
    except Exception:
        new_docs_week = 0

    return {
        "status": "success",
        "message": "ok",
        "response": {
            "user_metrics": {
                "total_queries": int(user_stats.get("total_queries", 0) or 0),
                "successful_queries": int(user_stats.get("successful_queries", 0) or 0),
                "failed_queries": int(user_stats.get("failed_queries", 0) or 0),
                "avg_response_time": round(user_stats.get("avg_response_time_ms", 0) or 0, 2),
                "documents_accessed": int(len(unique_files)),
            },
            "recent_queries": recent_queries,
            "organization_stats": {
                "organization_id": organization_id,
                "total_documents": int(len(documents)),
                "new_documents": int(new_docs_week),
                "active_users": int(org_stats_24h.get("unique_users", 0) or 0),
            },
        },
    }


@app.get("/dashboard/admin", tags=["Dashboard"])
async def get_admin_dashboard_data(
    current_user=Depends(get_current_user),
    since: str = Query("24h", description="Time range: 1h, 24h, 7d, etc"),
    scope: str = Query("global", description="org|global"),
    organization_id: Optional[str] = Query(None, description="Org ID when scope=org"),
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    if not ADVANCED_ANALYTICS_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")

    if since.endswith('h'):
        hours = int(since[:-1])
    elif since.endswith('d'):
        hours = int(since[:-1]) * 24
    else:
        hours = 24

    resolved_org = None
    if scope == "org":
        resolved_org = organization_id or _get_active_org_id(current_user)
        if not resolved_org:
            raise HTTPException(status_code=400, detail="Organization context required")
    elif scope == "global":
        resolved_org = None
    else:
        raise HTTPException(status_code=400, detail="Invalid scope. Use: org|global")

    analytics = get_analytics_core()
    summary = analytics.get_query_statistics(since_hours=hours, organization_id=resolved_org)
    summary_24h = analytics.get_query_statistics(since_hours=24, organization_id=resolved_org)
    summary_week = analytics.get_query_statistics(since_hours=168, organization_id=resolved_org)

    error_rate = 0.0
    try:
        total = float(summary.get("total_queries", 0) or 0)
        failed = float(summary.get("failed_queries", 0) or 0)
        error_rate = (failed / total) * 100 if total > 0 else 0.0
    except Exception:
        error_rate = 0.0

    health_status = "healthy"
    if error_rate >= 10:
        health_status = "critical"
    elif error_rate >= 5:
        health_status = "warning"

    active_sessions = 0
    try:
        import aiosqlite
        import datetime as _dt
        from userdb import DB_PATH as _USERS_DB_PATH
        now = _dt.datetime.utcnow().isoformat()
        async with aiosqlite.connect(_USERS_DB_PATH) as conn:
            if resolved_org:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM user_sessions WHERE expires_at > ? AND organization_id = ?",
                    (now, resolved_org),
                )
            else:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM user_sessions WHERE expires_at > ?",
                    (now,),
                )
            row = await cursor.fetchone()
            active_sessions = int(row[0] if row else 0)
    except Exception:
        active_sessions = 0

    storage_used_gb = 0.0
    try:
        from rag_api.db_utils import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        if resolved_org:
            cur.execute("SELECT COALESCE(SUM(LENGTH(content)), 0) as total_bytes FROM document_store WHERE organization_id = ?", (resolved_org,))
        else:
            cur.execute("SELECT COALESCE(SUM(LENGTH(content)), 0) as total_bytes FROM document_store")
        row = cur.fetchone()
        conn.close()
        total_bytes = int(row[0] if row and row[0] is not None else 0)
        storage_used_gb = round(total_bytes / (1024 ** 3), 4)
    except Exception:
        storage_used_gb = 0.0

    total_storage_gb = 100.0
    storage_pct = round((storage_used_gb / total_storage_gb) * 100, 2) if total_storage_gb > 0 else 0

    total_documents = 0
    documents_uploaded_today = 0
    try:
        from rag_api.db_utils import get_db_connection
        import datetime as _dt
        conn = get_db_connection()
        cur = conn.cursor()
        if resolved_org:
            cur.execute("SELECT COUNT(*) FROM document_store WHERE organization_id = ?", (resolved_org,))
        else:
            cur.execute("SELECT COUNT(*) FROM document_store")
        row = cur.fetchone()
        total_documents = int(row[0] if row else 0)

        cutoff = (_dt.datetime.utcnow() - _dt.timedelta(hours=24)).isoformat()
        if resolved_org:
            cur.execute(
                "SELECT COUNT(*) FROM document_store WHERE organization_id = ? AND upload_timestamp >= ?",
                (resolved_org, cutoff),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM document_store WHERE upload_timestamp >= ?", (cutoff,))
        row2 = cur.fetchone()
        documents_uploaded_today = int(row2[0] if row2 else 0)
        conn.close()
    except Exception:
        total_documents = 0
        documents_uploaded_today = 0

    top_docs = []
    try:
        docs = analytics.get_top_documents(limit=3, organization_id=resolved_org)
        for d in docs:
            views = int((d.get("rag_hit_count", 0) or 0) + (d.get("access_count", 0) or 0))
            top_docs.append({
                "filename": d.get("filename"),
                "views": views,
                "last_accessed": d.get("last_accessed") or d.get("created_at")
            })
    except Exception:
        top_docs = []

    failed_logins = 0
    suspicious_activity = 0
    permission_denials = 0
    try:
        conn = analytics.db.get_connection()
        cur = conn.cursor()
        where = ["timestamp >= datetime('now', ? || ' hours')"]
        params = [-24]
        if resolved_org:
            where.append("organization_id = ?")
            params.append(resolved_org)
        cur.execute(
            f"SELECT event_type, COUNT(*) as c FROM security_events WHERE {' AND '.join(where)} GROUP BY event_type",
            params,
        )
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            et = r[0] if not isinstance(r, dict) else r.get("event_type")
            c = r[1] if not isinstance(r, dict) else r.get("c")
            if et == "failed_login":
                failed_logins = int(c or 0)
            elif et == "suspicious_activity":
                suspicious_activity = int(c or 0)
            elif et == "permission_denied":
                permission_denials = int(c or 0)
    except Exception:
        pass

    top_users = []
    try:
        conn = analytics.db.get_connection()
        cur = conn.cursor()
        where = ["timestamp >= datetime('now', ? || ' hours')"]
        params = [-hours]
        if resolved_org:
            where.append("organization_id = ?")
            params.append(resolved_org)
        cur.execute(
            f"SELECT user_id, COUNT(*) as c, MAX(timestamp) as last_active FROM query_analytics WHERE {' AND '.join(where)} GROUP BY user_id ORDER BY c DESC LIMIT 5",
            params,
        )
        rows = cur.fetchall()
        conn.close()
        for r in rows:
            top_users.append({
                "username": r[0],
                "queries": int(r[1] or 0),
                "last_active": r[2],
            })
    except Exception:
        top_users = []

    total_users = 0
    try:
        from userdb import list_users
        users = await list_users(resolved_org) if resolved_org else await list_users(None)
        total_users = len(users)
    except Exception:
        total_users = 0

    trends = []
    try:
        conn = analytics.db.get_connection()
        cur = conn.cursor()
        where = ["timestamp >= datetime('now', ? || ' hours')"]
        params = [-24]
        if resolved_org:
            where.append("organization_id = ?")
            params.append(resolved_org)
        cur.execute(
            f"SELECT question, COUNT(*) as c FROM query_analytics WHERE {' AND '.join(where)} GROUP BY question ORDER BY c DESC LIMIT 5",
            params,
        )
        rows = cur.fetchall()
        conn.close()
        for q, c in rows:
            term = (q or "")
            if len(term) > 60:
                term = term[:57] + "..."
            trends.append({"term": term, "frequency": int(c or 0), "trend": "stable"})
    except Exception:
        trends = []

    success_rate = 0.0
    try:
        tq = float(summary.get("total_queries", 0) or 0)
        sq = float(summary.get("successful_queries", 0) or 0)
        success_rate = (sq / tq) * 100 if tq > 0 else 0.0
    except Exception:
        success_rate = 0.0

    avg_queries_per_user = 0.0
    try:
        uq = float(summary.get("unique_users", 0) or 0)
        tq = float(summary.get("total_queries", 0) or 0)
        avg_queries_per_user = tq / uq if uq > 0 else 0.0
    except Exception:
        avg_queries_per_user = 0.0

    return {
        "status": "success",
        "message": "ok",
        "response": {
            "system_health": {
                "status": health_status,
                "uptime": 99.9,
                "api_response_time": round(summary.get("avg_response_time_ms", 0) or 0, 2),
                "error_rate": round(error_rate, 2),
                "active_connections": int(active_sessions),
                "database_status": "connected",
                "storage_usage": {
                    "used": float(storage_used_gb),
                    "total": float(total_storage_gb),
                    "percentage": float(storage_pct),
                },
            },
            "user_analytics": {
                "total_users": int(total_users),
                "active_users_today": int(summary_24h.get("unique_users", 0) or 0),
                "new_registrations_today": 0,
                "active_users_week": int(summary_week.get("unique_users", 0) or 0),
                "user_growth_rate": 0,
                "top_active_users": top_users,
                "pending_approvals": 0,
            },
            "content_metrics": {
                "total_documents": int(total_documents),
                "documents_uploaded_today": int(documents_uploaded_today),
                "storage_used_gb": float(storage_used_gb),
                "popular_documents": top_docs,
                "flagged_content": 0,
                "processing_queue": 0,
            },
            "security_alerts": {
                "failed_logins": int(failed_logins),
                "suspicious_activity": int(suspicious_activity),
                "permission_denials": int(permission_denials),
                "active_sessions": int(active_sessions),
                "api_key_usage": [],
            },
            "business_intelligence": {
                "search_trends": trends,
                "department_usage": [],
                "productivity_metrics": {
                    "avg_queries_per_user": round(avg_queries_per_user, 2),
                    "success_rate": round(success_rate, 2),
                    "response_time_avg": round(summary.get("avg_response_time_ms", 0) or 0, 2),
                },
                "cost_metrics": {
                    "cost_per_query": 0,
                    "daily_operational_cost": 0,
                    "monthly_projection": 0,
                },
            },
            "scope": scope,
            "organization_id": resolved_org,
            "period": since,
        },
    }



@app.get("/metrics/summary-legacy", tags=["Analytics (Deprecated)"], deprecated=True)
async def get_metrics_summary_legacy(
    since: str = "24h",
    current_user=Depends(get_current_user)
):
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
    return {
        "status": "deprecated",
        "message": "This endpoint is deprecated. Please use /metrics/queries instead.",
        "redirect": "/metrics/queries"
    }





class QuizQuestionCreate(BaseModel):
    question: str
    options: List[str]
    answer: str
    explanation: Optional[str] = None
    points: int = 10

class QuizCreate(BaseModel):
    title: str
    description: str
    category: str
    difficulty: str = "medium"
    time_limit: int = 15
    passing_score: int = 70
    questions: List[QuizQuestionCreate]

class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    time_limit: Optional[int] = None
    passing_score: Optional[int] = None
    questions: Optional[List[QuizQuestionCreate]] = None

class QuizSubmissionCreate(BaseModel):
    quiz_id: str
    answers: Dict[str, str]
    time_spent: int

@app.post("/admin/quizzes", response_model=APIResponse, tags=["Quiz Management"])
async def create_quiz(
    quiz_data: QuizCreate,
    request_obj: Request,
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    organization_id = _get_active_org_id(current_user)
    
    try:
        
        questions = [QuizQuestion(**q.dict()) for q in quiz_data.questions]
        
        quiz_id = await create_manual_quiz(
            title=quiz_data.title,
            description=quiz_data.description,
            category=quiz_data.category,
            difficulty=quiz_data.difficulty,
            time_limit=quiz_data.time_limit,
            passing_score=quiz_data.passing_score,
            questions=questions,
            created_by=current_user[1],
            organization_id=organization_id
        )
        
        return APIResponse(
            status="success",
            message="Quiz created successfully",
            response={"quiz_id": quiz_id}
        )
    except Exception as e:
        logger.error(f"Error creating quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/quizzes", response_model=APIResponse, tags=["Quiz Management"])
async def list_quizzes(
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    organization_id = _get_active_org_id(current_user)
    
    try:
        quizzes = await get_all_quizzes(
            organization_id=organization_id,
            category=category,
            difficulty=difficulty,
            limit=limit,
            offset=offset
        )
        
        return APIResponse(
            status="success",
            message="Quizzes retrieved successfully",
            response={
                "quizzes": [quiz.dict() for quiz in quizzes],
                "total": len(quizzes)
            }
        )
    except Exception as e:
        logger.error(f"Error listing quizzes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/quizzes/{quiz_id}", response_model=APIResponse, tags=["Quiz Management"])
async def get_quiz(
    quiz_id: str,
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    organization_id = _get_active_org_id(current_user)
    
    try:
        quiz = await get_quiz_by_id(quiz_id, organization_id)
        
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        return APIResponse(
            status="success",
            message="Quiz retrieved successfully",
            response=quiz.dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/admin/quizzes/{quiz_id}", response_model=APIResponse, tags=["Quiz Management"])
async def update_quiz_endpoint(
    quiz_id: str,
    quiz_data: QuizUpdate,
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    organization_id = _get_active_org_id(current_user)
    
    try:
        
        questions = None
        if quiz_data.questions is not None:
            questions = [QuizQuestion(**q.dict()) for q in quiz_data.questions]
        
        success = await update_quiz(
            quiz_id=quiz_id,
            title=quiz_data.title,
            description=quiz_data.description,
            category=quiz_data.category,
            difficulty=quiz_data.difficulty,
            time_limit=quiz_data.time_limit,
            passing_score=quiz_data.passing_score,
            questions=questions,
            organization_id=organization_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        return APIResponse(
            status="success",
            message="Quiz updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/quizzes/{quiz_id}", response_model=APIResponse, tags=["Quiz Management"])
async def delete_quiz_endpoint(
    quiz_id: str,
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    organization_id = _get_active_org_id(current_user)
    
    try:
        success = await delete_quiz(quiz_id, organization_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        return APIResponse(
            status="success",
            message="Quiz deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quizzes", response_model=APIResponse, tags=["Quiz Management"])
async def get_available_quizzes(
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user)
):
    organization_id = _get_active_org_id(current_user)
    
    try:
        quizzes = await get_all_quizzes(
            organization_id=organization_id,
            category=category,
            difficulty=difficulty,
            limit=limit,
            offset=offset
        )
        
        
        quiz_summaries = []
        for quiz in quizzes:
            quiz_summaries.append({
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "category": quiz.category,
                "difficulty": quiz.difficulty,
                "time_limit": quiz.time_limit,
                "passing_score": quiz.passing_score,
                "question_count": len(quiz.questions),
                "created_at": quiz.created_at
            })
        
        return APIResponse(
            status="success",
            message="Quizzes retrieved successfully",
            response={
                "quizzes": quiz_summaries,
                "total": len(quiz_summaries)
            }
        )
    except Exception as e:
        logger.error(f"Error getting available quizzes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quizzes/{quiz_id}", response_model=APIResponse, tags=["Quiz Management"])
async def get_quiz_for_user(
    quiz_id: str,
    current_user=Depends(get_current_user)
):
    organization_id = _get_active_org_id(current_user)
    
    try:
        quiz = await get_quiz_by_id(quiz_id, organization_id)
        
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        return APIResponse(
            status="success",
            message="Quiz retrieved successfully",
            response=quiz.dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz for user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/quizzes/{quiz_id}/submit", response_model=APIResponse, tags=["Quiz Management"])
async def submit_quiz(
    quiz_id: str,
    submission: QuizSubmissionCreate,
    current_user=Depends(get_current_user)
):
    organization_id = _get_active_org_id(current_user)
    
    try:
        
        quiz = await get_quiz_by_id(quiz_id, organization_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        
        score = 0
        total_points = 0
        
        for question in quiz.questions:
            total_points += question.points
            user_answer = submission.answers.get(str(quiz.questions.index(question)))
            if user_answer == question.answer:
                score += question.points
        
        passed = (score / total_points * 100) >= quiz.passing_score
        
        
        submission_id = await submit_quiz_result(
            quiz_id=quiz_id,
            user_id=current_user[1],
            answers=submission.answers,
            score=score,
            total_points=total_points,
            passed=passed,
            time_spent=submission.time_spent,
            organization_id=organization_id
        )
        
        return APIResponse(
            status="success",
            message="Quiz submitted successfully",
            response={
                "submission_id": submission_id,
                "score": score,
                "total_points": total_points,
                "passed": passed,
                "percentage": round((score / total_points * 100), 2) if total_points > 0 else 0
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/quizzes/{quiz_id}/statistics", response_model=APIResponse, tags=["Quiz Management"])
async def get_quiz_stats(
    quiz_id: str,
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    organization_id = _get_active_org_id(current_user)
    
    try:
        stats = await get_quiz_statistics(quiz_id, organization_id)
        
        return APIResponse(
            status="success",
            message="Statistics retrieved successfully",
            response=stats
        )
    except Exception as e:
        logger.error(f"Error getting quiz statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/quizzes/{quiz_id}/submissions", response_model=APIResponse, tags=["Quiz Management"])
async def get_quiz_submissions_admin(
    quiz_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user)
):
    if current_user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    organization_id = _get_active_org_id(current_user)
    
    try:
        submissions = await get_quiz_submissions(
            quiz_id=quiz_id,
            organization_id=organization_id,
            limit=limit,
            offset=offset
        )
        
        return APIResponse(
            status="success",
            message="Submissions retrieved successfully",
            response={
                "submissions": [sub.dict() for sub in submissions],
                "total": len(submissions)
            }
        )
    except Exception as e:
        logger.error(f"Error getting quiz submissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
