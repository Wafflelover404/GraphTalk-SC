import aiosqlite
import os
import uuid
import datetime
import ipaddress
from typing import Optional, List, Tuple, Dict, Any
import secrets
import logging
import json

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'api_keys.db')

# Enhanced permissions list
AVAILABLE_PERMISSIONS = {
    'search': 'Search knowledge base',
    'upload': 'Upload documents',
    'download': 'Download documents',
    'delete_documents': 'Delete documents from knowledge base',
    'parse_users': 'View user data',
    'edit_users': 'Modify users',
    'view_reports': 'Access analytics and reports',
    'manage_api_keys': 'Manage API keys',
    'generate_ai_response': 'Generate AI-powered responses',
    'use_advanced_llm': 'Use advanced LLM models',
    'moderate_content': 'Perform content moderation',
    'export_data': 'Export data in bulk',
    'admin': 'Full administrative access',
}

async def init_api_keys_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        # Main api_keys table with enhanced columns
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                key_id TEXT UNIQUE NOT NULL,
                key_hash TEXT NOT NULL,
                
                -- Basic info
                name TEXT NOT NULL,
                description TEXT,
                organization_id TEXT,
                created_by TEXT,
                
                -- Permissions
                permissions TEXT NOT NULL,
                
                -- Status
                is_active BOOLEAN DEFAULT TRUE,
                status TEXT DEFAULT 'active',
                
                -- Timestamps
                created_at TEXT NOT NULL,
                updated_at TEXT,
                last_used_at TEXT,
                expires_at TEXT,
                
                -- Rate Limiting & Quota
                rate_limit_requests INTEGER DEFAULT 10000,
                rate_limit_period TEXT DEFAULT 'day',
                quota_type TEXT DEFAULT 'requests',
                quota_warning_threshold INTEGER DEFAULT 80,
                reset_on TEXT DEFAULT 'daily_utc',
                current_usage INTEGER DEFAULT 0,
                usage_reset_time TEXT,
                
                -- LLM Control & Features
                llm_enabled BOOLEAN DEFAULT TRUE,
                llm_models_allowed TEXT DEFAULT 'gpt3.5,gpt4,claude',
                max_tokens_per_request INTEGER DEFAULT 4000,
                max_tokens_per_day INTEGER DEFAULT 1000000,
                ai_features_allowed TEXT DEFAULT 'search_enhancement,suggestions',
                llm_cost_limit REAL DEFAULT 1000.0,
                current_llm_tokens_used INTEGER DEFAULT 0,
                current_llm_cost REAL DEFAULT 0.0,
                llm_cost_reset_date TEXT,
                
                -- Security
                allowed_ips TEXT,
                ip_whitelist_enabled BOOLEAN DEFAULT FALSE,
                
                -- Key Lifecycle
                renewal_window_days INTEGER DEFAULT 14,
                auto_renew BOOLEAN DEFAULT FALSE,
                replacement_key_id TEXT,
                rotation_status TEXT,
                
                -- Resource Allocation
                concurrent_requests_max INTEGER DEFAULT 100,
                batch_operation_max_size INTEGER DEFAULT 1000,
                storage_quota_gb REAL DEFAULT 100.0,
                current_storage_used_gb REAL DEFAULT 0.0,
                priority_tier TEXT DEFAULT 'standard',
                
                -- Monitoring
                anomaly_score REAL DEFAULT 0.0,
                last_checked_at TEXT,
                
                FOREIGN KEY (organization_id) REFERENCES organizations (id)
            )
        ''')
        
        # Enhanced usage log table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS api_key_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                method TEXT,
                status_code INTEGER,
                response_time_ms REAL,
                request_size_bytes INTEGER,
                response_size_bytes INTEGER,
                llm_tokens_used INTEGER DEFAULT 0,
                ai_features_used TEXT,
                error_message TEXT,
                user_agent TEXT,
                ip_address TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (key_id) REFERENCES api_keys (key_id)
            )
        ''')
        
        # Quota tracking table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS api_key_quota_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT NOT NULL UNIQUE,
                tracking_period TEXT,
                usage_count INTEGER DEFAULT 0,
                llm_tokens INTEGER DEFAULT 0,
                llm_cost REAL DEFAULT 0.0,
                storage_used_gb REAL DEFAULT 0.0,
                last_reset TEXT,
                next_reset TEXT,
                FOREIGN KEY (key_id) REFERENCES api_keys (key_id)
            )
        ''')
        
        # Audit log table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS api_key_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                changes TEXT,
                changed_by TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT NOT NULL,
                reason TEXT,
                FOREIGN KEY (key_id) REFERENCES api_keys (key_id)
            )
        ''')
        
        await conn.commit()


