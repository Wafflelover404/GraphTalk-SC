# sc_search.py - Basic Knowledge Base Search

## Overview
Provides quick, non-recursive search functionality for OSTIS knowledge bases. This module implements efficient substring-based searching with automatic element decoding. This is one of two search methods available, the other being a RAG-based approach.

## Key Features
- **Fast Search**: Quick substring-based search through knowledge base links
- **Automatic Decoding**: Converts SC-machine addresses to human-readable content
- **Connection Management**: Handles WebSocket connections to OSTIS server
- **Error Handling**: Robust error handling with informative messages

## Core Function

### `kb_search(search_string)`
Performs a quick search through the knowledge base using the provided query string.

#### Parameters
- `search_string` (str): The search query to look for in the knowledge base

#### Returns
- `list`: A list of strings containing search results, where each result can be:
  - `"Keynode: {identifier}"` - System-identified nodes
  - `"Link Content: {content}"` - Content from knowledge base links
  - `"Unknown Element: {address}"` - Unresolved elements
  - `"Error during search: {error}"` - Error messages

#### Algorithm
1. **Connection Setup**: Establishes WebSocket connection to OSTIS server (`ws://localhost:8090/ws_json`)
2. **Context Creation**: Creates a search context link with the query string
3. **Term Splitting**: Splits the search string into individual terms
4. **Link Search**: Uses `search_links_by_contents_substrings()` to find matching links
5. **Result Processing**: Decodes each found address using:
   - `get_element_system_identifier()` for keynodes
   - `get_link_content_data()` for link content
6. **Cleanup**: Automatically disconnects from the server

## Search Strategy
```
Input Query → Split Terms → Search Links → Decode Results → Return List
     ↓            ↓           ↓            ↓              ↓
  "OSTIS AI" → ["OSTIS", "AI"] → [addr1, addr2] → ["Keynode: OSTIS", "Link Content: AI"] → Results
```

## Connection Details
- **URL**: `ws://localhost:8090/ws_json`
- **Protocol**: WebSocket JSON protocol
- **Auto-disconnect**: Connection is automatically closed after search

## Dependencies
- **sc_client**: OSTIS Python client library
  - `connect`, `disconnect`, `is_connected`
  - `search_links_by_contents_substrings`
  - `generate_elements`
- **sc_kpm.utils**: Knowledge processing utilities
  - `get_element_system_identifier`
  - `get_link_content_data`

## Usage Examples

### Basic Search
```python
from sc_search import kb_search

# Search for OSTIS-related content
results = kb_search("OSTIS technology")
for result in results:
    print(result)
# Output:
# Keynode: ostis_technology
# Link Content: OSTIS is a technology for building knowledge bases
```

### Multiple Terms
```python
# Search with multiple keywords
results = kb_search("semantic networks AI")
# Searches for content containing "semantic", "networks", or "AI"
```

### Error Handling
```python
results = kb_search("test query")
if results and "Error during search:" in results[0]:
    print("Search failed:", results[0])
else:
    print(f"Found {len(results)} results")
```

## Performance Characteristics
- **Speed**: Fast execution due to non-recursive nature
- **Memory**: Minimal memory usage, no caching
- **Scalability**: Performance depends on knowledge base size
- **Connection**: New connection per search (stateless)

## Error Scenarios
1. **Connection Failure**: Returns `["Not connected to SC-machine"]`
2. **Server Unreachable**: Returns `["Error during search: connection error"]`
3. **Invalid Query**: Handles gracefully, may return empty results
4. **Server Timeout**: Automatic timeout and error reporting

## Integration with API
Used by `api.py` in the `/query` endpoint:
```python
# In api.py
from sc_search import kb_search

@app.post("/query")
async def process_query(request: QueryRequest, humanize: bool = False):
    kb_results = kb_search(request.text)
    # ... process results
```

## Comparison with sc_search-total.py
| Feature | sc_search.py | sc_search-total.py |
|---------|----------------|----------------------|
| Speed | Fast | Slower |
| Depth | Single level | Recursive (configurable) |
| Memory | Low usage | Higher usage |
| Complexity | Simple | Complex relationships |
| Use Case | Quick search | Deep analysis |

## Comparison with RAG Search
| Feature | sc_search.py | RAG Search |
|---|---|---|
| Technology | Substring search on SC-machine links | Vector-based search with LLM | 
| Search Type | Exact match, keyword-based | Semantic, context-aware | 
| Data Source | Structured knowledge base in OSTIS | Indexed documents (e.g., Markdown, PDF) | 
| Use Case | Finding specific keynodes or links | Answering complex questions, summarization |

## Best Practices
1. **Query Design**: Use specific terms for better results
2. **Error Checking**: Always check for error messages in results
3. **Connection**: Ensure OSTIS server is running before search
4. **Term Selection**: Avoid overly generic terms that may flood results
