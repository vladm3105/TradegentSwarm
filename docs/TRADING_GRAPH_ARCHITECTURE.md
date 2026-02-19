# Trading Knowledge Graph — Architecture Plan

> **Status**: Planning  
> **Last updated**: 2026-02-19  
> **Replaces**: LightRAG (extraction timeouts with local Ollama models)

## Overview

Domain-specific knowledge graph that discovers entities and relationships from
**real trading analysis output** as Claude skills produce it. The graph grows
organically from live trading activity — not backfilled from templates.

### Design Principles

1. **Live extraction only** — graph is populated when skills create real analyses, not by batch-processing template files
2. **Domain-specific entities** — 16 trading entity types (Bias, Catalyst, Strategy, etc.) that generic RAG tools miss
3. **Dual extraction** — Claude in-context during skill execution (highest quality) + Ollama batch for re-processing (free, local)
4. **Field-by-field processing** — each text field sent individually to LLM (avoids the timeout that killed LightRAG)
5. **Normalize on ingest** — dedup, name standardization, and alias resolution at write time

### Key Decision: Why Not LightRAG?

| Factor | LightRAG | Custom Graph |
|--------|----------|-------------|
| Entity types | Generic (Person, Org, Location) | Trading-specific (Bias, Catalyst, Strategy) |
| Extraction model | Requires fast cloud model ($) | Ollama field-by-field (free) or Claude in-context |
| `_graph` sections | Ignores them entirely | Can use as schema hints |
| Domain accuracy | Low — misses trading concepts | High — prompt-engineered for trading |
| Operational cost | Cloud API per document | $0 for Ollama, included for Claude |

---

## 1. Graph Schema Design

### 1.1 Node Types (Labels)

```
MARKET ENTITIES                        TRADING CONCEPTS
├── Ticker      {symbol, name,         ├── Strategy     {name, category, win_rate,
│                created_at}           │                 created_at, updated_at}
├── Company     {name, cik,            ├── Structure    {name, type}
│                created_at}           │                (bull-call-spread, shares, etc.)
├── Sector      {name}                 ├── Pattern      {name, description, win_rate}
├── Industry    {name}                 ├── Bias         {name, description}
└── Product     {name, maker}          ├── Signal       {name, source}
                                       └── Risk         {name, category}
EVENTS
├── EarningsEvent {quarter, date}      METRICS
├── Catalyst      {type, description,  ├── FinancialMetric {name, category}
│                  date, created_at}   └── PriceLevel     {value, type}
├── Conference    {name, date}             (support, resistance)
└── MacroEvent    {name, type, date}

PEOPLE                                 ANALYSIS
├── Executive   {name, title}          ├── Analysis  {id, type, created_at, updated_at,
└── Analyst     {name, firm}           │              extraction_version}
                                       ├── Trade     {id, direction, outcome,
                                       │              entry_date, exit_date, created_at}
PROVENANCE                             └── Learning  {id, rule, category, created_at}
├── Document    {id, type, file_path,
│                created_at}           TIME
└── (used for [:EXTRACTED_FROM])       └── Timeframe  {name, duration}
                                           (intraday, swing, position)
```

**Common temporal properties**: `created_at` (when node was added to graph), `updated_at` (last modification).
Event nodes also have domain-specific dates (`date`, `entry_date`, `exit_date`).
**Extraction tracking**: `extraction_version` tracks which prompt version created the entity (for selective re-extraction).

**16 entity types** — all discoverable from trading analysis text. Types like
`Index`, `Insider`, `FundManager`, `Filing` are intentionally excluded until
real documents reference them.

### 1.2 Relationship Types

```
STRUCTURAL                              TRADING
(Company)─[:ISSUED]────────>(Ticker)    (Strategy)─[:WORKS_FOR]──>(Ticker)
(Company)─[:IN_SECTOR]─────>(Sector)    (Strategy)─[:USES]───────>(Structure)
(Company)─[:IN_INDUSTRY]───>(Industry)  (Bias)─────[:DETECTED_IN]>(Trade)
(Company)─[:MAKES]─────────>(Product)   (Pattern)──[:OBSERVED_IN]>(Ticker)
(Executive)─[:LEADS]───────>(Company)   (Signal)───[:INDICATES]──>(Ticker)

COMPETITIVE                             EVENTS
(Company)─[:COMPETES_WITH]─>(Company)   (Ticker)──[:HAS_EARNINGS]──>(EarningsEvent)
(Company)─[:SUPPLIES_TO]──>(Company)    (Ticker)──[:AFFECTED_BY]───>(Catalyst)
(Company)─[:CUSTOMER_OF]──>(Company)    (Ticker)──[:EXPOSED_TO]────>(MacroEvent)
(Ticker)──[:CORRELATED_WITH]>(Ticker)   (Risk)────[:THREATENS]─────>(Ticker)

ANALYSIS                                LEARNING
(Analysis)─[:ANALYZES]─────>(Ticker)    (Learning)──[:DERIVED_FROM]──>(Trade)
(Analysis)─[:MENTIONS]─────>(any)       (Learning)──[:ADDRESSES]────>(Bias)
(Trade)────[:BASED_ON]─────>(Analysis)  (Learning)──[:UPDATES]──────>(Strategy)
(Trade)────[:TRADED]───────>(Ticker)    (Risk)──────[:MITIGATED_BY]─>(Strategy)
(Analyst)──[:COVERS]───────>(Ticker)
```

~20 relationship types covering market structure, competition, trading decisions,
and the learning feedback loop.

### 1.3 Relationship Properties

Some relationships carry properties beyond just connecting nodes:

```cypher
[:CORRELATED_WITH {coefficient, period, calculated_at}]
[:COVERS {rating, target_price, updated_at}]
[:DETECTED_IN {severity, impact_description}]
[:WORKS_FOR {win_rate, sample_size, last_used}]
[:EXTRACTED_FROM {field_path, confidence, extracted_at}]
```

### 1.4 Source Document Linkage

Every extracted entity links back to its source for auditability:

```cypher
(Document {id, type, file_path, created_at})

(Entity)-[:EXTRACTED_FROM {confidence, field_path}]->(Document)
```

This enables:

- "Where did this entity come from?" → traverse `[:EXTRACTED_FROM]`
- "What entities came from this analysis?" → reverse traversal
- Re-extraction when prompts improve

### 1.5 Constraints & Indexes

```cypher
-- Unique constraints
CREATE CONSTRAINT ticker_symbol IF NOT EXISTS
  FOR (t:Ticker) REQUIRE t.symbol IS UNIQUE;
CREATE CONSTRAINT company_name IF NOT EXISTS
  FOR (c:Company) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT analysis_id IF NOT EXISTS
  FOR (a:Analysis) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT trade_id IF NOT EXISTS
  FOR (t:Trade) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT learning_id IF NOT EXISTS
  FOR (l:Learning) REQUIRE l.id IS UNIQUE;
CREATE CONSTRAINT strategy_name IF NOT EXISTS
  FOR (s:Strategy) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT bias_name IF NOT EXISTS
  FOR (b:Bias) REQUIRE b.name IS UNIQUE;

-- Additional unique constraints (all named entities)
CREATE CONSTRAINT sector_name IF NOT EXISTS
  FOR (s:Sector) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT industry_name IF NOT EXISTS
  FOR (i:Industry) REQUIRE i.name IS UNIQUE;
CREATE CONSTRAINT pattern_name IF NOT EXISTS
  FOR (p:Pattern) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT risk_name IF NOT EXISTS
  FOR (r:Risk) REQUIRE r.name IS UNIQUE;
CREATE CONSTRAINT signal_name IF NOT EXISTS
  FOR (s:Signal) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT product_name IF NOT EXISTS
  FOR (p:Product) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS
  FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT timeframe_name IF NOT EXISTS
  FOR (t:Timeframe) REQUIRE t.name IS UNIQUE;

-- Indexes for traversal queries
CREATE INDEX ticker_symbol_idx IF NOT EXISTS FOR (t:Ticker) ON (t.symbol);
CREATE INDEX earnings_date_idx IF NOT EXISTS FOR (e:EarningsEvent) ON (e.date);
CREATE INDEX analysis_type_idx IF NOT EXISTS FOR (a:Analysis) ON (a.type);
CREATE INDEX analysis_created_idx IF NOT EXISTS FOR (a:Analysis) ON (a.created_at);
CREATE INDEX trade_outcome_idx IF NOT EXISTS FOR (t:Trade) ON (t.outcome);
CREATE INDEX trade_created_idx IF NOT EXISTS FOR (t:Trade) ON (t.created_at);
CREATE INDEX catalyst_type_idx IF NOT EXISTS FOR (c:Catalyst) ON (c.type);
CREATE INDEX catalyst_date_idx IF NOT EXISTS FOR (c:Catalyst) ON (c.date);
CREATE INDEX sector_name_idx IF NOT EXISTS FOR (s:Sector) ON (s.name);
CREATE INDEX learning_category_idx IF NOT EXISTS FOR (l:Learning) ON (l.category);

-- Full-text search for entity discovery
CALL db.index.fulltext.createNodeIndex(
  'entitySearch', ['Ticker','Company','Executive','Product','Pattern','Risk'], ['name','symbol','description']
);

-- Trading Intelligence indexes (Phase 5)
CREATE INDEX trade_pnl_idx IF NOT EXISTS FOR (t:Trade) ON (t.pnl_percent);
CREATE INDEX trade_conviction_idx IF NOT EXISTS FOR (t:Trade) ON (t.stated_conviction);
CREATE INDEX trade_exit_trigger_idx IF NOT EXISTS FOR (t:Trade) ON (t.exit_trigger);
CREATE INDEX trade_status_idx IF NOT EXISTS FOR (t:Trade) ON (t.status);
CREATE INDEX strategy_win_rate_idx IF NOT EXISTS FOR (s:Strategy) ON (s.win_rate);
CREATE INDEX strategy_profit_factor_idx IF NOT EXISTS FOR (s:Strategy) ON (s.profit_factor);
CREATE INDEX strategy_last_used_idx IF NOT EXISTS FOR (s:Strategy) ON (s.last_used);
CREATE INDEX bias_occurrences_idx IF NOT EXISTS FOR (b:Bias) ON (b.total_occurrences);
CREATE INDEX pattern_reliability_idx IF NOT EXISTS FOR (p:Pattern) ON (p.reliability_score);
CREATE INDEX learning_effectiveness_idx IF NOT EXISTS FOR (l:Learning) ON (l.effectiveness_score);
CREATE INDEX learning_compliance_idx IF NOT EXISTS FOR (l:Learning) ON (l.compliance_rate);
```

