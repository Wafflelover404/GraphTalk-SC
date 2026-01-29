from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import aiosqlite
import logging

from database import get_db_connection, dict_factory

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class DownloadRequest(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    resource_type: str  # whitepaper, case_study, ebook, etc.
    resource_id: str

class WebinarRegistration(BaseModel):
    name: str
    email: EmailStr
    company: Optional[str] = None
    job_title: Optional[str] = None
    webinar_id: str
    webinar_title: str

class EmailEvent(BaseModel):
    email: str
    event_type: str  # opened, clicked, unsubscribed, bounced
    campaign_id: Optional[str] = None
    url: Optional[str] = None  # for clicked events

class ABTestResult(BaseModel):
    test_name: str
    variant: str  # A or B
    conversion: bool
    page: str
    session_id: Optional[str] = None

# Lead Magnets & Downloads
@router.post("/download-request")
async def request_download(request: DownloadRequest):
    """Request downloadable content (whitepapers, case studies)"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            # Track the download request as an analytics event
            import json
            
            await db.execute(
                """
                INSERT INTO analytics_events 
                (event_type, page, user_id, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "download_request",
                    "landing_page",
                    request.email,
                    json.dumps({
                        "name": request.name,
                        "email": request.email,
                        "company": request.company,
                        "resource_type": request.resource_type,
                        "resource_id": request.resource_id
                    })
                )
            )
            
            # Also create a sales lead if it doesn't exist
            cursor = await db.execute(
                "SELECT id FROM sales_leads WHERE email = ?",
                (request.email,)
            )
            existing_lead = await cursor.fetchone()
            
            if not existing_lead:
                await db.execute(
                    """
                    INSERT INTO sales_leads 
                    (name, email, company, source, score, notes)
                    VALUES (?, ?, ?, 'download', 60, ?)
                    """,
                    (
                        request.name,
                        request.email,
                        request.company,
                        f"Downloaded {request.resource_type}: {request.resource_id}"
                    )
                )
            
            await db.commit()
            
            logger.info(f"Download request: {request.email} - {request.resource_type}")
            
            return {
                "message": "Download request processed successfully",
                "resource_type": request.resource_type,
                "download_url": f"/api/marketing/resources/{request.resource_id}/download"
            }
            
        except Exception as e:
            logger.error(f"Error processing download request: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process download request"
            )

@router.get("/resources")
async def get_marketing_resources():
    """Get available marketing resources"""
    resources = [
        {
            "id": "ai-km-whitepaper",
            "title": "AI-Powered Knowledge Management: The Future of Work",
            "type": "whitepaper",
            "description": "Comprehensive guide to implementing AI in knowledge management",
            "file_size": "2.4 MB",
            "format": "PDF",
            "cover_image": "/api/resources/ai-km-whitepaper/cover.jpg"
        },
        {
            "id": "roi-case-study",
            "title": "How Company X Increased Productivity by 40% with WikiAI",
            "type": "case_study",
            "description": "Real-world case study showing measurable ROI",
            "file_size": "1.8 MB",
            "format": "PDF",
            "cover_image": "/api/resources/roi-case-study/cover.jpg"
        },
        {
            "id": "implementation-guide",
            "title": "Complete Implementation Guide for Enterprise WikiAI",
            "type": "ebook",
            "description": "Step-by-step guide for successful enterprise deployment",
            "file_size": "4.2 MB",
            "format": "PDF",
            "cover_image": "/api/resources/implementation-guide/cover.jpg"
        },
        {
            "id": "comparison-sheet",
            "title": "WikiAI vs Traditional Knowledge Base Solutions",
            "type": "comparison",
            "description": "Detailed feature comparison and analysis",
            "file_size": "1.2 MB",
            "format": "PDF",
            "cover_image": "/api/resources/comparison-sheet/cover.jpg"
        }
    ]
    
    return {"resources": resources}

@router.get("/resources/{resource_id}/download")
async def download_resource(resource_id: str):
    """Get download URL for a resource"""
    # In a real implementation, this would generate a secure download link
    # For now, return a mock download URL
    return {
        "download_url": f"https://cdn.wikiai.com/resources/{resource_id}.pdf",
        "expires_in": 3600,  # 1 hour
        "message": "Download link generated successfully"
    }

