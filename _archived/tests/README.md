# Test Files

This directory contains test scripts for validating various components of the GraphTalk application.

## Test Categories

### Search & Retrieval Tests
- `test_chroma_search.py` - Validate Chroma vector database search functionality
- `test_full_context_search.py` - Test context-aware search capabilities
- `test_improved_search.py` - Test improved search implementations

### Document Processing Tests
- `test_multiformat_support.py` - Verify support for multiple document formats (PDF, DOCX, HTML, etc.)
- `test_enhanced_chunking.py` - Test document chunking with advanced tokenizers
- `test_chonkie_integration.py` - Validate Chonkie tokenizer integration

### Content & Citation Tests
- `test_citation_system.py` - Verify citation generation and formatting
- `test_auto_full_content.py` - Test automatic full content retrieval

### Integration Tests
- `test_final_integration.py` - Comprehensive integration test
- `test_websocket_query.py` - WebSocket connection and query tests

### Tokenization Tests
- `test_tokenizer_comparison.py` - Compare different tokenization strategies

## Running Tests

Run individual tests:
```bash
python test_chroma_search.py
python test_multiformat_support.py
```

Run all tests (requires test runner):
```bash
pytest
```

## Notes

- Tests may require specific environment variables to be set
- Some tests use temporary files and directories
- Tests validate both functionality and performance
