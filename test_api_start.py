import uvicorn
import sys
sys.path.insert(0, '.')
from api import app

# Try to start and immediately print status
import asyncio
async def check():
    from rag_api.elastic_client import health_check
    result = await health_check()
    print(f"ES Health: {result}")
    
asyncio.run(check())
