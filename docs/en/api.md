# api.py - Main FastAPI Application

## Overview
The main FastAPI application that provides a secure REST API for interacting with OSTIS knowledge bases. This is the entry point for the GraphTalk system.

## Key Features
- **Token-based Authentication**: Secure API access using bearer tokens
- **Knowledge Base Querying**: Process natural language queries against OSTIS knowledge bases
- **RAG-based Search**: New feature to use a RAG model for querying.
- **File Upload Support**: Upload and process knowledge base zip files
- **LLM Integration**: Optional humanized responses using language models
- **WebSocket Streaming**: Real-time streaming responses with Deepseek LLM token-by-token output
- **Interactive Documentation**: Swagger UI with authentication

## Architecture
```
FastAPI Application
├── Authentication Layer (Bearer Token)
├── Query Processing (/query)
├── File Upload (/upload/kb_zip)
├── Token Management (/create_token)
└── Documentation (/docs)
└── RAG Integration
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
    - `use_rag`: Optional boolean to use the RAG model for the query
  - Returns structured search results or humanized responses

### WebSocket Streaming API
- **WebSocket /ws/query**: Real-time streaming RAG queries with token-based authentication
  - Query Parameter: `token` (optional) - Bearer token for authentication
  - Message Format (JSON):
    ```json
    {
      "question": "Your query here",
      "humanize": true,
      "stream": true,
      "ai_agent_mode": false,
      "session_id": "optional-session-id"
    }
    ```
  - Response Messages:
    - `status`: Processing status updates
    - `immediate`: Fast RAG results with files and snippets
    - `stream_start`: Indicates beginning of LLM streaming
    - `stream_token`: Individual tokens from Deepseek LLM (when stream=true)
    - `stream_end`: Indicates completion of LLM streaming
    - `overview`: Complete LLM-generated analysis (when stream=false)
    - `chunks`: Raw document chunks for non-humanized responses
    - `error`: Error messages

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
- **rag_api**: RAG model integration

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
- **rag_api**: Handles RAG-based search
- **llm.py**: Language model integration for humanized responses with Deepseek streaming support
- **memloader.py**: Knowledge base file processing
- **OSTIS Server**: WebSocket connection at `ws://localhost:8090`

## WebSocket Streaming Example
```javascript
// Connect to WebSocket with streaming enabled
const ws = new WebSocket('ws://localhost:9001/ws/query?token=YOUR_TOKEN');

ws.onopen = () => {
    // Send query with streaming enabled
    ws.send(JSON.stringify({
        question: "What is the architecture of this system?",
        humanize: true,
        stream: true,
        ai_agent_mode: false
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'status':
            console.log('Status:', data.message);
            break;
        case 'immediate':
            console.log('Immediate results:', data.data.files);
            break;
        case 'stream_start':
            console.log('Starting LLM streaming...');
            break;
        case 'stream_token':
            // Append tokens to display in real-time
            appendToResponse(data.token);
            break;
        case 'stream_end':
            console.log('Streaming completed');
            break;
        case 'error':
            console.error('Error:', data.message);
            break;
    }
};
```
