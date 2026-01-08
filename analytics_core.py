"""
Comprehensive Analytics Core Module
Powerful analytics engine for collecting, tracking, and analyzing backend operations
Tracks performance, user behavior, security events, and system health
"""

import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field, asdict
import hashlib
import time

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ==================== ENUMS ====================

class EventCategory(str, Enum):
    """Event categorization for routing and analysis"""
    QUERY = "query"
    FILE_ACCESS = "file_access"
    AUTH = "authentication"
    PERFORMANCE = "performance"
    SECURITY = "security"
    SYSTEM = "system"
    ERROR = "error"
    USER_BEHAVIOR = "user_behavior"


class QueryType(str, Enum):
    """Types of queries processed"""
    RAG_SEARCH = "rag_search"
    HUMANIZED = "humanized"
    DIRECT = "direct"
    CHAT = "chat"
    WEBSOCKET = "websocket"


class AccessType(str, Enum):
    """Types of file access"""
    VIEW = "view"
    DOWNLOAD = "download"
    RETRIEVED_IN_RAG = "retrieved_in_rag"
    UPLOADED = "uploaded"
    DELETED = "deleted"


class SecurityEventType(str, Enum):
    """Types of security events"""
    FAILED_LOGIN = "failed_login"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PERMISSION_DENIED = "permission_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT = "rate_limit"


# ==================== DATA MODELS ====================

@dataclass
class QueryMetrics:
    """Comprehensive query metrics"""
    query_id: str
    session_id: str
    user_id: str
    role: str
    question: str
    answer_length: int
    model_type: str
    query_type: QueryType
    response_time_ms: int
    organization_id: Optional[str] = None
    answer_preview: Optional[str] = None
    token_input: int = 0
    token_output: int = 0
    source_document_count: int = 0
    source_files: List[str] = field(default_factory=list)
    humanized: bool = True
    security_filtered: bool = False
    rag_score: float = 0.0
    cache_hit: bool = False
    ip_address: str = None
    user_agent: str = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    success: bool = True
    error_message: str = None


@dataclass
class PerformanceMetrics:
    """System and operation performance metrics"""
    operation_name: str
    duration_ms: int
    organization_id: Optional[str] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    disk_io_mb: float = 0.0
    network_io_mb: float = 0.0
    component: str = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class UserBehaviorEvent:
    """User behavior tracking"""
    user_id: str
    session_id: str
    event_type: str
    organization_id: Optional[str] = None
    event_subtype: str = None
    duration_seconds: int = 0
    interaction_count: int = 0
    success: bool = True
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: str = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class SecurityEvent:
    """Security-related event"""
    event_type: SecurityEventType
    user_id: str = None
    organization_id: Optional[str] = None
    ip_address: str = None
    session_id: str = None
    severity: str = "medium"  # low, medium, high, critical
    details: Dict[str, Any] = field(default_factory=dict)
    blocked: bool = False
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# ==================== DATABASE SCHEMA ====================

