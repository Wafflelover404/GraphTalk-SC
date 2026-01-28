# GraphTalk Docker Commands

.PHONY: help build up down logs clean test health prod-build prod-up

# Default target
help:
	@echo "GraphTalk Docker Commands:"
	@echo ""
	@echo "  build        - Build development Docker image"
	@echo "  up           - Start development environment"
	@echo "  down         - Stop development environment"
	@echo "  logs         - Show application logs"
	@echo "  clean        - Clean up containers and images"
	@echo "  test         - Run tests in container"
	@echo "  health       - Check application health"
	@echo "  prod-build   - Build production Docker image"
	@echo "  prod-up      - Start production environment"
	@echo ""
	@echo "Example usage:"
	@echo "  make build && make up"

# Development commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f graphtalk

clean:
	docker-compose down -v
	docker system prune -f
	docker volume prune -f

test:
	docker-compose exec graphtalk python -m pytest

health:
	curl -f http://localhost:9001/health || echo "Health check failed"

# Production commands
prod-build:
	docker build -f Dockerfile.prod -t graphtalk:prod .

prod-up:
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Development utilities
dev-shell:
	docker-compose exec graphtalk /bin/bash

db-shell:
	docker-compose exec postgres psql -U graphtalk -d graphtalk

redis-shell:
	docker-compose exec redis redis-cli

# Full development cycle
dev: build up
	@echo "Development environment started. Use 'make logs' to follow logs."

reset: clean build up
	@echo "Environment reset complete."

# Production deployment
deploy: prod-build prod-up
	@echo "Production deployment complete."
