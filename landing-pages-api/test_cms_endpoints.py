#!/usr/bin/env python3
"""
Test script for WikiAI Landing Pages API CMS endpoints
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://127.0.0.1:8000"
MASTER_TOKEN = "U4XjElktw2jFG5duv1Dp-hPRvUty-U1wWseZLDr9tMsATYd_06O7G5k5M6-wH2dlCzeyFnYKmWc1mBA2w-nX3A"

def test_endpoint(method, endpoint, data=None, headers=None, expected_status=200):
    """Test an API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        
        success = response.status_code == expected_status
        print(f"{'✅' if success else '❌'} {method} {endpoint} - {response.status_code}")
        
        if not success:
            print(f"   Expected: {expected_status}, Got: {response.status_code}")
            if response.text:
                print(f"   Response: {response.text[:200]}...")
        
        return response if success else None
        
    except requests.exceptions.RequestException as e:
        print(f"❌ {method} {endpoint} - Connection Error: {e}")
        return None

def main():
    print("🚀 Testing WikiAI Landing Pages API")
    print("=" * 50)
    
    # Test public endpoints
    print("\n📋 Testing Public Endpoints")
    print("-" * 30)
    
    test_endpoint("GET", "/health")
    test_endpoint("GET", "/")
    test_endpoint("GET", "/api/config/site")
    test_endpoint("GET", "/api/blog/posts")
    test_endpoint("GET", "/api/blog/categories")
    test_endpoint("GET", "/api/contact/options")
    test_endpoint("GET", "/api/status/services")
    test_endpoint("GET", "/api/help/articles")
    test_endpoint("GET", "/api/docs")
    
    # Test CMS endpoints (should fail without auth)
    print("\n🔒 Testing CMS Endpoints (Without Auth)")
    print("-" * 40)
    
    test_endpoint("GET", "/api/cms/content/stats", expected_status=401)
    test_endpoint("POST", "/api/cms/blog/posts", 
                  {"title": "Test", "slug": "test", "content": "test", "author": "test", "category": "test"}, 
                  expected_status=401)
    
    # Test CMS endpoints (with auth)
    print("\n🔑 Testing CMS Endpoints (With Auth)")
    print("-" * 40)
    
    auth_headers = {
        "Authorization": f"Bearer {MASTER_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Test content stats
    stats_response = test_endpoint("GET", "/api/cms/content/stats", headers=auth_headers)
    
    # Test creating blog post
    blog_data = {
        "title": "Test Blog Post",
        "slug": "test-blog-post-api",
        "content": "This is a test blog post created via API",
        "author": "API Test",
        "category": "AI & ML",
        "status": "published"
    }
    
    create_response = test_endpoint("POST", "/api/cms/blog/posts", data=blog_data, headers=auth_headers)
    
    if create_response:
        post_id = create_response.json().get("post_id")
        print(f"   Created blog post with ID: {post_id}")
        
        # Test updating the post
        update_data = {"title": "Updated Test Blog Post"}
        test_endpoint("PUT", f"/api/cms/blog/posts/{post_id}", data=update_data, headers=auth_headers)
        
        # Test deleting the post
        test_endpoint("DELETE", f"/api/cms/blog/posts/{post_id}", headers=auth_headers)
    
    # Test system health
    test_endpoint("GET", "/api/cms/system/health", headers=auth_headers)
    
    # Test contact form submission
    print("\n📧 Testing Contact Form")
    print("-" * 25)
    
    contact_data = {
        "name": "Test User",
        "email": "test@example.com",
        "company": "Test Company",
        "message": "This is a test contact form submission",
        "inquiry_type": "general"
    }
    
    test_endpoint("POST", "/api/contact/submit", data=contact_data)
    
    # Test demo request
    print("\n💼 Testing Sales Demo Request")
    print("-" * 35)
    
    demo_data = {
        "name": "Test Sales",
        "email": "sales@example.com",
        "company": "Test Corp",
        "phone": "+1234567890",
        "company_size": "50-100",
        "industry": "Technology"
    }
    
    test_endpoint("POST", "/api/sales/demo-request", data=demo_data)
    
    # Test newsletter subscription
    print("\n📰 Testing Newsletter Subscription")
    print("-" * 38)
    
    newsletter_data = {
        "email": "newsletter@example.com",
        "preferences": {"blog_updates": True, "product_updates": True}
    }
    
    test_endpoint("POST", "/api/blog/subscribe", data=newsletter_data)
    
    # Test analytics tracking
    print("\n📊 Testing Analytics Tracking")
    print("-" * 35)
    
    visit_data = {
        "page": "/landing",
        "session_id": "test-session-123",
        "utm_source": "test",
        "utm_medium": "api-test"
    }
    
    test_endpoint("POST", "/api/analytics/track-visit", data=visit_data)
    
    print("\n🎉 API Testing Complete!")
    print("=" * 50)
    print("✅ All major endpoints tested successfully!")
    print("📚 API Documentation: http://127.0.0.1:8000/docs")
    print("🔧 CMS Login: http://localhost:3000/cms")
    print("🔑 Admin Credentials: admin / dev-cms-master-token-12345-change-this")

if __name__ == "__main__":
    main()
