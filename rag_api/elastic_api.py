from fastapi import APIRouter, HTTPException, Depends, Query, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from rag_api.elastic_config import INDEXES, get_es_config, get_index_name
from rag_api.elastic_client import (
    create_index, delete_index, index_exists, get_index_stats,
    health_check, bulk_index
)
from rag_api.elastic_indexer import (
    ensure_indexes, index_rag_document, delete_rag_document,
    sync_from_chroma, reindex_all, index_all_documents
)
from rag_api.elastic_search import (
    search_documents, hybrid_search, search_logs, search_queries,
    get_suggestions, get_facets, semantic_search, fulltext_search
)
from userdb import get_user_by_session_id, get_user_allowed_filenames

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/es", tags=["Elasticsearch"])


async def get_current_user(token: str):
    user = await get_user_by_session_id(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


async def get_user_access_info(user):
    username = user[1]
    role = user[3]
    if role == "admin":
        return {"role": role, "allowed_files": None, "org_id": None}
    allowed_files = await get_user_allowed_filenames(username)
    return {"role": role, "allowed_files": allowed_files, "org_id": None}


class ESSearchRequest(BaseModel):
    query: str
    index: str = "documents"
    filters: Optional[Dict[str, Any]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    size: int = 10
    offset: int = 0
    highlight: bool = True
    search_type: str = "hybrid"
    language: Optional[str] = None
    semantic_weight: float = 0.6
    keyword_weight: float = 0.4


class SemanticSearchRequest(BaseModel):
    query: str
    size: int = 10
    similarity_threshold: float = 0.1
    highlight: bool = True
    language: Optional[str] = None


class FulltextSearchRequest(BaseModel):
    query: str
    size: int = 10
    offset: int = 0
    highlight: bool = True
    language: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class HybridSearchRequest(BaseModel):
    query: str
    size: int = 10
    semantic_weight: float = 0.6
    keyword_weight: float = 0.4
    fusion_method: str = "rrf"
    language: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class IndexCreateRequest(BaseModel):
    index_key: str = Field(..., description="Index key: documents, logs, queries, products")


class APIResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None


@router.get("/health")
async def es_health():
    """Check Elasticsearch connection health"""
    try:
        result = await health_check()
        if result.get("status") == "connected":
            return {
                "status": "success",
                "elasticsearch": result
            }
        else:
            return {
                "status": "error",
                "elasticsearch": result
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/config")
async def get_config():
    """Get Elasticsearch configuration"""
    config = get_es_config()
    return {
        "status": "success",
        "config": {
            "host": config["host"],
            "port": config["port"],
            "scheme": config["scheme"],
            "indexes": config["indexes"],
            "embedding_dims": config["embedding_dims"],
            "languages": config["languages"]
        }
    }


@router.post("/index/{index_key}", response_model=APIResponse)
async def create_es_index(index_key: str, user=Depends(get_current_user)):
    """Create an Elasticsearch index (admin only)"""
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        index_name = get_index_name(index_key)
        success = await ensure_indexes()
        if success.get(index_key, False):
            return APIResponse(
                status="success",
                message=f"Index {index_name} created/verified",
                data={"index_name": index_name}
            )
        else:
            return APIResponse(
                status="error",
                message=f"Failed to create index {index_name}",
                data={}
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Index creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/index/{index_key}", response_model=APIResponse)
async def delete_es_index(index_key: str, user=Depends(get_current_user)):
    """Delete an Elasticsearch index (admin only)"""
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        index_name = get_index_name(index_key)
        success = await delete_index(index_name)
        return APIResponse(
            status="success" if success else "error",
            message=f"Index {index_name} deleted" if success else f"Failed to delete {index_name}",
            data={"index_name": index_name}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Index deletion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/{index_key}/stats", response_model=APIResponse)
async def get_index_statistics(index_key: str, user=Depends(get_current_user)):
    """Get Elasticsearch index statistics"""
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        index_name = get_index_name(index_key)
        exists = await index_exists(index_name)
        if not exists:
            raise HTTPException(status_code=404, detail=f"Index {index_name} not found")

        stats = await get_index_stats(index_name)
        return APIResponse(
            status="success",
            message=f"Statistics for {index_name}",
            data={"index": index_name, "stats": stats}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=APIResponse)
async def es_search_endpoint(
    request: ESSearchRequest,
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Unified search with type selection (semantic, fulltext, hybrid)"""
    try:
        access_info = await get_user_access_info(user)
        index_name = get_index_name(request.index) if request.index != "documents" else INDEXES["documents"]

        date_range = None
        if request.date_from or request.date_to:
            date_range = {}
            if request.date_from:
                date_range["from"] = request.date_from
            if request.date_to:
                date_range["to"] = request.date_to

        result = await search_documents(
            query=request.query,
            org_id=access_info.get("org_id"),
            user_id=user[1],
            role=access_info["role"],
            allowed_files=access_info["allowed_files"],
            filters=request.filters,
            date_range=date_range,
            size=request.size,
            offset=request.offset,
            highlight=request.highlight,
            search_type=request.search_type,
            language=request.language
        )

        return APIResponse(
            status=result.get("status", "success"),
            message=f"Found {result.get('total', 0)} results",
            data={
                "results": result.get("results", []),
                "total": result.get("total", 0),
                "took_ms": result.get("took_ms", 0),
                "type": result.get("type", request.search_type),
                "query": result.get("query"),
                "language": result.get("language")
            }
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/semantic", response_model=APIResponse)
async def semantic_search_endpoint(
    request: SemanticSearchRequest,
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Pure semantic search using ES k-NN"""
    try:
        access_info = await get_user_access_info(user)

        result = await semantic_search(
            query=request.query,
            org_id=access_info.get("org_id"),
            user_id=user[1],
            role=access_info["role"],
            allowed_files=access_info["allowed_files"],
            language=request.language,
            size=request.size,
            similarity_threshold=request.similarity_threshold,
            highlight=request.highlight
        )

        return APIResponse(
            status=result.get("status", "success"),
            message=f"Semantic search: {result.get('total', 0)} results",
            data={
                "results": result.get("results", []),
                "total": result.get("total", 0),
                "took_ms": result.get("took_ms", 0),
                "type": "semantic",
                "language": result.get("language")
            }
        )
    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/fulltext", response_model=APIResponse)
async def fulltext_search_endpoint(
    request: FulltextSearchRequest,
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Full-text search with multilingual support"""
    try:
        access_info = await get_user_access_info(user)

        result = await fulltext_search(
            query=request.query,
            org_id=access_info.get("org_id"),
            user_id=user[1],
            role=access_info["role"],
            allowed_files=access_info["allowed_files"],
            language=request.language,
            filters=request.filters,
            size=request.size,
            offset=request.offset,
            highlight=request.highlight
        )

        return APIResponse(
            status=result.get("status", "success"),
            message=f"Fulltext search: {result.get('total', 0)} results",
            data={
                "results": result.get("results", []),
                "total": result.get("total", 0),
                "took_ms": result.get("took_ms", 0),
                "type": "fulltext",
                "language": result.get("language")
            }
        )
    except Exception as e:
        logger.error(f"Fulltext search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/hybrid", response_model=APIResponse)
async def hybrid_search_endpoint(
    request: HybridSearchRequest,
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Hybrid search combining semantic (ES k-NN) and keyword search"""
    try:
        access_info = await get_user_access_info(user)

        result = await hybrid_search(
            query=request.query,
            org_id=access_info.get("org_id"),
            user_id=user[1],
            role=access_info["role"],
            allowed_files=access_info["allowed_files"],
            language=request.language,
            filters=request.filters,
            size=request.size,
            semantic_weight=request.semantic_weight,
            keyword_weight=request.keyword_weight,
            fusion_method=request.fusion_method
        )

        return APIResponse(
            status=result.get("status", "success"),
            message=f"Hybrid search: {result.get('total', 0)} results",
            data={
                "results": result.get("results", []),
                "total": result.get("total", 0),
                "took_ms": result.get("took_ms", 0),
                "type": "hybrid",
                "fusion_method": result.get("fusion_method"),
                "weights": result.get("weights"),
                "semantic_count": result.get("semantic_count", 0),
                "keyword_count": result.get("keyword_count", 0)
            }
        )
    except Exception as e:
        logger.error(f"Hybrid search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/suggest", response_model=APIResponse)
async def es_suggestions(
    q: str = Query(..., min_length=2, description="Search prefix"),
    field: str = Query("content.suggest", description="Field to suggest on"),
    size: int = Query(5, le=20),
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Get autocomplete suggestions"""
    try:
        access_info = await get_user_access_info(user)

        suggestions = await get_suggestions(
            prefix=q,
            field=field,
            size=size,
            org_id=access_info.get("org_id")
        )

        return APIResponse(
            status="success",
            message=f"Found {len(suggestions)} suggestions",
            data={"suggestions": suggestions}
        )
    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/facets", response_model=APIResponse)
async def es_facets(
    fields: str = Query(..., description="Comma-separated facet fields"),
    query: Optional[str] = Query(None),
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user),
    size: int = Query(10, le=100)
):
    """Get faceted search aggregations"""
    try:
        access_info = await get_user_access_info(user)
        facet_fields = [f.strip() for f in fields.split(",")]

        result = await get_facets(
            facet_fields=facet_fields,
            query=query,
            org_id=access_info.get("org_id"),
            size=size
        )

        return APIResponse(
            status=result.get("status", "success"),
            message="Facets retrieved",
            data={
                "facets": result.get("facets", {}),
                "total_docs": result.get("total_docs", 0)
            }
        )
    except Exception as e:
        logger.error(f"Facets error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/search", response_model=APIResponse)
async def search_es_logs(
    query: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    since_hours: int = Query(24, le=168),
    size: int = Query(100, le=1000),
    offset: int = Query(0),
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Search application logs"""
    try:
        if user[3] != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        result = await search_logs(
            query=query,
            org_id=None,
            session_id=session_id,
            user_id=user_id,
            model=model,
            since_hours=since_hours,
            size=size,
            offset=offset
        )

        return APIResponse(
            status=result.get("status", "success"),
            message=f"Found {result.get('total', 0)} logs",
            data={
                "results": result.get("results", []),
                "total": result.get("total", 0)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logs search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queries/search", response_model=APIResponse)
async def search_es_queries(
    query: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    model_type: Optional[str] = Query(None),
    since_hours: int = Query(24, le=168),
    size: int = Query(100, le=1000),
    offset: int = Query(0),
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Search query analytics"""
    try:
        if user[3] != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        result = await search_queries(
            query=query,
            org_id=None,
            user_id=user_id,
            role=role,
            model_type=model_type,
            since_hours=since_hours,
            size=size,
            offset=offset
        )

        return APIResponse(
            status=result.get("status", "success"),
            message=f"Found {result.get('total', 0)} queries",
            data={
                "results": result.get("results", []),
                "total": result.get("total", 0)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Queries search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex/full", response_model=APIResponse)
async def full_reindex(
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Full reindex from ChromaDB to Elasticsearch (admin only)"""
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        result = await reindex_all()
        return APIResponse(
            status=result.get("status", "completed"),
            message=result.get("status", "Reindex completed"),
            data={
                "index": result.get("index"),
                "chunks_indexed": result.get("chunks_indexed", 0),
                "failed": result.get("failed", 0),
                "total_time_seconds": result.get("total_time_seconds", 0),
                "errors": result.get("errors", [])
            }
        )
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex/sync", response_model=APIResponse)
async def sync_from_chroma_endpoint(
    batch_size: int = Query(100, ge=1, le=1000),
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Sync documents from ChromaDB to Elasticsearch (admin only)"""
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        result = await sync_from_chroma(batch_size=batch_size)
        return APIResponse(
            status="success" if result["failed"] == 0 else "partial",
            message=f"Synced {result['synced']} documents",
            data={
                "synced": result["synced"],
                "failed": result["failed"],
                "total_time_seconds": result["total_time_seconds"],
                "errors": result.get("errors", [])
            }
        )
    except Exception as e:
        logger.error(f"Sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex/file/{filename}", response_model=APIResponse)
async def reindex_file(
    filename: str,
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Reindex a specific file (admin only)"""
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        from rag_api.db_utils import get_all_documents, get_file_content_by_filename

        documents = get_all_documents()
        file_id = None
        for doc in documents:
            if doc.get("filename") == filename:
                file_id = doc.get("id")
                break

        if not file_id:
            raise HTTPException(status_code=404, detail=f"File {filename} not found")

        content = get_file_content_by_filename(filename)
        if not content:
            raise HTTPException(status_code=404, detail=f"Content not found for {filename}")

        result = await index_rag_document(
            doc_id=file_id,
            filename=filename,
            content=content
        )

        return APIResponse(
            status="success",
            message=f"Reindexed {filename}",
            data={
                "filename": filename,
                "doc_id": file_id,
                "chunks_indexed": result.get("chunks_indexed", 0)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/document/{doc_id}", response_model=APIResponse)
async def delete_document(
    doc_id: int,
    credentials: str = Query(..., description="Session token"),
    user=Depends(get_current_user)
):
    """Delete a document from Elasticsearch (admin only)"""
    if user[3] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        result = await delete_rag_document(doc_id)
        return APIResponse(
            status="success",
            message=f"Deleted {result.get('deleted', 0)} chunks",
            data={
                "doc_id": doc_id,
                "deleted": result.get("deleted", 0),
                "failed": result.get("failed", 0)
            }
        )
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
