#!/usr/bin/env python3
"""Test RAG system with a sample story and questions."""

import sys
from pathlib import Path

# Add trader to path
sys.path.insert(0, str(Path(__file__).parent.parent / "trader"))

from rag.embed import embed_text
from rag.search import semantic_search

# A trading story with ~200 tokens
STORY = """
The legendary trader Marcus Chen started his career at Goldman Sachs in 2008,
right before the financial crisis. He witnessed the collapse of Lehman Brothers
and learned valuable lessons about risk management and market psychology.

After leaving Goldman in 2012, Marcus founded Chen Capital with just $500,000
in seed money. His strategy focused on volatility trading around earnings
announcements, particularly in the semiconductor sector.

By 2020, Chen Capital had grown to manage $2.3 billion in assets. Marcus
became known for his "5-3-2 Rule": never risk more than 5% on a single trade,
maintain at least 3 uncorrelated positions, and always keep 2 weeks of runway
in cash.

His biggest trade came during the 2023 AI boom when he accumulated NVIDIA shares
at $180 before the ChatGPT announcement. He sold half his position at $480,
locking in over $150 million in profits.

Marcus attributes his success to three principles: patience, position sizing,
and psychological discipline. He meditates daily and never trades during
the first 30 minutes of market open.
"""

# Three questions to test RAG retrieval
QUESTIONS = [
    "What risk management rule does Marcus follow?",
    "Where did Marcus start his trading career?",
    "What was Marcus Chen's most profitable trade?",
]

def main():
    print("=" * 60)
    print("RAG Test: Storing and Querying a Trading Story")
    print("=" * 60)

    # Step 1: Embed the story
    print("\n[1] Embedding story (~200 tokens)...")
    try:
        result = embed_text(
            text=STORY,
            doc_id="test_story_marcus_chen",
            doc_type="research",
            ticker=None,
        )
        print(f"    Embedded {result.chunk_count} chunks")
        print(f"    Document ID: {result.doc_id}")
    except Exception as e:
        print(f"    ERROR embedding: {e}")
        return 1

    # Step 2: Search with questions
    print("\n[2] Testing semantic search with 3 questions...")
    print("-" * 60)

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\nQ{i}: {question}")
        try:
            results = semantic_search(
                query=question,
                top_k=1,
                min_similarity=0.3,
            )
            if results:
                r = results[0]
                print(f"    Similarity: {r.similarity:.3f}")
                print(f"    Answer excerpt: {r.content[:150]}...")
            else:
                print("    No results found")
        except Exception as e:
            print(f"    ERROR searching: {e}")

    print("\n" + "=" * 60)
    print("RAG Test Complete")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
