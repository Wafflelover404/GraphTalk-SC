#!/usr/bin/env python3
"""
Standalone Elasticsearch Indexing Script

This script indexes documents to Elasticsearch without the chroma_utils dependency.
Usage:
    cd /Users/wafflelover404/Documents/wikiai/graphtalk
    PYTHONPATH=. python3 rag_api/tests/standalone_index.py --status
    PYTHONPATH=. python3 rag_api/tests/standalone_index.py --index-all
    PYTHONPATH=. python3 rag_api/tests/standalone_index.py --index-file "filename"
    PYTHONPATH=. python3 rag_api/tests/standalone_index.py --delete-file "filename"
    PYTHONPATH=. python3 rag_api/tests/standalone_index.py --search "query"
"""

import asyncio
import sys
import os
import json
import tempfile
import hashlib

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

from rag_api.elastic_config import INDEXES, get_client, get_index_mapping

CHUNK_SIZE = 512
CHUNK_OVERLAP = 128


def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect("rag_app.db")
    conn.row_factory = sqlite3.Row
    return conn


def get_all_documents() -> List[Dict]:
    """Get all documents from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, content FROM document_store ORDER BY id")
    docs = []
    for row in cursor.fetchall():
        docs.append({
            "id": row["id"],
            "filename": row["filename"],
            "content": row["content"] if row["content"] else ""
        })
    conn.close()
    return docs


def get_document_by_filename(filename: str) -> Optional[Dict]:
    """Get document by filename"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, content FROM document_store WHERE filename = ?", (filename,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row["id"],
            "filename": row["filename"],
            "content": row["content"] if row["content"] else ""
        }
    return None


