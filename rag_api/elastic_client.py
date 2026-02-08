import logging
from typing import Dict, Any, Optional, List
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import NotFoundError, ConnectionError as ESConnectionError

from rag_api.elastic_config import get_index_mapping, get_client as get_es_client, close_client

logger = logging.getLogger(__name__)


async def create_index(index_name: str, settings: Dict[str, Any] = None, mappings: Dict[str, Any] = None) -> bool:
    es = await get_es_client()
    try:
        if await es.indices.exists(index=index_name):
            logger.info(f"Index {index_name} already exists")
            return True

        body = {}
        if settings:
            body["settings"] = settings
        if mappings:
            body["mappings"] = mappings

        await es.indices.create(index=index_name, body=body)
        logger.info(f"Created index: {index_name}")
        return True
    except Exception as e:
        logger.error(f"Error creating index {index_name}: {e}")
        return False
    finally:
        await es.close()


async def delete_index(index_name: str) -> bool:
    es = await get_es_client()
    try:
        if not await es.indices.exists(index=index_name):
            logger.info(f"Index {index_name} does not exist")
            return True

        await es.indices.delete(index=index_name)
        logger.info(f"Deleted index: {index_name}")
        return True
    except NotFoundError:
        logger.info(f"Index {index_name} not found")
        return True
    except Exception as e:
        logger.error(f"Error deleting index {index_name}: {e}")
        return False
    finally:
        await es.close()


async def index_exists(index_name: str) -> bool:
    es = await get_es_client()
    try:
        exists = await es.indices.exists(index=index_name)
        return exists
    except Exception as e:
        logger.error(f"Error checking index {index_name}: {e}")
        return False
    finally:
        await es.close()


async def get_index_stats(index_name: str) -> Dict[str, Any]:
    es = await get_es_client()
    try:
        stats = await es.indices.stats(index=index_name)
        indices_stats = stats["indices"].get(index_name, {})
        return {
            "docs": indices_stats.get("primaries", {}).get("docs", {}),
            "store": indices_stats.get("primaries", {}).get("store", {}),
            "indexing": indices_stats.get("primaries", {}).get("indexing", {}),
            "search": indices_stats.get("primaries", {}).get("search", {})
        }
    except NotFoundError:
        return {"error": f"Index {index_name} not found"}
    except Exception as e:
        logger.error(f"Error getting stats for {index_name}: {e}")
        return {"error": str(e)}
    finally:
        await es.close()


async def refresh_index(index_name: str) -> bool:
    es = await get_es_client()
    try:
        await es.indices.refresh(index=index_name)
        return True
    except Exception as e:
        logger.error(f"Error refreshing index {index_name}: {e}")
        return False
    finally:
        await es.close()


async def index_document(index_name: str, doc_id: str, document: Dict[str, Any]) -> bool:
    es = await get_es_client()
    try:
        await es.index(index=index_name, id=doc_id, document=document)
        return True
    except Exception as e:
        logger.error(f"Error indexing document {doc_id}: {e}")
        return False
    finally:
        await es.close()


async def get_document(index_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
    es = await get_es_client()
    try:
        result = await es.get(index=index_name, id=doc_id)
        return result["_source"]
    except NotFoundError:
        return None
    except Exception as e:
        logger.error(f"Error getting document {doc_id}: {e}")
        return None
    finally:
        await es.close()


async def delete_document(index_name: str, doc_id: str) -> bool:
    es = await get_es_client()
    try:
        await es.delete(index=index_name, id=doc_id)
        return True
    except NotFoundError:
        return True
    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}")
        return False
    finally:
        await es.close()


async def bulk_index(index_name: str, documents: List[Dict[str, Any]], chunk_size: int = 500) -> Dict[str, Any]:
    import numpy as np
    import logging
    logger = logging.getLogger(__name__)
    
    es = await get_es_client()
    success = 0
    failed = 0
    errors = []

    for i in range(0, len(documents), chunk_size):
        batch = documents[i:i + chunk_size]
        actions = []
        for doc in batch:
            doc_id = doc.get("_id") or doc.get("doc_id") or doc.get("id")
            doc_id_str = str(doc_id) if doc_id else None
            doc_source = {k: v for k, v in doc.items() if k not in ["doc_id", "id", "_id"]}
            
            if "embedding" in doc_source:
                emb = doc_source["embedding"]
                if isinstance(emb, np.ndarray):
                    doc_source["embedding"] = emb.tolist()
                elif emb is None or (hasattr(emb, '__len__') and len(emb) == 0):
                    doc_source["embedding"] = []
            
            if doc_id_str:
                try:
                    await es.index(index=index_name, id=doc_id_str, document=doc_source, refresh=True)
                    success += 1
                except Exception as e:
                    logger.error(f"Index error for {doc_id_str}: {e}")
                    failed += 1
                    errors.append(str(e))
            else:
                try:
                    await es.index(index=index_name, document=doc_source, refresh=True)
                    success += 1
                except Exception as e:
                    logger.error(f"Index error: {e}")
                    failed += 1
                    errors.append(str(e))

    await es.close()
    return {"success": success, "failed": failed, "errors": errors}


async def search(index_name: str, body: Dict[str, Any] = None, size: int = 10, from_: int = 0) -> Dict[str, Any]:
    es = await get_es_client()
    try:
        search_params = {
            "index": index_name,
            "body": body
        }
        result = await es.search(**search_params)
        hits = []
        for hit in result["hits"]["hits"]:
            doc = hit.get("_source", {})
            doc["_id"] = hit.get("_id")
            doc["_score"] = hit.get("_score")
            hits.append(doc)
        return {
            "hits": hits,
            "total": result["hits"]["total"]["value"],
            "max_score": result["hits"].get("max_score")
        }
    except Exception as e:
        logger.error(f"Search error on {index_name}: {e}")
        return {"hits": [], "total": 0, "error": str(e)}
    finally:
        await es.close()


async def health_check() -> Dict[str, Any]:
    try:
        es = await get_es_client()
        info = await es.info()
        await es.close()
        return {
            "status": "connected",
            "cluster_name": info["cluster_name"],
            "version": info["version"]["number"]
        }
    except ESConnectionError as e:
        logger.error(f"Elasticsearch connection failed: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        logger.error(f"Elasticsearch health check failed: {e}")
        return {"status": "error", "error": str(e)}
