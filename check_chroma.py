import os
import sys
from chromadb import PersistentClient
from chromadb.config import Settings

def check_chroma_db():
    # Initialize Chroma client
    client = PersistentClient(path="./chroma_db")
    
    # List all collections
    collections = client.list_collections()
    print(f"Found {len(collections)} collections:")
    
    for collection in collections:
        print(f"\nCollection: {collection.name}")
        print(f"  ID: {collection.id}")
        print(f"  Metadata: {collection.metadata}")
        
        # Get collection stats
        stats = collection.count()
        print(f"  Number of documents: {stats}")
        
        # Get a few sample documents if available
        if stats > 0:
            try:
                results = collection.get(limit=min(3, stats))
                print("  Sample documents:")
                for i, (id, doc, metadata) in enumerate(zip(results['ids'], results['documents'], results['metadatas'])):
                    print(f"    Document {i+1}:")
                    print(f"      ID: {id}")
                    print(f"      Content: {doc[:200]}..." if len(str(doc)) > 200 else f"      Content: {doc}")
                    print(f"      Metadata: {metadata}")
            except Exception as e:
                print(f"  Error getting documents: {str(e)}")

if __name__ == "__main__":
    check_chroma_db()
