```markdown
# OpenNIKA-API

A standalone API service for interacting with the [NIKA knowledge base](https://github.com/ostis-apps/nika) using OSTIS technology.

## Features
- REST API endpoints for knowledge base queries
- Simple keyword-based search
- Complex reasoning with LLM integration
- Connection to OSTIS knowledge bases via WebSocket
- Recursive knowledge graph traversal
- Automatic element decoding (keynodes, links, connectors)

## Prerequisites
- Python 3.9+
- OSTIS Knowledge Base running locally (`ws://localhost:8090`)
- [SC-server](https://github.com/ostis-dev/sc-server) running

## Installation
1. Clone the repository:
```bash
git clone https://github.com/yourusername/OpenNIKA-API.git
cd OpenNIKA-API
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the API
```bash
uvicorn api:app --host 0.0.0.0 --port 8080
```
The API will be available at `http://localhost:8080`

## API Endpoints

### 1. Simple Search (`/resp/simple`)
- **Method**: POST
- **Input**: 
  ```json
  {"text": "your search query"}
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "message": "Request processed",
    "response": ["Keynode: example", "Link Content: example"]
  }
  ```

### 2. Complex Reasoning (`/resp/complex`)
- **Method**: POST
- **Input**: 
  ```json
  {"text": "your complex question"}
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "message": "Complex request processed",
    "response": "LLM-generated answer based on KB data"
  }
  ```

## Search Modules
1. `nika_search.py` - Basic search:
   - Simple keyword matching
   - Returns keynodes and link contents
   - Fast response time

2. `nika_search-total.py` - Advanced search:
   - Recursive traversal (configurable depth)
   - Relationship mapping (parent/child/adjacent)
   - Full element decoding
   - Returns structured knowledge graph

## Project Structure
```
OpenNIKA-API/
├── api.py               # Main API application (FastAPI)
├── llm.py               # LLM integration module
├── nika_search.py       # Simple KB search implementation
├── nika_search-total.py # Advanced KB traversal implementation
├── socket-client.py     # OSTIS connection test script
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```

## Troubleshooting
1. **Connection issues**:
   - Verify OSTIS server is running: `ws://localhost:8090`
   - Test connection: `python socket-client.py`
   - Expected output: `"Connected to the server!"`

2. **Empty responses**:
   - Ensure knowledge base contains relevant data
   - Check search terms match KB identifiers
   - Increase max_depth in `nika_search-total.py` for deeper traversal

3. **LLM errors**:
   - Verify internet connection
   - Check GPT-4 API availability
   - Review `llm.py` for model compatibility

## Example Requests
```bash
# Simple search
curl -X POST http://localhost:8080/resp/simple \
  -H "Content-Type: application/json" \
  -d '{"text":"Когда защита первой лабы?"}'

# Complex reasoning
curl -X POST http://localhost:8080/resp/complex \
  -H "Content-Type: application/json" \
  -d '{"text":"Объясни тему семантических сетей"}'
```

## Contribution
Contributions are welcome! Please open an issue or PR for:
- New knowledge base connectors
- Additional LLM providers
- Performance improvements
- Documentation enhancements
```
