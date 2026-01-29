from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import aiosqlite
import logging

from database import get_db_connection, dict_factory

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class Documentation(BaseModel):
    title: str
    slug: str
    content: str
    category: str
    difficulty: str = "beginner"
    read_time: Optional[str] = None
    order_index: int = 0

class DocumentationResponse(Documentation):
    id: int
    created_at: datetime
    updated_at: datetime

class DocCategory(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None

class QuickLink(BaseModel):
    title: str
    description: str
    icon: str
    link: str

# Documentation endpoints
@router.get("", response_model=List[DocumentationResponse])
async def get_documentation(
    category: Optional[str] = Query(None, description="Filter by category"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    search: Optional[str] = Query(None, description="Search in title and content"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get documentation with optional filtering"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Build query
        query = "SELECT * FROM documentation WHERE status = 'published'"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        
        if search:
            query += " AND (title LIKE ? OR content LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        query += " ORDER BY order_index ASC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        docs = await cursor.fetchall()
        
        return docs

@router.get("/{doc_id}", response_model=DocumentationResponse)
async def get_documentation_by_id(doc_id: int):
    """Get single documentation by ID"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM documentation WHERE id = ? AND status = 'published'",
            (doc_id,)
        )
        doc = await cursor.fetchone()
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documentation not found"
            )
        
        return doc

@router.get("/slug/{slug}", response_model=DocumentationResponse)
async def get_documentation_by_slug(slug: str):
    """Get single documentation by slug"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM documentation WHERE slug = ? AND status = 'published'",
            (slug,)
        )
        doc = await cursor.fetchone()
        
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Documentation not found"
            )
        
        return doc

# Categories endpoints
@router.get("/categories", response_model=List[DocCategory])
async def get_documentation_categories():
    """Get all documentation categories"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Get unique categories from documentation
        cursor = await db.execute(
            """
            SELECT DISTINCT category as name, LOWER(REPLACE(category, ' ', '-')) as slug,
                   'Documentation for ' || category as description
            FROM documentation 
            WHERE status = 'published'
            ORDER BY category
            """
        )
        categories = await cursor.fetchall()
        
        return categories

@router.get("/categories/{category}/docs")
async def get_docs_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get documentation by category"""
    return await get_documentation(category=category, limit=limit, offset=offset)

# Search endpoint
@router.get("/search")
async def search_documentation(
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Search documentation"""
    return await get_documentation(
        search=q, 
        category=category, 
        difficulty=difficulty,
        limit=limit, 
        offset=offset
    )

# Quick Links endpoint
@router.get("/quick-links")
async def get_quick_links():
    """Get quick links for documentation"""
    quick_links = [
        {
            "title": "API Reference",
            "description": "Complete API documentation",
            "icon": "code",
            "link": "/docs/api"
        },
        {
            "title": "SDKs & Libraries",
            "description": "Official SDKs for popular languages",
            "icon": "book-open",
            "link": "/docs/sdks"
        },
        {
            "title": "Changelog",
            "description": "Latest updates and releases",
            "icon": "file-text",
            "link": "/docs/changelog"
        },
        {
            "title": "Community",
            "description": "Join our developer community",
            "icon": "users",
            "link": "/community"
        }
    ]
    
    return quick_links

# Version Control endpoints
@router.get("/versions")
async def get_documentation_versions():
    """Get documentation versions"""
    # In a real implementation, this would return actual version data
    return {
        "current_version": "1.0.0",
        "versions": [
            {
                "version": "1.0.0",
                "release_date": "2024-01-01",
                "status": "current",
                "description": "Current stable version"
            },
            {
                "version": "0.9.0",
                "release_date": "2023-12-01",
                "status": "previous",
                "description": "Previous stable version"
            }
        ]
    }

@router.get("/changelog")
async def get_changelog():
    """Get changelog"""
    # In a real implementation, this would return actual changelog data
    changelog_entries = [
        {
            "version": "1.0.0",
            "release_date": "2024-01-01",
            "changes": [
                "Initial release of WikiAI documentation",
                "Added API reference documentation",
                "Added getting started guides"
            ]
        },
        {
            "version": "0.9.0",
            "release_date": "2023-12-01",
            "changes": [
                "Beta release documentation",
                "Added basic setup guides",
                "Added troubleshooting section"
            ]
        }
    ]
    
    return changelog_entries

# Analytics endpoint
@router.get("/analytics")
async def get_documentation_analytics():
    """Get documentation analytics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Total documentation
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total_docs,
                COUNT(DISTINCT category) as total_categories
            FROM documentation 
            WHERE status = 'published'
            """
        )
        total_stats = await cursor.fetchone()
        
        # Docs by category
        cursor = await db.execute(
            """
            SELECT 
                category,
                COUNT(*) as count
            FROM documentation 
            WHERE status = 'published'
            GROUP BY category
            ORDER BY count DESC
            """
        )
        category_stats = await cursor.fetchall()
        
        # Docs by difficulty
        cursor = await db.execute(
            """
            SELECT 
                difficulty,
                COUNT(*) as count
            FROM documentation 
            WHERE status = 'published'
            GROUP BY difficulty
            ORDER BY count DESC
            """
        )
        difficulty_stats = await cursor.fetchall()
        
        return {
            "total_docs": total_stats['total_docs'],
            "total_categories": total_stats['total_categories'],
            "category_stats": category_stats,
            "difficulty_stats": difficulty_stats
        }
