import os
import re
import logging
import torch
import hashlib
import json
import nltk
from functools import lru_cache
from typing import List, Dict, Tuple, Optional, Union, Set, Any

# Ensure NLTK data is downloaded
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, UnstructuredHTMLLoader
from langchain_chroma import Chroma
from langchain_core.documents import Document
from difflib import SequenceMatcher
import numpy as np
from timing_utils import Timer, PerformanceTracker, time_block
from cachetools import TTLCache

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)

try:
    from langchain_huggingface import HuggingFaceEmbeddings as SentenceTransformerEmbeddings
except ImportError:
    from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings

# Import Chonkie for advanced chunking
from chonkie import TokenChunker, SentenceChunker

# Configure device (use GPU if available)
device = "cuda" if torch.cuda.is_available() else "cpu"

# Initialize embedding function with caching
class CachedEmbeddings:
    def __init__(self, model_name: str, device: str = "cpu"):
        # Only pass show_progress_bar in one place, not both
        self.embedder = SentenceTransformerEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device}
        )
        self.device = device
        self.cache = TTLCache(maxsize=1000, ttl=3600)  # Cache for 1 hour
        
    @lru_cache(maxsize=1000)
    def embed_query(self, text: str) -> List[float]:
        """Cache embeddings for frequently used queries"""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        embedding = self.embedder.embed_query(text)
        self.cache[cache_key] = embedding
        return embedding
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Batch process documents with caching"""
        # Try to get from cache first
        cache_keys = [hashlib.md5(text.encode()).hexdigest() for text in texts]
        cached_results = [self.cache.get(key) for key in cache_keys]
        
        # Find texts that need embedding
        to_embed = []
        indices = []
        results = [None] * len(texts)
        
        for i, (cached, text) in enumerate(zip(cached_results, texts)):
            if cached is not None:
                results[i] = cached
            else:
                to_embed.append(text)
                indices.append(i)
        
        # Embed remaining texts
        if to_embed:
            # Add batch processing for large document sets
            batch_size = 32
            embeddings = []
            for i in range(0, len(to_embed), batch_size):
                batch = to_embed[i:i + batch_size]
                batch_embeddings = self.embedder.embed_documents(batch)
                embeddings.extend(batch_embeddings)
            for idx, emb in zip(indices, embeddings):
                self.cache[cache_keys[idx]] = emb
                results[idx] = emb
                
        return results

# Use a faster model for production
EMBEDDING_MODEL = "intfloat/multilingual-e5-small" if device == "cpu" else "intfloat/multilingual-e5-base"
embedding_function = CachedEmbeddings(model_name=EMBEDDING_MODEL, device=device)

# Initialize Chonkie chunkers for different document types
# TokenChunker: Token-based chunking with overlap (best for general use and code)
# Using Mistral tokenizer for better multilingual support and larger vocabulary
try:
    # Try Mistral tokenizer first (best for multilingual, modern architecture)
    token_chunker = TokenChunker(
        tokenizer="mistralai/Mistral-7B-v0.1",
        chunk_size=512,
        chunk_overlap=128  # Increased overlap for better context preservation
    )
    print("✓ Using Mistral tokenizer for enhanced chunking")
except Exception as e:
    # Fallback to GPT-2 if Mistral not available
    print(f"⚠️  Mistral tokenizer not available ({e}), using GPT-2")
    token_chunker = TokenChunker(
        tokenizer="gpt2",
        chunk_size=512,
        chunk_overlap=128
    )

# SentenceChunker: Sentence-aware chunking (best for structured text)
sentence_chunker = SentenceChunker(
    chunk_size=512,
    chunk_overlap=1  # Overlap by 1 sentence
)

# Default chunker - use token chunker for best compatibility
chonkie_chunker = token_chunker

# Configure Chroma for optimal performance
chroma_settings = {
    "persist_directory": "./chroma_db",
    "collection_name": "documents_optimized",
    "embedding_function": embedding_function,
    "collection_metadata": {
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 128,  # Higher = more accurate but slower indexing
        "hnsw:search_ef": 64,         # Higher = more accurate but slower search
        "hnsw:M": 16                   # Higher = more memory usage but better accuracy
    }
}

# Initialize Chroma with optimized settings
vectorstore = Chroma(**chroma_settings)

# Ensure the collection exists and is properly configured
try:
    if not hasattr(vectorstore, '_collection'):
        vectorstore._collection = vectorstore._client.get_or_create_collection(
            name=chroma_settings["collection_name"],
            metadata=chroma_settings["collection_metadata"]
        )
except Exception as e:
    logging.warning(f"Could not configure Chroma collection: {str(e)}")

def select_optimal_chunker(file_path: str, content: str) -> Any:
    """
    Intelligently select the best chunker based on document type and content characteristics.
    
    Args:
        file_path: Path to the file
        content: Document content
        
    Returns:
        The optimal chunker for this document
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    content_length = len(content)
    
    # For structured documents (HTML, MD), use sentence chunker
    if file_ext in ['.html', '.md', '.markdown']:
        return sentence_chunker
    
    # For short documents, use sentence chunker to avoid over-splitting
    if content_length < 2000:
        return sentence_chunker
    
    # For all other cases (including code), use token chunker
    # Token chunker is most reliable and works well for all content types
    return token_chunker

