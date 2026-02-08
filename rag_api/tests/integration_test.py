#!/usr/bin/env python3
"""
Integration test script for Elasticsearch API
Run this script after starting Elasticsearch to test the integration.

Usage:
    python rag_api/tests/integration_test.py
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_api.elastic_config import INDEXES, get_es_config
from rag_api.elastic_client import health_check, create_index, index_document, search


async def test_connection():
    """Test Elasticsearch connection"""
    print("=" * 60)
    print("1. Testing Elasticsearch Connection")
    print("=" * 60)
    
    result = await health_check()
    print(f"Health check result: {json.dumps(result, indent=2)}")
    
    if result.get("status") == "connected":
        print("✓ Elasticsearch is connected!")
        return True
    else:
        print("✗ Cannot connect to Elasticsearch")
        print(f"  Error: {result.get('error', 'Unknown error')}")
        return False


async def test_indexes():
    """Test index creation"""
    print("\n" + "=" * 60)
    print("2. Testing Index Creation")
    print("=" * 60)
    
    from rag_api.elastic_client import create_index, index_exists, get_index_mapping
    
    for index_key, index_name in INDEXES.items():
        exists = await index_exists(index_name)
        print(f"Index {index_key}: {'exists' if exists else 'not found'}")
        
        if not exists:
            mapping = get_index_mapping(index_name)
            success = await create_index(
                index_name,
                settings=mapping.get("settings", {}),
                mappings=mapping.get("mappings", {})
            )
            print(f"  Created: {success}")


async def test_documents():
    """Test document indexing and search"""
    print("\n" + "=" * 60)
    print("3. Testing Document Operations")
    print("=" * 60)
    
    index_name = INDEXES["documents"]
    
    test_docs = [
        {
            "doc_id": 1,
            "filename": "test1.txt",
            "content": "This is a test document about machine learning and AI",
            "content_normalized": "test document machine learning ai",
            "file_type": ".txt",
            "chunk_index": 0,
            "token_count": 10,
            "relevance_score": 0.0,
            "embedding": [0.1] * 384
        },
        {
            "doc_id": 2,
            "filename": "test2.txt", 
            "content": "Another document about deep learning neural networks",
            "content_normalized": "document deep learning neural networks",
            "file_type": ".txt",
            "chunk_index": 0,
            "token_count": 8,
            "relevance_score": 0.0,
            "embedding": [0.2] * 384
        },
        {
            "doc_id": 3,
            "filename": "test3.txt",
            "content": "Natural language processing is a subfield of AI",
            "content_normalized": "natural language processing subfield ai",
            "file_type": ".txt", 
            "chunk_index": 0,
            "token_count": 9,
            "relevance_score": 0.0,
            "embedding": [0.3] * 384
        }
    ]
    
    print(f"Indexing {len(test_docs)} test documents...")
    for doc in test_docs:
        success = await index_document(index_name, str(doc["doc_id"]), doc)
        print(f"  Indexed {doc['filename']}: {success}")
    
    print("\nTesting search...")
    queries = [
        "machine learning",
        "neural networks",
        "artificial intelligence"
    ]
    
    for query in queries:
        result = await search(index_name, {
            "multi_match": {
                "query": query,
                "fields": ["content", "content_normalized"]
            }
        }, size=5)
        
        print(f"\nQuery: '{query}'")
        print(f"  Found: {result.get('total', 0)} results")
        for hit in result.get("hits", [])[:3]:
            print(f"    - {hit.get('filename', 'unknown')}: score={hit.get('_score', 0):.3f}")


async def test_filtering():
    """Test filtering by filename"""
    print("\n" + "=" * 60)
    print("4. Testing Security Filtering")
    print("=" * 60)
    
    index_name = INDEXES["documents"]
    
    result = await search(index_name, {
        "bool": {
            "must": [{"match": {"content": "document"}}],
            "filter": [{"term": {"filename": "test1.txt"}}]
        }
    }, size=10)
    
    print(f"Filter by filename='test1.txt'")
    print(f"  Found: {result.get('total', 0)} results")
    for hit in result.get("hits", []):
        print(f"    - {hit.get('filename')}")


async def test_aggregations():
    """Test aggregations/facets"""
    print("\n" + "=" * 60)
    print("5. Testing Aggregations")
    print("=" * 60)
    
    from rag_api.elastic_client import get_client
    
    index_name = INDEXES["documents"]
    es = await get_client()
    
    result = await es.search(index=index_name, body={
        "size": 0,
        "aggs": {
            "files": {
                "terms": {"field": "filename", "size": 10}
            }
        }
    })
    await es.close()
    
    buckets = result.get("aggregations", {}).get("files", {}).get("buckets", [])
    print("File distribution:")
    for bucket in buckets:
        print(f"  - {bucket['key']}: {bucket['doc_count']} documents")


async def run_all_tests():
    """Run all integration tests"""
    print("\n" + "#" * 60)
    print("# Elasticsearch Integration Tests")
    print("#" * 60)
    
    connected = await test_connection()
    
    if not connected:
        print("\n⚠️  Elasticsearch is not running. Please start Elasticsearch first:")
        print("   docker run -d --name elasticsearch -p 9200:9200 -e 'discovery.type=single-node' elasticsearch:8.10.0")
        return False
    
    await test_indexes()
    await test_documents()
    await test_filtering()
    await test_aggregations()
    
    print("\n" + "#" * 60)
    print("# All tests completed!")
    print("#" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
