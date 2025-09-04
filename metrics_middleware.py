from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from metricsdb import log_event, log_query, log_file_access, log_security_event
import time

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Get client IP
        client_ip = request.client.host if request.client else None
        
        # Get current path for metrics
        path = request.url.path
        
        response = await call_next(request)
        
        # Calculate response time
        response_time = int((time.time() - start_time) * 1000)
        
        # Store response time metric
        if hasattr(request.state, "user"):
            user = request.state.user
            log_event(
                event_type="api_request",
                user_id=user[1] if user else None,
                role=user[3] if user else None,
                ip_address=client_ip,
                details={
                    "path": path,
                    "method": request.method,
                    "response_time_ms": response_time,
                    "status_code": response.status_code
                }
            )
        
        return response
