#!/usr/bin/env python3
"""
Start the main WikiAI API server with WebSocket support
"""
import asyncio
import uvicorn
import logging
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Start the main API server"""
    try:
        # Import the FastAPI app
        from api import app
        logger.info("✅ FastAPI app loaded successfully")
        
        # Check WebSocket endpoints
        ws_routes = [route for route in app.routes if hasattr(route, 'path') and 'ws' in route.path]
        logger.info(f"🔌 WebSocket endpoints: {[route.path for route in ws_routes]}")
        
        # Start the server
        logger.info("🚀 Starting WikiAI API server on port 9001...")
        logger.info("📡 WebSocket messaging available at: ws://127.0.0.1:9001/ws/messaging")
        logger.info("🔍 WebSocket query available at: ws://127.0.0.1:9001/ws/query")
        
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=9001, 
            reload=False,  # Don't use reload with WebSockets
            log_level="info"
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
