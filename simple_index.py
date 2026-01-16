#!/usr/bin/env python3
"""
Simple script to index existing uploaded documents into Chroma vector database.
"""

import os
import sys
from pathlib import Path

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
    
    # Simple indexing without complex imports
    print("\n🔧 Starting document indexing...")
    
    try:
        # Import chroma directly
        import chromadb
        from chromadb.config import Settings
        from langchain_chroma import Chroma
        
        # Initialize Chroma
        chroma_settings = Settings(
            persist_directory="chroma_db",
            anonymized_telemetry=False
        )
        client = chromadb.PersistentClient(path="chroma_db", settings=chroma_settings)
        
        # Create collection
        collection_name = "documents"
        try:
            client.delete_collection(name=collection_name)
        except:
            pass
        
        collection = client.get_or_create_collection(name=collection_name)
        
        # Process each file
        processed = 0
        successful = 0
        failed = 0
        
        for file_path in file_paths:
            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Create document
                from langchain_core.documents import Document
                doc = Document(
                    page_content=content,
                    metadata={"source": os.path.basename(file_path)}
                )
                
                # Add to collection
                collection.add([doc])
                processed += 1
                successful += 1
                
                if processed % 10 == 0:
                    print(f"  Processed {processed}/{len(file_paths)} files...")
                
            except Exception as e:
                failed += 1
                print(f"❌ Failed to process {file_path}: {e}")
        
        print(f"\n✅ Indexing completed!")
        print(f"📊 Results:")
        print(f"  - Processed: {processed}")
        print(f"  - Successful: {successful}")
        print(f"  - Failed: {failed}")
        
    except Exception as e:
        print(f"❌ Indexing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
