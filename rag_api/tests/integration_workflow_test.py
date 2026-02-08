#!/usr/bin/env python3
"""
Integration Test for Elasticsearch API

Tests:
1. Upload document (auto-index to ES)
2. Search across documents
3. Get file list from ES
4. Reindex edited document
5. Delete document (auto-delete from ES)

Usage:
    python rag_api/tests/integration_workflow_test.py
"""

import asyncio
import sys
import os
import json
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_api.elastic_config import INDEXES, get_client
from rag_api.elastic_indexer import index_rag_document, delete_rag_document
from rag_api.elastic_search import search_documents, get_facets


def create_test_file(filename: str, content: str) -> str:
    """Create a temporary test file"""
    temp_dir = tempfile.gettempdir()
    filepath = os.path.join(temp_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath


def cleanup_test_file(filepath: str):
    """Remove test file"""
    if os.path.exists(filepath):
        os.remove(filepath)


async def test_upload_and_index():
    """Test 1: Upload document and verify ES indexing"""
    print("\n" + "="*60)
    print("TEST 1: Upload Document & Index to Elasticsearch")
    print("="*60)
    
    test_content = """
    Machine Learning Fundamentals
    
    Machine learning is a subset of artificial intelligence that focuses
    on building systems that learn from data. The main types include:
    
    1. Supervised Learning - Uses labeled training data
    2. Unsupervised Learning - Finds patterns in unlabeled data
    3. Reinforcement Learning - Learns through trial and error
    
    Deep learning uses neural networks with multiple layers to achieve
    state-of-the-art results in image recognition, natural language
    processing, and other domains.
    
    Russian: Машинное обучение - это подраздел искусственного интеллекта.
    """
    
    test_file = "test_ml_fundamentals.txt"
    filepath = create_test_file(test_file, test_content)
    
    try:
        with open(filepath, 'rb') as f:
            content_bytes = f.read()
        
        doc_id = int(time.time())
        
        print(f"  Created test file: {test_file}")
        print(f"  Content size: {len(content_bytes)} bytes")
        
        result = await index_rag_document(
            doc_id=doc_id,
            filename=test_file,
            content=content_bytes.decode('utf-8'),
            metadata={"uploaded_from": "integration_test"}
        )
        
        print(f"  Indexing result: {result}")
        
        if result.get("chunks_indexed", 0) > 0:
            print("  ✓ Document indexed successfully!")
            return True, doc_id, test_file
        else:
            print("  ✗ Failed to index document")
            return False, None, None
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False, None, None
    finally:
        cleanup_test_file(filepath)


async def test_search():
    """Test 2: Search across indexed documents"""
    print("\n" + "="*60)
    print("TEST 2: Search Across Documents")
    print("="*60)
    
    test_queries = [
        ("machine learning", "English query"),
        ("нейронных сетей", "Russian query"),
        ("supervised learning", "Specific term"),
    ]
    
    all_passed = True
    
    for query, description in test_queries:
        print(f"\n  Query: '{query}' ({description})")
        
        try:
            result = await search_documents(
                query=query,
                size=5,
                search_type="hybrid"
            )
            
            status = result.get("status", "error")
            total = result.get("total", 0)
            took = result.get("took_ms", 0)
            
            print(f"    Status: {status}")
            print(f"    Found: {total} results")
            print(f"    Time: {took}ms")
            
            if result.get("results"):
                for i, res in enumerate(result["results"][:3], 1):
                    filename = res.get("filename", "unknown")
                    score = res.get("score", 0)
                    print(f"      {i}. {filename} (score: {score:.3f})")
                    
            if total > 0:
                print(f"    ✓ Search successful")
            else:
                print(f"    ⚠ No results found")
                
        except Exception as e:
            print(f"    ✗ Error: {e}")
            all_passed = False
    
    return all_passed


async def test_get_file_list():
    """Test 3: Get file list from ES"""
    print("\n" + "="*60)
    print("TEST 3: Get File List from Elasticsearch")
    print("="*60)
    
    try:
        from rag_api.elastic_client import get_client
        
        es = await get_client()
        
        result = await es.search(
            index=INDEXES["documents"],
            body={
                "size": 0,
                "aggs": {
                    "files": {
                        "terms": {
                            "field": "filename",
                            "size": 100
                        }
                    }
                }
            }
        )
        await es.close()
        
        buckets = result.get("aggregations", {}).get("files", {}).get("buckets", [])
        
        print(f"  Found {len(buckets)} unique files in ES:")
        
        for bucket in buckets[:10]:
            print(f"    - {bucket['key']}: {bucket['doc_count']} chunks")
        
        if len(buckets) > 10:
            print(f"    ... and {len(buckets) - 10} more")
        
        print("  ✓ File list retrieved")
        return True, len(buckets)
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False, 0


async def test_reindex():
    """Test 4: Reindex edited document"""
    print("\n" + "="*60)
    print("TEST 4: Reindex Edited Document")
    print("="*60)
    
    test_content_v2 = """
    Machine Learning Fundamentals v2.0
    
    UPDATED: This is version 2.0 of our ML fundamentals document.
    
    Key concepts:
    - Neural Networks
    - Deep Learning  
    - Natural Language Processing
    - Computer Vision
    
    The field has evolved significantly with transformer models,
    BERT, GPT, and other architectures revolutionizing NLP.
    """
    
    try:
        from rag_api.db_utils import get_all_documents, get_file_content_by_filename
        
        docs = get_all_documents()
        
        if docs:
            first_doc = docs[0]
            filename = first_doc.get("filename", "unknown")
            doc_id = first_doc.get("id")
            
            print(f"  Reindexing: {filename} (ID: {doc_id})")
            
            result = await index_rag_document(
                doc_id=doc_id,
                filename=filename,
                content=test_content_v2
            )
            
            print(f"  Reindexing result: {result}")
            
            if result.get("chunks_indexed", 0) > 0:
                print("  ✓ Document reindexed successfully!")
                return True
            else:
                print("  ✗ Failed to reindex")
                return False
        else:
            print("  ⚠ No documents found in database to reindex")
            return True
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


async def test_delete_document():
    """Test 5: Delete document and auto-remove from ES"""
    print("\n" + "="*60)
    print("TEST 5: Delete Document & Remove from Elasticsearch")
    print("="*60)
    
    try:
        from rag_api.db_utils import get_all_documents, delete_document_record
        from rag_api.chroma_utils import delete_doc_from_chroma
        
        docs = get_all_documents()
        
        if docs:
            first_doc = docs[0]
            filename = first_doc.get("filename", "unknown")
            doc_id = first_doc.get("id")
            
            print(f"  Deleting: {filename} (ID: {doc_id})")
            
            print(f"    - Deleting from database...")
            delete_document_record(doc_id)
            
            print(f"    - Deleting from ChromaDB...")
            chroma_result = delete_doc_from_chroma(doc_id)
            print(f"      ChromaDB: {chroma_result}")
            
            print(f"    - Deleting from Elasticsearch...")
            es_result = await delete_rag_document(doc_id)
            print(f"      Elasticsearch: {es_result}")
            
            print("  ✓ Document deleted from all sources")
            return True
        else:
            print("  ⚠ No documents found to delete")
            return True
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


async def test_facets():
    """Test 6: Get facets/aggregations"""
    print("\n" + "="*60)
    print("TEST 6: Get Faceted Search Aggregations")
    print("="*60)
    
    try:
        result = await get_facets(
            facet_fields=["filename", "file_type"],
            size=10
        )
        
        if result.get("status") == "success":
            facets = result.get("facets", {})
            print(f"  Facets retrieved:")
            
            for field, values in facets.items():
                print(f"    {field}:")
                for v in values[:5]:
                    print(f"      - {v['value']}: {v['count']}")
            
            print("  ✓ Facets retrieved")
            return True
        else:
            print(f"  ✗ Error: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


async def test_semantic_search():
    """Test 7: Pure semantic search"""
    print("\n" + "="*60)
    print("TEST 7: Semantic Search (k-NN Vector Search)")
    print("="*60)
    
    try:
        result = await search_documents(
            query="neural networks deep learning AI",
            search_type="semantic",
            size=5
        )
        
        status = result.get("status", "error")
        total = result.get("total", 0)
        search_type = result.get("type", "unknown")
        
        print(f"  Search type: {search_type}")
        print(f"  Status: {status}")
        print(f"  Found: {total} results")
        
        if result.get("results"):
            for i, res in enumerate(result["results"][:3], 1):
                filename = res.get("filename", "unknown")
                score = res.get("score", 0)
                print(f"    {i}. {filename} (score: {score:.3f})")
        
        print("  ✓ Semantic search completed")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


async def run_all_tests():
    """Run all integration tests"""
    print("\n" + "#"*60)
    print("# Elasticsearch Integration Tests")
    print("#"*60)
    
    results = {}
    
    results["upload_and_index"] = await test_upload_and_index()
    results["search"] = await test_search()
    results["file_list"] = await test_get_file_list()
    results["facets"] = await test_facets()
    results["semantic_search"] = await test_semantic_search()
    results["reindex"] = await test_reindex()
    results["delete"] = await test_delete_document()
    
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        if isinstance(result, tuple):
            status = "PASS" if result[0] else "FAIL"
        else:
            status = "PASS" if result else "FAIL"
        
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\n  Total: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\n  🎉 All tests passed!")
        return 0
    else:
        print(f"\n  ⚠️ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
