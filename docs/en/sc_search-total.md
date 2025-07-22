# sc_search-total.py - Advanced Recursive Knowledge Base Search

## Overview
Provides comprehensive, recursive search functionality for OSTIS knowledge bases with configurable depth traversal. This module implements advanced knowledge graph exploration with relationship mapping.

## Key Features
- **Recursive Traversal**: Configurable depth exploration of knowledge graph connections
- **Multi-directional Search**: Explores child, parent, and adjacent relationships
- **Structured Results**: Returns nested dictionary structures representing knowledge graph
- **Element Type Detection**: Distinguishes between nodes, links, and connectors
- **Cycle Prevention**: Prevents infinite loops using visited node tracking

## Core Functions

### `kb_search(search_string, max_depth=2)`
Performs comprehensive knowledge base search with recursive connection traversal.

#### Parameters
- `search_string` (str): Search query string
- `max_depth` (int): Maximum depth for recursive traversal (default: 2)

#### Returns
- `list`: List of nested dictionaries with structure:
```python
[
  {
    "element": {
      "address": "ScAddr_value",
      "type": "Keynode|Link Content|Node|Connector",
      "value": "human_readable_content"
    },
    "connections": {
      "child": [...],    # Outgoing connections
      "parent": [...],   # Incoming connections  
      "adjacent": [...]  # Bidirectional connections
    }
  }
]
```

### `decode_sc_element(addr: ScAddr)`
Converts SC-machine addresses to human-readable information with proper type detection.

#### Parameters
- `addr` (ScAddr): SC-machine address to decode

#### Returns
- `dict`: Element information with address, type, and value

### `traverse_connections(start_addr, max_depth, visited, direction, current_depth=1)`
Recursively traverses knowledge graph connections in specified directions.

#### Parameters
- `start_addr` (ScAddr): Starting element address
- `max_depth` (int): Maximum traversal depth
- `visited` (set): Set of visited addresses (cycle prevention)
- `direction` (str): "child", "parent", or "adjacent"
- `current_depth` (int): Current traversal depth

## Search Directions

### Child Connections (Outgoing)
```
Template: start_addr --arc--> target
```
Finds elements that the starting element points to.

### Parent Connections (Incoming)
```
Template: source --arc--> start_addr
```
Finds elements that point to the starting element.

### Adjacent Connections (Bidirectional)
```
Template: start_addr --arc--> target OR source --arc--> start_addr
```
Finds all directly connected elements regardless of direction.

## Algorithm Flow

```
1. Initial Search
   ├── Split search string into terms
   ├── Use search_links_by_contents_substrings()
   └── Deduplicate found addresses

2. For Each Result Address
   ├── Decode element information
   ├── Traverse child connections (recursive)
   ├── Traverse parent connections (recursive)
   ├── Traverse adjacent connections (recursive)
   └── Build nested result structure

3. Recursive Traversal
   ├── Check depth limit and visited set
   ├── Create SC template for direction
   ├── Execute template search
   ├── Decode found elements
   ├── Recursively traverse deeper levels
   └── Return structured connections
```

## Element Types

### Keynodes
- System-identified nodes with semantic identifiers
- Example: `{"type": "Keynode", "value": "ostis_technology"}`

### Link Content
- Links containing actual data/content
- Example: `{"type": "Link Content", "value": "OSTIS documentation text"}`

### Nodes
- Generic nodes without system identifiers
- Example: `{"type": "Node", "value": "Node_12345"}`

### Connectors
- Relationship connectors between elements
- Example: `{"type": "Connector", "value": "Connector_67890"}`

## Configuration

### Connection Settings
- **URL**: `ws://localhost:8090/ws_json`
- **Default Max Depth**: 2 levels
- **Visited Tracking**: Prevents cycles in graph traversal

### Template Types
- **VAR_PERM_POS_ARC**: Variable permanent positive arc
- **VAR_NODE**: Variable node for template matching

## Usage Examples

### Basic Recursive Search
```python
from sc_search_total import kb_search, print_results

# Connect to OSTIS
connect("ws://localhost:8090/ws_json")

# Perform deep search
results = kb_search("OSTIS technology", max_depth=3)

# Print structured results
print_results(results)

# Disconnect
disconnect()
```

### Custom Depth Search
```python
# Shallow search (depth 1)
shallow_results = kb_search("AI", max_depth=1)

# Deep search (depth 4)
deep_results = kb_search("semantic networks", max_depth=4)
```

### Manual Connection Traversal
```python
from sc_search_total import traverse_connections, decode_sc_element

# Get element details
element_info = decode_sc_element(some_address)

# Explore only child connections
children = traverse_connections(
    some_address, 
    max_depth=2, 
    visited=set(), 
    direction="child"
)
```

## Output Format Example

```python
[
  {
    "element": {
      "address": "ScAddr(12345)",
      "type": "Keynode", 
      "value": "ostis_technology"
    },
    "connections": {
      "child": [
        {
          "element": {
            "address": "ScAddr(67890)",
            "type": "Link Content",
            "value": "OSTIS is a technology for building intelligent systems"
          },
          "depth": 2,
          "connections": [...]
        }
      ],
      "parent": [...],
      "adjacent": [...]
    }
  }
]
```

## Performance Considerations

### Memory Usage
- Grows exponentially with depth
- Large knowledge bases can consume significant memory
- Visited set prevents cycles but increases memory usage

### Execution Time
- Increases significantly with depth and graph density
- Network latency affects performance
- Consider depth limits for production use

### Optimization Tips
1. **Limit Depth**: Use minimal necessary depth (1-3 typically sufficient)
2. **Specific Queries**: More specific search terms reduce result set
3. **Connection Filtering**: Focus on specific connection directions
4. **Batch Processing**: Process large result sets in chunks

## Error Handling

### Connection Errors
```python
try:
    connect(url)
    if is_connected():
        results = kb_search("query")
    else:
        print("Connection failed")
except Exception as e:
    print(f"Error: {e}")
finally:
    disconnect()
```

### Template Search Failures
- Graceful handling of invalid templates
- Empty result handling
- Type checking for SC addresses

## Integration Points

### With API
```python
# In api.py for complex queries
from sc_search_total import kb_search as complex_search

# Use for detailed analysis
complex_results = complex_search(query, max_depth=2)
```

### With Basic Search
```python
# Combine approaches
basic_results = kb_search(query)          # Fast overview
detailed_results = complex_search(query)   # Deep analysis
```

## Best Practices

1. **Depth Management**: Start with depth 1-2, increase as needed
2. **Result Processing**: Use provided print functions for debugging
3. **Connection Strategy**: Choose appropriate direction based on use case
4. **Memory Monitoring**: Monitor memory usage with large graphs
5. **Error Recovery**: Implement proper connection cleanup
6. **Query Optimization**: Use specific search terms to reduce initial result set
