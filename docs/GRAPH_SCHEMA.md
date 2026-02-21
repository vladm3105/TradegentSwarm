# Graph Database Schema Reference

> **Last Updated**: 2026-02-21
> **Neo4j Version**: 5.x Community Edition
> **Skills Version**: v2.5

TradegentSwarm uses Neo4j for the knowledge graph, storing entities and relationships extracted from trading analyses.

## Schema Overview

```
Neo4j Graph
├── NODES (16 types)
│   ├── Market Entities: Ticker, Company, Sector, Industry, Product
│   ├── Trading Concepts: Strategy, Structure, Pattern, Bias, Signal, Risk
│   ├── Events: EarningsEvent, Catalyst, Conference, MacroEvent
│   ├── People: Executive, Analyst
│   ├── Analysis: Analysis, Trade, Learning
│   ├── Provenance: Document
│   └── Time: Timeframe
│
└── RELATIONSHIPS (~20 types)
    ├── Structural: ISSUED, IN_SECTOR, IN_INDUSTRY, MAKES, LEADS
    ├── Competitive: COMPETES_WITH, SUPPLIES_TO, CUSTOMER_OF, CORRELATED_WITH
    ├── Trading: WORKS_FOR, USES, DETECTED_IN, OBSERVED_IN, INDICATES
    ├── Events: HAS_EARNINGS, AFFECTED_BY, EXPOSED_TO, THREATENS
    ├── Analysis: ANALYZES, MENTIONS, BASED_ON, TRADED, COVERS
    └── Learning: DERIVED_FROM, ADDRESSES, UPDATES, MITIGATED_BY
```

---

## Node Types (Labels)

### Market Entities

#### Ticker
Stock symbols traded on exchanges.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `symbol` | string | YES | Stock symbol (unique key) |
| `name` | string | NO | Company name |
| `created_at` | datetime | YES | Node creation time |

**Constraints:**
```cypher
CREATE CONSTRAINT ticker_symbol IF NOT EXISTS
  FOR (t:Ticker) REQUIRE t.symbol IS UNIQUE;
```

#### Company
Corporate entities.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Company name (unique key) |
| `cik` | string | NO | SEC CIK number |
| `created_at` | datetime | YES | Node creation time |

#### Sector
Market sectors (Technology, Healthcare, etc.).

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Sector name (unique) |

#### Industry
Specific industries (Semiconductors, Cloud Computing, etc.).

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Industry name (unique) |

#### Product
Products or services.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Product name (unique) |
| `maker` | string | NO | Company that makes it |

---

### Trading Concepts

#### Strategy
Trading strategies with performance tracking.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Strategy name (unique) |
| `category` | string | NO | Strategy category |
| `win_rate` | float | NO | Historical win rate |
| `sample_size` | int | NO | Number of trades |
| `avg_pnl_percent` | float | NO | Average return per trade |
| `profit_factor` | float | NO | Gross profit / gross loss |
| `last_used` | datetime | NO | Last trade using this |
| `created_at` | datetime | YES | Node creation time |
| `updated_at` | datetime | NO | Last modification |

#### Pattern
Market patterns (technical or behavioral).

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Pattern name (unique) |
| `description` | string | NO | Pattern description |
| `win_rate` | float | NO | Historical accuracy |
| `sample_size` | int | NO | Occurrences |
| `reliability_score` | float | NO | Consistency (0.0-1.0) |
| `last_observed` | datetime | NO | Last seen |

#### Bias
Cognitive biases detected in trading.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Bias name (unique) |
| `description` | string | NO | Bias description |
| `total_occurrences` | int | NO | Times detected |
| `avg_pnl_impact` | float | NO | Average P&L when present |
| `effective_countermeasures` | list | NO | What works against it |
| `trigger_conditions` | list | NO | What activates it |

#### Signal
Trading signals.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Signal name (unique) |
| `source` | string | NO | Signal source |

#### Risk
Identified risks.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Risk name (unique) |
| `category` | string | NO | structural, cyclical, execution |
| `severity` | string | NO | H/M/L |

#### Structure
Trade structures.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Structure name (unique) |
| `type` | string | NO | shares, call-spread, etc. |

---

### Events

#### EarningsEvent
Quarterly/annual earnings reports.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `quarter` | string | YES | Q4-FY2025 |
| `date` | date | NO | Earnings date |

