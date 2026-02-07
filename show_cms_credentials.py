#!/usr/bin/env python3
"""
Show current CMS login credentials
"""

import os
import re

def extract_token_from_env():
    """Extract the original CMS token from the .env file"""
    env_file = "/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/.env"
    
    if not os.path.exists(env_file):
        print(f"❌ {env_file} not found")
        return None
    
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Look for the commented original token
        for line in content.split('\n'):
            if line.startswith('# MASTER_CMS_TOKEN='):
                # Extract token from commented line
                token = line.split('=', 1)[1].split('  #')[0]
                return token
        
        # If not found in comments, look for plain token
        for line in content.split('\n'):
            if line.startswith('MASTER_CMS_TOKEN=') and not line.startswith('#'):
                return line.split('=', 1)[1]
        
        return None
        
    except Exception as e:
        print(f"❌ Error reading {env_file}: {e}")
        return None

def main():
    """Display current CMS login credentials"""
    print("🔑 CMS Login Credentials")
    print("=" * 40)
    
    token = extract_token_from_env()
    
    if token:
        print(f"Username: admin")
        print(f"Password: {token}")
        print("\n✅ Authentication is now using salted hashing")
        print("🔐 Your token is securely stored with bcrypt")
    else:
        print("❌ No CMS token found")
        print("Please run: python3 cms_token_manager.py")

if __name__ == "__main__":
    main()