---

## 2. Component Architecture

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                           Extraction Triggers                                  │
├─────────────┬───────────────┬─────────────┬─────────────┬─────────────────────┤
│  Claude     │  Ollama Batch │  Manual CLI │  Python API │  HTTP Webhook       │
│  Skills     │  (re-process) │  (ad-hoc)   │  (scripts)  │  (external systems) │
│  (real-time │  qwen3:8b     │ orchestrator│ from any .py│  POST /extract      │
│   in-context│  field-by-    │ graph       │ import and  │  with file_path or  │
│   highest   │  field, $0    │ extract FILE│ call direct │  content payload    │
│   quality)  │               │             │             │                     │
└──────┬──────┴───────┬───────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │              │              │             │                 │
       ▼              ▼              ▼             ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                graph/extract.py                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Pass 1: Entity Extraction (per text field)              │   │
│  │  → Send field text + entity type list to LLM             │   │
│  │  → Receive JSON: [{type, value, confidence, evidence}]   │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Pass 2: Relationship Extraction (per document)          │   │
│  │  → Send all discovered entities + source text to LLM     │   │
│  │  → Receive JSON: [{from, relation, to, confidence}]      │   │
│  └────────────────────────┬─────────────────────────────────┘   │
│                           ▼                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  graph/normalize.py                                       │   │
│  │  • Separator standardization (underscores → hyphens)     │   │
│  │  • Ticker resolution (NVIDIA → NVDA)                     │   │
│  │  • Case normalization (types: PascalCase, values: Title) │   │
│  │  • Cross-doc merge (same entity = single node)           │   │
│  │  • Alias resolution (GOOGL/GOOG/Alphabet → one node)    │   │
│  └────────────────────────┬─────────────────────────────────┘   │
└───────────────────────────┼─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                graph/layer.py — TradingGraph                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  connect() / close()          — Neo4j session management │   │
│  │  merge_node(label, key, props)— MERGE with properties    │   │
│  │  merge_relation(from, rel, to)— MERGE relationship       │   │
│  │  find_related(symbol, depth)  — subgraph traversal       │   │
│  │  get_sector_peers(symbol)     — preset query             │   │
│  │  get_risks(symbol)            — preset query             │   │
│  │  get_bias_history()           — preset query             │   │
│  │  run_cypher(query, params)    — raw Cypher execution     │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                Neo4j (nexus-neo4j)                               │
│  bolt://localhost:7688 · http://localhost:7475                    │
│  Auth: neo4j/${NEO4J_PASS} · Plugins: APOC                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Sources — Text Fields for Extraction

The graph is populated by extracting entities from **real** analysis documents
as they are produced. Template/sample files in the knowledge base are NOT
processed. Extraction targets by document type:

### 3.1 Extraction Fields by Doc Type

| Doc Type | Text Fields to Extract From |
|----------|-----------------------------|
| **earnings-analysis** | `customer_demand.customers[].key_quote`, `competitive_context.*`, `steel_man.bear_case`, `recent_developments[].event`, thesis fields |
| **stock-analysis** | `thesis.detailed`, `catalyst.description`, `what_is_priced_in.*`, `bias_checks.*.analysis`, `decision_rationale` |
| **research** | `key_finding`, `data_points[].quote`, `data_points[].implication`, `risks[].risk`, `risks[].mitigation` |
| **ticker-profile** | `company.description`, `what_works[]`, `watch_out_for[].risk`, `notes[].note`, `trading_patterns.*` |
| **trade-journal** | `thesis.summary`, `thesis.edge`, `what_worked[]`, `what_failed[]`, `lessons[]`, `biases_detected[].impact` |
| **strategy** | `overview.description`, `edge_source`, `known_weaknesses[].weakness`, `known_weaknesses[].countermeasure` |
| **learning** | `pattern.description`, `pattern.behavior`, `root_cause.*`, `countermeasure.rule`, `evidence.observations[]` |

### 3.2 Processing Approach

Each text field is sent **individually** to the LLM (1-5 sentences per call,
10-30s per response). Results are merged per document, then deduplicated across
documents. This avoids the extraction timeout that killed LightRAG (which sent
entire documents to the LLM).

### 3.3 Extraction Prompt Template

Domain-specific prompt for entity extraction (`graph/prompts.py`):

```python
ENTITY_EXTRACTION_PROMPT = """
Extract trading-relevant entities from this text. Return JSON only.

ENTITY TYPES (use exactly these labels):
- Ticker: Stock symbols (NVDA, AAPL, MSFT)
- Company: Company names (NVIDIA, Apple Inc, Microsoft)
- Executive: Named executives with titles (Jensen Huang CEO)
- Product: Products/services (Blackwell GPU, iPhone, Azure)
- Catalyst: Events that move stock price (earnings beat, FDA approval)
- Sector: Market sectors (Technology, Healthcare)
- Industry: Specific industries (Semiconductors, Cloud Computing)
- Pattern: Trading patterns you observe (gap and go, earnings drift)
- Bias: Cognitive biases (loss aversion, confirmation bias)
- Strategy: Trading strategies (earnings momentum, mean reversion)
- Risk: Identified risks (concentration risk, macro exposure)
- Signal: Trading signals (RSI oversold, volume breakout)
- EarningsEvent: Quarterly/annual earnings reports (Q4 2025, FY 2025)
- MacroEvent: Macro-economic events (Fed rate decision, CPI release)
- Timeframe: Time horizons (intraday, swing, position)

TEXT:
{text}

Return JSON array: [{{"type": "...", "value": "...", "confidence": 0.0-1.0, "evidence": "quote from text"}}]
Only extract entities explicitly mentioned. Do not infer.
"""

RELATION_EXTRACTION_PROMPT = """
Given these entities extracted from a trading document, identify relationships between them.

ENTITIES:
{entities_json}

RELATIONSHIP TYPES (use exactly these):
- ISSUED: Company issued Ticker
- IN_SECTOR / IN_INDUSTRY: Company belongs to Sector/Industry
- COMPETES_WITH / SUPPLIES_TO / CUSTOMER_OF: Company relationships
- LEADS: Executive leads Company
- COVERS: Analyst covers Ticker
- AFFECTED_BY: Ticker affected by Catalyst
- DETECTED_IN: Bias detected in Trade
- WORKS_FOR: Strategy works for Ticker
- DERIVED_FROM: Learning derived from Trade
- ADDRESSES: Learning addresses Bias

SOURCE TEXT:
{text}

Return JSON array: [{{"from": {{"type": "...", "value": "..."}}, "relation": "...", "to": {{"type": "...", "value": "..."}}, "confidence": 0.0-1.0, "evidence": "quote"}}]
Only extract relationships explicitly stated or strongly implied. Do not infer weak connections.
"""
```

### 3.4 Disambiguation Rules

Beyond alias tables, these rules resolve ambiguous entities:

| Ambiguity | Resolution Rule |
|-----------|-----------------|
| Company vs Ticker | If appears with $ prefix or in price context → Ticker; otherwise → Company |
| "Apple" in trading context | Default to AAPL unless food/agriculture context |
| Person name only | Look up in alias table; if not found, create Executive with `needs_review: true` |
| Generic pattern name | Normalize to canonical form (e.g., "gap up" → "gap-and-go") |
| Same name, different entity | Append disambiguator: "Apple (company)" vs "Apple (product)" |
| Strategy vs Pattern | A Strategy is a repeatable playbook (has entry/exit rules). A Pattern is an observed market behavior (technical or behavioral). E.g., "earnings momentum" = Strategy if it has rules, Pattern if it's a price observation |

