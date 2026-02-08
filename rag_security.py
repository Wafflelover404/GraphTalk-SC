"""
RAG Security Module
Handles filtering RAG responses based on user file access permissions
"""

import sys
import os
from typing import List, Optional, Dict, Any
import logging
import uuid

# Add rag_api to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'rag_api'))

from userdb import get_user_allowed_filenames, check_file_access

# Import chroma_utils components with explicit path handling
try:
    import rag_api.chroma_utils as chroma_utils
    vectorstore = chroma_utils.vectorstore
except (ImportError, NameError, AttributeError) as e:
    print(f"Warning: Could not import vectorstore: {e}")
    vectorstore = None
    chroma_utils = None

from typing import List, Dict, Any
import os
from rag_api.timing_utils import Timer, PerformanceTracker, time_block

logger = logging.getLogger(__name__)

async def get_relevant_files_for_query(username: str, query: str, k: int = 20) -> List[Dict[str, Any]]:
    """
    Get list of relevant files and chunks for a query that the user has access to.
    Uses Elasticsearch for search (semantic + fulltext hybrid).
    """
    logger = logging.getLogger(__name__)
    tracker = PerformanceTracker(f"get_relevant_files_for_query('{username}', '{query[:50]}...')", logger)

    try:
        from rag_api.search_backend import search_documents

        # Get user's file access permissions
        tracker.start_operation("get_user_permissions")
        # Returns None for admins (full access) or a list of allowed files
        allowed_files = await get_user_allowed_filenames(username)
        tracker.end_operation("get_user_permissions")

        # Normalize filenames for comparison
        def normalize_filename(name: str) -> str:
            if not name:
                return ''
            try:
                # Handle different path formats (both forward and backslashes)
                name = name.replace('\\', '/')
                # Get just the filename without path
                base = os.path.basename(name)
                # Convert to lowercase for case-insensitive comparison
                normalized = base.lower()
                # Remove any URL parameters or fragments
                normalized = normalized.split('?')[0].split('#')[0]
                # Remove any temporary prefixes/suffixes if needed
                if normalized.startswith('temp_') and not any(f.startswith('temp_') for f in allowed_files or []):
                    normalized = normalized[5:]
                return normalized
            except Exception as e:
                logger.error(f"Error normalizing filename '{name}': {str(e)}")
                return ''

        # If user is not an admin (allowed_files is a list), create a set for faster lookups
        # For admins (allowed_files is None), they can access all files
        tracker.start_operation("build_access_set")
        allowed_files_set = None
        if allowed_files is not None:  # Not an admin, has restricted access
            allowed_files_set = {normalize_filename(f) for f in allowed_files if f}
            logger.info(f"User {username} has restricted access to files: {allowed_files_set}")
        else:
            logger.info(f"User {username} is an admin and has access to all files")
        tracker.end_operation("build_access_set")

        # Use Elasticsearch search
        logger.info(f"Searching for query: {query}")
        logger.info(f"User {username} access: {'admin' if allowed_files is None else 'restricted'}")

        tracker.start_operation("search_documents")
        search_results = await search_documents(
            query=query,
            allowed_files=allowed_files if allowed_files is not None else [],
            size=k * 3,
            search_type="hybrid",
            language='russian'
        )

        results = search_results.get('results', []) if search_results.get('status') == 'success' else []
        
        logger.info(f"Initial search results: {len(results)} total results")

        # If we don't have enough results, try semantic-only with lower threshold
        if len(results) < k:
            logger.info("Performing fallback semantic search with expanded parameters")
            fallback_results = await search_documents(
                query=query,
                allowed_files=allowed_files if allowed_files is not None else [],
                size=k * 5,
                search_type="semantic",
                language='russian',
                min_score=0.05
            )
            fallback = fallback_results.get('results', []) if fallback_results.get('status') == 'success' else []
            logger.info(f"Fallback search results: {len(fallback)} total results")
            
            # Merge results, preferring first pass
            existing_keys = {(r.get('filename', ''), r.get('chunk_index', 0)) for r in results}
            for r in fallback:
                key = (r.get('filename', ''), r.get('chunk_index', 0))
                if key not in existing_keys:
                    results.append(r)
        
        # Log all filenames from search results
        all_filenames = [r.get('filename', '') for r in results]
        logger.info(f"Search result filenames (raw): {set(all_filenames)}")
        normalized_filenames = [f"'{normalize_filename(f)}'" for f in set(all_filenames)]
        logger.info(f"Search result filenames (normalized): {{{', '.join(normalized_filenames)}}}")
        logger.info(f"User's allowed files (normalized): {allowed_files_set}")
        logger.info(f"Total results after merging: {len(results)} results")
        tracker.end_operation("search_documents")

        # Process results
        tracker.start_operation("process_results")
        relevant_files = []
        seen_files = set()
        file_chunks = {}
        total_skipped = 0
        total_allowed = 0

        for doc in results:
            file_source = doc.get('filename', '')
            if not file_source:
                continue
            
            # Check access if user has restricted access
            if allowed_files_set is not None:
                norm_name = normalize_filename(file_source)
                if not norm_name or norm_name not in allowed_files_set:
                    total_skipped += 1
                    continue
                total_allowed += 1

            if file_source not in file_chunks:
                file_chunks[file_source] = []
            
            chunk_data = {
                "content": doc.get('content', ''),
                "score": doc.get('score', 0.5),
                "metadata": {k: v for k, v in doc.items() if k not in ['filename', 'content', 'score']}
            }
            file_chunks[file_source].append(chunk_data)
        
        logger.info(f"Processed {len(results)} documents - Allowed: {total_allowed}, Skipped: {total_skipped}")

        # Process each file's chunks for optimal context
        for file_source, chunks in file_chunks.items():
            try:
                # Sort chunks by score (descending)
                chunks.sort(key=lambda x: x['score'], reverse=True)
                
                # Take top chunks but ensure we don't exceed reasonable context length
                max_chunks = 5  # Maximum chunks per file to include
                selected_chunks = chunks[:max_chunks]
                
                # Calculate aggregate relevance score (weighted average)
                total_score = sum(c['score'] for c in selected_chunks)
                avg_score = total_score / len(selected_chunks) if selected_chunks else 0
                
                # Combine chunks with separators
                combined_content = "\n\n---\n\n".join(
                    f"[Relevance: {c['score']:.2f}]\n{c['content']}" 
                    for c in selected_chunks
                )
                
                # Add file metadata
                file_metadata = {}
                if selected_chunks and 'metadata' in selected_chunks[0]:
                    file_metadata = selected_chunks[0]['metadata']
                
                relevant_files.append({
                    "file_path": file_source,
                    "file_name": os.path.basename(file_source),
                    "relevance_score": avg_score,
                    "content": combined_content,
                    "chunks": selected_chunks,
                    "metadata": file_metadata
                })
                seen_files.add(file_source)
                logger.debug(f"Added file {file_source} with score {avg_score:.2f} and {len(selected_chunks)} chunks")
                
            except Exception as e:
                logger.error(f"Error processing file {file_source}: {str(e)}", exc_info=True)
                continue

        # Sort by relevance score (higher is better) and take top k
        relevant_files.sort(key=lambda x: x["relevance_score"], reverse=True)
        result = relevant_files[:k]
        
        # Log final results
        logger.info(f"Returning {len(result)} relevant files")
        for i, file_info in enumerate(result, 1):
            logger.info(f"  {i}. {file_info['file_name']} (score: {file_info['relevance_score']:.2f})")
        
        tracker.end_operation("process_results")
        tracker.log_summary()
        return result

    except Exception as e:
        logger.error(f"Error in get_relevant_files_for_query: {str(e)}", exc_info=True)
        tracker.log_summary()
        return []

