# RAG API Documentation

## Overview
The RAG (Retrieval-Augmented Generation) API provides a powerful interface for document retrieval and generation using vector embeddings and large language models. This documentation covers the setup, usage, and integration of the RAG API.

## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Authentication](#authentication)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Features
- Document indexing and vectorization
- Semantic search capabilities
- Integration with multiple LLM providers
- Support for various document formats (PDF, DOCX, TXT, HTML, MD)
- Asynchronous processing
- Secure authentication and authorization

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Start the API server
python -m uvicorn rag_api.main:app --reload
```

## API Endpoints
### Document Management
- `POST /api/rag/documents` - Upload and index a new document
- `GET /api/rag/documents` - List all indexed documents
- `GET /api/rag/documents/{doc_id}` - Get document details
- `DELETE /api/rag/documents/{doc_id}` - Remove a document

### Search & Generation
- `POST /api/rag/search` - Semantic search across documents
- `POST /api/rag/generate` - Generate responses using RAG
- `POST /api/rag/chat` - Interactive chat with document context

## Configuration
Configuration is done through environment variables:
```
# Required
DATABASE_URL=sqlite:///rag_app.db

# Optional - for LLM-powered responses
DEEPSEEK_API_KEY=your_deepseek_api_key

# Optional
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
CHUNK_SIZE=1500
CHUNK_OVERLAP=300
```

## Authentication
All endpoints require authentication using JWT tokens. Include the token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

## Examples
### Search Example
```python
import requests

url = "http://localhost:8000/api/rag/search"
headers = {
    "Authorization": "Bearer your_jwt_token",
    "Content-Type": "application/json"
}
data = {
    "query": "What is the capital of France?",
    "top_k": 3
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Generate Response Example
```python
import requests

url = "http://localhost:8000/api/rag/generate"
headers = {
    "Authorization": "Bearer your_jwt_token",
    "Content-Type": "application/json"
}
data = {
    "query": "Explain the main concepts of RAG",
    "max_tokens": 500
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

## Troubleshooting
### Common Issues
1. **Document not found**
   - Ensure the document was successfully uploaded and indexed
   - Check the logs for any indexing errors

2. **Authentication failed**
   - Verify your JWT token is valid and not expired
   - Check the Authorization header format

3. **Slow responses**
   - Consider increasing server resources
   - Check if embedding model is properly loaded

### Getting Help
For additional support, please open an issue on our [GitHub repository](https://github.com/yourusername/graphtalk-sc/issues).
