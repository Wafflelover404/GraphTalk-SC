#!/usr/bin/env python3
"""
Test WebSocket authentication after server restart
"""
import asyncio
import websockets
import json

async def test_websocket_after_restart():
    print("🧪 Testing WebSocket Authentication After Restart")
    print("=" * 50)
    
    # Test with the CMS token from the logs
    token = 'U4XjElktw2jFG5duv1Dp-hPRvUty-U1wWseZLDr9tMsATYd_06O7G5k5M6-wH2dlCzeyFnYKmWc1mBA2w-nX3A'
    uri = f'ws://127.0.0.1:9001/ws/messaging?token={token}'
    
    print(f"Testing WebSocket with CMS token...")
    print(f"Token length: {len(token)}")
    print(f"WebSocket URL: {uri}")
    print()
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection established!")
            
            # Send a test message
            await websocket.send(json.dumps({
                "type": "ping",
                "timestamp": int(asyncio.get_event_loop().time())
            }))
            
            # Wait for response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                data = json.loads(response)
                print(f"📨 Server response: {data}")
                
                if data.get("type") == "error":
                    print(f"⚠️  Authentication error: {data.get('message')}")
                    print("This is expected if the token is not valid in the main API system")
                else:
                    print("🎉 WebSocket authentication working!")
                    
            except asyncio.TimeoutError:
                print("⏰ No response received (connection established but no response)")
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"🔌 WebSocket closed with code {e.code}: {e.reason}")
        
        if e.code == 1008:
            if "Authentication" in e.reason:
                print("❌ Authentication failed - token not valid in main API")
                print("💡 Solution: Log out of CMS and log back in through main API")
            elif "Access denied" in e.reason:
                print("❌ Access denied - user not admin")
            else:
                print(f"⚠️  Authentication failed: {e.reason}")
        else:
            print(f"⚠️  Unexpected close code: {e.code}")
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("💡 Make sure the server is restarted with the new authentication code")

if __name__ == "__main__":
    asyncio.run(test_websocket_after_restart())