Disambiguation is applied in `graph/normalize.py` before MERGE.

---

## 4. Extraction Pipeline

### 4.1 Trigger Flow

```
Skill produces real analysis
        │
        ▼
┌─────────────────────────┐         ┌──────────────────────┐
│ Claude (in-context)     │         │ Ollama (batch/re-run)│
│ • Already has full doc  │         │ • Field-by-field     │
│ • Highest quality       │         │ • Free, local        │
│ • Extracts during skill │         │ • CLI triggered      │
│   execution             │         │                      │
└──────────┬──────────────┘         └──────────┬───────────┘
           │                                   │
           └───────────────┬───────────────────┘
                           ▼
                 Extraction Result (JSON)
                   entities[]
                   relations[]
                   source_doc
                   extracted_at
                           │
                           ▼
                 ┌─────────────────┐
                 │  Normalize      │
                 │  + Merge        │
                 │  + Dedup        │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  MERGE into     │
                 │  Neo4j          │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │  Log extraction │
                 │  (audit trail)  │
                 └─────────────────┘
```

### 4.2 Extraction Mode Selection

| Trigger | Default LLM | Why | Cost |
|---------|-------------|-----|------|
| **Claude Skill** (real-time) | Claude (in-context) | Already has full context, highest quality | Included |
| **CLI batch** (`graph reextract`) | Ollama (qwen3:8b) | Local, free, field-by-field | $0 |
| **CLI ad-hoc** (`graph extract FILE`) | Ollama (configurable) | User choice via `--extractor` flag | Depends |
| **Python API** (`extract_document()`) | Ollama (configurable) | Caller specifies `extractor` param | Depends |
| **HTTP Webhook** (`POST /extract`) | Ollama (configurable) | Request body specifies `extractor` | Depends |

### 4.3 LLM Backend Options

All extraction modes support multiple LLM backends via unified interface:

| Backend | Config Key | Models | Cost | Use Case |
|---------|------------|--------|------|----------|
| **Ollama** (local) | `ollama` | qwen3:8b, llama3, mistral | $0 | Default for batch, always available |
| **Claude** (in-context) | `claude` | claude-3-5-sonnet | Included | Real-time during skills |
| **LiteLLM + OpenRouter** | `openrouter` | claude-3-5-sonnet, gpt-4o, mistral-large | ~$0.001-0.01/call | Backup when Ollama slow, quality boost |
| **Claude API** (direct) | `claude-api` | claude-3-5-sonnet, claude-3-haiku | ~$0.003/call | Standalone scripts, high quality |

**Fallback chain** (configurable in `trader/graph/config.yaml`):

```yaml
extraction:
  default_extractor: ollama
  fallback_chain:
    - ollama           # Try local first ($0)
    - openrouter       # Fallback to cloud if Ollama fails/times out
  timeout_seconds: 30

  # LiteLLM/OpenRouter config
  openrouter:
    api_key: ${OPENROUTER_API_KEY}
    model: "anthropic/claude-3-5-sonnet"  # or "openai/gpt-4o", "mistralai/mistral-large"
    fallback_model: "anthropic/claude-3-haiku"  # cheaper fallback

  # Direct Claude API (when not using OpenRouter)
  claude_api:
    api_key: ${ANTHROPIC_API_KEY}
    model: "claude-3-5-sonnet-20241022"
```

**LiteLLM benefits**:
- Unified API for 100+ models (OpenAI, Anthropic, Cohere, Mistral, etc.)
- Automatic retries and fallbacks
- Cost tracking and rate limiting
- OpenRouter integration for pay-per-use without API keys per provider

### 4.3 Extraction Result Schema

```yaml
extraction:
  source:
    doc_id: "EA-NVDA-Q4-2025"
    doc_type: earnings-analysis
    file_path: "knowledge/analysis/earnings/NVDA_20250418T0900.yaml"
    text_hash: "sha256:abc123..."
    extracted_at: "2026-02-19T10:00:00Z"
    extractor: ollama|claude  # which LLM performed extraction

  entities:
    - type: Company
      value: Microsoft
      confidence: 0.95
      evidence: "Microsoft raised cloud capex 79% to $80B"
      properties:
        role: customer

    - type: Product
      value: Blackwell
      confidence: 0.90
      evidence: "Blackwell GPU architecture driving data center growth"
      properties:
        maker: NVIDIA

  relations:
    - from: {type: Company, value: "Microsoft"}
      relation: CUSTOMER_OF
      to: {type: Company, value: "NVIDIA"}
      confidence: 0.88
      evidence: "Microsoft is the largest cloud customer for NVIDIA GPUs"

    - from: {type: Ticker, value: "NVDA"}
      relation: AFFECTED_BY
      to: {type: Catalyst, value: "AI CapEx acceleration"}
      confidence: 0.82
      evidence: "all 4 hyperscalers raising AI capex materially"
```

### 4.4 Extraction Logging

Extractions are logged to `trader/logs/graph_extractions.jsonl` (one JSON line
per extraction run). No file-based staging area — the log serves as audit trail
and can be replayed if needed.

```jsonl
{"ts":"2026-02-19T10:00:00Z","doc":"EA-NVDA-Q4-2025","extractor":"claude","entities":12,"relations":8,"status":"committed"}
```

---

## 5. Normalization Rules

| Rule | Example Input | Normalized Output |
|------|-----------|-----------|
| **Separators** | `loss_aversion` | `loss-aversion` |
| **Ticker resolution** | `"NVIDIA"` in text | Links to `Ticker(NVDA)` node |
| **Case: entity types** | `ticker`, `TICKER` | `Ticker` (PascalCase) |
| **Case: entity values** | `semiconductors` | `Semiconductors` (Title Case) |
| **ID prefix stripping** | `STR-earnings-momentum` / `earnings-momentum` | Same node |
| **Alias resolution** | `GOOGL` / `GOOG` / `Google` / `Alphabet` | One `Company` node |
| **Cross-doc merge** | Same entity from 3 docs | Single node, merged properties |
| **Self-reference** | `this` in relations | Resolved to `_meta.id` at extraction time |

Alias tables are stored in `trader/graph/aliases.yaml`:
```yaml
tickers:
  GOOG: GOOGL
  BRK.A: BRK-B
companies:
  Alphabet: {ticker: GOOGL}
  Google: {ticker: GOOGL}
  Meta Platforms: {ticker: META}
  Facebook: {ticker: META}
```

---

## 6. Integration Points

### 6.1 Orchestrator CLI (new `graph` command group)

```bash
# Schema management
python orchestrator.py graph init              # Create constraints + indexes
python orchestrator.py graph reset             # Wipe graph (dev only)
python orchestrator.py graph migrate --to X.Y.Z  # Run migrations to target version

# Extraction (for real documents only)
python orchestrator.py graph extract FILE      # Extract from one doc
python orchestrator.py graph extract --dir DIR # Extract from directory (skips template.yaml and files without ISO 8601 date in filename)
python orchestrator.py graph reextract --all   # Re-extract all docs (after prompt improvements)
python orchestrator.py graph reextract --since 2026-01-01  # Re-extract recent docs
python orchestrator.py graph reextract --version 1.0.0     # Re-extract entities created with older prompt version

# Queries
python orchestrator.py graph status            # Node/edge counts by type
python orchestrator.py graph search TICKER     # Subgraph around ticker
python orchestrator.py graph peers TICKER      # Sector peers + competitors
python orchestrator.py graph risks TICKER      # Known risks
python orchestrator.py graph biases            # Bias history across trades
python orchestrator.py graph query "CYPHER"    # Raw Cypher
```

### 6.2 Claude Skills — Post-Execution Hook

After each skill saves a real analysis YAML, it calls the extraction pipeline:

```
## Post-Execution: Graph Integration

After saving the analysis file:
1. Call `python orchestrator.py graph extract <saved_file>`
2. Or: extract entities inline (Claude already has the full context)
3. Push extracted entities/relations to Neo4j via graph/layer.py
```

Skills that trigger extraction:
- `earnings-analysis` → Ticker, Company, EarningsEvent, Catalyst, Product
- `stock-analysis` → Ticker, Catalyst, Sector, Industry, Pattern
- `research-analysis` → Company, Product, MacroEvent, Risk
- `trade-journal` → Trade, Bias, Pattern, Strategy
- `post-trade-review` → Learning, Bias, Strategy updates

### 6.3 Python API (Direct Import)

Any Python code can call the extraction pipeline directly:

