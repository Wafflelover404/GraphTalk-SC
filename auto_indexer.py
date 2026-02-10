#!/usr/bin/env python3
"""
Automatic Document Indexer for WikiAI RAG System
Monitors uploads directory and automatically indexes new documents into Chroma vector database.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Set, Dict, Any
import hashlib

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutoIndexer:
    """Automatic document indexer that monitors uploads directory"""
    
    def __init__(self, uploads_dir: str = "uploads", chroma_db_path: str = "chroma_db"):
        self.uploads_dir = Path(uploads_dir)
        self.chroma_db_path = chroma_db_path
        self.indexed_files: Set[str] = set()
        self.file_hashes: Dict[str, str] = {}
        
    def get_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file content"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return ""
    
    def get_indexed_files_from_chroma(self) -> Set[str]:
        """Get list of already indexed files from Chroma"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Connect to Chroma
            chroma_settings = Settings(persist_directory=self.chroma_db_path)
            client = chromadb.PersistentClient(path=self.chroma_db_path, settings=chroma_settings)
            
            try:
                collection = client.get_collection("documents")
                # Get all documents and their metadata
                results = collection.get(include=['metadatas'])
                
                indexed_files = set()
                if results and results.get('metadatas'):
                    for metadata in results['metadatas']:
                        if metadata and metadata.get('source'):
                            indexed_files.add(metadata['source'])
                
                logger.info(f"Found {len(indexed_files)} already indexed files in Chroma")
                return indexed_files
                
            except Exception as e:
                logger.warning(f"Collection not found or empty: {e}")
                return set()
                
        except Exception as e:
            logger.error(f"Error connecting to Chroma: {e}")
            return set()
    
    def index_document(self, file_path: str, file_hash: str, organization_id: str = None) -> bool:
        """Index a single document into Chroma"""
        try:
            import chromadb
            from chromadb.config import Settings
            from langchain_core.documents import Document
            from rag_api.chroma_utils import embedding_function, get_vectorstore
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Create document with organization_id for multi-tenant filtering
            doc = Document(
                page_content=content,
                metadata={
                    "source": os.path.basename(file_path),
                    "filename": os.path.basename(file_path),  # Required by rag_security.py
                    "path": str(file_path),
                    "hash": file_hash,
                    "indexed_at": time.time(),
                    "organization_id": organization_id
                }
            )
            
            # Use the global vectorstore instance to reuse embeddings
            vectorstore = get_vectorstore()
            
            # Add document with embeddings
            vectorstore.add_texts(
                texts=[doc.page_content],
                metadatas=[doc.metadata],
                ids=[f"{file_hash}_{os.path.basename(file_path)}"]
            )
            
            logger.info(f"✅ Indexed: {os.path.basename(file_path)} (org: {organization_id})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to index {file_path}: {e}")
            return False
    
    def scan_and_index(self) -> Dict[str, int]:
        """Scan uploads directory and index new/modified files"""
        stats = {
            'scanned': 0,
            'new_files': 0,
            'modified_files': 0,
            'failed': 0
        }
        
        if not self.uploads_dir.exists():
            logger.warning(f"Uploads directory {self.uploads_dir} does not exist")
            return stats
        
        # Get currently indexed files
        if not self.indexed_files:
            self.indexed_files = self.get_indexed_files_from_chroma()
        
        # Scan all files
        for file_path in self.uploads_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            stats['scanned'] += 1
            file_name = os.path.basename(file_path)
            current_hash = self.get_file_hash(str(file_path))
            
            if not current_hash:
                stats['failed'] += 1
                continue
            
            # Check if file needs indexing
            needs_indexing = False
            
            # New file
            if file_name not in self.indexed_files:
                needs_indexing = True
                stats['new_files'] += 1
                logger.info(f"📄 New file found: {file_name}")
            
            # Modified file
            elif file_name in self.file_hashes and self.file_hashes[file_name] != current_hash:
                needs_indexing = True
                stats['modified_files'] += 1
                logger.info(f"🔄 Modified file detected: {file_name}")
            
            # Index if needed
            if needs_indexing:
                if self.index_document(str(file_path), current_hash, organization_id="default"):
                    self.indexed_files.add(file_name)
                    self.file_hashes[file_name] = current_hash
                else:
                    stats['failed'] += 1
            else:
                # Update hash for existing files
                self.file_hashes[file_name] = current_hash
        
        return stats
    
    def index_all_existing(self) -> Dict[str, int]:
        """Force index all existing files (useful for initial setup)"""
        logger.info("🔧 Starting full indexing of all existing files...")
        
        # Clear existing indexed files tracking
        self.indexed_files.clear()
        self.file_hashes.clear()
        
        # Get all files and index them
        stats = self.scan_and_index()
        
        logger.info(f"🎉 Full indexing completed:")
        logger.info(f"  - Scanned: {stats['scanned']}")
        logger.info(f"  - New files: {stats['new_files']}")
        logger.info(f"  - Modified files: {stats['modified_files']}")
        logger.info(f"  - Failed: {stats['failed']}")
        
        return stats

def main():
    """Main function for auto-indexer"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Auto-index documents for RAG search")
    parser.add_argument("--scan", action="store_true", help="Scan and index new/modified files")
    parser.add_argument("--full", action="store_true", help="Force index all existing files")
    parser.add_argument("--uploads-dir", default="uploads", help="Uploads directory path")
    parser.add_argument("--chroma-db", default="chroma_db", help="Chroma database path")
    
    args = parser.parse_args()
    
    # Create auto-indexer
    indexer = AutoIndexer(args.uploads_dir, args.chroma_db)
    
    if args.full:
        # Full indexing
        indexer.index_all_existing()
    elif args.scan:
        # Scan for new/modified files
        stats = indexer.scan_and_index()
        logger.info(f"📊 Scan results:")
        logger.info(f"  - Scanned: {stats['scanned']}")
        logger.info(f"  - New files: {stats['new_files']}")
        logger.info(f"  - Modified files: {stats['modified_files']}")
        logger.info(f"  - Failed: {stats['failed']}")
    else:
        # Default: full indexing
        indexer.index_all_existing()

if __name__ == "__main__":
    main()
