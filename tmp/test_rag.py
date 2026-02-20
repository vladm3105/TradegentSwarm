#!/usr/bin/env python3
"""Test full RAG pipeline: retrieve context + generate answer with LLM."""

import sys
import requests
from pathlib import Path

# Add trader to path
sys.path.insert(0, str(Path(__file__).parent.parent / "trader"))

from rag.embed import embed_text
from rag.search import semantic_search

# LLM settings
LLM_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "llama3.2"  # Direct output, no thinking mode

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

# Three questions to test RAG
QUESTIONS = [
    "What is Marcus Chen's risk management rule?",
    "Where did Marcus Chen start his trading career?",
    "What was Marcus Chen's most profitable trade?",
]


def generate_answer(question: str, context: str) -> str:
    """Generate answer using LLM with retrieved context."""
    prompt = f"""Based only on the context below, answer the question in 1-2 sentences.

Context:
{context}

Question: {question}

Answer:"""

    try:
        response = requests.post(
            LLM_URL,
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 150},
            },
            timeout=60,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        return answer if answer else "[No answer generated]"
    except Exception as e:
        return f"[LLM Error: {e}]"


def main():
    print("=" * 70)
    print("Full RAG Test: Store → Retrieve → Generate")
    print("=" * 70)

    # Step 1: Embed the story
    print("\n[1] Embedding story (~200 tokens)...")
    try:
        result = embed_text(
            text=STORY,
            doc_id="test_story_marcus_chen",
            doc_type="research",
            ticker=None,
        )
        print(f"    Stored {result.chunk_count} chunk(s)")
        print(f"    Document ID: {result.doc_id}")
    except Exception as e:
        print(f"    ERROR embedding: {e}")
        return 1

    # Step 2: RAG Q&A
    print("\n[2] RAG Question-Answering")
    print("-" * 70)

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\nQ{i}: {question}")

        # Retrieve relevant context
        try:
            results = semantic_search(query=question, top_k=1, min_similarity=0.3)
            if not results:
                print("    [No context retrieved]")
                continue

            context = results[0].content
            similarity = results[0].similarity
            print(f"    Retrieved context (similarity: {similarity:.3f})")

            # Generate answer
            answer = generate_answer(question, context)
            print(f"    Answer: {answer}")

        except Exception as e:
            print(f"    ERROR: {e}")

    print("\n" + "=" * 70)
    print("RAG Test Complete")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
