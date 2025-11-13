import sys
import os
import logging
from rag_api.chroma_utils import search_documents

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_search(query: str = "test"):
    logger.info(f"Testing search with query: '{query}'")
    
    try:
        # Call the search_documents function
        results = search_documents(
            query=query,
            similarity_threshold=0.1,  # Very low threshold to get more results
            filename_similarity_threshold=0.3,
            max_results=5
        )
        
        # Print results
        print("\n=== Search Results ===")
        print(f"Query: {query}")
        
        if 'error' in results.get('stats', {}):
            print(f"Error: {results['stats']['error']}")
        
        # Print semantic results
        if results.get('semantic_results'):
            print(f"\nFound {len(results['semantic_results'])} semantic results:")
            for i, result in enumerate(results['semantic_results'][:5]):  # Limit to first 5 results
                print(f"\nResult {i+1}:")
                # Handle both dict and Document objects
                if hasattr(result, 'page_content'):  # It's a Document object
                    print(f"  Content: {result.page_content[:200]}..." if result.page_content else "  No content")
                    if hasattr(result, 'metadata') and result.metadata:
                        print(f"  Metadata: {result.metadata}")
                elif isinstance(result, dict):  # It's a dict
                    print(f"  Score: {result.get('score', 0):.4f}")
                    print(f"  Content: {result.get('content', '')[:200]}...")
                    if 'metadata' in result:
                        print(f"  Metadata: {result['metadata']}")
                else:
                    print(f"  Unknown result type: {type(result)}")
        else:
            print("\nNo semantic results found.")
        
        # Print filename matches
        if results.get('filename_matches'):
            print(f"\nFound {len(results['filename_matches'])} filename matches:")
            for i, (filename, match) in enumerate(list(results['filename_matches'].items())[:3]):  # Limit to first 3
                print(f"\nMatch {i+1}:")
                print(f"  Filename: {filename}")
                print(f"  Similarity: {match.get('similarity', 0):.4f}")
                if 'content' in match:
                    print(f"  Preview: {str(match['content'])[:200]}...")
        else:
            print("\nNo filename matches found.")
        
        # Print stats
        if 'stats' in results:
            print("\n=== Search Statistics ===")
            for key, value in results['stats'].items():
                if value is not None:  # Skip None values
                    print(f"{key.replace('_', ' ').title()}: {value}")
    
    except Exception as e:
        logger.error(f"Error during search: {str(e)}", exc_info=True)

if __name__ == "__main__":
    # Test with a default query or use the first command line argument
    query = sys.argv[1] if len(sys.argv) > 1 else "история компании"
    test_search(query)
