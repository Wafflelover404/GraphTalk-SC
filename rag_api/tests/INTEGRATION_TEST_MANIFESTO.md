# Elasticsearch Integration Test Manifesto

## Test Overview

This document describes the complete integration test workflow for Elasticsearch with GraphTalk.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      GraphTalk API                               │
│  (api.py - /upload, /delete, /query endpoints)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Elastic Indexer                              │
│  (elastic_indexer.py - auto-index on upload)                    │
│  - index_rag_document()                                          │
│  - delete_rag_document()                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Elasticsearch Cluster                            │
│  - graphtalk_documents (main search index)                      │
│  - graphtalk_logs (application logs)                            │
│  - graphtalk_queries (query analytics)                          │
│  - graphtalk_products (OpenCart products)                       │
└─────────────────────────────────────────────────────────────────┘
```

## Test Scenarios

### TEST 1: Upload & Auto-Index

**Objective**: Verify documents are automatically indexed to ES when uploaded

**Flow**:
```
POST /upload (admin only)
    ↓
    Insert to rag_app.db (document_store)
    ↓
    Index to ChromaDB
    ↓
    Index to Elasticsearch (NEW)
    ↓
    Return success response
```

**Verification**:
- Document appears in `graphtalk_documents` index
- Document chunks are indexed with proper metadata
- Embeddings are stored for semantic search

**CURL Test**:
```bash
# Upload a test file
curl -X POST "http://localhost:9001/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.txt"

# Verify indexing
curl "http://localhost:9200/graphtalk_documents/_search?size=1"
```

---

### TEST 2: Search Across Documents

**Objective**: Verify full-text and semantic search works

**Flow**:
```
POST /es/search (or /query)
    ↓
    Build ES query (fulltext + filters)
    ↓
    Execute search
    ↓
    Return results with highlights
```

**Search Types**:
| Type | Endpoint | Description |
|------|----------|-------------|
| Fulltext | `POST /es/search/fulltext` | Keyword matching |
| Semantic | `POST /es/search/semantic` | Vector similarity (k-NN) |
| Hybrid | `POST /es/search/hybrid` | Combined (RRF fusion) |

**CURL Tests**:
```bash
# Fulltext search
curl -X POST "http://localhost:9001/es/search/fulltext" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "size": 10}'

# Semantic search  
curl -X POST "http://localhost:9001/es/search/semantic" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "нейронные сети", "size": 10}'

# Hybrid search
curl -X POST "http://localhost:9001/es/search/hybrid" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/jsond '{"query":" \
  - "deep learning AI", "fusion_method": "rrf"}'
```

---

### TEST 3: Get File List

**Objective**: Retrieve indexed files from ES

**Flow**:
```
GET /es/index/documents/stats
    ↓
    Query aggregations
    ↓
    Return file list
```

**CURL Test**:
```bash
# Get file list with counts
curl "http://localhost:9200/graphtalk_documents/_search" \
  -H "Content-Type: application/json" \
  -d '{"size": 0, "aggs": {"files": {"terms": {"field": "filename", "size": 100}}}}'
```

---

### TEST 4: Reindex Edited Document

**Objective**: Re-index a document after it was edited

**Flow**:
```
POST /es/reindex/file/{filename}
    ↓
    Fetch from database
    ↓
    Re-index to Elasticsearch
    ↓
    Update embeddings
```

**CURL Test**:
```bash
# Reindex a specific file
curl -X POST "http://localhost:9001/es/reindex/file/test.txt" \
  -H "Authorization: Bearer $TOKEN"
```

---

### TEST 5: Delete Document (Auto-remove from ES)

**Objective**: Verify document deletion cascades to ES

**Flow**:
```
DELETE /delete/{file_id}
    ↓
    Delete from rag_app.db
    ↓
    Delete from ChromaDB
    ↓
    Delete from Elasticsearch (NEW)
