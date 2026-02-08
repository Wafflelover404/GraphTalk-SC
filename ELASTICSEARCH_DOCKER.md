# Elasticsearch Docker Commands for GraphTalk

# 1. Basic Single Node (no security) - Quick Start
docker run -d --name elasticsearch \
  -p 9200:9200 -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  elasticsearch:8.10.0

# 2. Single Node with Security (recommended for production)
docker run -d --name elasticsearch \
  -p 9200:9200 -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "ELASTIC_PASSWORD=your_secure_password" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  -v elasticsearch_data:/usr/share/elasticsearch/data \
  elasticsearch:8.10.0

# 3. Cluster Mode (3 nodes)
docker run -d --name es-node-1 \
  -e "cluster.name=graphtalk-cluster" \
  -e "node.name=es-node-1" \
  -e "discovery.seed_hosts=es-node-2,es-node-3" \
  -e "cluster.initial_master_nodes=es-node-1,es-node-2,es-node-3" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  -p 9200:9200 \
  --net es-network \
  elasticsearch:8.10.0

# 4. With Kibana for Visualization
docker run -d --name kibana \
  -p 5601:5601 \
  -e "ELASTICSEARCH_HOSTS=http://elasticsearch:9200" \
  --net es-network \
  kibana:8.10.0

# 5. Docker Compose (Recommended)
cat > docker-compose.elasticsearch.yml << 'EOF'
version: '3.8'
services:
  elasticsearch:
    image: elasticsearch:8.10.0
    container_name: elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - ES_JAVA_OPTS=-Xms1g -Xmx1g
    ports:
      - "9200:9200"
      - "9300:9300"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    networks:
      - es-network
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -vq '\"status\":\"red\"'"]
      interval: 30s
      timeout: 10s
      retries: 5

  kibana:
    image: kibana:8.10.0
    container_name: kibana
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch
    networks:
      - es-network

networks:
  es-network:
    driver: bridge

volumes:
  elasticsearch_data:
EOF

# 6. ARM/Apple Silicon (M1/M2/M3)
docker run -d --name elasticsearch \
  -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  --platform linux/amd64 \
  elasticsearch:8.10.0

# Useful Commands

# Check if ES is running
curl -s http://localhost:9200

# Check cluster health
curl -s http://localhost:9200/_cluster/health

# List indexes
curl -s http://localhost:9200/_cat/indices

# Stop and remove
docker stop elasticsearch && docker rm elasticsearch

# View logs
docker logs -f elasticsearch

# Execute shell in container
docker exec -it elasticsearch /bin/bash

# Inside container: check plugins
elasticsearch-plugin list

# Health check script
cat > check_es.sh << 'EOF'
#!/bin/bash
ES_HOST=${ES_HOST:-localhost}
ES_PORT=${ES_PORT:-9200}

if curl -s "http://$ES_HOST:$ES_PORT" > /dev/null; then
    echo "✅ Elasticsearch is running"
    curl -s "http://$ES_HOST:$ES_PORT/_cluster/health" | jq '.'
else
    echo "❌ Elasticsearch is not responding"
    exit 1
fi
EOF
chmod +x check_es.sh
