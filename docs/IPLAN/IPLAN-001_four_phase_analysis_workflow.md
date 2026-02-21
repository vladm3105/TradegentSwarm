# IPLAN-001: Four-Phase Analysis Workflow

**Status**: Implemented
**Created**: 2026-02-20
**Implemented**: 2026-02-20
**Author**: Claude Code

---

## Implementation Summary

All phases implemented and verified. The 4-phase workflow is controlled by the `four_phase_analysis_enabled` feature flag (default: `true`).

### Files Modified

| File | Changes |
|------|---------|
| `tradegent/orchestrator.py` | Added 12 new functions, `SynthesisContext` dataclass, `CONFIDENCE_MODIFIERS` constants |
| `tradegent/db/init.sql` | Added `four_phase_analysis_enabled` feature flag |
| `tradegent/db/migrations/002_adjusted_confidence.sql` | New migration for adjusted confidence columns |
| `tradegent/rag/hybrid.py` | Added `exclude_doc_id` parameter to `get_hybrid_context()` |

### Functions Implemented

| Function | Purpose |
|----------|---------|
| `_run_with_timeout()` | Execute functions with timeout protection |
| `_phase1_fresh_analysis()` | Run analysis WITHOUT KB context (unbiased) |
| `_phase2_dual_ingest()` | Index to BOTH Graph AND RAG |
| `_enrich_past_analyses()` | Add recommendation/confidence from database |
| `_phase3_retrieve_history()` | Retrieve historical context AFTER indexing |
| `_check_pattern_consistency()` | Compare current vs historical sentiment |
| `_calculate_adjusted_confidence()` | Apply confidence modifiers |
| `_get_pattern_description()` | Generate pattern alignment description |
| `_format_synthesis_section()` | Format markdown comparison table |
| `_phase4_synthesize()` | Generate synthesis section and append to file |
| `_update_analysis_confidence()` | Update database with adjusted confidence |
| `_run_analysis_4phase()` | Main 4-phase orchestration |
| `_legacy_run_analysis()` | Preserved original workflow |

### Usage

The 4-phase workflow is **enabled by default**. To run an analysis:

```bash
# Run analysis (4-phase workflow active by default)
python orchestrator.py analyze NVDA --type stock

# Verify output has synthesis section
grep "Historical Comparison" analyses/NVDA_stock_*.md

# To disable and use legacy workflow:
python orchestrator.py settings set four_phase_analysis_enabled false
```

---

## Problem Statement

The current analysis workflow retrieves historical context BEFORE running analysis, which biases the fresh analysis:

```
CURRENT: Historical → Analysis (biased) → Index (RAG only)
DESIRED: Fresh Analysis → Index (Graph+RAG) → Historical → Synthesis
```

**Key Issues:**
1. Historical context injected into prompt BEFORE analysis (introduces bias)
2. `kb_ingest_analysis()` only calls RAG embedding, NOT graph extraction
3. No synthesis step to compare current analysis with historical patterns

---

## Proposed 4-Phase Workflow

```
Phase 1: FRESH ANALYSIS     Phase 2: INDEX           Phase 3: RETRIEVE        Phase 4: SYNTHESIZE
─────────────────────────   ─────────────────────    ─────────────────────    ─────────────────────
│ Run analysis WITHOUT  │   │ Graph extraction  │   │ RAG semantic search │   │ Compare current vs │
│ KB context injection  │──▶│ + RAG embedding   │──▶│ + Graph context     │──▶│ historical         │
│ (unbiased)            │   │ (BOTH systems)    │   │ (past data)         │   │ Final synthesis    │
─────────────────────────   ─────────────────────    ─────────────────────    ─────────────────────
     Output: YAML               Output: indexed         Output: context          Output: synthesis
     (fresh analysis)           (both systems)          (historical data)        appended to file
```

---

## Implementation Approach

**Single `run_analysis()` call with 4 internal phases** (not 4 separate calls)

Rationale:
- Maintains backward compatibility with existing CLI and schedules
- Single transaction semantics for database tracking
- Easier error handling and rollback
- Feature flag `four_phase_analysis_enabled` to enable/disable

---

## Files to Modify

### 1. `tradegent/orchestrator.py`

**New Functions to Add:**

| Function | Purpose | Lines |
|----------|---------|-------|
| `_phase1_fresh_analysis()` | Run analysis with `kb_enabled=False` | New |
| `_phase2_dual_ingest()` | Call both graph extraction AND RAG embedding | New |
| `_phase3_retrieve_history()` | Get historical context after indexing | New |
| `_phase4_synthesize()` | Compare current vs historical, append to file | New |
| `_format_synthesis_section()` | Generate markdown comparison table | New |

**Functions to Modify:**

| Function | Change | Lines |
|----------|--------|-------|
| `run_analysis()` | Add 4-phase workflow with feature flag check | L613-691 |
| `Settings` class | Add `four_phase_analysis_enabled` property | ~L160 |

**Implementation Details:**

```python
# Add to Settings class (~L160)
@property
def four_phase_analysis_enabled(self) -> bool:
    """Enable 4-phase workflow: fresh → index → retrieve → synthesize."""
    return self._get_bool("four_phase_analysis_enabled", None, True)  # Default: enabled


# Modified run_analysis() flow
def run_analysis(db, ticker, analysis_type, schedule_id=None):
    if cfg.four_phase_analysis_enabled:
        # Phase 1: Fresh analysis (no KB context)
        result = _phase1_fresh_analysis(db, ticker, analysis_type, schedule_id)
        if not result:
            return None

        # Phase 2: Dual ingest (Graph + RAG)
        _phase2_dual_ingest(result.filepath)

        # Phase 3: Retrieve historical context
        historical_context = _phase3_retrieve_history(ticker, analysis_type)

        # Phase 4: Synthesize and append
        _phase4_synthesize(result, historical_context)

        return result
    else:
        # Legacy workflow (backward compatible)
        return _legacy_run_analysis(db, ticker, analysis_type, schedule_id)
```

### 2. `tradegent/db/init.sql`

**Add new setting:**

```sql
INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('four_phase_analysis_enabled', 'true', 'feature_flags',
     'Enable 4-phase workflow: fresh → index → retrieve → synthesize')
ON CONFLICT (key) DO NOTHING;
```

### 3. `tradegent/rag/hybrid.py`

**Modify `get_hybrid_context()` (L11):**

```python
def get_hybrid_context(
    ticker: str,
    query: str,
    analysis_type: str | None = None,
    exclude_doc_id: str | None = None,  # NEW: Prevent self-retrieval
) -> HybridContext:
```

### 4. `.claude/skills/earnings-analysis.md` and `stock-analysis.md`

**Update workflow section:**
- Remove "Get Historical Context" as Step 1
- Move it after "Index to Knowledge Base" (Phase 3)
- Add "Synthesize" section (Phase 4)

---

## New Data Structures

