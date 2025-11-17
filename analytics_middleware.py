"""
Enhanced Middleware for Comprehensive Analytics Collection
This middleware integrates with all API endpoints
"""

import time
import logging
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class AdvancedAnalyticsMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive analytics middleware for tracking:
    - Endpoint performance
    - User behavior
    - Error tracking
    - Security events
    """
    
    async def dispatch(self, request: Request, call_next):
        # Start timing
        start_time = time.time()
        
        # Extract request info
        endpoint = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get('user-agent', 'unknown')
        
        # Try to get user from auth header
        user_id = None
        role = None
        session_id = None
        
        try:
            from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
            auth_header = request.headers.get('authorization')
            
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header[7:]
                # Try to get user from token
                from userdb import get_user_by_token
                user = await get_user_by_token(token)
                if user:
                    user_id = user[1]  # username
                    role = user[3]  # role
                    session_id = token
        except Exception as e:
            logger.debug(f"Could not extract user info: {e}")
        
        # Attach to request state for later use
        request.state.user_id = user_id
        request.state.role = role
        request.state.session_id = session_id
        request.state.start_time = start_time
        request.state.endpoint = endpoint
        request.state.client_ip = client_ip
        
        # Get request size
        request_size = 0
        try:
            request_size = int(request.headers.get('content-length', 0))
        except:
            pass
        
        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error
            await log_error_event(
                error_type=type(e).__name__,
                message=str(e),
                endpoint=endpoint,
                user_id=user_id,
                ip_address=client_ip,
                method=method
            )
            raise
        
        # Calculate metrics
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        # Get response size
        response_size = 0
        try:
            response_size = int(response.headers.get('content-length', 0))
        except:
            pass
        
        # Log endpoint access
        await log_endpoint_access(
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            request_size_bytes=request_size,
            response_size_bytes=response_size,
            ip_address=client_ip,
            user_agent=user_agent,
            role=role
        )
        
        # Log user behavior for certain endpoints
        await log_user_behavior_by_endpoint(
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            session_id=session_id,
            success=(response.status_code < 400),
            response_time_ms=response_time_ms,
            ip_address=client_ip
        )
        
        # Log security events for auth endpoints
        await log_security_events_by_endpoint(
            endpoint=endpoint,
            method=method,
            status_code=response.status_code,
            user_id=user_id,
            ip_address=client_ip
        )
        
        return response


async def log_endpoint_access(
    endpoint: str,
    method: str,
    user_id: Optional[str],
    status_code: int,
    response_time_ms: int,
    request_size_bytes: int = 0,
    response_size_bytes: int = 0,
    ip_address: str = None,
    user_agent: str = None,
    role: str = None
):
    """Log endpoint access metrics"""
    try:
        from analytics_core import get_analytics_core
        analytics = get_analytics_core()
        
        analytics.log_endpoint_access(
            endpoint=endpoint,
            method=method,
            user_id=user_id,
            status_code=status_code,
            response_time_ms=response_time_ms,
            request_size=request_size_bytes,
            response_size=response_size_bytes,
            ip_address=ip_address
        )
    except Exception as e:
        logger.error(f"Error logging endpoint access: {e}")


async def log_user_behavior_by_endpoint(
    endpoint: str,
    method: str,
    user_id: Optional[str],
    session_id: Optional[str],
    success: bool,
    response_time_ms: int,
    ip_address: str = None
):
    """Log user behavior based on endpoint type"""
    if not user_id or not session_id:
        return
    
    try:
        from analytics_core import get_analytics_core, UserBehaviorEvent
        analytics = get_analytics_core()
        
        # Categorize endpoint
        if '/query' in endpoint:
            event_type = 'query_search'
            event_subtype = 'rag_search'
        elif '/chat' in endpoint:
            event_type = 'query_search'
            event_subtype = 'chat'
        elif '/upload' in endpoint:
            event_type = 'file_operation'
            event_subtype = 'upload'
        elif '/files' in endpoint and method == 'GET':
            event_type = 'file_access'
            event_subtype = 'list_files'
        elif '/files' in endpoint and method == 'DELETE':
            event_type = 'file_operation'
            event_subtype = 'delete'
        else:
            return
        
        event = UserBehaviorEvent(
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            event_subtype=event_subtype,
            duration_seconds=response_time_ms // 1000,
            interaction_count=1,
            success=success,
            details={
                'endpoint': endpoint,
                'method': method,
                'response_time_ms': response_time_ms
            },
            ip_address=ip_address
        )
        
        analytics.log_user_behavior(event)
    except Exception as e:
        logger.debug(f"Error logging user behavior: {e}")


async def log_security_events_by_endpoint(
    endpoint: str,
    method: str,
    status_code: int,
    user_id: Optional[str],
    ip_address: str = None
):
    """Log security-relevant events"""
    try:
        from analytics_core import get_analytics_core, SecurityEvent, SecurityEventType
        analytics = get_analytics_core()
        
        # Failed login attempt
        if '/login' in endpoint and status_code in [401, 403]:
            event = SecurityEvent(
                event_type=SecurityEventType.FAILED_LOGIN,
                user_id=user_id,
                ip_address=ip_address,
                severity='medium'
            )
            analytics.log_security_event(event)
        
        # Unauthorized access attempt
        elif status_code == 403 and user_id:
            event = SecurityEvent(
                event_type=SecurityEventType.UNAUTHORIZED_ACCESS,
                user_id=user_id,
                ip_address=ip_address,
                severity='high'
            )
            analytics.log_security_event(event)
        
        # Permission denied
        elif status_code == 403 and '/files' in endpoint:
            event = SecurityEvent(
                event_type=SecurityEventType.PERMISSION_DENIED,
                user_id=user_id,
                ip_address=ip_address,
                severity='medium',
                details={'endpoint': endpoint}
            )
            analytics.log_security_event(event)
    except Exception as e:
        logger.debug(f"Error logging security event: {e}")


async def log_error_event(
    error_type: str,
    message: str,
    endpoint: str = None,
    user_id: str = None,
    ip_address: str = None,
    method: str = None
):
    """Log error event"""
    try:
        from analytics_core import get_analytics_core
        analytics = get_analytics_core()
        
        analytics.log_error(
            error_type=error_type,
            message=message,
            endpoint=endpoint,
            user_id=user_id,
            ip_address=ip_address
        )
    except Exception as e:
        logger.error(f"Error logging error event: {e}")


class QueryAnalyticsHelper:
    """Helper for logging query metrics"""
    
    @staticmethod
    async def log_query(
        session_id: str,
        user_id: str,
        role: str,
        question: str,
        answer: str,
        model_type: str,
        query_type: str,
        response_time_ms: int,
        source_documents: list,
        humanized: bool = True,
        security_filtered: bool = False,
        ip_address: str = None,
        cache_hit: bool = False,
        success: bool = True,
        error_message: str = None
    ):
        """Log comprehensive query metrics"""
        try:
            from analytics_core import (
                get_analytics_core, QueryMetrics, QueryType, 
                AccessType
            )
            analytics = get_analytics_core()
            
            # Create metrics
            metrics = QueryMetrics(
                query_id=str(uuid.uuid4()),
                session_id=session_id,
                user_id=user_id,
                role=role,
                question=question,
                answer_length=len(answer or ''),
                model_type=model_type,
                query_type=QueryType(query_type),
                response_time_ms=response_time_ms,
                source_document_count=len(source_documents),
                source_files=[
                    doc.metadata.get('source', 'unknown') 
                    if hasattr(doc, 'metadata') 
                    else doc.get('filename', 'unknown')
                    for doc in (source_documents or [])
                ],
                humanized=humanized,
                security_filtered=security_filtered,
                ip_address=ip_address,
                cache_hit=cache_hit,
                success=success,
                error_message=error_message
            )
            
            # Log query
            analytics.log_query(metrics)
            
            # Update document analytics
            for doc in (source_documents or []):
                filename = (
                    doc.metadata.get('source', 'unknown')
                    if hasattr(doc, 'metadata')
                    else doc.get('filename', 'unknown')
                )
                analytics.update_document_analytics(
                    filename=filename,
                    increment_rag_hits=1
                )
            
            return True
        except Exception as e:
            logger.error(f"Error logging query: {e}")
            return False


class FileAccessAnalyticsHelper:
    """Helper for logging file access"""
    
    @staticmethod
    async def log_file_access(
        user_id: str,
        filename: str,
        access_type: str,
        file_id: str = None,
        session_id: str = None,
        ip_address: str = None,
        role: str = None,
        size_bytes: int = 0,
        chunk_count: int = 0
    ):
        """Log file access event"""
        try:
            from analytics_core import get_analytics_core, AccessType
            analytics = get_analytics_core()
            
            # Update document analytics
            analytics.update_document_analytics(
                filename=filename,
                file_id=file_id,
                size_bytes=size_bytes,
                chunk_count=chunk_count,
                increment_access=1 if access_type == 'view' else 0,
                increment_rag_hits=1 if access_type == 'retrieved_in_rag' else 0
            )
            
            return True
        except Exception as e:
            logger.error(f"Error logging file access: {e}")
            return False


class PerformanceTrackingHelper:
    """Helper for tracking operation performance"""
    
    @staticmethod
    def track_operation(operation_name: str, component: str = None):
        """Decorator for tracking operation performance"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                from performance_analytics import PerformanceTracker
                from analytics_core import get_analytics_core
                
                analytics = get_analytics_core()
                tracker = PerformanceTracker(analytics)
                
                with tracker.track_operation(operation_name, component):
                    return await func(*args, **kwargs)
            return wrapper
        return decorator
