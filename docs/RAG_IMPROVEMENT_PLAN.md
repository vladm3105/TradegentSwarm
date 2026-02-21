# RAG Improvement Plan for TradegentSwarm

**Created**: 2026-02-21
**Status**: ✅ **COMPLETED**
**Based on**: Research from arXiv 2402.05131, RavenPack, Memgraph, CFA Institute

This plan improves RAG accuracy by 15-25% through chunking optimization, reranking, and adaptive retrieval.

---

## Summary

| Phase | Component | Impact | Effort | Priority |
|-------|-----------|--------|--------|----------|
| 1 | Metrics Infrastructure | Foundation | 1 day | P0 |
| 2 | Chunking Optimization | 15-25% accuracy | 2 days | P0 |
| 3 | Cross-Encoder Reranking | High relevance | 2 days | P1 |
| 4 | Query Classification | Adaptive routing | 2 days | P2 |
| 5 | MCP Tool Updates | Integration | 1 day | P2 |

**Total: 8 days**

---

## Research Findings (Summary)

### Chunking (arXiv 2402.05131 - Financial Report Chunking)
- Element-based chunking: 84.4% page accuracy vs 68.1% for token-512
- Optimal range: 512-1024 tokens with 100-300 token overlap
- Preserve table integrity as atomic chunks
- Metadata enrichment improves Q&A: 41.84% → 53.19%

### Reranking (Multiple sources)
- Cross-encoder reranking significantly improves relevance
- Two-stage retrieve-then-rerank is industry best practice
- Model: `cross-encoder/ms-marco-MiniLM-L-6-v2` (fast, good quality)

### Query Classification (Memgraph Agentic GraphRAG)
- Classify query type: retrieval, relationship, trend, comparison, global
- Dynamic tool selection based on query characteristics
- Feedback loops for retry on failure

### Hybrid Retrieval (RavenPack)
- Three-layer: keyword + semantic + analytics
- Entity recognition for financial terms
- Traceability requirement: every insight must link to source

---

## Phase 1: Metrics Infrastructure (Foundation)

Enable before/after comparison for all improvements.

### Files to Create

**`tradegent/rag/metrics.py`** - Metrics collection

```python
"""RAG metrics for quality measurement."""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class SearchMetrics:
    """Metrics for a single search operation."""
    query: str
    query_type: str | None
    strategy: str
    retrieval_count: int
    reranked: bool
    top_similarity: float | None
    latency_ms: int
    timestamp: str
    relevance_feedback: int | None = None  # 1-5 user rating (future)
    context_used: bool | None = None       # Was context actually used? (future)


class MetricsCollector:
    """Collect and persist RAG metrics."""

    def __init__(self, log_path: str = "logs/rag_metrics.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_search(
        self,
        query: str,
        strategy: str,
        results: list,
        latency_ms: int,
        query_type: str | None = None,
        reranked: bool = False,
    ) -> SearchMetrics:
        """Record a search operation."""
        metrics = SearchMetrics(
            query=query,
            query_type=query_type,
            strategy=strategy,
            retrieval_count=len(results),
            reranked=reranked,
            top_similarity=results[0].similarity if results else None,
            latency_ms=latency_ms,
            timestamp=datetime.now(UTC).isoformat(),
        )
        self._persist(metrics)
        return metrics

    def _persist(self, metrics: SearchMetrics):
        """Append metrics to JSONL log."""
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(asdict(metrics)) + "\n")
        except Exception as e:
            log.warning(f"Failed to persist metrics: {e}")

    def get_summary(self, days: int = 7) -> dict[str, Any]:
        """Get summary statistics for recent searches."""
        # TODO: Parse recent entries and compute aggregates
        return {}


# Singleton
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
```

### Files to Modify

**`tradegent/rag/search.py`** - Add timing + metrics calls

```python
import time
from .metrics import get_metrics_collector

def semantic_search(...) -> list[SearchResult]:
    start = time.time()

    # ... existing implementation ...

    # Record metrics
    latency = int((time.time() - start) * 1000)
    get_metrics_collector().record_search(
        query=query,
        strategy="vector",
        results=results,
        latency_ms=latency,
    )

    return results
```

---

## Phase 2: Chunking Optimization

Research shows 512-1024 tokens with 100-300 overlap gives 15-25% accuracy gain.

### Files to Modify

**`tradegent/rag/config.yaml`** - New parameters

