# Utility & Diagnostic Scripts

This directory contains maintenance, diagnostic, and utility scripts for system administration and troubleshooting.

## Script Descriptions

### `check_chroma.py`
Diagnostic tool for verifying Chroma vector database integrity and status.

**Purpose:** Database health check and diagnostics
**Usage:**
```bash
python check_chroma.py
```

### `fix_sc_addresses.py`
Utility script to repair and fix semantic code addresses in the database.

**Purpose:** Data cleanup and repair
**Usage:**
```bash
python fix_sc_addresses.py
```

### `reindex_documents.py`
Reindex all documents in the Chroma vector database.

**Purpose:** Update vector embeddings and maintain search quality
**Usage:**
```bash
python reindex_documents.py
```

**When to use:**
- After updating embedding models
- If search quality degrades
- After database corruption recovery
- During maintenance windows

### `setup_metrics.py`
Initialize the metrics database with required tables and structures.

**Purpose:** Metrics system initialization
**Usage:**
```bash
python setup_metrics.py
```

**When to use:**
- First-time system setup
- After database reset
- To verify metrics schema

### `metrics_collection.py`
Alternative or supplementary metrics collection implementation.

**Purpose:** Metrics gathering and analytics
**Notes:** Check main `metrics_middleware.py` and `metricsdb.py` for the primary implementation

### `sc_search-total.py`
Alternative or duplicate search implementation (semantic code search).

**Purpose:** Experimental or backup search functionality
**Notes:** Check main `sc_search.py` for the primary implementation

## Maintenance Procedures

### Regular Maintenance
```bash
# Check database health
python check_chroma.py

# Setup/verify metrics
python setup_metrics.py
```

### After Major Updates
```bash
# Reindex documents for new embedding models
python reindex_documents.py

# Fix any corrupted addresses
python fix_sc_addresses.py
```

### Troubleshooting
```bash
# Run diagnostics
python check_chroma.py

# Rebuild indexes
python reindex_documents.py

# Verify data integrity
python fix_sc_addresses.py
```

## Script Dependencies

Most utilities depend on:
- Main application modules (llm.py, userdb.py, etc.)
- RAG API modules (chroma_utils.py, db_utils.py)
- Vector database (Chroma)

## Safety Notes

⚠️ **Important:**
- Back up your database before running reindex operations
- Run diagnostics before and after maintenance
- Test on a copy of production data first
- Monitor system performance after running utilities

## Logging

Most utilities output progress and status information. Check console output for:
- Completion status
- Number of items processed
- Any errors or warnings
- Performance metrics