```python
@dataclass
class SynthesisContext:
    """Historical context for Phase 4 synthesis."""
    ticker: str
    past_analyses: list[dict]      # From RAG semantic search
    graph_context: dict            # From TradingGraph.get_ticker_context()
    bias_warnings: list[dict]      # From get_bias_warnings()
    strategy_recommendations: list[dict]  # From get_strategy_recommendations()

    # NEW: History availability flags
    has_history: bool = False      # True if any past analyses found
    history_count: int = 0         # Number of past analyses
    has_graph_data: bool = False   # True if graph context populated

    @property
    def is_first_analysis(self) -> bool:
        """True if this is the first analysis for this ticker."""
        return not self.has_history and not self.has_graph_data


# Confidence adjustment rules
CONFIDENCE_MODIFIERS = {
    "no_history": -10,             # No past analyses: reduce 10%
    "sparse_history": -5,          # Only 1-2 past analyses: reduce 5%
    "no_graph_context": -5,        # No graph data: reduce 5%
    "bias_warning_each": -3,       # Per bias warning: reduce 3%
    "bias_warning_max": -15,       # Max penalty for biases
    "pattern_confirms": +5,        # Current aligns with history: add 5%
    "pattern_contradicts": -10,    # Current contradicts history: reduce 10%
}
```

---

## Phase Implementation Details

### Phase 1: Fresh Analysis

```python
def _phase1_fresh_analysis(db, ticker, analysis_type, schedule_id):
    """Run analysis WITHOUT historical context injection."""
    timestamp = datetime.now().strftime("%Y%m%dT%H%M")
    filepath = cfg.analyses_dir / f"{ticker}_{analysis_type.value}_{timestamp}.md"
    stock = db.get_stock(ticker) if ticker != "PORTFOLIO" else None

    # KEY CHANGE: kb_enabled=False
    prompt = build_analysis_prompt(ticker, analysis_type, stock, kb_enabled=False)
    output = call_claude_code(prompt, cfg.allowed_tools_analysis, f"ANALYZE-{ticker}")

    if not output:
        return None

    filepath.write_text(output)
    parsed = parse_json_block(output)

    return AnalysisResult(
        ticker=ticker,
        type=analysis_type,
        filepath=filepath,
        gate_passed=parsed.get("gate_passed", False) if parsed else False,
        recommendation=parsed.get("recommendation", "UNKNOWN") if parsed else "UNKNOWN",
        confidence=parsed.get("confidence", 0) if parsed else 0,
        expected_value=parsed.get("expected_value_pct", 0.0) if parsed else 0.0,
        raw_output=output,
        parsed_json=parsed,
    )
```

### Phase 2: Dual Ingest

```python
def _phase2_dual_ingest(filepath):
    """Index to BOTH Graph (Neo4j) AND RAG (pgvector)."""
    results = {"graph": None, "rag": None, "errors": []}

    if not cfg.kb_ingest_enabled:
        return results

    # Graph extraction (currently MISSING from kb_ingest_analysis!)
    try:
        from graph.extract import extract_document
        result = extract_document(str(filepath), commit=True)
        results["graph"] = {
            "entities": len(result.entities),
            "relations": len(result.relations),
        }
        log.info(f"Graph indexed: {len(result.entities)} entities")
    except Exception as e:
        results["errors"].append(f"Graph: {e}")
        log.warning(f"Graph extraction failed: {e}")

    # RAG embedding
    try:
        from rag.embed import embed_document
        result = embed_document(str(filepath))
        results["rag"] = {"chunks": result.chunk_count}
        log.info(f"RAG embedded: {result.chunk_count} chunks")
    except Exception as e:
        results["errors"].append(f"RAG: {e}")
        log.warning(f"RAG embedding failed: {e}")

    return results
```

### Phase 3: Retrieve History

```python
def _phase3_retrieve_history(ticker, analysis_type, current_doc_id=None):
    """Retrieve historical context AFTER indexing current analysis."""
    from rag.hybrid import get_hybrid_context, get_bias_warnings, get_strategy_recommendations

    hybrid = get_hybrid_context(
        ticker=ticker,
        query=f"{analysis_type.value} analysis historical patterns",
        analysis_type=analysis_type.value,
        exclude_doc_id=current_doc_id,  # Exclude just-indexed document
    )

    # Filter out current analysis from results (belt and suspenders)
    past_analyses = [
        r.to_dict() for r in hybrid.vector_results
        if r.doc_id != current_doc_id
    ]

    # Determine history availability
    has_history = len(past_analyses) > 0
    has_graph = bool(
        hybrid.graph_context
        and hybrid.graph_context.get("_status") != "empty"
        and (hybrid.graph_context.get("peers") or hybrid.graph_context.get("risks"))
    )

    return SynthesisContext(
        ticker=ticker,
        past_analyses=past_analyses,
        graph_context=hybrid.graph_context,
        bias_warnings=get_bias_warnings(ticker),
        strategy_recommendations=get_strategy_recommendations(ticker),
        has_history=has_history,
        history_count=len(past_analyses),
        has_graph_data=has_graph,
    )
```

### Phase 4: Synthesize