**Indexes:**
```cypher
CREATE INDEX earnings_date_idx IF NOT EXISTS FOR (e:EarningsEvent) ON (e.date);
```

#### Catalyst
Price-moving events.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `type` | string | YES | earnings, news, macro, etc. |
| `description` | string | NO | Event description |
| `date` | date | NO | Event date |
| `created_at` | datetime | YES | Node creation time |

**Indexes:**
```cypher
CREATE INDEX catalyst_type_idx IF NOT EXISTS FOR (c:Catalyst) ON (c.type);
CREATE INDEX catalyst_date_idx IF NOT EXISTS FOR (c:Catalyst) ON (c.date);
```

#### MacroEvent
Macro-economic events.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Event name |
| `type` | string | NO | Fed decision, CPI, etc. |
| `date` | date | NO | Event date |

---

### People

#### Executive
Company executives.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Full name |
| `title` | string | NO | CEO, CFO, etc. |

#### Analyst
Wall Street analysts.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | Full name |
| `firm` | string | NO | Employer firm |

---

### Analysis & Tracking

#### Analysis
Analysis documents.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | YES | Analysis ID (unique) |
| `type` | string | NO | stock-analysis, earnings-analysis |
| `created_at` | datetime | YES | Analysis date |
| `updated_at` | datetime | NO | Last update |
| `extraction_version` | string | NO | Prompt version used |

**Indexes:**
```cypher
CREATE INDEX analysis_type_idx IF NOT EXISTS FOR (a:Analysis) ON (a.type);
CREATE INDEX analysis_created_idx IF NOT EXISTS FOR (a:Analysis) ON (a.created_at);
```

#### Trade
Executed trades with outcomes.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | YES | Trade ID (unique) |
| `direction` | string | NO | long, short |
| `outcome` | string | NO | win, loss, breakeven |
| `entry_date` | datetime | NO | Position entry |
| `exit_date` | datetime | NO | Position exit |
| `pnl_dollars` | float | NO | Realized P&L |
| `pnl_percent` | float | NO | Percentage return |
| `stated_conviction` | int | NO | 1-5 at entry |
| `hold_duration_days` | int | NO | Days in position |
| `exit_trigger` | string | NO | stop, target, time, catalyst |
| `status` | string | NO | open, closed |
| `created_at` | datetime | YES | Node creation time |

**Indexes:**
```cypher
CREATE INDEX trade_outcome_idx IF NOT EXISTS FOR (t:Trade) ON (t.outcome);
CREATE INDEX trade_created_idx IF NOT EXISTS FOR (t:Trade) ON (t.created_at);
CREATE INDEX trade_pnl_idx IF NOT EXISTS FOR (t:Trade) ON (t.pnl_percent);
CREATE INDEX trade_status_idx IF NOT EXISTS FOR (t:Trade) ON (t.status);
```

#### Learning
Trading rules and lessons.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | YES | Learning ID (unique) |
| `rule` | string | NO | The rule/lesson |
| `category` | string | NO | bias, pattern, exit, etc. |
| `compliance_rate` | float | NO | How often followed |
| `effectiveness_score` | float | NO | Impact when followed |
| `violation_count` | int | NO | Times ignored |
| `created_at` | datetime | YES | Node creation time |

**Indexes:**
```cypher
CREATE INDEX learning_category_idx IF NOT EXISTS FOR (l:Learning) ON (l.category);
CREATE INDEX learning_effectiveness_idx IF NOT EXISTS FOR (l:Learning) ON (l.effectiveness_score);
```

---

### Provenance

#### Document
Source documents for entity tracing.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | YES | Document ID (unique) |
| `type` | string | NO | Document type |
| `file_path` | string | NO | File location |
| `created_at` | datetime | YES | Document date |

---

### Time

#### Timeframe
Trading timeframes.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | YES | intraday, swing, position |
| `duration` | string | NO | Duration description |

---

## Relationship Types

### Structural Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| `ISSUED` | Company | Ticker | Company issued stock |
| `IN_SECTOR` | Company | Sector | Company belongs to sector |
| `IN_INDUSTRY` | Company | Industry | Company in industry |
| `MAKES` | Company | Product | Company makes product |
| `LEADS` | Executive | Company | Executive leads company |

