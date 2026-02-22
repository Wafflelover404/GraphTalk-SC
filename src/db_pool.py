import aiosqlite
import asyncio
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')

class DatabasePool:
    """SQLite connection pool for better concurrency"""
    
    def __init__(self, db_path: str, max_connections: int = 20):
        self.db_path = db_path
        self.max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the connection pool"""
        if self._initialized:
            return
        
        async with self._lock:
            if self._initialized:
                return
                
            # Create initial connections
            for _ in range(min(5, self.max_connections)):  # Start with 5 connections
                conn = await aiosqlite.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=30.0
                )
                await self._pool.put(conn)
            
            self._initialized = True
            logger.info(f"Database pool initialized with {min(5, self.max_connections)} connections")
    
    async def get_connection(self):
        """Get a connection from the pool"""
        await self.initialize()
        try:
            # Try to get existing connection
            conn = await asyncio.wait_for(self._pool.get(), timeout=5.0)
            return conn
        except asyncio.TimeoutError:
            # If pool is empty and not at max capacity, create new connection
            if self._pool.qsize() < self.max_connections:
                conn = await aiosqlite.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=30.0
                )
                return conn
            else:
                # Pool is full, wait for connection
                conn = await self._pool.get()
                return conn
    
    async def return_connection(self, conn):
        """Return a connection to the pool"""
        try:
            await self._pool.put(conn)
        except asyncio.QueueFull:
            # Pool is full, close the connection
            await conn.close()
    
    async def close_all(self):
        """Close all connections in the pool"""
        while not self._pool.empty():
            conn = await self._pool.get()
            await conn.close()
        self._initialized = False

# Global database pool instance
db_pool = DatabasePool(DB_PATH)

async def get_db_connection():
    """Get a database connection from the pool"""
    return await db_pool.get_connection()

async def return_db_connection(conn):
    """Return a database connection to the pool"""
    await db_pool.return_connection(conn)