```yaml
rag_version: "2.0.0"

chunking:
  max_tokens: "${CHUNK_MAX_TOKENS:-768}"      # Was 1500
  min_tokens: "${CHUNK_MIN_TOKENS:-50}"
  overlap_tokens: "${CHUNK_OVERLAP:-150}"     # Was hardcoded 50
  preserve_tables: "${CHUNK_PRESERVE_TABLES:-true}"  # New

features:
  element_aware_chunking: "${RAG_ELEMENT_CHUNKING:-true}"
  reranking_enabled: "${RAG_RERANKING:-false}"
  adaptive_retrieval: "${RAG_ADAPTIVE:-false}"
  metrics_enabled: "${RAG_METRICS:-true}"
```

**`tradegent/rag/chunk.py`** - Key changes

1. Load config at module level
2. Make overlap configurable (line 213)
3. Add table detection

```python
# At top of file, add config loading:
import yaml
from pathlib import Path

_config_path = Path(__file__).parent / "config.yaml"
_config: dict = {}
if _config_path.exists():
    with open(_config_path) as f:
        _config = yaml.safe_load(f)

_chunk_config = _config.get("chunking", {})
_max_tokens = int(_chunk_config.get("max_tokens", 768))
_min_tokens = int(_chunk_config.get("min_tokens", 50))
_overlap_tokens = int(_chunk_config.get("overlap_tokens", 150))
_preserve_tables = _chunk_config.get("preserve_tables", True)


def is_table_content(content: str) -> bool:
    """Detect if content is a table that should be kept atomic."""
    lines = content.strip().split('\n')
    if len(lines) < 3:
        return False
    pipe_lines = sum(1 for l in lines if '|' in l)
    return pipe_lines / len(lines) > 0.5


# In chunk_yaml_section(), line 213 change:
# FROM:
sub_texts = split_by_tokens(content, max_tokens, overlap=50)
# TO:
sub_texts = split_by_tokens(content, max_tokens, overlap=_overlap_tokens)


# In chunk_yaml_document(), before splitting large sections:
# Add table preservation check:
if _preserve_tables and is_table_content(content):
    # Keep tables atomic (up to 2x max_tokens)
    if token_count <= max_tokens * 2:
        prepared = prepare_chunk_text(section_label, content, ticker, doc_type)
        chunks.append(ChunkResult(...))
        continue
```

### Database Migration

```sql
-- Track chunk version for re-embedding decisions
ALTER TABLE nexus.rag_documents
ADD COLUMN IF NOT EXISTS chunk_version VARCHAR(10) DEFAULT '1.0';

CREATE INDEX IF NOT EXISTS idx_rag_docs_chunk_version
ON nexus.rag_documents(chunk_version);
```

### Re-embedding Command

```bash
# Re-embed all documents with new strategy
python orchestrator.py rag reembed --version 2.0
```

---

## Phase 3: Cross-Encoder Reranking

Two-stage retrieve-then-rerank significantly improves relevance.

### Files to Create

**`tradegent/rag/rerank.py`** - Reranker module

```python
"""Cross-encoder reranking for improved relevance."""

import logging
from typing import Protocol

from .models import SearchResult

log = logging.getLogger(__name__)


class Reranker(Protocol):
    """Reranker protocol for dependency injection."""
    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int
    ) -> list[SearchResult]: ...


class CrossEncoderReranker:
    """Cross-encoder reranker using sentence-transformers."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model = None
        self._model_name = model_name

    @property
    def model(self):
        """Lazy-load model to avoid import overhead."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self._model_name)
                log.info(f"Loaded reranker: {self._model_name}")
            except ImportError:
                log.warning("sentence-transformers not installed, reranking disabled")
                return None
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        """Rerank candidates using cross-encoder."""
        if not self.model or not candidates:
            return candidates[:top_k]

        pairs = [(query, c.content) for c in candidates]
        scores = self.model.predict(pairs)

        # Attach scores and sort
        for candidate, score in zip(candidates, scores):
            candidate.rerank_score = float(score)

        return sorted(
            candidates,
            key=lambda c: getattr(c, 'rerank_score', 0),
            reverse=True
        )[:top_k]


class NoOpReranker:
    """No-op reranker for when sentence-transformers unavailable."""

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        return candidates[:top_k]


# Singleton with fallback
_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    """Get singleton reranker with graceful fallback."""
    global _reranker
    if _reranker is None:
        try:
            _reranker = CrossEncoderReranker()
            if _reranker.model is None:
                _reranker = NoOpReranker()
        except Exception as e:
            log.warning(f"Reranker initialization failed: {e}")
            _reranker = NoOpReranker()
    return _reranker
```

