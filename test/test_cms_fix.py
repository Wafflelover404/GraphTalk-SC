#!/usr/bin/env python3
"""
Test script to verify CMS endpoints work with Bearer token authentication
Tests the fix for 422 Unprocessable Entity error
"""

import requests
import json
import sys
import os
from datetime import datetime

# Configuration
BASE_URL = "http://127.0.0.1:9001"
ADMIN_TOKEN = os.getenv("MASTER_CMS_TOKEN", "U4XjElktw2jFG5duv1Dp-hPRvUty-U1wWseZLDr9tMsATYd_06O7G5k5M6-wH2dlCzeyFnYKmWc1mBA2w-nX3A")
CMS_PASSWORD = os.getenv("CMS_PASSWORD", "AdminTestPassword1423")

def test_cms_endpoint(method: str, endpoint: str, description: str, use_bearer: bool = True, data=None):
    """Test a CMS endpoint with both authentication methods"""
    print(f"\n{'='*60}")
    print(f"🧪 Testing: {description}")
    print(f"   Endpoint: {method} {endpoint}")
    
    url = f"{BASE_URL}/api/cms{endpoint}"
    
    # Test 1: Bearer token authentication (main API integration)
    if use_bearer:
        print(f"\n   📡 Test 1: Bearer Token Authentication")
        headers = {
            "Authorization": f"Bearer {ADMIN_TOKEN}",
            "Content-Type": "application/json"
        }
        
        try:
            response = None
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=5)
            elif method == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=5)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=headers, timeout=5)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=5)
            
            if response is not None:
                print(f"      Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"      ✅ Success")
                    try:
                        resp_data = response.json()
                        print(f"      Response keys: {list(resp_data.keys())[:5]}")
                    except Exception:
                        print(f"      Response: {response.text[:100]}")
                elif response.status_code == 422:
                    print(f"      ❌ FAILED: Unprocessable Entity (422)")
                    print(f"      Details: {response.text[:200]}")
                elif response.status_code == 401:
                    print(f"      ❌ FAILED: Unauthorized (401)")
                    print(f"      Details: {response.text[:200]}")
                else:
                    print(f"      ⚠️  Unexpected status: {response.status_code}")
                    print(f"      Details: {response.text[:200]}")
                
        except Exception as e:
            print(f"      ❌ Error: {str(e)}")
    
    # Test 2: Custom header authentication (backward compatibility)
    print(f"\n   📡 Test 2: Custom Header Authentication")
    headers = {
        "X-CMS-Password": CMS_PASSWORD,
        "Content-Type": "application/json"
    }
    
    try:
        response = None
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=5)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers, timeout=5)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=5)
        
        if response is not None:
            print(f"      Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"      ✅ Success")
            elif response.status_code == 422:
                print(f"      ❌ FAILED: Unprocessable Entity (422)")
                print(f"      Details: {response.text[:200]}")
            elif response.status_code == 401:
                print(f"      ❌ FAILED: Unauthorized (401)")
                print(f"      Details: {response.text[:200]}")
            else:
                print(f"      ⚠️  Unexpected status: {response.status_code}")
            
    except Exception as e:
        print(f"      ❌ Error: {str(e)}")

def main():
    print("=" * 60)
    print("🚀 CMS Endpoint Authentication Test")
    print("=" * 60)
    print(f"\n📍 Base URL: {BASE_URL}")
    print(f"🔐 Token: {ADMIN_TOKEN[:20]}...")
    print(f"🔑 Password: {CMS_PASSWORD[:15]}...")
    
    # Test key endpoints
    endpoints = [
        ("GET", "/content/stats", "Content Statistics (GET)"),
        ("GET", "/system/health", "System Health (GET)"),
        ("GET", "/blog/posts", "Blog Posts List (GET)"),
    ]
    
    print("\n" + "=" * 60)
    print("Testing CMS Endpoints")
    print("=" * 60)
    
    for method, endpoint, description in endpoints:
        test_cms_endpoint(method, endpoint, description)
    
    print("\n" + "=" * 60)
    print("🎉 CMS Endpoint Tests Complete!")
    print("=" * 60)
    print("\n✅ If all tests passed, the CMS endpoint authentication fix is working correctly.")
    print("❌ If you see 422 or 401 errors, there may still be an issue with authentication.")

if __name__ == "__main__":
    main()
