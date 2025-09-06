"""
RAG Security Module
Handles filtering RAG responses based on user file access permissions
"""

import sys
import os
from typing import List, Optional, Dict, Any
import logging

# Add rag_api to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'rag_api'))

from userdb import get_user_allowed_filenames, check_file_access
from rag_api.chroma_utils import vectorstore
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

async def get_relevant_files_for_query(username: str, query: str, k: int = 5) -> List[Dict[str, Any]]:
    """Get list of relevant files for a query that the user has access to."""
    try:
        # Get all files user has access to
        allowed_files = await get_user_allowed_filenames(username)
        
        # Get relevant documents from the vector store
        docs = vectorstore.similarity_search_with_score(query, k=20)
        
        # Filter and rank files based on relevance and access
        relevant_files = []
        seen_files = set()
        
        for doc, score in docs:
            file_source = doc.metadata.get("source", "")
            file_name = os.path.basename(file_source)
            
            # Check if user has access to this file
            has_access = (allowed_files is None or  # Admin has access to all files
                        file_name in allowed_files or 
                        file_source in allowed_files)
            
            if has_access and file_source and file_source not in seen_files:
                seen_files.add(file_source)
                relevant_files.append({
                    "file_path": file_source,
                    "file_name": file_name,
                    "relevance_score": float(score),  # Ensure score is serializable
                    "content": doc.page_content[:500]  # First 500 chars as preview
                })
        
        # Sort by relevance score (lower is better)
        relevant_files.sort(key=lambda x: x["relevance_score"])
        
        return relevant_files[:k]  # Return top k files
        
    except Exception as e:
        logger.error(f"Error getting relevant files: {str(e)}")
        return []

async def filter_documents_by_user_access(documents: List[Any], username: str) -> List[Any]:
    """
    Filter documents based on user's file access permissions.
    Only return documents from files the user is allowed to access.
    """
    try:
        # Get user's allowed files
        allowed_files = await get_user_allowed_filenames(username)
        
        # If None, user can access all files (admin or 'all' permission)
        if allowed_files is None:
            logger.info(f"User {username} has access to all files")
            return documents
        
        # Filter documents
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
                has_access = await check_file_access(username, clean_filename)
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
        
        logger.info(f"Filtered {len(documents)} documents to {len(filtered_docs)} for user {username}")
        return filtered_docs
        
    except Exception as e:
        logger.error(f"Error filtering documents for user {username}: {e}")
        # On error, return empty list for security
        return []

async def get_filtered_rag_context(query: str, username: str, k: int = 3) -> List[Any]:
    """
    Get RAG context documents filtered by user's file access permissions.
    """
    try:
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
    
    def __init__(self, username: str):
        self.username = username
        self.rag_chain = None
    
    async def get_relevant_documents(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Get relevant documents for a query that the user has access to.
        Returns a list of document dictionaries with metadata.
        """
        return await get_relevant_files_for_query(self.username, query, k)
    
    async def invoke_secure_rag_chain(self, rag_chain, query: str, chat_history: List = None, model_type: str = "server", humanize: bool = True):
        """
        Invoke RAG chain with security filtering.
        Returns a dictionary with answer, source documents, and relevant files.
        """
        try:
            # Get relevant files for the query
            relevant_files = await self.get_relevant_documents(query)
            
            if not relevant_files:
                return {
                    "answer": "I couldn't find any relevant information in the documents you have access to.",
                    "source_documents": [],
                    "relevant_files": [],
                    "security_filtered": True
                }
            
            # Prepare context for the RAG chain
            context = [{
                'page_content': file['content'],
                'metadata': {
                    'source': file['file_path'],
                    'filename': file['file_name']
                }
            } for file in relevant_files]
            
            # Format the context as a string for the prompt
            context_str = "\n\n".join([
                f"File: {file['file_name']}\nContent: {file['content']}"
                for file in relevant_files
            ])
            
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
                
                # Format the source documents for display
                formatted_sources = []
                for doc in relevant_files:
                    # Clean up the filename by removing 'temp_' and the extension
                    clean_name = doc.get('file_name', 'Unknown Document')
                    if clean_name.startswith('temp_'):
                        clean_name = clean_name[5:]  # Remove 'temp_' prefix
                    if '.' in clean_name:
                        clean_name = clean_name.rsplit('.', 1)[0]  # Remove file extension
                    
                    formatted_sources.append({
                        'title': clean_name,
                        'content': doc.get('content', '')[:200] + '...',  # Show first 200 chars
                        'relevance': f"{1 - doc.get('relevance_score', 0):.0%}"  # Convert to percentage
                    })
                
                return {
                    "answer": answer,
                    "source_documents": formatted_sources,
                    "security_filtered": False
                }
            except Exception as e:
                logger.error(f"Error in RAG chain: {str(e)}")
                # Format the source documents for display even in error case
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
                    "security_filtered": False
                }
            
        except Exception as e:
            logger.error(f"Error in secure RAG chain for user {self.username}: {e}")
            return {
                "answer": "An error occurred while processing your request securely.",
                "source_documents": [],
                "security_filtered": False
            }
