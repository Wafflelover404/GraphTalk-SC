# GraphTalk Docker Setup

This guide explains how to run GraphTalk using Docker containers for easy deployment and development.

## Quick Start

### 1. Using Docker Compose (Recommended)

```bash
# Clone and navigate to the project
cd graphtalk

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys and configuration

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f graphtalk

# Stop services
docker-compose down
```

### 2. Using Docker Only

```bash
# Build the image
docker build -t graphtalk .

# Run the container
docker run -d \
  --name graphtalk-api \
  -p 9001:9001 \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/chroma_db:/app/chroma_db \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  graphtalk
```

## Services

The Docker Compose setup includes:

### graphtalk
- **Main application** running on port 9001
- FastAPI server with all endpoints
- Automatic database initialization
- Health checks enabled

### redis (Optional)
- **Caching service** on port 6379
- Redis 7 Alpine for performance
- Persistent data storage

### postgres (Optional)
- **Database service** on port 5432
- PostgreSQL 15 Alpine
- Environment variable: `POSTGRES_PASSWORD`
- Persistent data storage

## Environment Configuration

Create a `.env` file from `.env.example`:

```bash
# Required for LLM features (optional)
DEEPSEEK_API_KEY=your_deepseek_api_key
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key

# Database (if using PostgreSQL)
DATABASE_URL=postgresql://graphtalk:your_password@postgres:5432/graphtalk

# Security
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here

# Server
HOST=0.0.0.0
PORT=9001
DEBUG=false
```

## Volumes

The following directories are mounted as volumes:

- `./uploads` - User uploaded files
- `./chroma_db` - Vector database storage
- `./data` - Application data
- `./logs` - Application logs

## Development

### Development Mode with Hot Reload

```bash
# Mount source code for development
docker-compose up --build
```

### Running Tests

```bash
# Execute tests in the container
docker-compose exec graphtalk python -m pytest

# Run specific test file
docker-compose exec graphtalk python test_analytics.py
```

### Database Management

```bash
# Access PostgreSQL
docker-compose exec postgres psql -U graphtalk -d graphtalk

# Access Redis
docker-compose exec redis redis-cli
```

## Production Deployment

### Environment Variables for Production

```bash
# Set production environment
DEBUG=false
LOG_LEVEL=WARNING

# Use strong secrets
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

# Database configuration
DATABASE_URL=postgresql://user:password@db-host:5432/graphtalk
```

### Scaling

```bash
# Scale the application
docker-compose up -d --scale graphtalk=3

# Use a load balancer for multiple instances
```

## Monitoring

### Health Checks

The application includes health checks:

```bash
# Check container health
docker-compose ps

# Manual health check
curl http://localhost:9001/health
```

### Logs

```bash
# View all logs
docker-compose logs

# Follow specific service logs
docker-compose logs -f graphtalk

# View last 100 lines
docker-compose logs --tail=100 graphtalk
```

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 9001, 5432, and 6379 are available
2. **Permission issues**: Check volume permissions on host system
3. **Memory issues**: Increase Docker memory allocation for large models

### Reset Everything

```bash
# Stop and remove all containers
docker-compose down -v

# Remove all images
docker rmi graphtalk_graphtalk

# Rebuild from scratch
docker-compose up --build
```

### Database Issues

```bash
# Reinitialize databases
docker-compose exec graphtalk python init_all_databases.py

# Check database status
docker-compose exec graphtalk python -c "from userdb import init_db; import asyncio; asyncio.run(init_db())"
```

## Performance Optimization

### Build Optimization

```bash
# Use build cache efficiently
docker-compose build --no-cache

# Multi-stage build for smaller image
# (Already implemented in Dockerfile)
```

### Runtime Optimization

```bash
# Set resource limits
docker-compose up -d --memory=4g --cpus=2

# Use production-ready base image
docker build -f Dockerfile.prod -t graphtalk:prod .
```

## Security Considerations

1. **Never commit `.env` files** to version control
2. **Use strong secrets** in production
3. **Enable HTTPS** with reverse proxy (nginx/traefik)
4. **Regular updates**: `docker-compose pull && docker-compose up -d`
5. **Network isolation**: Use custom Docker networks

## Next Steps

1. Configure environment variables
2. Set up reverse proxy for HTTPS
3. Configure backup strategy for volumes
4. Set up monitoring and alerting
5. Consider orchestration (Kubernetes) for large scale deployments
