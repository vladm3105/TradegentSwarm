"""RAG embedding tools."""

import sys
from pathlib import Path

# Add trader package to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trader"))

from rag.embed import embed_document, embed_text, delete_document


def rag_embed(file_path: str, force: bool = False) -> dict:
    """
    Embed a YAML document for semantic search.

    Args:
        file_path: Path to YAML file
        force: Re-embed even if unchanged

    Returns:
        Embed result dict
    """
    result = embed_document(file_path=file_path, force=force)
    return result.to_dict()


def rag_embed_text(
    text: str,
    doc_id: str,
    doc_type: str,
    ticker: str | None = None,
) -> dict:
    """
    Embed raw text for semantic search.

    Args:
        text: Text to embed
        doc_id: Document identifier
        doc_type: Document type
        ticker: Optional ticker symbol

    Returns:
        Embed result dict
    """
    result = embed_text(
        text=text,
        doc_id=doc_id,
        doc_type=doc_type,
        ticker=ticker,
    )
    return result.to_dict()


def rag_delete(doc_id: str) -> dict:
    """
    Delete embedded document.

    Args:
        doc_id: Document identifier

    Returns:
        Deletion status
    """
    success = delete_document(doc_id)
    return {"deleted": success, "doc_id": doc_id}
