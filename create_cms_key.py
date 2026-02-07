#!/usr/bin/env python3
"""
Create CMS token and test login
"""
import os
import secrets
import sys

def create_cms_token():
    """Create a new CMS token and save it to .env file"""
    env_file = "/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/.env"
    
    # Generate new token
    new_token = secrets.token_urlsafe(64)
    
    print("🔑 Creating CMS Token...")
    print(f"Generated token: {new_token}")
    
    # Read existing .env file or create new one
    env_content = ""
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            env_content = f.read()
    
    # Update or add MASTER_CMS_TOKEN
    lines = env_content.split('\n')
    updated_lines = []
    token_updated = False
    
    for line in lines:
        if line.startswith('MASTER_CMS_TOKEN='):
            updated_lines.append(f'MASTER_CMS_TOKEN={new_token}')
            token_updated = True
        else:
            updated_lines.append(line)
    
    # Add token if not found
    if not token_updated:
        updated_lines.append(f'MASTER_CMS_TOKEN={new_token}')
    
    # Write back to .env file
    with open(env_file, 'w') as f:
        f.write('\n'.join(updated_lines))
    
    print(f"✅ Token saved to {env_file}")
    return new_token

def test_cms_login(token):
    """Test CMS login with the token"""
    print(f"\n🧪 Testing CMS Login...")
    
    # Add path for CMS imports
    sys.path.append('./landing-pages-api')
    
    try:
        from auth import verify_cms_token, cms_auth
        
        # Test token verification
        if verify_cms_token(token):
            print("✅ Token verification successful!")
            print("✅ CMS login working correctly")
            return True
        else:
            print("❌ Token verification failed!")
            return False
            
    except Exception as e:
        print(f"❌ Login test failed: {e}")
        return False

def main():
    """Main function"""
    print("🚀 CMS Token Creation and Login Test")
    print("=" * 50)
    
    # Create token
    token = create_cms_token()
    
    print(f"\n📋 CMS Login Credentials:")
    print(f"Username: admin")
    print(f"Password: {token}")
    
    # Test login
    success = test_cms_login(token)
    
    if success:
        print(f"\n🎉 CMS setup complete!")
        print(f"📝 Use these credentials to access CMS endpoints:")
        print(f"   Authorization: Bearer {token}")
        print(f"\n🔄 Restart the API server to apply changes:")
        print(f"   python3 api.py")
    else:
        print(f"\n❌ CMS setup failed!")

if __name__ == "__main__":
    main()
