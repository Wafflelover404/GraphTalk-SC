#!/usr/bin/env python3
"""
Test script to verify Chonkie integration with the RAG system
"""
import sys
import os

# Add the rag_api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rag_api'))

from chonkie import TokenChunker

def test_chonkie_basic():
    """Test basic Chonkie functionality"""
    print("Testing Chonkie TokenChunker...")
    
    # Initialize chunker
    chunker = TokenChunker(
        tokenizer="gpt2",
        chunk_size=512,
        chunk_overlap=50
    )
    
    # Test text
    test_text = """
    This is a test document to verify that Chonkie is working correctly.
    Chonkie is a modern chunking library that provides better semantic boundaries
    compared to traditional character-based splitting methods. It uses token-based
    chunking which is more aligned with how language models process text.
    
    The TokenChunker uses a tokenizer (like GPT-2) to split text into meaningful
    chunks based on token counts rather than character counts. This ensures that
    chunks are more semantically coherent and better suited for embedding models.
    """
    
    # Chunk the text
    chunks = chunker.chunk(test_text)
    
    print(f"\n✓ Successfully created {len(chunks)} chunks")
    
    # Display chunk information
    for i, chunk in enumerate(chunks):
        print(f"\nChunk {i+1}:")
        print(f"  - Text length: {len(chunk.text)} characters")
        print(f"  - Token count: {chunk.token_count}")
        print(f"  - Start index: {chunk.start_index}")
        print(f"  - End index: {chunk.end_index}")
        print(f"  - Preview: {chunk.text[:100]}...")
    
    return True

def test_chonkie_with_langchain():
    """Test Chonkie integration with LangChain Document format"""
    print("\n\nTesting Chonkie with LangChain Document format...")
    
    from langchain_core.documents import Document
    from chonkie import TokenChunker
    
    chunker = TokenChunker(
        tokenizer="gpt2",
        chunk_size=512,
        chunk_overlap=50
    )
    
    # Sample text
    text = "This is a sample document for testing. " * 50
    
    # Chunk and convert to LangChain Documents
    chunks = chunker.chunk(text)
    documents = []
    
    for chunk in chunks:
        doc = Document(
            page_content=chunk.text,
            metadata={
                "chunk_start": chunk.start_index,
                "chunk_end": chunk.end_index,
                "token_count": chunk.token_count
            }
        )
        documents.append(doc)
    
    print(f"✓ Successfully created {len(documents)} LangChain Documents")
    print(f"  - First document metadata: {documents[0].metadata}")
    
    return True

if __name__ == "__main__":
    try:
        print("=" * 60)
        print("Chonkie Integration Test")
        print("=" * 60)
        
        # Run tests
        test_chonkie_basic()
        test_chonkie_with_langchain()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
