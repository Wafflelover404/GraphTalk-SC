from fastapi import APIRouter, HTTPException, status, UploadFile, File, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import aiosqlite
import json
import logging
import os
import uuid

from database import get_db_connection, dict_factory, get_database_path

logger = logging.getLogger(__name__)
router = APIRouter()

# Load CMS credentials from environment with defaults for development
# These are used for CMS admin dashboard authentication only
CMS_PASSWORD = os.getenv("CMS_PASSWORD", "AdminTestPassword1423")
CMS_TOKEN = os.getenv("MASTER_CMS_TOKEN", "AdminTestPassword1423")

# Use auto_error=False to allow both Bearer token and custom header authentication
security_scheme = HTTPBearer(auto_error=False)


async def verify_cms_password(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    x_cms_password: Optional[str] = Header(None)
):
    """
    Verify CMS authentication via either:
    1. Bearer token (for main API integration)
    2. x-cms-password header (for direct CMS calls)
    """
    # Check Bearer token first (main API integration)
    if credentials:
        if credentials.credentials == CMS_TOKEN or credentials.credentials == CMS_PASSWORD:
            return True
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid CMS token"
        )
    
    # Fall back to custom header for direct CMS calls
    if x_cms_password:
        if x_cms_password == CMS_PASSWORD:
            return True
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid CMS password"
        )
    
    # No valid authentication provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials"
    )

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
async def get_blog_posts(_: bool = Depends(verify_cms_password)):
    """Get all blog posts"""
    async with aiosqlite.connect(get_database_path()) as db:
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
async def create_blog_post(post: BlogPostCreate, _: bool = Depends(verify_cms_password)):
    """Create a new blog post"""
    async with aiosqlite.connect(get_database_path()) as db:
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
async def update_blog_post(post_id: int, post: BlogPostUpdate, _: bool = Depends(verify_cms_password)):
    """Update a blog post"""
    async with aiosqlite.connect(get_database_path()) as db:
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
async def delete_blog_post(post_id: int, _: bool = Depends(verify_cms_password)):
    """Delete a blog post"""
    async with aiosqlite.connect(get_database_path()) as db:
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
async def create_help_article(article: HelpArticleCreate, _: bool = Depends(verify_cms_password)):
    """Create a new help article"""
    async with aiosqlite.connect(get_database_path()) as db:
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
async def update_help_article(article_id: int, article: HelpArticleUpdate, _: bool = Depends(verify_cms_password)):
    """Update a help article"""
    async with aiosqlite.connect(get_database_path()) as db:
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
async def delete_help_article(article_id: int, _: bool = Depends(verify_cms_password)):
    """Delete a help article"""
    async with aiosqlite.connect(get_database_path()) as db:
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
async def upload_media(file: UploadFile = File(...), _: bool = Depends(verify_cms_password)):
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
async def get_media_file(filename: str, _: bool = Depends(verify_cms_password)):
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
async def delete_media_file(filename: str, _: bool = Depends(verify_cms_password)):
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
async def get_content_stats(_: bool = Depends(verify_cms_password)):
    """Get content management statistics"""
    async with aiosqlite.connect(get_database_path()) as db:
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
async def get_system_health(_: bool = Depends(verify_cms_password)):
    """Get system health information"""
    async with aiosqlite.connect(get_database_path()) as db:
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

# Organization Management Endpoints
class OrganizationApprovalRequest(BaseModel):
    organization_id: str
    action: str  # "approve" or "reject"
    reason: Optional[str] = None  # For rejection reason

@router.get("/organizations/pending")
async def get_pending_organizations(_: bool = Depends(verify_cms_password)):
    """Get all pending organization requests awaiting CMS approval"""
    import sys
    import os
    
    # Add parent directory to path to import from graphtalk
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    
    try:
        from graphtalk.orgdb import DB_PATH as ORG_DB_PATH
        import aiosqlite as org_sqlite
        
        pending_orgs = []
        
        async with org_sqlite.connect(ORG_DB_PATH) as db:
            db.row_factory = dict_factory
            cursor = await db.execute(
                "SELECT id, name, slug, status, created_at, updated_at FROM organizations WHERE status = 'pending' ORDER BY created_at DESC"
            )
            pending_orgs = await cursor.fetchall()
        
        return {
            "status": "success",
            "pending_organizations": pending_orgs,
            "count": len(pending_orgs)
        }
    except Exception as e:
        logger.error(f"Error fetching pending organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pending organizations: {str(e)}"
        )

@router.get("/organizations/all")
async def get_all_organizations(_: bool = Depends(verify_cms_password)):
    """Get all organizations with their current status"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        
        from graphtalk.orgdb import DB_PATH as ORG_DB_PATH
        import aiosqlite as org_sqlite
        
        all_orgs = []
        
        async with org_sqlite.connect(ORG_DB_PATH) as db:
            db.row_factory = dict_factory
            cursor = await db.execute(
                "SELECT id, name, slug, status, created_at, updated_at FROM organizations ORDER BY created_at DESC"
            )
            all_orgs = await cursor.fetchall()
        
        return {
            "status": "success",
            "organizations": all_orgs,
            "count": len(all_orgs)
        }
    except Exception as e:
        logger.error(f"Error fetching organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch organizations: {str(e)}"
        )

@router.post("/organizations/approve")
async def approve_organization(request: OrganizationApprovalRequest, _: bool = Depends(verify_cms_password)):
    """Approve a pending organization request"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        
        from graphtalk.orgdb import DB_PATH as ORG_DB_PATH
        import aiosqlite as org_sqlite
        
        async with org_sqlite.connect(ORG_DB_PATH) as db:
            # Update organization status to 'active'
            cursor = await db.execute(
                "UPDATE organizations SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (request.organization_id,)
            )
            await db.commit()
            
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization not found"
                )
            
            logger.info(f"Organization approved: {request.organization_id}")
            
            return {
                "status": "success",
                "message": f"Organization {request.organization_id} has been approved",
                "organization_id": request.organization_id,
                "new_status": "active"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve organization: {str(e)}"
        )

@router.post("/organizations/reject")
async def reject_organization(request: OrganizationApprovalRequest, _: bool = Depends(verify_cms_password)):
    """Reject a pending organization request"""
    try:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        
        from graphtalk.orgdb import DB_PATH as ORG_DB_PATH
        import aiosqlite as org_sqlite
        
        async with org_sqlite.connect(ORG_DB_PATH) as db:
            # Update organization status to 'rejected'
            cursor = await db.execute(
                "UPDATE organizations SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (request.organization_id,)
            )
            await db.commit()
            
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Organization not found"
                )
            
            logger.info(f"Organization rejected: {request.organization_id} - Reason: {request.reason or 'None provided'}")
            
            return {
                "status": "success",
                "message": f"Organization {request.organization_id} has been rejected",
                "organization_id": request.organization_id,
                "new_status": "rejected",
                "reason": request.reason
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject organization: {str(e)}"
        )
