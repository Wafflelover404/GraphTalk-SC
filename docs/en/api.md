# api.py - Main FastAPI Application

## Overview
The main FastAPI application that provides a secure REST API for interacting with OSTIS knowledge bases. This is the entry point for the GraphTalk system.

## Key Features
- **Token-based Authentication**: Secure API access using bearer tokens
- **Knowledge Base Querying**: Process natural language queries against OSTIS knowledge bases
- **File Upload Support**: Upload and process knowledge base zip files
- **LLM Integration**: Optional humanized responses using language models
- **Interactive Documentation**: Swagger UI with authentication

## Architecture
```
FastAPI Application
├── Authentication Layer (Bearer Token)
├── Query Processing (/query)
├── File Upload (/upload/kb_zip)
├── Token Management (/create_token)
└── Documentation (/docs)
```

## Endpoints

### Authentication
- **POST /create_token**: Generate a new access token (one-time only)
  - Returns a secure token for API access
  - Only allows one token creation per installation

### Core Operations
- **POST /query**: Process knowledge base queries
  - Parameters:
    - `text`: The query string
    - `humanize`: Optional boolean to get LLM-enhanced responses
  - Returns structured search results or humanized responses

- **POST /upload/kb_zip**: Upload knowledge base files
  - Accepts ZIP files containing .scs (Semantic Computer Source) files
  - Extracts and loads into the OSTIS system
  - Returns processing status

### Documentation
- **GET /docs**: Interactive API documentation (requires authentication)
- **GET /**: Landing page with endpoint overview

## Security Features
- **Single Token System**: Only one access token can be created
- **bcrypt Hashing**: Secure token storage using bcrypt with 12 rounds
- **Token Verification**: All protected endpoints require valid bearer token
- **File Validation**: Upload restrictions to .zip files only

## Configuration
- **Upload Directory**: `uploaded_kbs/` - Stores uploaded files
- **KB Base Directory**: `unpacked_kbs/` - Temporary extraction location
- **Secrets Path**: `~/secrets.toml` - Token storage location
- **Default Port**: 9001 (when run directly)

## Dependencies
- **FastAPI**: Web framework
- **uvicorn**: ASGI server
- **bcrypt**: Password/token hashing
- **toml**: Configuration file handling
- **sc_search**: Knowledge base search functionality

## Usage Example
```python
# Start the server
uvicorn api:app --host 0.0.0.0 --port 9001

# Create token (first time only)
curl -X POST http://localhost:9001/create_token

# Query with token
curl -X POST http://localhost:9001/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "What is OSTIS?"}'
```

## Error Handling
- Comprehensive exception handling for all endpoints
- Structured error responses with status and message fields
- Logging of critical errors for debugging
- Graceful handling of OSTIS connection failures

## Integration Points
- **sc_search.py**: Core search functionality
- **llm.py**: Language model integration for humanized responses
- **memloader.py**: Knowledge base file processing
- **OSTIS Server**: WebSocket connection at `ws://localhost:8090`
