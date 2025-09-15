import sys
import os
import logging
from chromadb import PersistentClient
from chromadb.config import Settings
from chromadb.utils import embedding_functions

def test_chroma_search():
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize Chroma client with local database
        client = PersistentClient(path="./chroma_db")
        
        # List all collections
        collections = client.list_collections()
        logger.info(f"Found {len(collections)} collections")
        
        for collection in collections:
            logger.info(f"\nCollection: {collection.name} (ID: {collection.id})")
            logger.info(f"Metadata: {collection.metadata}")
            
            # Get collection stats
            stats = collection.count()
            logger.info(f"Number of documents: {stats}")
            
            # Try a simple search
            if stats > 0:
                try:
                    logger.info("Getting first few documents...")
                    # Get the first few documents to see what's in the collection
                    results = collection.get(
                        limit=min(3, stats),
                        include=["documents", "metadatas"]
                    )
                    logger.info("Documents in collection:")
                    if results and 'documents' in results and results['documents']:
                        for i, doc in enumerate(results['documents']):
                            logger.info(f"  Document {i+1}:")
                            logger.info(f"    Content: {str(doc)[:200]}..." if len(str(doc)) > 200 else f"    Content: {doc}")
                            if 'metadatas' in results and results['metadatas'] and i < len(results['metadatas']):
                                logger.info(f"    Metadata: {results['metadatas'][i]}")
                except Exception as e:
                    logger.error(f"Error during search: {str(e)}")
                    raise
                    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    test_chroma_search()
