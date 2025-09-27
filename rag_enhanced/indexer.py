"""
Document indexing with enhanced processing and batching.
"""
import logging
import time
import uuid
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm

from .processor import DocumentProcessor
from .embeddings import get_vector_store

logger = logging.getLogger(__name__)

class DocumentIndexer:
    """
    Enhanced document indexing with versioning, metadata support, and optimization.
    
    Features:
    - Document versioning
    - Metadata extraction and storage
    - Chunk-level deduplication
    - Batch processing
    - Error recovery and retry logic
    """
    
    def __init__(
        self, 
        vector_store=None, 
        collection_name: str = "documents_enhanced",
        chunk_size: int = 1500,
        chunk_overlap: int = 300
    ):
        """
        Initialize the document indexer.
        
        Args:
            vector_store: Vector store to use for indexing
            collection_name: Name of the collection in the vector store
            chunk_size: Size of text chunks in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.vector_store = vector_store or get_vector_store(collection_name=collection_name)
        self.processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        self.collection_name = collection_name
        
    def index_document(
        self, 
        file_path: str, 
        document_id: str = None,
        metadata: Optional[Dict[str, Any]] = None,
        version: str = "1.0",
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Index a single document with enhanced processing and metadata support.
        
        Args:
            file_path: Path to the document file
            document_id: Unique ID for the document (auto-generated if None)
            metadata: Additional metadata to store with the document
            version: Document version string
            overwrite: Whether to overwrite existing document with same ID
            
        Returns:
            Dictionary with indexing results including document_id, status, chunks_processed, etc.
        """
        start_time = time.time()
        document_id = document_id or str(uuid.uuid4())
        
        # Initialize result dictionary
        result = {
            'document_id': document_id,
            'file_path': str(file_path),
            'version': version,
            'status': 'failed',
            'chunks_processed': 0,
            'error': None,
            'processing_time_seconds': 0,
            'metadata': metadata or {}
        }
        
        try:
            # Check if document exists and handle versioning
            existing_docs = self.vector_store.get(
                where={"document_id": document_id},
                limit=1
            )
            
            if existing_docs and not overwrite:
                result['status'] = 'skipped'
                result['message'] = f'Document {document_id} already exists and overwrite=False'
                return result
                
            # Process document with metadata
            file_metadata = {
                'document_id': document_id,
                'version': version,
                'indexed_at': datetime.datetime.utcnow().isoformat(),
                **(metadata or {})
            }
            
            docs = self.processor.process_document(file_path, file_metadata)
            if not docs:
                error_msg = f"No content extracted from {file_path}"
                logger.warning(error_msg)
                result['error'] = error_msg
                return result
                
            # Add document metadata to each chunk
            for doc in docs:
                doc.metadata.update(file_metadata)
                
            # Index the document chunks
            chunk_ids = [f"{document_id}_chunk_{i}" for i in range(len(docs))]
            texts = [doc.page_content for doc in docs]
            metadatas = [doc.metadata for doc in docs]
            
            # Add chunk-specific metadata
            for i, meta in enumerate(metadatas):
                meta.update({
                    'chunk_id': chunk_ids[i],
                    'chunk_index': i,
                    'total_chunks': len(docs)
                })
            
            # Add to vector store
            self.vector_store.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=chunk_ids
            )
            
            # Update result
            processing_time = time.time() - start_time
            result.update({
                'status': 'success',
                'chunks_processed': len(docs),
                'processing_time_seconds': round(processing_time, 2),
                'chunk_size_chars': len(texts[0]) if texts else 0
            })
            
            logger.info(
                f"Successfully indexed {len(docs)} chunks from {file_path} "
                f"(document_id: {document_id}, version: {version}, "
                f"took: {processing_time:.2f}s)"
            )
            
        except Exception as e:
            error_msg = f"Error indexing document {file_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.update({
                'status': 'error',
                'error': error_msg,
                'processing_time_seconds': round(time.time() - start_time, 2)
            })
            
        return result
    
    def batch_index_documents(self, file_paths: List[str], file_ids: List[str], max_workers: int = 4) -> Dict[str, bool]:
        """Index multiple documents in parallel with progress tracking."""
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.index_document, path, fid): (path, fid)
                for path, fid in zip(file_paths, file_ids)
            }
            
            for future in tqdm(futures, desc="Indexing documents"):
                path, fid = futures[future]
                try:
                    success = future.result()
                    results[path] = success
                except Exception as e:
                    logger.error(f"Error processing {path}: {str(e)}")
                    results[path] = False
        
        return results
    
    def optimize_index(self):
        """Optimize the vector index for faster search."""
        logger.info("Optimizing index...")
        try:
            # For ChromaDB, we can force a compaction of the database
            if hasattr(self.vector_store, 'persist'):
                self.vector_store.persist()
            elif hasattr(self.vector_store, '_client') and hasattr(self.vector_store._client, 'persist'):
                self.vector_store._client.persist()
            logger.info("Index optimization complete")
            return True
        except Exception as e:
            logger.error(f"Error optimizing index: {str(e)}")
            return False
        
    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete a document and all its chunks from the index.
        
        Args:
            document_id: ID of the document to delete
            
        Returns:
            Dictionary with deletion results
        """
        result = {
            'document_id': document_id,
            'status': 'failed',
            'chunks_deleted': 0,
            'error': None
        }
        
        try:
            # Get all chunks for this document
            chunks = self.vector_store.get(where={"document_id": document_id})
            if not chunks.get('ids'):
                logger.warning(f"No chunks found for document {document_id}")
                result.update({
                    'status': 'not_found',
                    'message': 'Document not found in the index'
                })
                return result
                
            # Delete all chunks
            self.vector_store.delete(ids=chunks['ids'])
            
            # Log the deletion
            chunks_deleted = len(chunks['ids'])
            logger.info(f"Deleted {chunks_deleted} chunks for document {document_id}")
            
            result.update({
                'status': 'success',
                'chunks_deleted': chunks_deleted,
                'document_id': document_id
            })
            
        except Exception as e:
            error_msg = f"Error deleting document {document_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.update({
                'status': 'error',
                'error': error_msg
            })
            
        return result
        
    def update_document(
        self,
        file_path: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        version: str = None
    ) -> Dict[str, Any]:
        """
        Update an existing document by first deleting it and then re-indexing.
        
        Args:
            file_path: Path to the updated document file
            document_id: ID of the document to update
            metadata: Updated metadata for the document
            version: New version string (will increment if None)
            
        Returns:
            Dictionary with update results
        """
        # First delete the existing document
        delete_result = self.delete_document(document_id)
        if delete_result['status'] not in ['success', 'not_found']:
            return {
                'document_id': document_id,
                'status': 'error',
                'error': f"Failed to delete existing document: {delete_result.get('error')}",
                'operation': 'delete'
            }
            
        # Get current version if not specified
        if version is None:
            # Try to get current version
            chunks = self.vector_store.get(
                where={"document_id": document_id},
                limit=1
            )
            
            if chunks.get('metadatas'):
                current_version = chunks['metadatas'][0].get('version', '1.0')
                try:
                    # Try to increment version number
                    major, minor = map(int, current_version.split('.'))
                    version = f"{major}.{minor + 1}"
                except (ValueError, AttributeError):
                    # If version is not in X.Y format, just append .1
                    version = f"{current_version}.1"
            else:
                version = "1.0"
                
        # Re-index the document
        return self.index_document(
            file_path=file_path,
            document_id=document_id,
            metadata=metadata,
            version=version,
            overwrite=True
        )
        
    def get_document_info(self, document_id: str) -> Dict[str, Any]:
        """
        Get information about a document in the index.
        
        Args:
            document_id: ID of the document to retrieve
            
        Returns:
            Dictionary with document information and metadata
        """
        try:
            # Get all chunks for this document
            chunks = self.vector_store.get(
                where={"document_id": document_id},
                include=["metadatas", "documents"]
            )
            
            if not chunks.get('ids'):
                return {
                    'status': 'not_found',
                    'document_id': document_id,
                    'message': 'Document not found in the index'
                }
                
            # Extract metadata from the first chunk (should be the same for all chunks)
            first_metadata = chunks['metadatas'][0] if chunks.get('metadatas') else {}
            
            return {
                'status': 'success',
                'document_id': document_id,
                'chunk_count': len(chunks['ids']),
                'metadata': first_metadata,
                'chunks': [
                    {
                        'chunk_id': meta.get('chunk_id', f"{document_id}_chunk_{i}"),
                        'chunk_index': meta.get('chunk_index', i),
                        'content': doc[:100] + '...' if doc else ''
                    }
                    for i, (doc, meta) in enumerate(zip(
                        chunks.get('documents', []),
                        chunks.get('metadatas', [])
                    ))
                ]
            }
            
        except Exception as e:
            error_msg = f"Error retrieving document {document_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'status': 'error',
                'document_id': document_id,
                'error': error_msg
            }

    def get_document_chunks(self, file_id: str, include_embeddings: bool = False) -> List[Dict[str, Any]]:
        """Retrieve all chunks for a specific document.
        
        Args:
            file_id: The ID of the file to retrieve chunks for
            include_embeddings: Whether to include embeddings in the response (default: False)
            
        Returns:
            List of document chunks with metadata
        """
        try:
            results = self.vector_store.get(where={"file_id": file_id})
            chunks = []
            
            for i, doc_id in enumerate(results["ids"]):
                chunk = {
                    "id": doc_id,
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i],
                }
                
                # Only include embeddings if explicitly requested
                if include_embeddings and "embeddings" in results:
                    chunk["embedding"] = results["embeddings"][i]
                    
                chunks.append(chunk)
                
            return chunks
            
        except Exception as e:
            logger.error(f"Error retrieving chunks for file_id {file_id}: {str(e)}")
            return []
