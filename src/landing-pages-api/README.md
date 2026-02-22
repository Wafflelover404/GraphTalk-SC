# WikiAI Landing Pages API

Backend API for WikiAI landing pages including blog, contact, sales, help center, status monitoring, documentation, analytics, marketing, and CMS functionality.

## Features

- **Blog Management**: Create, read, update, delete blog posts with categories and tags
- **Contact Forms**: Handle contact submissions with inquiry types and status tracking
- **Sales System**: Demo requests, lead management, quote requests, enterprise inquiries
- **Help Center**: Help articles, video tutorials, categories, search functionality
- **Status Monitoring**: Service status, incident management, uptime metrics
- **Documentation**: API docs, guides, version control, search
- **Analytics**: Page views, conversions, user engagement, marketing metrics
- **Marketing**: Lead magnets, webinar registration, email campaigns, A/B testing
- **CMS**: Content management with master token authentication
- **Media Management**: File upload and management

## Quick Start

### Prerequisites

- Python 3.8+
- pip or poetry

### Installation

1. Clone the repository:
```bash
cd /Users/wafflelover404/Documents/wikiai/landing-pages-api
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the API:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### API Documentation

Visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI).

## Authentication

The API uses a master CMS token for admin operations. Set the `MASTER_CMS_TOKEN` in your `.env` file.

### Using the Master Token

Include the token in the Authorization header:
```
Authorization: Bearer your-master-cms-token
```

Protected endpoints (CMS operations) require this token.

## API Endpoints

### Blog (`/api/blog`)
- `GET /posts` - Get blog posts
- `GET /posts/{id}` - Get single post
- `GET /posts/slug/{slug}` - Get post by slug
- `GET /posts/featured` - Get featured posts
- `GET /categories` - Get categories
- `POST /subscribe` - Subscribe to newsletter
- `GET /search` - Search posts

### Contact (`/api/contact`)
- `POST /submit` - Submit contact form
- `GET /submissions` - Get submissions (admin)
- `GET /options` - Get contact options
- `GET /inquiry-types` - Get inquiry types

### Sales (`/api/sales`)
- `POST /demo-request` - Create demo request
- `POST /leads` - Create sales lead
- `POST /quote-request` - Create quote request
- `POST /enterprise-inquiry` - Create enterprise inquiry
- `GET /analytics/leads` - Get sales analytics

### Help Center (`/api/help`)
- `GET /articles` - Get help articles
- `GET /articles/{id}` - Get single article
- `POST /articles/{id}/helpful` - Mark article helpful
- `GET /categories` - Get categories
- `GET /videos` - Get video tutorials
- `GET /search` - Search articles

### Status (`/api/status`)
- `GET /services` - Get service status
- `GET /overview` - Get system overview
- `GET /incidents` - Get incidents
- `GET /uptime` - Get uptime metrics

### Documentation (`/api/docs`)
- `GET /` - Get documentation
- `GET /categories` - Get categories
- `GET /search` - Search docs
- `GET /quick-links` - Get quick links

### Analytics (`/api/analytics`)
- `POST /track-visit` - Track page visit
- `POST /track-event` - Track event
- `GET /landing-page-conversions` - Get conversion data
- `GET /page-views` - Get page view stats
- `GET /dashboard` - Get dashboard analytics

### Marketing (`/api/marketing`)
- `POST /download-request` - Request download
- `GET /resources` - Get resources
- `POST /webinar-registration` - Register for webinar
- `POST /email-opened` - Track email open
- `GET /campaign-performance` - Get campaign stats

### CMS (`/api/cms`) - Protected
- `POST /blog/posts` - Create blog post
- `PUT /blog/posts/{id}` - Update blog post
- `DELETE /blog/posts/{id}` - Delete blog post
- `POST /media/upload` - Upload media file
- `GET /content/stats` - Get content stats

## Database Schema

The API uses SQLite with the following main tables:

- `blog_posts` - Blog articles
- `contact_submissions` - Contact form submissions
- `demo_requests` - Demo requests
- `sales_leads` - Sales leads
- `quote_requests` - Quote requests
- `help_articles` - Help center articles
- `video_tutorials` - Video tutorials
- `status_incidents` - Status incidents
- `service_status` - Service status
- `documentation` - Documentation pages
- `analytics_events` - Analytics events
- `landing_page_visits` - Page visits

## Configuration

### Environment Variables

- `DATABASE_URL` - Database connection string
- `SECRET_KEY` - JWT secret key
- `MASTER_CMS_TOKEN` - Master token for CMS access
- `ALLOWED_ORIGINS` - CORS allowed origins
- `MAX_FILE_SIZE` - Maximum file upload size
- `UPLOAD_DIR` - Upload directory

### Security

- Use HTTPS in production
- Change default tokens and secrets
- Implement rate limiting
- Validate all inputs
- Use secure file uploads

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

### Database Migrations

The database is automatically initialized on startup. For production, consider using proper migration tools.

## Deployment

### Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Setup

1. Set production environment variables
2. Use PostgreSQL or MySQL for production
3. Configure proper CORS origins
4. Set up SSL certificates
5. Configure reverse proxy (nginx)

## Monitoring

- Health check: `GET /health`
- System health: `GET /api/cms/system/health` (requires auth)
- API docs: `GET /docs`

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For support and questions:
- Email: info.wikiai@gmail.com
- Phone: +375 297 345 682
- Telegram: https://t.me/vikigolubeva
