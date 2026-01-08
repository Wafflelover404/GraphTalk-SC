#!/usr/bin/env python3
"""
Quick script to wipe databases and create test data with organization context
"""
import asyncio
import sqlite3
import uuid
from datetime import datetime, timedelta
from userdb import init_db, create_user
from orgdb import init_org_db, create_organization
from analytics_core import get_analytics_core, QueryMetrics, QueryType

async def setup_test_data():
    # Wipe databases
    import os
    db_files = ['users.db', 'organizations.db', 'analytics.db', 'documents.db', 'reports.db', 'uploads.db', 'plugins.db', 'metrics.db']
    for f in db_files:
        if os.path.exists(f):
            os.remove(f)
            print(f"Removed {f}")
    
    # Initialize databases
    await init_db()
    await init_org_db()
    analytics = get_analytics_core()
    
    # Create test organization
    org_id = 'org-test-123'
    created_org_id = await create_organization('Test Organization', 'test-org')
    print(f'Created organization: {created_org_id}')
    
    # Use the generated org ID
    org_id = created_org_id
    
    # Create test users
    test_users = [
        ('alice', 'alice123', 'admin'),
        ('bob', 'bob123', 'user'),
        ('charlie', 'charlie123', 'user')
    ]
    
    for username, password, role in test_users:
        success = await create_user(username, password, role=role, organization_id=org_id)
        if success:
            print(f'Created user: {username} ({role}) in org {org_id}')
        else:
            print(f'User {username} already exists')
    
    # Generate sample analytics data
    print('Generating sample analytics data...')
    now = datetime.now()
    
    # Sample queries for different users
    sample_queries = [
        ('alice', 'What are our Q4 sales figures?', 850, 1200),
        ('bob', 'How do I reset my password?', 320, 450),
        ('charlie', 'What is the return policy?', 280, 380),
        ('alice', 'Show me inventory reports', 1200, 1800),
        ('bob', 'Customer service contact info', 150, 220),
        ('charlie', 'Product catalog overview', 950, 1400),
        ('alice', 'Marketing budget analysis', 2100, 3200),
        ('bob', 'Employee handbook', 180, 260),
        ('charlie', 'Shipping information', 220, 310),
        ('alice', 'Financial summary', 1650, 2400),
    ]
    
    for i, (username, question, response_time, answer_length) in enumerate(sample_queries):
        timestamp = now - timedelta(hours=i*2)
        
        metrics = QueryMetrics(
            query_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            user_id=username,
            role='user',
            question=question,
            answer_length=answer_length,
            model_type='gpt-4',
            query_type=QueryType.RAG_SEARCH,
            response_time_ms=response_time,
            organization_id=org_id,
            answer_preview=f"Answer to: {question[:30]}...",
            timestamp=timestamp.isoformat()
        )
        
        analytics.log_query(metrics)
    
    print(f'Generated {len(sample_queries)} sample queries')
    print('Test data setup complete!')
    
    # Print login info
    print('\n=== Login Credentials ===')
    print('Admin: alice / alice123')
    print('Users: bob / bob123, charlie / charlie123')
    print('Organization ID:', org_id)
    print('========================')

if __name__ == '__main__':
    import aiosqlite
    asyncio.run(setup_test_data())