# Webinar Registration
@router.post("/webinar-registration")
async def register_webinar(registration: WebinarRegistration):
    """Register for a webinar"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            # Track webinar registration
            import json
            
            await db.execute(
                """
                INSERT INTO analytics_events 
                (event_type, page, user_id, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "webinar_registration",
                    "webinar_page",
                    registration.email,
                    json.dumps({
                        "name": registration.name,
                        "email": registration.email,
                        "company": registration.company,
                        "job_title": registration.job_title,
                        "webinar_id": registration.webinar_id,
                        "webinar_title": registration.webinar_title
                    })
                )
            )
            
            # Create or update sales lead
            cursor = await db.execute(
                "SELECT id FROM sales_leads WHERE email = ?",
                (registration.email,)
            )
            existing_lead = await cursor.fetchone()
            
            if not existing_lead:
                await db.execute(
                    """
                    INSERT INTO sales_leads 
                    (name, email, company, source, score, notes)
                    VALUES (?, ?, ?, 'webinar', 70, ?)
                    """,
                    (
                        registration.name,
                        registration.email,
                        registration.company,
                        f"Registered for webinar: {registration.webinar_title}"
                    )
                )
            
            await db.commit()
            
            logger.info(f"Webinar registration: {registration.email} - {registration.webinar_title}")
            
            return {
                "message": "Webinar registration successful",
                "webinar_title": registration.webinar_title,
                "confirmation_email": True
            }
            
        except Exception as e:
            logger.error(f"Error processing webinar registration: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register for webinar"
            )

@router.get("/webinars")
async def get_upcoming_webinars():
    """Get upcoming webinars"""
    webinars = [
        {
            "id": "ai-km-101",
            "title": "AI Knowledge Management 101: Getting Started",
            "description": "Learn the basics of implementing AI-powered knowledge management",
            "date": "2024-02-15",
            "time": "14:00 UTC",
            "duration": "60 minutes",
            "speaker": "Sarah Chen, AI Research Lead",
            "capacity": 100,
            "registered": 67
        },
        {
            "id": "enterprise-deployment",
            "title": "Enterprise Deployment Best Practices",
            "description": "Advanced strategies for large-scale WikiAI deployment",
            "date": "2024-02-22",
            "time": "16:00 UTC",
            "duration": "90 minutes",
            "speaker": "Marcus Johnson, CTO",
            "capacity": 50,
            "registered": 43
        }
    ]
    
    return {"webinars": webinars}

# Email Campaign Tracking
@router.post("/email-opened")
async def track_email_opened(event: EmailEvent):
    """Track email opens"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            import json
            
            await db.execute(
                """
                INSERT INTO analytics_events 
                (event_type, user_id, metadata)
                VALUES (?, ?, ?)
                """,
                (
                    "email_opened",
                    event.email,
                    json.dumps({
                        "campaign_id": event.campaign_id,
                        "timestamp": datetime.now().isoformat()
                    })
                )
            )
            await db.commit()
            
            return {"message": "Email open tracked"}
            
        except Exception as e:
            logger.error(f"Error tracking email open: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to track email open"
            )

@router.post("/email-clicked")
async def track_email_clicked(event: EmailEvent):
    """Track email clicks"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            import json
            
            await db.execute(
                """
                INSERT INTO analytics_events 
                (event_type, user_id, metadata)
                VALUES (?, ?, ?)
                """,
                (
                    "email_clicked",
                    event.email,
                    json.dumps({
                        "campaign_id": event.campaign_id,
                        "url": event.url,
                        "timestamp": datetime.now().isoformat()
                    })
                )
            )
            await db.commit()
            
            return {"message": "Email click tracked"}
            
        except Exception as e:
            logger.error(f"Error tracking email click: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to track email click"
            )

