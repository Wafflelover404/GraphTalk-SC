#!/usr/bin/env python3
"""
Advanced Analytics System - Quick Test Script (No Dependencies)
Tests all new metrics endpoints with curl commands
"""

import subprocess
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:9001"
ADMIN_TOKEN = "29c63be0-06c1-4051-b3ef-034e46a6dfed"

class AnalyticsQuickTest:
    """Quick test suite using curl"""
    
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token
        self.passed = 0
        self.failed = 0
    
    def print_header(self, title: str):
        """Print formatted header"""
        print(f"\n{'='*80}")
        print(f"  {title}")
        print(f"{'='*80}\n")
    
    def test_curl(self, name: str, endpoint: str, params: str = "") -> bool:
        """Test endpoint using curl"""
        try:
            cmd = [
                "curl",
                "-s",
                "-H", f"Authorization: Bearer {self.token}",
                "-H", "Content-Type: application/json",
                f"{self.base_url}{endpoint}{params}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                print(f"❌ {name}")
                print(f"   Error: {result.stderr[:100]}")
                self.failed += 1
                return False
            
            try:
                data = json.loads(result.stdout)
                
                # Check response
                if isinstance(data, dict):
                    status = data.get("status", "unknown")
                    if status in ["success", "ok"] or "error" not in str(data).lower():
                        print(f"✅ {name}")
                        
                        # Print key metrics if available
                        if "response" in data:
                            self._print_data_summary(data.get("response", {}))
                        elif "data" in data:
                            self._print_data_summary(data.get("data", {}))
                        
                        self.passed += 1
                        return True
                    else:
                        print(f"❌ {name}")
                        print(f"   Status: {status}")
                        self.failed += 1
                        return False
                else:
                    print(f"✅ {name}")
                    self.passed += 1
                    return True
                    
            except json.JSONDecodeError:
                print(f"❌ {name}")
                print(f"   Invalid JSON response")
                self.failed += 1
                return False
                
        except subprocess.TimeoutExpired:
            print(f"❌ {name}")
            print(f"   Timeout (10s)")
            self.failed += 1
            return False
        except Exception as e:
            print(f"❌ {name}")
            print(f"   Error: {str(e)[:100]}")
            self.failed += 1
            return False
    
    def _print_data_summary(self, data):
        """Print summary of response data"""
        if isinstance(data, dict):
            # Print key metrics
            for key, value in list(data.items())[:3]:
                if not isinstance(value, (dict, list)):
                    print(f"   └─ {key}: {value}")
        elif isinstance(data, list) and len(data) > 0:
            print(f"   └─ Items: {len(data)}")
    
    def run_tests(self):
        """Run all endpoint tests"""
        self.print_header("Advanced Analytics - Endpoint Tests")
        print(f"Base URL: {self.base_url}")
        print(f"Admin Token: {self.token[:16]}...\n")
        
        # Test 1: Health Check
        self.print_header("1️⃣  Health Check Endpoint")
        self.test_curl(
            "GET /metrics/health",
            "/metrics/health"
        )
        
        # Test 2: Metrics Summary
        self.print_header("2️⃣  Metrics Summary Endpoints")
        self.test_curl(
            "GET /metrics/summary (last 24 hours)",
            "/metrics/summary?since=24h&scope=org"
        )
        self.test_curl(
            "GET /metrics/summary (last 7 days)",
            "/metrics/summary?since=7d&scope=org"
        )
        self.test_curl(
            "GET /metrics/summary (user scope)",
            "/metrics/summary?since=24h&scope=user"
        )
        self.test_curl(
            "GET /metrics/summary (global scope)",
            "/metrics/summary?since=24h&scope=global"
        )
        
        # Test 3: Metrics Queries
        self.print_header("3️⃣  Metrics Queries Endpoints")
        self.test_curl(
            "GET /metrics/queries",
            "/metrics/queries?since=24h&limit=10&scope=org"
        )
        self.test_curl(
            "GET /metrics/queries (user scope)",
            "/metrics/queries?since=24h&limit=10&scope=user"
        )
        
        # Test 4: Metrics Performance
        self.print_header("4️⃣  Metrics Performance Endpoints")
        self.test_curl(
            "GET /metrics/performance",
            "/metrics/performance?since=24h&limit=20"
        )
        
        # Test 5: Metrics Errors
        self.print_header("5️⃣  Metrics Errors Endpoints")
        self.test_curl(
            "GET /metrics/errors",
            "/metrics/errors?since=24h&limit=50"
        )
        
        # Test 6: Metrics Documents
        self.print_header("6️⃣  Metrics Documents Endpoints")
        self.test_curl(
            "GET /metrics/documents",
            "/metrics/documents?limit=20"
        )
        
        # Test 7: Advanced Analytics - Performance
        self.print_header("7️⃣  Advanced Analytics - Performance")
        self.test_curl(
            "GET /analytics/performance/latency-distribution",
            "/analytics/performance/latency-distribution?since_hours=24"
        )
        self.test_curl(
            "GET /analytics/performance/endpoint-performance",
            "/analytics/performance/endpoint-performance?since_hours=24"
        )
        
        # Test 8: Advanced Analytics - Users
        self.print_header("8️⃣  Advanced Analytics - Users")
        self.test_curl(
            "GET /analytics/users/engagement",
            "/analytics/users/engagement"
        )
        self.test_curl(
            "GET /analytics/users/segments",
            "/analytics/users/segments"
        )
        self.test_curl(
            "GET /analytics/users/retention",
            "/analytics/users/retention"
        )
        
        # Test 9: Advanced Analytics - Security
        self.print_header("9️⃣  Advanced Analytics - Security")
        self.test_curl(
            "GET /analytics/security/events",
            "/analytics/security/events?since_hours=24&limit=100"
        )
        self.test_curl(
            "GET /analytics/security/threat-summary",
            "/analytics/security/threat-summary"
        )
        self.test_curl(
            "GET /analytics/security/suspicious-ips",
            "/analytics/security/suspicious-ips?limit=20"
        )
        
        # Test 10: Advanced Analytics - Compliance
        self.print_header("🔟 Advanced Analytics - Compliance")
        self.test_curl(
            "GET /analytics/compliance/audit-log",
            "/analytics/compliance/audit-log?since_hours=24"
        )
        self.test_curl(
            "GET /analytics/compliance/data-retention-status",
            "/analytics/compliance/data-retention-status"
        )
        
        # Test 11: Advanced Analytics - Conversion
        self.print_header("1️⃣1️⃣  Advanced Analytics - Conversion")
        self.test_curl(
            "GET /analytics/conversion/funnel",
            "/analytics/conversion/funnel"
        )
        
        # Print Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        self.print_header("📊 Test Results Summary")
        
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"Total Endpoints Tested: {total}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Pass Rate: {pass_rate:.1f}%\n")
        
        if self.failed == 0:
            print("🎉 ALL TESTS PASSED!")
            print("✨ Advanced Analytics System is working correctly.\n")
            return 0
        else:
            print(f"⚠️  {self.failed} test(s) failed.")
            print("Please check the errors above and verify:")
            print("  1. API server is running on " + self.base_url)
            print("  2. Admin token is valid")
            print("  3. Analytics modules are loaded\n")
            return 1