async def create_api_key(
    name: str,
    permissions: List[str],
    organization_id: Optional[str] = None,
    created_by: Optional[str] = None,
    description: Optional[str] = None,
    expires_in_days: Optional[int] = None,
    expires_at: Optional[str] = None,
    # Rate limiting
    rate_limit_requests: int = 10000,
    rate_limit_period: str = 'day',
    quota_warning_threshold: int = 80,
    # LLM control
    llm_enabled: bool = True,
    llm_models_allowed: Optional[List[str]] = None,
    max_tokens_per_request: int = 4000,
    max_tokens_per_day: int = 1000000,
    ai_features_allowed: Optional[List[str]] = None,
    llm_cost_limit: float = 1000.0,
    # Resource allocation
    priority_tier: str = 'standard',
    concurrent_requests_max: int = 100,
    storage_quota_gb: float = 100.0,
) -> Tuple[str, str]:
    """Create a new API key with advanced features. Returns (full_key, key_id)."""
    
    key_id = secrets.token_hex(8)
    full_key = f"gk_{key_id}_{secrets.token_hex(16)}"
    key_hash = secrets.token_hex(32)
    permissions_str = ','.join(sorted(permissions))
    now = datetime.datetime.utcnow().isoformat()
    
    # Default LLM models and features
    llm_models_str = ','.join(llm_models_allowed) if llm_models_allowed else 'gpt3.5,gpt4,claude'
    ai_features_str = ','.join(ai_features_allowed) if ai_features_allowed else 'search_enhancement,suggestions'
    
    # Calculate expiration
    if expires_at is None and expires_in_days is not None:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=expires_in_days)
        expires_at = expires_at.isoformat()
    
    # Calculate usage reset time
    usage_reset_time = calculate_next_reset_time('daily_utc')

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO api_keys (
                id, key_id, key_hash, name, description, organization_id, 
                created_by, permissions, created_at, expires_at,
                rate_limit_requests, rate_limit_period, quota_warning_threshold,
                llm_enabled, llm_models_allowed, max_tokens_per_request, 
                max_tokens_per_day, ai_features_allowed, llm_cost_limit,
                priority_tier, concurrent_requests_max, storage_quota_gb,
                usage_reset_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()), key_id, key_hash, name, description, organization_id,
                created_by, permissions_str, now, expires_at,
                rate_limit_requests, rate_limit_period, quota_warning_threshold,
                int(llm_enabled), llm_models_str, max_tokens_per_request,
                max_tokens_per_day, ai_features_str, llm_cost_limit,
                priority_tier, concurrent_requests_max, storage_quota_gb,
                usage_reset_time
            ),
        )
        await conn.commit()
        
        # Log the creation in audit log
        await log_audit_event(key_id, 'KEY_CREATED', {'name': name, 'tier': priority_tier}, created_by)

    return full_key, key_id

# ============ Helper Functions ============

def calculate_next_reset_time(reset_on: str) -> str:
    """Calculate the next quota reset time based on the reset strategy."""
    now = datetime.datetime.utcnow()
    
    if reset_on == 'daily_utc':
        next_reset = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif reset_on == 'weekly_monday':
        days_ahead = 0 - now.weekday()  # Monday is 0
        if days_ahead <= 0:
            days_ahead += 7
        next_reset = now + datetime.timedelta(days=days_ahead)
        next_reset = next_reset.replace(hour=0, minute=0, second=0, microsecond=0)
    elif reset_on == 'monthly_1st':
        if now.month == 12:
            next_reset = datetime.datetime(now.year + 1, 1, 1)
        else:
            next_reset = datetime.datetime(now.year, now.month + 1, 1)
    else:
        next_reset = now + datetime.timedelta(days=1)
    
    return next_reset.isoformat()


