#!/usr/bin/env python3
"""
Test API key deletion directly
"""

import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_keys import revoke_api_key

async def test_delete_endpoint():
    """Test API key deletion endpoint directly"""
    
    print("🔑 Testing API Key Deletion Endpoint Directly")
    
    try:
        # Test 1: Try to delete the key
        print("\n1️⃣ Attempting to delete API key 18ba0df7-8077-4465-983f-9e0711aad4c0...")
        result = await revoke_api_key("18ba0df7-8077-4465-983f-9e0711aad4c0", 1)
        
        print(f"📤 Delete API Response: {result}")
        
        if result.get("status") == "success":
            print("✅ SUCCESS: API key deletion worked!")
            return True
        else:
            print(f"❌ FAILED: API key deletion failed: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_delete_endpoint())
    if success:
        print("\n🎉 API key deletion endpoint is working correctly!")
    else:
        print("\n💥 API key deletion endpoint test failed!")