### Competitive Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| `COMPETES_WITH` | Company | Company | Direct competitors |
| `SUPPLIES_TO` | Company | Company | Supply chain |
| `CUSTOMER_OF` | Company | Company | Customer relationship |
| `CORRELATED_WITH` | Ticker | Ticker | Price correlation |

**Properties on CORRELATED_WITH:**
```cypher
[:CORRELATED_WITH {coefficient: float, period: string, calculated_at: datetime}]
```

### Trading Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| `WORKS_FOR` | Strategy | Ticker | Strategy effective for ticker |
| `USES` | Strategy | Structure | Strategy uses trade structure |
| `DETECTED_IN` | Bias | Trade | Bias detected in trade |
| `OBSERVED_IN` | Pattern | Ticker | Pattern seen in ticker |
| `INDICATES` | Signal | Ticker | Signal on ticker |

**Properties on DETECTED_IN:**
```cypher
[:DETECTED_IN {severity: int, impact_description: string}]
```

**Properties on WORKS_FOR:**
```cypher
[:WORKS_FOR {win_rate: float, sample_size: int, last_used: datetime}]
```

### Event Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| `HAS_EARNINGS` | Ticker | EarningsEvent | Ticker has earnings |
| `AFFECTED_BY` | Ticker | Catalyst | Ticker affected by catalyst |
| `EXPOSED_TO` | Ticker | MacroEvent | Macro exposure |
| `THREATENS` | Risk | Ticker | Risk threatens ticker |

### Analysis Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| `ANALYZES` | Analysis | Ticker | Analysis covers ticker |
| `MENTIONS` | Analysis | * | Analysis mentions entity |
| `BASED_ON` | Trade | Analysis | Trade based on analysis |
| `TRADED` | Trade | Ticker | Trade in ticker |
| `COVERS` | Analyst | Ticker | Analyst covers ticker |

**Properties on COVERS:**
```cypher
[:COVERS {rating: string, target_price: float, updated_at: datetime}]
```

### Learning Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| `DERIVED_FROM` | Learning | Trade | Lesson from trade |
| `ADDRESSES` | Learning | Bias | Learning addresses bias |
| `UPDATES` | Learning | Strategy | Learning updates strategy |
| `MITIGATED_BY` | Risk | Strategy | Risk mitigated by strategy |
| `FOLLOWED` | Trade | Learning | Trade followed rule |
| `VIOLATED` | Trade | Learning | Trade violated rule |

### Provenance Relationships

| Relationship | From | To | Description |
|-------------|------|-----|-------------|
| `EXTRACTED_FROM` | * | Document | Entity extracted from doc |

**Properties on EXTRACTED_FROM:**
```cypher
[:EXTRACTED_FROM {field_path: string, confidence: float, extracted_at: datetime}]
```

---

## Indexes Summary

```cypher
-- Unique constraints
CREATE CONSTRAINT ticker_symbol IF NOT EXISTS FOR (t:Ticker) REQUIRE t.symbol IS UNIQUE;
CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT analysis_id IF NOT EXISTS FOR (a:Analysis) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT trade_id IF NOT EXISTS FOR (t:Trade) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT learning_id IF NOT EXISTS FOR (l:Learning) REQUIRE l.id IS UNIQUE;
CREATE CONSTRAINT strategy_name IF NOT EXISTS FOR (s:Strategy) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT bias_name IF NOT EXISTS FOR (b:Bias) REQUIRE b.name IS UNIQUE;
CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT industry_name IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE;
CREATE CONSTRAINT pattern_name IF NOT EXISTS FOR (p:Pattern) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT risk_name IF NOT EXISTS FOR (r:Risk) REQUIRE r.name IS UNIQUE;
CREATE CONSTRAINT signal_name IF NOT EXISTS FOR (s:Signal) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT product_name IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT timeframe_name IF NOT EXISTS FOR (t:Timeframe) REQUIRE t.name IS UNIQUE;

-- Traversal indexes
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

-- Trading intelligence indexes
CREATE INDEX trade_pnl_idx IF NOT EXISTS FOR (t:Trade) ON (t.pnl_percent);
CREATE INDEX trade_conviction_idx IF NOT EXISTS FOR (t:Trade) ON (t.stated_conviction);
CREATE INDEX trade_status_idx IF NOT EXISTS FOR (t:Trade) ON (t.status);
CREATE INDEX strategy_win_rate_idx IF NOT EXISTS FOR (s:Strategy) ON (s.win_rate);
CREATE INDEX bias_occurrences_idx IF NOT EXISTS FOR (b:Bias) ON (b.total_occurrences);
CREATE INDEX pattern_reliability_idx IF NOT EXISTS FOR (p:Pattern) ON (p.reliability_score);
CREATE INDEX learning_effectiveness_idx IF NOT EXISTS FOR (l:Learning) ON (l.effectiveness_score);

-- Full-text search
CALL db.index.fulltext.createNodeIndex(
  'entitySearch',
  ['Ticker','Company','Executive','Product','Pattern','Risk'],
  ['name','symbol','description']
);
```