async def filter_documents_by_user_access(documents: List[Any], username: str) -> List[Any]:
    """
    Filter documents based on user's file access permissions.
    Only return documents from files the user is allowed to access.
    """
    logger = logging.getLogger(__name__)
    tracker = PerformanceTracker(f"filter_documents_by_user_access('{username}', {len(documents)} docs)", logger)

    try:
        # Get user's allowed files
        tracker.start_operation("get_user_permissions")
        allowed_files = await get_user_allowed_filenames(username)
        tracker.end_operation("get_user_permissions")

        # If None, user can access all files (admin or 'all' permission)
        if allowed_files is None:
            logger.info(f"User {username} has access to all files")
            tracker.log_summary()
            return documents

        # Filter documents
        tracker.start_operation("filter_documents")
        filtered_docs = []
        for doc in documents:
            # Get filename from document metadata
            filename = None
            if hasattr(doc, 'metadata') and doc.metadata:
                # First try to get filename directly from metadata
                filename = doc.metadata.get('filename', '')

                # If not found, try to extract from source path
                if not filename:
                    source = doc.metadata.get('source', '')
                    if source:
                        filename = os.path.basename(source)

            if filename:
                # Strip temp_ prefix when checking permissions
                clean_filename = filename.replace('temp_', '')
                # Check if user has access to this file
                tracker.start_operation("check_file_access")
                has_access = await check_file_access(username, clean_filename)
                tracker.end_operation("check_file_access")

                if has_access:
                    filtered_docs.append(doc)
                else:
                    logger.warning(f"User {username} denied access to document from file: {filename}")
                    try:
                        from reports_db import submit_report
                        submit_report(
                            user=username,
                            permitted_files=[filename],
                            issue=f"Denied access to document from file: {filename}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to save denied access report for user {username}: {e}")
            else:
                # If no filename found, be conservative and exclude
                logger.warning(f"Document has no filename metadata, excluding for user {username}")

        tracker.end_operation("filter_documents", f"Filtered {len(documents)} → {len(filtered_docs)} docs")
        tracker.log_summary()
        logger.info(f"Filtered {len(documents)} documents to {len(filtered_docs)} for user {username}")
        return filtered_docs

    except Exception as e:
        logger.error(f"Error filtering documents for user {username}: {e}")
        tracker.log_summary()
        # On error, return empty list for security
        return []

