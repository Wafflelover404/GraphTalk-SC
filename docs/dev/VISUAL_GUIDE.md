# Visual Guide - Multi-Format Document Support

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                            │
│                    (Vue.js Frontend / cURL)                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  API Endpoints  │
                    │  (api.py,       │
                    │   main.py)      │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │                             │
        ┌─────▼──────┐             ┌──────▼──────┐
        │ File Format │             │ Validation  │
        │ Validation  │             │  (Extension │
        │             │             │   Check)    │
        └─────┬──────┘             └──────┬──────┘
              │                           │
              └───────────┬───────────────┘
                          │
                   ┌──────▼───────┐
                   │ Load File    │
                   │ to Temp Dir  │
                   └──────┬───────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
    ┌─────▼────┐   ┌─────▼────┐   ┌─────▼────┐
    │   PDF    │   │  DOCX    │   │   ZIP    │
    │ (pdfplumb│   │ (python- │   │(zipfile) │
    │ er)      │   │  docx)   │   │          │
    └─────┬────┘   └─────┬────┘   └─────┬────┘
          │              │              │
          │              │      ┌───────┼───────┐
          │              │      │       │       │
          │              │  ┌───▼──┐ ┌──▼──┐ ┌──▼──┐
          │              │  │PDF   │ │DOCX │ │TXT  │
          │              │  │(inner)  │     │ │     │
          │              │  └───┬──┘ └──┬──┘ └──┬──┘
          │              │      │      │      │
          └──────┬───────┴──────┬──────┴──────┘
                 │
          ┌──────▼─────────┐
          │ Preprocessing  │
          │  - Lowercase   │
          │  - Remove URLs │
          │  - Tokenize    │
          │  - Stopwords   │
          └──────┬─────────┘
                 │
          ┌──────▼─────────┐
          │  Chonkie       │
          │  Chunking      │
          │  (Smart        │
          │   splitting)   │
          └──────┬─────────┘
                 │
          ┌──────▼──────────────┐
          │ Metadata Enrichment  │
          │ - Add filename       │
          │ - Add archive info   │
          │ - Add timestamps     │
          │ - Add chunk indices  │
          └──────┬──────────────┘
                 │
          ┌──────▼─────────┐
          │  Embeddings    │
          │  (Cached)      │
          │  - Batch       │
          │  - TTL: 1h     │
          └──────┬─────────┘
                 │
          ┌──────▼──────────┐
          │  Chroma Vector  │
          │  Store          │
          │  - Index        │
          │  - Persist      │
          │  - Retrieve     │
          └─────────────────┘
```

## File Format Flow Diagram

```
INPUT FILES
    │
    ├─ PDF ──────► EnhancedPDFLoader
    │              ├─ pdfplumber extraction
    │              ├─ Page numbers
    │              └─ PDF metadata
    │
    ├─ DOCX ─────► EnhancedDocxLoader
    │              ├─ python-docx parsing
    │              ├─ Document properties
    │              └─ Structure preservation
    │
    ├─ DOC ──────► Unstructured
    │              └─ Legacy format support
    │
    ├─ ZIP ──────► ZIPLoader
    │              ├─ Extract to temp dir
    │              ├─ Recursively process:
    │              │  ├─ PDFs
    │              │  ├─ DOCXs
    │              │  ├─ TXTs
    │              │  ├─ MDs
    │              │  └─ HTMLs
    │              └─ Archive metadata
    │
    ├─ TXT ──────► Direct Read
    │              ├─ UTF-8 decode
    │              └─ Fallback latin1
    │
    ├─ MD ───────► Direct Read
    │              └─ Markdown parsing
    │
    └─ HTML ─────► Unstructured
                   └─ HTML extraction

OUTPUT: Indexed Documents in Chroma
```

## Data Pipeline

```
┌──────────────┐
│  Upload ZIP  │
│documents.zip │
└──────┬───────┘
       │
       ├─ Extract to: /tmp/xyz123/
       │
       ├─ Find: readme.txt ─────────┐
       ├─ Find: guide.pdf ──────────┤
       ├─ Find: report.docx ───────┐│
       │                           ││
       └─ Detect allowed types    │└──► Chunk
                                   │
                            ┌──────┴──────────┐
                            │                 │
                    doc1    │    doc2    doc3 │
                    ┌──────┘         ┌────────┘
                    │                 │
          ┌─────────▼────────┐ ┌─────▼──────────┐
          │   Chonkie        │ │   Chonkie      │
          │   Chunker        │ │   Chunker      │
          └─────────┬────────┘ └─────┬──────────┘
                    │                 │
        ┌───────────┴──────┐  ┌──────┴──────────┐
        │                  │  │                 │
    [chunk] [chunk] [chunk] [chunk] [chunk] [chunk]
        │                  │  │                 │
        └──────────┬───────┴──┴────────┬────────┘
                   │                   │
    ┌──────────────▼───────────────────▼──────────┐
    │ Add Metadata to Each Chunk                  │
    │ - filename: document.pdf                    │
    │ - archive_source: /uploads/documents.zip    │
    │ - archive_path: guides/document.pdf         │
    │ - chunk_start: 0                            │
    │ - chunk_end: 512                            │
    │ - token_count: 128                          │
    │ - created_at: 2025-11-12 ...                │
    └──────────────┬──────────────────────────────┘
                   │
             ┌─────▼─────┐
             │ Embedding  │
             │ Generation │
             │ (Cached)   │
             └─────┬─────┘
                   │
    ┌──────────────▼──────────────┐
    │ Chroma Vector Store         │
    │ - Store embeddings          │
    │ - Index metadata            │
    │ - Enable semantic search    │
    └────────────────────────────┘