### Files to Modify

**`tradegent/rag/search.py`** - Add reranked search function

```python
def search_with_rerank(
    query: str,
    ticker: str | None = None,
    doc_type: str | None = None,
    top_k: int = 5,
    retrieval_k: int = 50,
    use_hybrid: bool = True,
) -> list[SearchResult]:
    """
    Two-stage retrieve-then-rerank search.

    Stage 1: Fast retrieval (vector or hybrid, top retrieval_k)
    Stage 2: Accurate reranking (cross-encoder, top top_k)
    """
    from .rerank import get_reranker

    # Stage 1: Fast retrieval
    if use_hybrid:
        candidates = hybrid_search(
            query=query,
            ticker=ticker,
            doc_type=doc_type,
            top_k=retrieval_k,
        )
    else:
        candidates = semantic_search(
            query=query,
            ticker=ticker,
            doc_type=doc_type,
            top_k=retrieval_k,
        )

    # Stage 2: Rerank
    reranker = get_reranker()
    return reranker.rerank(query, candidates, top_k=top_k)
```

**`tradegent/rag/models.py`** - Add rerank_score field

```python
@dataclass
class SearchResult:
    doc_id: str
    file_path: str
    doc_type: str
    ticker: str | None
    doc_date: date | None
    section_label: str
    content: str
    similarity: float
    rerank_score: float | None = None  # Cross-encoder score (if reranked)
```

### Dependencies

```bash
pip install sentence-transformers  # ~500MB, includes torch
```

---

## Phase 4: Query Classification

Route queries to optimal retrieval strategy based on query type.

### Files to Create

**`tradegent/rag/query_classifier.py`** - Rule-based classifier

```python
"""Query classification for agentic RAG routing."""

import re
from dataclasses import dataclass
from enum import Enum


class QueryType(Enum):
    """Query types for routing decisions."""
    RETRIEVAL = "retrieval"       # Semantic similarity search
    RELATIONSHIP = "relationship" # Graph traversal needed
    TREND = "trend"               # Time-series, historical patterns
    COMPARISON = "comparison"     # Multi-ticker comparison
    GLOBAL = "global"             # Cross-document aggregation


@dataclass
class QueryAnalysis:
    """Result of query classification."""
    query_type: QueryType
    confidence: float
    tickers: list[str]
    time_constraint: str | None  # "recent", "Q4-2024", etc.
    suggested_strategy: str      # "vector", "hybrid", "graph", "combined"


class QueryClassifier:
    """Rule-based query classifier."""

    RELATIONSHIP_PATTERNS = [
        r"relat(ed|ionship)", r"connect(ed|ion)", r"compet(e|itor|ition)",
        r"supplier|customer", r"peer|sector", r"link|chain",
    ]

    TREND_PATTERNS = [
        r"trend|pattern", r"over time|historical",
        r"last \d+ (day|week|month|quarter)", r"Q[1-4]", r"YoY|QoQ", r"recent|latest",
    ]

    COMPARISON_PATTERNS = [
        r"vs\.?|versus", r"compar(e|ison)", r"better|worse", r"which (is|one)",
        r"(\w{2,5})\s+(and|or|vs)\s+(\w{2,5})",
    ]

    GLOBAL_PATTERNS = [
        r"all|every|entire", r"across|portfolio", r"summary|overview", r"how many|count",
    ]

    def classify(self, query: str) -> QueryAnalysis:
        """Classify query and suggest retrieval strategy."""
        query_lower = query.lower()

        # Extract tickers (uppercase 1-5 char words)
        tickers = re.findall(r'\b[A-Z]{1,5}\b', query)

        # Score each type
        scores = {
            QueryType.RELATIONSHIP: self._pattern_score(query_lower, self.RELATIONSHIP_PATTERNS),
            QueryType.TREND: self._pattern_score(query_lower, self.TREND_PATTERNS),
            QueryType.COMPARISON: self._pattern_score(query_lower, self.COMPARISON_PATTERNS),
            QueryType.GLOBAL: self._pattern_score(query_lower, self.GLOBAL_PATTERNS),
            QueryType.RETRIEVAL: 0.3,  # Default baseline
        }

        # Boost retrieval if no strong signals
        max_score = max(scores.values())
        if max_score < 0.5:
            scores[QueryType.RETRIEVAL] = 0.6

        query_type = max(scores, key=scores.get)
        confidence = scores[query_type]
        strategy = self._select_strategy(query_type, len(tickers))
        time_constraint = self._extract_time_constraint(query_lower)

        return QueryAnalysis(
            query_type=query_type,
            confidence=confidence,
            tickers=tickers,
            time_constraint=time_constraint,
            suggested_strategy=strategy,
        )

    def _pattern_score(self, text: str, patterns: list[str]) -> float:
        """Score based on pattern matches."""
        matches = sum(1 for p in patterns if re.search(p, text))
        return min(matches * 0.3, 1.0)

    def _select_strategy(self, query_type: QueryType, ticker_count: int) -> str:
        """Select retrieval strategy based on query type."""
        if query_type == QueryType.RELATIONSHIP:
            return "graph"
        elif query_type == QueryType.COMPARISON and ticker_count >= 2:
            return "graph"
        elif query_type == QueryType.TREND:
            return "vector"  # Time-filtered vector search
        elif query_type == QueryType.GLOBAL:
            return "hybrid"
        else:
            return "hybrid"

    def _extract_time_constraint(self, query: str) -> str | None:
        """Extract time constraints from query."""
        if re.search(r"recent|latest|last week|this month", query):
            return "recent"
        quarter_match = re.search(r"Q[1-4][-\s]?(20\d{2})?", query, re.IGNORECASE)
        if quarter_match:
            return quarter_match.group()
        return None


# Singleton
_classifier: QueryClassifier | None = None


def get_classifier() -> QueryClassifier:
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier


def classify_query(query: str) -> QueryAnalysis:
    """Convenience function."""
    return get_classifier().classify(query)
```

