import logging
import time
import re
import sys
import os
from typing import Dict, Any, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rag_api.elastic_config import INDEXES
from rag_api.elastic_client import search as es_search_client

logger = logging.getLogger(__name__)

LANGUAGE_CODES = {
    'ru': 'russian', 'rus': 'russian',
    'en': 'english', 'eng': 'english'
}

_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            _embedding_model = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
        except Exception as e:
            logger.warning(f"Could not load embedding model: {e}")
    return _embedding_model

def embed_query(text: str) -> List[float]:
    """Generate embedding for a query using cached sentence-transformers"""
    model = get_embedding_model()
    if model is not None:
        return model.embed_query(text)
    return [0.0] * 384

def detect_language(text: str) -> str:
    """Detect language from text - Russian or English"""
    russian_chars = sum(1 for c in text.lower() if 'а' <= c <= 'я' or c in 'ёъыьэ')
    english_chars = sum(1 for c in text.lower() if 'a' <= c <= 'z')
    
    total = russian_chars + english_chars
    if total == 0:
        return 'multilingual'
    
    if russian_chars / total > 0.3:
        return 'russian'
    return 'english'


def preprocess_text(text: str) -> str:
    """Simple text preprocessing"""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def build_semantic_knn_query(
    embedding: List[float],
    k: int = 50,
    similarity_threshold: float = 0.1
) -> Dict[str, Any]:
    """Build ES k-NN query for semantic search"""
    return {
        "knn": {
            "field": "embedding",
            "query_vector": embedding,
            "k": k
        }
    }


def build_multilingual_query(
    query: str,
    language: str = None,
    fields: List[str] = None,
    fuzziness: str = "AUTO",
    phrase_slop: int = 2
) -> Dict[str, Any]:
    """Build multilingual full-text query"""
    if fields is None:
        fields = ["content^1", "content_normalized^0.8", "filename^2"]

    detected_lang = language or detect_language(query)
    
    boost_by_lang = {
        'russian': {"content_normalized": 1.2, "content": 1.0},
        'english': {"content_normalized": 1.2, "content": 1.0},
        'multilingual': {"content_normalized": 1.0, "content": 1.0}
    }
    
    lang_boost = boost_by_lang.get(detected_lang, boost_by_lang['multilingual'])
    
    boosted_fields = []
    for field in fields:
        if field.startswith("content") or field.startswith("content_normalized"):
            boost = lang_boost.get(field.replace("^1", "").replace("^0.8", ""), 1.0)
            parts = field.split("^")
            boosted_fields.append(f"{parts[0]}^{boost}")
        else:
            boosted_fields.append(field)

    return {
        "bool": {
            "should": [
                {
                    "multi_match": {
                        "query": query,
                        "fields": boosted_fields,
                        "type": "best_fields",
                        "fuzziness": fuzziness,
                        "prefix_length": 2,
                        "tie_breaker": 0.3,
                        "minimum_should_match": "50%"
                    }
                },
                {
                    "match_phrase": {
                        "content": {
                            "query": query,
                            "slop": phrase_slop,
                            "boost": 2.0
                        }
                    }
                },
                {
                    "match_phrase": {
                        "content_normalized": {
                            "query": query,
                            "slop": phrase_slop,
                            "boost": 1.5
                        }
                    }
                },
                {
                    "term": {
                        "filename": {
                            "value": query,
                            "boost": 3.0
                        }
                    }
                }
            ],
            "minimum_should_match": 1
        }
    }


def build_tenant_filter_query(
    org_id: str = None,
    user_id: str = None,
    role: str = None,
    allowed_files: List[str] = None,
    is_public: bool = None
) -> Dict[str, Any]:
    """Build multi-tenant security filter"""
    filter_clauses = []
    should_clauses = []
    
    if org_id:
        filter_clauses.append({"term": {"org_id": org_id}})
    
    if user_id:
        should_clauses.append({"term": {"owner_id": user_id}})
        should_clauses.append({"term": {"allowed_users": user_id}})
    
    if role:
        should_clauses.append({"term": {"allowed_roles": role}})
    
    if is_public is True:
        should_clauses.append({"term": {"is_public": True}})
    
    if allowed_files:
        should_clauses.append({"terms": {"filename": allowed_files}})
    
    query = {"bool": {}}
    
    if filter_clauses:
        query["bool"]["filter"] = filter_clauses
    
    if should_clauses:
        query["bool"]["should"] = should_clauses
        query["bool"]["minimum_should_match"] = 1
    
    if not filter_clauses and not should_clauses:
        query = {"match_all": {}}
    
    return query


