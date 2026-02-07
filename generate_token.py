#!/usr/bin/env python3
"""
Simple script to generate a new CMS master token (manual update required)
"""

import secrets

def generate_token():
    """Generate a new secure token"""
    new_token = secrets.token_urlsafe(64)
    
    print("🔑 New CMS Master Token Generated:")
    print("=" * 60)
    print(f"New Token: {new_token}")
    print(f"Length: {len(new_token)} characters")
    print("=" * 60)
    
    print("\n📝 Manual Update Required:")
    print("1. Update landing-pages-api/.env:")
    print(f"   MASTER_CMS_TOKEN={new_token}")
    print("\n2. Restart the backend server:")
    print("   cd /Users/wafflelover404/Documents/wikiai/graphtalk")
    print("   python3 api.py")
    print("\n3. Use new token for CMS login:")
    print("   Username: admin")
    print(f"   Password: {new_token}")
    
    return new_token

if __name__ == "__main__":
    generate_token()