def validate_ip_address(ip: str, allowed_ips_str: Optional[str]) -> bool:
    """Validate if an IP address is in the allowed list."""
    if not allowed_ips_str:
        return True
    
    try:
        client_ip = ipaddress.ip_address(ip)
        allowed_ips = allowed_ips_str.split(',')
        
        for allowed in allowed_ips:
            allowed = allowed.strip()
            if '/' in allowed:
                # CIDR notation
                if client_ip in ipaddress.ip_network(allowed, strict=False):
                    return True
            elif client_ip == ipaddress.ip_address(allowed):
                return True
        
        return False
    except ValueError:
        logger.error(f"Invalid IP format: {ip}")
        return False


async def check_rate_limit(key_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if an API key has exceeded its rate limit.
    Returns (is_allowed, info_dict)
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT rate_limit_requests, rate_limit_period, quota_warning_threshold, 
                   current_usage, usage_reset_time, status
            FROM api_keys WHERE key_id = ?
            """,
            (key_id,),
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                return False, {'error': 'Key not found'}
            
            limit, period, threshold, current_usage, reset_time, status = row
            
            if status != 'active':
                return False, {'error': 'Key is inactive'}
            
            # Check if reset time has passed
            now = datetime.datetime.utcnow()
            reset_dt = datetime.datetime.fromisoformat(reset_time)
            
            if now >= reset_dt:
                # Reset quota
                await reset_quota(key_id)
                current_usage = 0
            
            # Check against limit
            usage_percent = (current_usage / limit * 100) if limit > 0 else 0
            is_allowed = current_usage < limit
            
            return is_allowed, {
                'current_usage': current_usage,
                'limit': limit,
                'usage_percent': usage_percent,
                'warning_threshold': threshold,
                'is_warning': usage_percent >= threshold,
                'reset_time': reset_time
            }


async def increment_usage(key_id: str, amount: int = 1):
    """Increment usage counter for a key."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE api_keys SET current_usage = current_usage + ? WHERE key_id = ?",
            (amount, key_id),
        )
        await conn.commit()


async def reset_quota(key_id: str):
    """Reset quota for a key."""
    reset_time = calculate_next_reset_time('daily_utc')
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE api_keys SET current_usage = 0, usage_reset_time = ? WHERE key_id = ?",
            (reset_time, key_id),
        )
        await conn.commit()


