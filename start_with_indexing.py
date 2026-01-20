#!/usr/bin/env python3
"""
Startup script that ensures all documents are indexed before starting the server
"""

import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_documents_indexed():
    """Ensure all documents in uploads directory are indexed"""
    try:
        from auto_indexer import AutoIndexer
        
        logger.info("🔍 Checking document indexing status...")
        indexer = AutoIndexer()
        
        # Get indexed files
        indexed_files = indexer.get_indexed_files_from_chroma()
        
        # Count files in uploads directory
        uploads_dir = Path("uploads")
        if not uploads_dir.exists():
            logger.info("📁 No uploads directory found, creating it...")
            uploads_dir.mkdir(exist_ok=True)
            return
        
        all_files = [f.name for f in uploads_dir.rglob("*") if f.is_file()]
        
        logger.info(f"📊 Found {len(all_files)} files in uploads directory")
        logger.info(f"📊 Found {len(indexed_files)} files indexed in Chroma")
        
        # Check if all files are indexed
        unindexed_files = set(all_files) - indexed_files
        
        if unindexed_files:
            logger.info(f"🔧 Indexing {len(unindexed_files)} unindexed files...")
            stats = indexer.index_all_existing()
            
            if stats['failed'] > 0:
                logger.warning(f"⚠️ {stats['failed']} files failed to index")
            else:
                logger.info("✅ All documents successfully indexed!")
        else:
            logger.info("✅ All documents already indexed!")
            
    except Exception as e:
        logger.error(f"❌ Error during document indexing: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main startup function"""
    logger.info("🚀 Starting WikiAI RAG Server with document indexing...")
    
    # Ensure documents are indexed
    ensure_documents_indexed()
    
    # Start the main server
    logger.info("🚀 Starting FastAPI server...")
    try:
        import asyncio
        from main import main as main_func
        
        # Run the main function
        asyncio.run(main_func())
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
