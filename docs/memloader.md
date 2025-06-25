# memloader.py - Knowledge Base File Loader

## Overview
Handles loading and processing of SCS (Semantic Computer Source) files into OSTIS knowledge bases. This module provides batch processing capabilities for knowledge base population from file systems.

## Key Features
- **Recursive File Discovery**: Finds all .scs files in directory trees
- **Batch Processing**: Loads multiple files efficiently
- **Error Reporting**: Detailed status reporting for each file
- **Connection Management**: Handles OSTIS server connections
- **UTF-8 Support**: Proper encoding handling for international content

## Core Function

### `load_scs_directory(directory_path)`
Recursively finds and loads all .scs files from a specified directory into the OSTIS knowledge base.

#### Parameters
- `directory_path` (str): Path to directory containing .scs files

#### Returns
- `str`: Detailed status report including:
  - Total files found
  - Successfully loaded files count
  - Failed files with error details
  - Overall processing summary

#### Processing Flow
1. **Connection Setup**: Connects to OSTIS server at `ws://localhost:8090/ws_json`
2. **File Discovery**: Recursively searches for `.scs` files using glob patterns
3. **Content Reading**: Reads file contents with UTF-8 encoding
4. **Batch Generation**: Uses `generate_elements_by_scs()` for efficient loading
5. **Status Tracking**: Monitors success/failure for each file
6. **Cleanup**: Automatically disconnects from server

## Implementation Details

### File Discovery Pattern
```python
scs_files = glob.glob(os.path.join(directory_path, "**/*.scs"), recursive=True)
```
- Uses recursive glob pattern `**/*.scs`
- Searches all subdirectories
- Filters for .scs extension only

### Batch Processing Strategy
```python
scs_contents = []
for file_path in scs_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        scs_contents.append(f.read())

results = generate_elements_by_scs(scs_contents)
```

### Error Handling Levels
1. **File Read Errors**: Individual file access problems
2. **SCS Generation Errors**: Knowledge base loading failures
3. **Connection Errors**: OSTIS server communication issues

## Usage Examples

### Basic Directory Loading
```python
from memloader import load_scs_directory

# Load all .scs files from knowledge base directory
status = load_scs_directory("./knowledge_bases/medical_kb/")
print(status)
```

### Example Output
```
Total .scs files found: 15
Successfully loaded: 12 file(s)
Failed to load: 3 file(s)
  ❌ Failed to load: ./kb/broken_syntax.scs
  ❌ Error reading ./kb/locked_file.scs: Permission denied
  ❌ Failed to load: ./kb/invalid_format.scs
```

### Integration with API Upload
```python
# In api.py upload endpoint
@app.post("/upload/kb_zip")
async def upload_knowledge_base(file: UploadFile = File(...)):
    # ... extraction logic ...
    
    # Load extracted files
    await run_in_threadpool(load_scs_directory, extract_dir)
    
    return APIResponse(status="success", message="KB processed")
```

### Custom Processing with Error Handling
```python
def safe_kb_loading(directory):
    try:
        result = load_scs_directory(directory)
        
        # Parse result for success rate
        lines = result.split('\n')
        success_line = [l for l in lines if 'Successfully loaded:' in l][0]
        success_count = int(success_line.split(':')[1].strip().split()[0])
        
        return success_count > 0
    except Exception as e:
        print(f"Loading failed: {e}")
        return False
```

## Status Report Format

### Success Case
```
Total .scs files found: 8
Successfully loaded: 8 file(s)
Failed to load: 0 file(s)
```

### Mixed Results Case
```
Total .scs files found: 10
Failed to read 2 file(s):
  ❌ Error reading ./kb/corrupted.scs: UnicodeDecodeError
  ❌ Error reading ./kb/missing.scs: FileNotFoundError
Successfully loaded: 6 file(s)
Failed to load: 2 file(s)
  ❌ Failed to load: ./kb/syntax_error.scs
  ❌ Failed to load: ./kb/invalid_semantics.scs
```

