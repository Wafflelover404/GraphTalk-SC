#!/usr/bin/env python3
"""
Quick test to verify CMS endpoints are working after integration
"""
import asyncio
import aiohttp
import json

async def test_cms_endpoints():
    """Test CMS API endpoints"""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🔍 Testing CMS API endpoints...")
        
        endpoints = [
            "/api/cms/blog/posts",
            "/api/cms/content/stats", 
            "/api/cms/system/health"
        ]
        
        for endpoint in endpoints:
            try:
                async with session.get(f"{base_url}{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"✅ GET {endpoint} - Status: {resp.status}")
                        if isinstance(data, list):
                            print(f"   Returned {len(data)} items")
                        else:
                            print(f"   Response: {data}")
                    else:
                        print(f"❌ GET {endpoint} - Status: {resp.status}")
                        error_text = await resp.text()
                        print(f"   Error: {error_text}")
            except Exception as e:
                print(f"❌ GET {endpoint} - Connection Error: {e}")
        
        print("\n📝 CMS Integration Test Complete!")
        print("If you see connection errors, make sure the API server is running:")
        print("   python3 api.py or uvicorn api:app --reload --host 0.0.0.0 --port 8000")

if __name__ == "__main__":
    asyncio.run(test_cms_endpoints())
