from pydantic import BaseModel
from typing import List, Dict, Optional, Union, Any
from datetime import datetime

class TrendingSearch(BaseModel):
    query: str
    frequency: int
    last_user_id: Optional[str] = None
    timestamp: Optional[str] = None

class UserActivity(BaseModel):
    action: str
    endpoint: str
    details: Optional[str] = None
    timestamp: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class APIPerformanceMetric(BaseModel):
    endpoint: str
    avg_response_time: float
    total_requests: int
    success_rate: float

# Base metrics models
class QueryMetrics(BaseModel):
    total_queries: int
    avg_response_time: float
    successful_queries: int
    model_type_distribution: Dict[str, int]

class FileMetrics(BaseModel):
    total_uploads: int
    total_size_bytes: int
    mime_type_distribution: Dict[str, int]
    successful_uploads: int

class UserMetrics(BaseModel):
    total_users: int
    active_users_24h: int
    queries_per_user: Dict[str, int]
    top_users: List[Dict[str, Any]]

# New models for public/private data
class UserStats(BaseModel):
    total_queries: int
    successful_queries: int
    avg_response_time: float
    frequent_searches: List[str]
    last_activity: Optional[str]
    files_uploaded: int
    total_upload_size: int
    recent_activity: List[UserActivity]
    allowed_files: List[str]

class PublicStats(BaseModel):
    total_users_active: int
    total_queries_24h: int
    global_avg_response_time: float
    trending_searches: List[TrendingSearch]
    popular_files: List[Dict[str, str]]
    system_health: Dict[str, Any]

class UserPublicData(BaseModel):
    user_stats: UserStats
    public_stats: PublicStats

class AdminPrivateStats(BaseModel):
    users_detailed: Dict[str, UserStats]
    ip_activity: Dict[str, List[Dict[str, Any]]]
    security_events: List[Dict[str, Any]]
    system_logs: List[Dict[str, Any]]
    user_agents: Dict[str, int]
    error_rates: Dict[str, float]
    access_patterns: Dict[str, Any]
    sensitive_operations: List[Dict[str, Any]]
    failed_attempts: List[Dict[str, Any]]
    file_access_logs: List[Dict[str, Any]]
    queries_by_model: Dict[str, int]
    user_roles: Dict[str, str]
    ip_geolocation: Dict[str, Dict[str, Any]]

class CompleteMetrics(BaseModel):
    queries: QueryMetrics
    files: FileMetrics
    users: UserMetrics
    trending_searches: List[TrendingSearch]
    api_performance: List[APIPerformanceMetric]

class MetricsResponse(BaseModel):
    status: str
    message: str
    response: Union[
        List[TrendingSearch],
        List[UserActivity],
        List[APIPerformanceMetric],
        CompleteMetrics,
        UserPublicData,
        AdminPrivateStats,
        Dict[str, Any]
    ]
