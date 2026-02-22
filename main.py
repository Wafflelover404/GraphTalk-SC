#!/usr/bin/env python3
"""
Main entry point for the RAG API application.
Runs the api.py from the src directory.
"""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run the main API
if __name__ == "__main__":
    import uvicorn
    from api import app
    
    # Run the application
    uvicorn.run(app, host="0.0.0.0", port=8000)
