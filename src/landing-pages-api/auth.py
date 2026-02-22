import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CMSAuth:
    """Authentication system for CMS access"""
    
    def __init__(self):
        self.master_token = os.getenv("MASTER_CMS_TOKEN")
        if not self.master_token:
            logger.warning("MASTER_CMS_TOKEN not set in environment variables")
            # Generate a default token for development
            self.master_token = self.generate_token()
            logger.info(f"Generated development CMS token: {self.master_token}")
            logger.warning("Please set MASTER_CMS_TOKEN in production!")
    
    @staticmethod
    def generate_token(length: int = 64) -> str:
        """Generate a secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for storage"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    def verify_master_token(self, token: str) -> bool:
        """Verify the master CMS token"""
        return token == self.master_token
    
    def get_master_token(self) -> str:
        """Get the master token (for development only)"""
        return self.master_token

# Global auth instance
cms_auth = CMSAuth()

# FastAPI dependency
async def verify_master_token(token: str) -> Dict[str, Any]:
    """Verify master CMS token and return user info"""
    if not cms_auth.verify_master_token(token):
        raise ValueError("Invalid master token")
    
    return {
        "user_id": "cms_admin",
        "role": "admin",
        "permissions": ["cms:read", "cms:write", "cms:delete"],
        "token_type": "master"
    }

def create_master_token() -> str:
    """Create a new master token"""
    return CMSAuth.generate_token()

def verify_cms_token(token: str) -> bool:
    """Verify CMS token"""
    return cms_auth.verify_master_token(token)
