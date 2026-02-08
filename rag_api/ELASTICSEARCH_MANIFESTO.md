# Elasticsearch Implementation Manifesto

## Overview
This document outlines the Elasticsearch integration for GraphTalk, providing full-text search with semantic capabilities, aggregations, and hybrid search functionality.

## Project Status: IN PROGRESS

---

## Database Schemas Analyzed

### rag_app.db
| Table | Columns | Purpose |
|-------|---------|---------|
| document_store | id, filename, content, upload_timestamp | Document storage |
| application_logs | id, session_id, user_query, gpt_response, model, created_at | Query logs |

### metrics.db
| Table | Columns | Purpose |
|-------|---------|---------|
| queries | id, session_id, user_id, role, question, answer, model_type, source_document_count, response_time_ms, timestamp | Query analytics |
| user_events | id, session_id, user_id, role, event_type, timestamp, ip_address, details, success | User activity |
| file_access_logs | id, user_id, role, filename, file_id, access_type, timestamp, session_id, ip_address | File access tracking |
| security_events | id, event_type, user_id, ip_address, timestamp, details, severity | Security monitoring |

### users.db
| Table | Columns | Purpose |
|-------|---------|---------|
| users | id, username, password_hash, role, access_token, allowed_files, last_login | User accounts |
| user_sessions | session_id, username, created_at, last_activity, expires_at, is_active | Session management |

---

## Elasticsearch Index Mappings

### graphtalk_documents
```json
{
  "mappings": {
    "properties": {
      "doc_id": {"type": "integer"},
      "filename": {"type": "keyword"},
      "content": {"type": "text", "analyzer": "standard"},
      "content_normalized": {"type": "text", "analyzer": "standard"},
      "file_type": {"type": "keyword"},
      "chunk_index": {"type": "integer"},
      "token_count": {"type": "integer"},
      "upload_timestamp": {"type": "date"},
      "created_at": {"type": "date"},
      "modified_at": {"type": "date"},
      "embedding": {"type": "dense_vector", "dims": 384},
      "relevance_score": {"type": "float"}
    }
  }
}
```

### graphtalk_logs
```json
{
  "mappings": {
    "properties": {
      "session_id": {"type": "keyword"},
      "user_id": {"type": "keyword"},
      "user_query": {"type": "text"},
      "gpt_response": {"type": "text"},
      "model": {"type": "keyword"},
      "created_at": {"type": "date"}
    }
  }
}
```

### graphtalk_queries
```json
{
  "mappings": {
    "properties": {
      "session_id": {"type": "keyword"},
      "user_id": {"type": "keyword"},
      "role": {"type": "keyword"},
      "question": {"type": "text"},
      "answer": {"type": "text"},
      "model_type": {"type": "keyword"},
      "source_document_count": {"type": "integer"},
      "response_time_ms": {"type": "integer"},
      "timestamp": {"type": "date"}
    }
  }
}
```

---

## Modules to Create

### 1. elastic_config.py
**Purpose**: Centralized configuration for Elasticsearch connection
**Dependencies**: elasticsearch, python-dotenv
**Key Functions**:
- `get_es_config()` - Load settings from environment
- `get_async_client()` - Create async ES client
- `get_index_mapping(index_name)` - Return mapping for index
- `INDEXES` - Index names dictionary

### 2. elastic_client.py
**Purpose**: Low-level ES operations with connection pooling
**Key Functions**:
- `get_client()` - Get async ES client
- `create_index()` - Create index with mapping
- `delete_index()` - Delete index
- `index_exists()` - Check if index exists
- `get_index_stats()` - Get index statistics
- `bulk_index()` - Bulk document indexing
- `health_check()` - Verify ES connectivity

### 3. elastic_indexer.py
**Purpose**: Transform and index documents from various sources
**Key Functions**:
- `index_document()` - Index single document
- `index_rag_chunk()` - Index RAG document chunk
- `index_from_chroma()` - Sync from ChromaDB to ES
- `index_file_upload()` - Index uploaded file
- `delete_document()` - Delete from ES
- `reindex_all()` - Full reindex