```python
def _phase4_synthesize(result, historical, db=None):
    """Compare current analysis with historical context, adjust confidence, append synthesis."""
    current_metrics = result.parsed_json or {}
    original_confidence = current_metrics.get("confidence", 0)

    # Calculate adjusted confidence based on historical context
    adjusted_confidence, modifiers_applied = _calculate_adjusted_confidence(
        original_confidence=original_confidence,
        current_recommendation=current_metrics.get("recommendation"),
        historical=historical,
    )

    # Update result object with adjusted values
    result.confidence = adjusted_confidence
    result.parsed_json["adjusted_confidence"] = adjusted_confidence
    result.parsed_json["confidence_modifiers"] = modifiers_applied

    # Generate synthesis section
    synthesis = _format_synthesis_section(
        ticker=result.ticker,
        current=current_metrics,
        historical=historical,
        original_confidence=original_confidence,
        adjusted_confidence=adjusted_confidence,
        modifiers=modifiers_applied,
    )

    # Append to analysis file
    existing_content = result.filepath.read_text()
    result.filepath.write_text(existing_content + "\n\n" + synthesis)

    # Update database with adjusted confidence (if run_id exists)
    if db and result.parsed_json.get("run_id"):
        try:
            db.update_analysis_confidence(
                run_id=result.parsed_json["run_id"],
                adjusted_confidence=adjusted_confidence,
                modifiers=modifiers_applied,
            )
        except Exception as e:
            log.warning(f"Failed to update DB with adjusted confidence: {e}")

    log.info(
        f"Synthesis: {result.ticker} confidence {original_confidence}% → {adjusted_confidence}% "
        f"(modifiers: {modifiers_applied})"
    )


def _calculate_adjusted_confidence(original_confidence, current_recommendation, historical):
    """
    Calculate adjusted confidence based on historical context.

    Returns:
        tuple: (adjusted_confidence: int, modifiers_applied: dict)
    """
    modifiers = {}
    adjustment = 0

    # 1. No historical data penalty
    if historical.is_first_analysis:
        modifiers["first_analysis"] = CONFIDENCE_MODIFIERS["no_history"]
        adjustment += CONFIDENCE_MODIFIERS["no_history"]
    elif historical.history_count <= 2:
        modifiers["sparse_history"] = CONFIDENCE_MODIFIERS["sparse_history"]
        adjustment += CONFIDENCE_MODIFIERS["sparse_history"]

    # 2. No graph context penalty
    if not historical.has_graph_data:
        modifiers["no_graph"] = CONFIDENCE_MODIFIERS["no_graph_context"]
        adjustment += CONFIDENCE_MODIFIERS["no_graph_context"]

    # 3. Bias warnings penalty (capped)
    if historical.bias_warnings:
        bias_penalty = min(
            len(historical.bias_warnings) * CONFIDENCE_MODIFIERS["bias_warning_each"],
            CONFIDENCE_MODIFIERS["bias_warning_max"],
        )
        modifiers["bias_warnings"] = bias_penalty
        adjustment += bias_penalty

    # 4. Pattern consistency check (if we have history)
    if historical.has_history and historical.past_analyses:
        pattern_result = _check_pattern_consistency(
            current_recommendation, historical.past_analyses
        )
        if pattern_result == "confirms":
            modifiers["pattern_confirms"] = CONFIDENCE_MODIFIERS["pattern_confirms"]
            adjustment += CONFIDENCE_MODIFIERS["pattern_confirms"]
        elif pattern_result == "contradicts":
            modifiers["pattern_contradicts"] = CONFIDENCE_MODIFIERS["pattern_contradicts"]
            adjustment += CONFIDENCE_MODIFIERS["pattern_contradicts"]

    # Calculate final confidence (clamp to 0-100)
    adjusted = max(0, min(100, original_confidence + adjustment))

    return adjusted, modifiers


def _check_pattern_consistency(current_rec, past_analyses):
    """
    Check if current recommendation aligns with historical patterns.

    Returns: "confirms", "contradicts", or "neutral"
    """
    if not past_analyses:
        return "neutral"

    # Get last 3 recommendations
    recent_recs = [a.get("recommendation", "").upper() for a in past_analyses[:3]]
    current_upper = (current_rec or "").upper()

    if not recent_recs or not current_upper:
        return "neutral"

    # Bullish group: BUY, BULLISH, LONG
    # Bearish group: SELL, BEARISH, SHORT
    # Neutral group: WAIT, HOLD, NEUTRAL
    bullish = {"BUY", "BULLISH", "LONG"}
    bearish = {"SELL", "BEARISH", "SHORT"}

    current_sentiment = (
        "bullish" if current_upper in bullish else
        "bearish" if current_upper in bearish else
        "neutral"
    )

    # Count historical sentiments
    hist_sentiments = []
    for rec in recent_recs:
        if rec in bullish:
            hist_sentiments.append("bullish")
        elif rec in bearish:
            hist_sentiments.append("bearish")
        else:
            hist_sentiments.append("neutral")

    # Majority sentiment from history
    from collections import Counter
    sentiment_counts = Counter(hist_sentiments)
    majority_sentiment = sentiment_counts.most_common(1)[0][0]

    if current_sentiment == majority_sentiment:
        return "confirms"
    elif current_sentiment != "neutral" and majority_sentiment != "neutral":
        # Both have direction but different
        return "contradicts"
    else:
        return "neutral"
```

---

## Synthesis Output Format

### With Historical Data:

```markdown
---

## Historical Comparison (Auto-Generated)

*Synthesized from 5 past analyses*

### Past Recommendations

| Date | Recommendation | Confidence |
|------|----------------|------------|
| 2026-02-15 | BULLISH | 78% |
| 2026-01-20 | WAIT | 65% |

### Bias Warnings

- **Confirmation Bias**: 3 occurrences (-9%)

### Historical Strategy Performance

- **Earnings Momentum**: 72% win rate (8 trades)

### Sector Peers

AMD, INTC, QCOM, AVGO

### Known Risks

Export controls, China revenue exposure

---

### Confidence Adjustment

| Factor | Adjustment |
|--------|------------|
| Original confidence | 76% |
| Pattern confirms history | +5% |
| Bias warnings (3) | -9% |
| **Adjusted confidence** | **72%** |

**Current Analysis**: BULLISH
**Adjusted Confidence**: 72% (was 76%)
**Historical Pattern**: Confirms recent bullish sentiment
```

### First Analysis (No History):

```markdown
---

## Historical Comparison (Auto-Generated)

*This is the first analysis for NVDA*

> **Note**: No historical data available. Confidence reduced by 10%.
> Future analyses will benefit from comparison with this baseline.

### Knowledge Graph

*No graph context available yet.*

---

### Confidence Adjustment

| Factor | Adjustment |
|--------|------------|
| Original confidence | 76% |
| First analysis (no history) | -10% |
| No graph context | -5% |
| **Adjusted confidence** | **61%** |

**Current Analysis**: BULLISH
**Adjusted Confidence**: 61% (was 76%)
**Historical Pattern**: First analysis - establishing baseline
```

---

## Error Handling

| Phase | Failure Mode | Recovery |
|-------|--------------|----------|
| Phase 1 | Claude timeout/error | Return None, mark schedule failed |
| Phase 2 | Graph unavailable | Log warning, continue to Phase 3 |
| Phase 2 | RAG unavailable | Log warning, continue to Phase 3 |
| Phase 3 | No historical data | Use empty context, note "First analysis" |
| Phase 4 | Parse error | Log warning, skip synthesis section |

---

## Backward Compatibility

- Feature flag `four_phase_analysis_enabled` defaults to `true` (4-phase workflow active)
- Legacy workflow available by setting flag to `false`
- Legacy code path preserved in `_legacy_run_analysis()`

---

## Testing Strategy

### Unit Tests (`tests/test_orchestrator.py`)

```python
class TestFourPhaseWorkflow:
    def test_phase1_no_kb_context(self):
        """Verify prompt has no KB context when kb_enabled=False."""
        pass

    def test_phase2_dual_ingest_calls_both(self):
        """Verify both graph and RAG are called."""
        pass

    def test_phase3_retrieves_after_index(self):
        """Verify historical context retrieved after indexing."""
        pass

    def test_phase4_synthesis_format(self):
        """Verify synthesis markdown structure."""
        pass

    def test_legacy_workflow_unchanged(self):
        """Verify backward compatibility when flag disabled."""
        pass
```

### Manual Testing

