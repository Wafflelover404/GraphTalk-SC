"""
Enhanced document processing with structure-aware chunking and text cleaning.
"""
import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    HTMLHeaderTextSplitter
)

logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 300):
        """
        Initialize the document processor with configurable chunking.
        
        Args:
            chunk_size: Maximum size of chunks in characters
            chunk_overlap: Overlap between chunks in characters
        """
        # Initialize with different splitters for different file types
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "(?<=\. )", " ", ""]
        )
        
        # Markdown header splitter
        self.markdown_header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3")
            ]
        )
        
        # HTML header splitter
        self.html_header_splitter = HTMLHeaderTextSplitter(
            headers_to_split_on=[
                ("h1", "Header 1"),
                ("h2", "Header 2"),
                ("h3", "Header 3"),
                ("h4", "Header 4")
            ]
        )
    
    def clean_text(self, text: str) -> str:
        """Enhanced text cleaning with normalization."""
        # Normalize whitespace and clean up text
        text = re.sub(r'\s+', ' ', text)
        # Remove control characters
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)
        # Normalize quotes and dashes
        text = text.replace('"', "'").replace('—', '-').replace('–', '-')
        return text.strip()
    
    def extract_metadata(self, file_path: str, content: str) -> Dict[str, Any]:
        """Extract metadata from document content."""
        metadata = {
            "source": str(file_path),
            "filename": Path(file_path).name,
            "file_type": Path(file_path).suffix.lower(),
            "created_at": Path(file_path).stat().st_ctime,
            "modified_at": Path(file_path).stat().st_mtime
        }
        
        # Extract title from content (first non-empty line or first 100 chars)
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        if lines:
            metadata["title"] = lines[0][:200]
        
        return metadata
    
    def process_document(self, file_path: str) -> List[Document]:
        """Process a document with enhanced text extraction and chunking.
        
        Args:
            file_path: Path to the file to process
            
        Returns:
            List of Document objects with processed content and metadata
            
        Raises:
            FileNotFoundError: If the file does not exist
            PermissionError: If the file cannot be read
            ValueError: If the file is empty or no content can be extracted
        """
        try:
            file_path = str(Path(file_path).resolve())
            logger.info(f"Processing document: {file_path}")
            
            # Check if file exists and is readable
            if not os.path.exists(file_path):
                error_msg = f"File not found: {file_path}"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)
                
            if not os.path.isfile(file_path):
                error_msg = f"Path is not a file: {file_path}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            if not os.access(file_path, os.R_OK):
                error_msg = f"No read permission for file: {file_path}"
                logger.error(error_msg)
                raise PermissionError(error_msg)
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                error_msg = f"File is empty: {file_path}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                error_msg = f"File too large ({(file_size/1024/1024):.2f}MB > 100MB): {file_path}"
                logger.error(error_msg)
                raise ValueError("File too large. Maximum size is 100MB.")
            
            # Read file content with proper encoding handling
            logger.debug(f"Reading file: {file_path} ({(file_size/1024):.2f}KB)")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                logger.debug(f"UTF-8 decode failed, trying with error handling: {file_path}")
                # Fallback to binary read if UTF-8 fails
                with open(file_path, 'rb') as f:
                    content = f.read().decode('utf-8', errors='replace')
            
            if not content.strip():
                error_msg = f"File appears to be empty after reading: {file_path}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
            logger.debug(f"Read {len(content)} characters from {file_path}")
            content = self.clean_text(content)
            
            # Extract metadata
            metadata = self.extract_metadata(file_path, content)
            logger.debug(f"Extracted metadata: {metadata}")
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}", exc_info=True)
            return []
    
    def _process_text(self, file_path: Path, metadata: Dict[str, Any]) -> List[Document]:
        """
        Process plain text files.
        
        Args:
            file_path: Path to the text file
            metadata: Metadata to include with each chunk
            
        Returns:
            List of document chunks with metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
                
            # Clean and normalize text
            text = self.clean_text(text)
            
            # If text is empty after cleaning, return empty list
            if not text.strip():
                logger.warning(f"No content found in file after cleaning: {file_path}")
                return []
            
            # Split into chunks
            chunks = self.text_splitter.split_text(text)
            total_chunks = len(chunks)
            
            # Create document objects with enhanced metadata
            documents = []
            for i, chunk in enumerate(chunks):
                # Create chunk-specific metadata
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    'chunk_id': f"{file_path.stem}_{i}",
                    'chunk_index': i,
                    'total_chunks': total_chunks,
                    'chunk_hash': hash(chunk)  # For deduplication
                })
                
                # Create document with chunk content and metadata
                doc = Document(
                    page_content=chunk,
                    metadata=chunk_metadata
                )
                documents.append(doc)
                
            return documents
            
        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {str(e)}", exc_info=True)
            return []
    
    def _process_markdown(self, file_path: Path, metadata: Dict[str, Any]) -> List[Document]:
        """
        Process markdown files with header-based splitting.
        
        Args:
            file_path: Path to the markdown file
            metadata: Metadata to include with each chunk
            
        Returns:
            List of document chunks with metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                markdown_text = f.read()
                
            # Clean the markdown text
            markdown_text = self.clean_text(markdown_text)
            
            # If text is empty after cleaning, return empty list
            if not markdown_text.strip():
                logger.warning(f"No content found in markdown after cleaning: {file_path}")
                return []
                
            # First split by headers
            header_splits = self.markdown_header_splitter.split_text(markdown_text)
            
            # Then split each header section into smaller chunks
            all_chunks = []
            for i, doc in enumerate(header_splits):
                chunks = self.text_splitter.split_documents([doc])
                for j, chunk in enumerate(chunks):
                    # Create chunk-specific metadata
                    chunk_metadata = metadata.copy()
                    chunk_metadata.update({
                        'chunk_id': f"{file_path.stem}_h{i}_{j}",
                        'chunk_index': j,
                        'total_chunks': len(chunks),
                        'section_index': i,
                        'chunk_hash': hash(chunk.page_content)  # For deduplication
                    })
                    
                    # Update document metadata
                    chunk.metadata.update(chunk_metadata)
                    all_chunks.append(chunk)
                    
            return all_chunks
            
        except Exception as e:
            logger.error(f"Error processing markdown file {file_path}: {str(e)}", exc_info=True)
            return []
    
    def _process_html(self, file_path: Path, metadata: Dict[str, Any]) -> List[Document]:
        """
        Process HTML files with structure-aware splitting.
        
        Args:
            file_path: Path to the HTML file
            metadata: Metadata to include with each chunk
            
        Returns:
            List of document chunks with metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_text = f.read()
                
            # Clean the HTML text
            html_text = self.clean_text(html_text)
            
            # If text is empty after cleaning, return empty list
            if not html_text.strip():
                logger.warning(f"No content found in HTML after cleaning: {file_path}")
                return []
                
            # First split by HTML headers
            header_splits = self.html_header_splitter.split_text(html_text)
            
            # Then split each header section into smaller chunks
            all_chunks = []
            for i, doc in enumerate(header_splits):
                chunks = self.text_splitter.split_documents([doc])
                for j, chunk in enumerate(chunks):
                    # Create chunk-specific metadata
                    chunk_metadata = metadata.copy()
                    chunk_metadata.update({
                        'chunk_id': f"{file_path.stem}_h{i}_{j}",
                        'chunk_index': j,
                        'total_chunks': len(chunks),
                        'section_index': i,
                        'chunk_hash': hash(chunk.page_content)  # For deduplication
                    })
                    
                    # Update document metadata
                    chunk.metadata.update(chunk_metadata)
                    all_chunks.append(chunk)
                    
            return all_chunks
            
        except Exception as e:
            logger.error(f"Error processing HTML file {file_path}: {str(e)}", exc_info=True)
            return []
        # Split into chunks
        return self.text_splitter.split_documents([doc])
