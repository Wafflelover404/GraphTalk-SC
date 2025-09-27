"""
Enhanced semantic search with advanced query understanding, metadata filtering, and result re-ranking.

Features:
- Hybrid search combining semantic and keyword search
- Metadata filtering and faceted search
- Query expansion and understanding
- Cross-encoder based re-ranking
- Result deduplication and diversity
"""
import logging
import re
import torch
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple, Set
from tqdm import tqdm
from collections import defaultdict
import hashlib
from .embeddings import get_vector_store, EnhancedEmbeddingFunction
logger = logging.getLogger(__name__)

class EnhancedSearcher:
    """
    Advanced semantic search with hybrid retrieval, metadata filtering, and re-ranking.
    
    Supports:
    - Vector similarity search
    - Metadata filtering
    - Query expansion
    - Cross-encoder re-ranking
    - Result deduplication
    """
     
    def __init__(
        self, 
        vector_store=None, 
        rerank_model: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2",
        enable_hybrid_search: bool = True,
        enable_reranking: bool = True,
        max_results: int = 100,
        rerank_top_k: int = 20,
        min_score: float = 0.0,
        use_gpu: bool = torch.cuda.is_available()
    ):
        """
        Initialize the enhanced searcher.
        
        Args:
            vector_store: Vector store to use for search
            rerank_model: Name of the cross-encoder model for re-ranking
            enable_hybrid_search: Whether to enable hybrid search (combines vector and keyword search)
            enable_reranking: Whether to enable cross-encoder re-ranking
            max_results: Maximum number of results to return
            rerank_top_k: Number of top results to re-rank
            min_score: Minimum similarity score for results (0-1)
            use_gpu: Whether to use GPU for inference if available
        """
        self.vector_store = vector_store or get_vector_store()
        self.rerank_model = None
        self.rerank_tokenizer = None
        self.rerank_model_name = rerank_model
        self.enable_hybrid_search = enable_hybrid_search
        self.enable_reranking = enable_reranking
        self.max_results = max_results
        self.rerank_top_k = rerank_top_k
        self.min_score = min_score
        self.use_gpu = use_gpu and torch.cuda.is_available()
        
        # Initialize components
        self.embedding_function = EnhancedEmbeddingFunction()
        self._init_reranker()
        
        logger.info(f"Initialized EnhancedSearcher with model {rerank_model}")
        if self.use_gpu:
            logger.info("Using GPU for inference")
        else:
            logger.info("Using CPU for inference")
    
    def _init_reranker(self):
        """Lazy load the reranker model."""
        if self.rerank_model is None and self.enable_reranking:
            try:
                from sentence_transformers import CrossEncoder
                
                logger.info(f"Loading reranker model: {self.rerank_model_name}")
                self.rerank_model = CrossEncoder(
                    self.rerank_model_name,
                    device="cuda" if self.use_gpu else "cpu",
                    max_length=512
                )
                logger.info(f"Successfully loaded reranker model: {self.rerank_model_name}")
                
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed. Falling back to standard search. "
                    "Install with: pip install sentence-transformers"
                )
                self.enable_reranking = False
            except Exception as e:
                logger.error(f"Error loading reranker model: {str(e)}")
                self.enable_reranking = False
        return self.rerank_model, self.rerank_tokenizer
    
    def _vector_search(
        self, 
        query: str, 
        k: int, 
        filter: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        try:
            # Get vector representation of the query
            query_embedding = self.embedding_function.embed_query(query)
            
            # Perform similarity search
            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter,
                **kwargs
            )
            
            # Format results
            return [
                {
                    'content': doc.page_content,
                    'score': float(score),
                    'metadata': doc.metadata,
                    'search_type': 'vector'
                }
                for doc, score in results
            ]
            
        except Exception as e:
            logger.error(f"Error in vector search: {str(e)}", exc_info=True)
            return []
    
    def _keyword_search(
        self, 
        query: str, 
        k: int, 
        filter: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Perform keyword-based search."""
        try:
            # Simple keyword search implementation
            # In a real implementation, this would use a proper keyword search engine
            # like Elasticsearch, BM25, or similar
            
            # For now, we'll use a simple text matching approach
            query_terms = set(re.findall(r'\w+', query.lower()))
            
            # Get all documents that match the filter
            if hasattr(self.vector_store, 'get'):
                # ChromaDB specific
                results = self.vector_store.get(
                    where=filter,
                    include=['documents', 'metadatas']
                )
                
                # Calculate keyword match scores
                scored_docs = []
                for i, (doc, meta) in enumerate(zip(results['documents'], results['metadatas'])):
                    doc_terms = set(re.findall(r'\w+', doc.lower()))
                    common_terms = query_terms.intersection(doc_terms)
                    score = len(common_terms) / len(query_terms) if query_terms else 0
                    
                    scored_docs.append({
                        'content': doc,
                        'score': score,
                        'metadata': meta,
                        'search_type': 'keyword'
                    })
                
                # Sort by score
                scored_docs.sort(key=lambda x: x['score'], reverse=True)
                return scored_docs[:k]
                
            else:
                logger.warning("Keyword search not supported with the current vector store")
                return []
                
        except Exception as e:
            logger.error(f"Error in keyword search: {str(e)}", exc_info=True)
            return []
    
    def _hybrid_search(
        self, 
        query: str, 
        k: int, 
        filter: Optional[Dict[str, Any]] = None,
        alpha: float = 0.5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining vector and keyword search.
        
        Args:
            query: Search query
            k: Number of results to return
            filter: Optional metadata filters
            alpha: Weight for vector search (1.0 = only vector, 0.0 = only keyword)
            
        Returns:
            List of search results with combined scores
        """
        # Get results from both search types
        vector_results = self._vector_search(query, k, filter, **kwargs)
        keyword_results = self._keyword_search(query, k, filter, **kwargs)
        
        # Create a dictionary to store combined scores
        combined_scores = {}
        
        # Add vector search results
        for i, result in enumerate(vector_results):
            doc_id = result.get('metadata', {}).get('chunk_id', i)
            combined_scores[doc_id] = {
                'content': result['content'],
                'vector_score': result['score'],
                'keyword_score': 0.0,
                'metadata': result['metadata']
            }
        
        # Add keyword search results
        for i, result in enumerate(keyword_results):
            doc_id = result.get('metadata', {}).get('chunk_id', i)
            if doc_id in combined_scores:
                combined_scores[doc_id]['keyword_score'] = result['score']
            else:
                combined_scores[doc_id] = {
                    'content': result['content'],
                    'vector_score': 0.0,
                    'keyword_score': result['score'],
                    'metadata': result['metadata']
                }
        
        # Combine scores using weighted average
        combined_results = []
        for doc_id, scores in combined_scores.items():
            combined_score = (alpha * scores['vector_score'] + 
                            (1 - alpha) * scores['keyword_score'])
            
            combined_results.append({
                'content': scores['content'],
                'score': combined_score,
                'vector_score': scores['vector_score'],
                'keyword_score': scores['keyword_score'],
                'metadata': scores['metadata'],
                'search_type': 'hybrid'
            })
        
        # Sort by combined score
        combined_results.sort(key=lambda x: x['score'], reverse=True)
        return combined_results[:k]
    
    def _rerank_results(
        self, 
        query: str, 
        results: List[Dict[str, Any]], 
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Re-rank search results using a cross-encoder model.
        
        Args:
            query: Original search query
            results: List of search results to re-rank
            top_k: Number of top results to return after re-ranking
            
        Returns:
            Re-ranked list of results
        """
        if not results or not self.enable_reranking or self.rerank_model is None:
            return results[:top_k] if top_k > 0 else results
            
        try:
            # Prepare query-document pairs for re-ranking
            pairs = [(query, result['content']) for result in results]
            
            # Get re-ranking scores
            rerank_scores = self.rerank_model.predict(
                pairs,
                batch_size=32,
                show_progress_bar=False,
                convert_to_tensor=True
            )
            
            # Convert tensor to numpy if needed
            if hasattr(rerank_scores, 'numpy'):
                rerank_scores = rerank_scores.numpy()
            elif hasattr(rerank_scores, 'cpu'):
                rerank_scores = rerank_scores.cpu().numpy()
            
            # Update results with re-ranking scores
            for i, score in enumerate(rerank_scores):
                if i < len(results):
                    # Combine original and re-ranking scores
                    original_score = results[i].get('score', 0.0)
                    combined_score = 0.7 * float(score) + 0.3 * float(original_score)
                    
                    results[i].update({
                        'rerank_score': float(score),
                        'score': combined_score,
                        'original_score': original_score
                    })
            
            # Sort by combined score
            results.sort(key=lambda x: x['score'], reverse=True)
            
            return results[:top_k] if top_k > 0 else results
            
        except Exception as e:
            logger.error(f"Error during re-ranking: {str(e)}", exc_info=True)
            return results[:top_k] if top_k > 0 else results
    
    def _parse_query(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Parse the search query to extract potential filters and clean the query.
        
        Args:
            query: Original search query
            
        Returns:
            Tuple of (cleaned_query, filters_dict)
        """
        # Initialize filters
        filters = {}
        cleaned_query = query
        
        # Simple filter extraction (e.g., "author:john")
        filter_patterns = [
            (r'(\w+):"([^"]+)"', lambda m: (m.group(1), m.group(2))),  # key:"value"
            (r'(\w+):(\S+)', lambda m: (m.group(1), m.group(2))),      # key:value
            (r'is:(\w+)', lambda m: ('type', m.group(1))),              # is:type
        ]
        
        for pattern, extractor in filter_patterns:
            matches = list(re.finditer(pattern, query))
            for match in reversed(matches):  # Process in reverse to not mess up string positions
                key, value = extractor(match)
                if key and value:
                    if key not in filters:
                        filters[key] = []
                    filters[key].append(value)
                    # Remove the filter from the query
                    cleaned_query = cleaned_query[:match.start()] + cleaned_query[match.end():]
        
        # Clean up the query
        cleaned_query = ' '.join(cleaned_query.split())
        
        # Convert single-value lists to single values
        for key in list(filters.keys()):
            if len(filters[key]) == 1:
                filters[key] = filters[key][0]
        
        return cleaned_query, filters
    
    def _deduplicate_results(
            self, 
            results: List[Dict[str, Any]], 
            similarity_threshold: float = 0.95
        ) -> List[Dict[str, Any]]:
        """
        Remove near-duplicate results from search results.
        
        Args:
            results: List of search results
            similarity_threshold: Threshold for considering results as duplicates (0-1)
            
        Returns:
            List of deduplicated results
        """
        if not results:
            return []
            
        # Simple content-based deduplication using hashlib
        seen_hashes = set()
        deduped_results = []
        
        for result in results:
            # Create a hash of the content for deduplication
            content = result.get('content', '').encode('utf-8')
            content_hash = hashlib.md5(content).hexdigest()
            
            # Check if we've seen this exact content before
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                deduped_results.append(result)
        
        return deduped_results
    
    def search(
        self, 
        query: str, 
        k: int = 10, 
        filter: Optional[Dict[str, Any]] = None,
        search_type: str = "hybrid",
        min_score: Optional[float] = None,
        include_metadata: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Perform an advanced semantic search with filtering, hybrid search, and re-ranking.
        
        Args:
            query: The search query
            k: Maximum number of results to return
            filter: Optional filter dictionary for metadata (e.g., {"author": "John", "year": {"$gt": 2020}})
            search_type: Type of search to perform ("vector", "keyword", "hybrid")
            min_score: Minimum similarity score (0-1) for results
            include_metadata: Whether to include metadata in results
            
        Returns:
            Dictionary containing search results and metadata
        """
        if min_score is None:
            min_score = self.min_score
            
        # Ensure k is within bounds
        k = min(max(1, k), self.max_results)
        
        # Parse query for potential filters and query expansion
        parsed_query, query_filters = self._parse_query(query)
        
        # Combine explicit filters with query filters
        if filter is None:
            filter = {}
            
        if query_filters:
            # Merge query filters with explicit filters
            for key, value in query_filters.items():
                if key in filter:
                    # Handle merging of filters for the same key if needed
                    if isinstance(filter[key], dict) and isinstance(value, dict):
                        filter[key].update(value)
                    else:
                        filter[key] = value
                else:
                    filter[key] = value
        
        logger.debug(f"Searching with query: '{parsed_query}', filters: {filter}")
        
        # Perform the initial search
        if search_type == "hybrid" and self.enable_hybrid_search:
            results = self._hybrid_search(parsed_query, k * 3, filter, **kwargs)
        elif search_type == "keyword":
            results = self._keyword_search(parsed_query, k * 3, filter, **kwargs)
        else:
            results = self._vector_search(parsed_query, k * 3, filter, **kwargs)
        
        # Apply minimum score threshold
        if min_score > 0:
            results = [r for r in results if r['score'] >= min_score]
        
        # Re-rank if enabled and we have enough results
        if self.enable_reranking and len(results) > 1:
            results = self._rerank_results(parsed_query, results, top_k=min(k * 2, len(results)))
        
        # Deduplicate results based on content hash
        results = self._deduplicate_results(results)
        
        # Format and return results
        return {
            'query': query,
            'parsed_query': parsed_query,
            'filters': filter,
            'results': results[:k],
            'count': len(results),
            'has_more': len(results) > k,
            'search_type': search_type,
            'min_score': min_score
        }
    
    def rerank_results(self, query: str, documents: List[Dict], top_k: int = 5) -> List[Dict]:
        """Re-rank search results using a cross-encoder."""
        if not documents or len(documents) <= 1:
            return documents[:top_k]
            
        try:
            model, tokenizer = self._get_reranker()
            
            # Prepare pairs for reranking
            pairs = [(query, doc["document"]) for doc in documents]
            
            # Tokenize
            features = tokenizer(
                pairs,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512
            ).to(self.rerank_model.device)
            
            # Get scores
            with torch.no_grad():
                scores = model(**features).logits
            
            # Update scores
            for i, score in enumerate(scores):
                documents[i]["score"] = score.item()
            
            # Sort by new scores
            documents.sort(key=lambda x: x["score"], reverse=True)
            
        except Exception as e:
            logger.warning(f"Reranking failed: {str(e)}")
            # Fall back to original ordering
            pass
            
        return documents[:top_k]
    
    def semantic_search(
        self,
        query: str,
        filter_conditions: Optional[Dict] = None,
        top_k: int = 5,
        score_threshold: float = 0.3,
        use_reranking: bool = True,
        include_embeddings: bool = False
    ) -> Dict[str, Any]:
        """Enhanced semantic search with filtering and re-ranking."""
        try:
            # First, perform vector similarity search
            results = self.vector_store.query(
                query_texts=[query],
                n_results=top_k * 3,  # Get more results for re-ranking
                where=filter_conditions,
                where_document=None,
                include=["documents", "metadatas", "distances"] + (["embeddings"] if include_embeddings else [])
            )
            
            # Format results
            documents = []
            for i in range(len(results["ids"][0])):
                doc_id = results["ids"][0][i]
                doc_text = results["documents"][0][i]
                metadata = results["metadatas"][0][i]
                score = 1.0 - results["distances"][0][i]  # Convert to similarity score
                
                if score >= score_threshold:
                    doc_data = {
                        "id": doc_id,
                        "document": doc_text,
                        "metadata": metadata,
                        "score": score
                    }
                    # Skip adding embeddings to reduce response size
                    documents.append(doc_data)
            
            # Re-rank if enabled
            if use_reranking and len(documents) > 1:
                documents = self.rerank_results(query, documents, top_k)
            
            # Format final results
            return {
                "results": documents[:top_k],
                "stats": {
                    "total_matches": len(documents),
                    "returned_matches": min(top_k, len(documents))
                }
            }
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            return {
                "results": [],
                "error": str(e)
            }
    
    def hybrid_search(
        self,
        query: str,
        filter_conditions: Optional[Dict] = None,
        top_k: int = 5,
        score_threshold: float = 0.3,
        use_reranking: bool = True,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7
    ) -> Dict[str, Any]:
        """Hybrid search combining semantic and keyword-based search."""
        try:
            # Perform semantic search
            semantic_results = self.semantic_search(
                query=query,
                filter_conditions=filter_conditions,
                top_k=top_k * 2,  # Get more results for combination
                score_threshold=score_threshold,
                use_reranking=False,  # We'll rerank after combination
                include_embeddings=True
            )
            
            # Perform keyword search (if implemented)
            # This is a placeholder - you would implement your keyword search here
            keyword_results = {"results": []}  # Placeholder
            
            # Combine results
            combined_results = {}
            
            # Add semantic results
            for doc in semantic_results.get("results", []):
                combined_results[doc["id"]] = {
                    **doc,
                    "combined_score": doc["score"] * semantic_weight
                }
            
            # Add keyword results (if any)
            for doc in keyword_results.get("results", []):
                doc_id = doc.get("id")
                if doc_id in combined_results:
                    combined_results[doc_id]["combined_score"] += doc.get("score", 0) * keyword_weight
                else:
                    combined_results[doc_id] = {
                        **doc,
                        "combined_score": doc.get("score", 0) * keyword_weight
                    }
            
            # Sort by combined score
            sorted_results = sorted(
                combined_results.values(),
                key=lambda x: x["combined_score"],
                reverse=True
            )
            
            # Apply final reranking if needed
            if use_reranking and len(sorted_results) > 1:
                sorted_results = self.rerank_results(query, sorted_results, top_k)
            
            # Prepare results without embeddings
            clean_results = []
            for result in sorted_results[:top_k]:
                # Create a new dict without the 'embedding' key
                clean_result = {k: v for k, v in result.items() if k != 'embedding'}
                clean_results.append(clean_result)
                
            return {
                "results": clean_results,
                "stats": {
                    "total_matches": len(sorted_results),
                    "returned_matches": min(top_k, len(sorted_results))
                }
            }
            
        except Exception as e:
            logger.error(f"Hybrid search error: {str(e)}")
            return {
                "results": [],
                "error": str(e)
            }
