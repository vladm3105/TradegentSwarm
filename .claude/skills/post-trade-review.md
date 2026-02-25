---
title: Post-Trade Review
tags:
  - trading-skill
  - learning
  - review
  - ai-agent-primary
custom_fields:
  skill_category: learning
  priority: primary
  development_status: active
  upstream_artifacts:
    - trade-journal
  downstream_artifacts:
    - ticker-profile
    - learnings
  triggers:
    - "post-trade review"
    - "review trade"
    - "what did I learn"
    - "trade analysis"
    - "closed trade"
  auto_invoke: true
---

# Post-Trade Review Skill

Use this skill to analyze completed trades and extract lessons. Closes the learning loop. Auto-invokes after trade-journal records an exit.

## When to Use

- After every closed trade (win or loss)
- Within 24-48 hours of exit (while memory fresh)
- Automatically triggered by trade-journal exit
- User asks "what did I learn from TICKER trade?"

## Workflow

### Step 1: Find Closed Trade (RAG v2.0 + Graph)

```yaml
# Find the trade journal entry (v2.0: reranked for higher relevance)
Tool: rag_search_rerank
Input: {"query": "$TICKER trade entry exit", "ticker": "$TICKER", "top_k": 10}

# Find similar past trades for comparison and learning
Tool: rag_similar
Input: {"ticker": "$TICKER", "analysis_type": "trade-journal", "top_k": 3}

# Get original analysis that triggered trade
Tool: rag_search_rerank
Input: {"query": "$TICKER analysis recommendation", "ticker": "$TICKER", "top_k": 5}

# Get ticker context
Tool: graph_context
Input: {"ticker": "$TICKER"}

# Check historical biases
Tool: graph_biases
Input: {}
```

### Step 2: Get Post-Trade Market Data (IB MCP)

```yaml
# What happened after exit?
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "$TICKER"}

# Price action during trade period
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "$TICKER", "duration": "1 M", "bar_size": "1 day"}
```

### Step 3: Read Skill Definition

Load `tradegent_knowledge/skills/post-trade-review/SKILL.md` and execute the review framework:

1. **Step 1: Document Facts** (trade details, original thesis)
2. **Step 2: Execution Analysis**
   - Entry timing (early/on-time/late)
   - Exit timing and reason
   - Slippage analysis
   - Entry/Exit grades (A-F)
3. **Step 3: Thesis Accuracy**
   - Direction: correct?
   - Magnitude: within 50%?
   - Timing: correct?
   - Catalyst: played out?
4. **Step 4: What Worked / What Didn't**
5. **Step 5: Bias Check Retrospective** (score each 1-5)
   - Recency, Confirmation, Overconfidence, Loss Aversion, Anchoring
6. **Step 6: Grade the Trade** (overall A-F)
7. **Step 7: Extract Lessons** (actionable improvements)

### Step 4: Grading Components

```
Analysis Quality:      A / B / C / D / F
Entry Execution:       A / B / C / D / F
Exit Execution:        A / B / C / D / F
Risk Management:       A / B / C / D / F
Emotional Discipline:  A / B / C / D / F
─────────────────────────────────────────
OVERALL GRADE:         A / B / C / D / F
```

### Step 5: Lesson Extraction

For each significant lesson:
```
PRIMARY LESSON:
- Lesson: [specific insight]
- Action: [what to do differently]
- Applies to: All trades / Earnings / Technical / This ticker

PATTERN TO ADD:
- Pattern: [what you observed]
- Expected outcome: [probability/direction]
→ Save to learnings/patterns/

RULE TO ADD:
- Rule: [specific rule]
- Reason: [why this rule]
→ Save to learnings/rules/
```

### Step 6: Generate Output

Use `tradegent_knowledge/skills/post-trade-review/template.yaml` structure.

### Step 7: Save Review

Save to `tradegent_knowledge/knowledge/reviews/{TICKER}_{YYYYMMDDTHHMM}_review.yaml`

Optionally save learnings:
- `tradegent_knowledge/knowledge/learnings/patterns/{pattern_file}.yaml`
- `tradegent_knowledge/knowledge/learnings/rules/{rule_file}.yaml`

### Step 8: Index in Knowledge Base (Post-Save Hooks)

```yaml
# Extract entities to Graph (captures learnings, biases, patterns)
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/reviews/{TICKER}_{YYYYMMDDTHHMM}_review.yaml"}

# Embed for semantic search
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/reviews/{TICKER}_{YYYYMMDDTHHMM}_review.yaml"}

# If patterns extracted
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/learnings/patterns/{pattern_file}.yaml"}

Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/learnings/patterns/{pattern_file}.yaml"}
```

### Step 9: Push to Remote (Private Knowledge Repo)

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge    # Private knowledge repository
  branch: main
  files:
    - path: knowledge/reviews/{TICKER}_{YYYYMMDDTHHMM}_review.yaml
      content: [generated review content]
    - path: knowledge/learnings/patterns/{pattern_file}.yaml
      content: [pattern content if applicable]
    - path: knowledge/learnings/rules/{rule_file}.yaml
      content: [rule content if applicable]
  message: "Add post-trade review for {TICKER}"
```

## Chaining

- Automatically triggered by **trade-journal** exit
- Updates **ticker-profile** with trade history and lessons
- Adds patterns/rules to `tradegent_knowledge/knowledge/learnings/`
- Informs future **earnings-analysis** and **stock-analysis**

## Workflow Automation (Auto-Triggering)

Post-trade reviews are automatically queued when trades are closed via CLI:

```
trade close NVDA → nexus.trades updated → task_queue entry → process-queue
                                                                    │
                                                                    ▼
                                                         post-trade-review runs
```

**Database Tracking:**
| Table | Field | Purpose |
|-------|-------|---------|
| `nexus.trades` | `review_status` | pending → completed |
| `nexus.trades` | `review_path` | Path to review file |
| `nexus.task_queue` | `task_type` | `post_trade_review` |

**CLI Commands:**
```bash
# Process all queued reviews
python orchestrator.py process-queue

# Process only pending trade reviews
python orchestrator.py trade pending-reviews

# Check queue status
python orchestrator.py queue-status
```

**When Review Completes:**
1. `nexus.trades.review_status` → `completed`
2. `nexus.trades.review_path` → path to review file
3. Review indexed to RAG + Graph

## Arguments

- `$ARGUMENTS`: Ticker symbol of closed trade

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_search_rerank` | Find trade journal/analysis (v2.0: cross-encoder) |
| `rag_similar` | Find similar past trades for comparison |
| `graph_context` | Ticker relationships |
| `graph_biases` | Historical bias patterns |
| `mcp__ib-mcp__get_stock_price` | Current price (post-exit) |
| `mcp__ib-mcp__get_historical_data` | Price action during trade |
| `graph_extract` | Index learnings |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to private knowledge repo |

## Execution

Review the closed trade for $ARGUMENTS. Be honest in grading—learning requires truth. Follow all steps: find trade, analyze execution, grade, extract lessons, save, index, and push to remote.