---

## v2.5 Entity Extraction

Entities extracted from v2.5 skill sections (3-regime case analysis):

| Section | Entity Types | Description |
|---------|--------------|-------------|
| `bull_case_analysis` | Catalyst, Pattern, Strategy | Arguments for upside scenario |
| `base_case_analysis` | Pattern, Risk | Arguments for range-bound/flat scenario |
| `bear_case_analysis` | Risk, Catalyst, Pattern | Arguments for downside scenario |
| `bias_check.biases_detected` | Bias | Detected trading biases |
| `bias_check.countermeasures_applied` | Learning | Rules to counter biases |
| `threat_assessment.structural_threats` | Risk | Long-term structural risks |
| `threat_assessment.cyclical_risks` | Risk | Short-term cyclical risks |
| `meta_learning.patterns_applied` | Pattern | Patterns being tested |
| `meta_learning.rules_tested` | Learning | Rules being validated |
| `falsification.conditions` | Signal | Thesis invalidation triggers |

### 3-Regime Argument Extraction

Each case (bull/base/bear) extracts structured arguments:

```yaml
# Example extraction from bull_case_analysis.arguments[]
- argument: "Best-in-class business at multi-year low valuation"
  score: 8
  evidence: "28.5x P/E vs 5-year avg 33x"
  → Creates: Pattern node "low_valuation_opportunity"
  → Creates: SUPPORTS edge to bull thesis
```

---

## Common Queries

### Get Ticker Context
```cypher
MATCH (t:Ticker {symbol: $symbol})-[r*1..2]-(connected)
RETURN t, r, connected
```

### Sector Peers
```cypher
MATCH (c1:Company)-[:ISSUED]->(t:Ticker {symbol: $symbol}),
      (c1)-[:IN_SECTOR]->(s:Sector)<-[:IN_SECTOR]-(c2:Company),
      (c2)-[:ISSUED]->(peer:Ticker)
WHERE peer <> t
RETURN DISTINCT peer.symbol, c2.name
```

### Bias History
```cypher
MATCH (b:Bias)-[:DETECTED_IN]->(tr:Trade)
RETURN b.name, count(tr) AS occurrences,
       avg(tr.pnl_percent) AS avg_impact
ORDER BY occurrences DESC
```

### Strategy Performance
```cypher
MATCH (s:Strategy)<-[:BASED_ON]-(tr:Trade)
WITH s.name AS strategy,
     count(tr) AS trades,
     sum(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) * 1.0 / count(tr) AS win_rate,
     avg(tr.pnl_percent) AS avg_return
WHERE trades >= 3
RETURN strategy, trades, win_rate, avg_return
ORDER BY win_rate DESC
```

### Learning Effectiveness
```cypher
MATCH (l:Learning)
OPTIONAL MATCH (l)<-[:FOLLOWED]-(followed:Trade)
OPTIONAL MATCH (l)<-[:VIOLATED]-(violated:Trade)
WITH l, count(followed) AS follows, count(violated) AS violations,
     avg(followed.pnl_percent) AS follow_avg,
     avg(violated.pnl_percent) AS violate_avg
RETURN l.rule, follows, violations,
       follow_avg - violate_avg AS rule_value
ORDER BY rule_value DESC
```

---

## Schema Initialization

```bash
# Initialize graph schema
python orchestrator.py graph init

# Check status
python orchestrator.py graph status
```

The `graph init` command creates all constraints and indexes.

---

## Related Documentation

- [Trading Graph Architecture](TRADING_GRAPH_ARCHITECTURE.md) - Full architecture details
- [Trading RAG Architecture](TRADING_RAG_ARCHITECTURE.md) - Vector search companion
- [Database Schema](DATABASE_SCHEMA.md) - PostgreSQL schema
