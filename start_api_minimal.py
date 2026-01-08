#!/usr/bin/env python3
"""
Minimal API startup script that bypasses RAG dependencies
"""
import asyncio
import uvicorn
import logging
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_minimal_databases():
    """Initialize only essential databases"""
    logger.info("Initializing minimal databases...")
    
    try:
        # Initialize user database
        from userdb import init_db as init_user_db
        await init_user_db()
        logger.info("✅ User database initialized")
        
        # Ensure required directories exist
        os.makedirs("uploads", exist_ok=True)
        logger.info("✅ Required directories created")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize databases: {e}")
        raise

async def main():
    """Main function to initialize databases and start server"""
    try:
        # Initialize databases
        await init_minimal_databases()
        
        # Import only the essential parts of the API
        import sys
        sys.path.append('.')
        
        # Mock the RAG imports to prevent errors
        import types
        rag_mock = types.ModuleType('rag_api')
        sys.modules['rag_api'] = rag_mock
        
        # Import the FastAPI app
        from api import app
        logger.info("✅ FastAPI app loaded successfully")
        
        # Start the server
        logger.info("🚀 Starting minimal API server on port 8000...")
        uvicorn.run(
            "api:app", 
            host="0.0.0.0", 
            port=8000, 
            reload=True,
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check if we're in an async context
    try:
        # If there's already a running event loop, create a task
        loop = asyncio.get_running_loop()
        loop.create_task(main())
    except RuntimeError:
        # No event loop running, create one
        asyncio.run(main())