```python
from trader.graph.extract import extract_document, extract_text
from trader.graph.layer import TradingGraph

# Option 1: Extract from YAML file
result = extract_document(
    file_path="trading/knowledge/analysis/earnings/NVDA_20260219T0900.yaml",
    extractor="ollama",  # or "claude" (requires API key)
    commit=True          # False to preview without committing
)
print(f"Extracted {len(result.entities)} entities, {len(result.relations)} relations")

# Option 2: Extract from raw text (for external content)
result = extract_text(
    text="NVIDIA reported Q4 earnings beat. Jensen Huang announced Blackwell ramp.",
    doc_type="article",
    source_url="https://example.com/article",
    extractor="ollama"
)

# Option 3: Direct graph operations (skip extraction)
with TradingGraph() as g:
    g.merge_node("Ticker", "symbol", {"symbol": "NVDA", "name": "NVIDIA Corp"})
    g.merge_relation(
        from_node=("Company", "NVIDIA"),
        rel_type="ISSUED",
        to_node=("Ticker", "NVDA")
    )
    peers = g.get_sector_peers("NVDA")
```

### 6.4 HTTP Webhook API

For external systems (CI/CD, monitoring tools, other services):

```python
# trader/graph/webhook.py — FastAPI endpoints

POST /api/graph/extract
{
    "file_path": "trading/knowledge/analysis/earnings/NVDA_20260219T0900.yaml",
    "extractor": "ollama",
    "commit": true
}
# Returns: {"entities": 12, "relations": 8, "status": "committed"}

POST /api/graph/extract-text
{
    "text": "NVIDIA reported Q4 earnings beat...",
    "doc_type": "article",
    "source_url": "https://...",
    "extractor": "ollama"
}
# Returns: {"entities": [...], "relations": [...], "committed": true}

GET /api/graph/status
# Returns: {"nodes": {"Ticker": 45, "Company": 32, ...}, "edges": {"ISSUED": 45, ...}}

POST /api/graph/query
{
    "cypher": "MATCH (t:Ticker {symbol: $symbol})-[r]-(n) RETURN t, r, n",
    "params": {"symbol": "NVDA"}
}
# Returns: query results as JSON
```

Webhook server runs as optional sidecar or integrated into service.py:

```bash
# Standalone
uvicorn trader.graph.webhook:app --host 0.0.0.0 --port 8080

# Or add to docker-compose.yml as graph-api service
```

### 6.5 Service Integration

```python
# In service.py tick loop — watch for new YAML files
# Re-extract if extraction logic version has changed
# Periodic graph consistency checks
```

---

## 7. File Structure

```
trader/
├── graph/
│   ├── __init__.py           # Package init, SCHEMA_VERSION, EXTRACT_VERSION
│   ├── schema.py             # Neo4j schema init (run constraints/indexes)
│   ├── layer.py              # TradingGraph class (connect, CRUD, query)
│   ├── extract.py            # Entity/relationship extraction via LLM
│   ├── prompts.py            # Domain-specific extraction prompt templates
│   ├── normalize.py          # Entity dedup, name standardization, merge
│   ├── aliases.yaml          # Ticker/company alias resolution table
│   ├── query.py              # Preset query patterns for CLI
│   ├── webhook.py            # FastAPI HTTP endpoints for external systems
│   ├── migrations/           # Schema migration scripts (v1_0_0_to_v1_1_0.cypher)
│   │
│   │   # Trading Intelligence Layer (Phase 5-7)
│   ├── intelligence/
│   │   ├── __init__.py       # Trading intelligence module init
│   │   ├── outcomes.py       # Outcome-weighted traversal algorithms
│   │   ├── calibration.py    # Conviction calibration tracking
│   │   ├── bias_tracker.py   # Bias detection and chain analysis
│   │   ├── strategy_perf.py  # Strategy performance and decay detection
│   │   ├── patterns.py       # Pattern-to-outcome matching
│   │   ├── exits.py          # Exit trigger library and effectiveness
│   │   ├── portfolio.py      # Portfolio correlation and risk analysis
│   │   └── learning.py       # Learning loop integration
│   │
│   │   # Graph-RAG Hybrid (Phase 7)
│   ├── hybrid/
│   │   ├── __init__.py       # Hybrid context module init
│   │   ├── context.py        # Combined graph+RAG context builder
│   │   └── feedback.py       # Post-trade feedback loop processor
│   │
│   │   # Advanced Analytics (Phase 6)
│   └── analytics/
│       ├── __init__.py       # Analytics module init
│       ├── centrality.py     # Entity importance ranking (PageRank, etc.)
│       ├── communities.py    # Cluster detection (Louvain, etc.)
│       ├── temporal.py       # Time-windowed analysis
│       └── export.py         # Visualization export (Mermaid, GraphViz)
│
├── db/
│   ├── init.sql              # (existing) PostgreSQL schema
│   └── neo4j_schema.cypher   # Neo4j constraints and indexes
└── orchestrator.py           # (modify) add `graph` command group
```

---

## 8. Example Queries

### 8.1 Core Trading Queries

```cypher
// "What biases appear in my NVDA trades?"
MATCH (t:Trade)-[:TRADED]->(tk:Ticker {symbol:'NVDA'}),
      (b:Bias)-[:DETECTED_IN]->(t)
RETURN b.name, count(t) AS occurrences ORDER BY occurrences DESC

// "Which strategies work for earnings catalysts?"
MATCH (s:Strategy)-[:WORKS_FOR]->(tk:Ticker),
      (tk)-[:AFFECTED_BY]->(c:Catalyst {type:'earnings'})
RETURN s.name, collect(DISTINCT tk.symbol) AS tickers, count(*) AS uses

// "NVDA competitive landscape"
MATCH (c1:Company)-[:ISSUED]->(t:Ticker {symbol:'NVDA'}),
      (c1)-[:COMPETES_WITH]-(c2:Company)-[:ISSUED]->(t2:Ticker)
RETURN c2.name, t2.symbol

// "Risks across open positions"
MATCH (r:Risk)-[:THREATENS]->(tk:Ticker)<-[:TRADED]-(t:Trade)
WHERE t.status = 'open'
RETURN r.name, collect(DISTINCT tk.symbol) AS exposed_tickers

// "Learning loop: bias → trade → lesson"
MATCH path = (b:Bias)-[:DETECTED_IN]->(t:Trade)<-[:DERIVED_FROM]-(l:Learning)
RETURN b.name, t.id, l.rule

// "Supply chain for NVDA"
MATCH (c1:Company)-[:ISSUED]->(t:Ticker {symbol:'NVDA'}),
      (c2:Company)-[:SUPPLIES_TO]->(c1)
RETURN c2.name, c2.cik

// "What did I learn from loss-aversion?"
MATCH (b:Bias {name:'loss-aversion'})<-[:ADDRESSES]-(l:Learning)
RETURN l.id, l.rule, l.category
```

### 8.2 Trading Intelligence Queries

```cypher
// "My conviction calibration — am I overconfident?"
MATCH (tr:Trade)
WHERE tr.stated_conviction IS NOT NULL
WITH tr.stated_conviction as level,
     avg(CASE WHEN tr.outcome = 'win' THEN 1.0 ELSE 0.0 END) as actual,
     count(*) as n
RETURN level, actual, n,
       CASE level WHEN 5 THEN 0.8 WHEN 4 THEN 0.7 WHEN 3 THEN 0.6
                  WHEN 2 THEN 0.5 ELSE 0.4 END as expected,
       actual - CASE level WHEN 5 THEN 0.8 WHEN 4 THEN 0.7 WHEN 3 THEN 0.6
                           WHEN 2 THEN 0.5 ELSE 0.4 END as calibration_error
ORDER BY level

// "Which biases cost me the most money?"
MATCH (b:Bias)-[:DETECTED_IN]->(tr:Trade)
WITH b.name as bias,
     count(tr) as occurrences,
     sum(tr.pnl_percent) as total_impact,
     avg(tr.pnl_percent) as avg_impact
RETURN bias, occurrences, total_impact, avg_impact
ORDER BY total_impact ASC
LIMIT 10

// "Best exit triggers for my strategies"
MATCH (tr:Trade)-[:BASED_ON]->(s:Strategy)
WHERE tr.exit_trigger IS NOT NULL
WITH s.name as strategy, tr.exit_trigger as exit_type,
     avg(tr.pnl_percent) as avg_pnl, count(*) as uses
RETURN strategy, exit_type, avg_pnl, uses
ORDER BY strategy, avg_pnl DESC

// "What patterns predicted profitable trades?"
MATCH (p:Pattern)-[:OBSERVED_IN]->(tk:Ticker)<-[:TRADED]-(tr:Trade)
WHERE tr.pnl_percent > 0
WITH p.name as pattern,
     count(tr) as profitable_trades,
     avg(tr.pnl_percent) as avg_gain
ORDER BY profitable_trades DESC
RETURN pattern, profitable_trades, avg_gain
LIMIT 10

// "Portfolio correlation risk — shared factors"
MATCH (tr1:Trade {status:'open'})-[:TRADED]->(t1:Ticker),
      (tr2:Trade {status:'open'})-[:TRADED]->(t2:Ticker),
      (t1)-[]-(shared)-[]-(t2)
WHERE t1 <> t2
WITH t1.symbol as sym1, t2.symbol as sym2,
     count(DISTINCT shared) as shared_count,
     collect(DISTINCT labels(shared)[0])[0..3] as shared_types
WHERE shared_count >= 2
RETURN sym1, sym2, shared_count, shared_types

// "Learning rules I keep violating"
MATCH (l:Learning)<-[:VIOLATED]-(tr:Trade)
WITH l.rule as rule, l.category as category,
     count(tr) as violations,
     avg(tr.pnl_percent) as violation_cost
RETURN rule, category, violations, violation_cost
ORDER BY violations DESC

// "Strategy decay — performance degradation"
MATCH (s:Strategy)<-[:BASED_ON]-(tr:Trade)
WITH s, tr ORDER BY tr.entry_date
WITH s.name as strategy,
     collect(tr.pnl_percent) as returns,
     count(tr) as n
WHERE n >= 10
WITH strategy, returns, n,
     reduce(s = 0.0, x IN returns[0..n/2] | s + x) / (n/2) as early_avg,
     reduce(s = 0.0, x IN returns[n/2..] | s + x) / (n/2) as recent_avg
RETURN strategy, early_avg, recent_avg,
       recent_avg - early_avg as performance_change
ORDER BY performance_change ASC
```

