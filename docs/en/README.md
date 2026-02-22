# GraphTalk

**[English](README.md)** | **Русский**

A comprehensive knowledge base management and query system for OSTIS with REST API, LLM integration, and semantic processing capabilities.

```mermaid

flowchart TD
    %% Clients Layer
    subgraph "Clients"
        StreamlitUI["Streamlit Web UI"]:::client
        TelegramUI["Telegram Bot UI"]:::client
        CLI["CLI (curl/Postman)"]:::client
    end

    %% API Layer
    subgraph "API Layer"
        APIGateway["API Gateway<br/>(api.py)"]:::api
        Auth["Auth Module"]:::api
        MetricsMW["Metrics Middleware"]:::api
    end

    %% Knowledge Base Modules
    subgraph "Knowledge Base Layer"
        SearchBasic["Basic Search<br/>(sc_search.py)"]:::api
        SearchAdv["Advanced Search<br/>(sc_search-total.py)"]:::api
        MemLoader["Memory Loader<br/>(memloader.py)"]:::api
        JSONInterp["JSON Interpreter<br/>(json_interpreter.py)"]:::api
    end

    %% LLM Modules
    subgraph "LLM Layer"
        LLMCore["LLM Core<br/>(llm.py)"]:::api
        LLMJson["LLM JSON Conv.<br/>(json_llm.py)"]:::api
    end

    %% RAG Microservice
    subgraph "RAG Microservice"
        RAG_Main["Main Server<br/>(rag_api/main.py)"]:::api
        ChromaUtil["Chroma Utils"]:::api
    end

    %% Data Stores
    subgraph "Data Stores"
        UserDB["User Tokens DB<br/>(userdb.py)"]:::db
        UploadsDB["Uploads DB<br/>(uploadsdb.py)"]:::db
        MetricsDB["Metrics DB<br/>(metricsdb.py)"]:::db
        ChromaDB["Chroma Store"]:::db
    end

    %% External Services
    subgraph "External Services"
        SCMachine["OSTIS SC-machine WS"]:::external
        LLMService["Google LLM / GPT-4o-mini"]:::external
    end

    %% Connections
    StreamlitUI -->|HTTP| APIGateway
    TelegramUI -->|HTTP| APIGateway
    CLI -->|HTTP| APIGateway

    APIGateway -->|WebSocket| SCMachine
    APIGateway -->|POST /query| SearchBasic
    APIGateway -->|calls| LLMCore
    APIGateway -->|metrics| MetricsMW

    %% Styles
    classDef api fill:#CFE2FF,stroke:#03396c,color:#03396c
    classDef db fill:#D5E8D4,stroke:#2E7D32,color:#2E7D32
    classDef external fill:#FFEAC8,stroke:#E65100,color:#E65100
    classDef client fill:#EAD1DC,stroke:#880E4F,color:#880E4F

```

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

### 4. Alternative UI Access Methods

#### Streamlit Web Interface
```bash
streamlit run ui/sc_machine_ui.py
```
Access at `http://localhost:8501`

#### Telegram Bot
```bash
python ui/tg_bot.py
```

## API Endpoints

### Authentication
- **POST /create_token**: Generate access token (one-time only)
- **GET /**: API information and endpoint overview

### Core Operations
- **POST /query**: Search knowledge base with optional LLM humanization
  - Query parameter: `humanize=true` for AI-enhanced responses
- **POST /upload/kb_zip**: Upload ZIP files containing .scs knowledge base files
- **POST /upload/kb_nlp_text**: Convert plain text to semantic JSON and load into SC-memory
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

### Data Processing
- **JSON Interpreter (`json_interpreter.py`)**: Loads semantic JSON data into SC-memory
- **Knowledge Base Loader (`memloader.py`)**: Batch process SCS files

### User Interfaces
1. **Streamlit UI (`ui/sc_machine_ui.py`)**:
   - Web-based graphical interface for API interaction
   - Token management and server connection testing

2. **Telegram Bot (`ui/tg_bot.py`)**:
   - Telegram bot interface for mobile/remote access
   - Interactive commands for all API operations

### Utilities
- **Connection Tester (`socket-client.py`)**: Verify OSTIS connectivity
- **JSON Standard (`json-prompt.md`)**: Semantic conversion specification

## Project Structure
```
GraphTalk/
├── api.py                    # Main FastAPI application
├── sc_search.py             # Basic KB search module
├── sc_search-total.py       # Advanced recursive search
├── llm.py                   # LLM response generation
├── json_llm.py             # Natural language to JSON conversion
├── json_interpreter.py     # JSON to SC-memory loader
├── memloader.py            # SCS file batch processor
├── socket-client.py        # OSTIS connection test utility
├── rag_api/                # RAG microservice
├── ui/                    # User interface modules
│   ├── sc_machine_ui.py   # Streamlit web interface
│   └── tg_bot.py          # Telegram bot interface
└── docs/                  # Comprehensive documentation
    ├── en/                # English documentation
    └── ru/                # Russian documentation
```

## Project Documentation

Documentation for individual components can be found in the `docs/` directory:

- [API Module](api.md): Documentation for `api.py`, detailing API endpoints and security features.
- [Basic Search Module](sc_search.md): Details on `sc_search.py` for quick non-recursive knowledge base search.
- [Advanced Search Module](sc_search-total.md): Details on `sc_search-total.py` for recursive knowledge base exploration.
- [LLM Integration](llm.md): Information on `llm.py` for language model integration and response generation.
- [JSON LLM Converter](json-llm.md): Guide for `json_llm.py` explaining JSON generation from text.
- [Knowledge Base Loader](memloader.md): Instructions for `memloader.py` to process SCS files.
- [SC-Machine JSON Standard](json-prompt.md): Specification details for semantic JSON conversion.
- [NLP JSON Interpretation & LLM Integration](nlp_json_interpretation.md)

## Troubleshooting

### Connection Issues
- Verify OSTIS server is running at `ws://localhost:8090/ws_json`
- Run `python socket-client.py` to test connection

### Authentication Issues
- Only one token can be created per installation
- Token is stored in `~/secrets.toml`
- Delete `~/secrets.toml` to create a new token

### Search Issues
- Knowledge base may not contain relevant data
- Use specific terms that match KB content
- Verify OSTIS connection before searching

### LLM Issues
- Internet connection required for GPT-4o-mini access
- g4f client may have rate limits
- API returns raw KB results if LLM fails

### File Upload Issues
- Only .zip files containing .scs files are accepted
- Temporary files are stored in `unpacked_kbs/`

## License
This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](../../LICENSE) file for details.

## Contributing
Contributions are welcome! Please consider:
- Adding new search algorithms
- Improving LLM integration
- Enhancing security features
- Writing additional documentation
- Adding test coverage
