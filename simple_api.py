#!/usr/bin/env python3
"""
Simple API server with only invite endpoints
"""
import asyncio
import uvicorn
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import secrets
import datetime
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Mock dependencies
security_scheme = HTTPBearer()

# Models
class CreateInviteRequest(BaseModel):
    email: str = None
    role: str = "user"
    allowed_files: list = None
    expires_in_days: int = 7
    message: str = None

class APIResponse(BaseModel):
    status: str
    message: str
    response: dict = None

# Mock user functions
async def get_user_by_token(token: str):
    # Mock admin user for testing
    return ["test-admin-id", "test-admin", "admin@test.com", "admin", None, None, None, None]

def _get_active_org_id(user):
    return "test-org-id"

def log_event(**kwargs):
    logger.info(f"Event: {kwargs}")

# Invite endpoints
@app.post("/invites/create", response_model=APIResponse)
async def create_invite(
    request: CreateInviteRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
):
    """Create invite link"""
    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=request.expires_in_days or 7)
    base_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    invite_link = f"{base_url}/invite?token={invite_token}"
    
    return APIResponse(
        status="success",
        message="Invite link created successfully",
        response={
            "invite_id": invite_token,
            "token": invite_token,
            "link": invite_link,
            "email": request.email,
            "role": request.role,
            "expires_at": expires_at.isoformat(),
            "created_by": "test-admin"
        }
    )

@app.get("/invites", response_model=APIResponse)
async def list_invites(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    """List invites"""
    return APIResponse(
        status="success",
        message="Retrieved 0 invites",
        response={
            "invites": [],
            "count": 0,
            "listed_by": "test-admin"
        }
    )

@app.get("/invite/{token}", response_model=APIResponse)
async def get_invite_info(token: str):
    """Get invite info"""
    invite_info = {
        "valid": True,
        "email": None,
        "role": "user",
        "allowed_files": [],
        "expires_at": (datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat(),
        "created_by": "admin",
        "message": "You've been invited to join our platform!"
    }
    
    return APIResponse(
        status="success",
        message="Invite information retrieved",
        response=invite_info
    )

@app.post("/invites/accept", response_model=APIResponse)
async def accept_invite(
    request: dict,
    token: str = None,
    username: str = None,
    password: str = None
):
    """Accept invite"""
    if not token or not username or not password:
        return APIResponse(
            status="error", 
            message="Token, username, and password are required", 
            response={}
        )
    
    if len(password) < 6:
        return APIResponse(
            status="error", 
            message="Password must be at least 6 characters long", 
            response={}
        )
    
    return APIResponse(
        status="success",
        message=f"User '{username}' created successfully",
        response={
            "username": username,
            "role": "user",
            "allowed_files": [],
            "organization_id": None
        }
    )

if __name__ == "__main__":
    print("🚀 Starting simple API server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