class AnalyticsDB:
    """Database management for analytics"""
    
    def __init__(self, db_path: str = "analytics.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize all analytics tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        def _ensure_column(table: str, column: str, column_type: str):
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = {row[1] for row in cursor.fetchall()}
                if column not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
            except Exception:
                pass
        
        # Query analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id TEXT UNIQUE NOT NULL,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT,
                organization_id TEXT,
                question TEXT NOT NULL,
                answer_preview TEXT,
                answer_length INTEGER,
                model_type TEXT,
                query_type TEXT,
                response_time_ms INTEGER,
                token_input INTEGER DEFAULT 0,
                token_output INTEGER DEFAULT 0,
                source_document_count INTEGER,
                source_files JSON,
                humanized BOOLEAN,
                security_filtered BOOLEAN,
                rag_score REAL DEFAULT 0.0,
                cache_hit BOOLEAN DEFAULT 0,
                ip_address TEXT,
                user_agent TEXT,
                success BOOLEAN DEFAULT 1,
                error_message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for query_analytics
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qa_user_id ON query_analytics(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qa_session_id ON query_analytics(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qa_organization_id ON query_analytics(organization_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qa_timestamp ON query_analytics(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qa_query_type ON query_analytics(query_type)')
        
        _ensure_column('query_analytics', 'organization_id', 'TEXT')
        _ensure_column('query_analytics', 'answer_preview', 'TEXT')
        
        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_name TEXT NOT NULL,
                duration_ms INTEGER,
                organization_id TEXT,
                cpu_percent REAL DEFAULT 0.0,
                memory_mb REAL DEFAULT 0.0,
                disk_io_mb REAL DEFAULT 0.0,
                network_io_mb REAL DEFAULT 0.0,
                component TEXT,
                details JSON,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance_metrics
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pm_operation ON performance_metrics(operation_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pm_component ON performance_metrics(component)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pm_organization_id ON performance_metrics(organization_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pm_timestamp ON performance_metrics(timestamp)')
        
        _ensure_column('performance_metrics', 'organization_id', 'TEXT')
        
        # User behavior events
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_behavior_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                organization_id TEXT,
                event_type TEXT NOT NULL,
                event_subtype TEXT,
                duration_seconds INTEGER DEFAULT 0,
                interaction_count INTEGER DEFAULT 1,
                success BOOLEAN DEFAULT 1,
                details JSON,
                ip_address TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for user_behavior_events
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ube_user_id ON user_behavior_events(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ube_session_id ON user_behavior_events(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ube_event_type ON user_behavior_events(event_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ube_organization_id ON user_behavior_events(organization_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ube_timestamp ON user_behavior_events(timestamp)')
        
        _ensure_column('user_behavior_events', 'organization_id', 'TEXT')
        
        # Security events
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id TEXT,
                organization_id TEXT,
                ip_address TEXT NOT NULL,
                session_id TEXT,
                severity TEXT DEFAULT 'medium',
                details JSON,
                blocked BOOLEAN DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for security_events
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_se_user_id ON security_events(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_se_ip_address ON security_events(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_se_event_type ON security_events(event_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_se_severity ON security_events(severity)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_se_organization_id ON security_events(organization_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_se_timestamp ON security_events(timestamp)')
        
        _ensure_column('security_events', 'organization_id', 'TEXT')
        
        # Endpoint access logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS endpoint_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                user_id TEXT,
                organization_id TEXT,
                status_code INTEGER,
                response_time_ms INTEGER,
                request_size_bytes INTEGER,
                response_size_bytes INTEGER,
                ip_address TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for endpoint_access
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ea_endpoint ON endpoint_access(endpoint)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ea_user_id ON endpoint_access(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ea_status ON endpoint_access(status_code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ea_organization_id ON endpoint_access(organization_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ea_timestamp ON endpoint_access(timestamp)')
        
        _ensure_column('endpoint_access', 'organization_id', 'TEXT')
        
        # Error tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS error_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                error_message TEXT,
                error_stack TEXT,
                endpoint TEXT,
                user_id TEXT,
                organization_id TEXT,
                session_id TEXT,
                ip_address TEXT,
                frequency INTEGER DEFAULT 1,
                first_occurrence DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_occurrence DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for error_tracking
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_et_error_type ON error_tracking(error_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_et_endpoint ON error_tracking(endpoint)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_et_user_id ON error_tracking(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_et_organization_id ON error_tracking(organization_id)')
        
        _ensure_column('error_tracking', 'organization_id', 'TEXT')
        
        # Query funnel analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_funnel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                organization_id TEXT,
                step_number INTEGER,
                query_question TEXT,
                documents_found INTEGER,
                user_satisfied BOOLEAN,
                refinement_count INTEGER DEFAULT 0,
                total_time_ms INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for query_funnel
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qf_session_id ON query_funnel(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_qf_user_id ON query_funnel(user_id)')
        
        _ensure_column('query_funnel', 'organization_id', 'TEXT')
        
        # Document analytics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                organization_id TEXT,
                filename TEXT NOT NULL,
                file_id TEXT,
                access_count INTEGER DEFAULT 0,
                rag_hit_count INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                relevance_score REAL DEFAULT 0.0,
                size_bytes INTEGER,
                chunk_count INTEGER,
                last_accessed DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for document_analytics
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_da_filename ON document_analytics(filename)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_da_access_count ON document_analytics(access_count)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_da_rag_hit_count ON document_analytics(rag_hit_count)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_da_organization_id ON document_analytics(organization_id)')
        
        _ensure_column('document_analytics', 'organization_id', 'TEXT')
        
        # User journey tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_journey (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                organization_id TEXT,
                action_sequence JSON,
                session_start DATETIME,
                session_end DATETIME,
                session_duration_seconds INTEGER,
                queries_count INTEGER DEFAULT 0,
                files_accessed INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                conversion_flag BOOLEAN DEFAULT 0
            )
        ''')
        
        # Create indexes for user_journey
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_uj_user_id ON user_journey(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_uj_session_id ON user_journey(session_id)')
        
        _ensure_column('user_journey', 'organization_id', 'TEXT')
        
        conn.commit()
        conn.close()


# ==================== ANALYTICS CORE ====================

class AnalyticsCore:
    """Main analytics engine"""
    
    def __init__(self, db_path: str = "analytics.db"):
        self.db = AnalyticsDB(db_path)
        self.logger = logging.getLogger(__name__)
    
    # ========== QUERY ANALYTICS ==========
    
    def log_query(self, metrics: QueryMetrics) -> bool:
        """Log comprehensive query metrics"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO query_analytics 
                (query_id, session_id, user_id, role, organization_id, question, answer_preview, answer_length,
                 model_type, query_type, response_time_ms, token_input, token_output,
                 source_document_count, source_files, humanized, security_filtered,
                 rag_score, cache_hit, ip_address, user_agent, success, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics.query_id, metrics.session_id, metrics.user_id, metrics.role,
                metrics.organization_id,
                metrics.question, metrics.answer_preview, metrics.answer_length, metrics.model_type,
                metrics.query_type.value, metrics.response_time_ms, metrics.token_input,
                metrics.token_output, metrics.source_document_count,
                json.dumps(metrics.source_files), metrics.humanized, metrics.security_filtered,
                metrics.rag_score, metrics.cache_hit, metrics.ip_address, metrics.user_agent,
                metrics.success, metrics.error_message, metrics.timestamp
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error logging query metrics: {e}")
            return False
    
    def get_query_analytics(
        self,
        limit: int = 100,
        offset: int = 0,
        since_hours: int = 24,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> List[Dict]:
        """Retrieve query analytics"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        where_clauses = []
        params: List[Any] = []

        where_clauses.append("timestamp >= datetime('now', ? || ' hours')")
        params.append(-since_hours)
        if user_id:
            where_clauses.append('user_id = ?')
            params.append(user_id)
        if organization_id:
            where_clauses.append('organization_id = ?')
            params.append(organization_id)

        sql = 'SELECT * FROM query_analytics'
        if where_clauses:
            sql += ' WHERE ' + ' AND '.join(where_clauses)
        sql += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        cursor.execute(sql, params)
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    # ========== PERFORMANCE ANALYTICS ==========
    
    def log_performance(self, metrics: PerformanceMetrics) -> bool:
        """Log performance metrics"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO performance_metrics
                (operation_name, duration_ms, organization_id, cpu_percent, memory_mb, disk_io_mb,
                 network_io_mb, component, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics.operation_name, metrics.duration_ms, metrics.organization_id, metrics.cpu_percent,
                metrics.memory_mb, metrics.disk_io_mb, metrics.network_io_mb,
                metrics.component, json.dumps(metrics.details), metrics.timestamp
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error logging performance metrics: {e}")
            return False
    
    # ========== USER BEHAVIOR ANALYTICS ==========
    
    def log_user_behavior(self, event: UserBehaviorEvent) -> bool:
        """Log user behavior event"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_behavior_events
                (user_id, session_id, organization_id, event_type, event_subtype, duration_seconds,
                 interaction_count, success, details, ip_address, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.user_id, event.session_id, event.organization_id, event.event_type, event.event_subtype,
                event.duration_seconds, event.interaction_count, event.success,
                json.dumps(event.details), event.ip_address, event.timestamp
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error logging user behavior: {e}")
            return False
    
    # ========== SECURITY ANALYTICS ==========
    
    def log_security_event(self, event: SecurityEvent) -> bool:
        """Log security event"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO security_events
                (event_type, user_id, organization_id, ip_address, session_id, severity, details, blocked, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event.event_type.value, event.user_id, event.organization_id, event.ip_address, event.session_id,
                event.severity, json.dumps(event.details), event.blocked, event.timestamp
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error logging security event: {e}")
            return False
    
    # ========== ENDPOINT TRACKING ==========
    
    def log_endpoint_access(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[str],
        status_code: int,
        response_time_ms: int,
        organization_id: Optional[str] = None,
        request_size: int = 0,
        response_size: int = 0,
        ip_address: str = None,
    ) -> bool:
        """Log endpoint access"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO endpoint_access
                (endpoint, method, user_id, organization_id, status_code, response_time_ms,
                 request_size_bytes, response_size_bytes, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                endpoint,
                method,
                user_id,
                organization_id,
                status_code,
                response_time_ms,
                request_size,
                response_size,
                ip_address,
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error logging endpoint access: {e}")
            return False
    
    # ========== ERROR TRACKING ==========
    
    def log_error(
        self,
        error_type: str,
        message: str,
        stack: str = None,
        endpoint: str = None,
        user_id: str = None,
        organization_id: Optional[str] = None,
        session_id: str = None,
        ip_address: str = None,
    ) -> bool:
        """Log error event"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Check if error already exists (for frequency tracking)
            cursor.execute('''
                SELECT id, frequency FROM error_tracking
                WHERE error_type = ? AND error_message = ? AND endpoint = ? AND organization_id IS ?
            ''', (error_type, message, endpoint, organization_id))
            
            existing = cursor.fetchone()
            if existing:
                cursor.execute('''
                    UPDATE error_tracking
                    SET frequency = frequency + 1,
                        last_occurrence = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (existing['id'],))
            else:
                cursor.execute('''
                    INSERT INTO error_tracking
                    (error_type, error_message, error_stack, endpoint, user_id,
                     organization_id, session_id, ip_address, frequency)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ''', (error_type, message, stack, endpoint, user_id, organization_id, session_id, ip_address))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error logging error: {e}")
            return False
    
    # ========== DOCUMENT ANALYTICS ==========
    
    def update_document_analytics(
        self,
        filename: str,
        file_id: str = None,
        organization_id: Optional[str] = None,
        size_bytes: int = 0,
        chunk_count: int = 0,
        increment_access: int = 0,
        increment_rag_hits: int = 0,
    ) -> bool:
        """Update or create document analytics entry"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT id FROM document_analytics WHERE filename = ? AND organization_id IS ?',
                (filename, organization_id),
            )
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute('''
                    UPDATE document_analytics
                    SET access_count = access_count + ?,
                        rag_hit_count = rag_hit_count + ?,
                        last_accessed = CURRENT_TIMESTAMP
                    WHERE filename = ? AND organization_id IS ?
                ''', (increment_access, increment_rag_hits, filename, organization_id))
            else:
                cursor.execute('''
                    INSERT INTO document_analytics
                    (organization_id, filename, file_id, access_count, rag_hit_count, size_bytes, chunk_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (organization_id, filename, file_id, increment_access, increment_rag_hits, size_bytes, chunk_count))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error updating document analytics: {e}")
            return False
    
    # ========== QUERY FUNNEL ANALYSIS ==========
    
    def log_funnel_step(
        self,
        session_id: str,
        user_id: str,
        step_number: int,
        organization_id: Optional[str] = None,
        query: str = None,
        documents_found: int = 0,
        refinement_count: int = 0,
        total_time_ms: int = 0,
        user_satisfied: bool = None,
    ) -> bool:
        """Log query funnel step"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO query_funnel
                (session_id, user_id, organization_id, step_number, query_question, documents_found,
                 user_satisfied, refinement_count, total_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session_id, user_id, organization_id, step_number, query, documents_found,
                  user_satisfied, refinement_count, total_time_ms))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error logging funnel step: {e}")
            return False
    
    # ========== USER JOURNEY TRACKING ==========
    
    def start_user_session(self, user_id: str, session_id: str, organization_id: Optional[str] = None) -> bool:
        """Start tracking user session"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_journey
                (user_id, session_id, organization_id, session_start, action_sequence, queries_count,
                 files_accessed, errors_count)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, 0, 0, 0)
            ''', (user_id, session_id, organization_id, json.dumps([])))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error starting user session: {e}")
            return False
    
    def end_user_session(self, session_id: str, queries_count: int = 0, files_accessed: int = 0, errors_count: int = 0, conversion_flag: bool = False) -> bool:
        """End tracking user session"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE user_journey
                SET session_end = CURRENT_TIMESTAMP,
                    session_duration_seconds = (
                        SELECT CAST((julianday(CURRENT_TIMESTAMP) - julianday(session_start)) * 86400 AS INT)
                    ),
                    queries_count = ?,
                    files_accessed = ?,
                    errors_count = ?,
                    conversion_flag = ?
                WHERE session_id = ?
            ''', (queries_count, files_accessed, errors_count, conversion_flag, session_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error ending user session: {e}")
            return False
    
    # ========== ANALYTICS QUERIES ==========
    
    def get_query_statistics(
        self,
        since_hours: int = 24,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> Dict:
        """Get query statistics"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        where_clauses = ["timestamp >= datetime('now', ? || ' hours')"]
        params: List[Any] = [-since_hours]
        if user_id:
            where_clauses.append('user_id = ?')
            params.append(user_id)
        if organization_id:
            where_clauses.append('organization_id = ?')
            params.append(organization_id)

        cursor.execute(f'''
            SELECT
                COUNT(*) as total_queries,
                AVG(response_time_ms) as avg_response_time_ms,
                MIN(response_time_ms) as min_response_time_ms,
                MAX(response_time_ms) as max_response_time_ms,
                COUNT(DISTINCT user_id) as unique_users,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_queries,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_queries,
                SUM(token_input) as total_tokens_input,
                SUM(token_output) as total_tokens_output,
                AVG(source_document_count) as avg_docs_per_query,
                SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits
            FROM query_analytics
            WHERE {' AND '.join(where_clauses)}
        ''', params)
        
        result = dict(cursor.fetchone())
        conn.close()
        return result
    
    def get_performance_statistics(
        self,
        since_hours: int = 24,
        organization_id: Optional[str] = None,
    ) -> Dict:
        """Get performance statistics"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        where_clauses = ["timestamp >= datetime('now', ? || ' hours')"]
        params: List[Any] = [-since_hours]
        if organization_id:
            where_clauses.append('organization_id = ?')
            params.append(organization_id)
        
        cursor.execute(f'''
            SELECT
                operation_name,
                COUNT(*) as operation_count,
                AVG(duration_ms) as avg_duration_ms,
                MIN(duration_ms) as min_duration_ms,
                MAX(duration_ms) as max_duration_ms,
                AVG(cpu_percent) as avg_cpu,
                AVG(memory_mb) as avg_memory_mb,
                component
            FROM performance_metrics
            WHERE {' AND '.join(where_clauses)}
            GROUP BY operation_name, component
            ORDER BY avg_duration_ms DESC
        ''', params)
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_error_summary(
        self,
        since_hours: int = 24,
        limit: int = 50,
        organization_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get error summary"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        where_clauses = ["last_occurrence >= datetime('now', ? || ' hours')"]
        params: List[Any] = [-since_hours]
        if organization_id:
            where_clauses.append('organization_id = ?')
            params.append(organization_id)
        
        cursor.execute(f'''
            SELECT
                error_type,
                error_message,
                endpoint,
                frequency,
                first_occurrence,
                last_occurrence
            FROM error_tracking
            WHERE {' AND '.join(where_clauses)}
            ORDER BY frequency DESC
            LIMIT ?
        ''', (*params, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_top_documents(self, limit: int = 20, organization_id: Optional[str] = None) -> List[Dict]:
        """Get top performing documents"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        where_clauses = []
        params: List[Any] = []
        if organization_id:
            where_clauses.append('organization_id = ?')
            params.append(organization_id)

        sql = '''
            SELECT
                filename,
                file_id,
                access_count,
                rag_hit_count,
                unique_users,
                relevance_score,
                last_accessed,
                size_bytes,
                chunk_count
            FROM document_analytics
        '''
        if where_clauses:
            sql += ' WHERE ' + ' AND '.join(where_clauses)
        sql += ' ORDER BY rag_hit_count DESC, access_count DESC LIMIT ?'
        params.append(limit)
        cursor.execute(sql, params)
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_user_funnel_analysis(self, user_id: str) -> Dict:
        """Get user's query funnel analysis"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                session_id,
                COUNT(*) as refinement_steps,
                SUM(documents_found) as total_docs_found,
                AVG(documents_found) as avg_docs_per_step,
                SUM(CASE WHEN user_satisfied = 1 THEN 1 ELSE 0 END) as satisfied_queries,
                SUM(CASE WHEN user_satisfied = 0 THEN 1 ELSE 0 END) as unsatisfied_queries,
                SUM(total_time_ms) as total_session_time_ms
            FROM query_funnel
            WHERE user_id = ?
            GROUP BY session_id
            ORDER BY session_id DESC
        ''', (user_id,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_security_events_summary(self, since_hours: int = 24, organization_id: Optional[str] = None) -> Dict:
        """Get security events summary"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        where_clauses = ["timestamp >= datetime('now', ? || ' hours')"]
        params: List[Any] = [-since_hours]
        if organization_id:
            where_clauses.append('organization_id = ?')
            params.append(organization_id)
        
        cursor.execute(f'''
            SELECT
                event_type,
                severity,
                COUNT(*) as count,
                SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END) as blocked_count,
                COUNT(DISTINCT user_id) as affected_users,
                COUNT(DISTINCT ip_address) as unique_ips
            FROM security_events
            WHERE {' AND '.join(where_clauses)}
            GROUP BY event_type, severity
            ORDER BY count DESC
        ''', params)
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_endpoint_performance(
        self,
        since_hours: int = 24,
        limit: int = 30,
        organization_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get endpoint performance metrics"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        where_clauses = ["timestamp >= datetime('now', ? || ' hours')"]
        params: List[Any] = [-since_hours]
        if organization_id:
            where_clauses.append('organization_id = ?')
            params.append(organization_id)
        
        cursor.execute(f'''
            SELECT
                endpoint,
                method,
                COUNT(*) as total_requests,
                AVG(response_time_ms) as avg_response_ms,
                MIN(response_time_ms) as min_response_ms,
                MAX(response_time_ms) as max_response_ms,
                COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count,
                SUM(response_size_bytes) as total_response_bytes,
                COUNT(DISTINCT user_id) as unique_users
            FROM endpoint_access
            WHERE {' AND '.join(where_clauses)}
            GROUP BY endpoint, method
            ORDER BY total_requests DESC
            LIMIT ?
        ''', (*params, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results


# ==================== SINGLETON INSTANCE ====================

_analytics_instance = None

def get_analytics_core() -> AnalyticsCore:
    """Get or create global analytics instance"""
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = AnalyticsCore()
    return _analytics_instance
