#!/usr/bin/env python3
"""
Minimal test script for invite endpoints
"""
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

# Import just the invite-related models and endpoints
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

app = FastAPI()

@app.post("/invites/create", response_model=APIResponse)
async def create_invite(request: CreateInviteRequest):
    """Test invite creation endpoint"""
    import secrets
    import datetime
    
    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=request.expires_in_days or 7)
    base_url = "http://localhost:3000"
    invite_link = f"{base_url}/invite?token={invite_token}"
    
    return APIResponse(
        status="success",
        message="Invite link created successfully",
        response={
            "invite_id": "test-id",
            "token": invite_token,
            "link": invite_link,
            "email": request.email,
            "role": request.role,
            "expires_at": expires_at.isoformat(),
            "created_by": "test-admin"
        }
    )

@app.get("/invites")
async def list_invites():
    """Test invite listing endpoint"""
    return APIResponse(
        status="success",
        message="Retrieved 0 invites",
        response={
            "invites": [],
            "count": 0,
            "listed_by": "test-admin"
        }
    )

if __name__ == "__main__":
    print("Starting minimal API server for invite endpoints...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
