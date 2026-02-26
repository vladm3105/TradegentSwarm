---
title: Research Analysis
tags:
  - trading-skill
  - research
  - macro
  - thematic
  - ai-agent-primary
custom_fields:
  skill_category: research
  priority: primary
  development_status: active
  upstream_artifacts: []
  downstream_artifacts:
    - earnings-analysis
    - stock-analysis
    - watchlist
  triggers:
    - "research"
    - "macro analysis"
    - "sector analysis"
    - "thematic research"
    - "investment theme"
  auto_invoke: true
---

# Research Analysis Skill

Use this skill for macro, sector, and thematic research that informs trading decisions. Auto-invokes when user asks about investment themes, sector dynamics, or macro environment.

## When to Use

- Developing investment themes (AI infrastructure, clean energy, etc.)
- Analyzing sector dynamics and rotation
- Studying macro environment impact
- Building research-backed conviction for trades

## Workflow

### Step 1: Get Existing Research Context (RAG v2.0 + Graph)

```yaml
# Search with query expansion for broader recall (v2.0: generates variations)
Tool: rag_search_expanded
Input: {"query": "$TOPIC macro sector thematic", "top_k": 10, "n_expansions": 3}

# Alternative: Reranked search for specific topics (higher precision)
Tool: rag_search_rerank
Input: {"query": "$TOPIC investment thesis", "top_k": 5}

# Get related entities from graph
Tool: graph_query
Input: {"cypher": "MATCH (n) WHERE n.name CONTAINS $topic OR n.sector CONTAINS $topic RETURN n LIMIT 20", "params": {"topic": "$TOPIC"}}

# Discover broader relationships via graph search
Tool: graph_search
Input: {"ticker": "$RELATED_TICKER", "depth": 2}
```

### Step 2: Gather Primary Sources

Use web search and protected article fetching:

```yaml
# Search for recent research
Tool: mcp__brave-search__brave_web_search
Input: {"query": "$TOPIC investment thesis 2024 2025"}

# Fed statements, government data
Tool: mcp__brave-search__brave_web_search
Input: {"query": "$TOPIC federal reserve economic data"}

# Analyst research
Tool: fetch_protected_article
Input: {"url": "...", "wait_for_selector": "article"}
```

### Step 3: Get Market Data for Validation

```yaml
# Sector ETF performance
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "$SECTOR_ETF", "duration": "1 Y", "bar_size": "1 day"}

# Related stock performance
Tool: mcp__ib-mcp__get_quotes_batch
Input: {"symbols": ["TICKER1", "TICKER2", "TICKER3"]}
```

### Step 4: Read Skill Definition

Load `tradegent_knowledge/skills/research-analysis/SKILL.md` and execute the research framework:

1. **Step 1: Define the Research Question** (specific and answerable)
2. **Step 2: Gather Evidence**
   - Primary sources: earnings calls, SEC filings, Fed statements, government data
   - Secondary sources: analyst research, news, expert commentary
3. **Step 3: Develop Thesis**
   - Clear thesis statement
   - Supporting arguments with evidence
   - Counter-arguments addressed
4. **Step 4: Define Implications**
   - Beneficiaries (long candidates)
   - Losers (short/avoid candidates)
   - Sector positioning
5. **Step 5: Set Forecast Validity**
   - `forecast_valid_until`: YYYY-MM-DD when research expires
   - `forecast_horizon_days`: 30=tactical, 90=strategic, 365=secular
   - Review triggers and falsification criteria
   - After expiry, research is historical only (learning/review)

### Step 5: Generate Output

Use `tradegent_knowledge/skills/research-analysis/template.yaml` structure.

### Step 6: Save Research

Save to `tradegent_knowledge/knowledge/analysis/research/{TOPIC}_{YYYYMMDDTHHMM}.yaml`

### Step 7: Index in Knowledge Base (Post-Save Hooks)

```yaml
# Extract entities to Graph
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/research/{TOPIC}_{YYYYMMDDTHHMM}.yaml"}

# Embed for semantic search
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/research/{TOPIC}_{YYYYMMDDTHHMM}.yaml"}
```

### Step 8: Push to Remote (Private Knowledge Repo)

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge    # Private knowledge repository
  branch: main
  files:
    - path: knowledge/analysis/research/{TOPIC}_{YYYYMMDDTHHMM}.yaml
      content: [generated research content]
  message: "Add research: {TOPIC}"
```

## Chaining

After completion:
- Beneficiary tickers → queue for **stock-analysis** or **earnings-analysis**
- High-conviction themes → add tickers to **watchlist**
- Update related **ticker-profiles** with thematic context

## Arguments

- `$ARGUMENTS`: Research topic (e.g., "AI_CapEx_Cycle", "Rate_Cut_Impact", "Semiconductor_Cycle")

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_search_expanded` | Broader research recall (v2.0: query expansion) |
| `rag_search_rerank` | Precise topic search (v2.0: cross-encoder) |
| `graph_query` | Find related entities |
| `graph_search` | Discover broader relationships |
| `mcp__brave-search__brave_web_search` | Web research |
| `fetch_protected_article` | Paywalled content |
| `mcp__ib-mcp__get_historical_data` | Sector performance |
| `mcp__ib-mcp__get_quotes_batch` | Multiple stock prices |
| `graph_extract` | Index entities |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to private knowledge repo |

## Execution

Research $ARGUMENTS using the structured research framework. Follow all steps: get context, gather evidence, develop thesis, save, index, and push to remote.
