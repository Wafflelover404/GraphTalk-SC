import os
import re
import json
import logging
import hashlib
import time
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from langchain_core.documents import Document

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import nltk

from rag_api.elastic_config import (
    INDEXES, get_index_mapping, get_client, get_es_config
)
from rag_api.elastic_client import (
    create_index, delete_index, bulk_index, index_exists, refresh_index
)
from rag_api.chroma_utils import (
    vectorstore, embedding_function, preprocess_text
)
from rag_api.db_utils import (
    get_file_content_by_filename, get_all_documents, get_db_connection
)

logger = logging.getLogger(__name__)
import nltk


def generate_doc_id(doc_id: int, chunk_index: int) -> str:
    return f"{doc_id}_{chunk_index}"


def create_document_from_chunk(chunk_data: Dict[str, Any], doc_id: int) -> Dict[str, Any]:
    return {
        "doc_id": doc_id,
        "filename": chunk_data.get("metadata", {}).get("filename", ""),
        "content": chunk_data.get("page_content", ""),
        "content_normalized": preprocess_text(chunk_data.get("page_content", "")),
        "file_type": chunk_data.get("metadata", {}).get("file_type", ""),
        "chunk_index": chunk_data.get("metadata", {}).get("chunk_index", 0),
        "token_count": chunk_data.get("metadata", {}).get("token_count", 0),
        "upload_timestamp": datetime.fromtimestamp(
            chunk_data.get("metadata", {}).get("created_at", time.time())
        ).isoformat(),
        "created_at": datetime.fromtimestamp(
            chunk_data.get("metadata", {}).get("created_at", time.time())
        ).isoformat(),
        "modified_at": datetime.fromtimestamp(
            chunk_data.get("metadata", {}).get("modified_at", time.time())
        ).isoformat(),
        "embedding": [],
        "relevance_score": 0.0
    }


async def ensure_indexes() -> Dict[str, bool]:
    results = {}
    for index_key, index_name in INDEXES.items():
        try:
            mapping = get_index_mapping(index_name)
            success = await create_index(
                index_name,
                settings=mapping.get("settings", {}),
                mappings=mapping.get("mappings", {})
            )
            results[index_key] = success
        except Exception as e:
            logger.error(f"Error creating index {index_name}: {e}")
            results[index_key] = False
    return results


async def index_rag_document(
    doc_id: int,
    filename: str,
    content: str,
    metadata: Dict[str, Any] = None,
    chunk_size: int = 512,
    chunk_overlap: int = 128
) -> Dict[str, Any]:
    es = await get_client()
    index_name = INDEXES["documents"]

    if metadata is None:
        metadata = {}

    file_type = os.path.splitext(filename)[1].lower() if filename else ""

    if isinstance(content, bytes):
        try:
            content = content.decode('utf-8')
        except:
            content = content.decode('latin1')

    sentences = re.split(r'(?<=[.!?])\s+', content)
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
            chunk_metadata = {
                **metadata,
                "filename": filename,
                "file_type": file_type,
                "chunk_index": len(chunks),
                "chunk_text": chunk_text,
                "token_count": current_length
            }
            chunks.append({
                "page_content": chunk_text,
                "metadata": chunk_metadata
            })
            current_chunk = [sentence]
            current_length = sentence_length
        else:
            current_chunk.append(sentence)
            current_length += sentence_length

    if current_chunk:
        chunk_text = ' '.join(current_chunk)
        chunk_metadata = {
            **metadata,
            "filename": filename,
            "file_type": file_type,
            "chunk_index": len(chunks),
            "chunk_text": chunk_text,
            "token_count": current_length
        }
        chunks.append({
            "page_content": chunk_text,
            "metadata": chunk_metadata
        })

    documents_to_index = []
    for i, chunk in enumerate(chunks):
        embedding = embedding_function.embed_query(chunk["page_content"])
        doc = {
            "doc_id": doc_id,
            "filename": filename,
            "content": chunk["page_content"],
            "content_normalized": preprocess_text(chunk["page_content"]),
            "file_type": file_type,
            "chunk_index": chunk["metadata"].get("chunk_index", i),
            "token_count": chunk["metadata"].get("token_count", 0),
            "upload_timestamp": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "modified_at": datetime.now().isoformat(),
            "embedding": embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding),
            "relevance_score": 0.0
        }
        doc_id_str = generate_doc_id(doc_id, i)
        documents_to_index.append({"_id": doc_id_str, **doc})

    result = await bulk_index(index_name, documents_to_index)
    await es.close()

    return {
        "doc_id": doc_id,
        "filename": filename,
        "chunks_indexed": len(chunks),
        "success": result["success"],
        "failed": result["failed"]
    }


