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
from langchain_text_splitters import RecursiveCharacterTextSplitter
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

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,  # Increased chunk size for more context
    chunk_overlap=300,  # Increased overlap to maintain context between chunks
    length_function=len,
    separators=["\n\n", "\n", " ", ""]  # More granular separation
)

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

def load_and_split_document(file_path: str, filename: str) -> List[Document]:
    """Load and split document with enhanced metadata and preprocessing"""
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
            content = preprocess_text(content)
            
            document = Document(
                page_content=content, 
                metadata={
                    "source": file_path,
                    "filename": filename,
                    "file_type": os.path.splitext(filename)[1],
                    "created_at": os.path.getctime(file_path),
                    "modified_at": os.path.getmtime(file_path)
                }
            )
            return text_splitter.split_documents([document])
        else:
            raise ValueError(f"Unsupported file type: {file_path}")

        documents = loader.load()
        
        # Enhanced metadata for all documents
        for doc in documents:
            doc.metadata.update({
                "filename": filename,
                "file_type": os.path.splitext(filename)[1],
                "created_at": os.path.getctime(file_path),
                "modified_at": os.path.getmtime(file_path)
            })
            
            # Preprocess content to improve quality
            doc.page_content = preprocess_text(doc.page_content)
            
        return text_splitter.split_documents(documents)
        
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
    """Calculate cosine similarity in batch for better performance."""
    query_norm = np.linalg.norm(query_embedding)
    doc_norms = np.linalg.norm(doc_embeddings, axis=1)
    dot_products = np.dot(doc_embeddings, query_embedding)
    return dot_products / (doc_norms * query_norm + 1e-10)

def search_documents(
    query: str,
    similarity_threshold: float = 0.2,  # Increased from 0.1 to filter out weaker matches
    filename_similarity_threshold: float = 0.7,
    include_full_document: bool = True,
    max_results: int = 20,
    min_relevance_score: float = 0.3,  # Increased from 0.1 to show only more relevant results
    max_chunks_per_file: Optional[int] = None,  # If None, no limit on chunks per file
    filename_match_boost: float = 1.5,  # Reduced from 2.0 to balance between filename and content relevance
    use_cache: bool = True,
    language: str = 'russian',
    batch_size: int = 100,
    max_chars_per_chunk: int = 1000  # Maximum characters per chunk to return
) -> Dict[str, Union[List[Document], Dict[str, any]]]:
    """
    Optimized document search with vectorized operations and caching.
    
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

        # Process documents
        tracker.start_operation("process_results")
        file_chunks = {}
        
        # Get all documents by using a condition that's always true
        all_docs = vectorstore.get(where={"filename": {"$ne": ""}})  # This will match all documents with a non-empty filename
        metadatas = all_docs.get('metadatas', [])
        
        # Get filename similar in batch
        filenames = [m.get('filename', '') for m in metadatas] if metadatas else []
        filename_similarities = np.array([_calculate_filename_similarity(query, f) for f in filenames]) if filenames else np.array([])
        
        # Apply filename boost if we have documents
        if len(semantic_similarities) > 0 and len(filename_similarities) > 0:
            boosted_scores = np.where(
                filename_similarities >= filename_similarity_threshold,
                np.minimum(1.0, semantic_similarities * filename_match_boost),
                semantic_similarities
            )
        else:
            boosted_scores = semantic_similarities
        
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
        results['semantic_results'] = [doc for doc, _ in semantic_results]
        
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
