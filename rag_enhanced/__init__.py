"""
RAG Enhanced - Advanced RAG implementation with improved indexing and search.
"""

from .processor import DocumentProcessor
from .embeddings import EnhancedEmbeddingFunction, get_vector_store
from .indexer import DocumentIndexer
from .searcher import EnhancedSearcher

__version__ = "0.1.0"
__all__ = [
    "DocumentProcessor",
    "EnhancedEmbeddingFunction",
    "get_vector_store",
    "DocumentIndexer",
    "EnhancedSearcher"
]

# Initialize logging when the package is imported
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"Initialized RAG Enhanced v{__version__}")