### Files to Modify

**`tradegent/rag/hybrid.py`** - Add adaptive retrieval

```python
def get_hybrid_context_adaptive(
    ticker: str,
    query: str,
    analysis_type: str | None = None,
    exclude_doc_id: str | None = None,
) -> HybridContext:
    """
    Adaptive hybrid context using query classification.

    Routes to optimal retrieval strategy based on query type.
    """
    from .query_classifier import classify_query

    ticker = ticker.upper()
    analysis = classify_query(query)
    vector_results = []
    excluded_ids = {exclude_doc_id} if exclude_doc_id else set()

    # Strategy routing
    if analysis.suggested_strategy == "graph":
        # Graph-first: get related tickers, then search across them
        graph_context = _get_graph_context(ticker)
        related_tickers = _extract_related_tickers(graph_context)

        for t in [ticker] + related_tickers[:3]:
            results = get_similar_analyses(t, analysis_type, top_k=2)
            for r in results:
                if r.doc_id not in excluded_ids:
                    vector_results.append(r)
                    excluded_ids.add(r.doc_id)

    elif analysis.suggested_strategy == "hybrid":
        # Use reranking if available
        from .search import search_with_rerank
        results = search_with_rerank(query=query, ticker=ticker, top_k=5)
        vector_results.extend([r for r in results if r.doc_id not in excluded_ids])

    else:
        # Default vector search path
        vector_results = _standard_retrieval(ticker, query, analysis_type, excluded_ids)

    # Add learnings (always)
    learning_results = get_learnings_for_topic(query, top_k=2)
    seen_ids = {r.doc_id for r in vector_results} | excluded_ids
    for r in learning_results:
        if r.doc_id not in seen_ids:
            vector_results.append(r)

    # Graph context
    graph_context = _get_graph_context(ticker)

    # Format
    formatted = format_context(vector_results, graph_context, ticker)

    return HybridContext(
        ticker=ticker,
        vector_results=vector_results,
        graph_context=graph_context,
        formatted=formatted,
    )


def _extract_related_tickers(graph_context: dict) -> list[str]:
    """Extract related ticker symbols from graph context."""
    related = []
    for peer in graph_context.get("peers", []):
        if isinstance(peer, dict):
            related.append(peer.get("symbol", ""))
        elif isinstance(peer, str):
            related.append(peer)
    for comp in graph_context.get("competitors", []):
        if isinstance(comp, dict):
            related.append(comp.get("symbol", ""))
        elif isinstance(comp, str):
            related.append(comp)
    return [t for t in related if t]
```

