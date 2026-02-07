#!/usr/bin/env python3
"""
Restart the WikiAI API server with WebSocket support
"""
import subprocess
import sys
import time
import requests

def stop_server():
    """Try to stop any existing server on port 9001"""
    try:
        # Try to make a request to see if server is running
        response = requests.get('http://127.0.0.1:9001/', timeout=2)
        print("📡 Server is running, attempting to stop...")
        # Note: In a real scenario, you'd use process management
        print("⚠️  Please manually stop the server (Ctrl+C) and restart it")
        return True
    except:
        print("✅ No server running on port 9001")
        return False

def start_server():
    """Start the API server"""
    print("🚀 Starting WikiAI API server...")
    try:
        # Use the start script we created
        result = subprocess.run([
            sys.executable, 'start_api_server.py'
        ], cwd='.')
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        return True
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False

def main():
    print("🔄 WikiAI API Server Restart Utility")
    print("=" * 40)
    
    # Check if server is running
    server_running = stop_server()
    
    if server_running:
        input("Press Enter after stopping the current server...")
    
    # Start the server
    print("\n" + "=" * 40)
    success = start_server()
    
    if success:
        print("✅ Server restart completed")
    else:
        print("❌ Server restart failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