---

## 9. Implementation Phases

### Phase 1 — Foundation + Extraction Engine (~6 hrs)

| Deliverable | Description |
|-------------|-------------|
| `db/neo4j_schema.cypher` | Constraints + indexes for 16 entity types |
| `graph/schema.py` | Python schema initializer |
| `graph/layer.py` | TradingGraph class (MERGE-based CRUD) |
| `graph/prompts.py` | Domain-specific extraction prompts for Ollama |
| `graph/extract.py` | Two-pass field-by-field extraction |
| `graph/normalize.py` | Dedup + standardization + alias resolution |
| `graph/aliases.yaml` | Initial ticker/company alias table |
| `graph/query.py` | Preset query patterns |
| `orchestrator.py` | `graph init`, `graph extract`, `graph status`, `graph search` |
| **Test** | Extract from a synthetic test document, verify graph |

### Phase 2 — Skills Integration (~3 hrs)

| Deliverable | Description |
|-------------|-------------|
| Skill post-hooks | Auto-extract after skill saves real analysis |
| Graph context injection | Query graph before analysis for related context |
| `_graph` enrichment | Write discovered entities back to YAML `_graph` section |

### Phase 3 — MCP Server + Advanced Queries (~4 hrs)

| Deliverable | Description |
|-------------|-------------|
| `mcp_trading_graph/` | MCP server wrapping extraction + query tools |
| Claude skills | `knowledge-extraction` and `graph-query` skills |
| Preset query library | Full set of CLI query commands |
| pgvector integration | Semantic search alongside graph (hybrid RAG) |

### Phase 4 — Production Hardening

| Deliverable | Description |
|-------------|-------------|
| Extraction quality monitoring | Track entity/relation counts, confidence distributions |
| Alias table expansion | Grow alias tables from real data |
| Graph visualization | AGE Viewer, Neo4j Browser, or Mermaid export |
| Service integration | Periodic sync + consistency checks in service.py |

---

## 10. Infrastructure

### Current Docker Stack

| Service | Container | Port | Role |
|---------|-----------|------|------|
| Neo4j 5 | nexus-neo4j | 7475 (http), 7688 (bolt) | Graph storage |
| PostgreSQL | nexus-postgres | 5433 | Nexus schema + future pgvector |
| IB Gateway | nexus-ib-gateway | 4002 | Market data + order execution |
| Ollama | (host) | 11434 | Local LLM for batch extraction |

### Dependencies

```
# trader/requirements.txt additions
neo4j>=5.0.0        # Neo4j Python driver
pyyaml>=6.0         # YAML parsing (likely already installed)
requests>=2.28.0    # Ollama API calls (likely already installed)
fastapi>=0.100.0    # HTTP webhook API (optional, for external integrations)
uvicorn>=0.23.0     # ASGI server for webhook (optional)
```

### LightRAG Deprecation

Once Phase 1 is validated, the following can be removed:

| Item | Action |
|------|--------|
| `nexus-lightrag` container | Stop and remove from docker-compose.yml |
| LightRAG env vars in docker-compose | Remove `LLM_BINDING`, `EMBEDDING_BINDING`, etc. |
| `trading/workflows/.lightrag/` | Delete directory |
| LightRAG sync scripts | Delete if present |

---

## 11. Error Handling & Resilience

### 11.1 Extraction Failures

| Failure Mode | Behavior |
|--------------|----------|
| **Ollama timeout** | Retry 2x with exponential backoff (10s, 30s), then skip field and log |
| **Malformed JSON from LLM** | Log raw response, skip extraction, continue to next field |
| **Neo4j connection failure** | Queue extraction result to `trader/logs/pending_commits.jsonl`, retry on next run |
| **Partial document extraction** | Commit successful entities, log failed fields for re-processing |

### 11.2 Graceful Degradation

Skills must function even if graph is unavailable:

```python
# In skill post-hook
try:
    graph_extract(saved_file)
except GraphUnavailableError:
    log.warning(f"Graph extraction skipped for {saved_file} - Neo4j unavailable")
    # Skill output already saved to YAML - no data loss
```

### 11.3 Low-Confidence Extractions

| Confidence | Action |
|------------|--------|
| **≥ 0.7** | Commit to Neo4j |
| **0.5 - 0.7** | Commit with `confidence` property on node/edge for later review |
| **< 0.5** | Log but do not commit (too unreliable) |

---

## 12. Operations

### 12.1 Backup Strategy

```bash
# Daily Neo4j backup (Community Edition — requires stop/start)
# neo4j-admin dump requires Enterprise; use filesystem copy for Community
docker stop nexus-neo4j
docker cp nexus-neo4j:/data/ ~/backups/neo4j_data_$(date +%Y%m%d)/
docker start nexus-neo4j
```

### 12.2 Monitoring Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Node count by label | `graph status` | N/A (growth indicator) |
| Extraction success rate | `graph_extractions.jsonl` | < 90% over 24h |
| Avg confidence | Extraction logs | < 0.6 avg |
| Neo4j query latency | Application logs | > 500ms p95 |
| Pending commits queue | `pending_commits.jsonl` | > 10 items |

### 12.3 Graph Maintenance

```bash
# Periodic cleanup (run monthly)
python orchestrator.py graph prune --older-than 365d  # Archive old Trade/analysis nodes (re-labels to :Archived)
                                                       # Never prunes Learning, Bias, or Strategy nodes (core knowledge)
                                                       # Detaches relationships before archiving
python orchestrator.py graph dedupe                    # Merge duplicate entities
                                                       # Merge rules: latest updated_at wins for scalar props,
                                                       # highest confidence extraction wins for extracted props,
                                                       # relationships from all duplicates are preserved
python orchestrator.py graph validate                  # Check constraint violations
```

### 12.4 Schema Versioning

Schema version is tracked in `graph/__init__.py`:

```python
SCHEMA_VERSION = "1.0.0"    # Bump on breaking changes
EXTRACT_VERSION = "1.0.0"   # Bump when extraction prompts change
# Each entity stores extraction_version so selective re-extraction is possible
```

Migration strategy:

| Change Type | Action |
|-------------|--------|
| **Add new node label** | No migration needed (additive) |
| **Add new relationship type** | No migration needed (additive) |
| **Add property to existing nodes** | Run `graph migrate --version X.Y.Z` to backfill |
| **Rename label/relationship** | Create migration script, run in maintenance window |
| **Remove label/relationship** | Deprecate first, remove after 30 days |

Migration scripts stored in `trader/graph/migrations/` with naming: `v1_0_0_to_v1_1_0.cypher`

---

## 13. Testing Strategy

### 13.1 Unit Tests

| Module | Test Coverage |
|--------|---------------|
| `graph/normalize.py` | Alias resolution, case normalization, separator standardization |
| `graph/extract.py` | JSON parsing, field extraction, entity merging |
| `graph/layer.py` | MERGE operations, query builders (mock Neo4j) |

### 13.2 Integration Tests

| Test | Description |
|------|-------------|
| **Round-trip** | Extract → Commit → Query → Verify |
| **Idempotency** | Extract same doc twice → same graph state |
| **Alias resolution** | "NVIDIA" and "NVDA" → single node |

### 13.3 Test Fixtures

```text
trader/graph/tests/
├── fixtures/
│   ├── sample_earnings.yaml     # Synthetic earnings analysis
│   ├── sample_trade.yaml        # Synthetic trade journal
│   └── expected_extractions/    # Expected entity/relation output
├── test_normalize.py
├── test_extract.py
└── test_layer.py
```

---

## 14. Trading Intelligence Layer

Domain-specific graph analytics for improved trading decisions. These features transform the knowledge graph from passive storage into an active decision-support system.

### 14.1 Enhanced Entity Properties

Extend existing nodes with trading intelligence properties:

