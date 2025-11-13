# Archived Files

This directory contains files that are not part of the main application flow but may be useful for testing, development, and administration purposes.

## Directory Structure

### `tests/` - Test Files (14 files)
Test and validation scripts for various system components:
- `test_auto_full_content.py` - Tests for automatic full content retrieval
- `test_chonkie_integration.py` - Tests for Chonkie tokenizer integration
- `test_chroma_search.py` - Tests for Chroma vector database search
- `test_citation_system.py` - Tests for the citation system
- `test_enhanced_chunking.py` - Tests for enhanced document chunking
- `test_final_integration.py` - Full integration tests
- `test_full_context_search.py` - Tests for context-aware search
- `test_improved_search.py` - Tests for improved search functionality
- `test_multiformat_support.py` - Tests for multi-format document support
- `test_search.py` - Basic search tests
- `test_tokenizer_comparison.py` - Tokenizer comparison tests
- `test_websocket_query.py` - WebSocket query tests
- Plus additional test files

**Usage:** Run these tests to validate system functionality
```bash
python tests/test_<name>.py
```

### `examples/` - Example Scripts (2 files)
Example usage scripts demonstrating API capabilities:
- `example_ai_citations.py` - Example showing how to generate AI responses with citations
- `example_ai_with_full_context.py` - Example showing AI responses with full context retrieval

**Usage:** Reference these files to understand how to use the RAG API
```bash
python examples/example_ai_citations.py
```

### `utilities/` - Utility & Diagnostic Scripts (6 files)
Helper scripts for maintenance, diagnostics, and data operations:
- `check_chroma.py` - Diagnostic tool to verify Chroma database integrity
- `fix_sc_addresses.py` - Utility to fix semantic code addresses
- `metrics_collection.py` - Alternative metrics collection implementation
- `reindex_documents.py` - Reindex documents in the vector database
- `sc_search-total.py` - Alternative/duplicate search implementation
- `setup_metrics.py` - Initialize metrics database

**Usage:** Run as needed for maintenance
```bash
python utilities/check_chroma.py      # Check database health
python utilities/reindex_documents.py # Reindex all documents
python utilities/setup_metrics.py     # Initialize metrics
```

### `ui_tools/` - UI & Bot Tools (2 files)
User interface and bot integrations:
- `sc_machine_ui.py` - Semantic Code machine UI interface
- `tg_bot.py` - Telegram bot integration

**Usage:** These are alternative interfaces to the main API
```bash
python ui_tools/sc_machine_ui.py
python ui_tools/tg_bot.py
```

## Main Application Files

The main application consists of these core files in the parent directory:

- **`api.py`** - Main FastAPI application with RAG endpoints
- **`main.py`** - Application startup and initialization script
- **`api_sc.py`** - Semantic Code specific API endpoints

Supporting core modules:
- `llm.py` - LLM integration and calls
- `userdb.py` - User authentication and management
- `quizdb.py` - Quiz database operations
- `uploadsdb.py` - Upload tracking
- `metricsdb.py` - Metrics and analytics database
- `metrics_api.py` - Metrics API endpoints
- `metrics_middleware.py` - Request metrics middleware
- `rag_security.py` - RAG security and filtering
- Plus RAG API modules in `rag_api/` directory

## When to Use Archived Files

✅ **Use archived files for:**
- Running tests to verify functionality
- Examples to understand API usage
- Maintenance and diagnostics
- Bot integrations and alternative UIs
- Data reindexing and recovery

❌ **Don't use for:**
- Core application deployment
- Main API endpoints (use `api.py` instead)
- Production serving

## Notes

- Test files are useful for development but not required for production
- Utility scripts help with maintenance but are not part of the normal application flow
- UI tools provide alternative interfaces and are optional
- Examples are for reference and development

To return archived files to the main directory, simply move them back:
```bash
mv _archived/tests/*.py ../
mv _archived/examples/*.py ../
# etc.
```
