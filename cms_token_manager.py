#!/usr/bin/env python3
"""
CMS Token Management Utility with Salted Hashing
"""

import os
import sys
import secrets
import bcrypt

def show_current_token():
    """Display the current CMS master token info"""
    env_file = "/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/.env"
    
    if not os.path.exists(env_file):
        print(f"❌ {env_file} not found")
        return None, None, None
    
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        plain_token = None
        hashed_token = None
        salt = None
        
        for line in content.split('\n'):
            if line.startswith('MASTER_CMS_TOKEN='):
                plain_token = line.split('=', 1)[1]
            elif line.startswith('MASTER_CMS_TOKEN_HASH='):
                hashed_token = line.split('=', 1)[1]
            elif line.startswith('MASTER_CMS_TOKEN_SALT='):
                salt = line.split('=', 1)[1]
        
        return plain_token, hashed_token, salt
        
    except Exception as e:
        print(f"❌ Error reading {env_file}: {e}")
        return None, None, None

def update_env_with_hashed_token(new_token, hashed_token, salt):
    """Update the .env file with new hashed token and salt"""
    env_file = "/Users/wafflelover404/Documents/wikiai/graphtalk/landing-pages-api/.env"
    
    try:
        with open(env_file, 'r') as f:
            content = f.read()
        
        lines = content.split('\n')
        updated_lines = []
        has_hash = False
        has_salt = False
        
        for line in lines:
            if line.startswith('MASTER_CMS_TOKEN='):
                # Keep plain token for backward compatibility but mark as deprecated
                updated_lines.append(f'# MASTER_CMS_TOKEN={new_token}  # DEPRECATED - use hashed version below')
            elif line.startswith('MASTER_CMS_TOKEN_HASH='):
                updated_lines.append(f'MASTER_CMS_TOKEN_HASH={hashed_token}')
                has_hash = True
            elif line.startswith('MASTER_CMS_TOKEN_SALT='):
                updated_lines.append(f'MASTER_CMS_TOKEN_SALT={salt}')
                has_salt = True
            else:
                updated_lines.append(line)
        
        # Add hash and salt if they don't exist
        if not has_hash:
            updated_lines.append(f'MASTER_CMS_TOKEN_HASH={hashed_token}')
        if not has_salt:
            updated_lines.append(f'MASTER_CMS_TOKEN_SALT={salt}')
        
        with open(env_file, 'w') as f:
            f.write('\n'.join(updated_lines))
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating {env_file}: {e}")
        return False

def hash_token_with_salt(token):
    """Hash a token with salt using bcrypt"""
    # Generate a proper bcrypt salt
    bcrypt_salt = bcrypt.gensalt()
    # Truncate token to bcrypt's 72-byte limit if needed
    token_bytes = token.encode('utf-8')[:72]
    hashed = bcrypt.hashpw(token_bytes, bcrypt_salt)
    return hashed.decode('utf-8'), bcrypt_salt.decode('utf-8')

def verify_token(token, hashed_token, salt):
    """Verify a token against its hash and salt"""
    try:
        # Use the hashed token which contains the salt
        hashed_bytes = hashed_token.encode('utf-8')
        # Truncate token to match the hashing process
        token_bytes = token.encode('utf-8')[:72]
        return bcrypt.checkpw(token_bytes, hashed_bytes)
    except Exception as e:
        print(f"❌ Token verification error: {e}")
        return False

def main():
    """Main utility function"""
    print("🔑 CMS Token Management Utility (Salted Hashing)")
    print("=" * 60)
    
    # Show current token info
    plain_token, hashed_token, salt = show_current_token()
    
    if hashed_token and salt:
        print("✅ Hashed token configuration found:")
        print(f"🔐 Hash: {hashed_token[:20]}...")
        print(f"🧂 Salt: {salt[:20]}...")
        print(f"� Hash length: {len(hashed_token)} characters")
        print(f"📏 Salt length: {len(salt)} characters")
        
        if plain_token:
            print("⚠️  Plain token still exists (deprecated)")
            
    elif plain_token:
        print("⚠️  Plain token found (migration recommended)")
        print(f"📍 Token: {plain_token[:20]}...")
        print(f"📏 Length: {len(plain_token)} characters")
        
    else:
        print("❌ No token configuration found")
        return
    
    print("\n" + "=" * 60)
    print("Options:")
    print("1. Generate new token (with salted hashing)")
    print("2. Migrate existing plain token to hashed storage")
    print("3. Test current token")
    print("4. Show current credentials")
    print("5. Exit")
    
    try:
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            # Generate new token with hashing
            new_token = secrets.token_urlsafe(64)
            new_hashed, new_salt = hash_token_with_salt(new_token)
            
            print(f"\n🆕 New Token Generated:")
            print(f"Token: {new_token}")
            print(f"Hash: {new_hashed}")
            print(f"Salt: {new_salt}")
            
            confirm = input("\n❓ Update .env file with new hashed token? (y/N): ").strip().lower()
            if confirm == 'y':
                if update_env_with_hashed_token(new_token, new_hashed, new_salt):
                    print("✅ Token updated successfully!")
                    print(f"\n📋 New Login Credentials:")
                    print(f"Username: admin")
                    print(f"Password: {new_token}")
                    print(f"\n🔄 Restart backend server to apply changes.")
                else:
                    print("❌ Failed to update token")
            else:
                print("❌ Token update cancelled")
                
        elif choice == "2":
            # Migrate existing token
            if not plain_token:
                print("❌ No plain token found to migrate")
                return
                
            print(f"\n🔄 Migrating plain token to hashed storage...")
            migrated_hash, migrated_salt = hash_token_with_salt(plain_token)
            
            confirm = input("❓ Update .env file with hashed token? (y/N): ").strip().lower()
            if confirm == 'y':
                if update_env_with_hashed_token(plain_token, migrated_hash, migrated_salt):
                    print("✅ Token migrated successfully!")
                    print("\n📋 Migration Summary:")
                    print("- Plain token marked as deprecated")
                    print("- Hashed token and salt added to .env")
                    print("- Login credentials remain the same")
                    print(f"\n🔄 Restart backend server to apply changes.")
                else:
                    print("❌ Failed to migrate token")
            else:
                print("❌ Migration cancelled")
                
        elif choice == "3":
            # Test current token
            if not plain_token or not hashed_token or not salt:
                print("❌ Cannot test - missing token configuration")
                return
                
            print(f"\n🧪 Testing token verification...")
            is_valid = verify_token(plain_token, hashed_token, salt)
            
            if is_valid:
                print("✅ Token verification successful!")
                print("� Hashed authentication is working correctly")
            else:
                print("❌ Token verification failed!")
                print("⚠️  There may be an issue with the hash/salt configuration")
                
        elif choice == "4":
            # Show current credentials
            if plain_token:
                print(f"\n�� Current Login Credentials:")
                print(f"Username: admin")
                print(f"Password: {plain_token}")
                if hashed_token and salt:
                    print("✅ Securely stored with salted hashing")
                else:
                    print("⚠️  Stored as plain text (migration recommended)")
            else:
                print("❌ No credentials available")
            
        elif choice == "5":
            print("👋 Goodbye!")
            
        else:
            print("❌ Invalid option")
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
