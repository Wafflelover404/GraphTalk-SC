from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import os
import logging
from dotenv import load_dotenv

# Import our modules
from database import init_database
from auth import create_master_token, verify_master_token
from routers import (
    blog,
    contact,
    sales,
    help_center,
    status_monitoring,
    docs,
    analytics,
    cms,
    marketing
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting WikiAI Landing Pages API...")
    await init_database()
    
    # Create master CMS token if it doesn't exist
    master_token = os.getenv("MASTER_CMS_TOKEN")
    if not master_token:
        logger.warning("MASTER_CMS_TOKEN not set in environment variables")
    else:
        logger.info("Master CMS token is configured")
    
    logger.info("API startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down WikiAI Landing Pages API...")

# Create FastAPI app
app = FastAPI(
    title="WikiAI Landing Pages API",
    description="Backend API for WikiAI landing pages including blog, contact, sales, and CMS functionality",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

async def verify_cms_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the master CMS token for admin access"""
    token = credentials.credentials
    if token != os.getenv("MASTER_CMS_TOKEN"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing CMS token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

# Public routes (no authentication required)
app.include_router(blog.router, prefix="/api/blog", tags=["Blog"])
app.include_router(contact.router, prefix="/api/contact", tags=["Contact"])
app.include_router(sales.router, prefix="/api/sales", tags=["Sales"])
app.include_router(help_center.router, prefix="/api/help", tags=["Help Center"])
app.include_router(status_monitoring.router, prefix="/api/status", tags=["Status"])
app.include_router(docs.router, prefix="/api/docs", tags=["Documentation"])
app.include_router(marketing.router, prefix="/api/marketing", tags=["Marketing"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])

# Protected CMS routes (require master token)
app.include_router(
    cms.router, 
    prefix="/api/cms", 
    tags=["CMS - Admin"],
    dependencies=[Depends(verify_cms_token)]
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "WikiAI Landing Pages API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "WikiAI Landing Pages API"}

@app.get("/api/config/site")
async def get_site_config():
    """Get public site configuration"""
    return {
        "site_name": "WikiAI",
        "description": "AI-powered knowledge management platform",
        "version": "1.0.0",
        "features": {
            "blog": True,
            "contact": True,
            "sales": True,
            "help_center": True,
            "status_monitoring": True,
            "documentation": True
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