async def delete_rag_document(doc_id: int) -> Dict[str, Any]:
    index_name = INDEXES["documents"]
    deleted = 0
    failed = 0
    total = 0

    es = await get_client()
    try:
        prefix = f"{doc_id}_"
        query = {"query": {"bool": {"must": [{"prefix": {"_id": prefix}}]}}}
        count_result = await es.count(index=index_name, body=query)
        total = count_result.get("count", 0)

        if total > 0:
            await es.delete_by_query(
                index=index_name,
                body={"query": {"bool": {"must": [{"prefix": {"_id": prefix}}]}}},
                refresh=True
            )
            deleted = total
    except Exception as e:
        logger.error(f"Error deleting document {doc_id}: {e}")
        failed = total
    finally:
        await es.close()

    return {"deleted": deleted, "failed": failed}


async def sync_from_chroma(
    batch_size: int = 100,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]:
    start_time = time.time()
    synced = 0
    failed = 0
    errors = []

    index_name = INDEXES["documents"]

    try:
        collection = vectorstore._collection
        count = collection.count()
        logger.info(f"Found {count} documents in ChromaDB")

        for offset in range(0, count, batch_size):
            try:
                batch = collection.get(
                    limit=batch_size,
                    offset=offset,
                    include=['documents', 'metadatas', 'embeddings']
                )

                documents_to_index = []
                for i, (doc_content, metadata, embedding) in enumerate(zip(
                    batch.get('documents', []),
                    batch.get('metadatas', []),
                    batch.get('embeddings', [])
                )):
                    doc_id = metadata.get('file_id', offset + i)
                    chunk_index = metadata.get('chunk_index', i)
                    doc_id_str = generate_doc_id(doc_id, chunk_index)

                    import numpy as np
                    emb = embedding
                    if isinstance(emb, np.ndarray):
                        emb = emb.tolist()
                    elif emb is None or (hasattr(emb, '__len__') and len(emb) == 0):
                        emb = []
                    
                    doc = {
                        "_id": doc_id_str,
                        "doc_id": doc_id,
                        "filename": metadata.get('filename', ''),
                        "content": doc_content,
                        "content_normalized": preprocess_text(doc_content),
                        "file_type": metadata.get('file_type', ''),
                        "chunk_index": chunk_index,
                        "token_count": metadata.get('token_count', 0),
                        "upload_timestamp": datetime.fromtimestamp(
                            metadata.get('created_at', time.time())
                        ).isoformat(),
                        "created_at": datetime.fromtimestamp(
                            metadata.get('created_at', time.time())
                        ).isoformat(),
                        "modified_at": datetime.fromtimestamp(
                            metadata.get('modified_at', time.time())
                        ).isoformat(),
                        "embedding": emb,
                        "relevance_score": metadata.get('relevance_score', 0.0)
                    }
                    documents_to_index.append(doc)

                result = await bulk_index(index_name, documents_to_index)
                synced += int(result["success"]) if hasattr(result["success"], '__int__') else result["success"]
                failed += int(result["failed"]) if hasattr(result["failed"], '__int__') else result["failed"]
                if result.get("errors"):
                    errors.extend([str(e) for e in result["errors"]])

                if progress_callback:
                    progress_callback(min(offset + batch_size, count), count)

            except Exception as e:
                logger.error(f"Error syncing batch at offset {offset}: {e}")
                failed += batch_size
                errors.append(str(e))

    except Exception as e:
        logger.error(f"Error syncing from ChromaDB: {e}")
        errors.append(str(e))

    elapsed = time.time() - start_time
    return {
        "synced": synced,
        "failed": failed,
        "errors": errors[:10],
        "total_time_seconds": round(elapsed, 2)
    }


async def index_all_documents(
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> Dict[str, Any]:
    start_time = time.time()
    total_indexed = 0
    total_failed = 0
    errors = []

    documents = get_all_documents()
    logger.info(f"Found {len(documents)} documents to index")

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
                total_indexed += result.get("chunks_indexed", 0)
                total_failed += result.get("failed", 0)
            else:
                logger.warning(f"No content found for {filename}")
                total_failed += 1

            if progress_callback:
                progress_callback(i + 1, len(documents))

        except Exception as e:
            logger.error(f"Error indexing document {filename}: {e}")
            total_failed += 1
            errors.append(str(e))

    elapsed = time.time() - start_time
    return {
        "documents_processed": len(documents),
        "chunks_indexed": total_indexed,
        "failed": total_failed,
        "errors": errors[:10],
        "total_time_seconds": round(elapsed, 2)
    }


async def reindex_all(progress_callback: Optional[Callable[[int, int], None]] = None) -> Dict[str, Any]:
    start_time = time.time()
    index_name = INDEXES["documents"]

    try:
        if await index_exists(index_name):
            await delete_index(index_name)
            logger.info(f"Deleted existing index: {index_name}")

        await ensure_indexes()

        sync_result = await sync_from_chroma(progress_callback=progress_callback)

        elapsed = time.time() - start_time
        return {
            "status": "completed",
            "index": index_name,
            "chunks_indexed": sync_result["synced"],
            "failed": sync_result["failed"],
            "total_time_seconds": round(elapsed, 2),
            "errors": sync_result.get("errors", [])[:5]
        }

    except Exception as e:
        logger.error(f"Reindex failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "total_time_seconds": round(time.time() - start_time, 2)
        }
