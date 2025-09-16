import logging
import sys
import os
from rag_api.chroma_utils import search_documents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def test_search(query: str):
    print(f"\n{'='*80}")
    print(f"Testing search for query: '{query}'")
    print(f"{'='*80}")
    
    # Test with different similarity thresholds
    thresholds = [0.2, 0.3]  # Reduced to make output more concise
    
    for threshold in thresholds:
        print(f"\n{'*'*40}")
        print(f"Testing with threshold: {threshold}")
        print(f"{'*'*40}")
        
        results = search_documents(
            query=query,
            similarity_threshold=threshold,
            filename_similarity_threshold=0.5,
            max_results=10,
            min_relevance_score=0.2
        )
        
        # Print filename matches with full content info
        if results['filename_matches']:
            print("\n📂 Filename Matches (Full Content):")
            for i, (filename, match) in enumerate(results['filename_matches'].items(), 1):
                is_full = match.get('is_full_content', False)
                content_preview = match['content'][:150] + ('...' if len(match['content']) > 150 else '')
                print(f"{i}. {filename} (similarity: {match['similarity']:.2f}, full_content: {'✅' if is_full else '❌'})")
                print(f"   Preview: {content_preview}\n")
        
        # Print semantic matches with type info
        if results['semantic_results']:
            print("\n🔍 Combined Results (Filename Matches First):")
            for i, doc in enumerate(results['semantic_results'], 1):
                similarity = doc.metadata.get('similarity_score', 0)
                is_filename_match = doc.metadata.get('is_filename_match', False)
                is_full = doc.metadata.get('is_full_content', False)
                
                match_type = "FILENAME" if is_filename_match else "semantic"
                full_info = " (FULL)" if is_full else ""
                
                print(f"{i}. {match_type}{full_info}: {doc.metadata.get('filename', 'untitled')} (score: {similarity:.2f})")
                preview = doc.page_content[:150] + ('...' if len(doc.page_content) > 150 else '')
                print(f"   {preview}\n")
        
        # Print stats
        stats = results.get('stats', {})
        print("\n📊 Search Statistics:")
        print(f"- Total files processed: {stats.get('total_files_processed', 0)}")
        print(f"- Files with matches: {stats.get('files_with_matches', 0)}")
        print(f"- Total chunks processed: {stats.get('total_chunks_processed', 0)}")
        print(f"- Total matching chunks: {stats.get('total_matching_chunks', 0)}")
        print(f"- Processing time: {stats.get('processing_time_ms', 0)}ms")
        
        if 'error' in stats and stats['error']:
            print(f"\n❌ Error: {stats['error']}")

if __name__ == "__main__":
    # Test with the query that was having issues
    test_query = "История компании"
    
    # First test with the main query and full content loading
    print("\n" + "="*80)
    print("TESTING WITH FULL CONTENT LOADING")
    print("="*80)
    test_search(test_query)
    
    # Test with a simpler query to see more matches
    print("\n" + "="*80)
    print("TESTING WITH SIMPLER QUERY")
    print("="*80)
    test_search("история")
    
    # Test with company name
    print("\n" + "="*80)
    print("TESTING WITH COMPANY NAME")
    print("="*80)
    test_search("абтмэн")
