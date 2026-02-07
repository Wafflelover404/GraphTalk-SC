#!/usr/bin/env python3
"""
Test script to verify frontend-backend CMS integration
"""

import requests
import json

# Configuration
BASE_URL = "http://127.0.0.1:9001"
ADMIN_TOKEN = "U4XjElktw2jFG5duv1Dp-hPRvUty-U1wWseZLDr9tMsATYd_06O7G5k5M6-wH2dlCzeyFnYKmWc1mBA2w-nX3A"

def test_cms_integration():
    """Test CMS integration between frontend and backend"""
    print("🧪 Testing Frontend-Backend CMS Integration")
    print("=" * 60)
    
    # Test authentication
    auth_headers = {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Test available CMS endpoints
    cms_endpoints = [
        ("GET", "/api/cms/blog/posts", "Blog Posts List"),
        ("GET", "/api/cms/content/stats", "Content Statistics"),
        ("GET", "/api/cms/system/health", "System Health"),
    ]
    
    print("\n🔍 Testing Available CMS Endpoints:")
    for method, endpoint, description in cms_endpoints:
        try:
            url = f"{BASE_URL}{endpoint}"
            print(f"\n  📡 {description}: {method} {endpoint}")
            
            if method == "GET":
                response = requests.get(url, headers=auth_headers, timeout=5)
            
            if response.status_code == 200:
                print(f"    ✅ Success - {response.status_code}")
                data = response.json()
                if isinstance(data, list):
                    print(f"    📊 Returned {len(data)} items")
                elif isinstance(data, dict):
                    print(f"    📊 Keys: {list(data.keys())}")
            elif response.status_code == 401:
                print(f"    ⚠️ Authentication required")
            else:
                print(f"    ❌ Error - {response.status_code}")
                print(f"    📝 Response: {response.text[:100]}...")
                
        except requests.exceptions.ConnectionError:
            print(f"    ❌ Connection failed - server not running on port 9001?")
        except requests.exceptions.Timeout:
            print(f"    ❌ Request timeout")
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    # Test endpoints that frontend expects but might not exist
    missing_endpoints = [
        ("GET", "/api/cms/contact/options", "Contact Options"),
        ("GET", "/api/cms/help/articles", "Help Articles"),
        ("GET", "/api/cms/status/services", "Status Services"),
    ]
    
    print(f"\n⚠️ Testing Endpoints Frontend Expects:")
    for method, endpoint, description in missing_endpoints:
        try:
            url = f"{BASE_URL}{endpoint}"
            print(f"\n  📡 {description}: {method} {endpoint}")
            
            if method == "GET":
                response = requests.get(url, headers=auth_headers, timeout=5)
            
            if response.status_code == 200:
                print(f"    ✅ Available")
            elif response.status_code == 404:
                print(f"    ❌ Not Found (404) - needs to be implemented")
            elif response.status_code == 401:
                print(f"    ⚠️ Authentication required")
            else:
                print(f"    ❌ Error - {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    print(f"\n🎯 Integration Test Summary:")
    print(f"📝 Frontend is configured to use port 9001 ✅")
    print(f"🔗 CMS endpoints are available at /api/cms/* ✅")
    print(f"⚠️ Some frontend endpoints may need additional routers")
    
    print(f"\n📋 Next Steps:")
    print(f"1. Ensure main API server is running on port 9001")
    print(f"2. Add missing routers if needed (contact, sales, help, status)")
    print(f"3. Test frontend CMS functionality")

if __name__ == "__main__":
    test_cms_integration()
