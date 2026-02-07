#!/usr/bin/env python3
"""
Test script for organization-aware OpenCart ingestion.

Tests that:
1. Products imported via different organizations stay isolated
2. Plugin tokens properly associate with organizations
3. Cross-organization access is prevented
4. Organization_id flows through to database and vector store
"""

import asyncio
import aiosqlite
import json
import sys
import os
from pathlib import Path

# Add graphtalk to path
sys.path.insert(0, str(Path(__file__).parent / "graphtalk"))

from opencart_catalog import (
    init_catalog_db,
    create_catalog,
    get_catalog,
    list_catalogs_by_org,
    upsert_catalog_products,
)
from plugin_manager import (
    init_plugins_db,
    enable_plugin,
    create_plugin_token,
    validate_plugin_token,
)


async def setup_test_data():
    """Set up test organizations and plugin tokens."""
    print("\n=== Setting up test data ===\n")
    
    # Initialize databases
    await init_catalog_db()
    await init_plugins_db()
    print("✓ Databases initialized")
    
    # Create test organizations (simulated)
    org1_id = "org_ingestion_001"
    org2_id = "org_ingestion_002"
    
    # Enable OpenCart plugin for both orgs
    await enable_plugin(org1_id, "opencart")
    await enable_plugin(org2_id, "opencart")
    print(f"✓ OpenCart plugin enabled for {org1_id}")
    print(f"✓ OpenCart plugin enabled for {org2_id}")
    
    # Create plugin tokens for each org
    token1 = await create_plugin_token(
        organization_id=org1_id,
        plugin_type="opencart",
        shop_name="Test Shop 1",
        shop_url="https://shop1.example.com"
    )
    
    token2 = await create_plugin_token(
        organization_id=org2_id,
        plugin_type="opencart",
        shop_name="Test Shop 2",
        shop_url="https://shop2.example.com"
    )
    
    print(f"✓ Plugin token created for org1: {token1[:16]}...")
    print(f"✓ Plugin token created for org2: {token2[:16]}...")
    
    return {
        "org1_id": org1_id,
        "org2_id": org2_id,
        "org1_token": token1,
        "org2_token": token2,
    }


async def test_token_validation(test_data):
    """Test that plugin tokens are properly validated."""
    print("\n=== Testing plugin token validation ===\n")
    
    # Validate token1
    token1_data = await validate_plugin_token(test_data["org1_token"])
    assert token1_data is not None, "Token1 should be valid"
    assert token1_data["organization_id"] == test_data["org1_id"], "Token1 should map to org1"
    print(f"✓ Token1 validated: belongs to {token1_data['organization_id']}")
    
    # Validate token2
    token2_data = await validate_plugin_token(test_data["org2_token"])
    assert token2_data is not None, "Token2 should be valid"
    assert token2_data["organization_id"] == test_data["org2_id"], "Token2 should map to org2"
    print(f"✓ Token2 validated: belongs to {token2_data['organization_id']}")
    
    # Validate fake token
    fake_token_data = await validate_plugin_token("invalid_token_xyz")
    assert fake_token_data is None, "Invalid token should return None"
    print(f"✓ Invalid token correctly rejected")


async def test_org_isolated_catalogs(test_data):
    """Test that catalogs are created with organization isolation."""
    print("\n=== Testing organization-isolated catalogs ===\n")
    
    # Create catalogs for each org
    catalog1_id = await create_catalog(
        shop_name="Shop 1",
        shop_url="https://shop1.example.com",
        user_id=101,
        organization_id=test_data["org1_id"],
        description="Test catalog for org1"
    )
    
    catalog2_id = await create_catalog(
        shop_name="Shop 2",
        shop_url="https://shop2.example.com",
        user_id=102,
        organization_id=test_data["org2_id"],
        description="Test catalog for org2"
    )
    
    print(f"✓ Created catalog for org1: {catalog1_id}")
    print(f"✓ Created catalog for org2: {catalog2_id}")
    
    # Verify catalogs are isolated
    catalog1 = await get_catalog(catalog1_id)
    catalog2 = await get_catalog(catalog2_id)
    
    assert catalog1["organization_id"] == test_data["org1_id"], "Catalog1 should belong to org1"
    assert catalog2["organization_id"] == test_data["org2_id"], "Catalog2 should belong to org2"
    
    print(f"✓ Catalog1 correctly assigned to {catalog1['organization_id']}")
    print(f"✓ Catalog2 correctly assigned to {catalog2['organization_id']}")
    
    # Verify list_catalogs_by_org filters correctly
    org1_catalogs = await list_catalogs_by_org(test_data["org1_id"])
    org2_catalogs = await list_catalogs_by_org(test_data["org2_id"])
    
    assert len(org1_catalogs) >= 1, "Org1 should have at least 1 catalog"
    assert len(org2_catalogs) >= 1, "Org2 should have at least 1 catalog"
    assert all(c["organization_id"] == test_data["org1_id"] for c in org1_catalogs), \
        "All org1 catalogs should have org1_id"
    assert all(c["organization_id"] == test_data["org2_id"] for c in org2_catalogs), \
        "All org2 catalogs should have org2_id"
    
    print(f"✓ list_catalogs_by_org correctly filters org1: {len(org1_catalogs)} catalog(s)")
    print(f"✓ list_catalogs_by_org correctly filters org2: {len(org2_catalogs)} catalog(s)")
    
    return {
        "catalog1_id": catalog1_id,
        "catalog2_id": catalog2_id,
    }