```bash
# Run analysis (4-phase enabled by default)
python orchestrator.py analyze NVDA --type stock

# Verify output has synthesis section
cat analyses/NVDA_stock_*.md | grep "Historical Comparison"

# Verify graph indexed
python orchestrator.py graph status

# Verify RAG indexed
python orchestrator.py rag status

# Test legacy workflow (for backward compatibility)
python orchestrator.py settings set four_phase_analysis_enabled false
python orchestrator.py analyze AAPL --type stock
# Verify no synthesis section

# Re-enable 4-phase (default)
python orchestrator.py settings set four_phase_analysis_enabled true
```

---

## Implementation Order

1. Add feature flag to `db/init.sql`
2. Add `four_phase_analysis_enabled` property to `Settings` class
3. Add `SynthesisContext` dataclass
4. Implement `_phase1_fresh_analysis()`
5. Implement `_phase2_dual_ingest()`
6. Implement `_phase3_retrieve_history()`
7. Implement `_phase4_synthesize()` and `_format_synthesis_section()`
8. Modify `run_analysis()` to use 4-phase when flag enabled
9. Update `rag/hybrid.py` with `exclude_doc_id` parameter
10. Update skill documentation
11. Add unit tests
12. Manual testing

---

## Complexity Assessment

| Component | Complexity (1-5) | Notes |
|-----------|------------------|-------|
| Phase 1 refactor | 2 | Minor changes to existing function |
| Phase 2 dual ingest | 2 | Pattern exists in `kb_ingest_file()` |
| Phase 3 retrieval | 2 | Uses existing hybrid.py functions |
| Phase 4 synthesis | 3 | New formatting logic |
| Skill updates | 2 | Documentation changes |
| Testing | 3 | Comprehensive coverage needed |
| **Overall** | **2.5** | Moderate complexity |

---

## Dependencies

- No external dependencies required
- Uses existing `graph/extract.py` and `rag/embed.py`
- Uses existing `rag/hybrid.py` for context retrieval

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Phase 2 slows down analysis | Graph/RAG ingest is already fast (<1s each) |
| Self-retrieval in Phase 3 | Add `exclude_doc_id` parameter |
| Synthesis bloats output | Keep synthesis section concise (~20 lines) |
| Breaking existing workflow | Legacy mode available via `four_phase_analysis_enabled=false` |

---

## Additional Implementation Details

### `_format_synthesis_section()` Implementation

```python
def _format_synthesis_section(
    ticker: str,
    current: dict,
    historical: SynthesisContext,
    original_confidence: int,
    adjusted_confidence: int,
    modifiers: dict,
) -> str:
    """Generate markdown synthesis section to append to analysis file."""
    lines = [
        "---",
        "",
        "## Historical Comparison (Auto-Generated)",
        "",
    ]

    if historical.is_first_analysis:
        # First analysis case
        lines.extend([
            f"*This is the first analysis for {ticker}*",
            "",
            "> **Note**: No historical data available. Confidence adjusted accordingly.",
            "> Future analyses will benefit from comparison with this baseline.",
            "",
            "### Knowledge Graph",
            "",
            "*No graph context available yet.*" if not historical.has_graph_data else "",
        ])
    else:
        # Has historical data
        lines.append(f"*Synthesized from {historical.history_count} past analyses*")
        lines.append("")

        # Past recommendations table
        if historical.past_analyses:
            lines.extend([
                "### Past Recommendations",
                "",
                "| Date | Recommendation | Confidence |",
                "|------|----------------|------------|",
            ])
            for analysis in historical.past_analyses[:5]:  # Limit to 5
                date = analysis.get("date", "N/A")
                rec = analysis.get("recommendation", "N/A")
                conf = analysis.get("confidence", "N/A")
                lines.append(f"| {date} | {rec} | {conf}% |")
            lines.append("")

        # Bias warnings
        if historical.bias_warnings:
            lines.extend([
                "### Bias Warnings",
                "",
            ])
            for bias in historical.bias_warnings:
                count = bias.get("count", 1)
                penalty = count * CONFIDENCE_MODIFIERS["bias_warning_each"]
                lines.append(f"- **{bias.get('type', 'Unknown')}**: {count} occurrences ({penalty}%)")
            lines.append("")

        # Sector peers from graph
        if historical.graph_context and historical.graph_context.get("peers"):
            peers = ", ".join(historical.graph_context["peers"][:6])
            lines.extend([
                "### Sector Peers",
                "",
                peers,
                "",
            ])

        # Known risks from graph
        if historical.graph_context and historical.graph_context.get("risks"):
            risks = ", ".join(historical.graph_context["risks"][:4])
            lines.extend([
                "### Known Risks",
                "",
                risks,
                "",
            ])

    # Confidence adjustment table (always show)
    lines.extend([
        "---",
        "",
        "### Confidence Adjustment",
        "",
        "| Factor | Adjustment |",
        "|--------|------------|",
        f"| Original confidence | {original_confidence}% |",
    ])

    for factor, adjustment in modifiers.items():
        sign = "+" if adjustment > 0 else ""
        lines.append(f"| {factor.replace('_', ' ').title()} | {sign}{adjustment}% |")

    lines.append(f"| **Adjusted confidence** | **{adjusted_confidence}%** |")
    lines.append("")

    # Summary
    current_rec = current.get("recommendation", "UNKNOWN")
    pattern_desc = _get_pattern_description(modifiers, historical)
    lines.extend([
        f"**Current Analysis**: {current_rec}",
        f"**Adjusted Confidence**: {adjusted_confidence}% (was {original_confidence}%)",
        f"**Historical Pattern**: {pattern_desc}",
    ])

    return "\n".join(lines)


def _get_pattern_description(modifiers: dict, historical: SynthesisContext) -> str:
    """Generate description of pattern alignment."""
    if historical.is_first_analysis:
        return "First analysis - establishing baseline"
    elif "pattern_confirms" in modifiers:
        return "Confirms recent historical sentiment"
    elif "pattern_contradicts" in modifiers:
        return "⚠️ Contradicts recent historical sentiment"
    else:
        return "No clear pattern from history"
```

### `tradegent/db_layer.py` Update

Add to `DBLayer` class:

```python
def update_analysis_confidence(
    self, run_id: str, adjusted_confidence: int, modifiers: dict
) -> bool:
    """
    Update analysis_results with adjusted confidence from Phase 4 synthesis.

    Args:
        run_id: Analysis run ID
        adjusted_confidence: Confidence after historical comparison
        modifiers: Dict of factors that affected confidence

    Returns:
        True if updated successfully
    """
    with self.conn.cursor() as cur:
        cur.execute(
            """
            UPDATE nexus.analysis_results
            SET adjusted_confidence = %s,
                confidence_modifiers = %s,
                updated_at = now()
            WHERE run_id = %s
            """,
            (adjusted_confidence, json.dumps(modifiers), run_id),
        )
    self.conn.commit()
    return cur.rowcount > 0
```

### Database Migration: `db/migrations/002_adjusted_confidence.sql`