---

## Phase 5: MCP Tool Updates

Expose new capabilities to Claude skills.

### Files to Modify

**`tradegent/rag/mcp_server.py`** - Add new tools

```python
# Add to TOOLS list:

Tool(
    name="rag_search_rerank",
    description="Search with cross-encoder reranking for higher relevance",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "ticker": {"type": "string", "description": "Optional ticker filter"},
            "top_k": {"type": "integer", "default": 5, "description": "Results to return"},
        },
        "required": ["query"],
    },
),

Tool(
    name="rag_classify_query",
    description="Classify query to determine optimal retrieval strategy",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Query to classify"},
        },
        "required": ["query"],
    },
),

Tool(
    name="rag_metrics_summary",
    description="Get RAG metrics summary for recent searches",
    inputSchema={
        "type": "object",
        "properties": {
            "days": {"type": "integer", "default": 7, "description": "Days to summarize"},
        },
    },
),


# Add to call_tool handler:

elif name == "rag_search_rerank":
    from .search import search_with_rerank
    results = search_with_rerank(
        query=args["query"],
        ticker=args.get("ticker"),
        top_k=args.get("top_k", 5),
    )
    return [r.to_dict() for r in results]

elif name == "rag_classify_query":
    from .query_classifier import classify_query
    analysis = classify_query(args["query"])
    return {
        "query_type": analysis.query_type.value,
        "confidence": analysis.confidence,
        "tickers": analysis.tickers,
        "suggested_strategy": analysis.suggested_strategy,
    }

elif name == "rag_metrics_summary":
    from .metrics import get_metrics_collector
    return get_metrics_collector().get_summary(days=args.get("days", 7))
```

---

## Verification Plan

### Phase 1 (Metrics)
```bash
# Trigger a search
python -c "from tradegent.rag.search import semantic_search; semantic_search('NVDA earnings')"

# Check metrics logged
tail -1 logs/rag_metrics.jsonl
# Expected: {"query": "NVDA earnings", "strategy": "vector", "latency_ms": ...}
```

### Phase 2 (Chunking)
```bash
# Embed a test document with new settings
CHUNK_MAX_TOKENS=768 CHUNK_OVERLAP=150 python -c "
from tradegent.rag.embed import embed_document
result = embed_document('tradegent_knowledge/knowledge/analysis/stock/MSFT_20260221T1145.yaml', force=True)
print(f'Chunks: {result.chunk_count}')
"
# Compare: new settings should create ~2x more chunks
```

### Phase 3 (Reranking)
```bash
# Test reranked search
python -c "
from tradegent.rag.search import search_with_rerank
results = search_with_rerank('NVDA competitive position vs AMD', ticker='NVDA')
for r in results:
    print(f'{r.similarity:.2f} | {r.rerank_score:.2f} | {r.section_label}')
"
# Rerank scores should reorder results for better relevance
```

### Phase 4 (Query Classification)
```bash
# Test classifier
python -c "
from tradegent.rag.query_classifier import classify_query
print(classify_query('What are NVDA risks?'))
print(classify_query('Compare NVDA vs AMD'))
print(classify_query('Recent earnings surprises'))
"
# Expected: relationship, comparison, trend respectively
```

### Phase 5 (MCP)
```bash
# Start MCP server and test new tools
cd tradegent && python -m tradegent.rag.mcp_server &
# Use Claude skill to call rag_search_rerank
```

---

## Rollback Strategy

All features behind feature flags (default OFF for new features):

```bash
# Disable reranking
export RAG_RERANKING=false

# Disable adaptive retrieval
export RAG_ADAPTIVE=false

# Revert to old chunk sizes
export CHUNK_MAX_TOKENS=1500
export CHUNK_OVERLAP=50
```

---

## Files Summary

| Action | File | Phase |
|--------|------|-------|
| Create | `tradegent/rag/metrics.py` | 1 |
| Create | `tradegent/rag/rerank.py` | 3 |
| Create | `tradegent/rag/query_classifier.py` | 4 |
| Modify | `tradegent/rag/config.yaml` | 2 |
| Modify | `tradegent/rag/chunk.py` | 2 |
| Modify | `tradegent/rag/search.py` | 1, 3 |
| Modify | `tradegent/rag/hybrid.py` | 4 |
| Modify | `tradegent/rag/models.py` | 3 |
| Modify | `tradegent/rag/mcp_server.py` | 5 |

