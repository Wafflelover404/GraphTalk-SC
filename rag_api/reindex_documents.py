#!/usr/bin/env python3
"""
Script to reindex all documents in the database.

This script will:
1. Fetch all documents from the database
2. Save them to a temporary directory
3. Reindex them using the reindex_documents function
"""
import os
import tempfile
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
import logging
from .chroma_utils import reindex_documents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get a connection to the SQLite database."""
    db_path = os.path.join(os.path.dirname(__file__), "rag_app.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_documents() -> List[Dict[str, Any]]:
    """Fetch all documents from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, filename, content FROM document_store')
    documents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return documents

def save_documents_to_temp(documents: List[Dict[str, Any]]) -> str:
    """Save documents to a temporary directory and return the directory path."""
    temp_dir = tempfile.mkdtemp(prefix="reindex_docs_")
    
    for doc in documents:
        try:
            filename = doc['filename']
            content = doc['content']
            
            # Handle both string and bytes content
            if isinstance(content, str):
                content = content.encode('utf-8')
            elif not isinstance(content, bytes):
                logger.warning(f"Unexpected content type for {filename}, skipping")
                continue
                
            filepath = os.path.join(temp_dir, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'wb') as f:
                f.write(content)
                
            logger.info(f"Saved document to {filepath}")
            
        except Exception as e:
            logger.error(f"Error processing document {doc.get('id', 'unknown')}: {str(e)}")
    
    return temp_dir

def main():
    try:
        logger.info("Starting document reindexing process...")
        
        # 1. Get all documents from the database
        logger.info("Fetching documents from database...")
        documents = get_all_documents()
        
        if not documents:
            logger.warning("No documents found in the database.")
            return
            
        logger.info(f"Found {len(documents)} documents in the database.")
        
        # 2. Save documents to a temporary directory
        logger.info("Saving documents to temporary directory...")
        temp_dir = save_documents_to_temp(documents)
        
        # 3. Reindex the documents
        logger.info("Starting reindexing process...")
        stats = reindex_documents(temp_dir)
        
        # 4. Print statistics
        logger.info("\nReindexing completed!")
        logger.info(f"Total files processed: {stats['total_files']}")
        logger.info(f"Successfully indexed: {stats['successful']}")
        logger.info(f"Failed to index: {stats['failed']}")
        logger.info(f"Total chunks created: {stats['total_chunks']}")
        logger.info(f"Time taken: {stats['total_time_seconds']:.2f} seconds")
        
        if stats['file_types']:
            logger.info("\nFile types processed:")
            for ext, count in stats['file_types'].items():
                logger.info(f"  {ext}: {count}")
                
        if stats['errors']:
            logger.warning("\nEncountered some errors during processing:")
            for error in stats['errors'][:10]:  # Show first 10 errors to avoid flooding logs
                logger.warning(f"  - {error}")
            if len(stats['errors']) > 10:
                logger.warning(f"  ... and {len(stats['errors']) - 10} more errors")
                
    except Exception as e:
        logger.error(f"Fatal error during reindexing: {str(e)}", exc_info=True)
        raise
    finally:
        # Clean up temporary directory if it exists
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            import shutil
            try:
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Could not clean up temporary directory {temp_dir}: {str(e)}")

if __name__ == "__main__":
    main()