```cypher
-- Trade node with outcome tracking
(:Trade {
  id: string,
  direction: "long" | "short",
  outcome: "win" | "loss" | "breakeven",
  entry_date: datetime,
  exit_date: datetime,
  created_at: datetime,
  -- Trading intelligence additions:
  pnl_dollars: float,           -- Realized P&L
  pnl_percent: float,           -- Percentage return
  stated_conviction: int,       -- 1-5 scale at entry
  actual_edge: float,           -- Calculated post-trade (0.0-1.0)
  hold_duration_days: int,      -- Days in position
  exit_trigger: string,         -- What caused exit (stop, target, time, catalyst)
  thesis_accuracy: float        -- How accurate was entry thesis (0.0-1.0)
})

-- Strategy node with performance tracking
(:Strategy {
  name: string,
  category: string,
  win_rate: float,
  created_at: datetime,
  updated_at: datetime,
  -- Trading intelligence additions:
  sample_size: int,             -- Number of trades
  avg_pnl_percent: float,       -- Average return per trade
  profit_factor: float,         -- Gross profit / gross loss
  max_drawdown: float,          -- Worst peak-to-trough
  sharpe_ratio: float,          -- Risk-adjusted return
  last_used: datetime,          -- Detect strategy decay
  optimal_hold_days: float,     -- Average optimal holding period
  best_market_regime: string    -- "trending" | "ranging" | "volatile"
})

-- Bias node with impact tracking
(:Bias {
  name: string,
  description: string,
  -- Trading intelligence additions:
  total_occurrences: int,       -- How often detected
  avg_pnl_impact: float,        -- Average P&L when bias present
  worst_impact_trade: string,   -- Trade ID with worst impact
  effective_countermeasures: [string],  -- What works against this bias
  trigger_conditions: [string]  -- Conditions that activate this bias
})

-- Pattern node with predictive tracking
(:Pattern {
  name: string,
  description: string,
  win_rate: float,
  -- Trading intelligence additions:
  sample_size: int,
  avg_magnitude: float,         -- Average price move after pattern
  reliability_score: float,     -- Consistency of pattern (0.0-1.0)
  last_observed: datetime,
  optimal_timeframe: string,    -- Best timeframe for this pattern
  decay_rate: float             -- How quickly pattern effectiveness degrades
})

-- Learning node with effectiveness tracking
(:Learning {
  id: string,
  rule: string,
  category: string,
  created_at: datetime,
  -- Trading intelligence additions:
  compliance_rate: float,       -- How often rule is followed
  effectiveness_score: float,   -- Impact when followed vs ignored
  last_applied: datetime,
  violation_count: int,         -- Times rule was ignored
  successful_applications: int
})
```

### 14.2 Trading Intelligence Relationships

New relationship types for trading intelligence:

```cypher
-- Outcome tracking
(Trade)-[:RESULTED_IN {pnl: float, accuracy: float}]->(TradeOutcome)
(Strategy)-[:PERFORMED {win_rate: float, sample: int, period: string}]->(Ticker)
(Pattern)-[:PREDICTED {accuracy: float, sample: int}]->(PriceMove)

-- Bias chain detection (one bias triggering another)
(Bias)-[:TRIGGERED {frequency: float, lag_days: int}]->(Bias)
(Bias)-[:COUNTERED_BY {effectiveness: float}]->(Learning)

-- Conviction calibration
(Trade)-[:HAD_CONVICTION {stated: int, actual: float}]->(ConvictionRecord)

-- Strategy optimization
(Strategy)-[:OPTIMAL_FOR {win_rate: float, profit_factor: float}]->(Sector)
(Strategy)-[:OPTIMAL_FOR {win_rate: float, profit_factor: float}]->(Timeframe)
(Strategy)-[:DECAY_AFTER {days: int, effectiveness_drop: float}]->(MarketRegime)

-- Exit trigger tracking
(ExitTrigger)-[:EFFECTIVE_FOR {success_rate: float}]->(Strategy)
(ExitTrigger)-[:USED_IN]->(Trade)

-- Portfolio correlation
(Ticker)-[:RISK_CORRELATED {coefficient: float, period: string}]->(Ticker)
(Position)-[:OVERLAPS_RISK]->(Position)
```

### 14.3 Outcome-Weighted Graph Queries

Weight traversals by historical trade performance:

```cypher
// Find strategies with positive outcome weight for a ticker
MATCH (s:Strategy)-[w:WORKS_FOR]->(t:Ticker {symbol: $symbol}),
      (s)<-[:BASED_ON]-(tr:Trade)-[:TRADED]->(t)
WITH s,
     sum(CASE WHEN tr.outcome = 'win' THEN tr.pnl_percent ELSE 0 END) as total_wins,
     sum(CASE WHEN tr.outcome = 'loss' THEN abs(tr.pnl_percent) ELSE 0 END) as total_losses,
     count(tr) as sample
WHERE sample >= 3
RETURN s.name,
       total_wins / (total_wins + total_losses + 0.001) as win_weight,
       s.profit_factor,
       sample
ORDER BY win_weight DESC

// Rank entities by contribution to profitable trades
MATCH (e)-[r]-(tr:Trade)
WHERE tr.outcome = 'win' AND tr.pnl_percent > 0
WITH labels(e)[0] as entity_type, e.name as entity_name,
     sum(tr.pnl_percent) as total_contribution,
     count(tr) as appearances
RETURN entity_type, entity_name, total_contribution, appearances
ORDER BY total_contribution DESC
LIMIT 20
```

### 14.4 Bias Detection & Pattern Analysis

Track bias patterns across time and trades:

```cypher
// Bias frequency and impact over time
MATCH (b:Bias)-[:DETECTED_IN]->(tr:Trade)
WITH b, tr.entry_date as trade_date, tr.pnl_percent as impact
ORDER BY trade_date
WITH b.name as bias,
     collect({date: trade_date, impact: impact}) as occurrences,
     avg(impact) as avg_impact,
     count(*) as total
RETURN bias, total, avg_impact, occurrences[-5..] as recent_five
ORDER BY total DESC

// Bias chains (one bias triggering another)
MATCH (b1:Bias)-[:DETECTED_IN]->(t1:Trade),
      (b2:Bias)-[:DETECTED_IN]->(t2:Trade)
WHERE t2.entry_date > t1.entry_date
  AND t2.entry_date < t1.entry_date + duration('P7D')
  AND b1 <> b2
WITH b1, b2, count(*) as chain_count
WHERE chain_count >= 2
RETURN b1.name as trigger_bias, b2.name as subsequent_bias, chain_count
ORDER BY chain_count DESC

// Effective countermeasures for a specific bias
MATCH (b:Bias {name: $bias_name})<-[:ADDRESSES]-(l:Learning)
OPTIONAL MATCH (l)<-[:FOLLOWED]-(tr:Trade)
WITH l, count(tr) as applications,
     avg(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) as success_rate
RETURN l.rule, applications, success_rate
ORDER BY success_rate DESC
```

### 14.5 Conviction Calibration Queries

Track stated conviction vs actual outcomes:

```cypher
// Conviction accuracy by level
MATCH (tr:Trade)
WHERE tr.stated_conviction IS NOT NULL
WITH tr.stated_conviction as conviction,
     count(*) as trades,
     avg(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) as actual_win_rate,
     avg(tr.pnl_percent) as avg_return
RETURN conviction, trades,
       actual_win_rate,
       CASE conviction
         WHEN 5 THEN 0.8 WHEN 4 THEN 0.7 WHEN 3 THEN 0.6
         WHEN 2 THEN 0.5 WHEN 1 THEN 0.4
       END as expected_win_rate,
       actual_win_rate - CASE conviction
         WHEN 5 THEN 0.8 WHEN 4 THEN 0.7 WHEN 3 THEN 0.6
         WHEN 2 THEN 0.5 WHEN 1 THEN 0.4
       END as calibration_error
ORDER BY conviction

// Overconfidence detection (high conviction, low win rate)
MATCH (tr:Trade)
WHERE tr.stated_conviction >= 4 AND tr.outcome = 'loss'
WITH tr,
     [(b:Bias)-[:DETECTED_IN]->(tr) | b.name] as biases,
     [(s:Strategy)<-[:BASED_ON]-(tr) | s.name] as strategies
RETURN tr.id, tr.stated_conviction, tr.pnl_percent, biases, strategies
ORDER BY tr.pnl_percent ASC
LIMIT 10
```

### 14.6 Strategy Performance Analysis

