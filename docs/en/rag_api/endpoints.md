# RAG API Endpoint Reference

## Document Management

### Upload and Index Document
```http
POST /api/rag/documents
```
Upload a document to be processed and indexed by the RAG system.

**Request Headers**
```
Content-Type: multipart/form-data
Authorization: Bearer <jwt_token>
```

**Form Data**
- `file` (required): The document file to upload (PDF, DOCX, TXT, HTML, MD)
- `metadata` (optional): JSON string containing additional metadata
  - `title`: Document title
  - `description`: Document description
  - `tags`: Array of tags

**Response**
```json
{
  "id": "doc_123",
  "filename": "example.pdf",
  "status": "processing",
  "created_at": "2023-01-01T12:00:00Z"
}
```

### List Documents
```http
GET /api/rag/documents
```
List all indexed documents with pagination.

**Query Parameters**
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10, max: 100)
- `status`: Filter by status (processing, completed, failed)

**Response**
```json
{
  "items": [
    {
      "id": "doc_123",
      "filename": "example.pdf",
      "status": "completed",
      "created_at": "2023-01-01T12:00:00Z",
      "page_count": 42
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```

## Search & Generation

### Semantic Search
```http
POST /api/rag/search
```
Search across indexed documents using semantic similarity.

**Request Headers**
```
Content-Type: application/json
Authorization: Bearer <jwt_token>
```

**Request Body**
```json
{
  "query": "What is the capital of France?",
  "top_k": 5,
  "min_score": 0.5,
  "document_ids": ["doc_123", "doc_456"]
}
```

**Response**
```json
{
  "results": [
    {
      "document_id": "doc_123",
      "text": "Paris is the capital of France.",
      "score": 0.95,
      "page_number": 42,
      "metadata": {
        "title": "World Capitals"
      }
    }
  ],
  "query_time_ms": 123
}
```

### Generate Response
```http
POST /api/rag/generate
```
Generate a response using the RAG system.

**Request Headers**
```
Content-Type: application/json
Authorization: Bearer <jwt_token>
```

**Request Body**
```json
{
  "query": "Explain the main concepts of RAG",
  "max_tokens": 1000,
  "temperature": 0.7,
  "document_ids": ["doc_123"],
  "stream": false
}
```

**Response**
```json
{
  "response": "RAG (Retrieval-Augmented Generation) combines...",
  "sources": [
    {
      "document_id": "doc_123",
      "text": "RAG systems use retrieval to find...",
      "page_number": 42
    }
  ],
  "generation_time_ms": 1245
}
```

### Chat
```http
POST /api/rag/chat
```
Interactive chat with document context.

**Request Headers**
```
Content-Type: application/json
Authorization: Bearer <jwt_token>
```

**Request Body**
```json
{
  "messages": [
    {"role": "user", "content": "What is RAG?"},
    {"role": "assistant", "content": "RAG is..."},
    {"role": "user", "content": "How does it work?"}
  ],
  "document_ids": ["doc_123"]
}
```

**Response**
```json
{
  "message": "RAG works by first retrieving...",
  "sources": [
    {
      "document_id": "doc_123",
      "text": "The retrieval component finds relevant...",
      "page_number": 42
    }
  ]
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request parameters"
}
```

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

### 404 Not Found
```json
{
  "detail": "Document not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```
