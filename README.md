# GraphTalk
A comprehensive OSTIS knowledge base management and query system with REST API, LLM integration, and semantic processing capabilities.

## Overview
GraphTalk provides a secure, feature-rich interface for interacting with OSTIS knowledge bases through:
- **REST API**: Secure endpoints with bearer token authentication
- **Knowledge Base Search**: Multiple search algorithms for different use cases
- **LLM Integration**: AI-powered response generation and semantic parsing
- **File Management**: Upload and process knowledge base files
- **Semantic Processing**: Convert natural language to structured semantic representations

## Key Features
- 🔐 **Secure API**: Token-based authentication with bcrypt hashing
- 🔍 **Dual Search System**: Fast basic search and deep recursive exploration
- 🤖 **AI Integration**: GPT-4o-mini for humanized responses and JSON generation
- 📁 **File Processing**: Upload ZIP files containing SCS knowledge base files
- 🌐 **WebSocket Connection**: Direct integration with OSTIS SC-machine
- 📊 **Semantic Parsing**: Convert natural language to SC-Machine JSON format
- 📖 **Interactive Documentation**: Swagger UI with authentication

## Prerequisites
- Python 3.9+
- OSTIS SC-machine running locally (`ws://localhost:8090/ws_json`)
- Required Python packages (see requirements.txt)

## Installation
1. Clone the repository:
```bash
git clone https://github.com/Wafflelover404/GraphTalk
cd GraphTalk
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Verify OSTIS connection:
```bash
python socket-client.py
```
Expected output: "Connected to the server !"

## Quick Start

### 1. Start the API Server
```bash
python api.py
```
The API will be available at `http://localhost:9001`

### 2. Create Access Token (One-time setup)
```bash
curl -X POST http://localhost:9001/create_token
```
Save the returned token - it will only be shown once!

### 3. Query the Knowledge Base
```bash
# Basic search
curl -X POST http://localhost:9001/query \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "OSTIS technology"}'

# Humanized response with LLM
curl -X POST "http://localhost:9001/query?humanize=true" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "What is OSTIS?"}'
```

## API Endpoints

### Authentication
- **POST /create_token**: Generate access token (one-time only)
- **GET /**: API information and endpoint overview

### Core Operations
- **POST /query**: Search knowledge base with optional LLM humanization
  - Query parameter: `humanize=true` for AI-enhanced responses
- **POST /upload/kb_zip**: Upload ZIP files containing .scs knowledge base files
- **GET /docs**: Interactive API documentation (requires authentication)

## Module Overview

### Core API (`api.py`)
- FastAPI application with secure authentication
- File upload and processing capabilities
- Integration with search and LLM modules

### Search Modules
1. **Basic Search (`sc_search.py`)**:
   - Fast, non-recursive search
   - Substring-based matching
   - Returns keynodes and link content

2. **Advanced Search (`sc_search-total.py`)**:
   - Recursive knowledge graph traversal
   - Configurable depth exploration
   - Multi-directional relationship mapping
   - Structured nested results

### AI Integration
1. **Response Generation (`llm.py`)**:
   - Converts KB search results to natural language
   - Uses GPT-4o-mini for cost-effective processing
   - Context-aware response generation

2. **Semantic Parsing (`json-llm.py`)**:
   - Converts natural language to SC-Machine JSON format
   - Follows formal semantic specification
   - Supports Russian language processing

### Utilities
- **Knowledge Base Loader (`memloader.py`)**: Batch process SCS files
- **Connection Tester (`socket-client.py`)**: Verify OSTIS connectivity
- **JSON Standard (`json-prompt.md`)**: Semantic conversion specification

## Project Structure
```
GraphTalk/
├── api.py                    # Main FastAPI application
├── sc_search.py             # Basic KB search module
├── sc_search-total.py       # Advanced recursive search
├── llm.py                   # LLM response generation
├── json-llm.py             # Natural language to JSON conversion
├── memloader.py            # SCS file batch processor
├── socket-client.py        # OSTIS connection test utility
├── json-prompt.md          # SC-Machine JSON standard specification
├── requirements.txt        # Python dependencies
├── uploaded_kbs/           # Directory for uploaded files
├── unpacked_kbs/          # Temporary extraction directory
└── docs/                  # Comprehensive documentation
    ├── api.md
    ├── sc_search.md
    ├── sc_search-total.md
    ├── llm.md
    ├── json-llm.md
    ├── memloader.md
    ├── socket-client.md
    └── json-prompt.md
```

## Project Documentation

Documentation for individual components can be found in the `docs/` directory:

- [API Module](./docs/api.md): Documentation for `api.py`, detailing API endpoints and security features.
- [Basic Search Module](./docs/sc_search.md): Details on `sc_search.py` for quick non-recursive knowledge base search.
- [Advanced Search Module](./docs/sc_search-total.md): Details on `sc_search-total.py` for recursive knowledge base exploration.
- [LLM Integration](./docs/llm.md): Information on `llm.py` for language model integration and response generation.
- [JSON LLM Converter](./docs/json-llm.md): Guide for `json-llm.py` explaining JSON generation from text.
- [Knowledge Base Loader](./docs/memloader.md): Instructions for `memloader.py` to process SCS files.
- [Connection Testing Tool](./docs/socket-client.md): Details on `socket-client.py` for testing OSTIS connectivity.
- [SC-Machine JSON Standard](./docs/json-prompt.md): Specification details from `json-prompt.md` for semantic JSON conversion.
- [NLP JSON Interpretation & LLM Integration](docs/nlp_json_interpretation.md)

## Troubleshooting

### Connection Issues
- **OSTIS Server**: Verify OSTIS server is running at `ws://localhost:8090/ws_json`
- **Test Connection**: Run `python socket-client.py`
- **Expected Output**: "Connected to the server !"
- **Port Check**: Ensure port 8090 is not blocked by firewall

### Authentication Issues
- **Token Creation**: Only one token can be created per installation
- **Token Storage**: Token is stored in `~/secrets.toml`
- **Reset Token**: Delete `~/secrets.toml` to create a new token

### Search Issues
- **Empty Results**: Knowledge base may not contain relevant data
- **Search Terms**: Use specific terms that match KB content
- **Connection**: Verify OSTIS connection before searching

### LLM Issues
- **Internet Connection**: Required for GPT-4o-mini access
- **API Limits**: g4f client may have rate limits
- **Fallback**: API returns raw KB results if LLM fails

### File Upload Issues
- **File Format**: Only .zip files containing .scs files are accepted
- **Extraction**: Temporary files are stored in `unpacked_kbs/`
- **Permissions**: Ensure write permissions for upload directories

## Development

### Running Individual Modules
```bash
# Test OSTIS connection
python socket-client.py

# Test basic knowledge base search
python sc_search.py

# Test JSON conversion
python json-llm.py

# Test file loading
python memloader.py
```

### Environment Configuration
- **OSTIS URL**: Configurable in each module (default: `ws://localhost:8090/ws_json`)
- **API Port**: Configurable in `api.py` (default: 9001)
- **Upload Directories**: `uploaded_kbs/` and `unpacked_kbs/`

## License
This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Contributing
Contributions are welcome! Please consider:
- Adding new search algorithms
- Improving LLM integration
- Enhancing security features
- Writing additional documentation
- Adding test coverage
