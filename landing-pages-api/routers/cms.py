from fastapi import APIRouter, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import aiosqlite
import json
import logging
import os
import uuid

from database import get_db_connection, dict_factory

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for CMS operations
class BlogPostCreate(BaseModel):
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

class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    featured: Optional[bool] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = None
    read_time: Optional[str] = None
    status: Optional[str] = None

class HelpArticleCreate(BaseModel):
    title: str
    slug: str
    description: str
    content: str
    category: str
    read_time: Optional[str] = None
    difficulty: str = "beginner"
    order_index: int = 0
    status: str = "draft"

class HelpArticleUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    read_time: Optional[str] = None
    difficulty: Optional[str] = None
    order_index: Optional[int] = None
    status: Optional[str] = None

# Blog Management
@router.get("/blog/posts")
async def get_blog_posts():
    """Get all blog posts"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM blog_posts ORDER BY created_at DESC"
        )
        posts = await cursor.fetchall()
        
        # Parse JSON fields
        for post in posts:
            if post.get('tags'):
                try:
                    import json
                    post['tags'] = json.loads(post['tags'])
                except:
                    post['tags'] = []
            else:
                post['tags'] = []
        
        return posts

@router.post("/blog/posts")
async def create_blog_post(post: BlogPostCreate):
    """Create a new blog post"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            cursor = await db.execute(
                """
                INSERT INTO blog_posts 
                (title, slug, excerpt, content, author, category, featured, tags, 
                 image_url, read_time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.title,
                    post.slug,
                    post.excerpt,
                    post.content,
                    post.author,
                    post.category,
                    post.featured,
                    json.dumps(post.tags),
                    post.image_url,
                    post.read_time,
                    post.status
                )
            )
            
            post_id = cursor.lastrowid
            await db.commit()
            
            logger.info(f"Blog post created: ID {post_id}, Title: {post.title}")
            
            return {
                "message": "Blog post created successfully",
                "post_id": post_id
            }
            
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint failed: blog_posts.slug" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Slug already exists"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database constraint violation"
            )
        except Exception as e:
            logger.error(f"Error creating blog post: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create blog post"
            )

@router.put("/blog/posts/{post_id}")
async def update_blog_post(post_id: int, post: BlogPostUpdate):
    """Update a blog post"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            # Check if post exists
            cursor = await db.execute(
                "SELECT id FROM blog_posts WHERE id = ?",
                (post_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Blog post not found"
                )
            
            # Build update query dynamically
            update_fields = []
            params = []
            
            for field, value in post.dict(exclude_unset=True).items():
                if field == "tags" and value is not None:
                    update_fields.append(f"{field} = ?")
                    params.append(json.dumps(value))
                elif value is not None:
                    update_fields.append(f"{field} = ?")
                    params.append(value)
            
            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(post_id)
                
                query = f"UPDATE blog_posts SET {', '.join(update_fields)} WHERE id = ?"
                await db.execute(query, params)
                await db.commit()
                
                logger.info(f"Blog post updated: ID {post_id}")
            
            return {"message": "Blog post updated successfully"}
            
        except Exception as e:
            logger.error(f"Error updating blog post: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update blog post"
            )

@router.delete("/blog/posts/{post_id}")
async def delete_blog_post(post_id: int):
    """Delete a blog post"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            cursor = await db.execute(
                "DELETE FROM blog_posts WHERE id = ?",
                (post_id,)
            )
            
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Blog post not found"
                )
            
            await db.commit()
            
            logger.info(f"Blog post deleted: ID {post_id}")
            
            return {"message": "Blog post deleted successfully"}
            
        except Exception as e:
            logger.error(f"Error deleting blog post: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete blog post"
            )

# Help Articles Management
@router.post("/help/articles")
async def create_help_article(article: HelpArticleCreate):
    """Create a new help article"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            cursor = await db.execute(
                """
                INSERT INTO help_articles 
                (title, slug, description, content, category, read_time, 
                 difficulty, order_index, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.title,
                    article.slug,
                    article.description,
                    article.content,
                    article.category,
                    article.read_time,
                    article.difficulty,
                    article.order_index,
                    article.status
                )
            )
            
            article_id = cursor.lastrowid
            await db.commit()
            
            logger.info(f"Help article created: ID {article_id}, Title: {article.title}")
            
            return {
                "message": "Help article created successfully",
                "article_id": article_id
            }
            
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint failed: help_articles.slug" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Slug already exists"
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database constraint violation"
            )
        except Exception as e:
            logger.error(f"Error creating help article: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create help article"
            )

@router.put("/help/articles/{article_id}")
async def update_help_article(article_id: int, article: HelpArticleUpdate):
    """Update a help article"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            # Check if article exists
            cursor = await db.execute(
                "SELECT id FROM help_articles WHERE id = ?",
                (article_id,)
            )
            if not await cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Help article not found"
                )
            
            # Build update query dynamically
            update_fields = []
            params = []
            
            for field, value in article.dict(exclude_unset=True).items():
                if value is not None:
                    update_fields.append(f"{field} = ?")
                    params.append(value)
            
            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                params.append(article_id)
                
                query = f"UPDATE help_articles SET {', '.join(update_fields)} WHERE id = ?"
                await db.execute(query, params)
                await db.commit()
                
                logger.info(f"Help article updated: ID {article_id}")
            
            return {"message": "Help article updated successfully"}
            
        except Exception as e:
            logger.error(f"Error updating help article: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update help article"
            )

