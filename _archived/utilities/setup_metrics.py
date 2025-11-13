# Initialize metrics database and start collecting metrics
import os
from metricsdb import init_metrics_db

def setup_metrics():
    """Initialize metrics database tables and ensure metrics collection is ready"""
    print("Setting up metrics collection...")
    
    # Initialize metrics database
    init_metrics_db()
    print("✓ Metrics database initialized")
    
    # Check if metrics database is accessible
    db_path = os.getenv("METRICS_DB_PATH", "metrics.db")
    if os.path.exists(db_path):
        print(f"✓ Metrics database found at {db_path}")
    else:
        print(f"⚠ Warning: Metrics database not found at {db_path}")
    
    print("\nMetrics setup complete. The following data will be collected:")
    print(" - Query metrics (questions, answers, response times)")
    print(" - File access logs")
    print(" - User activity")
    print(" - Security events")
    print(" - System metrics")
    
    print("\nTo access metrics, use the following endpoints:")
    print(" - GET /metrics/queries - Get paginated RAG queries with filters")
    print(" - GET /metrics/aggregations/users - User activity summary")
    print(" - GET /metrics/aggregations/files - File popularity and access stats")
    print(" - GET /metrics/aggregations/timeseries - Time-series data for graphs")
    print(" - GET /metrics/aggregations/models - Model usage breakdown")
    print(" - GET /metrics/summary - Dashboard summary cards")

if __name__ == "__main__":
    setup_metrics()
