from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import aiosqlite
import logging

from database import get_db_connection, dict_factory

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models
class ServiceStatus(BaseModel):
    name: str
    description: str
    status: str  # operational, degraded, down, maintenance
    uptime_percentage: float = 99.9
    last_checked: Optional[datetime] = None

class ServiceStatusResponse(ServiceStatus):
    id: int
    created_at: datetime
    updated_at: datetime

class Incident(BaseModel):
    title: str
    description: str
    severity: str  # critical, major, minor, maintenance
    status: str  # investigating, identified, monitoring, resolved
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    affected_services: Optional[List[str]] = []

class IncidentResponse(Incident):
    id: int
    created_at: datetime
    updated_at: datetime

class UptimeMetric(BaseModel):
    period: str
    uptime: str

# Service Status endpoints
@router.get("/services", response_model=List[ServiceStatusResponse])
async def get_service_status():
    """Get status of all services"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM service_status ORDER BY name"
        )
        services = await cursor.fetchall()
        
        # Update last_checked time for all services
        await db.execute(
            "UPDATE service_status SET last_checked = CURRENT_TIMESTAMP"
        )
        await db.commit()
        
        return services

@router.get("/overview")
async def get_system_overview():
    """Get overall system status"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Get all services
        cursor = await db.execute("SELECT * FROM service_status")
        services = await cursor.fetchall()
        
        # Determine overall status
        if all(service['status'] == 'operational' for service in services):
            overall_status = 'operational'
            overall_message = 'All systems operational'
        elif any(service['status'] == 'down' for service in services):
            overall_status = 'down'
            overall_message = 'Some systems experiencing issues'
        else:
            overall_status = 'degraded'
            overall_message = 'Some systems degraded'
        
        # Get recent incidents
        cursor = await db.execute(
            """
            SELECT * FROM status_incidents 
            WHERE status != 'resolved' 
            ORDER BY created_at DESC 
            LIMIT 5
            """
        )
        active_incidents = await cursor.fetchall()
        
        return {
            "overall_status": overall_status,
            "overall_message": overall_message,
            "services": services,
            "active_incidents": active_incidents,
            "last_updated": datetime.now().isoformat()
        }

@router.get("/services/{service_id}", response_model=ServiceStatusResponse)
async def get_service_status_by_id(service_id: int):
    """Get status of a specific service"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM service_status WHERE id = ?",
            (service_id,)
        )
        service = await cursor.fetchone()
        
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )
        
        return service

# Incidents endpoints
@router.get("/incidents", response_model=List[IncidentResponse])
async def get_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get status incidents"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        query = "SELECT * FROM status_incidents WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = await db.execute(query, params)
        incidents = await cursor.fetchall()
        
        # Parse affected_services JSON
        for incident in incidents:
            if incident.get('affected_services'):
                try:
                    import json
                    incident['affected_services'] = json.loads(incident['affected_services'])
                except:
                    incident['affected_services'] = []
            else:
                incident['affected_services'] = []
        
        return incidents

@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident_by_id(incident_id: int):
    """Get single incident"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            "SELECT * FROM status_incidents WHERE id = ?",
            (incident_id,)
        )
        incident = await cursor.fetchone()
        
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Incident not found"
            )
        
        # Parse affected_services JSON
        if incident.get('affected_services'):
            try:
                import json
                incident['affected_services'] = json.loads(incident['affected_services'])
            except:
                incident['affected_services'] = []
        else:
            incident['affected_services'] = []
        
        return incident

@router.get("/incidents/recent")
async def get_recent_incidents(days: int = 30):
    """Get recent incidents from last N days"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        cursor = await db.execute(
            """
            SELECT * FROM status_incidents 
            WHERE created_at >= datetime('now', '-{} days')
            ORDER BY created_at DESC
            """.format(days)
        )
        incidents = await cursor.fetchall()
        
        # Parse affected_services JSON
        for incident in incidents:
            if incident.get('affected_services'):
                try:
                    import json
                    incident['affected_services'] = json.loads(incident['affected_services'])
                except:
                    incident['affected_services'] = []
            else:
                incident['affected_services'] = []
        
        return incidents

# Uptime metrics endpoints
@router.get("/uptime")
async def get_uptime_metrics():
    """Get uptime metrics for different time periods"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Get current uptime percentages from service_status
        cursor = await db.execute(
            """
            SELECT 
                AVG(uptime_percentage) as avg_uptime,
                MIN(uptime_percentage) as min_uptime,
                MAX(uptime_percentage) as max_uptime
            FROM service_status
            """
        )
        current_stats = await cursor.fetchone()
        
        # For demo purposes, we'll return static historical data
        # In a real implementation, this would come from historical monitoring data
        uptime_metrics = [
            {"period": "Last 24 hours", "uptime": "100.0%"},
            {"period": "Last 7 days", "uptime": "99.9%"},
            {"period": "Last 30 days", "uptime": "99.8%"},
            {"period": "Last 90 days", "uptime": "99.7%"},
            {"period": "Last 12 months", "uptime": "99.6%"}
        ]
        
        return {
            "current_avg_uptime": current_stats['avg_uptime'] or 0,
            "current_min_uptime": current_stats['min_uptime'] or 0,
            "current_max_uptime": current_stats['max_uptime'] or 0,
            "metrics": uptime_metrics
        }

# Subscription endpoints
@router.post("/subscribe")
async def subscribe_to_status_updates(email: str):
    """Subscribe to status updates (placeholder)"""
    # In a real implementation, this would add email to a notification list
    return {
        "message": "Successfully subscribed to status updates",
        "email": email
    }

@router.get("/rss")
async def get_status_rss():
    """Get RSS feed for status updates"""
    async with aiosqlite.connect("landing_pages.db") as db:
        db.row_factory = dict_factory
        
        # Get recent incidents and updates
        cursor = await db.execute(
            """
            SELECT 'incident' as type, title, description, created_at, updated_at
            FROM status_incidents 
            WHERE created_at >= datetime('now', '-7 days')
            UNION ALL
            SELECT 'service_update' as type, name as title, 
                   'Service status updated to ' || status as description, 
                   updated_at as created_at, updated_at
            FROM service_status 
            WHERE updated_at >= datetime('now', '-7 days')
            ORDER BY created_at DESC
            LIMIT 20
            """
        )
        updates = await cursor.fetchall()
        
        return {
            "title": "WikiAI Status Updates",
            "description": "Real-time status updates for WikiAI services",
            "updates": updates,
            "last_updated": datetime.now().isoformat()
        }

@router.get("/webhook")
async def get_webhook_info():
    """Get webhook information for status notifications"""
    return {
        "webhook_url": "/api/status/webhook",
        "supported_events": [
            "service.down",
            "service.operational", 
            "service.degraded",
            "incident.created",
            "incident.resolved"
        ],
        "authentication": "Bearer token required"
    }

@router.post("/webhook")
async def status_webhook():
    """Webhook endpoint for external monitoring services"""
    # In a real implementation, this would receive and process webhook data
    # from external monitoring services like UptimeRobot, Pingdom, etc.
    return {"message": "Webhook received successfully"}

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for status monitoring system"""
    return {
        "status": "healthy",
        "service": "WikiAI Status Monitoring",
        "timestamp": datetime.now().isoformat()
    }