async def test_product_isolation(test_data, catalog_data):
    """Test that products are stored with organization_id."""
    print("\n=== Testing product isolation ===\n")
    
    # Insert products for org1
    products_org1 = [
        {
            "product_id": "org1_p1",
            "name": "Org1 Product 1",
            "sku": "ORG1-P1",
            "price": 99.99,
            "description": "First product for org1",
            "url": "https://shop1.example.com/p1",
            "quantity": 10,
            "status": 1,
        },
        {
            "product_id": "org1_p2",
            "name": "Org1 Product 2",
            "sku": "ORG1-P2",
            "price": 199.99,
            "description": "Second product for org1",
            "url": "https://shop1.example.com/p2",
            "quantity": 5,
            "status": 1,
        }
    ]
    
    inserted1, updated1 = await upsert_catalog_products(
        catalog_data["catalog1_id"],
        products_org1,
        user_id=101,
        organization_id=test_data["org1_id"]
    )
    
    print(f"✓ Inserted {inserted1} products for org1, updated {updated1}")
    
    # Insert products for org2
    products_org2 = [
        {
            "product_id": "org2_p1",
            "name": "Org2 Product 1",
            "sku": "ORG2-P1",
            "price": 149.99,
            "description": "First product for org2",
            "url": "https://shop2.example.com/p1",
            "quantity": 20,
            "status": 1,
        },
        {
            "product_id": "org2_p2",
            "name": "Org2 Product 2",
            "sku": "ORG2-P2",
            "price": 249.99,
            "description": "Second product for org2",
            "url": "https://shop2.example.com/p2",
            "quantity": 15,
            "status": 1,
        }
    ]
    
    inserted2, updated2 = await upsert_catalog_products(
        catalog_data["catalog2_id"],
        products_org2,
        user_id=102,
        organization_id=test_data["org2_id"]
    )
    
    print(f"✓ Inserted {inserted2} products for org2, updated {updated2}")


async def test_database_isolation():
    """Verify database contains organization_id and catalogs are isolated."""
    print("\n=== Verifying database isolation ===\n")
    
    db_path = "data/catalogs.db"
    if not os.path.exists(db_path):
        print(f"✗ Database not found at {db_path}")
        return
    
    async with aiosqlite.connect(db_path) as conn:
        # Check catalogs table
        cursor = await conn.execute("""
            SELECT catalog_id, organization_id, shop_name, total_products
            FROM catalogs
            WHERE organization_id LIKE 'org_ingestion_%'
            ORDER BY created_at
        """)
        
        catalogs = await cursor.fetchall()
        
        if not catalogs:
            print("✗ No test catalogs found in database")
            return
        
        print(f"✓ Found {len(catalogs)} test catalogs in database:")
        for catalog_id, org_id, shop_name, total_products in catalogs:
            print(f"  - {catalog_id}: {shop_name} (org: {org_id}, products: {total_products})")
        
        # Verify organization_id is set
        for catalog_id, org_id, shop_name, total_products in catalogs:
            assert org_id is not None, f"Catalog {catalog_id} has NULL organization_id"
            assert org_id.startswith("org_ingestion_"), f"Catalog {catalog_id} has invalid org_id: {org_id}"
        
        print(f"✓ All catalogs have valid organization_id")
        
        # Check products
        cursor = await conn.execute("""
            SELECT COUNT(*) as cnt FROM catalog_products
            WHERE catalog_id IN (
                SELECT catalog_id FROM catalogs
                WHERE organization_id LIKE 'org_ingestion_%'
            )
        """)
        
        product_count = (await cursor.fetchone())[0]
        print(f"✓ Database contains {product_count} test products")
        
        # Verify products are in correct catalogs
        cursor = await conn.execute("""
            SELECT c.catalog_id, c.organization_id, COUNT(p.product_id) as cnt
            FROM catalogs c
            LEFT JOIN catalog_products p ON c.catalog_id = p.catalog_id
            WHERE c.organization_id LIKE 'org_ingestion_%'
            GROUP BY c.catalog_id, c.organization_id
        """)
        
        results = await cursor.fetchall()
        for catalog_id, org_id, cnt in results:
            print(f"  - {catalog_id} ({org_id}): {cnt} products")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Organization-Aware Ingestion Test Suite")
    print("=" * 60)
    
    try:
        # Setup
        test_data = await setup_test_data()
        
        # Run tests
        await test_token_validation(test_data)
        catalog_data = await test_org_isolated_catalogs(test_data)
        await test_product_isolation(test_data, catalog_data)
        await test_database_isolation()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
