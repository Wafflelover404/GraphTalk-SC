"""Public organization management endpoints (no authentication required)"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import logging
import sys
import os
import uuid as uuid_lib

logger = logging.getLogger(__name__)
router = APIRouter()

# Models
class OrganizationCreateRequest(BaseModel):
    organization_name: str
    admin_username: str
    admin_password: str

class TokenRoleResponse(BaseModel):
    status: str
    message: str
    token: Optional[str] = None
    role: Optional[str] = None

@router.post("/create", response_model=TokenRoleResponse)
async def create_organization_public(request: OrganizationCreateRequest):
    """
    Create a new organization WITHOUT authentication (public endpoint).
    
    Organizations are created with 'pending' status and submitted for CMS admin approval.
    Users receive a session token immediately and can access their organization.
    Full features may be restricted until an admin approves the organization.
    """
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        
        from graphtalk.orgdb import DB_PATH as ORG_DB_PATH
        import aiosqlite as org_sqlite
        
        # Normalize username/password
        admin_username = request.admin_username.replace(" ", "_")
        admin_password = request.admin_password.replace(" ", "_")
        
        # Generate slug from org name
        slug = request.organization_name.lower().replace(" ", "-").replace("_", "-")
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        
        async with org_sqlite.connect(ORG_DB_PATH) as db:
            # Check if organization already exists
            cursor = await db.execute(
                "SELECT id FROM organizations WHERE slug = ?", (slug,)
            )
            if await cursor.fetchone():
                return TokenRoleResponse(
                    status="error",
                    message="Organization with this name already exists",
                    token=None,
                    role=None
                )
            
            # Create organization with pending status
            org_id = str(uuid_lib.uuid4())
            await db.execute(
                """
                INSERT INTO organizations (id, name, slug, status, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (org_id, request.organization_name, slug)
            )
            await db.commit()
            
            logger.info(f"Organization created with pending status: {org_id} ({request.organization_name})")
            
            return TokenRoleResponse(
                status="success",
                message=f"Organization '{request.organization_name}' created successfully. Pending admin approval.",
                token=org_id,  # Return org_id as token
                role="owner"
            )
            
    except Exception as e:
        logger.error(f"Error creating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create organization: {str(e)}"
        )