```cypher
// Strategy effectiveness by market regime
MATCH (s:Strategy)<-[:BASED_ON]-(tr:Trade)-[:AFFECTED_BY]->(c:Catalyst)
WITH s.name as strategy, c.type as catalyst_type,
     count(tr) as trades,
     avg(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) as win_rate,
     avg(tr.pnl_percent) as avg_return
WHERE trades >= 3
RETURN strategy, catalyst_type, trades, win_rate, avg_return
ORDER BY strategy, win_rate DESC

// Strategy decay detection (performance over time)
MATCH (s:Strategy)<-[:BASED_ON]-(tr:Trade)
WITH s, tr.entry_date as trade_date, tr.pnl_percent as pnl
ORDER BY trade_date
WITH s.name as strategy,
     collect(trade_date) as dates,
     collect(pnl) as returns
WITH strategy, dates, returns,
     reduce(avg = 0.0, i IN range(0, size(returns)/2 - 1) |
       avg + returns[i]) / (size(returns)/2 + 0.001) as first_half_avg,
     reduce(avg = 0.0, i IN range(size(returns)/2, size(returns) - 1) |
       avg + returns[i]) / (size(returns)/2 + 0.001) as second_half_avg
RETURN strategy, first_half_avg, second_half_avg,
       second_half_avg - first_half_avg as performance_change
ORDER BY performance_change ASC

// Optimal strategy per sector
MATCH (s:Strategy)<-[:BASED_ON]-(tr:Trade)-[:TRADED]->(tk:Ticker),
      (c:Company)-[:ISSUED]->(tk),
      (c)-[:IN_SECTOR]->(sec:Sector)
WITH sec.name as sector, s.name as strategy,
     count(tr) as trades,
     avg(tr.pnl_percent) as avg_return,
     sum(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) * 1.0 / count(tr) as win_rate
WHERE trades >= 3
WITH sector, strategy, trades, avg_return, win_rate,
     avg_return * win_rate as score
ORDER BY sector, score DESC
WITH sector, collect({strategy: strategy, score: score, trades: trades})[0] as best
RETURN sector, best.strategy as best_strategy, best.score, best.trades
```

### 14.7 Pattern-to-Outcome Matching

```cypher
// Pattern predictive value
MATCH (p:Pattern)-[:OBSERVED_IN]->(tk:Ticker)<-[:TRADED]-(tr:Trade)
WHERE tr.entry_date > p.observed_date
  AND tr.entry_date < p.observed_date + duration('P3D')
WITH p.name as pattern,
     count(tr) as trades_after_pattern,
     avg(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) as follow_through_rate,
     avg(tr.pnl_percent) as avg_outcome
WHERE trades_after_pattern >= 3
RETURN pattern, trades_after_pattern, follow_through_rate, avg_outcome
ORDER BY follow_through_rate DESC

// Pattern + Strategy combination effectiveness
MATCH (p:Pattern)-[:OBSERVED_IN]->(tk:Ticker),
      (s:Strategy)<-[:BASED_ON]-(tr:Trade)-[:TRADED]->(tk)
WHERE tr.entry_date > p.observed_date
  AND tr.entry_date < p.observed_date + duration('P2D')
WITH p.name as pattern, s.name as strategy,
     count(tr) as combo_count,
     avg(tr.pnl_percent) as avg_return
WHERE combo_count >= 2
RETURN pattern, strategy, combo_count, avg_return
ORDER BY avg_return DESC
LIMIT 10
```

### 14.8 Exit Trigger Library

```cypher
// Most effective exit triggers by strategy
MATCH (tr:Trade)-[:BASED_ON]->(s:Strategy)
WHERE tr.exit_trigger IS NOT NULL
WITH s.name as strategy, tr.exit_trigger as exit_type,
     count(*) as uses,
     avg(tr.pnl_percent) as avg_pnl,
     avg(CASE WHEN tr.pnl_percent > 0 THEN tr.pnl_percent ELSE 0 END) as avg_win,
     avg(CASE WHEN tr.pnl_percent < 0 THEN tr.pnl_percent ELSE 0 END) as avg_loss
RETURN strategy, exit_type, uses, avg_pnl, avg_win, avg_loss
ORDER BY strategy, avg_pnl DESC

// Exit trigger effectiveness by holding period
MATCH (tr:Trade)
WHERE tr.exit_trigger IS NOT NULL AND tr.hold_duration_days IS NOT NULL
WITH tr.exit_trigger as trigger,
     CASE
       WHEN tr.hold_duration_days < 1 THEN 'intraday'
       WHEN tr.hold_duration_days < 5 THEN 'swing'
       ELSE 'position'
     END as hold_type,
     count(*) as count,
     avg(tr.pnl_percent) as avg_return
RETURN trigger, hold_type, count, avg_return
ORDER BY trigger, avg_return DESC
```

### 14.9 Portfolio Risk Correlation

```cypher
// Find correlated positions via shared entities
MATCH (tr1:Trade {status: 'open'})-[:TRADED]->(t1:Ticker),
      (tr2:Trade {status: 'open'})-[:TRADED]->(t2:Ticker),
      (t1)-[r]-(shared)-[r2]-(t2)
WHERE t1 <> t2
WITH t1.symbol as ticker1, t2.symbol as ticker2,
     collect(DISTINCT type(r) + ':' + labels(shared)[0]) as shared_factors,
     count(DISTINCT shared) as overlap_count
WHERE overlap_count >= 2
RETURN ticker1, ticker2, shared_factors, overlap_count
ORDER BY overlap_count DESC

// Sector concentration risk
MATCH (tr:Trade {status: 'open'})-[:TRADED]->(tk:Ticker),
      (c:Company)-[:ISSUED]->(tk),
      (c)-[:IN_SECTOR]->(s:Sector)
WITH s.name as sector, collect(tk.symbol) as tickers, count(*) as position_count
RETURN sector, tickers, position_count,
       position_count * 1.0 / sum(position_count) OVER () as concentration
ORDER BY concentration DESC

// Risk factor exposure across portfolio
MATCH (tr:Trade {status: 'open'})-[:TRADED]->(tk:Ticker),
      (r:Risk)-[:THREATENS]->(tk)
WITH r.name as risk, collect(DISTINCT tk.symbol) as exposed_tickers
RETURN risk, exposed_tickers, size(exposed_tickers) as exposure_count
ORDER BY exposure_count DESC
```

### 14.10 Learning Loop Integration

```cypher
// Learning rule compliance and impact
MATCH (l:Learning)
OPTIONAL MATCH (l)<-[:FOLLOWED]-(tr_followed:Trade)
OPTIONAL MATCH (l)<-[:VIOLATED]-(tr_violated:Trade)
WITH l,
     count(DISTINCT tr_followed) as followed_count,
     count(DISTINCT tr_violated) as violated_count,
     avg(tr_followed.pnl_percent) as followed_avg_pnl,
     avg(tr_violated.pnl_percent) as violated_avg_pnl
RETURN l.rule, l.category,
       followed_count, followed_avg_pnl,
       violated_count, violated_avg_pnl,
       followed_avg_pnl - violated_avg_pnl as rule_value
ORDER BY rule_value DESC

// Bias → Learning → Improvement path tracking
MATCH path = (b:Bias)-[:ADDRESSES]-(l:Learning)-[:UPDATES]-(s:Strategy)
OPTIONAL MATCH (b)-[:DETECTED_IN]->(tr:Trade)
WITH b, l, s,
     count(tr) as bias_occurrences,
     avg(tr.pnl_percent) as bias_impact
RETURN b.name as bias, l.rule as learning, s.name as strategy_updated,
       bias_occurrences, bias_impact
ORDER BY bias_occurrences DESC

// Knowledge graph feedback loop effectiveness
MATCH (l:Learning)-[:DERIVED_FROM]->(tr:Trade)
WITH l, tr.entry_date as derived_date
MATCH (l)<-[:FOLLOWED]-(subsequent:Trade)
WHERE subsequent.entry_date > derived_date
WITH l, count(subsequent) as times_applied,
     avg(CASE WHEN subsequent.outcome = 'win' THEN 1 ELSE 0 END) as success_rate
RETURN l.id, l.rule, times_applied, success_rate
ORDER BY success_rate DESC
```

---

## 15. Advanced Graph Analytics

### 15.1 Graph Algorithms (via APOC/GDS)

Enable advanced analytics with Neo4j Graph Data Science library:

```cypher
// Centrality: Most influential entities in trading knowledge
CALL gds.pageRank.stream('trading-graph', {
  maxIterations: 20,
  dampingFactor: 0.85
})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
RETURN labels(node)[0] as type, node.name as entity, score
ORDER BY score DESC
LIMIT 20

// Community detection: Clusters of related trading concepts
CALL gds.louvain.stream('trading-graph')
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) AS node, communityId
RETURN communityId,
       collect(node.name)[0..10] as sample_members,
       count(*) as size
ORDER BY size DESC

// Shortest path: Connection between two concepts
MATCH (start:Ticker {symbol: 'NVDA'}), (end:Risk {name: 'concentration-risk'})
CALL gds.shortestPath.dijkstra.stream('trading-graph', {
  sourceNode: start,
  targetNode: end
})
YIELD path
RETURN [node IN nodes(path) | node.name] as connection_path
```

### 15.2 Temporal Analysis

Time-windowed queries for trend detection:

