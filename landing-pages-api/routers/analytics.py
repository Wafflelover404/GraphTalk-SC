from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import aiosqlite
import logging

from database import get_db_connection, dict_factory

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class PageView(BaseModel):
    page: str
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None

class ConversionEvent(BaseModel):
    event_type: str
    page: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

# Landing page tracking
@router.post("/track-visit")
async def track_landing_page_visit(visit: PageView):
    """Track landing page visit"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            await db.execute(
                """
                INSERT INTO landing_page_visits 
                (page, ip_address, user_agent, referrer, utm_source, utm_medium, utm_campaign, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    visit.page,
                    visit.ip_address,
                    visit.user_agent,
                    visit.referrer,
                    visit.utm_source,
                    visit.utm_medium,
                    visit.utm_campaign,
                    visit.session_id
                )
            )
            await db.commit()
            
            return {"message": "Visit tracked successfully"}
            
        except Exception as e:
            logger.error(f"Error tracking visit: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to track visit"
            )

@router.post("/track-event")
async def track_analytics_event(event: ConversionEvent):
    """Track analytics event"""
    async with aiosqlite.connect("landing_pages.db") as db:
        try:
            import json
            
            await db.execute(
                """
                INSERT INTO analytics_events 
                (event_type, page, user_id, session_id, ip_address, user_agent, referrer, 
                 utm_source, utm_medium, utm_campaign, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_type,
                    event.page,
                    event.user_id,
                    event.session_id,
                    None,  # IP would come from request
                    None,  # User agent would come from request
                    None,  # Referrer would come from request
                    None,  # UTM params would come from request
                    None,
                    None,
                    json.dumps(event.metadata) if event.metadata else None
                )
            )
            await db.commit()
            
            return {"message": "Event tracked successfully"}
            
        except Exception as e:
            logger.error(f"Error tracking event: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to track event"
            )

# Landing page analytics
@router.get("/landing-page-conversions")
async def get_landing_page_conversions(
    days: int = Query(30, ge=1, le=365),
    page: Optional[str] = Query(None)
):
    """Get landing page conversion data"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Build date filter
        date_filter = f"datetime('now', '-{days} days')"
        
        # Page visits
        visits_query = f"""
            SELECT 
                page,
                COUNT(*) as visits,
                COUNT(DISTINCT session_id) as unique_sessions,
                COUNT(DISTINCT ip_address) as unique_visitors
            FROM landing_page_visits 
            WHERE created_at >= {date_filter}
        """
        params = []
        
        if page:
            visits_query += " AND page = ?"
            params.append(page)
        
        visits_query += " GROUP BY page ORDER BY visits DESC"
        
        cursor = await db.execute(visits_query, params)
        visits_data = await cursor.fetchall()
        
        # Conversion events
        conversions_query = f"""
            SELECT 
                event_type,
                COUNT(*) as conversions
            FROM analytics_events 
            WHERE created_at >= {date_filter}
        """
        
        if page:
            conversions_query += " AND page = ?"
            params.append(page)
        
        conversions_query += " GROUP BY event_type ORDER BY conversions DESC"
        
        cursor = await db.execute(conversions_query, params)
        conversions_data = await cursor.fetchall()
        
        # Calculate conversion rates
        total_visits = sum(item['visits'] for item in visits_data)
        conversion_rates = []
        
        for conversion in conversions_data:
            if total_visits > 0:
                rate = (conversion['conversions'] / total_visits) * 100
            else:
                rate = 0
            
            conversion_rates.append({
                "event_type": conversion['event_type'],
                "conversions": conversion['conversions'],
                "conversion_rate": round(rate, 2)
            })
        
        return {
            "period_days": days,
            "total_visits": total_visits,
            "page_stats": visits_data,
            "conversions": conversions_data,
            "conversion_rates": conversion_rates
        }

@router.get("/page-views")
async def get_page_view_stats(
    days: int = Query(30, ge=1, le=365),
    page: Optional[str] = Query(None)
):
    """Get page view statistics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        date_filter = f"datetime('now', '-{days} days')"
        
        # Daily page views
        daily_query = f"""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as page_views,
                COUNT(DISTINCT session_id) as unique_sessions
            FROM landing_page_visits 
            WHERE created_at >= {date_filter}
        """
        params = []
        
        if page:
            daily_query += " AND page = ?"
            params.append(page)
        
        daily_query += " GROUP BY DATE(created_at) ORDER BY date DESC"
        
        cursor = await db.execute(daily_query, params)
        daily_stats = await cursor.fetchall()
        
        # Top pages
        top_pages_query = f"""
            SELECT 
                page,
                COUNT(*) as views,
                COUNT(DISTINCT session_id) as unique_sessions
            FROM landing_page_visits 
            WHERE created_at >= {date_filter}
            GROUP BY page
            ORDER BY views DESC
            LIMIT 10
        """
        
        cursor = await db.execute(top_pages_query)
        top_pages = await cursor.fetchall()
        
        return {
            "period_days": days,
            "daily_stats": daily_stats,
            "top_pages": top_pages
        }

@router.get("/user-sessions")
async def get_user_session_stats(
    days: int = Query(30, ge=1, le=365)
):
    """Get user session statistics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        date_filter = f"datetime('now', '-{days} days')"
        
        # Session metrics
        cursor = await db.execute(
            f"""
            SELECT 
                COUNT(DISTINCT session_id) as total_sessions,
                COUNT(DISTINCT ip_address) as unique_visitors,
                AVG(session_length) as avg_session_length
            FROM (
                SELECT 
                    session_id,
                    ip_address,
                    (julianday(MAX(created_at)) - julianday(MIN(created_at))) * 24 * 60 as session_length
                FROM landing_page_visits 
                WHERE created_at >= {date_filter}
                AND session_id IS NOT NULL
                GROUP BY session_id, ip_address
            )
            """
        )
        session_stats = await cursor.fetchone()
        
        # Daily sessions
        cursor = await db.execute(
            f"""
            SELECT 
                DATE(created_at) as date,
                COUNT(DISTINCT session_id) as sessions,
                COUNT(DISTINCT ip_address) as unique_visitors
            FROM landing_page_visits 
            WHERE created_at >= {date_filter}
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """
        )
        daily_sessions = await cursor.fetchall()
        
        return {
            "period_days": days,
            "session_stats": session_stats,
            "daily_sessions": daily_sessions
        }

@router.get("/conversion")
async def get_conversion_metrics(
    days: int = Query(30, ge=1, le=365)
):
    """Get conversion metrics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        date_filter = f"datetime('now', '-{days} days')"
        
        # Conversion funnel
        cursor = await db.execute(
            f"""
            SELECT 
                'Page Views' as stage,
                COUNT(*) as count
            FROM landing_page_visits 
            WHERE created_at >= {date_filter}
            UNION ALL
            SELECT 
                'Contact Submissions' as stage,
                COUNT(*) as count
            FROM contact_submissions 
            WHERE created_at >= {date_filter}
            UNION ALL
            SELECT 
                'Demo Requests' as stage,
                COUNT(*) as count
            FROM demo_requests 
            WHERE created_at >= {date_filter}
            UNION ALL
            SELECT 
                'Newsletter Subscriptions' as stage,
                COUNT(*) as count
            FROM newsletter_subscriptions 
            WHERE created_at >= {date_filter}
            ORDER BY count DESC
            """
        )
        funnel_data = await cursor.fetchall()
        
        # Conversion rates by source
        cursor = await db.execute(
            f"""
            SELECT 
                utm_source,
                COUNT(*) as visits,
                COUNT(DISTINCT session_id) as unique_sessions
            FROM landing_page_visits 
            WHERE created_at >= {date_filter}
            AND utm_source IS NOT NULL
            GROUP BY utm_source
            ORDER BY visits DESC
            """
        )
        source_stats = await cursor.fetchall()
        
        return {
            "period_days": days,
            "conversion_funnel": funnel_data,
            "source_stats": source_stats
        }

@router.get("/search-popular")
async def get_popular_search_terms(
    days: int = Query(30, ge=1, le=365)
):
    """Get popular search terms"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        date_filter = f"datetime('now', '-{days} days')"
        
        # This would track search queries if we had a search tracking table
        # For now, return mock data
        popular_terms = [
            {"term": "AI knowledge management", "count": 45},
            {"term": "document search", "count": 38},
            {"term": "team collaboration", "count": 32},
            {"term": "semantic search", "count": 28},
            {"term": "enterprise wiki", "count": 25}
        ]
        
        return {
            "period_days": days,
            "popular_terms": popular_terms
        }

@router.get("/user-engagement")
async def get_user_engagement_metrics(
    days: int = Query(30, ge=1, le=365)
):
    """Get user engagement metrics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        date_filter = f"datetime('now', '-{days} days')"
        
        # Engagement metrics
        cursor = await db.execute(
            f"""
            SELECT 
                COUNT(DISTINCT ip_address) as returning_visitors,
                AVG(page_views_per_session) as avg_pages_per_session,
                AVG(time_on_site) as avg_time_on_site
            FROM (
                SELECT 
                    ip_address,
                    session_id,
                    COUNT(*) as page_views_per_session,
                    (julianday(MAX(created_at)) - julianday(MIN(created_at))) * 24 * 60 as time_on_site
                FROM landing_page_visits 
                WHERE created_at >= {date_filter}
                AND session_id IS NOT NULL
                GROUP BY ip_address, session_id
            )
            """
        )
        engagement_stats = await cursor.fetchone()
        
        # Most engaged pages
        cursor = await db.execute(
            f"""
            SELECT 
                page,
                COUNT(*) as visits,
                AVG(time_spent) as avg_time_spent
            FROM (
                SELECT 
                    page,
                    session_id,
                    (julianday(MAX(created_at)) - julianday(MIN(created_at))) * 24 * 60 as time_spent
                FROM landing_page_visits 
                WHERE created_at >= {date_filter}
                AND session_id IS NOT NULL
                GROUP BY page, session_id
            )
            GROUP BY page
            HAVING visits >= 5
            ORDER BY avg_time_spent DESC
            LIMIT 10
            """
        )
        engaged_pages = await cursor.fetchall()
        
        return {
            "period_days": days,
            "engagement_stats": engagement_stats,
            "engaged_pages": engaged_pages
        }

# Dashboard analytics
@router.get("/dashboard")
async def get_dashboard_analytics():
    """Get comprehensive dashboard analytics"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Get data from multiple sources
        cursor = await db.execute(
            """
            SELECT 
                (SELECT COUNT(*) FROM landing_page_visits WHERE created_at >= datetime('now', '-7 days')) as weekly_visits,
                (SELECT COUNT(*) FROM landing_page_visits WHERE created_at >= datetime('now', '-30 days')) as monthly_visits,
                (SELECT COUNT(*) FROM contact_submissions WHERE created_at >= datetime('now', '-30 days')) as monthly_contacts,
                (SELECT COUNT(*) FROM demo_requests WHERE created_at >= datetime('now', '-30 days')) as monthly_demos,
                (SELECT COUNT(*) FROM newsletter_subscriptions WHERE created_at >= datetime('now', '-30 days')) as monthly_newsletter
            """
        )
        dashboard_stats = await cursor.fetchone()
        
        # Recent activity
        cursor = await db.execute(
            """
            SELECT 'landing_page_visit' as activity_type, COUNT(*) as count, MAX(created_at) as last_activity
            FROM landing_page_visits 
            WHERE created_at >= datetime('now', '-1 day')
            UNION ALL
            SELECT 'contact_submission' as activity_type, COUNT(*) as count, MAX(created_at) as last_activity
            FROM contact_submissions 
            WHERE created_at >= datetime('now', '-1 day')
            UNION ALL
            SELECT 'demo_request' as activity_type, COUNT(*) as count, MAX(created_at) as last_activity
            FROM demo_requests 
            WHERE created_at >= datetime('now', '-1 day')
            ORDER BY count DESC
            """
        )
        recent_activity = await cursor.fetchall()
        
        return {
            "dashboard_stats": dashboard_stats,
            "recent_activity": recent_activity,
            "last_updated": datetime.now().isoformat()
        }
