"""
Test API for the enhanced RAG system.
"""
import os
import shutil
import uvicorn
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our enhanced RAG components
from rag_enhanced import DocumentIndexer, EnhancedSearcher
from rag_enhanced.embeddings import get_vector_store

# Initialize FastAPI app
app = FastAPI(
    title="Enhanced RAG API",
    description="Test API for the enhanced RAG system",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components with error handling
try:
    logger.info("Initializing RAG components...")
    
    # First, create the vector store
    vector_store = get_vector_store()
    
    # Then initialize the indexer and searcher with the same vector store
    indexer = DocumentIndexer(vector_store=vector_store)
    searcher = EnhancedSearcher(vector_store=vector_store)
    
    logger.info("RAG components initialized successfully")
    
except Exception as e:
    logger.error(f"Failed to initialize RAG components: {str(e)}")
    # Re-raise to fail fast if initialization fails
    raise

# Create uploads directory with absolute path
UPLOAD_DIR = Path(__file__).parent / "test_uploads"
try:
    UPLOAD_DIR.mkdir(exist_ok=True, parents=True, mode=0o755)
    logger.info(f"Upload directory: {UPLOAD_DIR.absolute()}")
except Exception as e:
    logger.error(f"Failed to create upload directory {UPLOAD_DIR}: {e}")
    raise

# Add a status endpoint
@app.get("/status")
async def get_status():
    """Get the status of the RAG system."""
    try:
        return {
            "status": "ready",
            "collection": indexer.vector_store.name,
            "num_documents": indexer.vector_store.count()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

# Mount static files for serving uploaded files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Helper function to clean up old files
def cleanup_old_files(max_files: int = 100):
    """Clean up old files if there are too many."""
    files = list(UPLOAD_DIR.glob("*"))
    if len(files) > max_files:
        # Sort by modification time (oldest first)
        files.sort(key=lambda x: x.stat().st_mtime)
        # Delete oldest files
        for file in files[:-max_files]:
            try:
                file.unlink()
                print(f"Cleaned up old file: {file}")
            except Exception as e:
                print(f"Error cleaning up {file}: {e}")

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    print("Starting Enhanced RAG API...")
    # Clean up old files on startup
    cleanup_old_files()

@app.post("/upload", response_model=dict)
async def upload_document(file: UploadFile = File(...)):
    """Upload and index a document."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    logger.info(f"Processing file upload: {file.filename}")
    
    # Create a unique filename
    try:
        file_ext = Path(file.filename).suffix
        file_id = str(uuid.uuid4())
        filename = f"{file_id}{file_ext}"
        file_path = UPLOAD_DIR / filename
        
        logger.info(f"Saving file to: {file_path}")
        
        # Save the file
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            logger.info(f"File saved successfully: {file_path}")
        except Exception as save_error:
            logger.error(f"Error saving file {file.filename}: {str(save_error)}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save file: {str(save_error)}"
            )
        
        # Verify file was saved and has content
        if not file_path.exists():
            error_msg = f"File {file_path} was not saved correctly"
            logger.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
            
        if file_path.stat().st_size == 0:
            error_msg = f"Uploaded file is empty: {file.filename}"
            logger.error(error_msg)
            file_path.unlink()  # Clean up empty file
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Index the document
        logger.info(f"Indexing document: {file_path}")
        try:
            success = indexer.index_document(str(file_path), file_id)
            if not success:
                error_msg = f"Failed to index document: {file_path}"
                logger.error(error_msg)
                if file_path.exists():
                    file_path.unlink()
                raise HTTPException(status_code=500, detail=error_msg)
            
            logger.info(f"Successfully indexed document: {file_path}")
            
            return {
                "status": "success",
                "file_id": file_id,
                "filename": filename,
                "download_url": f"/uploads/{filename}",
                "message": f"Successfully processed and indexed {file.filename}"
            }
            
        except HTTPException:
            raise
        except Exception as index_error:
            error_msg = f"Error indexing document: {str(index_error)}"
            logger.error(error_msg, exc_info=True)
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(status_code=500, detail=error_msg)
            
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Unexpected error processing file: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/search", response_model=dict)
async def search(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.3,
    use_reranking: bool = True
):
    """Search the document collection."""
    try:
        results = searcher.semantic_search(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            use_reranking=use_reranking
        )
        
        # Convert any numpy arrays to lists for JSON serialization
        def convert_numpy(obj):
            import numpy as np
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(item) for item in obj]
            return obj
            
        return convert_numpy(results)
        
    except Exception as e:
        logger.error(f"Error in search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/hybrid-search", response_model=dict)
async def hybrid_search(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.3,
    use_reranking: bool = True,
    keyword_weight: float = 0.3,
    semantic_weight: float = 0.7
):
    """Perform a hybrid search combining semantic and keyword search."""
    try:
        results = searcher.hybrid_search(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            use_reranking=use_reranking,
            keyword_weight=keyword_weight,
            semantic_weight=semantic_weight
        )
        
        # Convert any numpy arrays to lists for JSON serialization
        def convert_numpy(obj):
            import numpy as np
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(item) for item in obj]
            return obj
            
        return convert_numpy(results)
        
    except Exception as e:
        logger.error(f"Error in hybrid search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{file_id}/chunks", response_model=dict)
async def get_document_chunks(file_id: str):
    """Get all chunks for a specific document.
    
    Args:
        file_id: The ID of the file to retrieve chunks for
        
    Returns:
        A dictionary containing the list of document chunks (without embeddings)
    """
    try:
        # Explicitly set include_embeddings=False to reduce response size
        chunks = indexer.get_document_chunks(file_id, include_embeddings=False)
        if not chunks:
            raise HTTPException(status_code=404, detail="Document not found or has no chunks")
        return {"chunks": chunks}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving chunks for {file_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving document chunks: {str(e)}")

@app.delete("/documents/{file_id}", response_model=dict)
async def delete_document(file_id: str):
    """Delete a document and all its chunks."""
    try:
        success = indexer.delete_document(file_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "success", "message": f"Deleted document {file_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize", response_model=dict)
async def optimize_index():
    """Optimize the vector index for better search performance."""
    try:
        success = indexer.optimize_index()
        if success:
            return {
                "status": "success", 
                "message": "Index optimization completed successfully"
            }
        else:
            return {
                "status": "error", 
                "message": "Failed to optimize index. Check server logs for details."
            }
    except Exception as e:
        logger.error(f"Error in optimize_index: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error optimizing index: {str(e)}"
        )

@app.get("/health", response_model=dict)
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "test_rag_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )
