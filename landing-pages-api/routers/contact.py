from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import aiosqlite
import logging

from database import get_db_connection, dict_factory

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class ContactSubmission(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    phone: Optional[str] = None
    message: str
    inquiry_type: str = "general"  # general, sales, support, partnership

class ContactResponse(BaseModel):
    id: int
    name: str
    email: str
    company: Optional[str]
    phone: Optional[str]
    message: str
    inquiry_type: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime

class ContactOptions(BaseModel):
    email_support: dict
    phone_support: dict
    telegram_support: dict

class InquiryType(BaseModel):
    id: str
    name: str
    description: str

# Contact form submission
@router.post("/submit")
async def submit_contact_form(submission: ContactSubmission):
    """Submit contact form"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            # Determine priority based on inquiry type
            priority_map = {
                "sales": "high",
                "partnership": "high", 
                "support": "medium",
                "general": "low"
            }
            priority = priority_map.get(submission.inquiry_type, "medium")
            
            cursor = await db.execute(
                """
                INSERT INTO contact_submissions 
                (name, email, company, phone, message, inquiry_type, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    submission.name,
                    submission.email,
                    submission.company,
                    submission.phone,
                    submission.message,
                    submission.inquiry_type,
                    priority
                )
            )
            
            submission_id = cursor.lastrowid
            await db.commit()
            
            logger.info(f"Contact form submitted: ID {submission_id}, Type: {submission.inquiry_type}")
            
            return {
                "message": "Contact form submitted successfully",
                "submission_id": submission_id,
                "status": "submitted"
            }
            
        except Exception as e:
            logger.error(f"Error submitting contact form: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to submit contact form"
            )

@router.get("/submissions", response_model=List[ContactResponse])
async def get_contact_submissions(
    status: Optional[str] = None,
    inquiry_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get contact submissions (admin endpoint - would normally require auth)"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        query = "SELECT * FROM contact_submissions WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if inquiry_type:
            query += " AND inquiry_type = ?"
            params.append(inquiry_type)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        submissions = await cursor.fetchall()
        
        return submissions

@router.get("/submissions/{submission_id}", response_model=ContactResponse)
async def get_contact_submission(submission_id: int):
    """Get single contact submission"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM contact_submissions WHERE id = ?",
            (submission_id,)
        )
        submission = await cursor.fetchone()
        
        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact submission not found"
            )
        
        return submission

@router.get("/options")
async def get_contact_options():
    """Get contact options for the frontend"""
    return {
        "email_support": {
            "title": "Email Support",
            "description": "Send us a detailed message",
            "email": "info.wikiai@gmail.com",
            "hours": "24/7",
            "response_time": "Within 24 hours"
        },
        "phone_support": {
            "title": "Phone Support", 
            "description": "Speak directly with our team",
            "phone": "+375 297 345 682",
            "hours": "Mon-Fri, 9AM-6PM EST",
            "response_time": "Immediate"
        },
        "telegram_support": {
            "title": "Telegram Support",
            "description": "Join our Telegram community",
            "telegram": "https://t.me/vikigolubeva",
            "hours": "24/7",
            "response_time": "Within few hours"
        }
    }

@router.get("/inquiry-types")
async def get_inquiry_types():
    """Get available inquiry types"""
    return [
        {
            "id": "general",
            "name": "General Inquiry",
            "description": "General questions and information"
        },
        {
            "id": "sales",
            "name": "Sales",
            "description": "Product demos, pricing, and sales questions"
        },
        {
            "id": "support",
            "name": "Technical Support",
            "description": "Technical issues and troubleshooting"
        },
        {
            "id": "partnership",
            "name": "Partnership",
            "description": "Partnership and collaboration opportunities"
        }
    ]

@router.put("/submissions/{submission_id}/status")
async def update_submission_status(
    submission_id: int,
    new_status: str,
    notes: Optional[str] = None
):
    """Update submission status (admin endpoint)"""
    valid_statuses = ["new", "in_progress", "resolved", "closed"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    async with aiosqlite.connect("landing_pages.db") as db:
        # Check if submission exists
        cursor = await db.execute(
            "SELECT id FROM contact_submissions WHERE id = ?",
            (submission_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact submission not found"
            )
        
        # Update status
        update_query = """
            UPDATE contact_submissions 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
        """
        params = [new_status]
        
        if notes:
            update_query += ", notes = ?"
            params.append(notes)
        
        update_query += " WHERE id = ?"
        params.append(submission_id)
        
        await db.execute(update_query, params)
        await db.commit()
        
        return {"message": f"Submission status updated to {new_status}"}

@router.get("/analytics")
async def get_contact_analytics():
    """Get contact form analytics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Total submissions
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM contact_submissions"
        )
        total = await cursor.fetchone()
        
        # Submissions by type
        cursor = await db.execute(
            """
            SELECT inquiry_type, COUNT(*) as count
            FROM contact_submissions
            GROUP BY inquiry_type
            ORDER BY count DESC
            """
        )
        by_type = await cursor.fetchall()
        
        # Submissions by status
        cursor = await db.execute(
            """
            SELECT status, COUNT(*) as count
            FROM contact_submissions
            GROUP BY status
            ORDER BY count DESC
            """
        )
        by_status = await cursor.fetchall()
        
        # Recent submissions (last 7 days)
        cursor = await db.execute(
            """
            SELECT COUNT(*) as recent_count
            FROM contact_submissions
            WHERE created_at >= datetime('now', '-7 days')
            """
        )
        recent = await cursor.fetchone()
        
        return {
            "total_submissions": total['total'],
            "recent_submissions": recent['recent_count'],
            "by_inquiry_type": by_type,
            "by_status": by_status
        }
