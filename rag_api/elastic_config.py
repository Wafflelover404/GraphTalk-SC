import os
from typing import Dict, Any, Optional
from elasticsearch import AsyncElasticsearch
import logging

logger = logging.getLogger(__name__)

ES_HOST = os.getenv("ES_HOST", "localhost")
ES_PORT = int(os.getenv("ES_PORT", "9200"))
ES_SCHEME = os.getenv("ES_SCHEME", "http")
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "")
ES_INDEX_PREFIX = os.getenv("ES_INDEX_PREFIX", "graphtalk")

INDEXES = {
    "documents": f"{ES_INDEX_PREFIX}_documents",
    "logs": f"{ES_INDEX_PREFIX}_logs",
    "queries": f"{ES_INDEX_PREFIX}_queries",
    "products": f"{ES_INDEX_PREFIX}_products",
}

DOCUMENTS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "multilang_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "russian_stemmer", "english_stemmer", "russian_stop", "english_stop"]
                }
            },
            "filter": {
                "russian_stemmer": {
                    "type": "stemmer",
                    "language": "russian"
                },
                "english_stemmer": {
                    "type": "stemmer",
                    "language": "english"
                },
                "russian_stop": {
                    "type": "stop",
                    "stopwords": "_russian_"
                },
                "english_stop": {
                    "type": "stop",
                    "stopwords": "_english_"
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "integer"},
            "filename": {"type": "keyword"},
            "content": {
                "type": "text",
                "analyzer": "multilang_analyzer",
                "fields": {
                    "raw": {"type": "keyword"},
                    "suggest": {
                        "type": "completion",
                        "analyzer": "multilang_analyzer"
                    }
                }
            },
            "content_normalized": {
                "type": "text",
                "analyzer": "multilang_analyzer"
            },
            "file_type": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "token_count": {"type": "integer"},
            "upload_timestamp": {"type": "date"},
            "created_at": {"type": "date"},
            "modified_at": {"type": "date"},
            "embedding": {
                "type": "dense_vector",
                "dims": 384,
                "index": True,
                "similarity": "cosine",
                "index_options": {
                    "type": "hnsw",
                    "m": 16,
                    "ef_construction": 64
                }
            },
            "relevance_score": {"type": "float"},
            "org_id": {"type": "keyword"},
            "owner_id": {"type": "keyword"},
            "language": {"type": "keyword"},
            "allowed_users": {"type": "keyword"},
            "allowed_roles": {"type": "keyword"},
            "is_public": {"type": "boolean"},
            "metadata": {"type": "object", "enabled": False}
        }
    }
}

LOGS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "multilang_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "russian_stemmer", "english_stemmer", "russian_stop", "english_stop"]
                }
            },
            "filter": {
                "russian_stemmer": {"type": "stemmer", "language": "russian"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                "english_stop": {"type": "stop", "stopwords": "_english_"}
            }
        }
    },
    "mappings": {
        "properties": {
            "session_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "org_id": {"type": "keyword"},
            "user_query": {"type": "text", "analyzer": "multilang_analyzer"},
            "gpt_response": {"type": "text", "analyzer": "multilang_analyzer"},
            "model": {"type": "keyword"},
            "created_at": {"type": "date"}
        }
    }
}

QUERIES_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "multilang_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "russian_stemmer", "english_stemmer", "russian_stop", "english_stop"]
                }
            },
            "filter": {
                "russian_stemmer": {"type": "stemmer", "language": "russian"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                "english_stop": {"type": "stop", "stopwords": "_english_"}
            }
        }
    },
    "mappings": {
        "properties": {
            "session_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "org_id": {"type": "keyword"},
            "role": {"type": "keyword"},
            "question": {"type": "text", "analyzer": "multilang_analyzer"},
            "answer": {"type": "text", "analyzer": "multilang_analyzer"},
            "model_type": {"type": "keyword"},
            "source_document_count": {"type": "integer"},
            "response_time_ms": {"type": "integer"},
            "timestamp": {"type": "date"},
            "security_filtered": {"type": "boolean"},
            "source_filenames": {"type": "keyword"}
        }
    }
}

PRODUCTS_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "multilang_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "russian_stemmer", "english_stemmer", "russian_stop", "english_stop"]
                }
            },
            "filter": {
                "russian_stemmer": {"type": "stemmer", "language": "russian"},
                "english_stemmer": {"type": "stemmer", "language": "english"},
                "russian_stop": {"type": "stop", "stopwords": "_russian_"},
                "english_stop": {"type": "stop", "stopwords": "_english_"}
            }
        }
    },
    "mappings": {
        "properties": {
            "product_id": {"type": "integer"},
            "org_id": {"type": "keyword"},
            "name": {"type": "text", "analyzer": "multilang_analyzer"},
            "sku": {"type": "keyword"},
            "price": {"type": "float"},
            "special": {"type": "float"},
            "description": {"type": "text", "analyzer": "multilang_analyzer"},
            "url": {"type": "keyword"},
            "image": {"type": "keyword"},
            "quantity": {"type": "integer"},
            "status": {"type": "integer"},
            "rating": {"type": "integer"},
            "updated_at": {"type": "date"}
        }
    }
}

INDEX_MAPPINGS = {
    INDEXES["documents"]: DOCUMENTS_MAPPING,
    INDEXES["logs"]: LOGS_MAPPING,
    INDEXES["queries"]: QUERIES_MAPPING,
    INDEXES["products"]: PRODUCTS_MAPPING,
}

_client: Optional[AsyncElasticsearch] = None


def get_es_config() -> Dict[str, Any]:
    return {
        "host": ES_HOST,
        "port": ES_PORT,
        "scheme": ES_SCHEME,
        "username": ES_USERNAME,
        "password": ES_PASSWORD,
        "index_prefix": ES_INDEX_PREFIX,
        "indexes": INDEXES,
        "embedding_dims": 384,
        "languages": ["russian", "english"]
    }


async def get_client() -> AsyncElasticsearch:
    global _client
    if _client is None:
        _client = AsyncElasticsearch(
            hosts=[{"host": ES_HOST, "port": ES_PORT, "scheme": ES_SCHEME}],
            basic_auth=(ES_USERNAME, ES_PASSWORD) if ES_PASSWORD else None,
            max_retries=3,
            retry_on_timeout=True
        )
        logger.info(f"Elasticsearch client created: {ES_HOST}:{ES_PORT}")
    return _client


async def close_client():
    global _client
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("Elasticsearch client closed")


def get_index_mapping(index_name: str) -> Dict[str, Any]:
    if index_name in INDEX_MAPPINGS:
        return INDEX_MAPPINGS[index_name]
    if index_name in INDEXES:
        return INDEX_MAPPINGS[INDEXES[index_name]]
    raise ValueError(f"Unknown index: {index_name}")


def get_index_name(index_key: str) -> str:
    if index_key in INDEXES:
        return INDEXES[index_key]
    raise ValueError(f"Unknown index key: {index_key}")