def simple_chunk_text(text, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Simple text chunking without external dependencies"""
    if not text:
        return []
    
    # Handle bytes
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except:
            text = text.decode('latin-1')
    
    text = text.strip()
    if not text:
        return []
    
    sentences = text.replace('!', '.').replace('?', '.').split('.')
    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        words = sentence.split()
        sentence_length = len(words)
        
        if current_length + sentence_length > chunk_size and current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(chunk_text)
            current_chunk = [sentence]
            current_length = sentence_length
        else:
            current_chunk.append(sentence)
            current_length += sentence_length
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


async def index_document(doc_id: int, filename: str, content: str) -> Dict[str, Any]:
    """Index a document to Elasticsearch"""
    es = await get_client()
    index_name = INDEXES["documents"]
    
    chunks = simple_chunk_text(content)
    file_type = os.path.splitext(filename)[1].lower() if filename else ""
    
    documents = []
    for i, chunk in enumerate(chunks):
        doc = {
            "doc_id": doc_id,
            "filename": filename,
            "content": chunk,
            "content_normalized": chunk.lower().strip(),
            "file_type": file_type,
            "chunk_index": i,
            "token_count": len(chunk.split()),
            "upload_timestamp": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "modified_at": datetime.now().isoformat(),
            "embedding": [],
            "relevance_score": 0.0
        }
        doc_id_str = f"{doc_id}_{i}"
        documents.append({"_id": doc_id_str, **doc})
    
    success = 0
    failed = 0
    
    for i in range(0, len(documents), 100):
        batch = documents[i:i + 100]
        actions = []
        for doc in batch:
            action = {"index": {"_index": index_name, "_id": doc["_id"]}}
            doc_source = {k: v for k, v in doc.items() if k != "_id"}
            actions.append(action)
            actions.append(doc_source)
        
        try:
            result = await es.bulk(operations=actions, refresh=True)
            if not result.get("errors"):
                success += len(batch)
            else:
                failed += len(batch)
        except Exception as e:
            print(f"Error: {e}")
            failed += len(batch)
    
    await es.close()
    
    return {
        "doc_id": doc_id,
        "filename": filename,
        "chunks_indexed": success,
        "failed": failed
    }


async def delete_document(doc_id: int) -> Dict[str, Any]:
    """Delete a document from Elasticsearch"""
    es = await get_client()
    index_name = INDEXES["documents"]
    
    try:
        result = await es.delete_by_query(
            index=index_name,
            query={"term": {"doc_id": doc_id}},
            refresh=True
        )
        deleted = result.get("deleted", 0)
    except Exception as e:
        print(f"Delete error: {e}")
        deleted = 0
    
    await es.close()
    
    return {"deleted": deleted}


async def index_all_documents() -> Dict[str, Any]:
    """Index all documents from database to Elasticsearch"""
    print("=" * 60)
    print("INDEXING ALL DOCUMENTS")
    print("=" * 60)
    
    docs = get_all_documents()
    print(f"Found {len(docs)} documents in database\n")
    
    total_indexed = 0
    total_failed = 0
    
    for i, doc in enumerate(docs, 1):
        doc_id = doc["id"]
        filename = doc["filename"]
        content = doc["content"]
        
        print(f"[{i}/{len(docs)}] Indexing: {filename}")
        
        result = await index_document(doc_id, filename, content)
        total_indexed += result.get("chunks_indexed", 0)
        total_failed += result.get("failed", 0)
        print(f"  -> Indexed {result.get('chunks_indexed', 0)} chunks")
    
    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total_indexed} chunks indexed, {total_failed} failed")
    print(f"{'=' * 60}")
    
    return {"indexed": total_indexed, "failed": total_failed}


async def index_single_file(filename: str) -> Dict[str, Any]:
    """Index a single file by filename"""
    print("=" * 60)
    print(f"INDEXING FILE: {filename}")
    print("=" * 60)
    
    doc = get_document_by_filename(filename)
    
    if not doc:
        print(f"ERROR: File not found: {filename}")
        return {"error": "File not found"}
    
    result = await index_document(doc["id"], doc["filename"], doc["content"])
    
    print(f"\nResult: {result}")
    return result


async def delete_single_file(filename: str) -> Dict[str, Any]:
    """Delete a file from Elasticsearch by filename"""
    print("=" * 60)
    print(f"DELETING FILE: {filename}")
    print("=" * 60)
    
    doc = get_document_by_filename(filename)
    
    if not doc:
        print(f"ERROR: File not found: {filename}")
        return {"error": "File not found"}
    
    result = await delete_document(doc["id"])
    
    print(f"\nDeleted {result.get('deleted', 0)} chunks")
    return result


async def show_index_status():
    """Show current index status"""
    print("=" * 60)
    print("ELASTICSEARCH INDEX STATUS")
    print("=" * 60)
    
    es = await get_client()
    
    # ES info
    info = await es.info()
    print(f"Cluster: {info['cluster_name']}")
    print(f"Version: {info['version']['number']}")
    
    # Index stats
    index_name = INDEXES["documents"]
    try:
        count = await es.count(index=index_name)
        print(f"\nDocuments Index: {index_name}")
        print(f"  Total chunks: {count['count']}")
        
        # Get unique files
        result = await es.search(
            index=index_name,
            body={
                "size": 0,
                "aggs": {
                    "files": {
                        "terms": {"field": "filename", "size": 100}
                    }
                }
            }
        )
        
        buckets = result.get("aggregations", {}).get("files", {}).get("buckets", [])
        print(f"\nIndexed Files ({len(buckets)}):")
        for bucket in buckets:
            print(f"  - {bucket['key']}: {bucket['doc_count']} chunks")
    
    except Exception as e:
        print(f"Error: {e}")
    
    await es.close()


async def reindex_file(filename: str) -> Dict[str, Any]:
    """Delete and reindex a file"""
    print("=" * 60)
    print(f"REINDEXING FILE: {filename}")
    print("=" * 60)
    
    doc = get_document_by_filename(filename)
    
    if not doc:
        print(f"ERROR: File not found: {filename}")
        return {"error": "File not found"}
    
    # Delete first
    print("Deleting existing chunks...")
    delete_result = await delete_document(doc["id"])
    print(f"  Deleted: {delete_result.get('deleted', 0)}")
    
    # Reindex
    print("Reindexing...")
    index_result = await index_document(doc["id"], doc["filename"], doc["content"])
    print(f"  Indexed: {index_result.get('chunks_indexed', 0)}")
    
    return {"deleted": delete_result.get("deleted", 0), "indexed": index_result.get("chunks_indexed", 0)}


async def test_search(query: str, lang: str = "en"):
    """Test search functionality"""
    print("=" * 60)
    print(f"SEARCH TEST: '{query}' ({lang})")
    print("=" * 60)
    
    es = await get_client()
    
    result = await es.search(
        index=INDEXES["documents"],
        body={
            "query": {
                "match": {"content": query}
            },
            "size": 10
        }
    )
    
    await es.close()
    
    hits = result["hits"]["hits"]
    total = result["hits"]["total"]["value"]
    
    print(f"\nFound: {total} results\n")
    
    for hit in hits[:5]:
        src = hit["_source"]
        print(f"- {src.get('filename', '?')}")
        print(f"  Score: {hit['_score']:.3f}")
        print(f"  Chunk: {src.get('content', '')[:80]}...")
        print()


async def main():
    """Main CLI interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Elasticsearch Indexing CLI")
    parser.add_argument("--index-all", action="store_true", help="Index all documents from database")
    parser.add_argument("--index-file", type=str, metavar="FILENAME", help="Index a single file by filename")
    parser.add_argument("--delete-file", type=str, metavar="FILENAME", help="Delete a file from ES by filename")
    parser.add_argument("--reindex-file", type=str, metavar="FILENAME", help="Delete and reindex a file")
    parser.add_argument("--status", action="store_true", help="Show index status")
    parser.add_argument("--search", type=str, metavar="QUERY", help="Test search")
    parser.add_argument("--search-ru", type=str, metavar="QUERY", help="Test Russian search")
    
    args = parser.parse_args()
    
    if not any([args.index_all, args.index_file, args.delete_file, 
                 args.reindex_file, args.status, args.search, args.search_ru]):
        parser.print_help()
        return
    
    if args.status:
        await show_index_status()
    
    elif args.index_all:
        await index_all_documents()
    
    elif args.index_file:
        await index_single_file(args.index_file)
    
    elif args.delete_file:
        await delete_single_file(args.delete_file)
    
    elif args.reindex_file:
        await reindex_file(args.reindex_file)
    
    elif args.search:
        await test_search(args.search, "en")
    
    elif args.search_ru:
        await test_search(args.search_ru, "ru")


if __name__ == "__main__":
    asyncio.run(main())
