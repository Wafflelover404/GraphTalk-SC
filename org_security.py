"""
Organization Security and Permission Management Module

Handles organization-level access control, ensuring users can only access
documents and perform operations within their organization context.
"""

import logging
from typing import Optional, Tuple
from fastapi import HTTPException, status

from orgdb import (
    verify_user_in_organization,
    get_organization_by_id,
    get_user_organization_role,
)

logger = logging.getLogger(__name__)


class OrganizationPermissionError(HTTPException):
    """Raised when user lacks organization permissions."""

    def __init__(
        self,
        message: str = "User does not have access to this organization",
        status_code: int = status.HTTP_403_FORBIDDEN,
    ):
        super().__init__(status_code=status_code, detail=message)


async def require_organization_access(
    username: str, organization_id: Optional[str]
) -> bool:
    """
    Enforce that a user has access to an organization.
    
    Args:
        username: The username to verify
        organization_id: The organization ID to check access for
        
    Raises:
        OrganizationPermissionError: If user lacks access to organization
        
    Returns:
        True if user has access
    """
    if not organization_id:
        raise OrganizationPermissionError(
            "Organization ID is required for this operation"
        )

    # Verify user is in the organization
    is_member = await verify_user_in_organization(username, organization_id)
    if not is_member:
        logger.warning(
            f"Unauthorized access attempt: user '{username}' "
            f"not in organization '{organization_id}'"
        )
        raise OrganizationPermissionError(
            f"User does not have access to organization {organization_id}"
        )

    return True


async def validate_organization_exists(organization_id: str) -> bool:
    """
    Verify that an organization exists.
    
    Args:
        organization_id: The organization ID to validate
        
    Raises:
        OrganizationPermissionError: If organization doesn't exist
        
    Returns:
        True if organization exists
    """
    if not organization_id:
        raise OrganizationPermissionError(
            "Organization ID is required",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    org = await get_organization_by_id(organization_id)
    if not org:
        logger.warning(f"Access attempt with invalid organization ID: {organization_id}")
        raise OrganizationPermissionError(
            f"Organization {organization_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return True


async def extract_org_from_user_tuple(user_tuple: Optional[Tuple]) -> Optional[str]:
    """
    Extract organization_id from user tuple returned by get_user_by_session_id.
    
    User tuple format: (id, username, password_hash, role, access_token, 
                        allowed_files, last_login, organization_id)
    
    Args:
        user_tuple: The user tuple from database
        
    Returns:
        The organization_id or None if not found
    """
    try:
        if user_tuple and len(user_tuple) >= 8:
            return user_tuple[-1]  # organization_id is the last element
    except (IndexError, TypeError):
        pass
    return None


def enforce_organization_context(
    user_tuple: Tuple, required: bool = True
) -> Optional[str]:
    """
    Extract and validate organization context from user session.
    
    Args:
        user_tuple: User tuple from authentication
        required: If True, raise error if org_id not found
        
    Returns:
        The organization_id
        
    Raises:
        HTTPException: If required org_id is missing
    """
    org_id = None
    try:
        if user_tuple and len(user_tuple) >= 8:
            org_id = user_tuple[-1]
    except (IndexError, TypeError):
        pass

    if required and not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context required. User must be part of an organization.",
        )

    return org_id


async def check_organization_admin(
    username: str, organization_id: str
) -> bool:
    """
    Check if a user is an admin or owner in an organization.
    
    Args:
        username: The username to check
        organization_id: The organization ID
        
    Returns:
        True if user is admin or owner
    """
    role = await get_user_organization_role(username, organization_id)
    return role in ("admin", "owner")


async def check_document_organization_access(
    username: str, organization_id: str, document_org_id: str
) -> bool:
    """
    Verify that a user can access a document within their organization.
    
    This ensures that:
    1. The user belongs to an organization
    2. The document belongs to that same organization
    
    Args:
        username: The user accessing the document
        organization_id: The user's organization
        document_org_id: The document's organization
        
    Returns:
        True if access is allowed
        
    Raises:
        OrganizationPermissionError: If access is denied
    """
    # First verify user belongs to their org
    is_member = await verify_user_in_organization(username, organization_id)
    if not is_member:
        raise OrganizationPermissionError(
            "User does not belong to the specified organization"
        )

    # Then verify document belongs to same org
    if document_org_id != organization_id:
        logger.warning(
            f"Cross-organization access attempt: user '{username}' from "
            f"org '{organization_id}' tried to access document from org '{document_org_id}'"
        )
        raise OrganizationPermissionError(
            "Document belongs to a different organization"
        )

    return True