```sql
-- Add adjusted confidence columns to analysis_results
ALTER TABLE nexus.analysis_results
    ADD COLUMN IF NOT EXISTS adjusted_confidence INTEGER,
    ADD COLUMN IF NOT EXISTS confidence_modifiers JSONB;

COMMENT ON COLUMN nexus.analysis_results.adjusted_confidence IS
    'Confidence after Phase 4 synthesis adjustment (historical comparison)';
COMMENT ON COLUMN nexus.analysis_results.confidence_modifiers IS
    'JSON dict of factors that adjusted confidence: {factor: adjustment_pct}';
```

### Document ID Tracking Between Phases

Update Phase 2 to return the document ID for use in Phase 3:

```python
def _phase2_dual_ingest(filepath) -> dict:
    """Index to BOTH Graph (Neo4j) AND RAG (pgvector)."""
    results = {"graph": None, "rag": None, "doc_id": None, "errors": []}

    if not cfg.kb_ingest_enabled:
        return results

    # RAG embedding (returns doc_id)
    try:
        from rag.embed import embed_document
        result = embed_document(str(filepath))
        results["rag"] = {"chunks": result.chunk_count}
        results["doc_id"] = result.doc_id  # Save for Phase 3
        log.info(f"RAG embedded: {result.chunk_count} chunks")
    except Exception as e:
        results["errors"].append(f"RAG: {e}")
        log.warning(f"RAG embedding failed: {e}")

    # Graph extraction
    try:
        from graph.extract import extract_document
        result = extract_document(str(filepath), commit=True)
        results["graph"] = {
            "entities": len(result.entities),
            "relations": len(result.relations),
        }
        log.info(f"Graph indexed: {len(result.entities)} entities")
    except Exception as e:
        results["errors"].append(f"Graph: {e}")
        log.warning(f"Graph extraction failed: {e}")

    return results


# Updated run_analysis() flow
def run_analysis(db, ticker, analysis_type, schedule_id=None):
    if cfg.four_phase_analysis_enabled:
        # Phase 1: Fresh analysis (no KB context)
        result = _phase1_fresh_analysis(db, ticker, analysis_type, schedule_id)
        if not result:
            return None

        # Phase 2: Dual ingest (Graph + RAG)
        ingest_result = _phase2_dual_ingest(result.filepath)

        # Phase 3: Retrieve historical context (exclude current doc)
        historical_context = _phase3_retrieve_history(
            ticker, analysis_type,
            current_doc_id=ingest_result.get("doc_id")
        )

        # Phase 4: Synthesize and append
        _phase4_synthesize(result, historical_context, db)

        return result
    else:
        return _legacy_run_analysis(db, ticker, analysis_type, schedule_id)
```

---

## Updated Files Summary

| File | Changes |
|------|---------|
| `tradegent/orchestrator.py` | Add 4 phase functions, modify run_analysis() |
| `tradegent/db/init.sql` | Add feature flag setting |
| `tradegent/db/migrations/002_adjusted_confidence.sql` | New migration for adjusted confidence columns |
| `tradegent/db_layer.py` | Add `update_analysis_confidence()` method |
| `tradegent/rag/hybrid.py` | Add `exclude_doc_id` parameter |
| `tradegent/rag/embed.py` | Ensure `embed_document()` returns `doc_id` |
| `.claude/skills/earnings-analysis.md` | Update workflow documentation |
| `.claude/skills/stock-analysis.md` | Update workflow documentation |

---

## Implementation Checklist

- [x] Verify `rag/embed.py` returns `doc_id` in result
- [x] Verify `graph/extract.py` commit parameter works
- [x] Check `analysis_results` table exists and accepts new columns
- [x] Ensure feature flag mechanism works (`Settings._get_bool`)
- [x] Add feature flag to `db/init.sql`
- [x] Add `four_phase_analysis_enabled` property to Settings class
- [x] Add `SynthesisContext` dataclass
- [x] Add `doc_id` column to `analysis_results` table (migration)
- [x] Add `_enrich_past_analyses()` function
- [x] Implement `_phase1_fresh_analysis()`
- [x] Implement `_phase2_dual_ingest()`
- [x] Implement `_phase3_retrieve_history()` with db parameter
- [x] Implement `_phase4_synthesize()` with run_id parameter
- [x] Implement `_format_synthesis_section()` with correct field names
- [x] Implement `_legacy_run_analysis()`
- [x] Modify `run_analysis()` with schedule tracking
- [x] Update `rag/hybrid.py` with `exclude_doc_id` parameter
- [x] Add timeout handling (`_run_with_timeout`, phase timeouts)
- [x] Add phase timeout settings to Settings class
- [ ] Add connection timeouts (PostgreSQL, Neo4j) - **deferred**
- [ ] Add logging improvements (AnalysisTrace, PhaseMetrics) - **deferred**
- [ ] Add debug CLI commands (debug-phase, tail-log) - **deferred**
- [ ] Update skill documentation - **deferred**
- [ ] Add unit tests - **deferred**
- [ ] Manual testing - **pending**

---

## Critical Gap Resolutions

### Gap 1: SearchResult.to_dict() Missing Fields

**Problem**: `SearchResult.to_dict()` returns `doc_id, file_path, doc_type, ticker, doc_date, section_label, content, similarity` but synthesis expects `recommendation`, `confidence`, `date` fields.

**Solution**: Extract these from the analysis content via parsing, or query database.

```python
def _enrich_past_analyses(vector_results: list, db) -> list[dict]:
    """
    Enrich SearchResult dicts with recommendation/confidence from analysis_results table.

    Args:
        vector_results: List of SearchResult objects
        db: Database connection

    Returns:
        List of enriched dicts with recommendation, confidence, date fields
    """
    enriched = []
    for result in vector_results:
        base = result.to_dict()

        # Extract date from doc_id (format: TICKER_TYPE_YYYYMMDDTHHMM)
        try:
            parts = result.doc_id.rsplit("_", 1)
            if len(parts) == 2:
                date_str = parts[1][:8]  # YYYYMMDD
                base["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        except Exception:
            base["date"] = base.get("doc_date", "N/A")

        # Query analysis_results for recommendation/confidence
        try:
            with db.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT recommendation, confidence
                    FROM nexus.analysis_results
                    WHERE doc_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (result.doc_id,),
                )
                row = cur.fetchone()
                if row:
                    base["recommendation"] = row[0]
                    base["confidence"] = row[1]
                else:
                    base["recommendation"] = "N/A"
                    base["confidence"] = "N/A"
        except Exception:
            base["recommendation"] = "N/A"
            base["confidence"] = "N/A"

        enriched.append(base)

    return enriched
```

**Alternative**: Add `doc_id` column to `analysis_results` table if not present:

```sql
-- Migration: add doc_id to analysis_results for cross-reference
ALTER TABLE nexus.analysis_results
    ADD COLUMN IF NOT EXISTS doc_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_analysis_results_doc_id
    ON nexus.analysis_results(doc_id);
```