async def check_llm_availability(key_id: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if a key can use LLM features and has remaining tokens.
    Returns (is_available, info_dict)
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT llm_enabled, llm_models_allowed, max_tokens_per_day, 
                   current_llm_tokens_used, llm_cost_limit, current_llm_cost,
                   llm_cost_reset_date, status
            FROM api_keys WHERE key_id = ?
            """,
            (key_id,),
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                return False, {'error': 'Key not found'}
            
            llm_enabled, models_str, max_tokens, tokens_used, cost_limit, current_cost, reset_date, status = row
            
            if status != 'active' or not llm_enabled:
                return False, {'error': 'LLM access disabled for this key'}
            
            # Check daily token limit
            tokens_remaining = max(0, max_tokens - tokens_used)
            
            # Check cost limit
            can_afford = current_cost < cost_limit
            
            models = models_str.split(',') if models_str else []
            
            return can_afford and tokens_remaining > 0, {
                'llm_enabled': llm_enabled,
                'models_allowed': models,
                'tokens_remaining': tokens_remaining,
                'tokens_used': tokens_used,
                'tokens_limit': max_tokens,
                'cost_remaining': max(0, cost_limit - current_cost),
                'current_cost': current_cost,
                'cost_limit': cost_limit,
                'can_afford': can_afford
            }


async def check_ip_whitelist(key_id: str, ip_address: str) -> Tuple[bool, str]:
    """
    Check if IP address is allowed for a key.
    Returns (is_allowed, reason)
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT allowed_ips, ip_whitelist_enabled
            FROM api_keys WHERE key_id = ?
            """,
            (key_id,),
        ) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                return False, 'Key not found'
            
            allowed_ips, whitelist_enabled = row
            
            if not whitelist_enabled:
                return True, 'IP whitelist disabled'
            
            if validate_ip_address(ip_address, allowed_ips):
                return True, 'IP allowed'
            else:
                return False, 'IP not in whitelist'


async def log_audit_event(
    key_id: str,
    event_type: str,
    changes: Optional[Dict] = None,
    changed_by: Optional[str] = None,
    ip_address: Optional[str] = None,
    reason: Optional[str] = None
):
    """Log an audit event for a key."""
    timestamp = datetime.datetime.utcnow().isoformat()
    changes_json = json.dumps(changes) if changes else None
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO api_key_audit_log 
            (key_id, event_type, changes, changed_by, ip_address, timestamp, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (key_id, event_type, changes_json, changed_by, ip_address, timestamp, reason)
        )
        await conn.commit()


async def log_usage_event(
    key_id: str,
    endpoint: str,
    method: str = 'GET',
    status_code: int = 200,
    response_time_ms: float = 0,
    llm_tokens_used: int = 0,
    error_message: Optional[str] = None,
    ip_address: Optional[str] = None,
    request_size_bytes: int = 0,
    response_size_bytes: int = 0
):
    """Log API key usage."""
    timestamp = datetime.datetime.utcnow().isoformat()
    
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO api_key_usage_log 
            (key_id, endpoint, method, status_code, response_time_ms, 
             llm_tokens_used, error_message, ip_address, timestamp, 
             request_size_bytes, response_size_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (key_id, endpoint, method, status_code, response_time_ms, 
             llm_tokens_used, error_message, ip_address, timestamp,
             request_size_bytes, response_size_bytes)
        )
        await conn.commit()


# ============ Main API Key Functions ============
    """Validate an API key and return its details if valid."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT id, key_id, key_hash, name, organization_id, permissions, is_active, created_at, last_used_at, expires_at
            FROM api_keys WHERE key_id = ? AND is_active = 1
            """,
            (key_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'key_id': row[1],
                    'key_hash': row[2],
                    'name': row[3],
                    'organization_id': row[4],
                    'permissions': row[5].split(',') if row[5] else [],
                    'is_active': bool(row[6]),
                    'created_at': row[7],
                    'last_used_at': row[8],
                    'expires_at': row[9],
                }
            return None


async def check_api_key_permission(key_id: str, required_permission: str) -> bool:
    """Check if an API key has a specific permission."""
    key_data = await validate_api_key(key_id)
    if not key_data:
        return False
    permissions = key_data.get('permissions', [])
    if 'admin' in permissions:
        return True
    return required_permission in permissions


async def revoke_api_key(key_id: str) -> bool:
    """Revoke an API key by setting is_active to False."""
    async with aiosqlite.connect(DB_PATH) as conn:
        result = await conn.execute(
            "UPDATE api_keys SET is_active = 0 WHERE key_id = ?",
            (key_id,),
        )
        await conn.commit()
        return result.rowcount > 0


async def delete_api_key(id: str) -> bool:
    """Delete an API key from the database by internal id."""
    async with aiosqlite.connect(DB_PATH) as conn:
        result = await conn.execute(
            "DELETE FROM api_keys WHERE id = ?",
            (id,),
        )
        await conn.commit()
        return result.rowcount > 0


async def list_api_keys(organization_id: Optional[str] = None) -> List[dict]:
    """List all API keys, optionally filtered by organization."""
    async with aiosqlite.connect(DB_PATH) as conn:
        if organization_id:
            async with conn.execute(
                """
                SELECT id, key_id, name, description, organization_id, permissions, is_active, created_at, last_used_at, expires_at
                FROM api_keys WHERE organization_id = ?
                ORDER BY created_at DESC
                """,
                (organization_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with conn.execute(
                """
                SELECT id, key_id, name, description, organization_id, permissions, is_active, created_at, last_used_at, expires_at
                FROM api_keys ORDER BY created_at DESC
                """
            ) as cursor:
                rows = await cursor.fetchall()

        return [
            {
                'id': row[0],
                'key_id': row[1],
                'name': row[2],
                'description': row[3],
                'organization_id': row[4],
                'permissions': row[5].split(',') if row[5] else [],
                'is_active': bool(row[6]),
                'created_at': row[7],
                'last_used_at': row[8],
                'expires_at': row[9],
            }
            for row in rows
        ]


async def get_api_key_details(id: str) -> Optional[dict]:
    """Get detailed information about an API key by internal id."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT id, key_id, key_hash, name, description, organization_id, permissions, is_active, created_at, last_used_at, expires_at
            FROM api_keys WHERE id = ?
            """,
            (id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'key_id': row[1],
                    'key_hash': row[2],
                    'name': row[3],
                    'description': row[4],
                    'organization_id': row[5],
                    'permissions': row[6].split(',') if row[6] else [],
                    'is_active': bool(row[7]),
                    'created_at': row[8],
                    'last_used_at': row[9],
                    'expires_at': row[10],
                }
            return None


async def get_api_key_details_by_key_id(key_id: str, organization_id: Optional[str] = None) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        if organization_id:
            async with conn.execute(
                """
                SELECT id, key_id, key_hash, name, description, organization_id, permissions, is_active, created_at, last_used_at, expires_at
                FROM api_keys WHERE key_id = ? AND organization_id = ?
                """,
                (key_id, organization_id),
            ) as cursor:
                row = await cursor.fetchone()
        else:
            async with conn.execute(
                """
                SELECT id, key_id, key_hash, name, description, organization_id, permissions, is_active, created_at, last_used_at, expires_at
                FROM api_keys WHERE key_id = ?
                """,
                (key_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'key_id': row[1],
                'key_hash': row[2],
                'name': row[3],
                'description': row[4],
                'organization_id': row[5],
                'permissions': row[6].split(',') if row[6] else [],
                'is_active': bool(row[7]),
                'created_at': row[8],
                'last_used_at': row[9],
                'expires_at': row[10],
            }
        return None


async def delete_api_key_by_key_id(key_id: str, organization_id: Optional[str] = None) -> bool:
    async with aiosqlite.connect(DB_PATH) as conn:
        if organization_id:
            result = await conn.execute(
                "DELETE FROM api_keys WHERE key_id = ? AND organization_id = ?",
                (key_id, organization_id),
            )
        else:
            result = await conn.execute(
                "DELETE FROM api_keys WHERE key_id = ?",
                (key_id,),
            )
        await conn.commit()
        return result.rowcount > 0


async def update_api_key(
    key_id: str,
    name: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
    expires_at: Optional[str] = None
) -> bool:
    """Update an API key's properties."""
    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if permissions is not None:
        updates.append("permissions = ?")
        params.append(','.join(sorted(permissions)))
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(int(is_active))
    if expires_at is not None:
        updates.append("expires_at = ?")
        params.append(expires_at)

    if not updates:
        return False

    params.append(key_id)

    async with aiosqlite.connect(DB_PATH) as conn:
        result = await conn.execute(
            f"UPDATE api_keys SET {', '.join(updates)} WHERE key_id = ?",
            params,
        )
        await conn.commit()
        return result.rowcount > 0


async def update_api_key_by_key_id(
    key_id: str,
    organization_id: str,
    name: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    is_active: Optional[bool] = None,
    expires_at: Optional[str] = None
) -> bool:
    """Update an API key's properties by key_id with organization validation."""
    updates = []
    params = []

    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if permissions is not None:
        updates.append("permissions = ?")
        params.append(','.join(sorted(permissions)))
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(int(is_active))
    if expires_at is not None:
        updates.append("expires_at = ?")
        params.append(expires_at)

    if not updates:
        return False

    params.append(key_id)
    params.append(organization_id)

    async with aiosqlite.connect(DB_PATH) as conn:
        result = await conn.execute(
            f"UPDATE api_keys SET {', '.join(updates)} WHERE key_id = ? AND organization_id = ?",
            params,
        )
        await conn.commit()
        return result.rowcount > 0


async def update_api_key_last_used(key_id: str):
    """Update the last used timestamp for an API key."""
    now = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            "UPDATE api_keys SET last_used_at = ? WHERE key_id = ?",
            (now, key_id),
        )
        await conn.commit()


async def log_api_key_usage(
    key_id: str,
    endpoint: str,
    status_code: int,
    response_time_ms: float
):
    """Log API key usage for monitoring."""
    timestamp = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO api_key_usage_log (key_id, endpoint, timestamp, status_code, response_time_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key_id, endpoint, timestamp, status_code, response_time_ms),
        )
        await conn.commit()
