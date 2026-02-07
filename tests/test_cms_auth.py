#!/usr/bin/env python3
"""
Test CMS API endpoints with authentication
"""
import os
import sys
from dotenv import load_dotenv

def show_cms_credentials():
    """Show current CMS credentials"""
    env_file = "/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/.env"
    load_dotenv(env_file)
    
    token = os.getenv("MASTER_CMS_TOKEN")
    
    if token:
        print("🔑 Current CMS Credentials:")
        print(f"Username: admin")
        print(f"Password: {token}")
        print(f"\n📝 For API calls, use:")
        print(f"Authorization: Bearer {token}")
        print(f"\n🧪 Test with curl:")
        print(f"curl -H 'Authorization: Bearer {token}' http://localhost:8000/api/cms/blog/posts")
        return token
    else:
        print("❌ No CMS token found")
        return None

def test_cms_auth():
    """Test CMS authentication"""
    env_file = "/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/.env"
    load_dotenv(env_file)
    
    sys.path.append('./landing-pages-api')
    
    try:
        from auth import verify_cms_token, cms_auth
        
        token = os.getenv("MASTER_CMS_TOKEN")
        if token and verify_cms_token(token):
            print("✅ CMS authentication working correctly")
            return True
        else:
            print("❌ CMS authentication failed")
            return False
            
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False

def main():
    """Main function"""
    print("🔐 CMS Authentication Test")
    print("=" * 40)
    
    # Show credentials
    token = show_cms_credentials()
    
    if token:
        # Test authentication
        if test_cms_auth():
            print(f"\n🎉 CMS is ready!")
            print(f"📝 Start the API server to test endpoints:")
            print(f"   python3 api.py")
            print(f"\n🌐 Then test with:")
            print(f"   curl -H 'Authorization: Bearer {token}' http://localhost:8000/api/cms/system/health")
        else:
            print(f"\n❌ CMS authentication issues detected")
    else:
        print(f"\n❌ No CMS credentials found")
        print(f"📝 Run: python3 create_cms_key_fixed.py")

if __name__ == "__main__":
    main()
