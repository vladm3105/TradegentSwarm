"""Trading RAG (Retrieval Augmented Generation) package."""

RAG_VERSION = "1.0.0"
EMBED_DIMS = 768

from .models import (
    ChunkResult,
    EmbedResult,
    SearchResult,
    HybridContext,
)
from .exceptions import (
    RAGError,
    RAGUnavailableError,
    EmbeddingUnavailableError,
    ChunkingError,
    EmbedError,
)

__all__ = [
    "RAG_VERSION",
    "EMBED_DIMS",
    "ChunkResult",
    "EmbedResult",
    "SearchResult",
    "HybridContext",
    "RAGError",
    "RAGUnavailableError",
    "EmbeddingUnavailableError",
    "ChunkingError",
    "EmbedError",
]
