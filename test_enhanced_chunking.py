#!/usr/bin/env python3
"""
Test script to verify enhanced chunking and search capabilities
"""
import sys
import os
import tempfile

# Add the rag_api directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'rag_api'))

def test_chunker_selection():
    """Test intelligent chunker selection"""
    print("Testing intelligent chunker selection...")
    
    from chroma_utils import select_optimal_chunker, semantic_chunker, token_chunker, sentence_chunker
    
    # Test code file
    code_chunker = select_optimal_chunker("test.py", "def hello(): pass")
    assert code_chunker == token_chunker, "Code files should use token chunker"
    print("  ✓ Code files use TokenChunker")
    
    # Test markdown file
    md_chunker = select_optimal_chunker("test.md", "# Header\n\nContent here")
    assert md_chunker == sentence_chunker, "Markdown files should use sentence chunker"
    print("  ✓ Markdown files use SentenceChunker")
    
    # Test short text
    short_chunker = select_optimal_chunker("test.txt", "Short text" * 50)
    assert short_chunker == sentence_chunker, "Short texts should use sentence chunker"
    print("  ✓ Short texts use SentenceChunker")
    
    # Test long text
    long_chunker = select_optimal_chunker("test.txt", "Long text " * 500)
    assert long_chunker == semantic_chunker, "Long texts should use semantic chunker"
    print("  ✓ Long texts use SemanticChunker")
    
    return True

def test_semantic_chunking():
    """Test semantic chunking capabilities"""
    print("\nTesting semantic chunking...")
    
    from chroma_utils import semantic_chunker
    
    # Test text with clear semantic boundaries
    test_text = """
    Machine learning is a subset of artificial intelligence. It focuses on algorithms that learn from data.
    Deep learning is a type of machine learning. It uses neural networks with multiple layers.
    Natural language processing deals with text and speech. It enables computers to understand human language.
    """
    
    try:
        chunks = semantic_chunker.chunk(test_text)
        print(f"  ✓ Created {len(chunks)} semantic chunks")
        
        for i, chunk in enumerate(chunks):
            print(f"    Chunk {i+1}: {len(chunk.text)} chars, {chunk.token_count} tokens")
        
        return True
    except Exception as e:
        print(f"  ✗ Semantic chunking failed: {e}")
        return False

def test_hybrid_search():
    """Test hybrid search functionality"""
    print("\nTesting hybrid search components...")
    
    from chroma_utils import calculate_bm25_score, batch_cosine_similarity
    import numpy as np
    
    # Test BM25 scoring
    query_terms = ["machine", "learning"]
    document = "Machine learning is a powerful tool for data analysis and learning patterns"
    avg_length = 10.0
    
    score = calculate_bm25_score(query_terms, document, avg_length)
    assert score > 0, "BM25 score should be positive for matching terms"
    print(f"  ✓ BM25 scoring works (score: {score:.3f})")
    
    # Test cosine similarity with proper shapes
    query_emb = np.random.rand(384).astype(np.float32)
    doc_embs = np.random.rand(10, 384).astype(np.float32)
    
    similarities = batch_cosine_similarity(query_emb, doc_embs)
    assert len(similarities) == 10, "Should return similarity for each document"
    assert all(-1 <= s <= 1 for s in similarities), "Cosine similarities should be in [-1, 1]"
    print(f"  ✓ Batch cosine similarity works (shape: {similarities.shape})")
    
    return True

def test_document_loading():
    """Test document loading with enhanced chunking"""
    print("\nTesting document loading with enhanced chunking...")
    
    from chroma_utils import load_and_split_document
    from langchain_core.documents import Document
    
    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("""
        This is a test document for the enhanced chunking system.
        It contains multiple paragraphs to test the chunking capabilities.
        
        The system should intelligently split this content into meaningful chunks.
        Each chunk should maintain semantic coherence and context.
        
        This is the final paragraph of the test document.
        It helps verify that the chunking works correctly across boundaries.
        """)
        temp_file = f.name
    
    try:
        # Load and split the document
        chunks = load_and_split_document(temp_file, "test.txt")
        
        assert len(chunks) > 0, "Should create at least one chunk"
        assert all(isinstance(c, Document) for c in chunks), "All chunks should be Documents"
        
        # Check metadata
        for chunk in chunks:
            assert 'filename' in chunk.metadata, "Should have filename metadata"
            assert 'token_count' in chunk.metadata, "Should have token_count metadata"
            assert 'chunk_start' in chunk.metadata, "Should have chunk_start metadata"
        
        print(f"  ✓ Created {len(chunks)} chunks from test document")
        print(f"    First chunk: {len(chunks[0].page_content)} chars, {chunks[0].metadata.get('token_count', 0)} tokens")
        
        return True
    except Exception as e:
        print(f"  ✗ Document loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

if __name__ == "__main__":
    try:
        print("=" * 70)
        print("Enhanced Chunking and Search Test Suite")
        print("=" * 70)
        
        # Run tests
        tests = [
            ("Chunker Selection", test_chunker_selection),
            ("Semantic Chunking", test_semantic_chunking),
            ("Hybrid Search", test_hybrid_search),
            ("Document Loading", test_document_loading),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n✗ {test_name} failed with exception: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        
        print("\n" + "=" * 70)
        print(f"Test Results: {passed} passed, {failed} failed")
        print("=" * 70)
        
        if failed == 0:
            print("✓ All tests passed successfully!")
            sys.exit(0)
        else:
            print("✗ Some tests failed")
            sys.exit(1)
        
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
