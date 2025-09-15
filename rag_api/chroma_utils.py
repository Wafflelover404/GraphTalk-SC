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
    filename_similarity_threshold: float = 0.3,  # Lower threshold for filename matching
    include_full_document: bool = True,
    max_results: int = 20,  # Increased to allow for multiple chunks
    check_requirements_first: bool = True,
    min_relevance_score: float = 0.1,  # Lower threshold to include more potentially relevant chunks
    max_chunks_per_file: int = 3  # Maximum number of chunks to return per file
) -> Dict[str, Union[List[Document], Dict[str, any]]]:
    """
    Windsurf-like document search that first checks if files meet requirements
    before performing expensive operations.
    
    Args:
        query: The search query
        similarity_threshold: Minimum similarity score (0-1) for semantic search results
        filename_similarity_threshold: Minimum similarity score (0-1) for filename matching
        include_full_document: If True, includes full document content when filename matches
        max_results: Maximum number of results to return
        check_requirements_first: If True, performs lightweight checks before full processing
        
    Returns:
        Dictionary with search results:
        - 'semantic_results': List of matching document chunks with scores and metadata
        - 'filename_matches': Dict of {filename: {'content': str, 'similarity': float, 'metadata': dict}}
        - 'stats': Dictionary with search statistics
    """
    logger = logging.getLogger(__name__)
    results = {
        'semantic_results': [],
        'filename_matches': {},
        'stats': {
            'total_checked': 0,
            'met_requirements': 0,
            'filename_matches': 0,
            'semantic_matches': 0,
            'processing_time_ms': None,
            'error': None
        }
    }
    
    # Ensure we're using the correct embedding function
    if not hasattr(vectorstore, '_embedding_function'):
        logger.warning("No embedding function found for vectorstore, using default")
        vectorstore._embedding_function = SentenceTransformerEmbeddings(
            model_name="Qwen/Qwen3-Embedding-0.6B",
            model_kwargs={"device": "cpu"}
        )
    
    import time
    start_time = time.time()
    
    try:
        # Get all documents metadata first for requirement checking
        logger.info("Fetching all documents from vectorstore...")
        all_docs = vectorstore.get()
        total_docs = len(all_docs.get('ids', []))
        logger.info(f"Total documents in vectorstore: {total_docs}")
        
        if not all_docs.get('ids') or total_docs == 0:
            logger.warning("No documents found in the vectorstore")
            results['stats']['error'] = 'No documents in vectorstore'
            return results
            
        logger.info("Generating query embedding...")
        try:
            query_embedding = embedding_function.embed_query(query)
            if not query_embedding or len(query_embedding) == 0:
                raise ValueError("Empty query embedding generated")
            logger.info(f"Query embedding generated with dimension: {len(query_embedding)}")
        except Exception as e:
            logger.error(f"Error generating query embedding: {str(e)}")
            results['stats']['error'] = f'Error generating query embedding: {str(e)}'
            return results
        
        # 1. First, perform a semantic search to find all relevant chunks
        logger.info("Querying vectorstore...")
        try:
            all_chunks = vectorstore._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(50, len(all_docs.get('ids', []))),
                include=['documents', 'metadatas', 'distances']
            )
            
            # Verify the response structure
            if not all_chunks or 'ids' not in all_chunks or not all_chunks['ids']:
                logger.warning("No results returned from vectorstore query")
                results['stats']['error'] = 'No results from vectorstore query'
                return results
                
            # Group chunks by file
            file_chunks = {}
            
            # Log the number of chunks found
            num_chunks = len(all_chunks.get('ids', [[]])[0])
            logger.info(f"Found {num_chunks} chunks from vectorstore")
            
            if num_chunks == 0:
                logger.warning("No chunks found in vectorstore query results")
                results['stats']['error'] = 'No chunks found in vectorstore query results'
                return results
                
        except Exception as e:
            logger.error(f"Error querying vectorstore: {str(e)}")
            results['stats']['error'] = f'Error querying vectorstore: {str(e)}'
            return results
        
        chunks_data = zip(
            all_chunks.get('ids', [[]])[0],
            all_chunks.get('metadatas', [[]])[0],
            all_chunks.get('documents', [[]])[0],
            all_chunks.get('distances', [[1.0]])[0]
        )
        
        for i, (doc_id, metadata, content, distance) in enumerate(chunks_data):
            if not content or not isinstance(metadata, dict):
                continue
                
            filename = metadata.get('filename', 'untitled')
            similarity = 1.0 - min(max(float(distance), 0.0), 1.0)
            
            if similarity < min_relevance_score:
                continue
                
            if filename not in file_chunks:
                file_chunks[filename] = []
                
            file_chunks[filename].append({
                'content': content,
                'similarity': similarity,
                'metadata': metadata,
                'distance': distance
            })
        
        # Sort chunks within each file by similarity (highest first)
        for filename in file_chunks:
            file_chunks[filename].sort(key=lambda x: x['similarity'], reverse=True)
        
        # 2. Process the chunks, keeping the best ones per file
        processed_files = set()
        
        # First, add filename matches if they exist
        for filename, chunks in file_chunks.items():
            if not chunks:
                continue
                
            # Check if this is a filename match
            filename_similarity = _calculate_filename_similarity(query, filename)
            is_filename_match = filename_similarity >= filename_similarity_threshold
            
            if is_filename_match and include_full_document:
                # For filename matches, include all relevant chunks
                relevant_chunks = chunks[:max_chunks_per_file]
                full_content = "\n\n".join(chunk['content'] for chunk in relevant_chunks)
                
                # Calculate average similarity for the file
                avg_similarity = sum(chunk['similarity'] for chunk in relevant_chunks) / len(relevant_chunks)
                
                results['filename_matches'][filename] = {
                    'content': full_content,
                    'similarity': max(filename_similarity, avg_similarity),
                    'metadata': relevant_chunks[0]['metadata'],
                    'chunk_count': len(relevant_chunks)
                }
                processed_files.add(filename)
        
        # Then add semantic matches from files that weren't filename matches
        for filename, chunks in file_chunks.items():
            if filename in processed_files or not chunks:
                continue
                
            # Take top N chunks per file for semantic matches
            relevant_chunks = chunks[:max_chunks_per_file]
            
            # Add each chunk as a separate result
            for chunk in relevant_chunks:
                if chunk['similarity'] >= similarity_threshold:
                    doc_obj = Document(
                        page_content=chunk['content'],
                        metadata=chunk['metadata'].copy()
                    )
                    doc_obj.metadata.update({
                        'similarity_score': chunk['similarity'],
                        'filename': filename,
                        'is_filename_match': False
                    })
                    results['semantic_results'].append(doc_obj)
                    results['stats']['semantic_matches'] += 1
        
        # Sort and limit semantic results
        results['semantic_results'].sort(
            key=lambda x: x.metadata.get('similarity_score', 0),
            reverse=True
        )
        
        # Apply max_results to the combined results
        total_results = len(results['semantic_results']) + len(results['filename_matches'])
        if total_results > max_results:
            # If we have too many results, prioritize filename matches
            if results['filename_matches']:
                keep_filename = min(len(results['filename_matches']), max_results // 2)
                results['filename_matches'] = dict(
                    sorted(
                        results['filename_matches'].items(),
                        key=lambda x: x[1]['similarity'],
                        reverse=True
                    )[:keep_filename]
                )
                
                # Take remaining slots from semantic results
                remaining = max_results - len(results['filename_matches'])
                results['semantic_results'] = results['semantic_results'][:remaining]
            else:
                results['semantic_results'] = results['semantic_results'][:max_results]
        
        # Update stats
        results['stats'].update({
            'total_files_processed': len(file_chunks),
            'files_with_matches': len(processed_files),
            'total_chunks_processed': sum(len(chunks) for chunks in file_chunks.values()),
            'total_matching_chunks': len(results['semantic_results']) + sum(
                match.get('chunk_count', 1) for match in results['filename_matches'].values()
            )
        })
        
        # Log the final results
        results['stats']['processing_time_ms'] = int((time.time() - start_time) * 1000)
        logger.info(f"Search completed in {results['stats']['processing_time_ms']}ms")
        logger.info(f"Total semantic matches: {len(results['semantic_results'])}")
        logger.info(f"Total filename matches: {len(results['filename_matches'])}")
        
        # If no results, log some debug info
        if not results['semantic_results'] and not results['filename_matches']:
            logger.warning("No search results found. Check if documents are properly indexed.")
            logger.debug(f"Search parameters: {locals()}")
            
        return results
        
    except Exception as e:
        print(f"Error during search: {str(e)}")
        return results
        return results
        
    except Exception as e:
        print(f"Error during search: {str(e)}")
        return results