### 4. elastic_search.py
**Purpose**: Advanced search with highlighting, faceting, and aggregations
**Key Functions**:
- `search_documents()` - Full-text search
- `hybrid_search()` - Semantic + keyword search
- `search_with_highlighting()` - Search with highlighting
- `get_suggestions()` - Autocomplete
- `get_facets()` - Faceted search
- `search_logs()` - Search logs

### 5. elastic_api.py
**Purpose**: FastAPI router with endpoints
**Endpoints**:
- `POST /es/search` - Search documents
- `GET /es/search/suggest` - Autocomplete
- `GET /es/search/facets` - Faceted search
- `POST /es/index/{index_name}` - Create index
- `DELETE /es/index/{index_name}` - Delete index
- `GET /es/index/{index_name}/stats` - Index stats
- `POST /es/reindex/full` - Full reindex
- `POST /es/reindex/file/{filename}` - Reindex file
- `POST /es/hybrid/search` - Hybrid search

### 6. reindex_to_es.py
**Purpose**: Standalone migration script
**Usage**:
```bash
python rag_api/reindex_to_es.py --full
python rag_api/reindex_to_es.py --documents
python rag_api/reindex_to_es.py --logs
```

---

## Feature Comparison

| Feature | Current (ChromaDB) | New (Elasticsearch) |
|---------|---------------------|----------------------|
| Full-text search | BM25 only | Advanced text analysis |
| Highlighting | No | Yes |
| Faceted search | No | Yes |
| Aggregations | No | Yes |
| Suggestions | No | Yes |
| Fuzzy matching | Basic | Advanced |
| Vector search | Yes (Chroma) | Yes (ES k-NN) |
| Hybrid search | Yes | Yes (RRF fusion) |

---

## Search Capabilities

### Full-Text Search
- Multi-language support (Russian, English)
- Stopword removal
- Stemming
- Fuzzy matching

### Semantic Search
- Dense vector embeddings
- Cosine similarity
- k-NN search

### Hybrid Search
- Reciprocal Rank Fusion (RRF)
- Weighted scoring
- Result fusion

### Security Integration
- User-based access filtering
- allowed_files integration
- Role-based search

---

## Implementation Progress

- [x] elastic_config.py
- [x] elastic_client.py
- [x] elastic_indexer.py
- [x] elastic_search.py
- [x] elastic_api.py
- [x] reindex_to_es.py
- [x] Unit tests (31 passing, 1 requires ES)
- [x] Integration tests (script created)
- [x] CURL tests (script created)
- [x] Integration with api.py

## Test Results

```bash
$ /Users/wafflelover404/Library/Python/3.9/bin/pytest rag_api/tests/test_elasticsearch.py -v
...
=============================== short test summary info ============================
31 passed, 1 failed (requires Elasticsearch)
===========================

---

## Environment Variables Required

```bash
ES_HOST=localhost
ES_PORT=9200
ES_SCHEME=http
ES_USERNAME=elastic
ES_PASSWORD=your_password
ES_INDEX_PREFIX=graphtalk
```

---

## Dependencies to Add

```txt
elasticsearch>=8.0.0
elasticsearch-dsl>=8.0.0
python-dotenv>=1.0.0
```

---

## Integration Points

| Existing Module | Integration |
|-----------------|-------------|
| rag_security.py | get_accessible_files() for filtering |
| chroma_utils.py | search_documents(), chunking |
| db_utils.py | get_file_content_by_filename() |
| api.py | New router inclusion |
| metricsdb.py | Log search events |

---

## Testing Strategy

1. **Unit Tests**: Each module independently
2. **Integration Tests**: Full search flow
3. **Performance Tests**: Compare with ChromaDB
4. **CURL Tests**: Manual endpoint verification

---

## Migration Path

1. **Phase 1**: Add ES alongside ChromaDB (`/es/search` parallel to existing)
2. **Phase 2**: Enable hybrid search with RRF fusion
3. **Phase 3**: Make ES primary, ChromaDB fallback
4. **Phase 4**: Deprecate ChromaDB search endpoints

---

## Authors
Implementation for GraphTalk project
