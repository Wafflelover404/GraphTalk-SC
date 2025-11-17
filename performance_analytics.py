"""
Performance Analytics Module
Tracks and analyzes system performance, latency, and resource utilization
"""

import time
import logging
from typing import Dict, Optional, List, Callable
from datetime import datetime, timedelta
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from analytics_core import AnalyticsCore, PerformanceMetrics

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


@dataclass
class OperationTiming:
    """Timing information for an operation"""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[int] = None
    memory_start_mb: float = 0.0
    memory_end_mb: float = 0.0
    cpu_percent: float = 0.0


class PerformanceTracker:
    """Tracks performance metrics for operations"""
    
    def __init__(self, analytics: Optional[AnalyticsCore] = None):
        self.analytics = analytics or AnalyticsCore()
        self.timings: Dict[str, OperationTiming] = {}
        self.bottlenecks: List[Dict] = []
    
    @contextmanager
    def track_operation(self, operation_name: str, component: str = None):
        """Context manager for tracking operation performance"""
        start_time = time.time()
        start_mem = 0.0
        
        if psutil:
            try:
                start_mem = psutil.Process().memory_info().rss / 1024 / 1024  # Convert to MB
            except:
                start_mem = 0.0
        
        try:
            yield
        finally:
            end_time = time.time()
            end_mem = 0.0
            cpu_percent = 0.0
            
            if psutil:
                try:
                    end_mem = psutil.Process().memory_info().rss / 1024 / 1024
                    cpu_percent = psutil.Process().cpu_percent(interval=0.1)
                except:
                    end_mem = 0.0
                    cpu_percent = 0.0
            
            duration_ms = int((end_time - start_time) * 1000)
            
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                duration_ms=duration_ms,
                cpu_percent=cpu_percent,
                memory_mb=end_mem - start_mem,
                component=component
            )
            
            self.analytics.log_performance(metrics)
            self.timings[operation_name] = OperationTiming(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                memory_start_mb=start_mem,
                memory_end_mb=end_mem,
                cpu_percent=cpu_percent
            )
            
            # Flag bottlenecks (operations taking > 1 second)
            if duration_ms > 1000:
                self.bottlenecks.append({
                    'operation': operation_name,
                    'duration_ms': duration_ms,
                    'severity': 'high' if duration_ms > 5000 else 'medium'
                })
    
    def get_slowest_operations(self, limit: int = 10) -> List[Dict]:
        """Get slowest operations"""
        sorted_ops = sorted(
            self.timings.items(),
            key=lambda x: x[1].duration_ms or 0,
            reverse=True
        )
        return [
            {
                'operation': name,
                'duration_ms': timing.duration_ms,
                'memory_delta_mb': timing.memory_end_mb - timing.memory_start_mb,
                'cpu_percent': timing.cpu_percent
            }
            for name, timing in sorted_ops[:limit]
        ]
    
    def get_bottlenecks(self) -> List[Dict]:
        """Get identified bottlenecks"""
        return sorted(self.bottlenecks, key=lambda x: x['duration_ms'], reverse=True)


