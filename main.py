#!/usr/bin/env python3
"""
Main entry point for the RAG API with authentication.
Initializes all databases and runs the FastAPI application.
"""

import asyncio
import uvicorn
import logging
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_databases():
    """Initialize all required databases"""
    logger.info("Initializing databases...")
    
    try:
        # Initialize user database
        from userdb import init_db as init_user_db
        await init_user_db()
        logger.info("✅ User database initialized")
        
        # Initialize organizations database
        from orgdb import init_org_db
        await init_org_db()
        logger.info("✅ Organizations database initialized")
        
        # Initialize metrics database (synchronous)
        from metricsdb import init_metrics_db
        init_metrics_db()
        logger.info("✅ Metrics database initialized")
        
        # Initialize reports database (synchronous)
        from reports_db import init_reports_db
        init_reports_db()
        logger.info("✅ Reports database initialized")
        
        # Initialize plugins database
        from plugin_manager import init_plugins_db
        await init_plugins_db()
        logger.info("✅ Plugins database initialized")
        
        # Initialize API keys database
        from api_keys import init_api_keys_db
        await init_api_keys_db()
        logger.info("✅ API Keys database initialized")
        
        # Initialize OpenCart catalog database
        from opencart_catalog import init_catalog_db
        await init_catalog_db()
        logger.info("✅ OpenCart catalog database initialized")
        
        # Initialize quiz database
        from quizdb import init_quiz_db
        await init_quiz_db()
        logger.info("✅ Quiz database initialized")
        
        # Initialize uploads database
        from uploadsdb import init_uploads_db
        await init_uploads_db()
        logger.info("✅ Uploads database initialized")
        
        # Initialize RAG databases
        sys.path.append(os.path.join(os.path.dirname(__file__), 'rag_api'))
        from rag_api.db_utils import create_application_logs, create_document_store
        create_application_logs()
        create_document_store()
        logger.info("✅ RAG databases initialized")
        
        # Initialize analytics database (without auto-population)
        from analytics_core import AnalyticsCore
        analytics = AnalyticsCore()
        logger.info("✅ Analytics database initialized")
        
        # Ensure required directories exist
        os.makedirs("uploads", exist_ok=True)
        os.makedirs("chroma_db", exist_ok=True)
        os.makedirs("data", exist_ok=True)
        logger.info("✅ Required directories created")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize databases: {e}")
        raise

async def main():
    """Main function to initialize databases and start the server"""
    try:
        # Initialize databases
        await init_databases()
        
        # Import the FastAPI app
        from api import app
        logger.info("✅ FastAPI app loaded successfully")
        
        # Start the server
        logger.info("🚀 Starting RAG API server on port 9001...")
        uvicorn.run(
            "api:app", 
            host="0.0.0.0", 
            port=9001, 
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