@router.get("/campaign-performance")
async def get_campaign_performance(
    days: int = Query(30, ge=1, le=365)
):
    """Get email campaign performance data"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        date_filter = f"datetime('now', '-{days} days')"
        
        # Campaign metrics
        cursor = await db.execute(
            f"""
            SELECT 
                campaign_id,
                COUNT(CASE WHEN event_type = 'email_opened' THEN 1 END) as opens,
                COUNT(CASE WHEN event_type = 'email_clicked' THEN 1 END) as clicks,
                COUNT(DISTINCT user_id) as unique_recipients
            FROM analytics_events 
            WHERE created_at >= {date_filter}
            AND event_type IN ('email_opened', 'email_clicked')
            AND campaign_id IS NOT NULL
            GROUP BY campaign_id
            """
        )
        campaign_stats = await cursor.fetchall()
        
        # Calculate performance metrics
        performance_data = []
        for campaign in campaign_stats:
            if campaign['unique_recipients'] > 0:
                open_rate = (campaign['opens'] / campaign['unique_recipients']) * 100
                click_rate = (campaign['clicks'] / campaign['unique_recipients']) * 100
            else:
                open_rate = click_rate = 0
            
            if campaign['opens'] > 0:
                click_to_open_rate = (campaign['clicks'] / campaign['opens']) * 100
            else:
                click_to_open_rate = 0
            
            performance_data.append({
                "campaign_id": campaign['campaign_id'],
                "opens": campaign['opens'],
                "clicks": campaign['clicks'],
                "unique_recipients": campaign['unique_recipients'],
                "open_rate": round(open_rate, 2),
                "click_rate": round(click_rate, 2),
                "click_to_open_rate": round(click_to_open_rate, 2)
            })
        
        return {
            "period_days": days,
            "campaign_performance": performance_data
        }

# A/B Testing
@router.post("/ab-test-result")
async def track_ab_test_result(result: ABTestResult):
    """Track A/B test results"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            import json
            
            await db.execute(
                """
                INSERT INTO analytics_events 
                (event_type, page, session_id, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "ab_test_result",
                    result.page,
                    result.session_id,
                    json.dumps({
                        "test_name": result.test_name,
                        "variant": result.variant,
                        "conversion": result.conversion,
                        "timestamp": datetime.now().isoformat()
                    })
                )
            )
            await db.commit()
            
            return {"message": "A/B test result tracked"}
            
        except Exception as e:
            logger.error(f"Error tracking A/B test result: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to track A/B test result"
            )

@router.get("/ab-testing")
async def get_ab_test_results(
    test_name: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365)
):
    """Get A/B test results"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        date_filter = f"datetime('now', '-{days} days')"
        
        # Get A/B test results
        query = f"""
            SELECT 
                JSON_EXTRACT(metadata, '$.test_name') as test_name,
                JSON_EXTRACT(metadata, '$.variant') as variant,
                COUNT(*) as total_visitors,
                COUNT(CASE WHEN JSON_EXTRACT(metadata, '$.conversion') = 'true' THEN 1 END) as conversions
            FROM analytics_events 
            WHERE event_type = 'ab_test_result'
            AND created_at >= {date_filter}
        """
        params = []
        
        if test_name:
            query += " AND JSON_EXTRACT(metadata, '$.test_name') = ?"
            params.append(test_name)
        
        query += " GROUP BY JSON_EXTRACT(metadata, '$.test_name'), JSON_EXTRACT(metadata, '$.variant')"
        
        cursor = await db.execute(query, params)
        test_results = await cursor.fetchall()
        
        # Calculate conversion rates and statistical significance
        results_data = []
        for result in test_results:
            if result['total_visitors'] > 0:
                conversion_rate = (result['conversions'] / result['total_visitors']) * 100
            else:
                conversion_rate = 0
            
            results_data.append({
                "test_name": result['test_name'],
                "variant": result['variant'],
                "total_visitors": result['total_visitors'],
                "conversions": result['conversions'],
                "conversion_rate": round(conversion_rate, 2)
            })
        
        return {
            "period_days": days,
            "test_results": results_data
        }

# Marketing Analytics
@router.get("/analytics")
async def get_marketing_analytics(
    days: int = Query(30, ge=1, le=365)
):
    """Get comprehensive marketing analytics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        date_filter = f"datetime('now', '-{days} days')"
        
        # Marketing metrics
        cursor = await db.execute(
            f"""
            SELECT 
                COUNT(CASE WHEN event_type = 'download_request' THEN 1 END) as downloads,
                COUNT(CASE WHEN event_type = 'webinar_registration' THEN 1 END) as webinar_registrations,
                COUNT(CASE WHEN event_type = 'email_opened' THEN 1 END) as email_opens,
                COUNT(CASE WHEN event_type = 'email_clicked' THEN 1 END) as email_clicks,
                COUNT(DISTINCT CASE WHEN event_type LIKE 'email_%' THEN user_id END) as email_subscribers
            FROM analytics_events 
            WHERE created_at >= {date_filter}
            """
        )
        marketing_stats = await cursor.fetchone()
        
        # Lead generation from marketing activities
        cursor = await db.execute(
            f"""
            SELECT 
                source,
                COUNT(*) as leads,
                COUNT(CASE WHEN status = 'qualified' THEN 1 END) as qualified_leads
            FROM sales_leads 
            WHERE created_at >= {date_filter}
            AND source IN ('download', 'webinar', 'newsletter')
            GROUP BY source
            """
        )
        lead_sources = await cursor.fetchall()
        
        return {
            "period_days": days,
            "marketing_stats": marketing_stats,
            "lead_sources": lead_sources
        }
