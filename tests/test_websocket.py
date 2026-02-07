#!/usr/bin/env python3
"""
Quick test script to check WebSocket endpoint availability
"""
import asyncio
import websockets
import json

async def test_websocket_connection():
    print("🔍 Testing WebSocket endpoint availability...")
    
    # Test 1: Connection without token (should get 1008)
    try:
        uri = 'ws://127.0.0.1:9001/ws/messaging'
        print(f"Testing: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("❌ Unexpected success - should have failed")
            
    except websockets.exceptions.ConnectionClosed as e:
        if e.code == 1008:
            print("✅ Connection properly rejected (no token)")
        else:
            print(f"⚠️  Unexpected close code: {e.code}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    
    # Test 2: Connection with dummy token (should get 1008)
    try:
        uri = 'ws://127.0.0.1:9001/ws/messaging?token=dummy_token'
        print(f"Testing: {uri}")
        
        async with websockets.connect(uri) as websocket:
            print("❌ Unexpected success - should have failed")
            
    except websockets.exceptions.ConnectionClosed as e:
        if e.code == 1008:
            print("✅ Connection properly rejected (invalid token)")
        else:
            print(f"⚠️  Unexpected close code: {e.code}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())
