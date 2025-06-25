# socket-client.py - OSTIS Connection Testing Utility

## Overview
A simple utility script for testing connectivity to the OSTIS knowledge base server. This tool provides quick verification that the SC-machine instance is running and accessible via WebSocket.

## Key Features
- **Connection Testing**: Verifies OSTIS server availability
- **Simple Interface**: Minimal code for easy understanding
- **Clear Feedback**: Provides immediate connection status
- **Error Diagnosis**: Helps troubleshoot connection issues

## Script Functionality

### Connection Flow
1. **Establish Connection**: Attempts to connect to OSTIS server
2. **Status Check**: Verifies connection state
3. **Result Display**: Shows success or failure message
4. **Cleanup**: Automatically disconnects

### Code Structure
```python
from sc_client.client import connect, disconnect, is_connected

url = "ws://localhost:8090/ws_json"

connect(url)

if is_connected():
    print("Connected to the server !")
else:
    print("Failed to connect to the server. Check your sc machine instance and try again.")

disconnect()
```

## Usage Examples

### Basic Connection Test
```bash
python socket-client.py
```

**Expected Output (Success):**
```
Connected to the server !
```

**Expected Output (Failure):**
```
Failed to connect to the server. Check your sc machine instance and try again.
```

### Integration in Scripts
```python
# Use as a function in other modules
def test_ostis_connection():
    from sc_client.client import connect, disconnect, is_connected
    
    url = "ws://localhost:8090/ws_json"
    
    try:
        connect(url)
        connected = is_connected()
        disconnect()
        return connected
    except Exception:
        return False

# Use in application startup
if test_ostis_connection():
    start_application()
else:
    print("OSTIS server not available. Please start SC-machine.")
```

### Pre-deployment Validation
```python
# Health check script
def validate_system_dependencies():
    checks = {
        "OSTIS Connection": test_ostis_connection(),
        "Python Version": sys.version_info >= (3, 9),
        "Required Packages": check_package_availability()
    }
    
    for check, status in checks.items():
        print(f"{check}: {'✓' if status else '✗'}")
    
    return all(checks.values())
```

## Connection Details

### Server Configuration
- **URL**: `ws://localhost:8090/ws_json`
- **Protocol**: WebSocket with JSON messaging
- **Default Host**: localhost (127.0.0.1)
- **Default Port**: 8090
- **Endpoint**: `/ws_json`

### Network Requirements
- OSTIS SC-machine must be running
- Port 8090 must be accessible
- WebSocket protocol support required
- JSON message format support

## Troubleshooting Guide

### Common Connection Failures

#### Server Not Running
**Symptom**: "Failed to connect to the server"
**Solution**: 
```bash
# Start OSTIS SC-machine
cd /path/to/sc-machine
./scripts/start_server.sh
```

#### Port Blocked
**Symptom**: Connection timeout or refused
**Solution**:
```bash
# Check port availability
netstat -ln | grep 8090
# or
lsof -i :8090
```

#### Firewall Issues
**Symptom**: Connection timeout
**Solution**: Configure firewall to allow port 8090

#### Wrong URL
**Symptom**: Connection fails immediately
**Solution**: Verify URL format and server configuration

### Enhanced Diagnostic Version
```python
import socket
import time
from sc_client.client import connect, disconnect, is_connected

def detailed_connection_test():
    url = "ws://localhost:8090/ws_json"
    host = "localhost"
    port = 8090
    
    print("🔍 OSTIS Connection Diagnostics")
    print("=" * 40)
    
    # 1. Basic network connectivity
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        print("✓ Network connectivity: OK")
    except Exception as e:
        print(f"✗ Network connectivity: FAILED ({e})")
        return False
    
    # 2. WebSocket connection
    try:
        connect(url)
        if is_connected():
            print("✓ WebSocket connection: OK")
            print("✓ OSTIS server: RESPONDING")
            disconnect()
            return True
        else:
            print("✗ WebSocket connection: FAILED (connected but not responding)")
            disconnect()
            return False
    except Exception as e:
        print(f"✗ WebSocket connection: FAILED ({e})")
        return False

if __name__ == "__main__":
    detailed_connection_test()
```

