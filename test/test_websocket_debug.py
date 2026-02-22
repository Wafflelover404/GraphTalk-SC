#!/usr/bin/env python3
"""
Simple WebSocket test script to debug streaming
"""
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:9001/ws/query?token=95b7c6c2-dda0-4845-a6de-c75ba8e7ed57"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket")
            
            # Send a query with streaming enabled
            message = {
                "question": "test",
                "humanize": True,
                "stream": True,
                "session_id": "debug-test-123"
            }
            
            print(f"🚀 Sending message: {json.dumps(message, indent=2)}")
            await websocket.send(json.dumps(message))
            
            # Receive messages
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    data = json.loads(response)
                    print(f"📨 Received: {data['type']} - {data.get('message', '')[:50]}...")
                    
                    if data['type'] == 'stream_end':
                        print("✅ Streaming completed")
                        break
                    elif data['type'] == 'error':
                        print(f"❌ Error: {data.get('message', 'Unknown error')}")
                        break
                    elif data['type'] == 'overview':
                        print("✅ Received non-streaming overview")
                        break
                        
                except asyncio.TimeoutError:
                    print("⏰ Timeout waiting for response")
                    break
                    
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    print("🧪 Testing WebSocket streaming...")
    print("Make sure the server is running on localhost:9001")
    print()
    asyncio.run(test_websocket())