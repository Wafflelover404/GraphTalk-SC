import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

SEARCH_BACKEND = os.getenv("SEARCH_BACKEND", "elasticsearch")

def get_search_backend() -> str:
    return SEARCH_BACKEND


async def search_documents(
    query: str,
    allowed_files: List[str] = None,
    size: int = 20,
    search_type: str = "hybrid",
    language: str = None,
    min_score: float = 0.1
) -> Dict[str, Any]:
    """Search using Elasticsearch only"""
    from rag_api.elastic_search_standalone import search_documents as es_search
    
    return await es_search(
        query=query,
        allowed_files=allowed_files if allowed_files is not None else [],
        size=size,
        search_type=search_type,
        language=language,
        min_score=min_score
    )