### Gap 2: run_id Tracking Incorrect

**Problem**: Plan assumes `result.parsed_json["run_id"]` but `run_id` comes from `db.mark_schedule_started()`.

**Solution**: Pass `run_id` through the phase chain explicitly:

```python
def run_analysis(db, ticker, analysis_type, schedule_id=None):
    """Main entry point - either 4-phase or legacy workflow."""
    # Generate run_id at start (for both workflows)
    run_id = db.mark_schedule_started(schedule_id) if schedule_id else None

    if cfg.four_phase_analysis_enabled:
        try:
            # Phase 1: Fresh analysis (no KB context)
            result = _phase1_fresh_analysis(db, ticker, analysis_type, schedule_id)
            if not result:
                if run_id and schedule_id:
                    db.mark_schedule_completed(schedule_id, run_id, "failed", error="Phase 1 failed")
                return None

            # Phase 2: Dual ingest (Graph + RAG)
            ingest_result = _phase2_dual_ingest(result.filepath)

            # Phase 3: Retrieve historical context (exclude current doc)
            historical_context = _phase3_retrieve_history(
                ticker, analysis_type,
                current_doc_id=ingest_result.get("doc_id"),
                db=db,  # Pass db for enrichment
            )

            # Phase 4: Synthesize and append (pass run_id explicitly)
            _phase4_synthesize(result, historical_context, db, run_id)

            # Mark schedule completed
            if run_id and schedule_id:
                db.mark_schedule_completed(schedule_id, run_id, "completed")
                db.save_analysis_result(run_id, ticker, analysis_type.value, result.parsed_json)

            return result

        except Exception as e:
            if run_id and schedule_id:
                db.mark_schedule_completed(schedule_id, run_id, "failed", error=str(e))
            raise
    else:
        return _legacy_run_analysis(db, ticker, analysis_type, schedule_id, run_id)
```

**Update `_phase4_synthesize()` signature**:

```python
def _phase4_synthesize(result, historical, db=None, run_id=None):
    """Compare current analysis with historical context, adjust confidence, append synthesis."""
    # ... existing code ...

    # Update database with adjusted confidence
    if db and run_id:
        try:
            db.update_analysis_confidence(
                run_id=run_id,
                adjusted_confidence=adjusted_confidence,
                modifiers=modifiers_applied,
            )
        except Exception as e:
            log.warning(f"Failed to update DB with adjusted confidence: {e}")
```

### Gap 3: Bias Warning Field Name Mismatch

**Problem**: `get_bias_warnings()` returns `{"bias": ..., "occurrences": ...}` but `_format_synthesis_section()` uses `bias.get("type")` and `bias.get("count")`.

**Solution**: Fix field names in `_format_synthesis_section()`:

```python
# In _format_synthesis_section():
# BEFORE (wrong):
for bias in historical.bias_warnings:
    count = bias.get("count", 1)
    lines.append(f"- **{bias.get('type', 'Unknown')}**: ...")

# AFTER (correct):
for bias in historical.bias_warnings:
    count = bias.get("occurrences", 1)  # Correct field name
    penalty = count * CONFIDENCE_MODIFIERS["bias_warning_each"]
    lines.append(f"- **{bias.get('bias', 'Unknown')}**: {count} occurrences ({penalty}%)")
```

Also fix `_calculate_adjusted_confidence()`:

```python
# Bias penalty calculation uses len() which is correct
# But individual bias warnings should use 'occurrences' not 'count'
if historical.bias_warnings:
    total_occurrences = sum(b.get("occurrences", 1) for b in historical.bias_warnings)
    bias_penalty = min(
        total_occurrences * CONFIDENCE_MODIFIERS["bias_warning_each"],
        CONFIDENCE_MODIFIERS["bias_warning_max"],
    )
    modifiers["bias_warnings"] = bias_penalty
    adjustment += bias_penalty
```

### Gap 4: Pattern Consistency Will Always Return "neutral"

**Problem**: `_check_pattern_consistency()` looks for `recommendation` field in SearchResult.to_dict() but field doesn't exist without enrichment.

**Solution**: Use enriched analyses from Gap 1 fix, and update Phase 3:

```python
def _phase3_retrieve_history(ticker, analysis_type, current_doc_id=None, db=None):
    """Retrieve historical context AFTER indexing current analysis."""
    from rag.hybrid import get_hybrid_context, get_bias_warnings, get_strategy_recommendations

    hybrid = get_hybrid_context(
        ticker=ticker,
        query=f"{analysis_type.value} analysis historical patterns",
        analysis_type=analysis_type.value,
        exclude_doc_id=current_doc_id,
    )

    # Filter out current analysis
    filtered_results = [r for r in hybrid.vector_results if r.doc_id != current_doc_id]

    # CRITICAL: Enrich with recommendation/confidence from database
    if db:
        past_analyses = _enrich_past_analyses(filtered_results, db)
    else:
        past_analyses = [r.to_dict() for r in filtered_results]

    # ... rest of function
```

### Gap 5: Missing Schedule Completion Tracking

**Problem**: Existing code calls `mark_schedule_completed()` / `mark_schedule_failed()` but plan doesn't show this.

**Solution**: Added to Gap 2 fix above. The updated `run_analysis()` now includes:
- `db.mark_schedule_completed(schedule_id, run_id, "completed")` on success
- `db.mark_schedule_completed(schedule_id, run_id, "failed", error=...)` on failure

### Gap 6: _legacy_run_analysis() Undefined

**Problem**: Referenced but implementation not shown.

**Solution**: Extract existing `run_analysis()` body into `_legacy_run_analysis()`:

```python
def _legacy_run_analysis(db, ticker, analysis_type, schedule_id, run_id):
    """
    Original workflow (before 4-phase). Kept for backward compatibility.

    This is the existing run_analysis() code moved to a separate function.
    """
    stock = db.get_stock(ticker) if ticker != "PORTFOLIO" else None
    timestamp = datetime.now().strftime("%Y%m%dT%H%M")
    filepath = cfg.analyses_dir / f"{ticker}_{analysis_type.value}_{timestamp}.md"

    # Get historical context BEFORE analysis (legacy behavior)
    prompt = build_analysis_prompt(ticker, analysis_type, stock, kb_enabled=True)

    output = call_claude_code(prompt, cfg.allowed_tools_analysis, f"ANALYZE-{ticker}")

    if not output:
        if run_id and schedule_id:
            db.mark_schedule_completed(schedule_id, run_id, "failed", error="Empty output")
        return None

    filepath.write_text(output)
    parsed = parse_json_block(output)

    # Index to RAG only (legacy - no graph)
    if cfg.kb_ingest_enabled:
        try:
            kb_ingest_analysis(filepath)
        except Exception as e:
            log.warning(f"KB ingest failed: {e}")

    # Mark complete
    if run_id and schedule_id:
        db.mark_schedule_completed(schedule_id, run_id, "completed")
        db.save_analysis_result(run_id, ticker, analysis_type.value, parsed)

    return AnalysisResult(
        ticker=ticker,
        type=analysis_type,
        filepath=filepath,
        gate_passed=parsed.get("gate_passed", False) if parsed else False,
        recommendation=parsed.get("recommendation", "UNKNOWN") if parsed else "UNKNOWN",
        confidence=parsed.get("confidence", 0) if parsed else 0,
        expected_value=parsed.get("expected_value_pct", 0.0) if parsed else 0.0,
        raw_output=output,
        parsed_json=parsed,
    )
```