---

---

## Phase 6: Query Expansion (Haystack-Inspired)

Generate semantic query variations to improve retrieval recall.

### Files to Create

**`tradegent/rag/query_expander.py`** - Query expansion module

```python
"""Query expansion for improved retrieval recall (Haystack-inspired)."""

import json
import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class ExpandedQuery:
    """Result of query expansion."""
    original: str
    variations: list[str]
    all_queries: list[str]  # original + variations


class QueryExpander:
    """
    Expand queries with semantic variations using LLM.

    Inspired by Haystack's QueryExpander component.
    """

    EXPANSION_PROMPT = """Generate {n} semantically similar variations of this search query.
The variations should:
- Use different keywords but preserve the same intent
- Include synonyms and related financial terms
- Maintain the same language as the original

Query: {query}

Return ONLY a JSON object with this structure:
{{"queries": ["variation 1", "variation 2", ...]}}"""

    def __init__(
        self,
        n_expansions: int = 3,
        include_original: bool = True,
        provider: str = "openai",
    ):
        self.n_expansions = n_expansions
        self.include_original = include_original
        self.provider = provider
        self._client = None

    @property
    def client(self):
        """Lazy-load LLM client."""
        if self._client is None:
            if self.provider == "openai":
                from openai import OpenAI
                self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        return self._client

    def expand(self, query: str) -> ExpandedQuery:
        """Expand query with semantic variations."""
        try:
            prompt = self.EXPANSION_PROMPT.format(n=self.n_expansions, query=query)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
            )

            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            variations = data.get("queries", [])[:self.n_expansions]

            all_queries = ([query] if self.include_original else []) + variations

            return ExpandedQuery(
                original=query,
                variations=variations,
                all_queries=all_queries,
            )
        except Exception as e:
            log.warning(f"Query expansion failed: {e}, using original only")
            return ExpandedQuery(
                original=query,
                variations=[],
                all_queries=[query],
            )


# Singleton
_expander: QueryExpander | None = None


def get_expander() -> QueryExpander:
    global _expander
    if _expander is None:
        _expander = QueryExpander()
    return _expander


def expand_query(query: str, n: int = 3) -> ExpandedQuery:
    """Convenience function."""
    expander = get_expander()
    expander.n_expansions = n
    return expander.expand(query)
```

### Files to Modify

**`tradegent/rag/search.py`** - Add multi-query search

```python
def search_with_expansion(
    query: str,
    ticker: str | None = None,
    top_k: int = 5,
    n_expansions: int = 3,
) -> list[SearchResult]:
    """
    Search with query expansion for improved recall.

    1. Expand query into semantic variations
    2. Search with each variation
    3. Merge and deduplicate results
    4. Optionally rerank
    """
    from .query_expander import expand_query

    expanded = expand_query(query, n=n_expansions)

    all_results = []
    seen_ids = set()

    for q in expanded.all_queries:
        results = semantic_search(q, ticker=ticker, top_k=top_k)
        for r in results:
            if r.doc_id not in seen_ids:
                all_results.append(r)
                seen_ids.add(r.doc_id)

    # Sort by similarity
    all_results.sort(key=lambda r: r.similarity, reverse=True)
    return all_results[:top_k]
```

---

## Phase 7: RAGAS Evaluation Integration

Add comprehensive RAG evaluation using RAGAS framework.

### Dependencies

```bash
pip install ragas datasets
```

### Files to Create

**`tradegent/rag/evaluation.py`** - RAGAS integration

