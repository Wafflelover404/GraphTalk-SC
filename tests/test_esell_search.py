#!/usr/bin/env python3
"""
Test script for esell.by search endpoint
Tests the newly created /search/esell endpoint
"""

import requests
import json
import time

BASE_URL = "http://localhost:9001"
API_KEY = "wk_AI6pGkU2xyeNoBxSDmg-FTLO-rOf-kWJQKYbwryaVjk"

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def test_esell_search_endpoint():
    """Test the esell search endpoint"""
    print_header("Testing esell.by Search Endpoint")
    
    test_cases = [
        {"query": "headphones", "limit": 5},
        {"query": "laptop", "limit": 10},
        {"query": "wireless mouse", "limit": 3},
    ]
    
    for test_case in test_cases:
        query = test_case["query"]
        limit = test_case["limit"]
        
        print(f"🔍 Testing search: '{query}' (limit={limit})")
        print(f"   URL: {BASE_URL}/search/esell?query={query}&limit={limit}")
        
        try:
            response = requests.get(
                f"{BASE_URL}/search/esell",
                params={"query": query, "limit": limit},
                timeout=30
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Success!")
                print(f"   Response: {json.dumps(data, indent=2)}")
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   Response: {response.text}")
        
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection Error: Unable to connect to {BASE_URL}")
            print(f"   Make sure the server is running: python main.py or uvicorn api:app --reload --host 0.0.0.0 --port 9001")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()

def test_esell_search_test_endpoint():
    """Test the esell search test endpoint"""
    print_header("Testing esell.by Search Test Endpoint")
    
    print(f"📋 Testing: {BASE_URL}/search/esell/test")
    
    try:
        response = requests.post(
            f"{BASE_URL}/search/esell/test",
            timeout=10
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Test endpoint working!")
            print(f"Response: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
    
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection Error: Unable to connect to {BASE_URL}")
        print(f"Make sure the server is running on port 9001")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_health_check():
    """Test if server is running"""
    print_header("Checking Server Health")
    
    print(f"Checking {BASE_URL}/health...")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ Server is running!")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"❌ Server error: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to server at {BASE_URL}")
        print(f"\n📝 Please start the server with one of these commands:")
        print(f"   python main.py")
        print(f"   OR")
        print(f"   uvicorn api:app --reload --host 0.0.0.0 --port 9001")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  esell.by Search Endpoint Test Suite")
    print("="*60)
    print(f"\nServer URL: {BASE_URL}")
    print(f"API Key: {API_KEY[:20]}...")
    
    # Check if server is running
    if test_health_check():
        print("\n✅ Server is online! Running endpoint tests...\n")
        
        # Test the test endpoint first
        test_esell_search_test_endpoint()
        
        # Test the actual search endpoint
        test_esell_search_endpoint()
        
        print("\n" + "="*60)
        print("  Test Suite Complete")
        print("="*60)
    else:
        print("\n⚠️  Server is not responding. Start it first, then run this test again.")

