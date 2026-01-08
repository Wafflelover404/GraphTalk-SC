import aiosqlite
import os
import uuid
import datetime
from typing import Optional, List, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "organizations.db")


async def init_org_db():
    """Initialize organizations database with orgs and memberships."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organization_users (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('owner', 'admin', 'member')),
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                UNIQUE(organization_id, username),
                FOREIGN KEY (organization_id) REFERENCES organizations (id)
            )
            """
        )
        await conn.commit()


async def create_organization(name: str, slug: str) -> str:
    """Create a new organization and return its id."""
    org_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO organizations (id, name, slug, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (org_id, name, slug, now, now),
        )
        await conn.commit()
    return org_id


async def get_organization_by_slug(slug: str) -> Optional[Tuple]:
    """Return organization row for a given slug or None."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT id, name, slug, created_at, updated_at FROM organizations WHERE slug = ?",
            (slug,),
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else None


async def create_organization_membership(
    organization_id: str, username: str, role: str = "member"
) -> str:
    """Create a membership row for a user in an organization."""
    if role not in ("owner", "admin", "member"):
        raise ValueError("Role must be one of: owner, admin, member")

    membership_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT OR IGNORE INTO organization_users (
                id, organization_id, username, role, status, created_at
            ) VALUES (?, ?, ?, ?, 'active', ?)
            """,
            (membership_id, organization_id, username, role, now),
        )
        await conn.commit()
    return membership_id


async def list_user_organizations(username: str) -> List[Tuple]:
    """
    List organizations a user belongs to.
    Returns rows: (organization_id, name, slug, role, status).
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT o.id, o.name, o.slug, ou.role, ou.status
            FROM organizations o
            JOIN organization_users ou ON o.id = ou.organization_id
            WHERE ou.username = ?
            ORDER BY o.created_at ASC
            """,
            (username,),
        ) as cursor:
            rows = await cursor.fetchall()
            return rows or []


async def verify_user_in_organization(username: str, organization_id: str) -> bool:
    """
    Verify that a user belongs to an organization.
    
    Args:
        username: The username to verify
        organization_id: The organization ID to check membership
        
    Returns:
        True if user is an active member, False otherwise
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT id FROM organization_users
            WHERE username = ? AND organization_id = ? AND status = 'active'
            """,
            (username, organization_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def get_organization_by_id(org_id: str) -> Optional[Tuple]:
    """Get organization details by ID."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT id, name, slug, created_at, updated_at FROM organizations WHERE id = ?",
            (org_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else None


async def get_user_organization_role(username: str, organization_id: str) -> Optional[str]:
    """
    Get a user's role in a specific organization.
    
    Returns:
        The role ('owner', 'admin', 'member') or None if user is not in org
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT role FROM organization_users
            WHERE username = ? AND organization_id = ? AND status = 'active'
            """,
            (username, organization_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


