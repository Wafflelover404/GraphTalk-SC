#!/bin/bash

# Advanced Analytics System - Curl Test Script
# Usage: bash test_analytics_curl.sh

BASE_URL="http://localhost:9001"
ADMIN_TOKEN="29c63be0-06c1-4051-b3ef-034e46a6dfed"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

# Helper functions
print_header() {
    echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"
}

test_endpoint() {
    local name=$1
    local endpoint=$2
    local response=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
                          -H "Content-Type: application/json" \
                          "$BASE_URL$endpoint")
    
    # Check if response contains error
    if echo "$response" | grep -q '"status":"error"' || [ -z "$response" ]; then
        echo -e "${RED}❌ $name${NC}"
        FAILED=$((FAILED + 1))
    else
        echo -e "${GREEN}✅ $name${NC}"
        PASSED=$((PASSED + 1))
        
        # Extract and display key data
        if echo "$response" | grep -q '"data"'; then
            echo "$response" | python3 -m json.tool 2>/dev/null | head -15 | sed 's/^/   /'
        fi
    fi
}

print_summary() {
    local total=$((PASSED + FAILED))
    local pass_rate=0
    
    if [ $total -gt 0 ]; then
        pass_rate=$((PASSED * 100 / total))
    fi
    
    echo -e "\n${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  📊 Test Results Summary${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}\n"
    
    echo "Total Tests: $total"
    echo -e "${GREEN}✅ Passed: $PASSED${NC}"
    echo -e "${RED}❌ Failed: $FAILED${NC}"
    echo "Pass Rate: $pass_rate%"
    
    if [ $FAILED -eq 0 ]; then
        echo -e "\n${GREEN}🎉 ALL TESTS PASSED!${NC}"
        echo -e "${GREEN}✨ Advanced Analytics System is working correctly.${NC}\n"
        return 0
    else
        echo -e "\n${RED}⚠️  $FAILED test(s) failed.${NC}"
        echo -e "${YELLOW}Please verify:${NC}"
        echo "  1. API server is running: python3 api.py"
        echo "  2. Admin token is valid"
        echo "  3. Analytics modules are loaded\n"
        return 1
    fi
}

# Main execution
echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  ADVANCED ANALYTICS SYSTEM - CURL TEST SUITE${NC}"
echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
echo -e "\nBase URL: $BASE_URL"
echo "Admin Token: ${ADMIN_TOKEN:0:16}...\n"

# Test 1: Health Check
print_header "1️⃣  Health Check Endpoint"
test_endpoint "GET /metrics/health" "/metrics/health"

# Test 2: Metrics Summary
print_header "2️⃣  Metrics Summary Endpoints"
test_endpoint "GET /metrics/summary (24h)" "/metrics/summary?since=24h"
test_endpoint "GET /metrics/summary (7d)" "/metrics/summary?since=7d"

# Test 3: Metrics Queries
print_header "3️⃣  Metrics Queries Endpoints"
test_endpoint "GET /metrics/queries" "/metrics/queries?since=24h&limit=10"

# Test 4: Metrics Performance
print_header "4️⃣  Metrics Performance Endpoints"
test_endpoint "GET /metrics/performance" "/metrics/performance?since=24h&limit=20"

# Test 5: Metrics Errors
print_header "5️⃣  Metrics Errors Endpoints"
test_endpoint "GET /metrics/errors" "/metrics/errors?since=24h&limit=50"

# Test 6: Metrics Documents
print_header "6️⃣  Metrics Documents Endpoints"
test_endpoint "GET /metrics/documents" "/metrics/documents?limit=20"

# Test 7: Advanced Analytics - Performance
print_header "7️⃣  Advanced Analytics - Performance"
test_endpoint "GET /analytics/performance/latency-distribution" \
    "/analytics/performance/latency-distribution?since_hours=24"
test_endpoint "GET /analytics/performance/endpoint-performance" \
    "/analytics/performance/endpoint-performance?since_hours=24"

# Test 8: Advanced Analytics - Users
print_header "8️⃣  Advanced Analytics - Users"
test_endpoint "GET /analytics/users/engagement" "/analytics/users/engagement"
test_endpoint "GET /analytics/users/segments" "/analytics/users/segments"
test_endpoint "GET /analytics/users/retention" "/analytics/users/retention"

# Test 9: Advanced Analytics - Security
print_header "9️⃣  Advanced Analytics - Security"
test_endpoint "GET /analytics/security/events" \
    "/analytics/security/events?since_hours=24&limit=100"
test_endpoint "GET /analytics/security/threat-summary" \
    "/analytics/security/threat-summary"
test_endpoint "GET /analytics/security/suspicious-ips" \
    "/analytics/security/suspicious-ips?limit=20"

# Test 10: Advanced Analytics - Compliance
print_header "🔟 Advanced Analytics - Compliance"
test_endpoint "GET /analytics/compliance/audit-log" \
    "/analytics/compliance/audit-log?since_hours=24"
test_endpoint "GET /analytics/compliance/data-retention-status" \
    "/analytics/compliance/data-retention-status"

# Test 11: Advanced Analytics - Conversion
print_header "1️⃣1️⃣  Advanced Analytics - Conversion"
test_endpoint "GET /analytics/conversion/funnel" "/analytics/conversion/funnel"

# Print Summary and Exit
print_summary
exit $?