---

---

## Timeout Handling

### Current Timeout Status

| Component | Current Timeout | Location |
|-----------|-----------------|----------|
| Claude Code call | 600s (configurable) | `Settings.claude_timeout` |
| Graph LLM extraction | 30s per call | `graph/extract.py:150` |
| RAG embedding API | 30s per call | `rag/embedding_client.py:69` |
| PostgreSQL connections | ❌ **None** | `psycopg.connect()` |
| Neo4j connections | ❌ **None** | `neo4j.GraphDatabase.driver()` |

### Required Timeout Additions

#### 1. Per-Phase Timeouts

```python
# Add to Settings class
@property
def phase2_timeout(self) -> int:
    """Timeout for Phase 2 (Graph + RAG ingest) in seconds."""
    return int(self._get("phase2_timeout_seconds", "PHASE2_TIMEOUT", 120))

@property
def phase3_timeout(self) -> int:
    """Timeout for Phase 3 (historical retrieval) in seconds."""
    return int(self._get("phase3_timeout_seconds", "PHASE3_TIMEOUT", 60))

@property
def phase4_timeout(self) -> int:
    """Timeout for Phase 4 (synthesis) in seconds."""
    return int(self._get("phase4_timeout_seconds", "PHASE4_TIMEOUT", 30))
```

#### 2. Phase Execution with Timeout

```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

def _run_with_timeout(func, timeout: int, phase_name: str, *args, **kwargs):
    """
    Execute a function with timeout. Returns (result, error).

    Args:
        func: Function to execute
        timeout: Timeout in seconds
        phase_name: Name for logging
        *args, **kwargs: Arguments to pass to func

    Returns:
        tuple: (result, None) on success, (None, error_message) on failure
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=timeout)
            return result, None
        except FuturesTimeoutError:
            log.error(f"[{phase_name}] Timed out after {timeout}s")
            return None, f"Timeout after {timeout}s"
        except Exception as e:
            log.error(f"[{phase_name}] Failed: {e}")
            return None, str(e)


# Usage in run_analysis():
def run_analysis(db, ticker, analysis_type, schedule_id=None):
    if cfg.four_phase_analysis_enabled:
        trace_id = f"{ticker}-{datetime.now().strftime('%H%M%S')}"
        log.info(f"[{trace_id}] Starting 4-phase workflow")

        # Phase 1: Fresh analysis (uses existing claude_timeout)
        result = _phase1_fresh_analysis(db, ticker, analysis_type, schedule_id)
        if not result:
            return None

        # Phase 2: Dual ingest WITH TIMEOUT
        ingest_result, p2_error = _run_with_timeout(
            _phase2_dual_ingest,
            cfg.phase2_timeout,
            f"{trace_id}/P2",
            result.filepath,
        )
        if p2_error:
            log.warning(f"[{trace_id}] Phase 2 failed: {p2_error}, continuing...")
            ingest_result = {"doc_id": None, "errors": [p2_error]}

        # Phase 3: Retrieve history WITH TIMEOUT
        historical_context, p3_error = _run_with_timeout(
            _phase3_retrieve_history,
            cfg.phase3_timeout,
            f"{trace_id}/P3",
            ticker, analysis_type,
            current_doc_id=ingest_result.get("doc_id"),
            db=db,
        )
        if p3_error:
            log.warning(f"[{trace_id}] Phase 3 failed: {p3_error}, using empty context")
            historical_context = SynthesisContext(
                ticker=ticker,
                past_analyses=[],
                graph_context={},
                bias_warnings=[],
                strategy_recommendations=[],
                has_history=False,
                history_count=0,
                has_graph_data=False,
            )

        # Phase 4: Synthesize WITH TIMEOUT
        _, p4_error = _run_with_timeout(
            _phase4_synthesize,
            cfg.phase4_timeout,
            f"{trace_id}/P4",
            result, historical_context, db, run_id,
        )
        if p4_error:
            log.warning(f"[{trace_id}] Phase 4 failed: {p4_error}, skipping synthesis")

        log.info(f"[{trace_id}] 4-phase workflow completed")
        return result
```

#### 3. Database Connection Timeouts

**PostgreSQL** (`db_layer.py`):
```python
def connect(self) -> "NexusDB":
    """Establish database connection with timeout."""
    self._conn = psycopg.connect(
        self.dsn,
        row_factory=dict_row,
        connect_timeout=10,  # 10 second connection timeout
    )
    log.info("Database connected")
    return self
```

**Neo4j** (`graph/layer.py`):
```python
def connect(self) -> None:
    """Establish Neo4j connection with timeout."""
    self._driver = GraphDatabase.driver(
        self.uri,
        auth=(self.user, self.password),
        connection_timeout=10,  # 10 second connection timeout
        max_connection_lifetime=300,  # 5 minute max connection lifetime
    )
    self._driver.verify_connectivity()
```

**RAG psycopg calls** (`rag/schema.py`, `rag/embed.py`, `rag/search.py`):
```python
# Add connect_timeout to all psycopg.connect() calls
with psycopg.connect(get_database_url(), connect_timeout=10) as conn:
    ...
```

#### 4. Database Settings for Timeouts

```sql
-- Add to db/init.sql
INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('phase2_timeout_seconds', '120', 'timeouts', 'Phase 2 (ingest) timeout'),
    ('phase3_timeout_seconds', '60', 'timeouts', 'Phase 3 (retrieval) timeout'),
    ('phase4_timeout_seconds', '30', 'timeouts', 'Phase 4 (synthesis) timeout')
ON CONFLICT (key) DO NOTHING;
```

---

## Logging and Debugging

### Current Logging Status

| Component | Log File | Format |
|-----------|----------|--------|
| Orchestrator | `logs/orchestrator.log` | `%(asctime)s [%(levelname)s] %(message)s` |
| Graph/RAG modules | Uses orchestrator logger | Same format |

### Logging Improvements

#### 1. Structured Logging with Trace IDs

