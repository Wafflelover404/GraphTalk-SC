"""
Enhanced Metrics API - Advanced Analytics Endpoints
Provides comprehensive analytics dashboards and insights
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from analytics_core import get_analytics_core, EventCategory
from performance_analytics import (
    PerformanceTracker, LatencyAnalyzer, ResourceMonitor, QueryPerformanceAnalyzer
)
from user_behavior_analytics import UserBehaviorAnalyzer, ConversionAnalyzer
from security_analytics import SecurityAnalyzer, ComplianceAnalyzer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/analytics", tags=["Advanced Analytics"])
security_scheme = HTTPBearer(auto_error=False)


# ==================== SECURITY ====================

async def require_admin_or_master(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
):
    """Verify admin access or master key"""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required.")

    from userdb import get_user_by_token
    user = await get_user_by_token(credentials.credentials)
    if user and user[3] == "admin":
        return user

    import os
    import toml
    import bcrypt
    
    SECRETS_PATH = os.path.expanduser("~/secrets.toml")
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r") as f:
                secrets_data = toml.load(f)
            stored_hash = secrets_data.get("access_token_hash")
            if stored_hash:
                if bcrypt.checkpw(credentials.credentials.encode("utf-8"), stored_hash.encode("utf-8")):
                    return ("system", "master", None, "admin")
        except Exception:
            pass

    raise HTTPException(status_code=403, detail="Admin or master key required.")


# ==================== PERFORMANCE ANALYTICS ====================

@router.get("/performance/overview", summary="Performance metrics overview")
async def get_performance_overview(
    since_hours: int = Query(24),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get comprehensive performance overview"""
    analytics = get_analytics_core()
    analyzer = QueryPerformanceAnalyzer(analytics)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "performance": analyzer.get_query_performance_breakdown(since_hours),
        "period_hours": since_hours
    }


@router.get("/performance/query-latency", summary="Query latency analysis")
async def get_query_latency(
    since_hours: int = Query(24),
    limit: int = Query(50),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get query latency percentiles and trends"""
    analytics = get_analytics_core()
    analyzer = QueryPerformanceAnalyzer(analytics)
    
    slow_queries = analyzer.identify_slow_queries(threshold_ms=5000, limit=limit)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "slow_queries": slow_queries,
        "analysis": {
            "queries_over_5s": len(slow_queries),
            "period_hours": since_hours
        }
    }


@router.get("/performance/bottlenecks", summary="Identify system bottlenecks")
async def get_bottlenecks(
    since_hours: int = Query(24),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Identify performance bottlenecks"""
    analytics = get_analytics_core()
    
    performance_stats = analytics.get_performance_statistics(since_hours)
    
    # Sort by average duration
    bottlenecks = sorted(
        performance_stats,
        key=lambda x: x.get('avg_duration_ms', 0),
        reverse=True
    )[:20]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "bottlenecks": bottlenecks,
        "period_hours": since_hours
    }


