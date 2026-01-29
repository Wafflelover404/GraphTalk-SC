from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, date
import aiosqlite
import logging

from database import get_db_connection, dict_factory

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class DemoRequest(BaseModel):
    name: str
    email: EmailStr
    company: str
    phone: Optional[str] = None
    job_title: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    preferred_time: Optional[str] = None
    preferred_date: Optional[date] = None
    message: Optional[str] = None

class SalesLead(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    phone: Optional[str] = None
    source: str = "website"
    score: int = 0

class QuoteRequest(BaseModel):
    company_name: str
    contact_email: EmailStr
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    requirements: Optional[str] = None
    user_count: Optional[int] = None
    current_solution: Optional[str] = None
    budget_range: Optional[str] = None
    timeline: Optional[str] = None

class EnterpriseInquiry(BaseModel):
    company_name: str
    contact_name: str
    contact_email: EmailStr
    phone: Optional[str] = None
    requirements: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    current_challenges: Optional[str] = None
    expected_users: Optional[int] = None

# Demo Request endpoints
@router.post("/demo-request")
async def create_demo_request(request: DemoRequest):
    """Create a new demo request"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            cursor = await db.execute(
                """
                INSERT INTO demo_requests 
                (name, email, company, phone, job_title, company_size, industry, 
                 preferred_time, preferred_date, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.name,
                    request.email,
                    request.company,
                    request.phone,
                    request.job_title,
                    request.company_size,
                    request.industry,
                    request.preferred_time,
                    request.preferred_date.isoformat() if request.preferred_date else None,
                    request.message
                )
            )
            
            request_id = cursor.lastrowid
            await db.commit()
            
            logger.info(f"Demo request created: ID {request_id}, Company: {request.company}")
            
            # Also create a sales lead from this demo request
            await create_sales_lead_from_demo(request)
            
            return {
                "message": "Demo request submitted successfully",
                "request_id": request_id,
                "status": "pending"
            }
            
        except Exception as e:
            logger.error(f"Error creating demo request: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create demo request"
            )

@router.get("/demo-requests")
async def get_demo_requests(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get demo requests (admin endpoint)"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        query = "SELECT * FROM demo_requests WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        requests = await cursor.fetchall()
        
        return requests

@router.get("/demo-request/{request_id}")
async def get_demo_request(request_id: int):
    """Get single demo request"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM demo_requests WHERE id = ?",
            (request_id,)
        )
        request = await cursor.fetchone()
        
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Demo request not found"
            )
        
        return request

# Sales Leads endpoints
async def create_sales_lead_from_demo(demo_request: DemoRequest):
    """Create a sales lead from demo request"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            await db.execute(
                """
                INSERT INTO sales_leads 
                (name, email, company, phone, source, score, notes)
                VALUES (?, ?, ?, ?, 'demo_request', 80, ?)
                """,
                (
                    demo_request.name,
                    demo_request.email,
                    demo_request.company,
                    demo_request.phone,
                    f"Demo request - Company size: {demo_request.company_size}, Industry: {demo_request.industry}"
                )
            )
            await db.commit()
        except Exception as e:
            logger.error(f"Error creating sales lead from demo: {e}")

@router.post("/leads")
async def create_sales_lead(lead: SalesLead):
    """Create a new sales lead"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            cursor = await db.execute(
                """
                INSERT INTO sales_leads 
                (name, email, company, phone, source, score)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    lead.name,
                    lead.email,
                    lead.company,
                    lead.phone,
                    lead.source,
                    lead.score
                )
            )
            
            lead_id = cursor.lastrowid
            await db.commit()
            
            logger.info(f"Sales lead created: ID {lead_id}, Source: {lead.source}")
            
            return {
                "message": "Sales lead created successfully",
                "lead_id": lead_id
            }
            
        except Exception as e:
            logger.error(f"Error creating sales lead: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create sales lead"
            )

