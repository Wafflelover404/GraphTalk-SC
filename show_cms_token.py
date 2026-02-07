#!/usr/bin/env python3
"""
Simple script to display the current CMS master token
"""

import os

def show_current_token():
    """Display the current CMS master token from .env file"""
    env_file = "/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/.env"
    
    if not os.path.exists(env_file):
        print(f"❌ {env_file} not found")
        return
    
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Find the master token line
        for line in content.split('\n'):
            if line.startswith('MASTER_CMS_TOKEN='):
                token = line.split('=', 1)[1]
                print("🔑 Current CMS Master Token:")
                print("=" * 50)
                print(f"Token: {token}")
                print(f"Length: {len(token)} characters")
                print("=" * 50)
                print("\n📋 Usage:")
                print("Username: admin")
                print(f"Password: {token}")
                return
        
        print("❌ MASTER_CMS_TOKEN not found in .env file")
        
    except Exception as e:
        print(f"❌ Error reading {env_file}: {e}")

if __name__ == "__main__":
    show_current_token()
