import os
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
    similarity_threshold: float = 0.7,
    filename_similarity_threshold: float = 0.7,
    include_full_document: bool = True,
    max_results: int = 10,
    check_requirements_first: bool = True
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
    results = {
        'semantic_results': [],
        'filename_matches': {},
        'stats': {
            'total_checked': 0,
            'met_requirements': 0,
            'filename_matches': 0,
            'semantic_matches': 0,
            'processing_time_ms': None
        }
    }
    
    import time
    start_time = time.time()
    
    try:
        # Get all documents metadata first for requirement checking
        all_docs = vectorstore.get()
        
        # 1. First pass: Check which documents meet our requirements
        candidate_docs = []
        
        for i, metadata in enumerate(all_docs.get('metadatas', [])):
            results['stats']['total_checked'] += 1
            
            # Check if document meets our requirements
            meets_reqs, similarity, is_filename_match = _meets_search_requirements(
                query, metadata, filename_similarity_threshold
            )
            
            if meets_reqs:
                results['stats']['met_requirements'] += 1
                if is_filename_match:
                    results['stats']['filename_matches'] += 1
                candidate_docs.append((i, metadata, similarity, is_filename_match))
        
        # 2. Process only the documents that met our requirements
        processed_files = set()
        
        for doc_idx, metadata, similarity, is_filename_match in candidate_docs:
            if len(results['semantic_results']) >= max_results and \
               len(results['filename_matches']) >= max_results:
                break
                
            file_id = metadata.get('file_id')
            filename = metadata.get('filename')
            
            # Skip if we've already processed this file
            if filename in processed_files:
                continue
                
            # If it's a filename match and we want full document
            if is_filename_match and include_full_document and filename:
                # Get all chunks for this file
                file_chunks = vectorstore.get(where={"filename": filename})
                if file_chunks and 'documents' in file_chunks:
                    # Combine all chunks for this file
                    full_content = "\n\n".join(
                        chunk for chunk in file_chunks['documents'] 
                        if chunk and isinstance(chunk, str)
                    )
                    results['filename_matches'][filename] = {
                        'content': full_content,
                        'similarity': similarity,
                        'metadata': metadata
                    }
                    processed_files.add(filename)
            
            # For semantic search, process individual chunks
            if not is_filename_match or not include_full_document:
                doc_id = all_docs['ids'][doc_idx]
                doc = vectorstore._collection.get(ids=[doc_id], include=['documents', 'metadatas'])
                if doc and 'documents' in doc and doc['documents']:
                    content = doc['documents'][0]
                    if content:
                        doc_obj = Document(
                            page_content=content,
                            metadata=metadata.copy()
                        )
                        doc_obj.metadata['similarity_score'] = similarity
                        results['semantic_results'].append(doc_obj)
                        results['stats']['semantic_matches'] += 1
        
        # Sort and limit results
        results['semantic_results'].sort(
            key=lambda x: x.metadata.get('similarity_score', 0),
            reverse=True
        )
        results['semantic_results'] = results['semantic_results'][:max_results]
        
        # Convert filename matches to list and sort by similarity
        sorted_matches = sorted(
            results['filename_matches'].items(),
            key=lambda x: x[1]['similarity'],
            reverse=True
        )
        results['filename_matches'] = dict(sorted_matches[:max_results])
        
        # Update processing time
        results['stats']['processing_time_ms'] = (time.time() - start_time) * 1000
        
        # Sort results by similarity score (highest first)
        if results['semantic_results']:
            results['semantic_results'].sort(
                key=lambda x: x.metadata.get('similarity', 0),
                reverse=True
            )
        
        return results
        
    except Exception as e:
        print(f"Error during search: {str(e)}")
        return results
