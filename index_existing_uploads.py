#!/usr/bin/env python3
"""
Index existing uploaded documents into Chroma vector database.
This script processes all files in the uploads directory and indexes them for search.
"""

import os
import sys
from pathlib import Path

# Add rag_api to path
rag_api_path = os.path.join(os.path.dirname(__file__), 'rag_api')
sys.path.append(rag_api_path)

# Import after path is set
from chroma_utils import index_document_to_chroma, reindex_documents

def main():
    """Index all existing uploaded documents"""
    uploads_dir = Path("uploads")
    
    if not uploads_dir.exists():
        print("❌ Uploads directory not found")
        return
    
    # Get all files in uploads directory
    file_paths = []
    for file_path in uploads_dir.rglob("*"):
        if file_path.is_file():
            file_paths.append(str(file_path))
    
    if not file_paths:
        print("❌ No files found in uploads directory")
        return
    
    print(f"📁 Found {len(file_paths)} files to index:")
    for file_path in file_paths[:10]:  # Show first 10
        print(f"  - {os.path.basename(file_path)}")
    
    if len(file_paths) > 10:
        print(f"  ... and {len(file_paths) - 10} more files")
    
    # Index all documents
    print("\n🔧 Starting document indexing...")
    try:
        stats = reindex_documents("uploads", file_paths)
        
        print(f"✅ Indexing completed!")
        print(f"📊 Results:")
        print(f"  - Processed: {stats['processed']}")
        print(f"  - Successful: {stats['successful']}")
        print(f"  - Failed: {stats['failed']}")
        print(f"  - Errors: {len(stats['errors'])}")
        
        if stats['errors']:
            print("\n❌ Errors encountered:")
            for error in stats['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")
        
    except Exception as e:
        print(f"❌ Indexing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
