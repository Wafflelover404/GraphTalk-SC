#!/usr/bin/env python3
"""
Test script for WebSocket query endpoint
"""
import asyncio
import websockets
import json

# Configuration
SERVER_URL = "ws://localhost:9001"
TOKEN = "your_session_token_here"  # Replace with actual token

async def test_websocket_query():
    """Test WebSocket query endpoint"""
    uri = f"{SERVER_URL}/ws/query?token={TOKEN}"
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket")
            
            # Send a test query
            test_query = {
                "question": "What is the API documentation about?",
                "humanize": True,
                "session_id": "test_session_123"
            }
            
            print(f"\n→ Sending query: {test_query['question']}")
            await websocket.send(json.dumps(test_query))
            
            # Receive messages
            print("\n← Receiving responses:\n")
            message_count = 0
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    message_count += 1
                    
                    data = json.loads(message)
                    message_type = data.get("type", "unknown")
                    
                    print(f"  [{message_count}] Message type: {message_type}")
                    
                    if message_type == "status":
                        print(f"      Status: {data.get('message')}")
                    
                    elif message_type == "immediate":
                        files = data.get("data", {}).get("files", [])
                        snippets_count = len(data.get("data", {}).get("snippets", []))
                        print(f"      Files: {files}")
                        print(f"      Snippets: {snippets_count}")
                    
                    elif message_type == "overview":
                        overview = data.get("data", "")
                        print(f"      Overview length: {len(overview)} chars")
                        print(f"      Preview: {overview[:100]}...")
                    
                    elif message_type == "chunks":
                        chunks_count = len(data.get("data", {}).get("chunks", []))
                        print(f"      Chunks: {chunks_count}")
                    
                    elif message_type == "error":
                        print(f"      ✗ Error: {data.get('message')}")
                        break
                    
                    elif message_type == "complete":
                        response_time = data.get("response_time_ms", 0)
                        print(f"      ✓ Query completed in {response_time}ms")
                        break
                    
                except asyncio.TimeoutError:
                    print("\n  ✗ Timeout waiting for response")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("\n  ✓ Connection closed")
                    break
            
            print(f"\n✓ Test completed. Received {message_count} messages.")
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n✗ Connection failed: {e}")
        print("  Make sure:")
        print("  1. The server is running")
        print("  2. TOKEN is set correctly")
        print("  3. The user is authenticated")
    except Exception as e:
        print(f"\n✗ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Query Endpoint Test")
    print("=" * 60)
    print()
    print("Prerequisites:")
    print("  1. Server running at http://localhost:9001")
    print("  2. Valid session token set in TOKEN variable")
    print()
    print("=" * 60)
    print()
    
    asyncio.run(test_websocket_query())