async def get_filtered_rag_context(query: str, username: str, k: int = 3) -> List[Any]:
    """
    Get RAG context documents filtered by user's file access permissions.
    """
    try:
        # Check if vectorstore is available
        if vectorstore is None:
            logger.error("Vectorstore not available for RAG context retrieval")
            return []

        # Get documents from vector store
        retriever = vectorstore.as_retriever(search_kwargs={"k": k * 2})  # Get more than needed
        all_docs = retriever.get_relevant_documents(query)

        # Filter by user permissions
        filtered_docs = await filter_documents_by_user_access(all_docs, username)

        # Return only the requested number of documents
        return filtered_docs[:k]

    except Exception as e:
        logger.error(f"Error getting filtered RAG context for user {username}: {e}")
        return []

async def check_rag_response_security(response_text: str, username: str, source_documents: List[Any]) -> Dict[str, Any]:
    """
    Check if RAG response is secure for the user based on source documents.
    Returns dict with security info and filtered response if needed.
    """
    try:
        # Filter source documents by user access
        allowed_docs = await filter_documents_by_user_access(source_documents, username)
        
        security_info = {
            "total_source_documents": len(source_documents),
            "allowed_source_documents": len(allowed_docs),
            "access_denied_count": len(source_documents) - len(allowed_docs),
            "is_secure": len(allowed_docs) > 0,
            "filtered_response": response_text
        }
        
        # If user has no access to any source documents, return generic message
        if len(allowed_docs) == 0 and len(source_documents) > 0:
            security_info["is_secure"] = False
            security_info["filtered_response"] = (
                "I don't have access to information that can answer your question based on "
                "the documents you're authorized to view. Please contact an administrator "
                "if you need access to additional files."
            )
            logger.warning(f"User {username} denied access to all source documents for query")
        
        # If some documents were filtered out, add a note
        elif security_info["access_denied_count"] > 0:
            security_info["filtered_response"] += (
                f"\n\n*Note: This response is based on {len(allowed_docs)} out of "
                f"{len(source_documents)} relevant documents. Some documents were "
                f"excluded based on your access permissions.*"
            )
            logger.info(f"User {username} had {security_info['access_denied_count']} documents filtered out")
        
        return security_info
        
    except Exception as e:
        logger.error(f"Error checking RAG response security for user {username}: {e}")
        return {
            "total_source_documents": 0,
            "allowed_source_documents": 0,
            "access_denied_count": 0,
            "is_secure": False,
            "filtered_response": "An error occurred while processing your request. Please try again."
        }