class LatencyAnalyzer:
    """Analyzes latency patterns and breakdown"""
    
    def __init__(self, analytics: Optional[AnalyticsCore] = None):
        self.analytics = analytics or AnalyticsCore()
        self.latency_samples: Dict[str, List[int]] = {}
    
    def record_latency(self, component: str, latency_ms: int):
        """Record latency sample"""
        if component not in self.latency_samples:
            self.latency_samples[component] = []
        self.latency_samples[component].append(latency_ms)
    
    def get_latency_percentiles(self, component: str) -> Dict:
        """Get latency percentiles for a component"""
        if component not in self.latency_samples or not self.latency_samples[component]:
            return {}
        
        samples = sorted(self.latency_samples[component])
        n = len(samples)
        
        return {
            'component': component,
            'p50': samples[int(n * 0.50)],
            'p75': samples[int(n * 0.75)],
            'p90': samples[int(n * 0.90)],
            'p95': samples[int(n * 0.95)],
            'p99': samples[int(n * 0.99)],
            'min': samples[0],
            'max': samples[-1],
            'avg': sum(samples) / n,
            'median': samples[n // 2],
            'sample_count': n
        }
    
    def identify_latency_anomalies(self, component: str, threshold_std_devs: float = 2.0) -> List[int]:
        """Identify anomalous latency spikes"""
        if component not in self.latency_samples or len(self.latency_samples[component]) < 10:
            return []
        
        samples = self.latency_samples[component]
        mean = sum(samples) / len(samples)
        variance = sum((x - mean) ** 2 for x in samples) / len(samples)
        std_dev = variance ** 0.5
        
        threshold = mean + (threshold_std_devs * std_dev)
        anomalies = [s for s in samples if s > threshold]
        
        return anomalies


class ResourceMonitor:
    """Monitors system resource utilization"""
    
    def __init__(self, analytics: Optional[AnalyticsCore] = None):
        self.analytics = analytics or AnalyticsCore()
        self.samples: List[Dict] = []
    
    def collect_metrics(self, component: str = None) -> Dict:
        """Collect current resource metrics"""
        if not psutil:
            return {'timestamp': datetime.utcnow().isoformat(), 'status': 'psutil_not_available'}
        
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent(interval=0.1)
            io_counters = process.io_counters()
            
            metrics = {
                'timestamp': datetime.utcnow().isoformat(),
                'component': component,
                'memory_rss_mb': memory_info.rss / 1024 / 1024,
                'memory_vms_mb': memory_info.vms / 1024 / 1024,
                'cpu_percent': cpu_percent,
                'io_read_mb': io_counters.read_bytes / 1024 / 1024,
                'io_write_mb': io_counters.write_bytes / 1024 / 1024,
            }
            
            # Add system-wide metrics
            try:
                memory_percent = psutil.virtual_memory().percent
                disk_percent = psutil.disk_usage('/').percent
                metrics['system_memory_percent'] = memory_percent
                metrics['system_disk_percent'] = disk_percent
            except:
                pass
            
            self.samples.append(metrics)
            return metrics
        except Exception as e:
            logger.error(f"Error collecting resource metrics: {e}")
            return {}
    
    def get_resource_trends(self, minutes: int = 60) -> Dict:
        """Get resource usage trends"""
        if not self.samples:
            return {}
        
        # Filter samples within time window
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=minutes)
        recent_samples = [
            s for s in self.samples
            if datetime.fromisoformat(s['timestamp']) >= cutoff
        ]
        
        if not recent_samples:
            return {}
        
        memory_values = [s.get('memory_rss_mb', 0) for s in recent_samples]
        cpu_values = [s.get('cpu_percent', 0) for s in recent_samples]
        
        return {
            'period_minutes': minutes,
            'sample_count': len(recent_samples),
            'memory': {
                'min_mb': min(memory_values),
                'max_mb': max(memory_values),
                'avg_mb': sum(memory_values) / len(memory_values),
            },
            'cpu': {
                'min_percent': min(cpu_values),
                'max_percent': max(cpu_values),
                'avg_percent': sum(cpu_values) / len(cpu_values),
            }
        }
    
    def identify_memory_leaks(self, threshold_mb: float = 100) -> Dict:
        """Identify potential memory leaks"""
        if len(self.samples) < 10:
            return {'status': 'insufficient_data', 'samples': len(self.samples)}
        
        memory_values = [s.get('memory_rss_mb', 0) for s in self.samples[-100:]]
        
        # Calculate trend
        first_quarter = sum(memory_values[:len(memory_values)//4]) / (len(memory_values)//4)
        last_quarter = sum(memory_values[-len(memory_values)//4:]) / (len(memory_values)//4)
        
        growth = last_quarter - first_quarter
        
        return {
            'status': 'potential_leak' if growth > threshold_mb else 'normal',
            'memory_growth_mb': round(growth, 2),
            'threshold_mb': threshold_mb,
            'initial_mb': round(first_quarter, 2),
            'current_mb': round(last_quarter, 2)
        }


class QueryPerformanceAnalyzer:
    """Analyzes query performance patterns"""
    
    def __init__(self, analytics: Optional[AnalyticsCore] = None):
        self.analytics = analytics or AnalyticsCore()
    
    def get_query_performance_breakdown(self, since_hours: int = 24) -> Dict:
        """Get detailed query performance breakdown"""
        stats = self.analytics.get_query_statistics(since_hours)
        
        return {
            'period_hours': since_hours,
            'total_queries': stats.get('total_queries', 0),
            'successful_queries': stats.get('successful_queries', 0),
            'failed_queries': stats.get('failed_queries', 0),
            'success_rate_percent': (
                (stats.get('successful_queries', 0) / stats.get('total_queries', 1)) * 100
                if stats.get('total_queries', 0) > 0 else 0
            ),
            'response_time': {
                'avg_ms': round(stats.get('avg_response_time_ms', 0), 2),
                'min_ms': stats.get('min_response_time_ms', 0),
                'max_ms': stats.get('max_response_time_ms', 0),
            },
            'token_usage': {
                'total_input': stats.get('total_tokens_input', 0),
                'total_output': stats.get('total_tokens_output', 0),
            },
            'documents': {
                'avg_per_query': round(stats.get('avg_docs_per_query', 0), 2),
            },
            'cache': {
                'hits': stats.get('cache_hits', 0),
                'hit_rate_percent': (
                    (stats.get('cache_hits', 0) / stats.get('total_queries', 1)) * 100
                    if stats.get('total_queries', 0) > 0 else 0
                )
            },
            'unique_users': stats.get('unique_users', 0),
        }
    
    def identify_slow_queries(self, threshold_ms: int = 5000, limit: int = 50) -> List[Dict]:
        """Identify queries slower than threshold"""
        from analytics_core import get_analytics_core
        core = get_analytics_core()
        
        conn = core.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT
                query_id,
                user_id,
                question,
                response_time_ms,
                source_document_count,
                model_type,
                timestamp
            FROM query_analytics
            WHERE response_time_ms > ?
            ORDER BY response_time_ms DESC
            LIMIT ?
        ''', (threshold_ms, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results


# ==================== HELPER FUNCTIONS ====================

def measure_function(analytics: Optional[AnalyticsCore] = None,
                    component: str = None) -> Callable:
    """Decorator to measure function performance"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            tracker = PerformanceTracker(analytics)
            with tracker.track_operation(f"{func.__module__}.{func.__name__}", component):
                return func(*args, **kwargs)
        return wrapper
    return decorator