@router.delete("/help/articles/{article_id}")
async def delete_help_article(article_id: int):
    """Delete a help article"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            cursor = await db.execute(
                "DELETE FROM help_articles WHERE id = ?",
                (article_id,)
            )
            
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Help article not found"
                )
            
            await db.commit()
            
            logger.info(f"Help article deleted: ID {article_id}")
            
            return {"message": "Help article deleted successfully"}
            
        except Exception as e:
            logger.error(f"Error deleting help article: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete help article"
            )

# Media Management
@router.post("/media/upload")
async def upload_media(file: UploadFile = File(...)):
    """Upload media file"""
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Check file size
        max_size = int(os.getenv("MAX_FILE_SIZE", 10485760))  # 10MB default
        if os.path.getsize(file_path) > max_size:
            os.remove(file_path)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large"
            )
        
        file_url = f"/uploads/{unique_filename}"
        
        logger.info(f"Media uploaded: {file.filename} -> {unique_filename}")
        
        return {
            "message": "File uploaded successfully",
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_url": file_url,
            "file_size": os.path.getsize(file_path),
            "content_type": file.content_type
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )

@router.get("/media/{filename}")
async def get_media_file(filename: str):
    """Get media file"""
    try:
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        file_path = os.path.join(upload_dir, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        from fastapi.responses import FileResponse
        return FileResponse(file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve file"
        )

@router.delete("/media/{filename}")
async def delete_media_file(filename: str):
    """Delete media file"""
    try:
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        file_path = os.path.join(upload_dir, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        os.remove(file_path)
        
        logger.info(f"Media deleted: {filename}")
        
        return {"message": "File deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )

# Content Management Utilities
@router.get("/content/stats")
async def get_content_stats():
    """Get content management statistics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Blog stats
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total_posts,
                COUNT(CASE WHEN status = 'published' THEN 1 END) as published_posts,
                COUNT(CASE WHEN status = 'draft' THEN 1 END) as draft_posts,
                COUNT(CASE WHEN featured = 1 THEN 1 END) as featured_posts
            FROM blog_posts
            """
        )
        blog_stats = await cursor.fetchone()
        
        # Help articles stats
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total_articles,
                COUNT(CASE WHEN status = 'published' THEN 1 END) as published_articles,
                COUNT(CASE WHEN status = 'draft' THEN 1 END) as draft_articles,
                SUM(views) as total_views
            FROM help_articles
            """
        )
        help_stats = await cursor.fetchone()
        
        # Contact submissions stats
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total_submissions,
                COUNT(CASE WHEN status = 'new' THEN 1 END) as new_submissions,
                COUNT(CASE WHEN status = 'in_progress' THEN 1 END) as in_progress_submissions
            FROM contact_submissions
            """
        )
        contact_stats = await cursor.fetchone()
        
        # Sales leads stats
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total_leads,
                COUNT(CASE WHEN status = 'new' THEN 1 END) as new_leads,
                COUNT(CASE WHEN status = 'qualified' THEN 1 END) as qualified_leads
            FROM sales_leads
            """
        )
        sales_stats = await cursor.fetchone()
        
        return {
            "blog_stats": blog_stats,
            "help_stats": help_stats,
            "contact_stats": contact_stats,
            "sales_stats": sales_stats
        }

@router.get("/system/health")
async def get_system_health():
    """Get system health information"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            # Test database connection
            cursor = await db.execute("SELECT 1")
            await cursor.fetchone()
            
            db_status = "healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = "unhealthy"
        
        # Check uploads directory
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        upload_status = "healthy" if os.path.exists(upload_dir) else "unhealthy"
        
        # Overall status
        overall_status = "healthy" if db_status == "healthy" and upload_status == "healthy" else "degraded"
        
        return {
            "overall_status": overall_status,
            "database_status": db_status,
            "upload_status": upload_status,
            "timestamp": datetime.now().isoformat()
        }
