"""
FastAPI backend for OpenCart RAG product synchronization
Receives product data from OpenCart module and stores it in the database
"""

from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import local modules
from database import get_db, init_db, engine
import models
import schemas
import crud

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API version
API_VERSION = "1.0.0"

# Create FastAPI app
app = FastAPI(
    title="OpenCart RAG Product Sync API",
    description="Backend API for receiving and storing OpenCart product data",
    version=API_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Add CORS middleware - MUST be added before routes for preflight to work
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],  # Explicit methods
    allow_headers=["*"],  # Allow all headers
    max_age=600,  # Cache preflight for 10 minutes
)


# Event handlers
@app.on_event("startup")
async def startup():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")


# Health check
@app.get("/", response_model=schemas.HealthCheckResponse, tags=["Health"])
@app.get("/health", response_model=schemas.HealthCheckResponse, tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection (use text() for SQLAlchemy 2.x)
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
        raise HTTPException(status_code=503, detail="Database connection failed")
    
    return schemas.HealthCheckResponse(
        status="healthy",
        version=API_VERSION,
        database=db_status,
        message="OpenCart RAG Sync API is running"
    )


# Store endpoints
@app.post("/api/stores", response_model=schemas.StoreResponse, tags=["Stores"])
async def create_store(store: schemas.StoreCreate, db: Session = Depends(get_db)):
    """Create or get a store"""
    try:
        db_store = crud.StoreCRUD.get_or_create(db, store.store_url, store.store_name)
        return db_store
    except Exception as e:
        logger.error(f"Error creating store: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/stores", response_model=List[schemas.StoreResponse], tags=["Stores"])
async def get_stores(skip: int = Query(0, ge=0), limit: int = Query(100, le=1000), db: Session = Depends(get_db)):
    """Get all stores"""
    try:
        stores = crud.StoreCRUD.get_all(db, skip=skip, limit=limit)
        return stores
    except Exception as e:
        logger.error(f"Error fetching stores: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/stores/{store_id}", response_model=schemas.StoreResponse, tags=["Stores"])
async def get_store(store_id: int, db: Session = Depends(get_db)):
    """Get a specific store"""
    store = crud.StoreCRUD.get_by_id(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@app.get("/api/stores/{store_id}/statistics", response_model=schemas.StoreStatisticsResponse, tags=["Stores"])
async def get_store_statistics(store_id: int, db: Session = Depends(get_db)):
    """Get statistics for a store"""
    store = crud.StoreCRUD.get_by_id(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    
    try:
        stats = crud.ProductCRUD.get_statistics(db, store_id)
        latest_sync = crud.SyncLogCRUD.get_latest_by_store(db, store_id)
        
        return schemas.StoreStatisticsResponse(
            store_id=store_id,
            store_name=store.store_name,
            total_products=stats['total_products'],
            products_with_images=stats['products_with_images'],
            products_with_reviews=stats['products_with_reviews'],
            average_rating=stats['average_rating'],
            total_categories=stats['total_categories'],
            last_sync=latest_sync.created_at if latest_sync else None
        )
    except Exception as e:
        logger.error(f"Error getting store statistics: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Product sync endpoints
@app.post("/api/products/sync", response_model=schemas.SyncBatchResponse, tags=["Products"])
async def sync_products(
    batch: schemas.SyncBatchRequest,
    api_key: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db)
):
    """
    Receive and store a batch of products from OpenCart
    
    Expected Authorization header format: Bearer <api_key>
    """
    try:
        # Validate API key if configured
        required_api_key = os.getenv("API_KEY")
        if required_api_key and api_key:
            # Remove 'Bearer ' prefix if present
            api_key = api_key.replace("Bearer ", "")
            if api_key != required_api_key:
                raise HTTPException(status_code=401, detail="Invalid API key")
        elif required_api_key and not api_key:
            raise HTTPException(status_code=401, detail="API key required")
        
        logger.info(f"Processing sync batch {batch.batch_number}/{batch.total_batches} from {batch.store_url}")
        
        # Get or create store
        store = crud.StoreCRUD.get_or_create(db, batch.store_url)
        
        # Create sync log entry
        sync_log = crud.SyncLogCRUD.create(db, store.id, batch)
        
        # Save products
        try:
            saved_products = crud.ProductCRUD.create_bulk(db, store.id, batch.products)
            
            # Update statistics
            stats = crud.ProductCRUD.get_statistics(db, store.id)
            crud.ProductStatisticsCRUD.create_or_update(db, store.id, stats)
            
            # Update sync log status
            crud.SyncLogCRUD.update_status(db, sync_log.id, "completed", total_products=len(saved_products))
            
            logger.info(f"Successfully saved {len(saved_products)} products")
            
            return schemas.SyncBatchResponse(
                success=True,
                batch_number=batch.batch_number,
                total_batches=batch.total_batches,
                products_saved=len(saved_products),
                message=f"Batch {batch.batch_number}/{batch.total_batches} processed successfully"
            )
        except Exception as e:
            error_msg = f"Error saving products: {str(e)}"
            logger.error(error_msg)
            crud.SyncLogCRUD.update_status(db, sync_log.id, "failed", error_message=error_msg)
            raise HTTPException(status_code=400, detail=error_msg)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing sync batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Product endpoints
@app.get("/api/products", response_model=List[schemas.ProductResponse], tags=["Products"])
async def get_products(
    store_id: int = Query(..., description="Store ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    """Get products for a store"""
    try:
        products = crud.ProductCRUD.get_by_store(db, store_id, skip=skip, limit=limit)
        return products
    except Exception as e:
        logger.error(f"Error fetching products: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/products/{product_id}", response_model=schemas.ProductResponse, tags=["Products"])
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Get a specific product by database ID"""
    try:
        product = crud.ProductCRUD.get_by_id(db, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching product: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/products/search", response_model=List[schemas.ProductResponse], tags=["Products"])
async def search_products(
    store_id: int = Query(..., description="Store ID"),
    q: str = Query(..., description="Search query"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db)
):
    """Search products by name or SKU"""
    try:
        products = crud.ProductCRUD.search(db, store_id, q, skip=skip, limit=limit)
        return products
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/stores/{store_id}/products", tags=["Products"])
async def delete_store_products(store_id: int, db: Session = Depends(get_db)):
    """Delete all products for a store"""
    try:
        store = crud.StoreCRUD.get_by_id(db, store_id)
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        
        count = crud.ProductCRUD.delete_by_store(db, store_id)
        logger.info(f"Deleted {count} products for store {store_id}")
        
        return {
            "success": True,
            "message": f"Deleted {count} products",
            "deleted_count": count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting products: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Sync log endpoints
@app.get("/api/stores/{store_id}/sync-logs", tags=["Sync Logs"])
async def get_sync_logs(
    store_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db)
):
    """Get sync logs for a store"""
    try:
        store = crud.StoreCRUD.get_by_id(db, store_id)
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        
        logs = crud.SyncLogCRUD.get_by_store(db, store_id, skip=skip, limit=limit)
        return logs
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching sync logs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Test endpoint - accepts both GET and POST
@app.get("/api/test", tags=["Testing"])
@app.post("/api/test", tags=["Testing"])
async def test_connection(test_payload: Optional[dict] = None, db: Session = Depends(get_db)):
    """Test endpoint for verifying backend connectivity"""
    try:
        return {
            "success": True,
            "message": "Backend is reachable and accepting requests",
            "timestamp": datetime.utcnow().isoformat(),
            "version": API_VERSION,
            "received_payload": test_payload or {}
        }
    except Exception as e:
        logger.error(f"Error in test endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Preview endpoint - shows sample products from database (GET only)
@app.get("/api/preview", response_model=dict, tags=["Products"])
async def preview_products(
    store_id: Optional[int] = Query(None, description="Store ID (optional)"),
    limit: int = Query(5, ge=1, le=50, description="Number of products to preview"),
    db: Session = Depends(get_db)
):
    """
    Get a preview of products stored in the database
    If store_id is not provided, shows first available store's products
    """
    try:
        # Get store_id if not provided
        if store_id is None:
            store = db.query(models.Store).first()
            if not store:
                return {
                    "success": False,
                    "message": "No stores found in database",
                    "total_products": 0,
                    "preview_count": 0,
                    "preview_samples": [],
                    "data_fields": []
                }
            store_id = store.id
        
        # Get products
        products = crud.ProductCRUD.get_by_store(db, store_id, skip=0, limit=limit)
        
        # Get statistics
        stats = crud.ProductCRUD.get_statistics(db, store_id)
        
        # Convert to response format
        product_list = [schemas.ProductResponse.from_orm(p).dict() for p in products]
        
        return {
            "success": True,
            "total_products": stats['total_products'],
            "preview_count": len(product_list),
            "preview_samples": product_list,
            "data_fields": list(product_list[0].keys()) if product_list else [],
            "statistics": stats
        }
    except Exception as e:
        logger.error(f"Error in preview endpoint: {e}")
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