@router.get("/leads")
async def get_sales_leads(
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get sales leads (admin endpoint)"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        query = "SELECT * FROM sales_leads WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if source:
            query += " AND source = ?"
            params.append(source)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        leads = await cursor.fetchall()
        
        return leads

@router.get("/leads/{lead_id}")
async def get_sales_lead(lead_id: int):
    """Get single sales lead"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM sales_leads WHERE id = ?",
            (lead_id,)
        )
        lead = await cursor.fetchone()
        
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sales lead not found"
            )
        
        return lead

@router.put("/leads/{lead_id}/status")
async def update_lead_status(
    lead_id: int,
    new_status: str,
    notes: Optional[str] = None
):
    """Update lead status"""
    valid_statuses = ["new", "contacted", "qualified", "proposal", "closed_won", "closed_lost"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )
    
    async with aiosqlite.connect("landing_pages.db") as db:
        # Check if lead exists
        cursor = await db.execute(
            "SELECT id FROM sales_leads WHERE id = ?",
            (lead_id,)
        )
        if not await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sales lead not found"
            )
        
        # Update status
        update_query = """
            UPDATE sales_leads 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
        """
        params = [new_status]
        
        if notes:
            update_query += ", notes = ?"
            params.append(notes)
        
        update_query += " WHERE id = ?"
        params.append(lead_id)
        
        await db.execute(update_query, params)
        await db.commit()
        
        return {"message": f"Lead status updated to {new_status}"}

# Quote Request endpoints
@router.post("/quote-request")
async def create_quote_request(request: QuoteRequest):
    """Create a new quote request"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            cursor = await db.execute(
                """
                INSERT INTO quote_requests 
                (company_name, contact_email, contact_name, phone, requirements,
                 user_count, current_solution, budget_range, timeline)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.company_name,
                    request.contact_email,
                    request.contact_name,
                    request.phone,
                    request.requirements,
                    request.user_count,
                    request.current_solution,
                    request.budget_range,
                    request.timeline
                )
            )
            
            quote_id = cursor.lastrowid
            await db.commit()
            
            logger.info(f"Quote request created: ID {quote_id}, Company: {request.company_name}")
            
            return {
                "message": "Quote request submitted successfully",
                "quote_id": quote_id,
                "status": "pending"
            }
            
        except Exception as e:
            logger.error(f"Error creating quote request: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create quote request"
            )

@router.get("/quote-requests")
async def get_quote_requests(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get quote requests (admin endpoint)"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        query = "SELECT * FROM quote_requests WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        requests = await cursor.fetchall()
        
        return requests

# Enterprise Inquiry endpoints
@router.post("/enterprise-inquiry")
async def create_enterprise_inquiry(inquiry: EnterpriseInquiry):
    """Create a new enterprise inquiry"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            cursor = await db.execute(
                """
                INSERT INTO quote_requests 
                (company_name, contact_email, contact_name, phone, requirements,
                 status, user_count)
                VALUES (?, ?, ?, ?, ?, 'enterprise', ?)
                """,
                (
                    inquiry.company_name,
                    inquiry.contact_email,
                    inquiry.contact_name,
                    inquiry.phone,
                    f"{inquiry.requirements}\n\nIndustry: {inquiry.industry}\nCompany Size: {inquiry.company_size}\nCurrent Challenges: {inquiry.current_challenges}\nExpected Users: {inquiry.expected_users}",
                    inquiry.expected_users
                )
            )
            
            inquiry_id = cursor.lastrowid
            await db.commit()
            
            logger.info(f"Enterprise inquiry created: ID {inquiry_id}, Company: {inquiry.company_name}")
            
            return {
                "message": "Enterprise inquiry submitted successfully",
                "inquiry_id": inquiry_id,
                "status": "pending"
            }
            
        except Exception as e:
            logger.error(f"Error creating enterprise inquiry: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create enterprise inquiry"
            )

# Sales Analytics
@router.get("/analytics/leads")
async def get_sales_analytics():
    """Get sales analytics data"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Total leads
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM sales_leads"
        )
        total_leads = await cursor.fetchone()
        
        # Leads by status
        cursor = await db.execute(
            """
            SELECT status, COUNT(*) as count
            FROM sales_leads
            GROUP BY status
            ORDER BY count DESC
            """
        )
        leads_by_status = await cursor.fetchall()
        
        # Leads by source
        cursor = await db.execute(
            """
            SELECT source, COUNT(*) as count
            FROM sales_leads
            GROUP BY source
            ORDER BY count DESC
            """
        )
        leads_by_source = await cursor.fetchall()
        
        # Demo requests
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM demo_requests"
        )
        total_demos = await cursor.fetchone()
        
        # Quote requests
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM quote_requests"
        )
        total_quotes = await cursor.fetchone()
        
        # Recent activity (last 30 days)
        cursor = await db.execute(
            """
            SELECT 
                (SELECT COUNT(*) FROM sales_leads WHERE created_at >= datetime('now', '-30 days')) as recent_leads,
                (SELECT COUNT(*) FROM demo_requests WHERE created_at >= datetime('now', '-30 days')) as recent_demos,
                (SELECT COUNT(*) FROM quote_requests WHERE created_at >= datetime('now', '-30 days')) as recent_quotes
            """
        )
        recent_activity = await cursor.fetchone()
        
        return {
            "total_leads": total_leads['total'],
            "total_demo_requests": total_demos['total'],
            "total_quote_requests": total_quotes['total'],
            "leads_by_status": leads_by_status,
            "leads_by_source": leads_by_source,
            "recent_activity": recent_activity
        }

@router.get("/analytics/funnel")
async def get_sales_funnel():
    """Get sales funnel data"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Sales funnel stages
        cursor = await db.execute(
            """
            SELECT 
                'Leads' as stage,
                COUNT(*) as count
            FROM sales_leads
            UNION ALL
            SELECT 
                'Demo Requests' as stage,
                COUNT(*) as count
            FROM demo_requests
            UNION ALL
            SELECT 
                'Quote Requests' as stage,
                COUNT(*) as count
            FROM quote_requests
            UNION ALL
            SELECT 
                'Qualified' as stage,
                COUNT(*) as count
            FROM sales_leads
            WHERE status IN ('qualified', 'proposal', 'closed_won')
            UNION ALL
            SELECT 
                'Closed Won' as stage,
                COUNT(*) as count
            FROM sales_leads
            WHERE status = 'closed_won'
            ORDER BY count DESC
            """
        )
        funnel_data = await cursor.fetchall()
        
        return {"funnel": funnel_data}