## Integration Patterns

### Application Startup Validation
```python
# In api.py or main application
def startup_checks():
    print("Performing startup validation...")
    
    if not test_ostis_connection():
        print("❌ OSTIS server not available")
        print("Please ensure SC-machine is running at ws://localhost:8090/ws_json")
        sys.exit(1)
    
    print("✅ All systems ready")

if __name__ == "__main__":
    startup_checks()
    # Start application
```

### Health Check Endpoint
```python
# In api.py
@app.get("/health")
async def health_check():
    ostis_status = test_ostis_connection()
    
    return {
        "status": "healthy" if ostis_status else "unhealthy",
        "ostis_connection": ostis_status,
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Monitoring Integration
```python
# Continuous monitoring
import time
import logging

def monitor_ostis_connection(interval=60):
    """Monitor OSTIS connection every interval seconds"""
    logging.basicConfig(level=logging.INFO)
    
    while True:
        if test_ostis_connection():
            logging.info("OSTIS connection: OK")
        else:
            logging.warning("OSTIS connection: FAILED")
        
        time.sleep(interval)
```

## Configuration Variations

### Custom URL Testing
```python
def test_custom_ostis(host="localhost", port=8090, endpoint="/ws_json"):
    url = f"ws://{host}:{port}{endpoint}"
    
    try:
        connect(url)
        connected = is_connected()
        disconnect()
        return connected
    except Exception:
        return False

# Test different configurations
configs = [
    ("localhost", 8090, "/ws_json"),
    ("127.0.0.1", 8090, "/ws_json"),
    ("ostis-server", 8090, "/ws_json")
]

for host, port, endpoint in configs:
    status = test_custom_ostis(host, port, endpoint)
    print(f"{host}:{port}{endpoint} - {'✓' if status else '✗'}")
```

### Environment-based Configuration
```python
import os

def get_ostis_url():
    host = os.getenv("OSTIS_HOST", "localhost")
    port = os.getenv("OSTIS_PORT", "8090")
    endpoint = os.getenv("OSTIS_ENDPOINT", "/ws_json")
    
    return f"ws://{host}:{port}{endpoint}"

# Use environment variables
url = get_ostis_url()
connect(url)
```

## Best Practices

1. **Early Validation**: Test connection before starting main application
2. **Error Reporting**: Provide clear error messages for connection failures
3. **Retry Logic**: Implement retry mechanisms for transient failures
4. **Monitoring**: Include connection testing in health monitoring
5. **Configuration**: Make connection parameters configurable
6. **Timeout Handling**: Use appropriate timeouts for connection attempts
7. **Resource Cleanup**: Always disconnect after testing
8. **Logging**: Log connection status for operational monitoring

## Script Modifications

### Add Retry Logic
```python
import time

def test_connection_with_retry(max_retries=3, delay=2):
    url = "ws://localhost:8090/ws_json"
    
    for attempt in range(max_retries):
        try:
            connect(url)
            if is_connected():
                print(f"Connected to the server on attempt {attempt + 1}!")
                disconnect()
                return True
            disconnect()
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
        
        if attempt < max_retries - 1:
            time.sleep(delay)
    
    print("Failed to connect after all retries.")
    return False
```

### JSON Output for Automation
```python
import json

def connection_test_json():
    url = "ws://localhost:8090/ws_json"
    result = {
        "url": url,
        "connected": False,
        "timestamp": time.time(),
        "error": None
    }
    
    try:
        connect(url)
        result["connected"] = is_connected()
        disconnect()
    except Exception as e:
        result["error"] = str(e)
    
    print(json.dumps(result, indent=2))
    return result
```

This utility serves as a fundamental diagnostic tool for the GraphTalk system, ensuring that the OSTIS foundation is available before attempting more complex operations.
