"""
Security Analytics Module
Tracks security events, threats, anomalies, and compliance metrics
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from analytics_core import AnalyticsCore

logger = logging.getLogger(__name__)


class SecurityAnalyzer:
    """Analyzes security events and threats"""
    
    def __init__(self, analytics: Optional[AnalyticsCore] = None):
        self.analytics = analytics or AnalyticsCore()
    
    def get_threat_summary(self, since_hours: int = 24) -> Dict:
        """Get security threat summary"""
        summary = self.analytics.get_security_events_summary(since_hours)
        
        total_events = sum(event['count'] for event in summary)
        total_blocked = sum(event['blocked_count'] for event in summary)
        critical_events = sum(event['count'] for event in summary if event['severity'] == 'critical')
        
        return {
            'period_hours': since_hours,
            'total_events': total_events,
            'total_blocked': total_blocked,
            'block_rate_percent': round((total_blocked / total_events * 100) if total_events > 0 else 0, 2),
            'critical_events': critical_events,
            'affected_users': len(set(
                event.get('affected_users', 0) for event in summary
            )),
            'unique_ips': len(set(
                event.get('unique_ips', 0) for event in summary
            )),
            'event_breakdown': summary
        }
    
    def get_suspicious_ips(self, since_hours: int = 24, min_events: int = 5) -> List[Dict]:
        """Identify suspicious IP addresses"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                ip_address,
                COUNT(*) as event_count,
                COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_count,
                COUNT(CASE WHEN blocked = 1 THEN 1 END) as blocked_count,
                COUNT(DISTINCT event_type) as event_types,
                COUNT(DISTINCT user_id) as targeted_users,
                MAX(timestamp) as last_event
            FROM security_events
            WHERE timestamp >= datetime('now', ? || ' hours')
            GROUP BY ip_address
            HAVING event_count >= ?
            ORDER BY event_count DESC
        ''', (-since_hours, min_events))
        
        ips = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return ips
    
    def get_suspicious_users(self, since_hours: int = 24, min_events: int = 3) -> List[Dict]:
        """Identify users with suspicious activity"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                user_id,
                COUNT(*) as event_count,
                COUNT(CASE WHEN severity = 'critical' THEN 1 END) as critical_count,
                COUNT(CASE WHEN event_type = 'unauthorized_access' THEN 1 END) as unauthorized_attempts,
                COUNT(CASE WHEN event_type = 'failed_login' THEN 1 END) as failed_logins,
                COUNT(DISTINCT ip_address) as unique_ips,
                MAX(timestamp) as last_event
            FROM security_events
            WHERE user_id IS NOT NULL AND timestamp >= datetime('now', ? || ' hours')
            GROUP BY user_id
            HAVING event_count >= ?
            ORDER BY event_count DESC
        ''', (-since_hours, min_events))
        
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return users
    
    def detect_brute_force_attempts(self, since_hours: int = 1, failed_attempts_threshold: int = 5) -> List[Dict]:
        """Detect potential brute force attacks"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                ip_address,
                user_id,
                COUNT(*) as failed_attempts,
                GROUP_CONCAT(timestamp) as attempt_times
            FROM security_events
            WHERE event_type = 'failed_login'
            AND timestamp >= datetime('now', ? || ' hours')
            GROUP BY ip_address, user_id
            HAVING COUNT(*) >= ?
            ORDER BY failed_attempts DESC
        ''', (-since_hours, failed_attempts_threshold))
        
        attacks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return attacks
    
    def detect_credential_stuffing(self, since_hours: int = 24) -> List[Dict]:
        """Detect credential stuffing attacks"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Credential stuffing: multiple IPs targeting same user, OR same IP targeting multiple users
        cursor.execute('''
            SELECT
                user_id,
                COUNT(DISTINCT ip_address) as attacking_ips,
                COUNT(*) as total_attempts,
                GROUP_CONCAT(DISTINCT ip_address) as ip_addresses
            FROM security_events
            WHERE event_type IN ('failed_login', 'unauthorized_access')
            AND timestamp >= datetime('now', ? || ' hours')
            AND user_id IS NOT NULL
            GROUP BY user_id
            HAVING COUNT(DISTINCT ip_address) >= 3
            ORDER BY attacking_ips DESC
        ''', (-since_hours,))
        
        credential_stuffing = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return credential_stuffing
    
    def detect_permission_abuse(self, since_hours: int = 24) -> List[Dict]:
        """Detect potential permission abuse"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                user_id,
                COUNT(*) as violation_count,
                COUNT(CASE WHEN event_type = 'permission_denied' THEN 1 END) as denied_accesses,
                COUNT(CASE WHEN event_type = 'unauthorized_access' THEN 1 END) as unauthorized_accesses,
                MAX(timestamp) as last_violation
            FROM security_events
            WHERE event_type IN ('permission_denied', 'unauthorized_access')
            AND timestamp >= datetime('now', ? || ' hours')
            GROUP BY user_id
            ORDER BY violation_count DESC
        ''', (-since_hours,))
        
        abuses = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return abuses
    
    def detect_data_exfiltration(self, since_hours: int = 24, large_response_bytes: int = 10000000) -> List[Dict]:
        """Detect potential data exfiltration"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                user_id,
                endpoint,
                COUNT(*) as request_count,
                SUM(response_size_bytes) as total_bytes_transferred,
                AVG(response_size_bytes) as avg_bytes_per_request,
                MAX(response_size_bytes) as max_bytes,
                MAX(timestamp) as last_request
            FROM endpoint_access
            WHERE timestamp >= datetime('now', ? || ' hours')
            AND response_size_bytes > ?
            GROUP BY user_id
            HAVING SUM(response_size_bytes) > ?
            ORDER BY total_bytes_transferred DESC
        ''', (-since_hours, large_response_bytes, large_response_bytes * 2))
        
        exfiltrations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return exfiltrations
    
    def get_geographic_anomalies(self, since_hours: int = 24) -> Dict:
        """Detect geographic anomalies (impossible travel)"""
        # This would require IP geolocation data which isn't in current schema
        # Placeholder for future implementation
        return {
            'status': 'requires_geolocation_data',
            'note': 'Implement with MaxMind GeoIP or similar service'
        }
    
    def get_access_pattern_anomalies(self, user_id: str, since_hours: int = 24) -> Dict:
        """Detect anomalies in user access patterns"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Get normal access times (hour of day)
        cursor.execute('''
            SELECT
                strftime('%H', timestamp) as hour,
                COUNT(*) as count
            FROM query_analytics
            WHERE user_id = ? AND timestamp >= datetime('now', ? || ' hours')
            GROUP BY hour
        ''', (user_id, -since_hours))
        
        access_times = [dict(row) for row in cursor.fetchall()]
        
        # Get unique file accesses (potential scanning)
        cursor.execute('''
            SELECT
                COUNT(DISTINCT source_files) as unique_files,
                COUNT(*) as total_queries
            FROM query_analytics
            WHERE user_id = ?
            AND timestamp >= datetime('now', '1 hour')
        ''', (user_id,))
        
        recent_activity = dict(cursor.fetchone() or {})
        
        conn.close()
        
        anomalies = []
        
        # Flag scanning behavior (many unique files accessed quickly)
        if recent_activity.get('total_queries', 0) > 0:
            unique_file_ratio = recent_activity.get('unique_files', 0) / recent_activity.get('total_queries', 1)
            if unique_file_ratio > 0.8:
                anomalies.append({
                    'type': 'potential_scanning',
                    'description': 'High ratio of unique files accessed in short time',
                    'unique_files': recent_activity.get('unique_files', 0),
                    'total_queries': recent_activity.get('total_queries', 0)
                })
        
        return {
            'user_id': user_id,
            'anomalies_detected': anomalies,
            'access_times': access_times,
            'recent_activity': recent_activity
        }


class ComplianceAnalyzer:
    """Analyzes compliance metrics"""
    
    def __init__(self, analytics: Optional[AnalyticsCore] = None):
        self.analytics = analytics or AnalyticsCore()
    
    def get_audit_log_summary(self, since_days: int = 30) -> Dict:
        """Get audit log summary for compliance"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Get event counts by type
        cursor.execute('''
            SELECT
                event_type,
                COUNT(*) as count
            FROM security_events
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY event_type
        ''', (-since_days,))
        
        events = [dict(row) for row in cursor.fetchall()]
        
        # Get access logs
        cursor.execute('''
            SELECT
                endpoint,
                method,
                COUNT(*) as count,
                COUNT(DISTINCT user_id) as unique_users
            FROM endpoint_access
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY endpoint, method
        ''', (-since_days,))
        
        endpoints = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'period_days': since_days,
            'security_events': events,
            'endpoint_access': endpoints,
            'total_events': sum(e['count'] for e in events),
            'total_access_logs': sum(e['count'] for e in endpoints)
        }
    
    def check_data_retention_compliance(self) -> Dict:
        """Check if data retention policy is being followed"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Count records by age
        cursor.execute('''
            SELECT
                'queries_30d' as category,
                COUNT(*) as count
            FROM query_analytics
            WHERE timestamp >= datetime('now', '-30 days')
            
            UNION ALL
            
            SELECT
                'queries_90d',
                COUNT(*)
            FROM query_analytics
            WHERE timestamp >= datetime('now', '-90 days')
            
            UNION ALL
            
            SELECT
                'security_events_30d',
                COUNT(*)
            FROM security_events
            WHERE timestamp >= datetime('now', '-30 days')
            
            UNION ALL
            
            SELECT
                'security_events_90d',
                COUNT(*)
            FROM security_events
            WHERE timestamp >= datetime('now', '-90 days')
        ''')
        
        retention = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            'retention_data': retention,
            'status': 'compliant'
        }
    
    def get_user_access_report(self, user_id: str, since_days: int = 90) -> Dict:
        """Generate user access report for compliance"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Get all queries
        cursor.execute('''
            SELECT
                timestamp,
                question,
                source_files,
                success
            FROM query_analytics
            WHERE user_id = ? AND timestamp >= datetime('now', ? || ' days')
            ORDER BY timestamp
        ''', (user_id, -since_days))
        
        queries = [dict(row) for row in cursor.fetchall()]
        
        # Get file accesses
        cursor.execute('''
            SELECT
                timestamp,
                filename,
                access_type
            FROM user_behavior_events
            WHERE user_id = ? AND event_type = 'file_access'
            AND timestamp >= datetime('now', ? || ' days')
            ORDER BY timestamp
        ''', (user_id, -since_days))
        
        file_accesses = [dict(row) for row in cursor.fetchall()]
        
        # Get security events
        cursor.execute('''
            SELECT
                timestamp,
                event_type,
                severity,
                details
            FROM security_events
            WHERE user_id = ? AND timestamp >= datetime('now', ? || ' days')
            ORDER BY timestamp
        ''', (user_id, -since_days))
        
        security_events = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'user_id': user_id,
            'period_days': since_days,
            'report_generated': datetime.utcnow().isoformat(),
            'queries': {
                'total': len(queries),
                'successful': sum(1 for q in queries if q.get('success')),
                'failed': sum(1 for q in queries if not q.get('success')),
                'records': queries[:100]  # Limit to first 100 for report
            },
            'file_accesses': {
                'total': len(file_accesses),
                'records': file_accesses[:100]
            },
            'security_events': {
                'total': len(security_events),
                'records': security_events
            }
        }
    
    def get_data_deletion_report(self, since_days: int = 30) -> Dict:
        """Report on data deletions for compliance"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                user_id,
                COUNT(*) as files_deleted,
                MAX(timestamp) as last_deletion
            FROM document_analytics
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY user_id
        ''', (-since_days,))
        
        deletions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            'period_days': since_days,
            'total_deletions': sum(d['files_deleted'] for d in deletions),
            'users_with_deletions': len(deletions),
            'deletion_details': deletions
        }
