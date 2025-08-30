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

logger = logging.getLogger(__name__)

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
                source = doc.metadata.get('source', '')
                if source:
                    # Extract filename from full path
                    filename = os.path.basename(source)
                
                # Also check for direct filename in metadata
                if not filename:
                    filename = doc.metadata.get('filename', '')
            
            if filename:
                # Check if user has access to this file
                has_access = await check_file_access(username, filename)
                if has_access:
                    filtered_docs.append(doc)
                else:
                    logger.warning(f"User {username} denied access to document from file: {filename}")
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
    """
    
    def __init__(self, username: str):
        self.username = username
    
    async def get_relevant_documents(self, query: str, k: int = 3):
        """Get relevant documents filtered by user permissions."""
        return await get_filtered_rag_context(query, self.username, k)
    
    async def invoke_secure_rag_chain(self, rag_chain, query: str, chat_history: List = None, model_type: str = "server", humanize: bool = True):
        """
        Invoke RAG chain with security filtering and model selection.
        model_type: "local" for llama3.2 or "server" for gemini
        humanize: True = return LLM response, False = return raw RAG chunks with filename tags
        """
        try:
            # Get user-filtered documents
            filtered_docs = await self.get_relevant_documents(query)
            
            if not filtered_docs:
                return {
                    "answer": (
                        "I don't have access to relevant information to answer your question "
                        "based on the documents you're authorized to view."
                    ),
                    "source_documents": [],
                    "security_filtered": True
                }
            
            # If humanize is False, return raw chunks with filename tags
            if not humanize:
                raw_chunks = []
                for doc in filtered_docs:
                    filename = "unknown"
                    if hasattr(doc, 'metadata') and doc.metadata:
                        source = doc.metadata.get('source', '')
                        if source:
                            filename = os.path.basename(source)
                        if not filename or filename == "unknown":
                            filename = doc.metadata.get('filename', 'unknown')
                    
                    chunk_with_filename = f"{doc.page_content}\n<filename>{filename}</filename>"
                    raw_chunks.append(chunk_with_filename)
                
                return {
                    "answer": raw_chunks,  # Return array of chunks with filename tags
                    "source_documents": filtered_docs,
                    "security_filtered": len(filtered_docs) > 0,
                    "raw_mode": True
                }
            
            # Create a custom context string from filtered docs for LLM processing
            context = "\n".join([doc.page_content for doc in filtered_docs])
            
            # Choose model based on type for humanized response
            if model_type == "local":
                # Use local llama3.2 model via RAG chain
                try:
                    from rag_api.langchain_utils import get_rag_chain
                    rag_chain = get_rag_chain("llama3.2")
                    # Create a simple input for the chain
                    answer = rag_chain.invoke({
                        "input": query,
                        "chat_history": chat_history or [],
                        "context": context
                    })['answer']
                except Exception as e:
                    logger.error(f"Local model error, falling back to server model: {e}")
                    from llm import llm_call
                    answer = await llm_call(query, context)
            else:
                # Use server gemini model
                from llm import llm_call
                answer = await llm_call(query, context)
            
            return {
                "answer": answer,
                "source_documents": filtered_docs,
                "security_filtered": len(filtered_docs) > 0
            }
            
        except Exception as e:
            logger.error(f"Error in secure RAG chain for user {self.username}: {e}")
            return {
                "answer": "An error occurred while processing your request securely.",
                "source_documents": [],
                "security_filtered": False
            }
