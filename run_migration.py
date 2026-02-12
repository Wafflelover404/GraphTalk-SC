#!/usr/bin/env python3
"""
Quick migration script to add missing columns to the api_keys database
Run this if the backend hasn't been restarted yet to apply schema changes.
"""

import asyncio
import sqlite3
import sys

DB_PATH = 'api_keys.db'

async def main():
    """Run database migration."""
    try:
        # Use sqlite3 to ensure the migration runs
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(api_keys)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        print(f"Found {len(existing_columns)} existing columns in api_keys table")
        print(f"Columns: {', '.join(sorted(existing_columns))}")
        
        # Define columns to add
        required_columns = {
            'status': "ALTER TABLE api_keys ADD COLUMN status TEXT DEFAULT 'active'",
            'priority_tier': "ALTER TABLE api_keys ADD COLUMN priority_tier TEXT DEFAULT 'standard'",
            'llm_enabled': "ALTER TABLE api_keys ADD COLUMN llm_enabled BOOLEAN DEFAULT 1",
            'llm_models_allowed': "ALTER TABLE api_keys ADD COLUMN llm_models_allowed TEXT DEFAULT 'gpt3.5,gpt4,claude'",
            'max_tokens_per_request': "ALTER TABLE api_keys ADD COLUMN max_tokens_per_request INTEGER DEFAULT 4000",
            'max_tokens_per_day': "ALTER TABLE api_keys ADD COLUMN max_tokens_per_day INTEGER DEFAULT 1000000",
            'ai_features_allowed': "ALTER TABLE api_keys ADD COLUMN ai_features_allowed TEXT DEFAULT 'search_enhancement,suggestions'",
            'current_llm_tokens_used': "ALTER TABLE api_keys ADD COLUMN current_llm_tokens_used INTEGER DEFAULT 0",
            'llm_cost_limit': "ALTER TABLE api_keys ADD COLUMN llm_cost_limit REAL DEFAULT 1000.0",
            'current_llm_cost': "ALTER TABLE api_keys ADD COLUMN current_llm_cost REAL DEFAULT 0.0",
            'llm_cost_reset_date': "ALTER TABLE api_keys ADD COLUMN llm_cost_reset_date TEXT",
            'allowed_ips': "ALTER TABLE api_keys ADD COLUMN allowed_ips TEXT",
            'ip_whitelist_enabled': "ALTER TABLE api_keys ADD COLUMN ip_whitelist_enabled BOOLEAN DEFAULT 0",
            'concurrent_requests_max': "ALTER TABLE api_keys ADD COLUMN concurrent_requests_max INTEGER DEFAULT 100",
            'batch_operation_max_size': "ALTER TABLE api_keys ADD COLUMN batch_operation_max_size INTEGER DEFAULT 1000",
            'storage_quota_gb': "ALTER TABLE api_keys ADD COLUMN storage_quota_gb REAL DEFAULT 100.0",
            'current_storage_used_gb': "ALTER TABLE api_keys ADD COLUMN current_storage_used_gb REAL DEFAULT 0.0",
            'reset_on': "ALTER TABLE api_keys ADD COLUMN reset_on TEXT DEFAULT 'daily_utc'",
            'usage_reset_time': "ALTER TABLE api_keys ADD COLUMN usage_reset_time TEXT",
            'quota_type': "ALTER TABLE api_keys ADD COLUMN quota_type TEXT DEFAULT 'requests'",
            'quota_warning_threshold': "ALTER TABLE api_keys ADD COLUMN quota_warning_threshold INTEGER DEFAULT 80",
            'current_usage': "ALTER TABLE api_keys ADD COLUMN current_usage INTEGER DEFAULT 0",
            'rate_limit_requests': "ALTER TABLE api_keys ADD COLUMN rate_limit_requests INTEGER DEFAULT 10000",
            'rate_limit_period': "ALTER TABLE api_keys ADD COLUMN rate_limit_period TEXT DEFAULT 'day'",
            'created_by': "ALTER TABLE api_keys ADD COLUMN created_by TEXT",
            'updated_at': "ALTER TABLE api_keys ADD COLUMN updated_at TEXT",
        }
        
        # Add missing columns
        added_count = 0
        for column_name, alter_statement in required_columns.items():
            if column_name not in existing_columns:
                try:
                    print(f"Adding column: {column_name}")
                    cursor.execute(alter_statement)
                    added_count += 1
                except sqlite3.OperationalError as e:
                    print(f"Warning: Could not add column {column_name}: {e}")
        
        conn.commit()
        conn.close()
        
        if added_count > 0:
            print(f"\n✅ Migration complete: added {added_count} columns")
        else:
            print(f"\n✅ Database schema is already up to date")
        
        return 0
        
    except Exception as e:
        print(f"❌ Migration failed: {e}", file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
