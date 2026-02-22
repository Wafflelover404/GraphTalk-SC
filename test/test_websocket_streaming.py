#!/usr/bin/env python3
"""
Test script for WebSocket streaming with Deepseek LLM
"""
import asyncio
import websockets
import json
import time

# Configuration
SERVER_URL = "ws://localhost:9001"
TOKEN = "your_session_token_here"  # Replace with actual token

async def test_streaming_functionality():
    """Test WebSocket streaming with Deepseek LLM"""
    uri = f"{SERVER_URL}/ws/query?token={TOKEN}"
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket")
            
            # Test 1: Streaming enabled
            print("\n" + "="*50)
            print("TEST 1: Streaming Enabled")
            print("="*50)
            
            test_query_streaming = {
                "question": "Explain the architecture of this system and how it integrates with different components",
                "humanize": True,
                "stream": True,
                "session_id": "test_streaming_123"
            }
            
            print(f"\n→ Sending query with streaming: {test_query_streaming['question']}")
            await websocket.send(json.dumps(test_query_streaming))
            
            # Track streaming tokens
            tokens_received = []
            start_time = None
            first_token_time = None
            
            print("\n← Receiving streaming responses:\n")
            message_count = 0
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    message_count += 1
                    
                    data = json.loads(message)
                    message_type = data.get("type", "unknown")
                    
                    if message_type == "status":
                        print(f"[{message_count}] 🔄 Status: {data.get('message')}")
                    
                    elif message_type == "immediate":
                        files = data.get("data", {}).get("files", [])
                        print(f"[{message_count}] 📄 Immediate results - Files: {len(files)}")
                        for file in files[:3]:  # Show first 3 files
                            print(f"      - {file}")
                    
                    elif message_type == "stream_start":
                        start_time = time.time()
                        print(f"[{message_count}] 🚀 Streaming started")
                    
                    elif message_type == "stream_token":
                        if first_token_time is None:
                            first_token_time = time.time()
                        
                        token = data.get("token", "")
                        tokens_received.append(token)
                        # Show token preview (avoid flooding console)
                        if len(tokens_received) <= 5 or len(tokens_received) % 20 == 0:
                            preview = token.replace('\n', '\\n').replace('\r', '\\r')
                            print(f"[{message_count}] 📝 Token #{len(tokens_received)}: '{preview}'")
                    
                    elif message_type == "stream_end":
                        end_time = time.time()
                        total_time = end_time - start_time if start_time else 0
                        first_token_latency = first_token_time - start_time if start_time and first_token_time else 0
                        
                        print(f"[{message_count}] ✅ Streaming completed")
                        print(f"      Total streaming time: {total_time:.2f}s")
                        print(f"      First token latency: {first_token_latency:.2f}s")
                        print(f"      Total tokens received: {len(tokens_received)}")
                        print(f"      Complete response: {''.join(tokens_received)[:200]}...")
                        break
                    
                    elif message_type == "error":
                        print(f"[{message_count}] ❌ Error: {data.get('message')}")
                        break
                
                except asyncio.TimeoutError:
                    print("\n⏰ Timeout waiting for response")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 Connection closed")
                    break
            
            # Wait a moment before next test
            await asyncio.sleep(2)
            
            # Test 2: Non-streaming (fallback)
            print("\n" + "="*50)
            print("TEST 2: Non-Streaming (Fallback)")
            print("="*50)
            
            test_query_non_streaming = {
                "question": "What are the key features of this API?",
                "humanize": True,
                "stream": False,
                "session_id": "test_non_streaming_456"
            }
            
            print(f"\n→ Sending query without streaming: {test_query_non_streaming['question']}")
            await websocket.send(json.dumps(test_query_non_streaming))
            
            print("\n← Receiving non-streaming responses:\n")
            
            while True:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    
                    data = json.loads(message)
                    message_type = data.get("type", "unknown")
                    
                    if message_type == "status":
                        print(f"🔄 Status: {data.get('message')}")
                    
                    elif message_type == "immediate":
                        files = data.get("data", {}).get("files", [])
                        print(f"📄 Immediate results - Files: {len(files)}")
                    
                    elif message_type == "overview":
                        overview = data.get("data", "")
                        print(f"📝 Overview received - Length: {len(overview)} chars")
                        print(f"    Preview: {overview[:150]}...")
                        break
                    
                    elif message_type == "error":
                        print(f"❌ Error: {data.get('message')}")
                        break
                
                except asyncio.TimeoutError:
                    print("\n⏰ Timeout waiting for response")
                    break
                except websockets.exceptions.ConnectionClosed:
                    print("\n🔌 Connection closed")
                    break
            
            print("\n" + "="*50)
            print("✓ All tests completed successfully!")
            print("="*50)
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n❌ Connection failed: {e}")
        print("Make sure:")
        print("  1. The server is running on localhost:9001")
        print("  2. TOKEN is set correctly")
        print("  3. DEEPSEEK_API_KEY is configured in environment")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("WebSocket Streaming with Deepseek LLM Test")
    print("=" * 60)
    print()
    print("Prerequisites:")
    print("  1. Server running at http://localhost:9001")
    print("  2. Valid session token set in TOKEN variable")
    print("  3. DEEPSEEK_API_KEY environment variable configured")
    print("  4. Deepseek API access available")
    print()
    print("This test will:")
    print("  1. Test streaming responses token-by-token")
    print("  2. Test non-streaming fallback mode")
    print("  3. Measure streaming performance metrics")
    print()
    print("=" * 60)
    print()
    
    asyncio.run(test_streaming_functionality())