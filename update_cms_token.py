#!/usr/bin/env python3
"""
Script to generate a new CMS master token and automatically update .env file
"""

import secrets
import os
import sys

def generate_new_token():
    """Generate a new secure token"""
    return secrets.token_urlsafe(64)

def update_env_file(new_token):
    """Update the landing-pages-api .env file with new token"""
    env_file = "/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/.env"
    
    if not os.path.exists(env_file):
        print(f"❌ {env_file} not found")
        return False
    
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        # Replace the master token line
        lines = content.split('\n')
        updated_lines = []
        token_updated = False
        
        for line in lines:
            if line.startswith('MASTER_CMS_TOKEN='):
                updated_lines.append(f'MASTER_CMS_TOKEN={new_token}')
                token_updated = True
            else:
                updated_lines.append(line)
        
        # Add the token if it wasn't found
        if not token_updated:
            updated_lines.append(f'MASTER_CMS_TOKEN={new_token}')
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.write('\n'.join(updated_lines))
        
        print(f"✅ Updated {env_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating {env_file}: {e}")
        return False

def main():
    """Main function to generate and update token"""
    print("🔑 Auto-Update CMS Master Token")
    print("=" * 50)
    
    # Generate new token
    new_token = generate_new_token()
    print(f"🆕 New Token: {new_token}")
    print(f"📏 Length: {len(new_token)} characters")
    
    # Update .env file
    print(f"\n🔄 Updating .env file...")
    success = update_env_file(new_token)
    
    if success:
        print(f"\n✅ Token updated successfully!")
        print(f"\n📋 Next Steps:")
        print(f"1. Restart the backend server:")
        print(f"   cd /Users/wafflelover404/Documents/wikiai/graphtalk")
        print(f"   python3 api.py")
        print(f"")
        print(f"2. Use new token for CMS login:")
        print(f"   Username: admin")
        print(f"   Password: {new_token}")
        print(f"")
        print(f"3. Restart React dev server if needed:")
        print(f"   cd /Users/wafflelover404/Documents/wikiai/wiki-ai-react")
        print(f"   npm run dev")
    else:
        print(f"\n❌ Failed to update .env file")
        sys.exit(1)

if __name__ == "__main__":
    main()
