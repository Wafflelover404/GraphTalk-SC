#!/bin/bash
# Elasticsearch API CURL Tests
# Run this after starting Elasticsearch

BASE_URL="http://localhost:9001"

echo "=============================================="
echo "Elasticsearch API CURL Tests"
echo "=============================================="
echo ""

# 1. Health Check
echo "1. Health Check"
echo "----------------"
curl -s "$BASE_URL/es/health" | python3 -m json.tool
echo ""

# 2. Config
echo "2. Get Config"
echo "-------------"
curl -s "$BASE_URL/es/config" | python3 -m json.tool
echo ""

# Note: For subsequent tests, you need to be logged in and have a session token
# First, login to get a token:
echo "To test authenticated endpoints, first login:"
echo "  curl -X POST '$BASE_URL/login' -H 'Content-Type: application/json' -d '{\"username\": \"admin\", \"password\": \"password\"}'"
echo ""
echo "Then use the token in subsequent requests:"
echo "  TOKEN=\$(echo \$response | python3 -c \"import sys, json; print(json.load(sys.stdin)['token'])\")"
echo "  curl -s '$BASE_URL/es/search?query=test&credentials=\$TOKEN' | python3 -m json.tool"
echo ""

# 3. Search (requires auth)
echo "3. Search Endpoint (requires auth)"
echo "-----------------------------------"
echo "  POST /es/search"
echo "  Body: {\"query\": \"test query\", \"size\": 10}"
echo ""

# 4. Hybrid Search (requires auth)
echo "4. Hybrid Search Endpoint (requires auth)"
echo "----------------------------------------"
echo "  POST /es/hybrid/search"
echo "  Body: {\"query\": \"test\", \"fusion_method\": \"rrf\"}"
echo ""

# 5. Reindex (admin only)
echo "5. Reindex Endpoints (admin only)"
echo "----------------------------------"
echo "  POST /es/reindex/full"
echo "  POST /es/reindex/sync?batch_size=100"
echo ""

# 6. Index Management (admin only)
echo "6. Index Management (admin only)"
echo "--------------------------------"
echo "  POST /es/index/documents"
echo "  GET /es/index/documents/stats"
echo "  DELETE /es/index/documents"
echo ""

echo "=============================================="
echo "Integration Tests"
echo "=============================================="
echo ""

echo "1. Start Elasticsearch with Docker:"
echo "   docker run -d --name elasticsearch -p 9200:9200 -e 'discovery.type=single-node' elasticsearch:8.10.0"
echo ""

echo "2. Verify ES is running:"
echo "   curl http://localhost:9200"
echo ""

echo "3. Run Python integration tests:"
echo "   python rag_api/tests/integration_test.py"
echo ""

echo "4. Run unit tests:"
echo "   /Users/wafflelover404/Library/Python/3.9/bin/pytest rag_api/tests/test_elasticsearch.py -v"
echo ""

echo "5. Reindex all documents:"
echo "   python rag_api/reindex_to_es.py --full"
echo ""