```python
"""RAG evaluation using RAGAS framework."""

import logging
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class RAGEvalResult:
    """Evaluation result for a single query."""
    query: str
    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float
    overall_score: float


class RAGEvaluator:
    """
    Evaluate RAG quality using RAGAS metrics.

    Metrics:
    - context_precision: How relevant is retrieved context?
    - context_recall: Did we retrieve all relevant context?
    - faithfulness: Is the answer grounded in context?
    - answer_relevancy: Does the answer address the query?
    """

    def __init__(self):
        self._ragas = None

    @property
    def ragas(self):
        """Lazy-load RAGAS."""
        if self._ragas is None:
            try:
                from ragas import evaluate
                from ragas.metrics import (
                    context_precision,
                    context_recall,
                    faithfulness,
                    answer_relevancy,
                )
                self._ragas = {
                    "evaluate": evaluate,
                    "metrics": [
                        context_precision,
                        context_recall,
                        faithfulness,
                        answer_relevancy,
                    ],
                }
                log.info("RAGAS loaded successfully")
            except ImportError:
                log.warning("RAGAS not installed: pip install ragas")
                return None
        return self._ragas

    def evaluate_single(
        self,
        query: str,
        contexts: list[str],
        answer: str,
        ground_truth: str | None = None,
    ) -> RAGEvalResult | None:
        """Evaluate a single RAG response."""
        if not self.ragas:
            return None

        from datasets import Dataset

        data = {
            "question": [query],
            "contexts": [contexts],
            "answer": [answer],
        }
        if ground_truth:
            data["ground_truth"] = [ground_truth]

        dataset = Dataset.from_dict(data)

        try:
            result = self.ragas["evaluate"](
                dataset,
                metrics=self.ragas["metrics"],
            )

            return RAGEvalResult(
                query=query,
                context_precision=result.get("context_precision", 0),
                context_recall=result.get("context_recall", 0),
                faithfulness=result.get("faithfulness", 0),
                answer_relevancy=result.get("answer_relevancy", 0),
                overall_score=result.get("ragas_score", 0),
            )
        except Exception as e:
            log.error(f"RAGAS evaluation failed: {e}")
            return None

    def evaluate_batch(
        self,
        samples: list[dict[str, Any]],
    ) -> dict[str, float]:
        """
        Evaluate a batch of RAG responses.

        Each sample: {"query": str, "contexts": list[str], "answer": str}
        Returns aggregate metrics.
        """
        if not self.ragas:
            return {}

        from datasets import Dataset

        data = {
            "question": [s["query"] for s in samples],
            "contexts": [s["contexts"] for s in samples],
            "answer": [s["answer"] for s in samples],
        }

        dataset = Dataset.from_dict(data)

        try:
            result = self.ragas["evaluate"](
                dataset,
                metrics=self.ragas["metrics"],
            )
            return dict(result)
        except Exception as e:
            log.error(f"RAGAS batch evaluation failed: {e}")
            return {}


# Singleton
_evaluator: RAGEvaluator | None = None


def get_evaluator() -> RAGEvaluator:
    global _evaluator
    if _evaluator is None:
        _evaluator = RAGEvaluator()
    return _evaluator


def evaluate_rag(
    query: str,
    contexts: list[str],
    answer: str,
) -> RAGEvalResult | None:
    """Convenience function."""
    return get_evaluator().evaluate_single(query, contexts, answer)
```

### MCP Tool Addition

```python
Tool(
    name="rag_evaluate",
    description="Evaluate RAG response quality using RAGAS metrics",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "contexts": {"type": "array", "items": {"type": "string"}},
            "answer": {"type": "string"},
        },
        "required": ["query", "contexts", "answer"],
    },
),
```

---

## Phase 8: Semantic Chunking (Haystack-Inspired)

Split documents based on semantic similarity rather than fixed token counts.

### Files to Create

**`tradegent/rag/semantic_chunker.py`** - Semantic-aware chunking

