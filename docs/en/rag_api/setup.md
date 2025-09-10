# RAG API Setup Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git
- Google Cloud account (for Google API access)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/graphtalk-sc.git
   cd graphtalk-sc
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the project root:
   ```bash
   cp .env.example .env
   ```
   Edit the `.env` file with your configuration:
   ```
   # Required
   GOOGLE_API_KEY=your_google_api_key
   DATABASE_URL=sqlite:///rag_app.db
   
   # Optional
   EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
   CHUNK_SIZE=1500
   CHUNK_OVERLAP=300
   DEBUG=True
   ```

## Running the API

### Development Mode
```bash
uvicorn rag_api.main:app --reload
```

### Production Mode
For production, use a production ASGI server like `uvicorn` with multiple workers:
```bash
uvicorn rag_api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker
1. Build the Docker image:
   ```bash
   docker build -t rag-api .
   ```

2. Run the container:
   ```bash
   docker run -p 8000:8000 --env-file .env rag-api
   ```

## Initial Setup

1. **Initialize the database**
   ```bash
   python -m rag_api.db.init_db
   ```

2. **Create a superuser** (for admin access)
   ```bash
   python -m rag_api.scripts.create_superuser
   ```

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Google Cloud API key | - |
| `DATABASE_URL` | Database connection URL | `sqlite:///rag_app.db` |
| `EMBEDDING_MODEL` | Model for text embeddings | `sentence-transformers/all-mpnet-base-v2` |
| `CHUNK_SIZE` | Size of text chunks for processing | `1500` |
| `CHUNK_OVERLAP` | Overlap between chunks | `300` |
| `DEBUG` | Enable debug mode | `False` |
| `SECRET_KEY` | Secret key for JWT tokens | Randomly generated |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token expiration time | `30` |

### API Documentation
Once the API is running, you can access:
- Interactive API docs: http://localhost:8000/docs
- Alternative API docs: http://localhost:8000/redoc

## Updating the API

1. Pull the latest changes:
   ```bash
   git pull origin main
   ```

2. Update dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run database migrations (if any):
   ```bash
   alembic upgrade head
   ```

4. Restart the API server.
