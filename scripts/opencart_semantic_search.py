"""
OpenCart Semantic Search Module

Provides semantic search capabilities for OpenCart products by leveraging the existing RAG infrastructure.
"""
import os
import sys
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any, Union
from datetime import datetime
import aiosqlite
import hashlib

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Now import from rag_api
from rag_api.chroma_utils import (
    search_documents,
    CachedEmbeddings,
    get_vectorstore,
    preprocess_text,
    vectorstore,  # Reuse the global vectorstore instance
    EMBEDDING_MODEL,
    device
)

logger = logging.getLogger(__name__)

# Database paths
CATALOG_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "catalogs.db")

# Initialize the embedding function
embedding_function = CachedEmbeddings(model_name=EMBEDDING_MODEL, device=device)

# Collection name for OpenCart products in the vectorstore
OPENCART_COLLECTION = "opencart_products"

# Metadata field names
METADATA_FIELDS = {
    'product_id': 'product_id',
    'catalog_id': 'catalog_id',
    'name': 'name',
    'sku': 'sku',
    'price': 'price',
    'url': 'url',
    'image': 'image',
    'quantity': 'quantity',
    'organization_id': 'organization_id',
    'source_type': 'source_type',
    'indexed_at': 'indexed_at'
}

def get_product_text(product_data: Dict[str, Any]) -> str:
    """Extract and combine relevant text fields from product data for embedding."""
    text_parts = [
        product_data.get('name', ''),
        product_data.get('description', ''),
        product_data.get('meta_keyword', ''),
        product_data.get('meta_description', ''),
        product_data.get('sku', '')
    ]
    return ' '.join(filter(None, text_parts))

async def index_product(
    product_id: str,
    catalog_id: str,
    product_data: Dict[str, Any],
    organization_id: Optional[str] = None
) -> bool:
    """
    Index a single product in the vectorstore using the existing RAG infrastructure.
    
    Args:
        product_id: Unique product ID
        catalog_id: Catalog ID the product belongs to
        product_data: Dictionary containing product fields
        organization_id: Optional organization ID for multi-tenancy
        
    Returns:
        bool: True if indexing was successful, False otherwise
    """
    try:
        # Prepare product text for embedding
        text = get_product_text(product_data)
        if not text.strip():
            logger.warning(f"Skipping empty product text for {product_id}")
            return False
        
        # Prepare metadata
        metadata = {
            METADATA_FIELDS['product_id']: str(product_id),
            METADATA_FIELDS['catalog_id']: str(catalog_id),
            METADATA_FIELDS['name']: product_data.get('name', ''),
            METADATA_FIELDS['sku']: product_data.get('sku', ''),
            METADATA_FIELDS['price']: str(product_data.get('price', 0)),
            METADATA_FIELDS['url']: product_data.get('url', ''),
            METADATA_FIELDS['image']: product_data.get('image', ''),
            METADATA_FIELDS['quantity']: str(product_data.get('quantity', 0)),
            METADATA_FIELDS['source_type']: 'opencart_product',
            METADATA_FIELDS['indexed_at']: datetime.utcnow().isoformat(),
            'source': f'opencart:{catalog_id}:{product_id}'
        }
        
        # Add organization ID if provided
        if organization_id:
            metadata[METADATA_FIELDS['organization_id']] = organization_id
        
        # Generate a unique ID for this product in the vectorstore
        doc_id = f"opencart_{catalog_id}_{product_id}"
        
        # Add to vectorstore using the existing infrastructure
        vectorstore.add_texts(
            texts=[text],
            metadatas=[metadata],
            ids=[doc_id],
            collection_name=OPENCART_COLLECTION
        )
        
        # Update product's indexed status in the database
        async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
            await conn.execute(
                """
                UPDATE catalog_products 
                SET indexed = 1, updated_at = ? 
                WHERE product_id = ? AND catalog_id = ?
                """,
                (datetime.utcnow().isoformat(), product_id, catalog_id)
            )
            await conn.commit()
            
            # Update catalog's indexed_products count
            await conn.execute(
                """
                UPDATE catalogs 
                SET indexed_products = (
                    SELECT COUNT(*) 
                    FROM catalog_products 
                    WHERE catalog_id = ? AND indexed = 1
                ),
                updated_at = ?,
                last_indexed_at = ?
                WHERE catalog_id = ?
                """,
                (catalog_id, datetime.utcnow().isoformat(), 
                 datetime.utcnow().isoformat(), catalog_id)
            )
            await conn.commit()
            
        logger.info(f"Successfully indexed product {product_id} in catalog {catalog_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error indexing product {product_id}: {e}", exc_info=True)
        return False