```python
import uuid
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class AnalysisTrace:
    """Trace context for correlating logs across phases."""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    ticker: str = ""
    analysis_type: str = ""
    phase: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    def log(self, level: str, message: str, **extra):
        """Log with trace context."""
        prefix = f"[{self.trace_id}][P{self.phase}][{self.ticker}]"
        full_message = f"{prefix} {message}"
        getattr(log, level)(full_message)

    def phase_start(self, phase: int, name: str):
        """Log phase start."""
        self.phase = phase
        self.log("info", f"Starting {name}")
        return datetime.now()

    def phase_end(self, phase_start: datetime, success: bool, error: str = None):
        """Log phase end with duration."""
        duration_ms = (datetime.now() - phase_start).total_seconds() * 1000
        status = "completed" if success else f"failed: {error}"
        self.log("info", f"Phase {self.phase} {status} ({duration_ms:.0f}ms)")


# Usage:
def run_analysis(db, ticker, analysis_type, schedule_id=None):
    trace = AnalysisTrace(ticker=ticker, analysis_type=analysis_type.value)
    trace.log("info", f"Starting analysis workflow (4-phase={cfg.four_phase_analysis_enabled})")

    if cfg.four_phase_analysis_enabled:
        # Phase 1
        p1_start = trace.phase_start(1, "Fresh Analysis")
        result = _phase1_fresh_analysis(db, ticker, analysis_type, schedule_id)
        trace.phase_end(p1_start, result is not None)

        # Phase 2
        p2_start = trace.phase_start(2, "Dual Ingest")
        ingest_result, p2_error = _run_with_timeout(...)
        trace.phase_end(p2_start, p2_error is None, p2_error)
        # ... etc
```

#### 2. Phase Timing Metrics

```python
@dataclass
class PhaseMetrics:
    """Metrics for a single phase execution."""
    phase: int
    name: str
    start_time: datetime
    end_time: datetime | None = None
    success: bool = False
    error: str | None = None
    details: dict = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        if not self.end_time:
            return 0
        return int((self.end_time - self.start_time).total_seconds() * 1000)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "name": self.name,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "details": self.details,
        }


@dataclass
class WorkflowMetrics:
    """Aggregate metrics for entire workflow."""
    trace_id: str
    ticker: str
    analysis_type: str
    phases: list[PhaseMetrics] = field(default_factory=list)
    total_duration_ms: int = 0

    def add_phase(self, metrics: PhaseMetrics):
        self.phases.append(metrics)

    def finalize(self):
        self.total_duration_ms = sum(p.duration_ms for p in self.phases)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "ticker": self.ticker,
            "analysis_type": self.analysis_type,
            "total_duration_ms": self.total_duration_ms,
            "phases": [p.to_dict() for p in self.phases],
        }

    def log_summary(self):
        """Log workflow summary."""
        log.info(f"[{self.trace_id}] Workflow completed in {self.total_duration_ms}ms")
        for p in self.phases:
            status = "✓" if p.success else "✗"
            log.info(f"  {status} Phase {p.phase} ({p.name}): {p.duration_ms}ms")
```

#### 3. Debug Log Level Setting

```python
# Add to Settings class
@property
def log_level(self) -> str:
    """Log level: DEBUG, INFO, WARNING, ERROR."""
    return self._get("log_level", "LOG_LEVEL", "INFO")

# Add to orchestrator startup
def configure_logging():
    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.getLogger("nexus-light").setLevel(level)

    # Also set for submodules
    for module in ["graph", "rag"]:
        logging.getLogger(module).setLevel(level)
```

#### 4. CLI Debug Commands

```python
# Add to CLI (if __name__ == "__main__" section)

@app.command()
def debug_phase(
    ticker: str = typer.Argument(..., help="Ticker symbol"),
    phase: int = typer.Option(1, help="Phase number (1-4)"),
):
    """Run a single phase for debugging."""
    db = NexusDB().connect()
    trace = AnalysisTrace(ticker=ticker)

    if phase == 1:
        result = _phase1_fresh_analysis(db, ticker, AnalysisType.STOCK, None)
        print(f"Phase 1 result: {result}")
    elif phase == 2:
        # Need filepath
        filepath = Path(f"analyses/{ticker}_stock_debug.md")
        result = _phase2_dual_ingest(filepath)
        print(f"Phase 2 result: {result}")
    elif phase == 3:
        context = _phase3_retrieve_history(ticker, AnalysisType.STOCK, db=db)
        print(f"Phase 3 context: {context}")
    elif phase == 4:
        # Needs prior phases
        print("Phase 4 requires Phases 1-3 to run first")


@app.command()
def debug_timeout(
    seconds: int = typer.Option(5, help="Timeout in seconds"),
):
    """Test timeout mechanism."""
    import time

    def slow_func():
        time.sleep(10)
        return "done"

    result, error = _run_with_timeout(slow_func, seconds, "DEBUG")
    print(f"Result: {result}, Error: {error}")


@app.command()
def tail_log(
    lines: int = typer.Option(50, help="Number of lines"),
    follow: bool = typer.Option(False, "-f", help="Follow log output"),
):
    """Tail the orchestrator log."""
    log_path = BASE_DIR / "logs" / "orchestrator.log"
    if follow:
        subprocess.run(["tail", "-f", str(log_path)])
    else:
        subprocess.run(["tail", "-n", str(lines), str(log_path)])
```

#### 5. Database Settings for Logging

```sql
-- Add to db/init.sql
INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('log_level', 'INFO', 'logging', 'Log level: DEBUG, INFO, WARNING, ERROR'),
    ('log_phase_metrics', 'true', 'logging', 'Log detailed phase timing metrics')
ON CONFLICT (key) DO NOTHING;
```

---

## Updated Implementation Order

### Completed (2026-02-20)

1. ✅ Add feature flag to `db/init.sql`
2. ✅ Add `four_phase_analysis_enabled` property to `Settings` class
3. ✅ Add `SynthesisContext` dataclass
4. ✅ **Add `doc_id` column to `analysis_results` table** (Gap 1) - via migration
5. ✅ **Add `_enrich_past_analyses()` function** (Gap 1)
6. ✅ Implement `_phase1_fresh_analysis()`
7. ✅ Implement `_phase2_dual_ingest()`
8. ✅ Implement `_phase3_retrieve_history()` **with db parameter** (Gap 4)
9. ✅ Implement `_phase4_synthesize()` **with run_id parameter** (Gap 2)
10. ✅ Implement `_format_synthesis_section()` **with correct field names** (Gap 3)
11. ✅ **Implement `_legacy_run_analysis()`** (Gap 6)
12. ✅ Modify `run_analysis()` with **schedule tracking** (Gap 5)
13. ✅ Update `rag/hybrid.py` with `exclude_doc_id` parameter
14. ✅ **Add timeout handling** (`_run_with_timeout`, phase timeouts)

### Deferred

15. ⏸️ **Add connection timeouts** (PostgreSQL, Neo4j) - low priority
16. ⏸️ **Add logging improvements** (AnalysisTrace, PhaseMetrics) - enhancement
17. ⏸️ **Add debug CLI commands** (debug-phase, tail-log) - enhancement
18. ⏸️ Update skill documentation - after testing
19. ⏸️ Add unit tests - after validation
20. ⏸️ Manual testing - next step