def load_and_split_document(file_path: str, filename: str) -> List[Document]:
    """Load and split document with enhanced metadata and preprocessing using Chonkie"""
    try:
        if file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith('.docx'):
            loader = Docx2txtLoader(file_path)
        elif file_path.endswith('.html'):
            loader = UnstructuredHTMLLoader(file_path)
        elif file_path.endswith('.txt') or file_path.endswith('.md'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Preprocess content to improve quality
            preprocessed_content = preprocess_text(content)
            
            # Select optimal chunker based on document characteristics
            optimal_chunker = select_optimal_chunker(file_path, content)
            
            # Use Chonkie to chunk the text
            chunks = optimal_chunker.chunk(preprocessed_content)
            
            # Convert Chonkie chunks to LangChain Documents
            documents = []
            for chunk in chunks:
                doc = Document(
                    page_content=chunk.text,
                    metadata={
                        "source": file_path,
                        "filename": filename,
                        "file_type": os.path.splitext(filename)[1],
                        "created_at": os.path.getctime(file_path),
                        "modified_at": os.path.getmtime(file_path),
                        "chunk_start": chunk.start_index,
                        "chunk_end": chunk.end_index,
                        "token_count": chunk.token_count
                    }
                )
                documents.append(doc)
            return documents
        else:
            raise ValueError(f"Unsupported file type: {file_path}")

        documents = loader.load()
        
        # Process loaded documents with Chonkie
        chunked_documents = []
        for doc in documents:
            # Preprocess content to improve quality
            preprocessed_content = preprocess_text(doc.page_content)
            
            # Select optimal chunker
            optimal_chunker = select_optimal_chunker(file_path, doc.page_content)
            
            # Use Chonkie to chunk the text
            chunks = optimal_chunker.chunk(preprocessed_content)
            
            # Convert Chonkie chunks to LangChain Documents
            for chunk in chunks:
                new_doc = Document(
                    page_content=chunk.text,
                    metadata={
                        **doc.metadata,
                        "filename": filename,
                        "file_type": os.path.splitext(filename)[1],
                        "created_at": os.path.getctime(file_path),
                        "modified_at": os.path.getmtime(file_path),
                        "chunk_start": chunk.start_index,
                        "chunk_end": chunk.end_index,
                        "token_count": chunk.token_count
                    }
                )
                chunked_documents.append(new_doc)
            
        return chunked_documents
        
    except Exception as e:
        print(f"Error loading document {filename}: {str(e)}")
        raise

def preprocess_text(text: str, language: str = 'russian') -> str:
    """
    Enhanced text preprocessing for better search quality.
    
    Args:
        text: Input text to preprocess
        language: Language for stopwords ('russian' or 'english')
    
    Returns:
        Preprocessed text
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', '', text)
    
    # Remove HTML tags
    text = re.sub(r'<.*?>', ' ', text)
    
    # Remove special characters but keep essential punctuation and numbers
    text = re.sub(r'[^\w\s.,!?;:\-\'\"%()\[\]{}]', ' ', text)
    
    # Tokenize and remove stopwords
    try:
        stop_words = set(nltk.corpus.stopwords.words(language))
        # Add English stopwords for mixed language content
        if language != 'english':
            stop_words.update(nltk.corpus.stopwords.words('english'))
        
        tokens = nltk.word_tokenize(text, language=language)
        tokens = [token for token in tokens if token not in stop_words and len(token) > 1]
        text = ' '.join(tokens)
    except Exception as e:
        logging.warning(f"Error in tokenization: {str(e)}")
    
    # Normalize whitespace and remove extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def preprocess_query(query: str, language: str = 'russian') -> str:
    """
    Preprocess search queries for better matching.
    
    Args:
        query: Search query string
        language: Language for preprocessing
        
    Returns:
        Preprocessed query string
    """
    if not query or not isinstance(query, str):
        return ""
    
    # Basic cleaning
    query = query.lower().strip()
    query = re.sub(r'[^\w\s]', ' ', query)  # Keep only alphanumeric and spaces
    
    # Remove common search operators that might interfere
    query = re.sub(r'\b(and|or|not|filetype|site|intitle|inurl)\b', '', query)
    
    # Apply the same preprocessing as regular text
    return preprocess_text(query, language)

def index_document_to_chroma(file_path: str, file_id: int) -> bool:
	try:
		# Extract just the filename from the path
		filename = os.path.basename(file_path)
		splits = load_and_split_document(file_path, filename)
		for split in splits:
			split.metadata['file_id'] = file_id
			split.metadata['filename'] = filename  # Ensure filename is in metadata
		vectorstore.add_documents(splits)
		return True
	except Exception as e:
		print(f"Error indexing document: {e}")
		return False

def delete_doc_from_chroma(file_id: int) -> bool:
    try:
        docs = vectorstore.get(where={"file_id": file_id})
        print(f"Found {len(docs['ids'])} document chunks for file_id {file_id}")
        vectorstore._collection.delete(where={"file_id": file_id})
        print(f"Deleted all documents with file_id {file_id}")
        return True
    except Exception as e:
        print(f"Error deleting document with file_id {file_id}: {e}")
        return False

def reindex_documents(documents_dir: str, file_paths: List[str] = None) -> Dict[str, Any]:
    """
    Completely reindex all documents in the specified directory or from the provided file paths.
    
    Args:
        documents_dir: Directory containing documents to index
        file_paths: Optional list of specific file paths to index (if not provided, all files in directory will be indexed)
        
    Returns:
        Dictionary with reindexing statistics
    """
    global vectorstore
    import time
    from datetime import datetime
    from pathlib import Path
    
    start_time = time.time()
    stats = {
        'processed': 0,
        'successful': 0,
        'failed': 0,
        'errors': [],
        'total_chunks': 0,
        'file_types': {},
        'start_time': datetime.now().isoformat()
    }
    
    try:
        # Reinitialize the vectorstore
        vectorstore = Chroma(**chroma_settings)
        
        # Delete existing collection
        logger.info("Deleting existing Chroma collection...")
        vectorstore.delete_collection()
        
        # Recreate the collection
        vectorstore = Chroma(**chroma_settings)
        
        # Get list of files to process
        if file_paths is None:
            file_paths = []
            for ext in ['.pdf', '.docx', '.txt', '.md', '.html']:
                file_paths.extend(list(Path(documents_dir).rglob(f'*{ext}')))
        
        stats['total_files'] = len(file_paths)
        logger.info(f"Starting reindexing of {stats['total_files']} files...")
        
        # Process each file
        for file_path in file_paths:
            file_path = str(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            file_id = hash(file_path) % (2**32)  # Generate a consistent file ID
            
            if file_ext not in stats['file_types']:
                stats['file_types'][file_ext] = 0
            stats['file_types'][file_ext] += 1
            
            try:
                logger.info(f"Indexing {file_path}...")
                if index_document_to_chroma(file_path, file_id):
                    # Get the number of chunks added
                    docs = vectorstore.get(where={"file_id": file_id})
                    chunks_added = len(docs['ids']) if docs and 'ids' in docs else 0
                    stats['total_chunks'] += chunks_added
                    stats['successful'] += 1
                    stats['processed'] += 1
                    logger.info(f"Successfully indexed {file_path} ({chunks_added} chunks)")
                else:
                    stats['failed'] += 1
                    stats['processed'] += 1
                    stats['errors'].append(f"Failed to index {file_path}")
                    logger.error(f"Failed to index {file_path}")
            except Exception as e:
                stats['failed'] += 1
                stats['processed'] += 1
                error_msg = f"Error indexing {file_path}: {str(e)}"
                stats['errors'].append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        # Persist the vectorstore
        vectorstore.persist()
        
    except Exception as e:
        error_msg = f"Fatal error during reindexing: {str(e)}"
        stats['errors'].append(error_msg)
        logger.error(error_msg, exc_info=True)
        raise
    finally:
        # Calculate total time
        stats['end_time'] = datetime.now().isoformat()
        stats['total_time_seconds'] = time.time() - start_time
        
        logger.info(f"Reindexing completed. Success: {stats['successful']}, Failed: {stats['failed']}, "
                   f"Total chunks: {stats['total_chunks']}, Time: {stats['total_time_seconds']:.2f}s")
    
    return stats


def _calculate_filename_similarity(filename1: str, filename2: str) -> float:
    """
    Calculate similarity between two filenames using sequence matching.
    Returns a float between 0 and 1, where 1 is an exact match.
    """
    # Remove file extensions for better matching
    name1 = os.path.splitext(filename1)[0].lower()
    name2 = os.path.splitext(filename2)[0].lower()
    return SequenceMatcher(None, name1, name2).ratio()


def _meets_search_requirements(
    query: str,
    metadata: Dict[str, any],
    filename_similarity_threshold: float
) -> Tuple[bool, float, bool]:
    """
    Check if a document meets the search requirements.
    Returns a tuple of (meets_requirements, similarity_score, is_filename_match)
    """
    # Check filename similarity if filename exists
    filename = metadata.get('filename', '')
    if filename:
        filename_similarity = _calculate_filename_similarity(query, filename)
        if filename_similarity >= filename_similarity_threshold:
            return True, filename_similarity, True
    
    # Check other metadata fields if needed
    # For example, you could check document type, creation date, etc.
    # if metadata.get('doc_type') == 'research_paper':
    #     return True, 0.8, False
    
    return False, 0.0, False

def batch_cosine_similarity(query_embedding: np.ndarray, doc_embeddings: np.ndarray) -> np.ndarray:
    """Calculate cosine similarity in batch for better performance with numerical stability."""
    # Ensure proper shape
    if query_embedding.ndim == 1:
        query_embedding = query_embedding.reshape(1, -1)
    if doc_embeddings.ndim == 1:
        doc_embeddings = doc_embeddings.reshape(1, -1)
    
    # Normalize vectors for numerical stability
    query_norm = np.linalg.norm(query_embedding, axis=1, keepdims=True)
    doc_norms = np.linalg.norm(doc_embeddings, axis=1, keepdims=True)
    
    # Avoid division by zero
    query_norm = np.maximum(query_norm, 1e-10)
    doc_norms = np.maximum(doc_norms, 1e-10)
    
    # Normalize
    query_normalized = query_embedding / query_norm
    doc_normalized = doc_embeddings / doc_norms
    
    # Calculate cosine similarity
    similarities = np.dot(doc_normalized, query_normalized.T).flatten()
    
    return similarities

def calculate_bm25_score(query_terms: List[str], document: str, avg_doc_length: float, k1: float = 1.5, b: float = 0.75) -> float:
    """Calculate BM25 score for keyword-based relevance."""
    doc_terms = document.lower().split()
    doc_length = len(doc_terms)
    
    score = 0.0
    for term in query_terms:
        term = term.lower()
        term_freq = doc_terms.count(term)
        if term_freq > 0:
            # BM25 formula
            idf = np.log((1 + avg_doc_length) / (term_freq + 0.5))
            numerator = term_freq * (k1 + 1)
            denominator = term_freq + k1 * (1 - b + b * (doc_length / avg_doc_length))
            score += idf * (numerator / denominator)
    
    return score

def search_documents(
    query: str,
    similarity_threshold: float = 0.15,  # Lowered for better recall
    filename_similarity_threshold: float = 0.7,
    include_full_document: bool = True,
    max_results: int = 20,
    min_relevance_score: float = 0.2,  # Lowered for better recall
    max_chunks_per_file: Optional[int] = None,
    filename_match_boost: float = 1.3,
    use_cache: bool = True,
    language: str = 'russian',
    batch_size: int = 100,
    max_chars_per_chunk: int = 1000,
    use_hybrid_search: bool = True,  # Enable hybrid semantic + keyword search
    bm25_weight: float = 0.3  # Weight for BM25 score in hybrid search
) -> Dict[str, Union[List[Document], Dict[str, any]]]:
    """
    Advanced hybrid document search combining semantic similarity and keyword matching.
    
    Args:
        query: The search query
        similarity_threshold: Minimum similarity score for semantic search results
        filename_similarity_threshold: Similarity threshold for filename matching
        include_full_document: If True, includes full document content when filename matches
        max_results: Maximum number of results to return
        min_relevance_score: Minimum score to include a result
        max_chunks_per_file: Maximum number of chunks to return per file
        filename_match_boost: Score multiplier for filename matches
        use_cache: Whether to use caching for queries
        use_hybrid_search: Enable hybrid semantic + BM25 keyword search
        bm25_weight: Weight for BM25 score (1 - bm25_weight is semantic weight)
        
    Returns:
        Dictionary with search results and statistics
    """
    logger = logging.getLogger(__name__)
    tracker = PerformanceTracker(f"search_documents('{query[:50]}...')", logger)
    
    # Preprocess query
    preprocessed_query = preprocess_query(query, language=language)
    if not preprocessed_query:
        return {
            'semantic_results': [],
            'filename_matches': {},
            'stats': {'error': 'Empty query after preprocessing'}
        }
    
    # Generate cache key
    cache_key = None
    if use_cache:
        cache_key = hashlib.md5(json.dumps({
            'query': preprocessed_query,
            'similarity_threshold': similarity_threshold,
            'filename_similarity_threshold': filename_similarity_threshold,
            'min_relevance_score': min_relevance_score,
            'max_results': max_results,
            'max_chunks_per_file': max_chunks_per_file,
            'filename_match_boost': filename_match_boost,
            'language': language
        }, sort_keys=True).encode()).hexdigest()
        
        # Check cache first
        if hasattr(search_documents, '_cache') and cache_key in search_documents._cache:
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return search_documents._cache[cache_key]
    
    # Initialize results
    results = {
        'semantic_results': [],
        'filename_matches': {},
        'stats': {
            'total_checked': 0,
            'filename_matches': 0,
            'semantic_matches': 0,
            'processing_time_ms': None,
            'query': query,
            'error': None,
            'cache_hit': False
        }
    }

    try:
        # Get query embedding with preprocessing
        tracker.start_operation("query_embedding")
        try:
            query_embedding = embedding_function.embed_query(preprocessed_query)
            query_embedding_np = np.array(query_embedding, dtype=np.float32)
            tracker.end_operation("query_embedding")
        except Exception as e:
            logger.error(f"Error generating query embedding: {str(e)}")
            results['stats']['error'] = f"Error generating query embedding: {str(e)}"
            return results

        # Get all documents with their embeddings in batches
        tracker.start_operation("get_all_documents")
        try:
            # Get total count first
            count = vectorstore._collection.count()
            if count == 0:
                return results
                
            # Process in batches to reduce memory usage
            batch_size = min(batch_size, max(100, count // 10))  # Adaptive batch size
            doc_embeddings = []
            metadatas = []
            documents = []
            
            for i in range(0, count, batch_size):
                batch = vectorstore._collection.get(
                    limit=batch_size,
                    offset=i,
                    include=['embeddings', 'metadatas', 'documents']
                )
                doc_embeddings.extend(batch['embeddings'])
                metadatas.extend(batch['metadatas'])
                documents.extend(batch['documents'])
                
            if not doc_embeddings:
                return results
                
            doc_embeddings_np = np.array(doc_embeddings, dtype=np.float32)
            tracker.end_operation("get_all_documents", 
                               f"Loaded {len(doc_embeddings_np)} documents in {count//batch_size + 1} batches")
        except Exception as e:
            logger.error(f"Error loading documents: {str(e)}")
            results['stats']['error'] = f"Error loading documents: {str(e)}"
            return results

        # Calculate similarities in batch
        tracker.start_operation("calculate_similarities")
        semantic_similarities = batch_cosine_similarity(query_embedding_np, doc_embeddings_np)
        tracker.end_operation("calculate_similarities")
        
        # Calculate BM25 scores if hybrid search is enabled
        bm25_scores = None
        if use_hybrid_search:
            tracker.start_operation("calculate_bm25")
            query_terms = query.lower().split()
            avg_doc_length = np.mean([len(doc.split()) for doc in documents])
            bm25_scores = np.array([
                calculate_bm25_score(query_terms, doc, avg_doc_length) 
                for doc in documents
            ])
            # Normalize BM25 scores to [0, 1]
            if bm25_scores.max() > 0:
                bm25_scores = bm25_scores / bm25_scores.max()
            tracker.end_operation("calculate_bm25")

        # Process documents
        tracker.start_operation("process_results")
        file_chunks = {}
        
        # Get all documents by using a condition that's always true
        all_docs = vectorstore.get(where={"filename": {"$ne": ""}})  # This will match all documents with a non-empty filename
        metadatas = all_docs.get('metadatas', [])
        
        # Get filename similar in batch
        filenames = [m.get('filename', '') for m in metadatas] if metadatas else []
        filename_similarities = np.array([_calculate_filename_similarity(query, f) for f in filenames]) if filenames else np.array([])
        
        # Combine semantic and BM25 scores if hybrid search is enabled
        if use_hybrid_search and bm25_scores is not None:
            # Hybrid score: weighted combination of semantic and keyword matching
            combined_scores = (1 - bm25_weight) * semantic_similarities + bm25_weight * bm25_scores
        else:
            combined_scores = semantic_similarities
        
        # Apply filename boost if we have documents
        if len(combined_scores) > 0 and len(filename_similarities) > 0:
            boosted_scores = np.where(
                filename_similarities >= filename_similarity_threshold,
                np.minimum(1.0, combined_scores * filename_match_boost),
                combined_scores
            )
        else:
            boosted_scores = combined_scores
        
        # Filter by minimum relevance
        relevant_indices = np.where(boosted_scores >= min_relevance_score)[0]
        results['stats']['total_checked'] = len(metadatas)
        
        # Process relevant documents
        for idx in relevant_indices:
            if idx < len(metadatas):  # Ensure we don't go out of bounds
                metadata = metadatas[idx]
                filename = metadata.get('filename', '')
                file_id = metadata.get('file_id', '')
                score = float(boosted_scores[idx])
            
            # Track chunks per file
            if file_id not in file_chunks:
                file_chunks[file_id] = {
                    'chunks': [],
                    'filename': filename,
                    'metadata': metadata,
                    'best_score': 0.0
                }
            
            # Add chunk
            chunk_data = {
                'content': all_docs['documents'][idx],
                'score': score,
                'metadata': metadata
            }
            file_chunks[file_id]['chunks'].append(chunk_data)
            file_chunks[file_id]['best_score'] = max(file_chunks[file_id]['best_score'], score)
            
            # Track filename matches
            if filename_similarities[idx] >= filename_similarity_threshold:
                if filename not in results['filename_matches']:
                    results['stats']['filename_matches'] += 1
                    results['filename_matches'][filename] = {
                        'chunks': [],
                        'metadata': metadata,
                        'total_chunks': 0
                    }
                results['filename_matches'][filename]['chunks'].append(chunk_data)
        
        # Sort and filter results
        sorted_files = sorted(
            file_chunks.values(),
            key=lambda x: x['best_score'],
            reverse=True
        )
        
        # Process top chunks
        semantic_results = []
        for file_data in sorted_files:
            # Sort chunks by score in descending order
            sorted_chunks = sorted(
                file_data['chunks'],
                key=lambda x: x['score'],
                reverse=True
            )
            
            # Filter chunks by minimum score and apply max_chunks_per_file if specified
            relevant_chunks = []
            for chunk in sorted_chunks:
                if chunk['score'] >= min_relevance_score:
                    relevant_chunks.append(chunk)
                    if max_chunks_per_file and len(relevant_chunks) >= max_chunks_per_file:
                        break
            
            # Add relevant chunks to results with content length limit
            for chunk in relevant_chunks:
                # Limit chunk content length
                content = chunk['content']
                if len(content) > max_chars_per_chunk:
                    # Try to find a good truncation point near the limit
                    truncate_at = content.rfind(' ', 0, max_chars_per_chunk)
                    if truncate_at > 0:  # Found a space to truncate at
                        content = content[:truncate_at] + '...'
                    else:
                        content = content[:max_chars_per_chunk] + '...'
                
                doc = Document(
                    page_content=content,
                    metadata={
                        **chunk['metadata'],
                        'relevance_score': float(chunk['score']),  # Add score to metadata
                        'is_filename_match': chunk.get('is_filename_match', False)
                    }
                )
                semantic_results.append((doc, chunk['score']))
                results['stats']['semantic_matches'] += 1
                
                if len(semantic_results) >= max_results:
                    break
            
            if len(semantic_results) >= max_results:
                break
        
        # Sort and store results
        semantic_results.sort(key=lambda x: x[1], reverse=True)
        
        # Group results by file and add full file content to each
        file_content_cache = {}  # Cache to avoid retrieving same file multiple times
        enhanced_results = []
        
        for doc, score in semantic_results:
            file_id = doc.metadata.get('file_id')
            filename = doc.metadata.get('filename')
            source = doc.metadata.get('source')
            
            # Create a cache key
            cache_key = f"{file_id}_{filename}_{source}"
            
            # Get full file content (use cache if available)
            if cache_key not in file_content_cache:
                if file_id or filename or source:
                    file_data = get_full_file_content(
                        file_id=file_id,
                        filename=filename,
                        source_path=source
                    )
                    if file_data and file_data.get('content'):
                        file_content_cache[cache_key] = file_data['content']
                    else:
                        file_content_cache[cache_key] = None
                else:
                    file_content_cache[cache_key] = None
            
            # Update document metadata with full file content
            if file_content_cache[cache_key]:
                doc.metadata['full_file_content'] = file_content_cache[cache_key]
            
            enhanced_results.append(doc)
        
        results['semantic_results'] = enhanced_results
        
        # Update filename matches with limited chunks
        if include_full_document:
            for filename, match_data in results['filename_matches'].items():
                match_data['chunks'].sort(key=lambda x: x['score'], reverse=True)
                match_data['chunks'] = match_data['chunks'][:max_chunks_per_file]
                match_data['total_chunks'] = len(match_data['chunks'])
        
        tracker.end_operation("process_results")
        
        # Cache the results
        if use_cache and cache_key:
            if not hasattr(search_documents, '_cache'):
                search_documents._cache = TTLCache(maxsize=1000, ttl=300)  # 5 min cache
            search_documents._cache[cache_key] = results
            results['stats']['cache_hit'] = True
        
        tracker.log_summary()
        
    except Exception as e:
        logger.error(f"Error in search_documents: {str(e)}", exc_info=True)
        results['stats']['error'] = str(e)
    
    return results

def get_full_file_content(file_id: int = None, filename: str = None, source_path: str = None) -> Dict[str, Any]:
    """
    Retrieve the full content of a file from the database or filesystem.
    
    Args:
        file_id: Database ID of the file
        filename: Name of the file
        source_path: Direct path to the file
        
    Returns:
        Dictionary with file content and metadata
    """
    import sqlite3
    
    result = {
        'content': None,
        'filename': None,
        'file_id': None,
        'metadata': {},
        'error': None
    }
    
    try:
        # Try to get from source path first
        if source_path and os.path.exists(source_path):
            with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
                result['content'] = f.read()
                result['filename'] = os.path.basename(source_path)
                result['metadata']['source'] = source_path
                result['metadata']['size'] = os.path.getsize(source_path)
                return result
        
        # Try to get from database
        if file_id or filename:
            conn = sqlite3.connect("rag_app.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if file_id:
                cursor.execute("SELECT id, filename, content FROM document_store WHERE id = ?", (file_id,))
            elif filename:
                cursor.execute("SELECT id, filename, content FROM document_store WHERE filename = ?", (filename,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                result['file_id'] = row['id']
                result['filename'] = row['filename']
                # Decode binary content
                try:
                    result['content'] = row['content'].decode('utf-8')
                except:
                    result['content'] = row['content'].decode('utf-8', errors='ignore')
                result['metadata']['from_database'] = True
                return result
            else:
                result['error'] = f"File not found in database (file_id={file_id}, filename={filename})"
        else:
            result['error'] = "No file identifier provided (need file_id, filename, or source_path)"
            
    except Exception as e:
        result['error'] = f"Error retrieving file content: {str(e)}"
    
    return result

def search_with_full_context(
    query: str,
    include_full_file: bool = True,
    relevance_threshold: float = 0.5,
    **search_kwargs
) -> Dict[str, Any]:
    """
    Enhanced search that includes full file content for highly relevant results.
    
    Args:
        query: Search query
        include_full_file: If True, include full file content for top results
        relevance_threshold: Minimum score to include full file content
        **search_kwargs: Additional arguments passed to search_documents
        
    Returns:
        Search results with full file content for top matches
    """
    # Perform standard search
    search_results = search_documents(query, **search_kwargs)
    
    if not include_full_file:
        return search_results
    
    # Add full file content for highly relevant results
    enhanced_results = []
    
    for doc in search_results.get('semantic_results', []):
        result_item = {
            'chunk': doc.page_content,
            'metadata': doc.metadata,
            'relevance_score': doc.metadata.get('relevance_score', 0),
            'full_file_content': None
        }
        
        # If relevance is high enough, get full file content
        if result_item['relevance_score'] >= relevance_threshold:
            file_id = doc.metadata.get('file_id')
            filename = doc.metadata.get('filename')
            source = doc.metadata.get('source')
            
            file_content = get_full_file_content(
                file_id=file_id,
                filename=filename,
                source_path=source
            )
            
            if file_content['content']:
                result_item['full_file_content'] = file_content['content']
                result_item['full_file_metadata'] = file_content['metadata']
        
        enhanced_results.append(result_item)
    
    return {
        'results': enhanced_results,
        'stats': search_results.get('stats', {}),
        'total_results': len(enhanced_results),
        'results_with_full_content': sum(1 for r in enhanced_results if r['full_file_content'])
    }

def generate_citation(metadata: Dict[str, Any], citation_style: str = "inline") -> str:
    """
    Generate a citation string for a document.
    
    Args:
        metadata: Document metadata containing filename, source, etc.
        citation_style: Style of citation ("inline", "footnote", "academic")
        
    Returns:
        Formatted citation string
    """
    filename = metadata.get('filename', 'Unknown')
    source = metadata.get('source', '')
    file_type = metadata.get('file_type', '')
    created_at = metadata.get('created_at')
    
    # Format timestamp if available
    timestamp = ""
    if created_at:
        from datetime import datetime
        try:
            dt = datetime.fromtimestamp(created_at)
            timestamp = dt.strftime('%Y-%m-%d')
        except:
            pass
    
    if citation_style == "inline":
        # Simple inline citation: [filename]
        return f"[{filename}]"
    
    elif citation_style == "footnote":
        # Footnote style: Source: filename (path)
        if source:
            return f"Source: {filename} ({source})"
        return f"Source: {filename}"
    
    elif citation_style == "academic":
        # Academic style with more details
        parts = [filename]
        if file_type:
            parts.append(f"Type: {file_type}")
        if timestamp:
            parts.append(f"Date: {timestamp}")
        if source:
            parts.append(f"Path: {source}")
        return " | ".join(parts)
    
    else:
        return f"[{filename}]"

def format_search_results_with_citations(
    search_results: Dict[str, Any],
    citation_style: str = "inline",
    include_relevance_scores: bool = True
) -> str:
    """
    Format search results with citations for AI consumption.
    
    Args:
        search_results: Results from search_documents or search_with_full_context
        citation_style: Citation format ("inline", "footnote", "academic")
        include_relevance_scores: Whether to include relevance scores
        
    Returns:
        Formatted string with citations ready for AI
    """
    formatted_parts = []
    
    # Handle both regular search results and full context results
    results = search_results.get('results', search_results.get('semantic_results', []))
    
    for idx, result in enumerate(results, 1):
        # Extract data based on result type
        if isinstance(result, dict):
            # Full context result
            chunk = result.get('chunk', '')
            metadata = result.get('metadata', {})
            score = result.get('relevance_score', 0)
            full_content = result.get('full_file_content')
        else:
            # Regular Document result
            chunk = result.page_content
            metadata = result.metadata
            score = metadata.get('relevance_score', 0)
            full_content = None
        
        # Generate citation
        citation = generate_citation(metadata, citation_style)
        
        # Format the result
        result_text = f"\n{'='*70}\nResult {idx}"
        
        if include_relevance_scores:
            result_text += f" (Relevance: {score:.2f})"
        
        result_text += f"\n{'='*70}\n"
        result_text += f"Citation: {citation}\n\n"
        
        # Always show both chunk and full content if available
        result_text += f"Relevant Excerpt:\n{'-'*70}\n{chunk}\n\n"
        
        if full_content:
            result_text += f"Complete Source Document:\n{'-'*70}\n{full_content}\n"
        elif metadata.get('full_file_content'):
            # Check if full content is in metadata
            result_text += f"Complete Source Document:\n{'-'*70}\n{metadata['full_file_content']}\n"
        
        formatted_parts.append(result_text)
    
    # Add summary
    summary = f"\n{'='*70}\n"
    summary += f"SEARCH SUMMARY\n"
    summary += f"{'='*70}\n"
    summary += f"Total results: {len(results)}\n"
    
    if 'results_with_full_content' in search_results:
        summary += f"Results with full content: {search_results['results_with_full_content']}\n"
    
    stats = search_results.get('stats', {})
    if stats:
        summary += f"Total documents checked: {stats.get('total_checked', 'N/A')}\n"
    
    summary += f"\nCitation Style: {citation_style}\n"
    summary += f"{'='*70}\n"
    
    return summary + "\n".join(formatted_parts)

def create_ai_prompt_with_citations(
    query: str,
    search_results: Dict[str, Any],
    citation_style: str = "inline",
    instruction: str = None
) -> str:
    """
    Create a complete prompt for AI with search results and citations.
    
    Args:
        query: Original search query
        search_results: Search results with documents
        citation_style: Citation format
        instruction: Custom instruction for AI (optional)
        
    Returns:
        Complete prompt ready for AI
    """
    default_instruction = """You are a helpful AI assistant. Answer the user's question based ONLY on the provided documents.

CRITICAL CITATION REQUIREMENTS:
1. You MUST cite the source file for EVERY piece of information
2. Use the format [filename] immediately after each statement
3. Start your response by listing which files you are using
4. End your response with "Sources used:" and list all files
5. If information is not in the provided documents, say "Not found in provided sources"
6. NEVER provide information without a citation

Example format:
"Machine learning is a subset of AI [ml_guide.pdf]. It uses algorithms to learn from data [ml_guide.pdf]."

Sources used:
- [ml_guide.pdf]"""

    instruction = instruction or default_instruction
    
    formatted_results = format_search_results_with_citations(
        search_results,
        citation_style=citation_style,
        include_relevance_scores=True
    )
    
    prompt = f"""{'='*70}
AI ASSISTANT PROMPT
{'='*70}

INSTRUCTION:
{instruction}

USER QUERY:
{query}

PROVIDED SOURCES:
{formatted_results}

{'='*70}
YOUR RESPONSE:
{'='*70}

IMPORTANT: You MUST follow this format:

Files used: [list all files you reference]

[Your answer with citations after each statement]

Sources used:
- [filename1]
- [filename2]

Now provide your response:
"""
    
    return prompt