def build_fulltext_query(
    query: str,
    fields: List[str] = None,
    fuzziness: str = "AUTO",
    phrase_slop: int = 2
) -> Dict[str, Any]:
    return build_multilingual_query(query, None, fields, fuzziness, phrase_slop)


def build_filter_query(
    filters: Dict[str, Any] = None,
    user_access: List[str] = None,
    date_range: Dict[str, str] = None
) -> Dict[str, Any]:
    must_clauses = []
    filter_clauses = []

    if user_access:
        filter_clauses.append({
            "terms": {"filename": user_access}
        })

    if filters:
        if "file_type" in filters:
            filter_clauses.append({
                "term": {"file_type": filters["file_type"]}
            })
        if "doc_id" in filters:
            filter_clauses.append({
                "term": {"doc_id": filters["doc_id"]}
            })
        if "filename" in filters:
            filter_clauses.append({
                "term": {"filename": filters["filename"]}
            })
        if "min_token_count" in filters:
            filter_clauses.append({
                "range": {"token_count": {"gte": filters["min_token_count"]}}
            })
        if "max_token_count" in filters:
            filter_clauses.append({
                "range": {"token_count": {"lte": filters["max_token_count"]}}
            })
        if "language" in filters:
            filter_clauses.append({
                "term": {"language": filters["language"]}
            })

    if date_range:
        range_clause = {}
        if "from" in date_range:
            range_clause["gte"] = date_range["from"]
        if "to" in date_range:
            range_clause["lte"] = date_range["to"]
        if range_clause:
            filter_clauses.append({"range": {"created_at": range_clause}})

    query = {"bool": {}}
    if must_clauses:
        query["bool"]["must"] = must_clauses
    query["bool"]["filter"] = filter_clauses

    return query


async def semantic_search(
    query: str,
    org_id: str = None,
    user_id: str = None,
    role: str = None,
    allowed_files: List[str] = None,
    language: str = None,
    size: int = 10,
    similarity_threshold: float = 0.1,
    highlight: bool = True
) -> Dict[str, Any]:
    """Pure semantic search using ES k-NN with embeddings"""
    start_time = time.time()

    preprocessed_query = preprocess_text(query)
    if not preprocessed_query:
        return {"status": "error", "message": "Empty query", "results": []}

    embedding = embed_query(preprocessed_query)

    tenant_filter = build_tenant_filter_query(org_id, user_id, role, allowed_files)

    knn_query = build_semantic_knn_query(embedding, k=size * 2, similarity_threshold=similarity_threshold)

    combined_query = {
        "bool": {
            "must": [knn_query],
            "filter": tenant_filter.get("bool", {}).get("filter", [])
        }
    }

    search_body: Dict[str, Any] = {
        "query": combined_query,
        "size": size,
        "from": 0
    }

    if highlight:
        search_body["highlight"] = {
            "fields": {"content": {}, "content_normalized": {}},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 150,
            "number_of_fragments": 3
        }

    try:
        result = await es_search_client(INDEXES["documents"], search_body)
        hits = result.get("hits", [])
        total = result.get("total", 0)

        results = []
        for hit in hits:
            doc = {k: v for k, v in hit.items() if k not in ["_source", "_id", "_score"]}
            doc["_id"] = hit.get("_id")
            doc["score"] = hit.get("_score", 0)
            if "_source" in hit:
                doc.update(hit["_source"])
            if "highlight" in hit:
                doc["highlights"] = hit["highlight"]
            results.append(doc)

        elapsed = (time.time() - start_time) * 1000

        return {
            "status": "success",
            "query": query,
            "language": language or detect_language(query),
            "results": results,
            "total": total,
            "type": "semantic",
            "took_ms": round(elapsed, 2)
        }

    except Exception as e:
        logger.error(f"Semantic search error: {e}")
        return {"status": "error", "message": str(e), "results": []}