```cypher
// Entity emergence over time (new concepts appearing)
MATCH (n)
WHERE n.created_at IS NOT NULL
WITH date(n.created_at) as creation_date,
     labels(n)[0] as entity_type,
     count(*) as daily_count
ORDER BY creation_date
RETURN creation_date, entity_type, daily_count

// Relationship trends (changing market dynamics)
MATCH (c1:Company)-[r:COMPETES_WITH]->(c2:Company)
WHERE r.created_at IS NOT NULL
WITH date(r.created_at) as relation_date,
     count(*) as new_competitions
RETURN relation_date, new_competitions
ORDER BY relation_date

// Rolling performance windows
MATCH (s:Strategy)<-[:BASED_ON]-(tr:Trade)
WHERE tr.entry_date > date() - duration('P90D')
WITH s.name as strategy,
     date.truncate('week', tr.entry_date) as week,
     avg(tr.pnl_percent) as weekly_return,
     count(*) as trades
RETURN strategy, week, weekly_return, trades
ORDER BY strategy, week
```

### 15.3 Graph-RAG Hybrid Queries

Combine graph structure with semantic similarity for enhanced context:

```cypher
// Graph-guided context expansion
// Step 1: Get structurally related entities
MATCH (t:Ticker {symbol: $symbol})-[r*1..2]-(related)
WITH collect(DISTINCT related) as graph_context

// Step 2: Use entity names for vector similarity search (in application layer)
// Python pseudocode:
// vector_results = rag.search(query, filter_entities=graph_context)
// combined_context = merge(graph_context, vector_results)

// Provenance-aware context building
MATCH (a:Analysis)-[:ANALYZES]->(t:Ticker {symbol: $symbol}),
      (d:Document)<-[:EXTRACTED_FROM]-(e)-[*1]-(a)
RETURN a.id, d.file_path, collect(DISTINCT e.name) as entities
ORDER BY a.created_at DESC
LIMIT 5
```

### 15.4 Graph Visualization Exports

```cypher
// Export subgraph for visualization (Mermaid format)
MATCH path = (t:Ticker {symbol: $symbol})-[r*1..2]-(connected)
WITH relationships(path) as rels, nodes(path) as nodes
UNWIND rels as rel
WITH DISTINCT startNode(rel) as from_node, rel, endNode(rel) as to_node
RETURN
  labels(from_node)[0] + '_' + coalesce(from_node.symbol, from_node.name, from_node.id) as from_id,
  type(rel) as relationship,
  labels(to_node)[0] + '_' + coalesce(to_node.symbol, to_node.name, to_node.id) as to_id

// Output can be transformed to:
// graph LR
//   Ticker_NVDA -->|ISSUED| Company_NVIDIA
//   Company_NVIDIA -->|IN_SECTOR| Sector_Technology
```

---

## 16. Trading Intelligence CLI Commands

Additional CLI commands for trading intelligence features:

```bash
# Outcome analysis
python orchestrator.py graph outcomes TICKER       # P&L by entity for ticker
python orchestrator.py graph outcomes --strategy   # Strategy performance summary
python orchestrator.py graph outcomes --period 90d # Last 90 days

# Bias analysis
python orchestrator.py graph biases --impact       # Biases ranked by P&L impact
python orchestrator.py graph biases --chains       # Bias trigger chains
python orchestrator.py graph biases --counter BIAS # Countermeasures for bias

# Conviction calibration
python orchestrator.py graph calibration           # Conviction accuracy report
python orchestrator.py graph calibration --detail  # Per-level breakdown

# Strategy analysis
python orchestrator.py graph strategy-decay        # Detect decaying strategies
python orchestrator.py graph strategy-fit TICKER   # Best strategy for ticker
python orchestrator.py graph strategy-fit --sector # Best strategy per sector

# Pattern analysis
python orchestrator.py graph patterns --predictive # Pattern predictive value
python orchestrator.py graph patterns --combos     # Best pattern+strategy combos

# Exit analysis
python orchestrator.py graph exits                 # Exit trigger effectiveness
python orchestrator.py graph exits --by-strategy   # Exit triggers by strategy

# Portfolio risk
python orchestrator.py graph risk-correlation      # Cross-position correlations
python orchestrator.py graph risk-concentration    # Sector/factor concentration
python orchestrator.py graph risk-exposure         # Risk factor exposure

# Learning effectiveness
python orchestrator.py graph learning-impact       # Learning rule value
python orchestrator.py graph learning-compliance   # Rule follow/violate rates

# Graph analytics
python orchestrator.py graph centrality            # Most connected entities
python orchestrator.py graph communities           # Entity clusters
python orchestrator.py graph path FROM TO          # Shortest path between entities
```

---

## 17. Trading Intelligence Integration

### 17.1 Real-Time Decision Support

When Claude skills execute, inject graph intelligence into analysis:

```python
# In skill execution flow
def enrich_analysis_context(ticker: str) -> dict:
    """Query graph for decision-relevant intelligence."""
    with TradingGraph() as g:
        return {
            # Historical performance
            "strategy_rankings": g.get_strategy_rankings(ticker),
            "pattern_signals": g.get_recent_patterns(ticker, days=7),

            # Bias warnings
            "active_biases": g.get_user_bias_tendency(),
            "bias_impact_history": g.get_bias_impact(ticker),

            # Calibration feedback
            "conviction_accuracy": g.get_conviction_calibration(),

            # Risk context
            "correlated_positions": g.get_position_correlations(ticker),
            "risk_exposure": g.get_risk_factors(ticker),

            # Learning reminders
            "relevant_learnings": g.get_applicable_learnings(ticker)
        }
```

### 17.2 Graph-RAG Hybrid Context Builder

Combine graph structure with vector similarity for optimal context:

```python
# trader/graph/hybrid_context.py

class HybridContextBuilder:
    """Combine graph traversal with RAG similarity for analysis context."""

    def build_context(self, ticker: str, query: str) -> dict:
        # 1. Graph traversal for structural relationships
        graph_context = self._traverse_graph(ticker, depth=2)

        # 2. Filter graph entities by relevance to query
        relevant_entities = self._filter_by_relevance(graph_context, query)

        # 3. Vector search within graph-connected documents
        doc_ids = [e.source_doc for e in relevant_entities]
        vector_results = self.rag.search(query, doc_filter=doc_ids)

        # 4. Outcome-weight the results
        weighted_results = self._apply_outcome_weights(vector_results)

        # 5. Inject bias warnings and learnings
        context = self._add_intelligence_layer(weighted_results, ticker)

        return context
```

### 17.3 Post-Trade Feedback Loop

Automatically update graph intelligence after trade completion:

```python
# trader/graph/feedback.py

def process_trade_outcome(trade_id: str):
    """Update graph intelligence based on trade outcome."""
    with TradingGraph() as g:
        trade = g.get_trade(trade_id)

        # 1. Update strategy performance stats
        g.update_strategy_stats(trade.strategy, trade.outcome, trade.pnl)

        # 2. Record bias impact
        for bias in trade.detected_biases:
            g.record_bias_impact(bias, trade.pnl)

        # 3. Update pattern reliability
        for pattern in trade.observed_patterns:
            g.update_pattern_stats(pattern, trade.outcome)

        # 4. Track conviction calibration
        g.record_conviction_outcome(trade.stated_conviction, trade.outcome)

        # 5. Update exit trigger effectiveness
        g.update_exit_stats(trade.exit_trigger, trade.strategy, trade.pnl)

        # 6. Check for new bias chains
        g.detect_bias_chains(trade)

        # 7. Generate learning suggestions
        learnings = g.suggest_learnings(trade)
        return learnings
```

### 17.4 RAG Integration Points

Graph complements RAG system (see TRADING_RAG_ARCHITECTURE.md):

| Component | Graph Role | RAG Role |
|-----------|------------|----------|
| **Entity retrieval** | Structural relationships | Semantic similarity |
| **Context ranking** | Outcome weighting | Relevance scoring |
| **Bias detection** | Historical patterns | Current text analysis |
| **Learning lookup** | Rule effectiveness stats | Rule content retrieval |
| **Risk assessment** | Portfolio correlations | Risk description text |

---

## 18. Implementation Phases (Updated)

### Phase 5 — Trading Intelligence Layer

| Deliverable | Description |
|-------------|-------------|
| `graph/intelligence.py` | Trading intelligence query methods |
| `graph/outcomes.py` | Outcome-weighted traversal algorithms |
| `graph/calibration.py` | Conviction calibration tracking |
| Enhanced node properties | Add trading intelligence fields to existing nodes |
| New relationships | Add intelligence-specific relationship types |
| CLI commands | `outcomes`, `biases`, `calibration`, `strategy-*` commands |

### Phase 6 — Advanced Analytics

| Deliverable | Description |
|-------------|-------------|
| GDS integration | Neo4j Graph Data Science library setup |
| `graph/analytics.py` | Centrality, community detection, pathfinding |
| Temporal queries | Time-windowed analysis patterns |
| Visualization export | Mermaid/GraphViz export for graph visualization |

### Phase 7 — Graph-RAG Hybrid

| Deliverable | Description |
|-------------|-------------|
| `graph/hybrid_context.py` | Combined graph+RAG context builder |
| `graph/feedback.py` | Post-trade feedback loop processor |
| Skill integration | Auto-inject graph intelligence into skill context |
| Real-time enrichment | Decision support during skill execution |
