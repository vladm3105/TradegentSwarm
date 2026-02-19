"""Graph extraction tools."""

import sys
from pathlib import Path

# Add trader package to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "trader"))

from graph.extract import extract_document, extract_text
from graph.exceptions import ExtractionError


def graph_extract(file_path: str, extractor: str = "ollama", commit: bool = True) -> dict:
    """
    Extract entities and relationships from a YAML document.

    Args:
        file_path: Path to YAML file
        extractor: LLM backend (ollama, claude-api, openrouter)
        commit: Whether to commit to Neo4j

    Returns:
        Extraction result dict
    """
    result = extract_document(
        file_path=file_path,
        extractor=extractor,
        commit=commit,
    )
    return result.to_dict()


def graph_extract_text(
    text: str,
    doc_type: str,
    doc_id: str,
    source_url: str | None = None,
    extractor: str = "ollama",
) -> dict:
    """
    Extract entities from raw text.

    Args:
        text: Text to extract from
        doc_type: Document type
        doc_id: Document identifier
        source_url: Optional source URL
        extractor: LLM backend

    Returns:
        Extraction result dict
    """
    result = extract_text(
        text=text,
        doc_type=doc_type,
        doc_id=doc_id,
        source_url=source_url,
        extractor=extractor,
    )
    return result.to_dict()
