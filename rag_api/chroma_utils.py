import os
import logging
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, UnstructuredHTMLLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
try:
    from langchain_huggingface import HuggingFaceEmbeddings as SentenceTransformerEmbeddings
except ImportError:
    from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_chroma import Chroma
from typing import List, Dict, Tuple, Optional, Union
from langchain_core.documents import Document
from difflib import SequenceMatcher
import numpy as np

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,  # Increased chunk size for more context
    chunk_overlap=300,  # Increased overlap to maintain context between chunks
    length_function=len,
    separators=["\n\n", "\n", " ", ""]  # More granular separation
)

embedding_function = SentenceTransformerEmbeddings(
    model_name="Qwen/Qwen3-Embedding-0.6B",  # More capable model for better embeddings
    model_kwargs={"device": "cpu"}
)

# Create a fresh Chroma instance with explicit dimensions
vectorstore = Chroma(
    persist_directory="./chroma_db",
    collection_name="documents_qwen",  # New collection name to force recreation
    embedding_function=embedding_function,
    collection_metadata={"hnsw:space": "cosine"}  # Add metadata to ensure new collection
)

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

def preprocess_text(text: str) -> str:
    """Preprocess text to improve quality of embeddings"""
    import re
    
    # Remove multiple newlines and whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters but keep essential punctuation
    text = re.sub(r'[^\w\s.,!?;:\-\'\"%()\[\]{}]', ' ', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text.strip()

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
        print(f"Error deleting document with file_id {file_id} from Chroma: {str(e)}")
        return False


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

def search_documents(
    query: str,
    similarity_threshold: float = 0.1,  # Lower threshold to get more chunks
    filename_similarity_threshold: float = 0.5,  # Increased threshold for more precise filename matching
    include_full_document: bool = True,
    max_results: int = 20,  # Maximum total results to return
    check_requirements_first: bool = True,
    min_relevance_score: float = 0.1,  # Lower threshold to include more potentially relevant chunks
    max_chunks_per_file: int = 5,  # Increased number of chunks to return per file
    filename_match_boost: float = 2.0  # Boost score for filename matches
) -> Dict[str, Union[List[Document], Dict[str, any]]]:
    """
    Enhanced document search with improved filename matching and chunk retrieval.
    
    Args:
        query: The search query
        similarity_threshold: Minimum similarity score (0-1) for semantic search results
        filename_similarity_threshold: Similarity threshold for filename matching (0-1)
        include_full_document: If True, includes full document content when filename matches
        max_results: Maximum number of results to return
        check_requirements_first: If True, performs lightweight checks first
        min_relevance_score: Minimum score to include a result
        max_chunks_per_file: Maximum number of chunks to return per file
        filename_match_boost: Score multiplier for filename matches
        
    Returns:
        Dictionary with search results:
        - 'semantic_results': List of matching document chunks with scores and metadata
        - 'filename_matches': Dict of {filename: {'chunks': List[dict], 'metadata': dict, 'total_chunks': int}}
        - 'stats': Dictionary with search statistics
    """
    import time
    start_time = time.time()
    logger = logging.getLogger(__name__)
    
    # Ensure we're using the correct embedding function
    if not hasattr(vectorstore, '_embedding_function'):
        logger.warning("No embedding function found for vectorstore, using default")
        vectorstore._embedding_function = SentenceTransformerEmbeddings(
            model_name="Qwen/Qwen3-Embedding-0.6B",
            model_kwargs={"device": "cpu"}
        )
    
    # Initialize results
    results = {
        'semantic_results': [],
        'filename_matches': {},
        'stats': {
            'total_checked': 0,
            'filename_matches': 0,
            'semantic_matches': 0,
            'processing_time_ms': None,
            'query': query,  # Include original query in stats
            'error': None
        }
    }
    
    try:
        # First, perform a semantic search
        query_embedding = vectorstore._embedding_function.embed_query(query)
        
        # Get all documents with their embeddings
        collection = vectorstore._collection.get(include=['embeddings', 'metadatas', 'documents'])
        
        # Track seen files and their chunks
        file_chunks = {}
        
        # Process each document
        for idx, (doc_embedding, metadata, content) in enumerate(zip(
            collection['embeddings'], 
            collection['metadatas'], 
            collection['documents']
        )):
            results['stats']['total_checked'] += 1
            filename = metadata.get('filename', '')
            file_id = metadata.get('file_id', '')
            
            # Calculate filename similarity
            filename_similarity = _calculate_filename_similarity(query, filename)
            
            # Calculate semantic similarity
            semantic_similarity = np.dot(query_embedding, doc_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
            )
            
            # Boost score for filename matches
            if filename_similarity >= filename_similarity_threshold:
                semantic_similarity = min(1.0, semantic_similarity * filename_match_boost)
            
            # Skip if below minimum relevance
            if semantic_similarity < min_relevance_score:
                continue
                
            # Create document object
            doc = Document(
                page_content=content,
                metadata=metadata
            )
            
            # Track chunks per file
            if file_id not in file_chunks:
                file_chunks[file_id] = {
                    'chunks': [],
                    'filename': filename,
                    'metadata': metadata,
                    'best_score': 0
                }
            
            # Store chunk with score
            chunk_data = {
                'content': content,
                'score': float(semantic_similarity),
                'metadata': metadata
            }
            
            file_chunks[file_id]['chunks'].append(chunk_data)
            file_chunks[file_id]['best_score'] = max(
                file_chunks[file_id]['best_score'], 
                semantic_similarity
            )
            
            # Track filename matches
            if filename_similarity >= filename_similarity_threshold:
                if filename not in results['filename_matches']:
                    results['stats']['filename_matches'] += 1
                    results['filename_matches'][filename] = {
                        'chunks': [],
                        'metadata': metadata,
                        'total_chunks': 0
                    }
                
                # Add to filename matches
                results['filename_matches'][filename]['chunks'].append(chunk_data)
                results['filename_matches'][filename]['total_chunks'] += 1
        
        # Process file chunks to get top results
        sorted_files = sorted(
            file_chunks.values(), 
            key=lambda x: x['best_score'], 
            reverse=True
        )
        
        # Add top chunks to results
        for file_data in sorted_files:
            # Sort chunks by score
            sorted_chunks = sorted(
                file_data['chunks'], 
                key=lambda x: x['score'], 
                reverse=True
            )
            
            # Take top N chunks per file
            top_chunks = sorted_chunks[:max_chunks_per_file]
            
            # Add to semantic results
            for chunk in top_chunks:
                doc = Document(
                    page_content=chunk['content'],
                    metadata=chunk['metadata']
                )
                results['semantic_results'].append((doc, chunk['score']))
                results['stats']['semantic_matches'] += 1
                
                # Limit total results
                if len(results['semantic_results']) >= max_results:
                    break
            
            if len(results['semantic_results']) >= max_results:
                break
        
        # Sort semantic results by score
        results['semantic_results'] = sorted(
            results['semantic_results'],
            key=lambda x: x[1],
            reverse=True
        )
        
        # Convert to list of documents for compatibility
        semantic_docs = [doc for doc, _ in results['semantic_results']]
        results['semantic_results'] = semantic_docs
        
        # Process filename matches to include full document if requested
        if include_full_document:
            for filename, match_data in results['filename_matches'].items():
                # Sort chunks by score and take top N
                sorted_chunks = sorted(
                    match_data['chunks'],
                    key=lambda x: x['score'],
                    reverse=True
                )[:max_chunks_per_file]
                
                # Update with sorted and limited chunks
                match_data['chunks'] = sorted_chunks
                match_data['total_chunks'] = len(sorted_chunks)
        
        # Update stats
        results['stats']['processing_time_ms'] = int((time.time() - start_time) * 1000)
        
    except Exception as e:
        logger.error(f"Error in search_documents: {str(e)}", exc_info=True)
        results['stats']['error'] = str(e)
    
    return results