async def get_user_accessible_file_ids(username: str) -> Optional[List[int]]:
    """
    Get list of file IDs that user can access from the RAG document store.
    Returns None if user can access all files.
    """
    try:
        # Get allowed filenames for user
        allowed_filenames = await get_user_allowed_filenames(username)
        
        # If None, user can access all files
        if allowed_filenames is None:
            return None
        
        # Get file IDs from RAG document store
        from rag_api.db_utils import get_all_documents
        all_documents = get_all_documents()
        
        accessible_file_ids = []
        for doc in all_documents:
            filename = doc.get('filename', '')
            file_id = doc.get('id')
            
            if filename in allowed_filenames and file_id:
                accessible_file_ids.append(file_id)
        
        logger.info(f"User {username} has access to {len(accessible_file_ids)} document files")
        return accessible_file_ids
        
    except Exception as e:
        logger.error(f"Error getting accessible file IDs for user {username}: {e}")
        return []

class SecureRAGRetriever:
    """
    A secure RAG retriever that respects user file access permissions.
    Uses file-based retrieval without chat history.
    """
    
    def __init__(self, username: str, session_id: str = None):
        self.username = username
        self.session_id = session_id or str(uuid.uuid4())
        self.rag_chain = None
    
    async def get_relevant_documents(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Get relevant documents for a query that the user has access to.
        Returns a list of document dictionaries with metadata and multiple chunks per file.
        """
        logger = logging.getLogger(__name__)
        try:
            files = await get_relevant_files_for_query(self.username, query, k)
            
            # Convert to list of documents with proper format
            documents = []
            for file_info in files:
                # For each chunk in the file, create a document
                chunks = file_info.get('chunks', [{'content': file_info.get('content', '')}])
                
                for chunk in chunks:
                    doc = {
                        'page_content': chunk.get('content', ''),
                        'metadata': {
                            'source': file_info['file_path'],
                            'filename': file_info['file_name'],
                            'relevance_score': 1.0 - chunk.get('score', 0.5),
                            'is_filename_match': file_info.get('is_filename_match', False),
                            'session_id': self.session_id  # Add session_id to metadata
                        }
                    }
                    documents.append(doc)
            
            return documents
        except Exception as e:
            logger.error(f"Error in get_relevant_documents for session {self.session_id}: {str(e)}")
            return []
    
    async def invoke_secure_rag_chain(self, rag_chain, query: str, chat_history: List = None, model_type: str = "server", humanize: bool = True, skip_llm: bool = False):
        """
        Invoke RAG chain with security filtering.
        Returns a dictionary with answer, source documents, and relevant files.
        Handles multiple chunks per file and preserves chunk relevance scores.
        
        Args:
            skip_llm: If True, skip LLM generation and return only documents (for immediate results)
        """
        try:
            # Get relevant documents for the query
            relevant_docs = await self.get_relevant_documents(query)
            
            if not relevant_docs:
                return {
                    "answer": "I couldn't find any relevant information in the documents you have access to.",
                    "source_documents": [],
                    "source_documents_raw": [],
                    "relevant_files": [],
                    "security_filtered": True
                }
            
            # Group documents by file
            files_dict = {}
            for doc in relevant_docs:
                file_path = doc['metadata']['source']
                if file_path not in files_dict:
                    files_dict[file_path] = {
                        'file_path': file_path,
                        'file_name': doc['metadata'].get('filename', os.path.basename(file_path)),
                        'chunks': [],
                        'is_filename_match': doc['metadata'].get('is_filename_match', False)
                    }
                files_dict[file_path]['chunks'].append({
                    'content': doc['page_content'],
                    'score': 1.0 - doc['metadata'].get('relevance_score', 0.5)
                })
            
            # Convert to list and sort by best chunk score
            relevant_files = list(files_dict.values())
            for file_info in relevant_files:
                file_info['chunks'].sort(key=lambda x: x['score'], reverse=True)
                file_info['relevance_score'] = file_info['chunks'][0]['score'] if file_info['chunks'] else 0
            
            relevant_files.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            # Prepare context for the RAG chain (use top chunks from each file)
            context = []
            for file_info in relevant_files:
                if file_info['chunks']:
                    # Use the top chunk for context
                    top_chunk = file_info['chunks'][0]
                    context.append({
                        'page_content': top_chunk['content'],
                        'metadata': {
                            'source': file_info['file_path'],
                            'filename': file_info['file_name'],
                            'relevance_score': top_chunk['score']
                        }
                    })
            
            # Format the context as a string for the prompt
            context_str = "\n\n".join([
                f"File: {doc['metadata']['filename']}\nContent: {doc['page_content']}"
                for doc in context
            ])
            
            # Skip LLM generation if requested (for immediate results)
            answer = None
            if not skip_llm:
                try:
                    # Get answer using the RAG chain
                    result = await rag_chain["answer"]({
                        "input": query,
                        "context": context_str
                    })
                    
                    # Extract the answer from the result
                    answer = result
                    if isinstance(result, dict):
                        answer = result.get('answer', 'No answer generated.')
                    elif hasattr(result, 'content'):
                        answer = result.content
                    
                    # Ensure answer is a string
                    if not isinstance(answer, str):
                        answer = str(answer)
                    
                    # Clean up the answer
                    answer = answer.strip()
                except Exception as e:
                    logger.error(f"Error in RAG chain LLM generation: {str(e)}")
                    answer = None
            
            try:
                
                # Prepare both raw and formatted source documents
                # Raw docs with page_content/metadata expected by API
                raw_sources = []
                for doc in context:
                    raw_sources.append({
                        'page_content': doc['page_content'],
                        'metadata': {
                            'source': doc['metadata'].get('source', ''),
                            'filename': doc['metadata'].get('filename', ''),
                            'relevance_score': doc['metadata'].get('relevance_score', 0.5)
                        }
                    })

                # Formatted docs for display
                formatted_sources = []
                for file_info in relevant_files:
                    if not file_info.get('chunks'):
                        continue
                        
                    # Clean up the filename by removing 'temp_' and the extension
                    clean_name = file_info.get('file_name', 'Unknown Document')
                    if clean_name.startswith('temp_'):
                        clean_name = clean_name[5:]  # Remove 'temp_' prefix
                    if '.' in clean_name:
                        clean_name = clean_name.rsplit('.', 1)[0]  # Remove file extension
                    
                    # Show top chunk content and indicate if there are more
                    top_chunk = file_info['chunks'][0]
                    has_more = len(file_info['chunks']) > 1
                    
                    formatted_sources.append({
                        'title': clean_name,
                        'content': top_chunk['content'][:200] + ('...' if len(top_chunk['content']) > 200 else ''),
                        'relevance': f"{top_chunk['score']:.0%}",  # Convert to percentage
                        'has_more_chunks': has_more,
                        'chunk_count': len(file_info['chunks'])
                    })
                
                return {
                    "answer": answer,
                    "source_documents": formatted_sources,
                    "source_documents_raw": raw_sources,
                    "security_filtered": False
                }
            except Exception as e:
                logger.error(f"Error in RAG chain: {str(e)}")
                # Prepare raw and formatted source documents even in error case
                raw_sources = []
                for file in relevant_files:
                    raw_sources.append({
                        'page_content': file.get('content', ''),
                        'metadata': {
                            'source': file.get('file_path', ''),
                            'filename': file.get('file_name', '')
                        }
                    })

                formatted_sources = []
                for doc in relevant_files:
                    clean_name = doc.get('file_name', 'Unknown Document')
                    if clean_name.startswith('temp_'):
                        clean_name = clean_name[5:]
                    if '.' in clean_name:
                        clean_name = clean_name.rsplit('.', 1)[0]
                    
                    formatted_sources.append({
                        'title': clean_name,
                        'content': doc.get('content', '')[:200] + '...',
                        'relevance': f"{1 - doc.get('relevance_score', 0):.0%}"
                    })
                
                return {
                    "answer": f"Error generating response: {str(e)}",
                    "source_documents": formatted_sources,
                    "source_documents_raw": raw_sources,
                    "security_filtered": False
                }
            
        except Exception as e:
            logger.error(f"Error in secure RAG chain for user {self.username}: {e}")
            return {
                "answer": "An error occurred while processing your request securely.",
                "source_documents": [],
                "security_filtered": False
            }
