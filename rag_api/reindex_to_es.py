#!/usr/bin/env python3
"""
Elasticsearch Reindex Script

Usage:
    python rag_api/reindex_to_es.py --full
    python rag_api/reindex_to_es.py --documents
    python rag_api/reindex_to_es.py --logs
    python rag_api/reindex_to_es.py --queries
    python rag_api/reindex_to_es.py --sync
    python rag_api/reindex_to_es.py --batch-size 200
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rag_api.elastic_config import INDEXES, get_index_mapping
from rag_api.elastic_client import (
    create_index, delete_index, index_exists, get_index_stats,
    bulk_index, search as es_search
)
from rag_api.elastic_indexer import (
    ensure_indexes, sync_from_chroma, reindex_all, index_all_documents
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def reindex_documents(batch_size: int = 100) -> Dict[str, Any]:
    """Reindex documents from database to Elasticsearch"""
    logger.info("Starting document reindexing...")

    from rag_api.db_utils import get_all_documents, get_file_content_by_filename
    from rag_api.elastic_indexer import index_rag_document

    documents = get_all_documents()
    logger.info(f"Found {len(documents)} documents to reindex")

    indexed = 0
    failed = 0
    errors = []

    for i, doc in enumerate(documents):
        try:
            doc_id = doc.get('id')
            filename = doc.get('filename')
            content = get_file_content_by_filename(filename)

            if content:
                result = await index_rag_document(
                    doc_id=doc_id,
                    filename=filename,
                    content=content
                )
                indexed += result.get("chunks_indexed", 0)
                failed += result.get("failed", 0)
            else:
                logger.warning(f"No content found for {filename}")
                failed += 1

            if (i + 1) % 10 == 0:
                logger.info(f"Processed {i + 1}/{len(documents)} documents")

        except Exception as e:
            logger.error(f"Error reindexing {filename}: {e}")
            failed += 1
            errors.append(str(e))

    return {
        "documents_processed": len(documents),
        "chunks_indexed": indexed,
        "failed": failed,
        "errors": errors[:10]
    }


async def reindex_logs(batch_size: int = 500) -> Dict[str, Any]:
    """Reindex application logs to Elasticsearch"""
    logger.info("Starting logs reindexing...")

    import sqlite3
    from datetime import datetime, timedelta

    conn = sqlite3.connect("rag_app.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    since = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute(
        "SELECT * FROM application_logs WHERE created_at >= ? ORDER BY created_at DESC",
        (since,)
    )
    logs = cursor.fetchall()
    conn.close()

    logger.info(f"Found {len(logs)} logs to reindex")

    documents = []
    for log in logs:
        doc = {
            "session_id": log["session_id"],
            "user_id": "",
            "user_query": log["user_query"],
            "gpt_response": log["gpt_response"],
            "model": log["model"],
            "created_at": log["created_at"]
        }
        documents.append(doc)

    index_name = INDEXES["logs"]
    result = await bulk_index(index_name, documents, chunk_size=batch_size)

    return {
        "logs_processed": len(logs),
        "success": result["success"],
        "failed": result["failed"],
        "errors": result.get("errors", [])
    }


async def reindex_queries(batch_size: int = 500) -> Dict[str, Any]:
    """Reindex query analytics to Elasticsearch"""
    logger.info("Starting queries reindexing...")

    import sqlite3
    import json
    from datetime import datetime, timedelta

    conn = sqlite3.connect("metrics.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    since = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute(
        "SELECT * FROM queries WHERE timestamp >= ? ORDER BY timestamp DESC",
        (since,)
    )
    queries = cursor.fetchall()
    conn.close()

    logger.info(f"Found {len(queries)} queries to reindex")

    documents = []
    for q in queries:
        source_filenames = []
        if q["source_filenames"]:
            try:
                source_filenames = json.loads(q["source_filenames"])
            except:
                source_filenames = []

        doc = {
            "session_id": q["session_id"],
            "user_id": q["user_id"],
            "role": q["role"],
            "question": q["question"],
            "answer": q["answer"],
            "model_type": q["model_type"],
            "source_document_count": q["source_document_count"],
            "response_time_ms": q["response_time_ms"],
            "timestamp": q["timestamp"],
            "security_filtered": bool(q["security_filtered"]) if q["security_filtered"] else False,
            "source_filenames": source_filenames
        }
        documents.append(doc)

    index_name = INDEXES["queries"]
    result = await bulk_index(index_name, documents, chunk_size=batch_size)

    return {
        "queries_processed": len(queries),
        "success": result["success"],
        "failed": result["failed"],
        "errors": result.get("errors", [])
    }


async def verify_reindex(source_index: str, target_index: str) -> Dict[str, Any]:
    """Verify reindex by comparing document counts"""
    logger.info(f"Verifying reindex from {source_index} to {target_index}")

    try:
        from rag_api.elastic_client import get_client

        es = await get_client()

        source_count = await es.count(index=source_index)
        target_count = await es.count(index=target_index)

        await es.close()

        return {
            "source_count": source_count.get("count", 0),
            "target_count": target_count.get("count", 0),
            "match": source_count.get("count", 0) == target_count.get("count", 0)
        }
    except Exception as e:
        logger.error(f"Verification error: {e}")
        return {"error": str(e)}


async def reset_indexes(confirm: bool = False) -> Dict[str, Any]:
    """Delete and recreate all indexes"""
    if not confirm:
        logger.warning("Use --confirm to actually delete indexes")
        return {"status": "cancelled"}

    logger.info("Resetting all Elasticsearch indexes...")

    results = {}
    for index_key, index_name in INDEXES.items():
        try:
            if await index_exists(index_name):
                await delete_index(index_name)
                logger.info(f"Deleted {index_name}")
            results[index_key] = "deleted"
        except Exception as e:
            logger.error(f"Error deleting {index_name}: {e}")
            results[index_key] = f"error: {e}"

    await ensure_indexes()
    logger.info("All indexes recreated")

    return results


async def show_status() -> Dict[str, Any]:
    """Show current Elasticsearch and index status"""
    logger.info("Showing Elasticsearch status...")

    try:
        from rag_api.elastic_client import get_client, health_check

        health = await health_check()

        es = await get_client()
        info = await es.info()
        await es.close()

        status = {
            "elasticsearch": health,
            "cluster_name": info.get("cluster_name"),
            "version": info.get("version", {}).get("number"),
            "indexes": {}
        }

        for index_key, index_name in INDEXES.items():
            exists = await index_exists(index_name)
            if exists:
                stats = await get_index_stats(index_name)
                status["indexes"][index_key] = {
                    "name": index_name,
                    "exists": True,
                    "docs": stats.get("docs", {}).get("count", 0)
                }
            else:
                status["indexes"][index_key] = {
                    "name": index_name,
                    "exists": False
                }

        return status

    except Exception as e:
        logger.error(f"Status error: {e}")
        return {"error": str(e)}


async def main():
    parser = argparse.ArgumentParser(description="Elasticsearch Reindex Tool")

    parser.add_argument("--full", action="store_true", help="Full reindex of all data")
    parser.add_argument("--documents", action="store_true", help="Reindex documents only")
    parser.add_argument("--logs", action="store_true", help="Reindex application logs only")
    parser.add_argument("--queries", action="store_true", help="Reindex query analytics only")
    parser.add_argument("--sync", action="store_true", help="Sync from ChromaDB to Elasticsearch")
    parser.add_argument("--reset", action="store_true", help="Reset all indexes")
    parser.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for indexing")
    parser.add_argument("--verify", action="store_true", help="Verify reindex")
    parser.add_argument("--confirm", action="store_true", help="Confirm destructive operations")

    args = parser.parse_args()

    if not any([args.full, args.documents, args.logs, args.queries, args.sync,
                args.reset, args.status, args.verify]):
        parser.print_help()
        return 1

    start_time = datetime.now()
    logger.info(f"=== Elasticsearch Reindex Started at {start_time} ===")

    try:
        if args.status:
            result = await show_status()
            print("\n=== Status ===")
            print(f"ES Status: {result.get('elasticsearch', {})}")
            print(f"Indexes:")
            for key, idx in result.get("indexes", {}).items():
                print(f"  {key}: {idx}")

        elif args.reset:
            result = await reset_indexes(confirm=args.confirm)
            print(f"\n=== Reset Results ===")
            for key, status in result.items():
                print(f"  {key}: {status}")

        elif args.full:
            print("\n=== Full Reindex ===")

            await ensure_indexes()
            print("Ensured indexes created")

            doc_result = await reindex_documents(args.batch_size)
            print(f"Documents: {doc_result.get('chunks_indexed', 0)} indexed, {doc_result.get('failed', 0)} failed")

            log_result = await reindex_logs(args.batch_size)
            print(f"Logs: {log_result.get('logs_processed', 0)} processed, {log_result.get('success', 0)} success")

            query_result = await reindex_queries(args.batch_size)
            print(f"Queries: {query_result.get('queries_processed', 0)} processed, {query_result.get('success', 0)} success")

        elif args.documents:
            print("\n=== Document Reindex ===")
            await ensure_indexes()
            result = await reindex_documents(args.batch_size)
            print(f"Documents: {result.get('chunks_indexed', 0)} indexed, {result.get('failed', 0)} failed")

        elif args.logs:
            print("\n=== Logs Reindex ===")
            await ensure_indexes()
            result = await reindex_logs(args.batch_size)
            print(f"Logs: {result.get('logs_processed', 0)} processed, {result.get('success', 0)} success")

        elif args.queries:
            print("\n=== Queries Reindex ===")
            await ensure_indexes()
            result = await reindex_queries(args.batch_size)
            print(f"Queries: {result.get('queries_processed', 0)} processed, {result.get('success', 0)} success")

        elif args.sync:
            print("\n=== Sync from ChromaDB ===")
            await ensure_indexes()
            result = await sync_from_chroma(batch_size=args.batch_size)
            print(f"Sync: {result.get('synced', 0)} synced, {result.get('failed', 0)} failed")
            print(f"Time: {result.get('total_time_seconds', 0)}s")

        elif args.verify:
            print("\n=== Verify Reindex ===")
            if await index_exists("chroma_db"):
                result = await verify_reindex("chroma_db", INDEXES["documents"])
                print(f"Source count: {result.get('source_count', 'N/A')}")
                print(f"Target count: {result.get('target_count', 'N/A')}")
                print(f"Match: {result.get('match', False)}")
            else:
                print("Source index not found, skipping verification")

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n=== Completed in {elapsed:.2f}s ===")

    except Exception as e:
        logger.error(f"Reindex failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
