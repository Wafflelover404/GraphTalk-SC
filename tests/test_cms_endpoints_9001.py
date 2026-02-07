#!/usr/bin/env python3
"""
Test script to verify CMS endpoints are accessible on port 9001
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://127.0.0.1:9001"
ADMIN_TOKEN = "U4XjElktw2jFG5duv1Dp-hPRvUty-U1wWseZLDr9tMsATYd_06O7G5k5M6-wH2dlCzeyFnYKmWc1mBA2w-nX3A"

def test_cms_endpoints():
    """Test CMS endpoints on port 9001"""
    print("🧪 Testing CMS Endpoints on Port 9001")
    print("=" * 50)
    
    # Test authentication
    auth_headers = {
        "Authorization": f"Bearer {ADMIN_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Test CMS endpoints
    cms_endpoints = [
        ("GET", "/api/cms/content/stats", "Content Statistics"),
        ("GET", "/api/cms/system/health", "System Health"),
        ("GET", "/api/cms/blog/posts", "Blog Posts"),
    ]
    
    for method, endpoint, description in cms_endpoints:
        try:
            url = f"{BASE_URL}{endpoint}"
            print(f"\n🔍 Testing {description}: {method} {endpoint}")
            
            if method == "GET":
                response = requests.get(url, headers=auth_headers, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ {description} - Success")
                data = response.json()
                print(f"   Response: {json.dumps(data, indent=2)[:200]}...")
            elif response.status_code == 401:
                print(f"⚠️ {description} - Authentication required (expected)")
            else:
                print(f"❌ {description} - Status {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ {description} - Connection failed (server not running?)")
        except requests.exceptions.Timeout:
            print(f"❌ {description} - Timeout")
        except Exception as e:
            print(f"❌ {description} - Error: {e}")
    
    print(f"\n🎉 CMS Endpoint Testing Complete!")
    print(f"📝 All CMS endpoints should be accessible at: {BASE_URL}/api/cms/*")

if __name__ == "__main__":
    test_cms_endpoints()
