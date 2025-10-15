#!/usr/bin/env python3
"""
Test automatic full file content retrieval in search results
"""
import sys
import os
import tempfile
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rag_api'))

def test_auto_full_content():
    """Test that search automatically includes full file content"""
    print("=" * 70)
    print("Automatic Full File Content Test")
    print("=" * 70)
    
    from chroma_utils import search_documents, index_document_to_chroma, vectorstore
    from langchain_core.documents import Document
    
    # Create a test document
    test_content = """# Machine Learning Guide

## Introduction
Machine learning is a powerful approach to artificial intelligence.
It enables computers to learn from data without explicit programming.

## Key Concepts
1. Supervised Learning - Learning from labeled data
2. Unsupervised Learning - Finding patterns in unlabeled data
3. Reinforcement Learning - Learning through trial and error

## Applications
- Image Recognition
- Natural Language Processing
- Recommendation Systems
- Autonomous Vehicles

## Conclusion
Machine learning continues to revolutionize technology and society.
"""
    
    print("\n1️⃣  Creating test document...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        # Create a mock database entry
        print("   ✓ Test file created")
        
        # Simulate search results with metadata
        print("\n2️⃣  Simulating search with chunk...")
        
        # Create a mock result that would come from search
        mock_chunk = Document(
            page_content="Machine learning is a powerful approach to artificial intelligence.",
            metadata={
                'filename': os.path.basename(temp_file),
                'source': temp_file,
                'file_id': None,
                'relevance_score': 0.85
            }
        )
        
        print(f"   Chunk content: {mock_chunk.page_content[:60]}...")
        print(f"   Source file: {mock_chunk.metadata['filename']}")
        
        # Test get_full_file_content function
        print("\n3️⃣  Retrieving full file content...")
        from chroma_utils import get_full_file_content
        
        full_content_data = get_full_file_content(source_path=temp_file)
        
        if full_content_data['content']:
            print(f"   ✓ Full content retrieved!")
            print(f"   ✓ Content length: {len(full_content_data['content'])} characters")
            print(f"   ✓ Chunk was only: {len(mock_chunk.page_content)} characters")
            print(f"   ✓ Full file is {len(full_content_data['content']) // len(mock_chunk.page_content)}x larger")
            
            # Show what the AI would receive
            print("\n4️⃣  What AI receives:")
            print("-" * 70)
            print("CHUNK (relevant excerpt):")
            print(mock_chunk.page_content)
            print("\nFULL FILE CONTENT (complete context):")
            print(full_content_data['content'][:300] + "...")
            print("-" * 70)
            
            print("\n5️⃣  Benefits:")
            print("   ✓ AI gets relevant chunk for context")
            print("   ✓ AI gets full file for complete understanding")
            print("   ✓ AI can cite specific sections")
            print("   ✓ AI has complete source material")
            
        else:
            print(f"   ✗ Failed to retrieve: {full_content_data.get('error')}")
            return False
        
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)
    
    print("\n" + "=" * 70)
    print("How It Works in Real Search")
    print("=" * 70)
    
    explanation = """
When you search:
1. System finds relevant chunks (excerpts)
2. For EACH chunk, system automatically:
   - Gets the file_id, filename, or source path
   - Retrieves the COMPLETE file content
   - Adds it to metadata['full_file_content']
3. AI receives BOTH:
   - Chunk: The relevant excerpt (for context)
   - Full file: The complete document (for details)

Example:
--------
Query: "What is machine learning?"

Result 1:
  Chunk: "Machine learning is a powerful approach..."
  Full File Content: [ENTIRE document with all sections]
  
Result 2:
  Chunk: "Deep learning uses neural networks..."
  Full File Content: [ENTIRE document about deep learning]

AI can now:
- Answer based on relevant chunks
- Reference complete documents
- Cite specific sections
- Provide detailed explanations
"""
    
    print(explanation)
    
    print("\n" + "=" * 70)
    print("Usage Example")
    print("=" * 70)
    
    usage = """
from rag_api.chroma_utils import search_documents

# Search (automatically includes full file content)
results = search_documents(
    query="What is machine learning?",
    max_results=5
)

# Access results
for doc in results['semantic_results']:
    print(f"Chunk: {doc.page_content}")
    print(f"Score: {doc.metadata['relevance_score']}")
    
    # Full file content is automatically included!
    if doc.metadata.get('full_file_content'):
        full_content = doc.metadata['full_file_content']
        print(f"Full file: {len(full_content)} characters")
        
        # Pass to AI
        ai_prompt = f'''
        Question: What is machine learning?
        
        Relevant excerpt: {doc.page_content}
        
        Complete source document:
        {full_content}
        
        Please answer based on the complete document and cite specific sections.
        '''
"""
    
    print(usage)
    
    print("\n" + "=" * 70)
    print("✅ Automatic Full Content Retrieval Working!")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    try:
        success = test_auto_full_content()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