async def search_products_semantic(
    query: str,
    catalog_ids: List[str],
    organization_id: Optional[str] = None,
    limit: int = 10,
    min_relevance_score: float = 0.2,
    use_hybrid_search: bool = True,
    bm25_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Search products using semantic similarity by leveraging the existing RAG search infrastructure.
    
    Args:
        query: Search query text
        catalog_ids: List of catalog IDs to search in
        organization_id: Optional organization ID for multi-tenancy
        limit: Maximum number of results to return
        min_relevance_score: Minimum relevance score (0-1) for results
        use_hybrid_search: Whether to use hybrid semantic + keyword search
        bm25_weight: Weight for BM25 score in hybrid search (0-1)
        
    Returns:
        List of matching products with scores and metadata
    """
    try:
        if not query or not catalog_ids:
            return []
        
        # First, search without filters to understand the document structure
        logger.info("Performing initial search without filters to check document structure")
        test_results = search_documents(
            query=query,
            max_results=5,  # Just get a few results
            min_relevance_score=0.9,  # Lower the threshold to see more results
            use_hybrid_search=use_hybrid_search,
            bm25_weight=bm25_weight,
            filter_conditions=None  # No filters for this test
        )
        
        # Log the structure of the results
        if test_results.get('semantic_results'):
            logger.info(f"Found {len(test_results['semantic_results'])} documents in test search")
            for i, doc in enumerate(test_results['semantic_results'][:3]):  # Log first 3 docs
                if hasattr(doc, 'metadata'):
                    logger.info(f"Document {i+1} metadata: {doc.metadata}")
        
        # Now prepare the actual filter conditions
        filter_conditions = {
            "$and": [
                {"source_type": {"$eq": "opencart_product"}},
                {"catalog_id": {"$in": [str(cid) for cid in catalog_ids]}}
            ]
        }
        
        # Add organization filter if provided
        if organization_id:
            filter_conditions["$and"].append({"organization_id": {"$eq": str(organization_id)}})
        
        logger.info(f"Using filter conditions: {filter_conditions}")
        
        # Perform the actual search with filters
        search_results = search_documents(
            query=query,
            max_results=limit,
            min_relevance_score=min_relevance_score,
            use_hybrid_search=use_hybrid_search,
            bm25_weight=bm25_weight,
            filter_conditions=filter_conditions
        )
        
        logger.info(f"Search returned {len(search_results.get('semantic_results', []))} results")
        
        # Process and format results
        products = []
        for doc in search_results.get('semantic_results', []):
            if not hasattr(doc, 'metadata'):
                continue
                
            metadata = doc.metadata
            score = metadata.get('relevance_score', 0)
            
            # Skip results below threshold
            if score < min_relevance_score:
                continue
            
            # Format product data
            product = {
                'product_id': metadata.get('product_id'),
                'catalog_id': metadata.get('catalog_id'),
                'name': metadata.get('name'),
                'sku': metadata.get('sku'),
                'price': float(metadata.get('price', 0)),
                'url': metadata.get('url'),
                'image': metadata.get('image'),
                'quantity': int(metadata.get('quantity', 0)),
                'similarity_score': score,
                'metadata': metadata
            }
            products.append(product)
        
        # Sort by score in descending order
        products.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)
        
        return products[:limit]
        
    except Exception as e:
        logger.error(f"Error in semantic product search: {e}", exc_info=True)
        return []

async def batch_index_products(
    products: List[Dict[str, Any]],
    catalog_id: str,
    organization_id: Optional[str] = None,
    batch_size: int = 50
) -> Tuple[int, List[str]]:
    """
    Index multiple products in batches using the existing RAG infrastructure.
    
    Args:
        products: List of product dictionaries
        catalog_id: Catalog ID
        organization_id: Optional organization ID
        batch_size: Number of products to process in each batch
        
    Returns:
        Tuple of (success_count, failed_ids)
    """
    success_count = 0
    failed_ids = []
    
    # Process products in batches
    for i in range(0, len(products), batch_size):
        batch = products[i:i + batch_size]
        batch_texts = []
        batch_metadatas = []
        batch_ids = []
        
        for product in batch:
            try:
                product_id = str(product.get('product_id'))
                if not product_id:
                    continue
                
                # Prepare product text and metadata
                text = get_product_text(product)
                if not text.strip():
                    logger.warning(f"Skipping empty product text for {product_id}")
                    continue
                
                metadata = {
                    METADATA_FIELDS['product_id']: product_id,
                    METADATA_FIELDS['catalog_id']: catalog_id,
                    METADATA_FIELDS['name']: product.get('name', ''),
                    METADATA_FIELDS['sku']: product.get('sku', ''),
                    METADATA_FIELDS['price']: str(product.get('price', 0)),
                    METADATA_FIELDS['url']: product.get('url', ''),
                    METADATA_FIELDS['image']: product.get('image', ''),
                    METADATA_FIELDS['quantity']: str(product.get('quantity', 0)),
                    METADATA_FIELDS['source_type']: 'opencart_product',
                    METADATA_FIELDS['indexed_at']: datetime.utcnow().isoformat(),
                    'source': f'opencart:{catalog_id}:{product_id}'
                }
                
                if organization_id:
                    metadata[METADATA_FIELDS['organization_id']] = organization_id
                
                batch_texts.append(text)
                batch_metadatas.append(metadata)
                batch_ids.append(f"opencart_{catalog_id}_{product_id}")
                
            except Exception as e:
                logger.error(f"Error preparing product {product.get('product_id')}: {e}")
                failed_ids.append(str(product.get('product_id', 'unknown')))
        
        # Add batch to vectorstore
        if batch_texts:
            try:
                vectorstore.add_texts(
                    texts=batch_texts,
                    metadatas=batch_metadatas,
                    ids=batch_ids,
                    collection_name=OPENCART_COLLECTION
                )
                success_count += len(batch_texts)
                
                # Update database for successful products
                for product_id in [m.get('product_id') for m in batch_metadatas if m.get('product_id')]:
                    try:
                        async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
                            await conn.execute(
                                """
                                UPDATE catalog_products 
                                SET indexed = 1, updated_at = ? 
                                WHERE product_id = ? AND catalog_id = ?
                                """,
                                (datetime.utcnow().isoformat(), product_id, catalog_id)
                            )
                            await conn.commit()
                    except Exception as e:
                        logger.error(f"Error updating database for product {product_id}: {e}")
                        failed_ids.append(product_id)
                        
            except Exception as e:
                logger.error(f"Error adding batch to vectorstore: {e}")
                failed_ids.extend([m.get('product_id', 'unknown') for m in batch_metadatas])
    
    # Update catalog stats after all batches are processed
    if success_count > 0:
        try:
            async with aiosqlite.connect(CATALOG_DB_PATH) as conn:
                await conn.execute(
                    """
                    UPDATE catalogs 
                    SET indexed_products = (
                        SELECT COUNT(*) 
                        FROM catalog_products 
                        WHERE catalog_id = ? AND indexed = 1
                    ),
                    updated_at = ?,
                    last_indexed_at = ?
                    WHERE catalog_id = ?
                    """,
                    (catalog_id, datetime.utcnow().isoformat(), 
                     datetime.utcnow().isoformat(), catalog_id)
                )
                await conn.commit()
        except Exception as e:
            logger.error(f"Error updating catalog stats: {e}")
    
    return success_count, failed_ids
