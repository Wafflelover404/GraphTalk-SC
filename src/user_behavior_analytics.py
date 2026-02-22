"""
User Behavior Analytics Module
Tracks and analyzes user engagement, session patterns, and conversion
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from analytics_core import AnalyticsCore, UserBehaviorEvent

logger = logging.getLogger(__name__)


class UserBehaviorAnalyzer:
    """Analyzes user behavior and engagement patterns"""
    
    def __init__(self, analytics: Optional[AnalyticsCore] = None):
        self.analytics = analytics or AnalyticsCore()
    
    def get_user_engagement_score(self, user_id: str, since_hours: int = 24) -> Dict:
        """Calculate user engagement score (0-100)"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Get user statistics
        cursor.execute('''
            SELECT
                COUNT(*) as query_count,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_queries,
                AVG(response_time_ms) as avg_response_time,
                COUNT(DISTINCT source_files) as unique_files_accessed
            FROM query_analytics
            WHERE user_id = ? AND timestamp >= datetime('now', ? || ' hours')
        ''', (user_id, -since_hours))
        
        query_stats = dict(cursor.fetchone() or {})
        
        # Get file access count
        cursor.execute('''
            SELECT COUNT(*) as file_access_count
            FROM user_behavior_events
            WHERE user_id = ? AND event_type = 'file_access'
            AND timestamp >= datetime('now', ? || ' hours')
        ''', (user_id, -since_hours))
        
        behavior_stats = dict(cursor.fetchone() or {})
        
        conn.close()
        
        # Calculate engagement score
        score_components = {
            'query_activity': min((query_stats.get('query_count', 0) or 0) / 10 * 100, 100),
            'success_rate': (
                ((query_stats.get('successful_queries', 0) or 0) / (query_stats.get('query_count', 1) or 1)) * 100
                if (query_stats.get('query_count', 0) or 0) > 0 else 0
            ),
            'file_exploration': min((behavior_stats.get('file_access_count', 0) or 0) / 5 * 100, 100),
            'response_time_efficiency': max(100 - ((query_stats.get('avg_response_time', 0) or 0) / 50), 0)
        }
        
        overall_score = sum(score_components.values()) / len(score_components)
        
        return {
            'user_id': user_id,
            'period_hours': since_hours,
            'overall_score': round(overall_score, 2),
            'components': {k: round(v, 2) for k, v in score_components.items()},
            'metrics': {
                'total_queries': query_stats.get('query_count', 0),
                'successful_queries': query_stats.get('successful_queries', 0),
                'unique_files': query_stats.get('unique_files_accessed', 0),
                'file_access_count': behavior_stats.get('file_access_count', 0)
            }
        }
    
    def get_user_session_analysis(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Analyze user sessions"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                session_id,
                session_start,
                session_end,
                session_duration_seconds,
                queries_count,
                files_accessed,
                errors_count,
                conversion_flag
            FROM user_journey
            WHERE user_id = ?
            ORDER BY session_start DESC
            LIMIT ?
        ''', (user_id, limit))
        
        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return sessions
    
    def get_feature_adoption(self, feature_name: str = None, since_days: int = 7) -> Dict:
        """Get feature adoption metrics"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        if feature_name:
            cursor.execute('''
                SELECT
                    event_subtype as feature,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) as usage_count,
                    COUNT(CASE WHEN success = 1 THEN 1 END) as successful_uses
                FROM user_behavior_events
                WHERE event_type = ? AND timestamp >= datetime('now', ? || ' days')
                GROUP BY event_subtype
                ORDER BY usage_count DESC
            ''', (feature_name, -since_days))
        else:
            cursor.execute('''
                SELECT
                    event_subtype as feature,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) as usage_count,
                    COUNT(CASE WHEN success = 1 THEN 1 END) as successful_uses
                FROM user_behavior_events
                WHERE timestamp >= datetime('now', ? || ' days')
                GROUP BY event_subtype
                ORDER BY usage_count DESC
            ''', (-since_days,))
        
        features = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            'period_days': since_days,
            'features': features
        }
    
    def get_user_segments(self) -> Dict:
        """Segment users by behavior patterns"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Power users: >50 queries in last 7 days
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) as count
            FROM query_analytics
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY user_id
            HAVING COUNT(*) > 50
        ''')
        power_users = len(cursor.fetchall())
        
        # Active users: 10-50 queries in last 7 days
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) as count
            FROM query_analytics
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY user_id
            HAVING COUNT(*) BETWEEN 10 AND 50
        ''')
        active_users = len(cursor.fetchall())
        
        # Casual users: 1-9 queries in last 7 days
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) as count
            FROM query_analytics
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY user_id
            HAVING COUNT(*) BETWEEN 1 AND 9
        ''')
        casual_users = len(cursor.fetchall())
        
        # Inactive users: No activity in last 7 days
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) as total
            FROM query_analytics
        ''')
        total_users = cursor.fetchone()[0] or 0
        inactive_users = total_users - power_users - active_users - casual_users
        
        conn.close()
        
        return {
            'power_users': {
                'count': power_users,
                'definition': '>50 queries in 7 days',
                'percent': round((power_users / total_users * 100) if total_users > 0 else 0, 2)
            },
            'active_users': {
                'count': active_users,
                'definition': '10-50 queries in 7 days',
                'percent': round((active_users / total_users * 100) if total_users > 0 else 0, 2)
            },
            'casual_users': {
                'count': casual_users,
                'definition': '1-9 queries in 7 days',
                'percent': round((casual_users / total_users * 100) if total_users > 0 else 0, 2)
            },
            'inactive_users': {
                'count': inactive_users,
                'definition': 'No activity in 7 days',
                'percent': round((inactive_users / total_users * 100) if total_users > 0 else 0, 2)
            },
            'total_users': total_users
        }
    
    def get_user_retention(self, cohort_days: int = 7) -> Dict:
        """Get user retention metrics"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Get users from cohort period
        cursor.execute('''
            SELECT DISTINCT user_id, MIN(session_start) as first_session
            FROM user_journey
            WHERE session_start >= datetime('now', ? || ' days')
            AND session_start < datetime('now')
            GROUP BY user_id
        ''', (-cohort_days,))
        
        cohort_users = [dict(row) for row in cursor.fetchall()]
        
        if not cohort_users:
            return {'status': 'no_data', 'cohort_days': cohort_days}
        
        # Check retention at different intervals
        retention_days = {}
        for days_back in [1, 7, 14, 30]:
            retained = 0
            for user in cohort_users:
                cursor.execute('''
                    SELECT COUNT(*) as count
                    FROM user_journey
                    WHERE user_id = ?
                    AND session_start >= datetime(?, ? || ' days')
                    AND session_start < datetime('now')
                ''', (user['user_id'], user['first_session'], days_back))
                
                if cursor.fetchone()[0] > 0:
                    retained += 1
            
            retention_days[f'day_{days_back}'] = {
                'retained_users': retained,
                'retention_rate': round((retained / len(cohort_users) * 100), 2)
            }
        
        conn.close()
        
        return {
            'cohort_size': len(cohort_users),
            'cohort_days': cohort_days,
            'retention': retention_days
        }
    
    def identify_churned_users(self, days_inactive: int = 14) -> List[Dict]:
        """Identify potentially churned users"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                user_id,
                MAX(session_end) as last_session,
                COUNT(*) as total_sessions,
                AVG(session_duration_seconds) as avg_session_duration
            FROM user_journey
            WHERE session_end < datetime('now', ? || ' days')
            GROUP BY user_id
            ORDER BY last_session DESC
        ''', (-days_inactive,))
        
        churned_users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return churned_users
    
    def get_user_query_patterns(self, user_id: str, limit: int = 20) -> Dict:
        """Get user's query patterns"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Get most common query types
        cursor.execute('''
            SELECT
                query_type,
                COUNT(*) as count,
                AVG(response_time_ms) as avg_response_time,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
            FROM query_analytics
            WHERE user_id = ?
            GROUP BY query_type
            ORDER BY count DESC
        ''', (user_id,))
        
        query_types = [dict(row) for row in cursor.fetchall()]
        
        # Get most accessed documents
        cursor.execute('''
            SELECT
                source_files,
                COUNT(*) as access_count,
                AVG(response_time_ms) as avg_response_time
            FROM query_analytics
            WHERE user_id = ?
            GROUP BY source_files
            ORDER BY access_count DESC
            LIMIT ?
        ''', (user_id, limit))
        
        documents = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'user_id': user_id,
            'query_types': query_types,
            'most_accessed_documents': documents
        }


class ConversionAnalyzer:
    """Analyzes user conversion metrics"""
    
    def __init__(self, analytics: Optional[AnalyticsCore] = None):
        self.analytics = analytics or AnalyticsCore()
    
    def get_conversion_funnel(self, action_sequence: List[str] = None) -> Dict:
        """Analyze conversion funnel"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        # Define default funnel: login -> query -> view_results -> download
        if action_sequence is None:
            action_sequence = ['login', 'first_query', 'view_results', 'download']
        
        # Get funnel metrics
        results = {}
        for i, action in enumerate(action_sequence):
            if i == 0:
                cursor.execute('SELECT COUNT(DISTINCT user_id) as count FROM user_journey')
            else:
                cursor.execute(f'''
                    SELECT COUNT(DISTINCT user_id) as count
                    FROM user_journey
                    WHERE conversion_flag = 1
                ''')
            
            results[action] = cursor.fetchone()[0] or 0
        
        conn.close()
        
        # Calculate conversion rates
        funnel = {}
        for i, action in enumerate(action_sequence):
            if i == 0:
                funnel[action] = {
                    'count': results[action],
                    'conversion_rate': 100.0
                }
            else:
                prev_action = action_sequence[i - 1]
                conversion_rate = (
                    (results[action] / results[prev_action] * 100)
                    if results[prev_action] > 0 else 0
                )
                funnel[action] = {
                    'count': results[action],
                    'conversion_rate': round(conversion_rate, 2),
                    'dropoff': results[prev_action] - results[action]
                }
        
        return {
            'funnel_steps': funnel,
            'overall_conversion_rate': round(
                (results[action_sequence[-1]] / results[action_sequence[0]] * 100)
                if results[action_sequence[0]] > 0 else 0,
                2
            )
        }
    
    def get_high_value_users(self, min_queries: int = 100, since_days: int = 30) -> List[Dict]:
        """Identify high-value users"""
        conn = self.analytics.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                user_id,
                COUNT(*) as query_count,
                AVG(response_time_ms) as avg_response_time,
                COUNT(DISTINCT source_files) as unique_files,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_queries
            FROM query_analytics
            WHERE timestamp >= datetime('now', ? || ' days')
            GROUP BY user_id
            HAVING COUNT(*) >= ?
            ORDER BY query_count DESC
        ''', (-since_days, min_queries))
        
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return users