### Error Categories

#### File Read Errors
- **Permission Issues**: File access denied
- **Encoding Problems**: Non-UTF-8 encoded files
- **Missing Files**: Broken symlinks or moved files
- **Disk Issues**: I/O errors during read

#### SCS Generation Errors
- **Syntax Errors**: Invalid SCS syntax
- **Semantic Errors**: Invalid knowledge representation
- **Server Errors**: OSTIS processing failures
- **Memory Issues**: Large file processing problems

## Directory Structure Handling

### Typical KB Directory Structure
```
knowledge_base/
├── core/
│   ├── concepts.scs
│   ├── relations.scs
│   └── axioms.scs
├── domain/
│   ├── medical_terms.scs
│   ├── procedures.scs
│   └── diseases.scs
└── instances/
    ├── patients.scs
    └── cases.scs
```

### Processing Order
- Files are processed in the order returned by glob.glob()
- No specific ordering guarantees
- Dependencies between files should be designed to be order-independent

## Connection Management

### OSTIS Server Configuration
- **URL**: `ws://localhost:8090/ws_json`
- **Protocol**: WebSocket JSON
- **Auto-connection**: Establishes connection automatically
- **Auto-cleanup**: Disconnects in finally block

### Connection Error Handling
```python
try:
    connect("ws://localhost:8090/ws_json")
    # ... file processing ...
except Exception as e:
    return f"Fatal error occurred: {str(e)}"
finally:
    disconnect()
```

## Performance Considerations

### Memory Usage
- All file contents loaded into memory simultaneously
- Large directories may require significant RAM
- Consider chunking for very large knowledge bases

### Processing Speed
- Batch processing is more efficient than individual file loading
- Network latency affects performance
- File I/O speed depends on storage type

### Optimization Strategies
```python
# For large directories, consider chunked processing
def chunked_directory_loading(directory, chunk_size=10):
    scs_files = glob.glob(os.path.join(directory, "**/*.scs"), recursive=True)
    
    for i in range(0, len(scs_files), chunk_size):
        chunk = scs_files[i:i + chunk_size]
        # Process chunk...
```

## Integration Points

### With API File Upload
```python
# api.py integration
extract_dir = os.path.join(KB_BASE_DIR, f"kb_{uuid.uuid4().hex}")
# ... file extraction ...
await run_in_threadpool(load_scs_directory, extract_dir)
```

### With Knowledge Base Management
```python
# KB management system
def update_knowledge_base(kb_id, new_files_dir):
    status = load_scs_directory(new_files_dir)
    
    # Log status to KB management system
    log_kb_update(kb_id, status)
    
    return parse_success_status(status)
```

### Standalone Usage
```python
# Direct command-line usage
if __name__ == "__main__":
    status_string = load_scs_directory("./unpacked_kbs/")
    print(status_string)
```

## Error Recovery Strategies

### Partial Success Handling
```python
def extract_success_count(status_report):
    """Extract number of successfully loaded files from status report"""
    for line in status_report.split('\n'):
        if 'Successfully loaded:' in line:
            return int(line.split(':')[1].strip().split()[0])
    return 0

# Use for partial success scenarios
success_count = extract_success_count(status)
if success_count > 0:
    print(f"Partial success: {success_count} files loaded")
```

### Retry Mechanisms
```python
def robust_directory_loading(directory, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = load_scs_directory(directory)
            if "Fatal error" not in result:
                return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Exponential backoff
```

## Best Practices

1. **Directory Validation**: Ensure directory exists before processing
2. **Permission Checks**: Verify read permissions on target directory
3. **Encoding Consistency**: Use UTF-8 encoding for all .scs files
4. **Error Monitoring**: Parse status reports for error detection
5. **Batch Size Management**: Consider memory limits for large directories
6. **Connection Stability**: Ensure OSTIS server is stable before large loads
7. **Backup Strategy**: Backup knowledge base before loading new content
8. **Status Logging**: Log status reports for audit trails
