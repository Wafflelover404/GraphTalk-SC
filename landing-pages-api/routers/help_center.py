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
class HelpArticle(BaseModel):
    title: str
    slug: str
    description: str
    content: str
    category: str
    read_time: Optional[str] = None
    difficulty: str = "beginner"
    order_index: int = 0

class HelpArticleResponse(HelpArticle):
    id: int
    views: int = 0
    helpful_count: int = 0
    total_votes: int = 0
    created_at: datetime
    updated_at: datetime

class VideoTutorial(BaseModel):
    title: str
    description: str
    video_url: str
    thumbnail_url: Optional[str] = None
    duration: str
    category: str

class HelpCategory(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    icon: Optional[str] = None
    order_index: int = 0

# Help Articles endpoints
@router.get("/articles")
async def get_help_articles(
    category: Optional[str] = Query(None, description="Filter by category"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get help articles with optional filtering"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Build query
        query = "SELECT * FROM help_articles WHERE status = 'published'"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        
        if search:
            query += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        query += " ORDER BY order_index ASC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        articles = await cursor.fetchall()
        
        return articles

@router.get("/articles/{article_id}", response_model=HelpArticleResponse)
async def get_help_article(article_id: int):
    """Get single help article by ID"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM help_articles WHERE id = ? AND status = 'published'",
            (article_id,)
        )
        article = await cursor.fetchone()
        
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Help article not found"
            )
        
        # Increment view count
        await db.execute(
            "UPDATE help_articles SET views = views + 1 WHERE id = ?",
            (article_id,)
        )
        await db.commit()
        
        return article

@router.get("/articles/slug/{slug}", response_model=HelpArticleResponse)
async def get_help_article_by_slug(slug: str):
    """Get single help article by slug"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM help_articles WHERE slug = ? AND status = 'published'",
            (slug,)
        )
        article = await cursor.fetchone()
        
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Help article not found"
            )
        
        # Increment view count
        await db.execute(
            "UPDATE help_articles SET views = views + 1 WHERE slug = ?",
            (slug,)
        )
        await db.commit()
        
        return article

@router.post("/articles/{article_id}/helpful")
async def mark_article_helpful(article_id: int, helpful: bool = True):
    """Mark article as helpful or not helpful"""
    async with aiosqlite.connect("landing_pages.db") as db:
        # Check if article exists
        cursor = await db.execute(
            "SELECT id FROM help_articles WHERE id = ? AND status = 'published'",
            (article_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Help article not found"
            )
        
        # Update helpful count
        if helpful:
            await db.execute(
                "UPDATE help_articles SET helpful_count = helpful_count + 1, total_votes = total_votes + 1 WHERE id = ?",
                (article_id,)
            )
        else:
            await db.execute(
                "UPDATE help_articles SET total_votes = total_votes + 1 WHERE id = ?",
                (article_id,)
            )
        
        await db.commit()
        
        return {"message": "Feedback recorded successfully", "helpful": helpful}

# Categories endpoints
@router.get("/categories", response_model=List[HelpCategory])
async def get_help_categories():
    """Get all help categories"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM help_categories ORDER BY order_index ASC, name ASC"
        )
        categories = await cursor.fetchall()
        
        return categories

@router.get("/categories/{category}/articles")
async def get_articles_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get articles by category"""
    return await get_help_articles(category=category, limit=limit, offset=offset)

# Video Tutorials endpoints
@router.get("/videos")
async def get_video_tutorials(
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get video tutorials"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        query = "SELECT * FROM video_tutorials WHERE status = 'published'"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        videos = await cursor.fetchall()
        
        return videos

@router.get("/videos/{video_id}")
async def get_video_tutorial(video_id: int):
    """Get single video tutorial"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM video_tutorials WHERE id = ? AND status = 'published'",
            (video_id,)
        )
        video = await cursor.fetchone()
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video tutorial not found"
            )
        
        # Increment view count
        await db.execute(
            "UPDATE video_tutorials SET views = views + 1 WHERE id = ?",
            (video_id,)
        )
        await db.commit()
        
        return video

# Popular Topics endpoints
@router.get("/popular-topics")
async def get_popular_topics():
    """Get popular help topics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Get most viewed articles
        cursor = await db.execute(
            """
            SELECT title, slug, views, category, helpful_count, total_votes
            FROM help_articles 
            WHERE status = 'published' AND views > 0
            ORDER BY views DESC 
            LIMIT 10
            """
        )
        popular_articles = await cursor.fetchall()
        
        # Get most helpful articles (highest helpful ratio)
        cursor = await db.execute(
            """
            SELECT title, slug, views, category, helpful_count, total_votes,
                   CASE 
                       WHEN total_votes > 0 THEN (helpful_count * 100.0 / total_votes)
                       ELSE 0
                   END as helpful_percentage
            FROM help_articles 
            WHERE status = 'published' AND total_votes >= 5
            ORDER BY helpful_percentage DESC 
            LIMIT 10
            """
        )
        most_helpful = await cursor.fetchall()
        
        return {
            "most_viewed": popular_articles,
            "most_helpful": most_helpful
        }

# Search endpoint
@router.get("/search")
async def search_help_articles(
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Search help articles"""
    return await get_help_articles(
        search=q, 
        category=category, 
        difficulty=difficulty,
        limit=limit, 
        offset=offset
    )

# Analytics endpoint
@router.get("/analytics")
async def get_help_analytics():
    """Get help center analytics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Total articles and views
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total_articles,
                SUM(views) as total_views,
                SUM(helpful_count) as total_helpful_votes,
                SUM(total_votes) as total_votes
            FROM help_articles 
            WHERE status = 'published'
            """
        )
        article_stats = await cursor.fetchone()
        
        # Articles by category
        cursor = await db.execute(
            """
            SELECT 
                category,
                COUNT(*) as count,
                SUM(views) as total_views
            FROM help_articles 
            WHERE status = 'published'
            GROUP BY category
            ORDER BY count DESC
            """
        )
        category_stats = await cursor.fetchall()
        
        # Articles by difficulty
        cursor = await db.execute(
            """
            SELECT 
                difficulty,
                COUNT(*) as count,
                SUM(views) as total_views
            FROM help_articles 
            WHERE status = 'published'
            GROUP BY difficulty
            ORDER BY count DESC
            """
        )
        difficulty_stats = await cursor.fetchall()
        
        # Video stats
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total_videos,
                SUM(views) as total_video_views
            FROM video_tutorials 
            WHERE status = 'published'
            """
        )
        video_stats = await cursor.fetchone()
        
        # Top articles
        cursor = await db.execute(
            """
            SELECT title, slug, views, helpful_count, total_votes
            FROM help_articles 
            WHERE status = 'published'
            ORDER BY views DESC 
            LIMIT 10
            """
        )
        top_articles = await cursor.fetchall()
        
        return {
            "article_stats": article_stats,
            "video_stats": video_stats,
            "category_stats": category_stats,
            "difficulty_stats": difficulty_stats,
            "top_articles": top_articles
        }