def print_instructions():
    """Print test instructions"""
    print("\n" + "="*80)
    print("  ADVANCED ANALYTICS TEST SUITE - INSTRUCTIONS")
    print("="*80 + "\n")
    
    print("Prerequisites:")
    print("  1. FastAPI server running: python3 api.py")
    print("  2. curl installed (usually pre-installed on macOS/Linux)")
    print("  3. Valid admin token\n")
    
    print("Running this test script:")
    print("  Option 1 - Using Python test_analytics.py (requires 'requests' library):")
    print("    python3 test_analytics.py\n")
    print("  Option 2 - Using curl commands directly (see test_analytics_curl.sh):")
    print("    bash test_analytics_curl.sh\n")
    print("  Option 3 - Using this quick test script:")
    print("    python3 test_analytics_quick.py\n")
    
    print("Manual curl test example:")
    print("  curl -H 'Authorization: Bearer 29c63be0-06c1-4051-b3ef-034e46a6dfed' \\")
    print("       http://localhost:8000/metrics/health\n")
    
    print("Expected results:")
    print("  - Health check should return current metrics")
    print("  - Summary endpoints should show query statistics")
    print("  - Advanced analytics should return user/security/performance data")
    print("  - All responses should have HTTP 200 status\n")


def main():
    """Main entry point"""
    print_instructions()
    
    # Create and run test suite
    print("\n" + "="*80)
    print(f"Starting tests at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    suite = AnalyticsQuickTest(BASE_URL, ADMIN_TOKEN)
    exit_code = suite.run_tests()
    
    print(f"Tests completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
