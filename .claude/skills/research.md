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

1. **Read skill definition**: Load `trading/skills/research-analysis/SKILL.md`
2. **Execute research framework**:
   - Step 1: Define the Research Question (specific and answerable)
   - Step 2: Gather Evidence
     - Primary sources: earnings calls, SEC filings, Fed statements, government data
     - Secondary sources: analyst research, news, expert commentary
   - Step 3: Develop Thesis
     - Clear thesis statement
     - Supporting arguments with evidence
     - Counter-arguments addressed
   - Step 4: Define Implications
     - Beneficiaries (long candidates)
     - Losers (short/avoid candidates)
     - Sector positioning
   - Step 5: Set Review Schedule
     - Validity period (30/90/365 days)
     - Review triggers
     - Falsification criteria
3. **Generate output** using `trading/skills/research-analysis/template.yaml`
4. **Save** to `trading/knowledge/analysis/research/{TOPIC}_{YYYYMMDDTHHMM}.yaml`

## Chaining

After completion:
- Beneficiary tickers → queue for **stock-analysis** or **earnings-analysis**
- High-conviction themes → add tickers to **watchlist**
- Update related **ticker-profiles** with thematic context

## Arguments

- `$ARGUMENTS`: Research topic (e.g., "AI_CapEx_Cycle", "Rate_Cut_Impact", "Semiconductor_Cycle")

## Auto-Commit to Remote

After saving the research file, use the GitHub MCP server to push directly:

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: trading_light_pilot
  branch: main
  files:
    - path: trading/knowledge/analysis/research/{TOPIC}_{YYYYMMDDTHHMM}.yaml
      content: [generated research content]
  message: "Add research: {TOPIC}"
```

## Execution

Research $ARGUMENTS using the structured research framework. Read the full skill definition from `trading/skills/research-analysis/SKILL.md`. After saving the output file, auto-commit and push to remote.
