"""
Plugin management system for organizations.
Handles plugin enablement, API tokens, and plugin configuration.
"""

import os
import uuid
import datetime
import aiosqlite
import logging
from typing import Optional, List, Dict, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "plugins.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


class PluginType(str, Enum):
    """Available plugins"""
    OPENCART = "opencart"
    DOCUMENTS = "documents"
    CUSTOM = "custom"


async def init_plugins_db():
    """Initialize plugins database."""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Organization plugins table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_plugins (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                plugin_type TEXT NOT NULL CHECK(plugin_type IN ('opencart', 'documents', 'custom')),
                is_enabled BOOLEAN DEFAULT 1,
                config JSON,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(organization_id, plugin_type),
                FOREIGN KEY (organization_id) REFERENCES organizations (id)
            )
            """
        )
        
        # Plugin tokens table (for OpenCart shops and external integrations)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plugin_tokens (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                plugin_type TEXT NOT NULL,
                plugin_resource_id TEXT,
                token TEXT NOT NULL UNIQUE,
                shop_name TEXT,
                shop_url TEXT,
                is_active BOOLEAN DEFAULT 1,
                last_used TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (organization_id) REFERENCES organizations (id)
            )
            """
        )
        
        # Plugin resource bindings (e.g., OpenCart shops to catalogs)
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plugin_resource_bindings (
                id TEXT PRIMARY KEY,
                organization_id TEXT NOT NULL,
                plugin_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                metadata JSON,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(organization_id, plugin_type, resource_id),
                FOREIGN KEY (organization_id) REFERENCES organizations (id)
            )
            """
        )
        
        await conn.commit()


async def enable_plugin(
    organization_id: str,
    plugin_type: str,
    config: Optional[Dict] = None
) -> str:
    """Enable a plugin for an organization."""
    plugin_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    config_str = str(config or {})
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO org_plugins 
            (id, organization_id, plugin_type, is_enabled, config, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (plugin_id, organization_id, plugin_type, config_str, now, now),
        )
        await conn.commit()
    
    logger.info(f"Plugin {plugin_type} enabled for org {organization_id}")
    return plugin_id


async def disable_plugin(organization_id: str, plugin_type: str) -> bool:
    """Disable a plugin for an organization."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            UPDATE org_plugins
            SET is_enabled = 0, updated_at = ?
            WHERE organization_id = ? AND plugin_type = ?
            """,
            (datetime.datetime.utcnow().isoformat(), organization_id, plugin_type),
        )
        await conn.commit()
    
    logger.info(f"Plugin {plugin_type} disabled for org {organization_id}")
    return True


async def is_plugin_enabled(organization_id: str, plugin_type: str) -> bool:
    """Check if a plugin is enabled for an organization."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT is_enabled FROM org_plugins
            WHERE organization_id = ? AND plugin_type = ?
            """,
            (organization_id, plugin_type),
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row and row[0])


async def list_enabled_plugins(organization_id: str) -> List[str]:
    """List all enabled plugins for an organization."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT plugin_type FROM org_plugins
            WHERE organization_id = ? AND is_enabled = 1
            """,
            (organization_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def create_plugin_token(
    organization_id: str,
    plugin_type: str,
    shop_name: Optional[str] = None,
    shop_url: Optional[str] = None,
    plugin_resource_id: Optional[str] = None
) -> str:
    """Create a new API token for a plugin resource (e.g., OpenCart shop)."""
    token_id = str(uuid.uuid4())
    token = str(uuid.uuid4()).replace("-", "")  # Generate a secure token
    now = datetime.datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO plugin_tokens
            (id, organization_id, plugin_type, plugin_resource_id, token, 
             shop_name, shop_url, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                token_id,
                organization_id,
                plugin_type,
                plugin_resource_id,
                token,
                shop_name,
                shop_url,
                now,
                now,
            ),
        )
        await conn.commit()
    
    logger.info(f"Plugin token created for {plugin_type} in org {organization_id}")
    return token


async def validate_plugin_token(token: str) -> Optional[Dict]:
    """Validate a plugin token and return its details."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT id, organization_id, plugin_type, plugin_resource_id, 
                   shop_name, shop_url, is_active, last_used
            FROM plugin_tokens
            WHERE token = ? AND is_active = 1
            """,
            (token,),
        ) as cursor:
            row = await cursor.fetchone()
            
            if row:
                # Update last_used timestamp
                await conn.execute(
                    """
                    UPDATE plugin_tokens
                    SET last_used = ?
                    WHERE token = ?
                    """,
                    (datetime.datetime.utcnow().isoformat(), token),
                )
                await conn.commit()
                
                return {
                    "id": row[0],
                    "organization_id": row[1],
                    "plugin_type": row[2],
                    "plugin_resource_id": row[3],
                    "shop_name": row[4],
                    "shop_url": row[5],
                    "is_active": bool(row[6]),
                    "last_used": row[7],
                }
    
    return None


async def revoke_plugin_token(token: str) -> bool:
    """Revoke a plugin token."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            UPDATE plugin_tokens
            SET is_active = 0, updated_at = ?
            WHERE token = ?
            """,
            (datetime.datetime.utcnow().isoformat(), token),
        )
        await conn.commit()
    
    logger.info(f"Plugin token revoked")
    return True


async def list_plugin_tokens(
    organization_id: str,
    plugin_type: Optional[str] = None
) -> List[Dict]:
    """List plugin tokens for an organization."""
    async with aiosqlite.connect(DB_PATH) as conn:
        if plugin_type:
            query = """
                SELECT id, plugin_type, plugin_resource_id, shop_name, shop_url,
                       is_active, last_used, created_at
                FROM plugin_tokens
                WHERE organization_id = ? AND plugin_type = ?
                ORDER BY created_at DESC
            """
            params = (organization_id, plugin_type)
        else:
            query = """
                SELECT id, plugin_type, plugin_resource_id, shop_name, shop_url,
                       is_active, last_used, created_at
                FROM plugin_tokens
                WHERE organization_id = ?
                ORDER BY created_at DESC
            """
            params = (organization_id,)
        
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "plugin_type": row[1],
                    "plugin_resource_id": row[2],
                    "shop_name": row[3],
                    "shop_url": row[4],
                    "is_active": bool(row[5]),
                    "last_used": row[6],
                    "created_at": row[7],
                }
                for row in rows
            ]


async def bind_plugin_resource(
    organization_id: str,
    plugin_type: str,
    resource_id: str,
    resource_name: str,
    resource_type: str,
    metadata: Optional[Dict] = None
) -> str:
    """Bind a plugin resource (e.g., OpenCart shop) to an organization."""
    binding_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    metadata_str = str(metadata or {})
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO plugin_resource_bindings
            (id, organization_id, plugin_type, resource_id, resource_name,
             resource_type, metadata, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                binding_id,
                organization_id,
                plugin_type,
                resource_id,
                resource_name,
                resource_type,
                metadata_str,
                now,
                now,
            ),
        )
        await conn.commit()
    
    logger.info(
        f"Resource {resource_type} {resource_id} bound to {plugin_type} in org {organization_id}"
    )
    return binding_id


async def get_org_plugin_resources(
    organization_id: str,
    plugin_type: str,
    resource_type: Optional[str] = None
) -> List[Dict]:
    """Get all resources of a type bound to a plugin in an organization."""
    async with aiosqlite.connect(DB_PATH) as conn:
        if resource_type:
            query = """
                SELECT id, resource_id, resource_name, resource_type, metadata, is_active
                FROM plugin_resource_bindings
                WHERE organization_id = ? AND plugin_type = ? AND resource_type = ?
                AND is_active = 1
            """
            params = (organization_id, plugin_type, resource_type)
        else:
            query = """
                SELECT id, resource_id, resource_name, resource_type, metadata, is_active
                FROM plugin_resource_bindings
                WHERE organization_id = ? AND plugin_type = ? AND is_active = 1
            """
            params = (organization_id, plugin_type)
        
        async with conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "resource_id": row[1],
                    "resource_name": row[2],
                    "resource_type": row[3],
                    "metadata": row[4],
                    "is_active": bool(row[5]),
                }
                for row in rows
            ]


async def get_organization_plugin_status(organization_id: str) -> Dict[str, bool]:
    """Get enabled/disabled status of all plugins for an organization."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT plugin_type, is_enabled FROM org_plugins
            WHERE organization_id = ?
            """,
            (organization_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0]: bool(row[1]) for row in rows}