async def fulltext_search(
    query: str,
    org_id: str = None,
    user_id: str = None,
    role: str = None,
    allowed_files: List[str] = None,
    language: str = None,
    filters: Dict[str, Any] = None,
    size: int = 10,
    offset: int = 0,
    highlight: bool = True
) -> Dict[str, Any]:
    """Full-text search with multilingual support"""
    start_time = time.time()

    preprocessed_query = preprocess_text(query)
    if not preprocessed_query:
        return {"status": "error", "message": "Empty query", "results": []}

    fulltext_query = build_multilingual_query(preprocessed_query, language)
    tenant_filter = build_tenant_filter_query(org_id, user_id, role, allowed_files)
    filter_query = build_filter_query(filters)

    combined_query = {
        "bool": {
            "must": [fulltext_query],
            "filter": tenant_filter.get("bool", {}).get("filter", []) + filter_query.get("bool", {}).get("filter", [])
        }
    }

    search_body: Dict[str, Any] = {
        "query": combined_query,
        "size": size,
        "from": offset
    }

    if highlight:
        search_body["highlight"] = {
            "fields": {"content": {}, "content_normalized": {}},
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fragment_size": 150,
            "number_of_fragments": 3
        }

    try:
        result = await es_search_client(INDEXES["documents"], search_body)
        hits = result.get("hits", [])
        total = result.get("total", 0)

        results = []
        for hit in hits:
            doc = {k: v for k, v in hit.items() if k not in ["_source", "_id", "_score"]}
            doc["_id"] = hit.get("_id")
            doc["score"] = hit.get("_score", 0)
            if "_source" in hit:
                doc.update(hit["_source"])
            if "highlight" in hit:
                doc["highlights"] = hit["highlight"]
            results.append(doc)

        elapsed = (time.time() - start_time) * 1000

        return {
            "status": "success",
            "query": query,
            "language": language or detect_language(query),
            "results": results,
            "total": total,
            "type": "fulltext",
            "took_ms": round(elapsed, 2)
        }

    except Exception as e:
        logger.error(f"Fulltext search error: {e}")
        return {"status": "error", "message": str(e), "results": []}


def fuse_rrf(es_results: List[Dict], keyword_results: List[Dict], k: int = 60) -> List[Dict]:
    scores = {}

    for rank, item in enumerate(es_results):
        filename = item.get("filename", "")
        chunk_index = item.get("chunk_index", 0)
        key = (filename, chunk_index)
        rrf_score = 1.0 / (k + rank + 1)
        es_score = item.get("score", 0)
        scores[key] = {
            **item,
            "semantic_rank": rank + 1,
            "semantic_score": es_score,
            "rrf_score": rrf_score,
            "combined_score": rrf_score + es_score * 0.1
        }

    for rank, item in enumerate(keyword_results):
        filename = item.get("filename", "")
        chunk_index = item.get("chunk_index", 0)
        key = (filename, chunk_index)
        rrf_score = 1.0 / (k + rank + 1)
        keyword_score = item.get("score", 0)
        if key in scores:
            scores[key]["keyword_rank"] = rank + 1
            scores[key]["keyword_score"] = keyword_score
            scores[key]["rrf_score"] = max(scores[key]["rrf_score"], rrf_score)
            scores[key]["combined_score"] += rrf_score + keyword_score * 0.1
        else:
            scores[key] = {
                **item,
                "keyword_rank": rank + 1,
                "keyword_score": keyword_score,
                "rrf_score": rrf_score,
                "combined_score": rrf_score + keyword_score * 0.1
            }

    return sorted(scores.values(), key=lambda x: x.get("combined_score", 0), reverse=True)