```

**CURL Test**:
```bash
# Delete file
curl -X DELETE "http://localhost:9001/delete/123" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Verify removal from ES
curl "http://localhost:9200/graphtalk_documents/_search?q=filename:test.txt"
```

---

## Test Data

### Sample Test Files

| File | Content | Language | Purpose |
|------|---------|----------|---------|
| `ml_basics.txt` | Machine learning fundamentals | English | Fulltext search |
| `neural_networks.txt` | Deep learning concepts | English | Semantic search |
| `ml_fundamentals_ru.txt` | Основы машинного обучения | Russian | Multilingual search |
| `hybrid_test.txt` | Mix of EN/RU text | Both | Cross-language |

### Sample Queries

| Query | Language | Expected Results |
|--------|----------|-----------------|
| "machine learning" | English | ml_basics.txt |
| "нейронные сети" | Russian | neural_networks.txt (if contains) |
| "deep learning" | English | neural_networks.txt |
| "обучение" | Russian | ml_fundamentals_ru.txt |

---

## Expected Results

### Test 1: Upload & Index
- ✅ Document indexed within 2 seconds
- ✅ Chunks created based on content length
- ✅ Embeddings generated (384-dim)
- ✅ Metadata preserved (filename, file_type, etc.)

### Test 2: Search
- ✅ Fulltext: Results within 100ms
- ✅ Semantic: Results within 200ms
- ✅ Hybrid: Results within 300ms
- ✅ Highlighting works
- ✅ Multilingual (EN/RU) supported

### Test 3: File List
- ✅ Aggregations return correct counts
- ✅ Faceted search works

### Test 4: Reindex
- ✅ Document updated in < 5 seconds
- ✅ Old chunks removed
- ✅ New embeddings generated

### Test 5: Delete
- ✅ Document removed from all sources
- ✅ Cleanup within 1 second

---

## Running the Tests

### Prerequisites
```bash
# Start Elasticsearch
docker run -d --name elastic-wikiai \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  docker.elastic.co/elasticsearch/elasticsearch:9.3.0-arm64

# Run integration tests
cd /Users/wafflelover404/Documents/wikiai/graphtalk
PYTHONPATH=. python3 rag_api/tests/integration_workflow_test.py
```

### Manual CURL Tests
```bash
# 1. Health check
curl http://localhost:9001/es/health

# 2. Upload file (get token first)
TOKEN=$(curl -s -X POST "http://localhost:9001/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 3. Search
curl -X POST "http://localhost:9001/es/search/hybrid" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning"}'

# 4. Reindex
curl -X POST "http://localhost:9001/es/reindex/file/test.txt" \
  -H "Authorization: Bearer $TOKEN"

# 5. Delete
curl -X DELETE "http://localhost:9001/delete/1" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Test Results Format

### Success Output
```
============================================================
TEST 1: Upload Document & Index to Elasticsearch
============================================================
  Created test file: test_ml_fundamentals.txt
  Content size: 685 bytes
  Indexing result: {'doc_id': 123, 'chunks_indexed': 3, 'success': 3}
  ✓ Document indexed successfully!
```

### Failure Output
```
============================================================
TEST 2: Search Across Documents
============================================================
  Query: 'machine learning'
    Status: success
    Found: 0 results
  ✗ Expected results not found
  Error: Query returned empty
```

---

## Troubleshooting

### ES Connection Issues
```bash
# Check ES status
curl http://localhost:9200

# Restart ES container
docker restart elastic-wikiai

# Check ES logs
docker logs elastic-wikiai --tail 50
```

### Index Not Created
```bash
# Recreate indexes
cd /Users/wafflelover404/Documents/wikiai/graphtalk
PYTHONPATH=. python3 -c "
import asyncio
from rag_api.elastic_config import get_client, INDEXES, get_index_mapping

async def create():
    es = await get_client()
    for key, name in INDEXES.items():
        await es.indices.delete(index=name, ignore_unavailable=True)
        await es.indices.create(index=name, body=get_index_mapping(key))
        print(f'Created: {name}')
    await es.close()

asyncio.run(create())
"
```

### Search Returns No Results
```bash
# Check indexed documents
curl "http://localhost:9200/graphtalk_documents/_count"

# Refresh index
curl -X POST "http://localhost:9200/graphtalk_documents/_refresh"

# Test basic search
curl "http://localhost:9200/graphtalk_documents/_search?q=*"
```

---

## Performance Benchmarks

| Operation | Target | Maximum |
|-----------|--------|---------|
| Index single doc | < 500ms | 2s |
| Bulk index (100 docs) | < 5s | 10s |
| Fulltext search | < 100ms | 500ms |
| Semantic search | < 200ms | 1s |
| Hybrid search | < 300ms | 1.5s |
| Delete document | < 500ms | 2s |

---

## Security Tests

### Multi-tenancy
```bash
# User from org_1 searches
TOKEN_USER1=$(...)
curl -X POST "http://localhost:9001/es/search" \
  -H "Authorization: Bearer $TOKEN_USER1" \
  -d '{"query": "test"}'

# Should only return files org_1 has access to
```

### Admin-only Operations
```bash
# Regular user tries reindex
curl -X POST "http://localhost:9001/es/reindex/full" \
  -H "Authorization: Bearer $USER_TOKEN"
# Expected: 403 Forbidden
```
