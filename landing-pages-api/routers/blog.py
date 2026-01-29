from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import aiosqlite
import json
import logging

from database import get_db_connection, dict_factory

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class BlogPost(BaseModel):
    title: str
    slug: str
    excerpt: Optional[str] = None
    content: str
    author: str
    category: str
    featured: bool = False
    tags: Optional[List[str]] = []
    image_url: Optional[str] = None
    read_time: Optional[str] = None
    status: str = "draft"

class BlogPostResponse(BlogPost):
    id: int
    views: int = 0
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class NewsletterSubscription(BaseModel):
    email: EmailStr
    preferences: Optional[dict] = {}

class BlogCategory(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    color: str = "#3b82f6"

# Blog Posts endpoints
@router.get("/posts", response_model=List[BlogPostResponse])
async def get_blog_posts(
    category: Optional[str] = Query(None, description="Filter by category"),
    featured: Optional[bool] = Query(None, description="Filter featured posts"),
    status: str = Query("published", description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Number of posts to return"),
    offset: int = Query(0, ge=0, description="Number of posts to skip"),
    search: Optional[str] = Query(None, description="Search in title and excerpt")
):
    """Get blog posts with optional filtering"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Build query
        query = "SELECT * FROM blog_posts WHERE 1=1"
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if featured is not None:
            query += " AND featured = ?"
            params.append(featured)
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if search:
            query += " AND (title LIKE ? OR excerpt LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        query += " ORDER BY published_at DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        posts = await cursor.fetchall()
        
        # Parse JSON fields
        for post in posts:
            if post.get('tags'):
                try:
                    post['tags'] = json.loads(post['tags'])
                except:
                    post['tags'] = []
            else:
                post['tags'] = []
        
        return posts

@router.get("/posts/{post_id}", response_model=BlogPostResponse)
async def get_blog_post(post_id: int):
    """Get a single blog post by ID"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM blog_posts WHERE id = ? AND status = 'published'",
            (post_id,)
        )
        post = await cursor.fetchone()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog post not found"
            )
        
        # Increment view count
        await db.execute(
            "UPDATE blog_posts SET views = views + 1 WHERE id = ?",
            (post_id,)
        )
        await db.commit()
        
        # Parse JSON fields
        if post.get('tags'):
            try:
                post['tags'] = json.loads(post['tags'])
            except:
                post['tags'] = []
        else:
            post['tags'] = []
        
        return post

@router.get("/posts/slug/{slug}", response_model=BlogPostResponse)
async def get_blog_post_by_slug(slug: str):
    """Get a single blog post by slug"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM blog_posts WHERE slug = ? AND status = 'published'",
            (slug,)
        )
        post = await cursor.fetchone()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blog post not found"
            )
        
        # Increment view count
        await db.execute(
            "UPDATE blog_posts SET views = views + 1 WHERE slug = ?",
            (slug,)
        )
        await db.commit()
        
        # Parse JSON fields
        if post.get('tags'):
            try:
                post['tags'] = json.loads(post['tags'])
            except:
                post['tags'] = []
        else:
            post['tags'] = []
        
        return post

@router.get("/posts/featured", response_model=List[BlogPostResponse])
async def get_featured_posts(limit: int = Query(5, ge=1, le=20)):
    """Get featured blog posts"""
    return await get_blog_posts(featured=True, limit=limit)

# Categories endpoints
@router.get("/categories", response_model=List[BlogCategory])
async def get_blog_categories():
    """Get all blog categories"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute("SELECT * FROM blog_categories ORDER BY name")
        categories = await cursor.fetchall()
        
        return categories

@router.get("/categories/{category}/posts", response_model=List[BlogPostResponse])
async def get_posts_by_category(
    category: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get posts by category"""
    return await get_blog_posts(category=category, limit=limit, offset=offset)

# Newsletter endpoints
@router.post("/subscribe")
async def subscribe_newsletter(subscription: NewsletterSubscription):
    """Subscribe to newsletter"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            await db.execute(
                """
                INSERT INTO newsletter_subscriptions (email, preferences, source)
                VALUES (?, ?, 'website')
                """,
                (subscription.email, json.dumps(subscription.preferences))
            )
            await db.commit()
            
            return {"message": "Successfully subscribed to newsletter"}
        
        except aiosqlite.IntegrityError:
            # Email already exists
            return {"message": "Email already subscribed"}
        
        except Exception as e:
            logger.error(f"Error subscribing to newsletter: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to subscribe to newsletter"
            )

@router.post("/unsubscribe")
async def unsubscribe_newsletter(email: EmailStr):
    """Unsubscribe from newsletter"""
    async with aiosqlite.connect("landing_pages.db") as db:
        cursor = await db.execute(
            "UPDATE newsletter_subscriptions SET status = 'unsubscribed', updated_at = CURRENT_TIMESTAMP WHERE email = ?",
            (email,)
        )
        await db.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not found in subscription list"
            )
        
        return {"message": "Successfully unsubscribed from newsletter"}

@router.get("/search")
async def search_blog_posts(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Search blog posts"""
    return await get_blog_posts(search=q, limit=limit, offset=offset)

# Analytics endpoint
@router.get("/analytics/views")
async def get_blog_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
):
    """Get blog analytics data"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Get total views
        cursor = await db.execute(
            "SELECT SUM(views) as total_views, COUNT(*) as total_posts FROM blog_posts WHERE status = 'published'"
        )
        total_stats = await cursor.fetchone()
        
        # Get top posts
        cursor = await db.execute(
            """
            SELECT id, title, slug, views, author, category 
            FROM blog_posts 
            WHERE status = 'published' 
            ORDER BY views DESC 
            LIMIT 10
            """
        )
        top_posts = await cursor.fetchall()
        
        # Get posts by category
        cursor = await db.execute(
            """
            SELECT category, COUNT(*) as count, SUM(views) as total_views
            FROM blog_posts 
            WHERE status = 'published'
            GROUP BY category
            ORDER BY count DESC
            """
        )
        category_stats = await cursor.fetchall()
        
        return {
            "total_views": total_stats['total_views'] or 0,
            "total_posts": total_stats['total_posts'] or 0,
            "top_posts": top_posts,
            "category_stats": category_stats
        }
