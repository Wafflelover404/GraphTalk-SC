#!/usr/bin/env python3
"""
Advanced Analytics System - Comprehensive Test Script
Tests all new metrics endpoints with the provided admin token
"""

import requests
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
ADMIN_TOKEN = "29c63be0-06c1-4051-b3ef-034e46a6dfed"

# Test data
HEADERS = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}

class AnalyticsTestSuite:
    """Comprehensive test suite for analytics endpoints"""
    
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def print_header(self, title: str):
        """Print formatted header"""
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
    
    def print_test(self, name: str, status: str, details: str = ""):
        """Print test result"""
        symbol = "✅" if status == "PASS" else "❌"
        print(f"{symbol} {name}")
        if details:
            print(f"   └─ {details}")
        
        if status == "PASS":
            self.passed += 1
        else:
            self.failed += 1
        
        self.results.append({
            "test": name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def test_endpoint(self, 
                     name: str, 
                     method: str, 
                     endpoint: str, 
                     params: Optional[Dict] = None,
                     expected_status: int = 200) -> Optional[Dict]:
        """Test a single endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=params, timeout=10)
            else:
                self.print_test(name, "SKIP", f"Unknown method: {method}")
                return None
            
            # Check response status
            if response.status_code != expected_status:
                self.print_test(
                    name, 
                    "FAIL", 
                    f"Expected {expected_status}, got {response.status_code}"
                )
                return None
            
            # Parse JSON response
            try:
                data = response.json()
                
                # Check for success status in response
                if isinstance(data, dict):
                    if data.get("status") == "success" or response.status_code == 200:
                        self.print_test(name, "PASS", f"Status: {response.status_code}")
                        return data
                    else:
                        self.print_test(
                            name, 
                            "FAIL", 
                            f"Response status: {data.get('status', 'unknown')}"
                        )
                        return None
                else:
                    self.print_test(name, "PASS", f"Status: {response.status_code}")
                    return data
            except json.JSONDecodeError:
                self.print_test(name, "FAIL", "Invalid JSON response")
                return None
            
        except requests.exceptions.ConnectionError:
            self.print_test(
                name, 
                "FAIL", 
                f"Connection error: Cannot reach {self.base_url}"
            )
            return None
        except requests.exceptions.Timeout:
            self.print_test(name, "FAIL", "Request timeout (10s)")
            return None
        except Exception as e:
            self.print_test(name, "FAIL", str(e))
            return None
    
    def validate_response_structure(self, 
                                   response: Dict, 
                                   expected_keys: list) -> bool:
        """Validate response has expected structure"""
        if not isinstance(response, dict):
            return False
        
        for key in expected_keys:
            if key not in response:
                return False
        
        return True
    
    def run_all_tests(self):
        """Run all test suites"""
        self.print_header("Advanced Analytics Test Suite")
        print(f"Base URL: {self.base_url}")
        print(f"Admin Token: {self.token[:16]}...")
        print(f"Test Start Time: {datetime.now().isoformat()}")
        
        # Test 1: Health Check
        self.test_health_endpoint()
        
        # Test 2: Metrics Summary
        self.test_metrics_summary()
        
        # Test 3: Metrics Queries
        self.test_metrics_queries()
        
        # Test 4: Metrics Performance
        self.test_metrics_performance()
        
        # Test 5: Metrics Errors
        self.test_metrics_errors()
        
        # Test 6: Metrics Documents
        self.test_metrics_documents()
        
        # Test 7: Advanced Analytics - Performance
        self.test_analytics_performance()
        
        # Test 8: Advanced Analytics - Users
        self.test_analytics_users()
        
        # Test 9: Advanced Analytics - Security
        self.test_analytics_security()
        
        # Test 10: Advanced Analytics - Compliance
        self.test_analytics_compliance()
        
        # Print Summary
        self.print_summary()
        
        # Print Detailed Results
        self.print_detailed_results()
    
    def test_health_endpoint(self):
        """Test /metrics/health endpoint"""
        self.print_header("Test 1: Health Check Endpoint")
        
        response = self.test_endpoint(
            "GET /metrics/health",
            "GET",
            "/metrics/health"
        )
        
        if response:
            print(f"   Health Status: {response.get('health', 'unknown')}")
            print(f"   Queries Last Hour: {response.get('data', {}).get('queries_last_hour', 0)}")
            print(f"   Analytics Enabled: {response.get('data', {}).get('analytics_enabled', False)}")
    
    def test_metrics_summary(self):
        """Test /metrics/summary endpoint"""
        self.print_header("Test 2: Metrics Summary Endpoint")
        
        # Test with different time ranges
        for since in ["1h", "24h", "7d"]:
            response = self.test_endpoint(
                f"GET /metrics/summary (since={since})",
                "GET",
                "/metrics/summary",
                params={"since": since}
            )
            
            if response:
                data = response.get("data", {})
                print(f"   Period: {since}")
                print(f"     - Total Queries: {data.get('total_queries', 0)}")
                print(f"     - Success Rate: {data.get('success_rate', 0)}%")
                print(f"     - Avg Response Time: {data.get('avg_response_time_ms', 0)}ms")
                print(f"     - Unique Users: {data.get('unique_users', 0)}")
    
    def test_metrics_queries(self):
        """Test /metrics/queries endpoint"""
        self.print_header("Test 3: Metrics Queries Endpoint")
        
        # Test with pagination
        response = self.test_endpoint(
            "GET /metrics/queries (limit=10, offset=0)",
            "GET",
            "/metrics/queries",
            params={"since": "24h", "limit": 10, "offset": 0}
        )
        
        if response:
            queries = response.get("data", {}).get("queries", [])
            print(f"   Total Queries Retrieved: {len(queries)}")
            if queries:
                print(f"   Sample Query:")
                first_query = queries[0]
                print(f"     - User: {first_query.get('user_id', 'N/A')[:20]}...")
                print(f"     - Response Time: {first_query.get('response_time_ms', 0)}ms")
                print(f"     - Success: {first_query.get('success', False)}")
    
    def test_metrics_performance(self):
        """Test /metrics/performance endpoint"""
        self.print_header("Test 4: Metrics Performance Endpoint")
        
        response = self.test_endpoint(
            "GET /metrics/performance (limit=20)",
            "GET",
            "/metrics/performance",
            params={"since": "24h", "limit": 20}
        )
        
        if response:
            operations = response.get("data", {}).get("operations", [])
            print(f"   Total Operations: {len(operations)}")
            if operations:
                print(f"   Slowest Operations:")
                for i, op in enumerate(operations[:3], 1):
                    print(f"     {i}. {op.get('operation_name', 'Unknown')} "
                          f"- Avg: {op.get('avg_duration_ms', 0)}ms")
    
    def test_metrics_errors(self):
        """Test /metrics/errors endpoint"""
        self.print_header("Test 5: Metrics Errors Endpoint")
        
        response = self.test_endpoint(
            "GET /metrics/errors (limit=50)",
            "GET",
            "/metrics/errors",
            params={"since": "24h", "limit": 50}
        )
        
        if response:
            errors = response.get("data", {}).get("errors", [])
            print(f"   Total Unique Errors: {len(errors)}")
            if errors:
                print(f"   Most Frequent Errors:")
                for i, error in enumerate(errors[:3], 1):
                    print(f"     {i}. {error.get('error_type', 'Unknown')}")
    
    def test_metrics_documents(self):
        """Test /metrics/documents endpoint"""
        self.print_header("Test 6: Metrics Documents Endpoint")
        
        response = self.test_endpoint(
            "GET /metrics/documents (limit=20)",
            "GET",
            "/metrics/documents",
            params={"limit": 20}
        )
        
        if response:
            documents = response.get("data", {}).get("documents", [])
            print(f"   Total Documents Tracked: {len(documents)}")
            if documents:
                print(f"   Top Documents:")
                for i, doc in enumerate(documents[:3], 1):
                    print(f"     {i}. {doc.get('filename', 'Unknown')} "
                          f"- Accesses: {doc.get('access_count', 0)}")
    
    def test_analytics_performance(self):
        """Test /analytics/performance/* endpoints"""
        self.print_header("Test 7: Advanced Analytics - Performance")
        
        endpoints = [
            ("/analytics/performance/latency-distribution", "Latency Distribution"),
            ("/analytics/performance/endpoint-performance", "Endpoint Performance"),
        ]
        
        for endpoint, name in endpoints:
            self.test_endpoint(
                f"GET {endpoint}",
                "GET",
                endpoint,
                params={"since_hours": 24}
            )
    
    def test_analytics_users(self):
        """Test /analytics/users/* endpoints"""
        self.print_header("Test 8: Advanced Analytics - Users")
        
        endpoints = [
            ("/analytics/users/engagement", "User Engagement"),
            ("/analytics/users/segments", "User Segments"),
            ("/analytics/users/retention", "User Retention"),
        ]
        
        for endpoint, name in endpoints:
            response = self.test_endpoint(
                f"GET {endpoint}",
                "GET",
                endpoint
            )
            
            if response and endpoint == "/analytics/users/engagement":
                data = response.get("data", [])
                print(f"   Users Tracked: {len(data)}")
                if data:
                    print(f"   Sample User Engagement:")
                    for i, user in enumerate(data[:2], 1):
                        print(f"     {i}. Score: {user.get('engagement_score', 0)}")
    
    def test_analytics_security(self):
        """Test /analytics/security/* endpoints"""
        self.print_header("Test 9: Advanced Analytics - Security")
        
        endpoints = [
            ("/analytics/security/events", "Security Events"),
            ("/analytics/security/threat-summary", "Threat Summary"),
        ]
        
        for endpoint, name in endpoints:
            self.test_endpoint(
                f"GET {endpoint}",
                "GET",
                endpoint,
                params={"since_hours": 24} if endpoint == "/analytics/security/events" else None
            )
    
    def test_analytics_compliance(self):
        """Test /analytics/compliance/* endpoints"""
        self.print_header("Test 10: Advanced Analytics - Compliance")
        
        endpoints = [
            ("/analytics/compliance/audit-log", "Audit Log"),
            ("/analytics/compliance/data-retention-status", "Data Retention Status"),
        ]
        
        for endpoint, name in endpoints:
            self.test_endpoint(
                f"GET {endpoint}",
                "GET",
                endpoint,
                params={"since_hours": 24} if endpoint == "/analytics/compliance/audit-log" else None
            )
    
    def print_summary(self):
        """Print test summary"""
        self.print_header("Test Summary")
        
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        
        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED! Analytics system is working correctly.")
        else:
            print(f"\n⚠️  {self.failed} test(s) failed. See details above.")
    
    def print_detailed_results(self):
        """Print detailed results"""
        self.print_header("Detailed Test Results")
        
        print(f"\n{'Test':<50} {'Status':<10} {'Details'}")
        print("-" * 90)
        
        for result in self.results:
            test = result["test"][:48]
            status = result["status"]
            details = result["details"][:35] if result["details"] else "OK"
            print(f"{test:<50} {status:<10} {details}")


def main():
    """Run the test suite"""
    print("\n" + "="*70)
    print("  ADVANCED ANALYTICS SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*70)
    print(f"\nStarting analytics tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Create test suite
    suite = AnalyticsTestSuite(BASE_URL, ADMIN_TOKEN)
    
    # Run all tests
    suite.run_all_tests()
    
    # Print execution time info
    print("\n" + "="*70)
    print(f"Test execution completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    # Return exit code based on results
    return 0 if suite.failed == 0 else 1


if __name__ == "__main__":
    exit(main())