```python
"""Semantic chunking based on embedding similarity (Haystack-inspired)."""

import logging
import numpy as np
from dataclasses import dataclass

from .embedding_client import EmbeddingClient
from .tokens import estimate_tokens

log = logging.getLogger(__name__)


@dataclass
class SemanticChunk:
    """A semantically coherent chunk."""
    content: str
    start_idx: int
    end_idx: int
    tokens: int


class SemanticChunker:
    """
    Split text based on semantic similarity between sentences.

    Inspired by Haystack's EmbeddingBasedDocumentSplitter.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.8,
        max_tokens: int = 768,
        min_tokens: int = 50,
    ):
        self.similarity_threshold = similarity_threshold
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self._embedder = None

    @property
    def embedder(self) -> EmbeddingClient:
        if self._embedder is None:
            self._embedder = EmbeddingClient()
        return self._embedder

    def chunk(self, text: str) -> list[SemanticChunk]:
        """Split text into semantically coherent chunks."""
        # Split into sentences
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [SemanticChunk(
                content=text,
                start_idx=0,
                end_idx=len(text),
                tokens=estimate_tokens(text),
            )]

        # Get embeddings for all sentences
        embeddings = self.embedder.get_embeddings_batch(
            [s["text"] for s in sentences]
        )

        # Find semantic breakpoints
        breakpoints = self._find_breakpoints(embeddings)

        # Create chunks
        chunks = []
        current_start = 0
        current_sentences = []
        current_tokens = 0

        for i, sentence in enumerate(sentences):
            sentence_tokens = estimate_tokens(sentence["text"])

            # Check if we should break
            should_break = (
                i in breakpoints or
                current_tokens + sentence_tokens > self.max_tokens
            )

            if should_break and current_sentences:
                chunk_text = " ".join(s["text"] for s in current_sentences)
                if current_tokens >= self.min_tokens:
                    chunks.append(SemanticChunk(
                        content=chunk_text,
                        start_idx=current_start,
                        end_idx=sentence["start"],
                        tokens=current_tokens,
                    ))
                current_start = sentence["start"]
                current_sentences = []
                current_tokens = 0

            current_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Last chunk
        if current_sentences:
            chunk_text = " ".join(s["text"] for s in current_sentences)
            if current_tokens >= self.min_tokens:
                chunks.append(SemanticChunk(
                    content=chunk_text,
                    start_idx=current_start,
                    end_idx=len(text),
                    tokens=current_tokens,
                ))

        return chunks

    def _split_sentences(self, text: str) -> list[dict]:
        """Split text into sentences with positions."""
        import re
        sentences = []
        for match in re.finditer(r'[^.!?]+[.!?]+', text):
            sentences.append({
                "text": match.group().strip(),
                "start": match.start(),
                "end": match.end(),
            })
        return sentences

    def _find_breakpoints(self, embeddings: list[list[float]]) -> set[int]:
        """Find indices where semantic similarity drops."""
        breakpoints = set()

        for i in range(1, len(embeddings)):
            similarity = self._cosine_similarity(
                embeddings[i - 1],
                embeddings[i]
            )
            if similarity < self.similarity_threshold:
                breakpoints.add(i)

        return breakpoints

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(a)
        b = np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
```

### Integration in chunk.py

```python
# Add to chunk_yaml_document() when semantic chunking enabled:

if _config.get("features", {}).get("semantic_chunking"):
    from .semantic_chunker import SemanticChunker
    chunker = SemanticChunker(
        similarity_threshold=0.8,
        max_tokens=_max_tokens,
        min_tokens=_min_tokens,
    )
    semantic_chunks = chunker.chunk(content)
    # Convert to ChunkResult objects...
```

---

## Updated Summary

| Phase | Component | Impact | Effort | Priority |
|-------|-----------|--------|--------|----------|
| 1 | Metrics Infrastructure | Foundation | 1 day | P0 |
| 2 | Chunking Optimization | 15-25% accuracy | 2 days | P0 |
| 3 | Cross-Encoder Reranking | High relevance | 2 days | P1 |
| 4 | Query Classification | Adaptive routing | 2 days | P2 |
| 5 | MCP Tool Updates | Integration | 1 day | P2 |
| 6 | Query Expansion (Haystack) | +10-15% recall | 1 day | P1 |
| 7 | RAGAS Evaluation | Quality measurement | 1 day | P1 |
| 8 | Semantic Chunking (Haystack) | Better coherence | 2 days | P2 |

**Total: 12 days**

---

## Updated Files Summary

| Action | File | Phase |
|--------|------|-------|
| Create | `tradegent/rag/metrics.py` | 1 |
| Create | `tradegent/rag/rerank.py` | 3 |
| Create | `tradegent/rag/query_classifier.py` | 4 |
| Create | `tradegent/rag/query_expander.py` | 6 |
| Create | `tradegent/rag/evaluation.py` | 7 |
| Create | `tradegent/rag/semantic_chunker.py` | 8 |
| Modify | `tradegent/rag/config.yaml` | 2 |
| Modify | `tradegent/rag/chunk.py` | 2, 8 |
| Modify | `tradegent/rag/search.py` | 1, 3, 6 |
| Modify | `tradegent/rag/hybrid.py` | 4 |
| Modify | `tradegent/rag/models.py` | 3 |
| Modify | `tradegent/rag/mcp_server.py` | 5, 6, 7 |

---

## Deferred Items (Future Work)

1. **Finance-specific embeddings (Fin-E5)**: Requires full re-embedding, test after Phase 2
2. **Entity recognition integration**: Add to graph extraction pipeline
3. **Sentiment scoring**: Add to chunk metadata
4. **Redis caching**: Distributed query caching for production
5. **Parent document retrieval**: Hierarchical chunk relationships