def fuse_weighted(es_results: List[Dict], keyword_results: List[Dict], es_weight: float, keyword_weight: float) -> List[Dict]:
    scores = {}

    for item in es_results:
        filename = item.get("filename", "")
        chunk_index = item.get("chunk_index", 0)
        key = (filename, chunk_index)
        es_score = item.get("score", 0) * es_weight
        scores[key] = {
            **item,
            "semantic_score": item.get("score", 0),
            "keyword_score": 0,
            "combined_score": es_score
        }

    for item in keyword_results:
        filename = item.get("filename", "")
        chunk_index = item.get("chunk_index", 0)
        key = (filename, chunk_index)
        keyword_score = item.get("score", 0) * keyword_weight
        if key in scores:
            scores[key]["keyword_score"] = item.get("score", 0)
            scores[key]["combined_score"] += keyword_score
        else:
            scores[key] = {
                **item,
                "semantic_score": 0,
                "keyword_score": item.get("score", 0),
                "combined_score": keyword_score
            }

    return sorted(scores.values(), key=lambda x: x.get("combined_score", 0), reverse=True)


async def hybrid_search(
    query: str,
    org_id: str = None,
    user_id: str = None,
    role: str = None,
    allowed_files: List[str] = None,
    language: str = None,
    filters: Dict[str, Any] = None,
    size: int = 10,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
    fusion_method: str = "rrf",
    rrf_k: int = 60
) -> Dict[str, Any]:
    """Hybrid search combining semantic (ES k-NN) and keyword search"""
    start_time = time.time()

    preprocessed_query = preprocess_text(query)
    if not preprocessed_query:
        return {"status": "error", "message": "Empty query", "results": []}

    semantic_results = []
    keyword_results = []

    try:
        semantic_result = await semantic_search(
            query=preprocessed_query,
            org_id=org_id, user_id=user_id, role=role,
            allowed_files=allowed_files, language=language,
            size=size * 2, similarity_threshold=0.1, highlight=True
        )
        if semantic_result.get("status") == "success":
            semantic_results = semantic_result.get("results", [])
    except Exception as e:
        logger.warning(f"Semantic search failed: {e}")

    try:
        keyword_result = await fulltext_search(
            query=preprocessed_query,
            org_id=org_id, user_id=user_id, role=role,
            allowed_files=allowed_files, language=language,
            filters=filters, size=size * 2, highlight=True
        )
        if keyword_result.get("status") == "success":
            keyword_results = keyword_result.get("results", [])
    except Exception as e:
        logger.warning(f"Keyword search failed: {e}")

    if fusion_method == "rrf":
        combined = fuse_rrf(semantic_results, keyword_results, k=rrf_k)
    elif fusion_method == "weighted":
        combined = fuse_weighted(semantic_results, keyword_results, semantic_weight, keyword_weight)
    else:
        combined = semantic_results[:size] + keyword_results[:size]

    unique_results = {}
    for item in combined:
        key = (item.get("filename", ""), item.get("chunk_index", 0))
        if key not in unique_results:
            unique_results[key] = item

    final_results = list(unique_results.values())[:size]

    elapsed = (time.time() - start_time) * 1000

    return {
        "status": "success",
        "query": query,
        "language": language or detect_language(query),
        "results": final_results,
        "total": len(final_results),
        "semantic_count": len(semantic_results),
        "keyword_count": len(keyword_results),
        "type": "hybrid",
        "fusion_method": fusion_method,
        "weights": {"semantic": semantic_weight, "keyword": keyword_weight},
        "took_ms": round(elapsed, 2)
    }


async def search_documents(
    query: str,
    org_id: str = None,
    user_id: str = None,
    role: str = None,
    allowed_files: List[str] = None,
    filters: Dict[str, Any] = None,
    date_range: Dict[str, str] = None,
    size: int = 10,
    offset: int = 0,
    highlight: bool = True,
    search_type: str = "hybrid",
    language: str = None,
    min_score: float = 0.1
) -> Dict[str, Any]:
    """Unified search with type selection"""
    if search_type == "semantic":
        return await semantic_search(
            query, org_id, user_id, role, allowed_files, language, size, min_score, highlight
        )
    elif search_type == "fulltext":
        return await fulltext_search(
            query, org_id, user_id, role, allowed_files, language, filters, size, offset, highlight
        )
    else:
        return await hybrid_search(
            query, org_id, user_id, role, allowed_files, language, filters, size, 0.6, 0.4, "rrf", 60
        )