@router.get("/performance/endpoints", summary="Endpoint performance metrics")
async def get_endpoint_performance(
    since_hours: int = Query(24),
    limit: int = Query(30),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get performance metrics by endpoint"""
    analytics = get_analytics_core()
    
    endpoints = analytics.get_endpoint_performance(since_hours, limit)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": endpoints,
        "total_endpoints": len(endpoints),
        "period_hours": since_hours
    }


# ==================== USER BEHAVIOR ANALYTICS ====================

@router.get("/users/engagement-score/{user_id}", summary="User engagement score")
async def get_user_engagement(
    user_id: str,
    since_hours: int = Query(24),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get individual user engagement score"""
    analyzer = UserBehaviorAnalyzer()
    
    return analyzer.get_user_engagement_score(user_id, since_hours)


@router.get("/users/segments", summary="User segmentation analysis")
async def get_user_segments(
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get user segmentation by activity level"""
    analyzer = UserBehaviorAnalyzer()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "segments": analyzer.get_user_segments()
    }


@router.get("/users/retention", summary="User retention metrics")
async def get_retention_analysis(
    cohort_days: int = Query(7),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get user retention analysis"""
    analyzer = UserBehaviorAnalyzer()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "retention": analyzer.get_user_retention(cohort_days)
    }


@router.get("/users/churned", summary="Identify churned users")
async def get_churned_users(
    days_inactive: int = Query(14),
    limit: int = Query(50),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Identify potentially churned users"""
    analyzer = UserBehaviorAnalyzer()
    
    churned = analyzer.identify_churned_users(days_inactive)[:limit]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "churned_users": churned,
        "inactivity_days": days_inactive
    }


@router.get("/users/feature-adoption", summary="Feature adoption metrics")
async def get_feature_adoption(
    feature_name: Optional[str] = Query(None),
    since_days: int = Query(7),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get feature adoption metrics"""
    analyzer = UserBehaviorAnalyzer()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "adoption": analyzer.get_feature_adoption(feature_name, since_days)
    }


@router.get("/users/funnel/{user_id}", summary="User query funnel")
async def get_user_funnel(
    user_id: str,
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get user's query refinement funnel"""
    analytics = get_analytics_core()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "funnel": analytics.get_user_funnel_analysis(user_id)
    }


@router.get("/users/high-value", summary="High-value users")
async def get_high_value_users(
    min_queries: int = Query(100),
    since_days: int = Query(30),
    limit: int = Query(50),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Identify high-value users"""
    analyzer = ConversionAnalyzer()
    
    users = analyzer.get_high_value_users(min_queries, since_days)[:limit]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "high_value_users": users,
        "criteria": {
            "min_queries": min_queries,
            "period_days": since_days
        }
    }


@router.get("/conversion/funnel", summary="Conversion funnel analysis")
async def get_conversion_funnel(
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get user conversion funnel"""
    analyzer = ConversionAnalyzer()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "funnel": analyzer.get_conversion_funnel()
    }


# ==================== SECURITY ANALYTICS ====================

@router.get("/security/threats", summary="Threat summary")
async def get_threats(
    since_hours: int = Query(24),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get security threat summary"""
    analyzer = SecurityAnalyzer()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "threats": analyzer.get_threat_summary(since_hours)
    }


@router.get("/security/suspicious-ips", summary="Suspicious IP addresses")
async def get_suspicious_ips(
    since_hours: int = Query(24),
    min_events: int = Query(5),
    limit: int = Query(50),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get list of suspicious IP addresses"""
    analyzer = SecurityAnalyzer()
    
    ips = analyzer.get_suspicious_ips(since_hours, min_events)[:limit]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "suspicious_ips": ips,
        "criteria": {
            "period_hours": since_hours,
            "min_events": min_events
        }
    }


@router.get("/security/suspicious-users", summary="Suspicious user activity")
async def get_suspicious_users(
    since_hours: int = Query(24),
    min_events: int = Query(3),
    limit: int = Query(50),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get list of users with suspicious activity"""
    analyzer = SecurityAnalyzer()
    
    users = analyzer.get_suspicious_users(since_hours, min_events)[:limit]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "suspicious_users": users,
        "criteria": {
            "period_hours": since_hours,
            "min_events": min_events
        }
    }


@router.get("/security/brute-force", summary="Brute force attack detection")
async def detect_brute_force(
    since_hours: int = Query(1),
    threshold: int = Query(5),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Detect potential brute force attacks"""
    analyzer = SecurityAnalyzer()
    
    attacks = analyzer.detect_brute_force_attempts(since_hours, threshold)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "brute_force_attacks": attacks,
        "threshold": threshold,
        "period_hours": since_hours
    }


@router.get("/security/credential-stuffing", summary="Credential stuffing detection")
async def detect_credential_stuffing(
    since_hours: int = Query(24),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Detect potential credential stuffing attacks"""
    analyzer = SecurityAnalyzer()
    
    attacks = analyzer.detect_credential_stuffing(since_hours)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "credential_stuffing_attacks": attacks,
        "period_hours": since_hours
    }


@router.get("/security/permission-abuse", summary="Permission abuse detection")
async def detect_permission_abuse(
    since_hours: int = Query(24),
    limit: int = Query(50),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Detect potential permission abuse"""
    analyzer = SecurityAnalyzer()
    
    abuses = analyzer.detect_permission_abuse(since_hours)[:limit]
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "permission_abuse_incidents": abuses,
        "period_hours": since_hours
    }


@router.get("/security/anomalies/{user_id}", summary="Access pattern anomalies")
async def get_access_anomalies(
    user_id: str,
    since_hours: int = Query(24),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get access pattern anomalies for a user"""
    analyzer = SecurityAnalyzer()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "user_id": user_id,
        "anomalies": analyzer.get_access_pattern_anomalies(user_id, since_hours)
    }


# ==================== COMPLIANCE & AUDITING ====================

@router.get("/compliance/audit-log", summary="Audit log summary")
async def get_audit_log(
    since_days: int = Query(30),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get audit log summary for compliance"""
    analyzer = ComplianceAnalyzer()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "audit_log": analyzer.get_audit_log_summary(since_days),
        "period_days": since_days
    }


@router.get("/compliance/retention", summary="Data retention compliance")
async def check_retention(
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Check data retention policy compliance"""
    analyzer = ComplianceAnalyzer()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "retention": analyzer.check_data_retention_compliance()
    }


@router.get("/compliance/user-report/{user_id}", summary="User access report")
async def get_user_access_report(
    user_id: str,
    since_days: int = Query(90),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Generate user access report for compliance"""
    analyzer = ComplianceAnalyzer()
    
    return analyzer.get_user_access_report(user_id, since_days)


# ==================== DOCUMENT ANALYTICS ====================

@router.get("/documents/top", summary="Top performing documents")
async def get_top_documents(
    limit: int = Query(20),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get top performing documents by usage and relevance"""
    analytics = get_analytics_core()
    
    documents = analytics.get_top_documents(limit)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "top_documents": documents
    }


# ==================== ERROR TRACKING ====================

@router.get("/errors/summary", summary="Error summary")
async def get_error_summary(
    since_hours: int = Query(24),
    limit: int = Query(50),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get error summary and trends"""
    analytics = get_analytics_core()
    
    errors = analytics.get_error_summary(since_hours, limit)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "errors": errors,
        "total_unique_errors": len(errors),
        "period_hours": since_hours
    }


# ==================== CUSTOM REPORTS ====================

@router.get("/report/executive-summary", summary="Executive summary dashboard")
async def get_executive_summary(
    since_hours: int = Query(24),
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get executive summary dashboard"""
    analytics = get_analytics_core()
    
    query_stats = analytics.get_query_statistics(since_hours)
    performance = analytics.get_performance_statistics(since_hours)
    errors = analytics.get_error_summary(since_hours, limit=5)
    threats = SecurityAnalyzer(analytics).get_threat_summary(since_hours)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "period_hours": since_hours,
        "key_metrics": {
            "total_queries": query_stats.get('total_queries', 0),
            "success_rate": round(
                ((query_stats.get('successful_queries', 0) or 0) / 
                 (query_stats.get('total_queries', 1) or 1)) * 100, 2
            ),
            "avg_response_time_ms": round(query_stats.get('avg_response_time_ms', 0) or 0, 2),
            "cache_hit_rate": round(
                ((query_stats.get('cache_hits', 0) or 0) / 
                 (query_stats.get('total_queries', 1) or 1)) * 100, 2
            ),
            "unique_users": query_stats.get('unique_users', 0),
        },
        "performance": {
            "slowest_operations": sorted(
                performance,
                key=lambda x: x.get('avg_duration_ms', 0),
                reverse=True
            )[:5]
        },
        "errors": {
            "total_errors": len(errors),
            "top_errors": errors[:3]
        },
        "security": {
            "security_events": threats.get('total_events', 0),
            "blocked_events": threats.get('total_blocked', 0),
            "critical_events": threats.get('critical_events', 0)
        }
    }


@router.get("/report/daily-summary", summary="Daily summary report")
async def get_daily_summary(
    admin_user=Depends(require_admin_or_master)
) -> Dict:
    """Get daily summary report"""
    analytics = get_analytics_core()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "period_hours": 24,
        "summary": {
            "queries": analytics.get_query_statistics(24),
            "performance": analytics.get_performance_statistics(24),
            "errors": analytics.get_error_summary(24, 10),
            "security": SecurityAnalyzer(analytics).get_threat_summary(24),
            "documents": analytics.get_top_documents(10)
        }
    }
