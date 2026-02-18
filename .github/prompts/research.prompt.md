---
mode: agent
description: Conduct macro, sector, or thematic research using the structured research framework
---

# Research Analysis

Research **${input:topic}** using the structured research framework to inform trading decisions.

## Context

Load the full skill definition and output template:
- #file:../../trading/skills/research-analysis/SKILL.md
- #file:../../trading/skills/research-analysis/template.yaml

## When to Use

- Developing investment themes (AI infrastructure, clean energy, etc.)
- Analyzing sector dynamics and rotation
- Studying macro environment impact
- Building research-backed conviction for trades

## Workflow

1. **Read skill definition** from `trading/skills/research-analysis/SKILL.md`
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

## Output

Save the completed research to `trading/knowledge/analysis/research/` using the naming convention `{TOPIC}_{YYYYMMDDTHHMM}.yaml`.
