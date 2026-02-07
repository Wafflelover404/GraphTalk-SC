#!/usr/bin/env python3
"""
Test script to validate CMS integration with main API
"""

import sys
import os
import asyncio

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Add landing-pages-api to path
cms_path = os.path.join(current_dir, 'landing-pages-api')
sys.path.insert(0, cms_path)

async def test_cms_integration():
    """Test CMS integration with main API"""
    print("🧪 Testing CMS Integration")
    print("=" * 50)
    
    try:
        # Test CMS router import
        print("\n1. Testing CMS Router Import...")
        from routers.cms import router as cms_router
        print("✅ CMS router imported successfully")
        
        # Test database import
        print("\n2. Testing Database Import...")
        from database import init_database
        print("✅ CMS database module imported successfully")
        
        # Test database initialization (dry run)
        print("\n3. Testing Database Initialization...")
        await init_database()
        print("✅ CMS database initialized successfully")
        
        # Show available endpoints
        print("\n4. Available CMS Endpoints:")
        for route in cms_router.routes:
            methods = list(route.methods)
            path = route.path
            print(f"   {methods} {path}")
        
        print("\n🎉 CMS Integration Test Complete!")
        print("✅ All components loaded successfully")
        print("📝 CMS endpoints will be available at /api/cms/*")
        
        return True
        
    except Exception as e:
        print(f"❌ CMS Integration Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_cms_integration())
    exit(0 if success else 1)