```

## Metadata Flow

```
ORIGINAL FILE
    │
    ├─ PDF: document.pdf
    │  └─ Extract: {author, pages, created_date}
    │
    ├─ DOCX: report.docx
    │  └─ Extract: {title, author, revision}
    │
    ├─ ZIP: archive.zip
    │  └─ Extract: {path, created_date, size}
    │
    └─ TEXT: notes.txt
       └─ Extract: {created_date, modified_date}

CHUNKED DOCUMENTS
    │
    └─ Each chunk includes:
       ├─ page_content: The actual text
       ├─ filename: Original filename
       ├─ file_type: .pdf, .docx, .zip, etc.
       ├─ file_id: Unique identifier
       ├─ chunk_start: Starting position
       ├─ chunk_end: Ending position
       ├─ token_count: Number of tokens
       ├─ created_at: File creation timestamp
       ├─ modified_at: File modification timestamp
       ├─ archive_source: Path to ZIP (if from archive)
       ├─ archive_path: Original path in ZIP
       ├─ author: Document author (if available)
       ├─ page: Page number (if available)
       └─ source: Full source path
```

## Upload Process Flow

```
START: User uploads file
│
├─ VALIDATE
│  ├─ Check extension
│  ├─ Allowed: .pdf, .docx, .doc, .zip, .txt, .md, .html
│  └─ REJECT if not in list
│
├─ AUTHENTICATE
│  ├─ Check user is admin
│  └─ REJECT if not admin
│
├─ SAVE TO DATABASE
│  ├─ Generate file_id
│  ├─ Store file content as bytes
│  └─ Create database record
│
├─ PROCESS FOR INDEXING
│  ├─ Write to temporary file
│  ├─ Call load_and_split_document()
│  │  ├─ Detect file type
│  │  ├─ Select appropriate loader
│  │  └─ Extract content
│  ├─ Chunk document
│  └─ Add metadata
│
├─ INDEX TO CHROMA
│  ├─ Generate embeddings
│  ├─ Store in vector DB
│  └─ Enable semantic search
│
├─ GENERATE QUIZ (async)
│  └─ Use LLM to create quiz (background task)
│
├─ CLEANUP
│  ├─ Delete temporary file
│  └─ Release resources
│
└─ RESPOND
   ├─ Return success status
   ├─ Provide file_id
   └─ Send confirmation message

END: File ready for querying
```

## Test Coverage Map

```
test_multiformat_support.py
│
├─ Test 1: Text File Loading
│  └─ Verifies: TXT chunking, metadata, file_type
│
├─ Test 2: ZIP File Extraction
│  └─ Verifies: ZIP extraction, archive_source, archive_path
│
├─ Test 3: ZIP File Chunking
│  └─ Verifies: Chunk generation, token_count, chunk indices
│
├─ Test 4: Mixed File Types in ZIP
│  └─ Verifies: Multi-format processing, extension handling
│
├─ Test 5: File Type Validation
│  └─ Verifies: Extension filtering, unsupported file handling
│
└─ Test 6: Metadata Preservation
   └─ Verifies: Complete metadata through pipeline
```

## Error Handling Flow

```
INPUT
 │
 ├─ Invalid extension
 │  └─ Return: "Unsupported file type"
 │
 ├─ Corrupted ZIP
 │  └─ Return: "ZIP extraction failed"
 │
 ├─ Unsupported file in ZIP
 │  └─ Skip file, continue with others
 │
 ├─ PDF extraction fails
 │  └─ Fallback to basic extraction
 │
 ├─ DOCX metadata unavailable
 │  └─ Continue without optional metadata
 │
 ├─ Encoding error
 │  ├─ Try: UTF-8
 │  └─ Fallback: latin1
 │
 └─ Unknown error
    └─ Log error, return generic message

All errors logged with:
- Error type
- File/archive involved
- User ID
- Timestamp
```

## Performance Profile

```
File Size → Processing Time Estimate

< 100 KB  ──► ~100-200ms    (Fast path)
100 KB    ──► ~200-500ms    (Normal)
1 MB      ──► ~500ms-2s     (Standard)
10 MB     ──► ~2-5s         (Large document)
100 MB    ──► ~20-50s       (Very large)
ZIP (20×1MB) ──► ~15-30s    (Multiple files)

Breakdown:
  ├─ Extraction: 10-20%
  ├─ Preprocessing: 5-10%
  ├─ Chunking: 10-15%
  ├─ Embedding: 60-70%
  └─ Storage: 5-10%
```

## Configuration Options

```
GraphTalk/rag_api/chroma_utils.py
├─ EMBEDDING_MODEL: intfloat/multilingual-e5-small
├─ chunk_size: 512 tokens (Chonkie TokenChunker)
├─ chunk_overlap: 128 tokens
└─ device: GPU if available, else CPU

GraphTalk/rag_api/document_loaders.py
├─ ZIPLoader.max_files: 100
└─ allowed_extensions: ['.pdf', '.docx', '.doc', '.txt', '.md', '.html']

GraphTalk/rag_api/chroma_utils.py (Chroma config)
├─ hnsw:construction_ef: 128
├─ hnsw:search_ef: 64
├─ hnsw:M: 16
└─ collection_name: documents_optimized
```

---

This visual guide helps understand how multi-format documents flow through the system from upload to indexing to retrieval.
