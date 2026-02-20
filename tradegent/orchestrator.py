#!/usr/bin/env python3
"""
Nexus Light Trading Platform - Orchestrator v2.2
Database-driven two-stage pipeline: Analysis → Execution via Claude Code CLI

All configuration (stocks, scanners, schedules) lives in PostgreSQL.
RAG embeddings stored in pgvector, knowledge graph in Neo4j.

Usage:
    python orchestrator.py analyze NFLX --type earnings
    python orchestrator.py execute analyses/NFLX_earnings_20260217.md
    python orchestrator.py pipeline NFLX --type earnings
    python orchestrator.py scan                              # run all enabled IB scanners
    python orchestrator.py scan --scanner HIGH_OPT_IMP_VOLAT # specific scanner
    python orchestrator.py watchlist                          # analyze all enabled stocks
    python orchestrator.py review                             # portfolio review
    python orchestrator.py run-due                            # execute all due schedules
    python orchestrator.py status                             # show system status
    python orchestrator.py db-init                            # initialize database schema
"""

import subprocess
import sys
import json
import re
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from db_layer import NexusDB, Stock, IBScanner, Schedule

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

for d in [BASE_DIR / "analyses", BASE_DIR / "trades", BASE_DIR / "logs"]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "logs" / "orchestrator.log"),
    ],
)
log = logging.getLogger("nexus-light")


class Settings:
    """
    Hot-reloadable settings from PostgreSQL.
    Call refresh() to pull latest values — no restart required.
    Falls back to env vars → hardcoded defaults if DB unavailable.
    """

    def __init__(self, db: Optional["NexusDB"] = None):
        self._cache: dict = {}
        self._last_refresh: Optional[datetime] = None
        self._db = db
        if db:
            self.refresh()

    def refresh(self):
        """Pull all settings from DB into local cache."""
        if not self._db:
            return
        try:
            self._cache = self._db.get_all_settings()
            self._last_refresh = datetime.now()
            log.debug(f"Settings refreshed: {len(self._cache)} keys")
        except Exception as e:
            log.warning(f"Settings refresh failed (using cached): {e}")

    def _get(self, key: str, env_key: Optional[str] = None, default: Any = None) -> Any:
        """Get setting: DB cache → env var → default."""
        # DB cache first
        if key in self._cache:
            return self._cache[key]
        # Env var fallback
        if env_key and os.getenv(env_key):
            return os.getenv(env_key)
        return default

    def _get_bool(self, key: str, env_key: Optional[str] = None, default: bool = False) -> bool:
        """Get a boolean setting with safe coercion (handles string 'false')."""
        val = self._get(key, env_key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ('true', '1', 'yes')
        return bool(val)

    # ─── Accessors ───────────────────────────────────────────────────

    @property
    def claude_cmd(self) -> str:
        return self._get('claude_cmd', 'CLAUDE_CMD', 'claude')

    @property
    def claude_timeout(self) -> int:
        return int(self._get('claude_timeout_seconds', 'CLAUDE_TIMEOUT', 600))

    @property
    def allowed_tools_analysis(self) -> str:
        return self._get('allowed_tools_analysis', None,
                         'mcp__ib-mcp__*,WebSearch,mcp__brave-search__*,mcp__trading-rag__*,mcp__trading-graph__*')

    @property
    def allowed_tools_execution(self) -> str:
        return self._get('allowed_tools_execution', None,
                         'mcp__ib-mcp__*,mcp__trading-rag__*,mcp__trading-graph__*')

    @property
    def allowed_tools_scanner(self) -> str:
        return self._get('allowed_tools_scanner', None, 'mcp__ib-mcp__*')

    @property
    def ib_account(self) -> str:
        return self._get('ib_account', 'IB_ACCOUNT', 'DU_PAPER')

    @property
    def kb_ingest_enabled(self) -> bool:
        """Enable ingestion to RAG (pgvector) and Graph (Neo4j) after analysis."""
        return self._get_bool('kb_ingest_enabled', None, True)

    @property
    def max_daily_analyses(self) -> int:
        return int(self._get('max_daily_analyses', 'MAX_DAILY_ANALYSES', 15))

    @property
    def max_daily_executions(self) -> int:
        return int(self._get('max_daily_executions', 'MAX_DAILY_EXECUTIONS', 5))

    @property
    def max_concurrent_runs(self) -> int:
        return int(self._get('max_concurrent_runs', None, 2))

    @property
    def auto_execute_enabled(self) -> bool:
        return self._get_bool('auto_execute_enabled', None, False)

    @property
    def scanners_enabled(self) -> bool:
        return self._get_bool('scanners_enabled', None, True)

    @property
    def kb_query_enabled(self) -> bool:
        """Enable RAG+Graph context injection during analysis."""
        return self._get_bool('kb_query_enabled', None, True)

    @property
    def dry_run_mode(self) -> bool:
        return self._get_bool('dry_run_mode', None, True)

    @property
    def scheduler_poll_seconds(self) -> int:
        return int(self._get('scheduler_poll_seconds', None, 60))

    @property
    def earnings_check_hours(self) -> list[int]:
        val = self._get('earnings_check_hours', None, [6, 7])
        return val if isinstance(val, list) else [6, 7]

    @property
    def earnings_lookback_days(self) -> int:
        return int(self._get('earnings_lookback_days', None, 21))

    @property
    def analyses_dir(self) -> Path:
        return BASE_DIR / self._get('analyses_dir', None, 'analyses')

    @property
    def trades_dir(self) -> Path:
        return BASE_DIR / self._get('trades_dir', None, 'trades')

    @property
    def logs_dir(self) -> Path:
        return BASE_DIR / self._get('logs_dir', None, 'logs')


# Module-level default (overridden when DB is available)
cfg = Settings()


# ─── Data Models ─────────────────────────────────────────────────────────────

class AnalysisType(Enum):
    EARNINGS = "earnings"
    STOCK = "stock"
    SCAN = "scan"
    REVIEW = "review"
    POSTMORTEM = "postmortem"


@dataclass
class AnalysisResult:
    ticker: str
    type: AnalysisType
    filepath: Path
    gate_passed: bool
    recommendation: str
    confidence: int
    expected_value: float
    raw_output: str
    parsed_json: Optional[dict] = None


@dataclass
class ExecutionResult:
    analysis_path: Path
    order_placed: bool
    order_details: Optional[dict] = None
    reason: str = ""
    filepath: Optional[Path] = None
    raw_output: str = ""


# ─── Prompt Builders ─────────────────────────────────────────────────────────

def build_analysis_prompt(ticker: str, analysis_type: AnalysisType,
                          stock: Optional[Stock] = None,
                          kb_enabled: bool = True) -> str:
    """Build Stage 1 prompt, enriched with stock metadata from DB and KB context."""

    stock_ctx = ""
    if stock:
        stock_ctx = f"""
STOCK CONTEXT (from database):
- Ticker: {stock.ticker} ({stock.name or 'N/A'})
- Sector: {stock.sector or 'N/A'}
- State: {stock.state} | Priority: {stock.priority}/10
- Earnings: {stock.next_earnings_date or 'Unknown'} ({'confirmed' if stock.earnings_confirmed else 'unconfirmed'})
- Beat History: {stock.beat_history or 'Unknown'}
- Open Position: {stock.has_open_position} ({stock.position_state or 'none'})
- Max Position Size: {stock.max_position_pct}%
- Tags: {', '.join(stock.tags) if stock.tags else 'none'}
- Notes: {stock.comments or 'none'}
"""

    json_block = """
End with a JSON block for machine parsing:
```json
{{
    "ticker": "{ticker}",
    "gate_passed": true/false,
    "recommendation": "BULLISH/BEARISH/NEUTRAL/WAIT",
    "confidence": 0-100,
    "expected_value_pct": 0.0,
    "entry_price": null,
    "stop_loss": null,
    "target": null,
    "position_size_pct": 0.0,
    "structure": "none/shares/call_spread/put_spread/iron_condor/straddle",
    "expiry": null,
    "strikes": null,
    "rationale_summary": "one line summary"
}}
```
""".replace("{ticker}", ticker)

    # Get KB context (RAG + Graph)
    kb_ctx = ""
    if kb_enabled and ticker != "PORTFOLIO":
        kb_ctx = build_kb_context(ticker, analysis_type.value)
        if kb_ctx:
            kb_ctx = f"\nKNOWLEDGE BASE CONTEXT:\n{kb_ctx}\n"

    if analysis_type == AnalysisType.EARNINGS:
        return f"""You are a systematic trading analyst. Follow the earnings-analysis skill framework EXACTLY.

SKILL INSTRUCTIONS: Read and follow /mnt/skills/user/earnings-analysis/SKILL.md
{stock_ctx}
{kb_ctx}
DATA GATHERING (use tools):
1. Via IB MCP: Get {ticker} current price, IV percentile, options chain (nearest monthly expiry)
2. Via IB MCP: Get {ticker} historical volatility (20-day, 60-day)
3. Via Web Search: Get {ticker} earnings estimates (EPS, revenue consensus)
4. Via Web Search: Get {ticker} recent analyst upgrades/downgrades (last 30 days)
5. Via Web Search: Get {ticker} recent news and catalysts (last 14 days)
6. Via IB MCP: Get current portfolio positions to check existing exposure

ANALYSIS:
Run the complete 8-phase earnings analysis framework.
Pay special attention to:
- The "Do Nothing" gate (ALL 4 criteria must pass)
- Bias detection (especially timing conservatism pattern)
- Pre-earnings positioning matrix
- News age decay assessment

OUTPUT FORMAT: Use the exact output format from the skill.
CRITICAL: If the Do Nothing gate FAILS, state NO POSITION RECOMMENDED.
{json_block}"""

    elif analysis_type == AnalysisType.STOCK:
        return f"""You are a systematic trading analyst. Follow the stock-analysis skill framework EXACTLY.

SKILL INSTRUCTIONS: Read and follow /mnt/skills/user/stock-analysis/SKILL.md
Also read: /mnt/skills/user/stock-analysis/comprehensive_framework.md
{stock_ctx}
{kb_ctx}
DATA GATHERING (use tools):
1. Via IB MCP: Get {ticker} current price, volume, key technicals
2. Via IB MCP: Get {ticker} options chain for implied volatility assessment
3. Via Web Search: Get {ticker} recent news, analyst ratings, price targets
4. Via Web Search: Get {ticker} sector and competitor performance

ANALYSIS: Run the complete stock analysis framework.
{json_block}"""

    elif analysis_type == AnalysisType.POSTMORTEM:
        return f"""You are a systematic trading analyst performing a MANDATORY post-earnings review.

SKILL INSTRUCTIONS: Read Phase 8 of /mnt/skills/user/earnings-analysis/SKILL.md
{stock_ctx}
{kb_ctx}
DATA GATHERING:
1. Via Web Search: Get {ticker} actual earnings results
2. Via Web Search: Get {ticker} post-earnings stock reaction
3. Via IB MCP: Get {ticker} current price and any open positions

POST-MORTEM: Compare predictions vs results, error analysis, bias detection.

End with JSON:
```json
{{
    "ticker": "{ticker}",
    "prediction_accuracy": 0-100,
    "scenario_matched": "strong_beat/modest_beat/miss",
    "direction_correct": true/false,
    "magnitude_correct": true/false,
    "key_learning": "one line",
    "framework_adjustment": "one line recommendation"
}}
```
"""

    elif analysis_type == AnalysisType.REVIEW:
        return f"""You are a systematic portfolio manager performing a comprehensive review.

DATA GATHERING:
1. Via IB MCP: Get all current positions, P&L, and account summary
2. Via IB MCP: Get portfolio Greeks and risk metrics
3. Via Web Search: Get current market overview and key sector performance

REVIEW: Portfolio composition, P&L attribution, risk assessment, framework effectiveness.
Output as comprehensive markdown report.
"""

    return f"Analyze {ticker} using available tools."


def build_scanner_prompt(scanner: IBScanner) -> str:
    """Build prompt for running an IB scanner."""
    filters_str = json.dumps(scanner.filters, indent=2)

    return f"""You are a market scanner operator. Run an IB market scanner and report results.

SCANNER: {scanner.scanner_code} ({scanner.display_name})
Instrument: {scanner.instrument} | Location: {scanner.location} | Max: {scanner.num_results}
Filters: {filters_str}

INSTRUCTIONS:
1. Via IB MCP: Run scanner "{scanner.scanner_code}" with parameters above
2. For top {scanner.max_candidates} results: get price, volume, IV%
3. Score each (1-10)

OUTPUT as markdown table then list top candidates.

End with JSON:
```json
{{
    "scanner": "{scanner.scanner_code}",
    "scan_time": "ISO-8601",
    "results_count": 0,
    "candidates": [
        {{"ticker": "XXX", "score": 8, "price": 0.0, "notes": "..."}}
    ]
}}
```
"""


def build_execution_prompt(analysis_path: Path, analysis_content: str,
                           stock: Optional[Stock] = None) -> str:
    """Build Stage 2 prompt for trade execution."""

    ticker = analysis_path.stem.split("_")[0]
    stock_ctx = ""
    if stock:
        state_map = {
            'analysis': f"\n⚠️ CRITICAL: Stock in ANALYSIS state — DO NOT PLACE ORDERS. Log recommendation only.",
            'paper': f"\n✅ Stock in PAPER state — place orders on paper account {cfg.ib_account}.",
            'live': f"\n🔴 Stock in LIVE state — requires additional confirmation. DO NOT auto-execute.",
        }
        stock_ctx = f"""
STOCK STATE FROM DATABASE:
- State: {stock.state}{state_map.get(stock.state, '')}
- Max Position: {stock.max_position_pct}%
- Open Position: {stock.has_open_position} ({stock.position_state or 'none'})
"""

    return f"""You are a trade execution agent. Read analysis, validate, place paper orders if appropriate.

ANALYSIS FILE: {analysis_path.name}
{stock_ctx}
ANALYSIS CONTENT:
{analysis_content}

EXECUTION PROTOCOL:

STEP 1: Parse the JSON trade plan from analysis.
STEP 2: Validate "Do Nothing" gate — must be PASSED. If FAILED → NO ORDER.
STEP 3: Check stock state — "analysis" → recommendation only, "paper" → paper orders OK.
STEP 4: Pre-flight via IB MCP:
  a. Check existing {ticker} exposure
  b. Verify buying power
  c. Verify current price is within entry zone
  d. If options: verify strikes exist with <15% bid/ask spread
STEP 5: Position sizing — max {stock.max_position_pct if stock else 6.0}% of portfolio.
STEP 6: Place LIMIT order (paper only, account {cfg.ib_account}).
  - Price >3% from entry → GTC limit
  - Price in entry zone → DAY limit

End with JSON:
```json
{{
    "ticker": "{ticker}",
    "action": "ORDER_PLACED/NO_ORDER/RECOMMENDATION_ONLY",
    "gate_passed": true/false,
    "stock_state": "{stock.state if stock else 'unknown'}",
    "reason": "...",
    "order_id": null,
    "order_type": "LIMIT",
    "quantity": 0,
    "limit_price": 0.0,
    "structure": "...",
    "account": "{cfg.ib_account}",
    "timestamp": "ISO-8601"
}}
```
"""


# ─── Core Functions ──────────────────────────────────────────────────────────

def call_claude_code(prompt: str, allowed_tools: str, label: str,
                     timeout: Optional[int] = None) -> str:
    """Execute a Claude Code CLI call."""
    timeout = timeout or cfg.claude_timeout

    if cfg.dry_run_mode:
        log.info(f"[{label}] DRY RUN — would call Claude Code ({len(prompt)} char prompt)")
        return ""

    log.info(f"[{label}] Calling Claude Code...")
    try:
        result = subprocess.run(
            [cfg.claude_cmd, "--print", "--dangerously-skip-permissions",
             "--allowedTools", allowed_tools, "-p", prompt],
            capture_output=True, text=True, timeout=timeout, cwd=str(BASE_DIR),
        )
        if result.returncode != 0:
            log.error(f"[{label}] Error (rc={result.returncode}): {result.stderr[:500]}")
            return ""
        log.info(f"[{label}] Completed ({len(result.stdout)} chars)")
        return result.stdout
    except subprocess.TimeoutExpired:
        log.error(f"[{label}] Timed out after {timeout}s")
        return ""
    except FileNotFoundError:
        log.error(f"[{label}] 'claude' CLI not found in PATH")
        return ""


def parse_json_block(text: str) -> Optional[dict]:
    """Extract the last JSON block from output."""
    # Try fenced JSON blocks first
    pattern = r"```json\s*\n(.*?)\n\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if not matches:
        # Fallback: find balanced braces containing "ticker"
        # Handles nested objects like {"candidates": [{...}]}
        for i in range(len(text) - 1, -1, -1):
            if text[i] == '}':
                depth = 0
                for j in range(i, -1, -1):
                    if text[j] == '}':
                        depth += 1
                    elif text[j] == '{':
                        depth -= 1
                    if depth == 0:
                        candidate = text[j:i+1]
                        if '"ticker"' in candidate or '"scanner"' in candidate:
                            matches = [candidate]
                        break
                if matches:
                    break
    if matches:
        try:
            return json.loads(matches[-1])
        except json.JSONDecodeError as e:
            log.warning(f"JSON parse error: {e}")
    return None


def kb_ingest_analysis(filepath: Path, metadata: dict):
    """Ingest analysis document into RAG (pgvector) for semantic search."""
    if not cfg.kb_ingest_enabled:
        return
    try:
        from rag.embed import embed_document
        result = embed_document(str(filepath))
        if result.error_message:
            log.warning(f"RAG ingest warning: {result.error_message}")
        else:
            log.debug(f"RAG ingest: {result.doc_id} ({result.chunk_count} chunks)")
    except ImportError:
        log.debug("RAG module not available, skipping ingest")
    except Exception as e:
        log.warning(f"RAG ingest failed: {e}")


# ─── Knowledge Base Context ──────────────────────────────────────────────────

def build_kb_context(ticker: str, analysis_type: str) -> str:
    """
    Gather hybrid RAG + Graph context before analysis.

    Called by build_analysis_prompt() to inject historical context.
    Returns empty string if knowledge base unavailable.
    """
    try:
        from rag.hybrid import build_analysis_context as rag_context
        context = rag_context(ticker, analysis_type)
        if context and len(context) > 100:
            log.info(f"KB context injected for {ticker} ({len(context)} chars)")
            return context
    except ImportError:
        log.debug("RAG module not available, skipping KB context")
    except Exception as e:
        log.warning(f"KB context injection failed: {e}")
    return ""


def kb_ingest_file(file_path: str) -> dict:
    """
    Ingest a file into both Graph and RAG systems.

    Returns dict with extraction and embedding results.
    """
    results = {"graph": None, "rag": None, "errors": []}

    # Graph extraction
    try:
        from graph.extract import extract_document
        result = extract_document(file_path, commit=True)
        results["graph"] = {
            "entities": len(result.entities),
            "relations": len(result.relations),
            "committed": result.committed,
        }
    except Exception as e:
        results["errors"].append(f"Graph: {e}")

    # RAG embedding
    try:
        from rag.embed import embed_document
        result = embed_document(file_path)
        results["rag"] = {
            "chunks": result.chunk_count,
            "duration_ms": result.duration_ms,
        }
    except Exception as e:
        results["errors"].append(f"RAG: {e}")

    return results


# ─── Stage 1: Analysis ──────────────────────────────────────────────────────

def run_analysis(db: NexusDB, ticker: str, analysis_type: AnalysisType,
                 schedule_id: Optional[int] = None) -> Optional[AnalysisResult]:
    """Stage 1: Generate analysis via Claude Code."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filepath = cfg.analyses_dir / f"{ticker}_{analysis_type.value}_{timestamp}.md"
    stock = db.get_stock(ticker) if ticker != "PORTFOLIO" else None

    run_id = db.mark_schedule_started(schedule_id) if schedule_id else None

    log.info(f"═══ STAGE 1: ANALYSIS ═══ {ticker} ({analysis_type.value})")

    prompt = build_analysis_prompt(ticker, analysis_type, stock,
                                    kb_enabled=cfg.kb_query_enabled)
    output = call_claude_code(prompt, cfg.allowed_tools_analysis, f"ANALYZE-{ticker}")

    if not output:
        if run_id and schedule_id:
            db.mark_schedule_completed(schedule_id, run_id, 'failed',
                                       error="Claude Code returned empty")
        return None

    filepath.write_text(output)
    parsed = parse_json_block(output)

    result = AnalysisResult(
        ticker=ticker, type=analysis_type, filepath=filepath,
        gate_passed=parsed.get("gate_passed", False) if parsed else False,
        recommendation=parsed.get("recommendation", "UNKNOWN") if parsed else "UNKNOWN",
        confidence=parsed.get("confidence", 0) if parsed else 0,
        expected_value=parsed.get("expected_value_pct", 0.0) if parsed else 0.0,
        raw_output=output, parsed_json=parsed,
    )

    # Persist to DB
    if run_id and schedule_id:
        db.mark_schedule_completed(schedule_id, run_id, 'completed',
            gate_passed=result.gate_passed, recommendation=result.recommendation,
            confidence=result.confidence, expected_value=result.expected_value,
            analysis_file=str(filepath))

    if parsed and ticker not in ("PORTFOLIO", "SCAN"):
        try:
            db.save_analysis_result(run_id, ticker, analysis_type.value, parsed)
        except Exception as e:
            log.warning(f"Save analysis result failed: {e}")

    kb_ingest_analysis(filepath, {"ticker": ticker, "type": analysis_type.value,
                                   "date": timestamp, "gate_passed": result.gate_passed})

    # Increment service counters
    try:
        db.increment_service_counter('analyses_total')
        db.increment_service_counter('today_analyses')
    except Exception:
        pass

    log.info(f"Analysis: {ticker} | Gate: {'PASS' if result.gate_passed else 'FAIL'} | "
             f"Rec: {result.recommendation} | Conf: {result.confidence}%")
    return result


# ─── Stage 2: Execution ─────────────────────────────────────────────────────

def run_execution(db: NexusDB, analysis_path: Path) -> ExecutionResult:
    """Stage 2: Read analysis, validate, place paper order."""

    log.info(f"═══ STAGE 2: EXECUTION ═══ {analysis_path.name}")
    content = analysis_path.read_text()
    ticker = analysis_path.stem.split("_")[0]
    stock = db.get_stock(ticker)

    # Short-circuits
    if '"gate_passed": false' in content or "GATE: ❌ FAIL" in content:
        log.info("Gate FAILED → skip execution")
        return ExecutionResult(analysis_path=analysis_path, order_placed=False,
                               reason="Do Nothing gate failed")

    if stock and stock.state == 'analysis':
        log.info(f"{ticker} state=analysis → recommendation only")

    prompt = build_execution_prompt(analysis_path, content, stock)
    output = call_claude_code(prompt, cfg.allowed_tools_execution, f"EXECUTE-{ticker}")

    if not output:
        return ExecutionResult(analysis_path=analysis_path, order_placed=False,
                               reason="Execution call failed")

    parsed = parse_json_block(output)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    trade_path = cfg.trades_dir / f"{ticker}_trade_{ts}.md"
    trade_path.write_text(output)

    result = ExecutionResult(
        analysis_path=analysis_path,
        order_placed=parsed.get("action") == "ORDER_PLACED" if parsed else False,
        order_details=parsed,
        reason=parsed.get("reason", "") if parsed else "Parse failed",
        filepath=trade_path, raw_output=output,
    )

    if result.order_placed and stock:
        db.update_stock_position(ticker, True, 'pending')

    # Increment service counters
    try:
        db.increment_service_counter('executions_total')
        db.increment_service_counter('today_executions')
    except Exception:
        pass

    kb_ingest_analysis(trade_path, {"ticker": ticker, "type": "trade_execution",
                                     "date": ts, "order_placed": result.order_placed})

    log.info(f"Execution: {ticker} | {'ORDER PLACED' if result.order_placed else 'NO ORDER'}")
    return result


# ─── Pipeline Orchestration ──────────────────────────────────────────────────

def run_pipeline(db: NexusDB, ticker: str, analysis_type: AnalysisType,
                 auto_execute: bool = True, schedule_id: Optional[int] = None):
    """Full two-stage pipeline."""
    log.info(f"╔═ PIPELINE: {ticker} ({analysis_type.value}) ═╗")

    analysis = run_analysis(db, ticker, analysis_type, schedule_id)
    if not analysis:
        return

    if not auto_execute or not cfg.auto_execute_enabled or not analysis.gate_passed:
        reasons = []
        if not auto_execute:
            reasons.append("auto-execute OFF (schedule)")
        if not cfg.auto_execute_enabled:
            reasons.append("auto-execute OFF (global)")
        if not analysis.gate_passed:
            reasons.append("gate FAILED")
        log.info(f"Pipeline stop: {', '.join(reasons)}")
        return

    stock = db.get_stock(ticker)
    if stock and stock.state == 'analysis':
        log.info(f"{ticker} state=analysis → no execution")
        return

    run_execution(db, analysis.filepath)


def run_watchlist(db: NexusDB, auto_execute: bool = False):
    """Analyze all enabled stocks."""
    stocks = db.get_enabled_stocks()
    remaining = cfg.max_daily_analyses - db.get_today_run_count()
    log.info(f"═══ WATCHLIST: {len(stocks)} stocks, {remaining} slots remaining ═══")

    for stock in stocks[:max(0, remaining)]:
        atype = AnalysisType(stock.default_analysis_type)
        if stock.days_to_earnings is not None and stock.days_to_earnings <= 14:
            atype = AnalysisType.EARNINGS
        run_pipeline(db, stock.ticker, atype, auto_execute=auto_execute)


def run_scanners(db: NexusDB, scanner_code: Optional[str] = None):
    """Run IB scanners."""
    if not cfg.scanners_enabled:
        log.info("Scanners disabled (scanners_enabled=false)")
        return

    if scanner_code:
        s = db.get_scanner_by_code(scanner_code)
        scanners = [s] if s else []
    else:
        scanners = db.get_enabled_scanners()

    log.info(f"═══ SCANNERS: {len(scanners)} ═══")

    for scanner in scanners:
        log.info(f"Scanner: {scanner.display_name}")
        output = call_claude_code(
            build_scanner_prompt(scanner), cfg.allowed_tools_scanner,
            f"SCAN-{scanner.scanner_code}")
        if not output:
            continue

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        fp = cfg.analyses_dir / f"scanner_{scanner.scanner_code}_{ts}.md"
        fp.write_text(output)

        parsed = parse_json_block(output)
        if not parsed or "candidates" not in parsed:
            continue

        candidates = parsed["candidates"]
        log.info(f"  {len(candidates)} candidates found")

        if scanner.auto_add_to_watchlist:
            for c in candidates[:scanner.max_candidates]:
                db.upsert_stock(c["ticker"], is_enabled=True,
                                tags=[f"scanner:{scanner.scanner_code}"])

        if scanner.auto_analyze:
            atype = AnalysisType(scanner.analysis_type)
            for c in candidates[:scanner.max_candidates]:
                run_pipeline(db, c["ticker"], atype, auto_execute=False)


def run_earnings_check(db: NexusDB):
    """Trigger pre/post-earnings schedules based on earnings dates."""
    stocks = db.get_stocks_near_earnings(days=21)
    log.info(f"═══ EARNINGS CHECK: {len(stocks)} stocks ═══")

    for stock in stocks:
        days = stock.days_to_earnings
        if days is None:
            continue
        schedules = db.get_earnings_triggered_schedules(stock.ticker, days)
        for sched in schedules:
            log.info(f"  Triggering: {sched.name} for {stock.ticker} (T-{days})")
            run_pipeline(db, stock.ticker, AnalysisType(sched.analysis_type),
                         auto_execute=sched.auto_execute, schedule_id=sched.id)


def run_due_schedules(db: NexusDB):
    """Execute all schedules that are due."""
    schedules = db.get_due_schedules()
    log.info(f"═══ DUE SCHEDULES: {len(schedules)} ═══")

    remaining_analyses = cfg.max_daily_analyses - db.get_today_run_count()
    if remaining_analyses <= 0:
        log.info("Daily analysis limit reached — skipping due schedules")
        return

    def _run_scanner_task(s: Schedule) -> None:
        if s.target_scanner_id:
            scanner = db.get_scanner(s.target_scanner_id)
            if scanner:
                run_scanners(db, scanner.scanner_code)

    task_dispatch = {
        'analyze_stock': lambda s: run_analysis(db, s.target_ticker, AnalysisType(s.analysis_type), s.id) if s.target_ticker else None,
        'analyze_watchlist': lambda s: run_watchlist(db, s.auto_execute),
        'run_scanner': _run_scanner_task,
        'run_all_scanners': lambda s: run_scanners(db),
        'pipeline': lambda s: run_pipeline(db, s.target_ticker, AnalysisType(s.analysis_type), s.auto_execute, s.id) if s.target_ticker else None,
        'portfolio_review': lambda s: run_analysis(db, "PORTFOLIO", AnalysisType.REVIEW, s.id),
        'postmortem': lambda s: run_analysis(db, s.target_ticker, AnalysisType.POSTMORTEM, s.id) if s.target_ticker else None,
    }

    executed = 0
    for sched in schedules:
        if executed >= remaining_analyses:
            log.info("Daily analysis limit reached mid-batch — stopping")
            break

        log.info(f"Executing: {sched.name}")
        try:
            handler = task_dispatch.get(sched.task_type)
            if handler:
                handler(sched)
                executed += 1
            elif sched.task_type == 'custom' and sched.custom_prompt:
                output = call_claude_code(sched.custom_prompt, cfg.allowed_tools_analysis, f"CUSTOM-{sched.id}")
                if output:
                    ts = datetime.now().strftime("%Y%m%d_%H%M")
                    (cfg.analyses_dir / f"custom_{sched.id}_{ts}.md").write_text(output)
        except Exception as e:
            log.error(f"Schedule '{sched.name}' failed: {e}")

        next_run = db.calculate_next_run(sched)
        db.update_next_run(sched.id, next_run)


# ─── Status ──────────────────────────────────────────────────────────────────

def show_status(db: NexusDB):
    stocks = db.get_enabled_stocks()
    by_state: dict[str, list[Stock]] = {}
    for s in stocks:
        by_state.setdefault(s.state, []).append(s)

    print(f"\n{'═'*60}")
    print(f"  NEXUS LIGHT - STATUS")
    print(f"{'═'*60}")

    print(f"\n  WATCHLIST ({len(stocks)} enabled)")
    for state in ['analysis', 'paper', 'live']:
        items = by_state.get(state, [])
        tickers = ', '.join(s.ticker for s in items) if items else '—'
        print(f"    {state:>10}: {tickers}")

    earnings = db.get_stocks_near_earnings()
    if earnings:
        print(f"\n  UPCOMING EARNINGS")
        for s in earnings[:5]:
            print(f"    {s.ticker:<6} {str(s.next_earnings_date):<12} (T-{s.days_to_earnings})")

    scanners = db.get_enabled_scanners()
    print(f"\n  SCANNERS ({len(scanners)} enabled)")
    for sc in scanners:
        auto = "→auto" if sc.auto_analyze else ""
        print(f"    {sc.scanner_code:<35} {auto}")

    schedules = db.get_enabled_schedules()
    due = db.get_due_schedules()
    print(f"\n  SCHEDULES ({len(schedules)} enabled, {len(due)} due)")
    for sch in schedules[:10]:
        status = sch.last_run_status or 'never'
        print(f"    {(sch.name or '')[:40]:<40} {sch.frequency:<12} [{status}]")

    print(f"\n  TODAY: {db.get_today_run_count()} runs (limit {cfg.max_daily_analyses})")
    print(f"{'═'*60}\n")


# ─── Graph and RAG CLI Handlers ──────────────────────────────────────────────

def _check_all_health() -> None:
    """Check health of all services: Neo4j, PostgreSQL, Ollama."""
    import requests

    print(f"\n{'═'*50}")
    print("SERVICE HEALTH CHECK")
    print(f"{'═'*50}\n")

    # PostgreSQL + pgvector
    try:
        from rag.schema import health_check as rag_health
        if rag_health():
            print("✅ PostgreSQL (pgvector): OK")
        else:
            print("❌ PostgreSQL (pgvector): FAIL")
    except Exception as e:
        print(f"❌ PostgreSQL (pgvector): {e}")

    # Neo4j
    try:
        from graph.layer import TradingGraph
        with TradingGraph() as g:
            if g.health_check():
                print("✅ Neo4j (graph): OK")
            else:
                print("❌ Neo4j (graph): FAIL")
    except Exception as e:
        print(f"❌ Neo4j (graph): {e}")

    # Ollama
    try:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            has_embed = any("nomic-embed" in n for n in model_names)
            has_llm = any("qwen" in n or "llama" in n for n in model_names)
            status = "OK" if has_embed else "WARN (no embedding model)"
            print(f"✅ Ollama: {status}")
            print(f"   Models: {', '.join(model_names[:5])}")
        else:
            print(f"❌ Ollama: HTTP {resp.status_code}")
    except Exception as e:
        print(f"❌ Ollama: {e}")

    # IB Gateway
    try:
        from ib_insync import IB
        ib = IB()
        ib.connect("localhost", 4002, clientId=99, readonly=True, timeout=5)
        print(f"✅ IB Gateway: Connected")
        ib.disconnect()
    except Exception as e:
        print(f"⚠️ IB Gateway: {e}")

    # Check pending commits
    pending_file = Path("logs/pending_commits.jsonl")
    if pending_file.exists():
        import json
        with open(pending_file, "r") as f:
            pending_count = sum(1 for line in f if line.strip())
        if pending_count > 0:
            print(f"\n⚠️ Pending commits: {pending_count} items")
            print("   Run 'python orchestrator.py graph retry' to process")
    else:
        print(f"\n✅ No pending commits")

    print(f"\n{'═'*50}\n")


def _retry_pending_commits(limit: int = 10) -> None:
    """Retry pending commits from the queue."""
    import json
    from pathlib import Path as _Path

    pending_file = _Path("logs/pending_commits.jsonl")
    if not pending_file.exists():
        print("No pending commits file found")
        return

    from graph.extract import extract_document
    from graph.exceptions import ExtractionError, GraphUnavailableError

    pending_items = []
    with open(pending_file, "r") as f:
        for line in f:
            if line.strip():
                pending_items.append(json.loads(line))

    if not pending_items:
        print("No pending commits to retry")
        return

    print(f"Found {len(pending_items)} pending commits")
    remaining = []
    success_count = 0

    for item in pending_items[:limit]:
        file_path = item.get("file_path", "")
        doc_id = item.get("doc", "unknown")
        retry_count = item.get("retry_count", 0)

        if not _Path(file_path).exists():
            print(f"❌ {doc_id}: File not found, skipping")
            continue

        try:
            result = extract_document(file_path, commit=True)
            if result.committed:
                print(f"✅ {doc_id}: Retry successful")
                success_count += 1
            else:
                item["retry_count"] = retry_count + 1
                item["reason"] = result.error_message or "commit_failed"
                remaining.append(item)
                print(f"⚠️ {doc_id}: Still failing (retry {retry_count + 1})")
        except GraphUnavailableError:
            print(f"❌ {doc_id}: Neo4j still unavailable")
            item["retry_count"] = retry_count + 1
            remaining.append(item)
        except ExtractionError as e:
            print(f"❌ {doc_id}: {e}")
            item["retry_count"] = retry_count + 1
            item["reason"] = str(e)
            remaining.append(item)

    # Keep items beyond the limit
    remaining.extend(pending_items[limit:])

    # Rewrite file with remaining items
    with open(pending_file, "w") as f:
        for item in remaining:
            f.write(json.dumps(item) + "\n")

    print(f"\nRetry complete: {success_count} succeeded, {len(remaining)} remaining")


def _handle_graph_command(args):
    """Handle graph subcommands."""
    from pathlib import Path as _Path
    import glob

    if args.graph_cmd == "init":
        from graph.schema import init_schema
        init_schema()
        print("✅ Neo4j schema initialized")

    elif args.graph_cmd == "reset":
        confirm = input("This will DELETE ALL graph data. Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            from graph.schema import reset_schema
            reset_schema(confirm=True)
            print("✅ Graph reset complete")
        else:
            print("Aborted")

    elif args.graph_cmd == "extract":
        from graph.extract import extract_document
        from graph.exceptions import ExtractionError

        files = []
        if args.file:
            files = [args.file]
        elif args.dir:
            files = list(glob.glob(f"{args.dir}/**/*.yaml", recursive=True))
            files += list(glob.glob(f"{args.dir}/**/*.yml", recursive=True))

        if not files:
            print("No files specified. Use --file or --dir")
            return

        for f in files:
            try:
                result = extract_document(
                    f,
                    extractor=args.extractor,
                    commit=not args.dry_run,
                    dry_run=args.dry_run,
                )
                status = "✅" if result.committed else "⚠️"
                print(f"{status} {result.source_doc_id}: {len(result.entities)} entities, {len(result.relations)} relations")
            except ExtractionError as e:
                print(f"❌ {f}: {e}")

    elif args.graph_cmd == "status":
        from graph.layer import TradingGraph
        try:
            with TradingGraph() as g:
                stats = g.get_stats()
                print(f"\n{'═'*40}")
                print("KNOWLEDGE GRAPH STATUS")
                print(f"{'═'*40}")
                print(f"Total Nodes: {stats.total_nodes}")
                print(f"Total Edges: {stats.total_edges}")
                if stats.node_counts:
                    print("\nNode Types:")
                    for label, count in sorted(stats.node_counts.items(), key=lambda x: -x[1]):
                        print(f"  {label:<20} {count:>6}")
                if stats.edge_counts:
                    print("\nRelationship Types:")
                    for rel, count in sorted(stats.edge_counts.items(), key=lambda x: -x[1])[:10]:
                        print(f"  {rel:<25} {count:>6}")
        except Exception as e:
            print(f"❌ Graph unavailable: {e}")

    elif args.graph_cmd == "search":
        from graph.layer import TradingGraph
        with TradingGraph() as g:
            results = g.find_related(args.ticker.upper(), depth=args.depth)
            print(f"\nNodes within {args.depth} hops of {args.ticker.upper()}:")
            for r in results[:20]:
                labels = ", ".join(r["labels"]) if r["labels"] else "?"
                name = r["props"].get("name") or r["props"].get("symbol") or r["props"].get("id") or "?"
                print(f"  [{labels}] {name}")

    elif args.graph_cmd == "peers":
        from graph.layer import TradingGraph
        with TradingGraph() as g:
            peers = g.get_sector_peers(args.ticker.upper())
            print(f"\nSector peers for {args.ticker.upper()}:")
            for p in peers:
                print(f"  {p.get('peer', '?'):<8} {p.get('company', ''):<30} ({p.get('sector', '')})")

    elif args.graph_cmd == "risks":
        from graph.layer import TradingGraph
        with TradingGraph() as g:
            risks = g.get_risks(args.ticker.upper())
            print(f"\nKnown risks for {args.ticker.upper()}:")
            for r in risks:
                print(f"  • {r.get('risk', '?')}")

    elif args.graph_cmd == "biases":
        from graph.layer import TradingGraph
        with TradingGraph() as g:
            biases = g.get_bias_history(args.name)
            print("\nBias History:")
            for b in biases:
                if "occurrences" in b:
                    print(f"  {b.get('bias', '?'):<25} {b.get('occurrences', 0):>4} occurrences")
                else:
                    print(f"  {b.get('bias', '?')}: trade {b.get('trade_id', '?')} ({b.get('outcome', '?')})")

    elif args.graph_cmd == "query":
        from graph.layer import TradingGraph
        with TradingGraph() as g:
            results = g.run_cypher(args.cypher)
            for r in results:
                print(r)

    elif args.graph_cmd == "dedupe":
        from graph.layer import TradingGraph
        with TradingGraph() as g:
            count = g.dedupe_entities()
            print(f"✅ Merged {count} duplicate entities")

    elif args.graph_cmd == "validate":
        from graph.layer import TradingGraph
        with TradingGraph() as g:
            issues = g.validate_constraints()
            if issues:
                print("⚠️ Constraint issues found:")
                for issue in issues:
                    print(f"  • {issue}")
            else:
                print("✅ No constraint issues")

    elif args.graph_cmd == "retry":
        _retry_pending_commits(limit=args.limit)

    else:
        print("Unknown graph command. Try: graph init, graph extract, graph status, graph search")


def _handle_rag_command(args):
    """Handle rag subcommands."""
    from pathlib import Path as _Path
    from datetime import date as _date
    import glob

    if args.rag_cmd == "init":
        from rag.schema import init_schema
        init_schema()
        print("✅ pgvector schema initialized")

    elif args.rag_cmd == "reset":
        confirm = input("This will DELETE ALL embedded documents. Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            from rag.schema import reset_schema
            reset_schema(confirm=True)
            print("✅ RAG tables reset")
        else:
            print("Aborted")

    elif args.rag_cmd == "embed":
        from rag.embed import embed_document
        from rag.exceptions import EmbedError

        files = []
        if args.file:
            files = [args.file]
        elif args.dir:
            files = list(glob.glob(f"{args.dir}/**/*.yaml", recursive=True))
            files += list(glob.glob(f"{args.dir}/**/*.yml", recursive=True))

        if not files:
            print("No files specified. Use file path or --dir")
            return

        for f in files:
            try:
                result = embed_document(f, force=args.force)
                if result.error_message == "unchanged":
                    print(f"⏭️ {result.doc_id}: unchanged")
                else:
                    print(f"✅ {result.doc_id}: {result.chunk_count} chunks ({result.duration_ms}ms)")
            except EmbedError as e:
                print(f"❌ {f}: {e}")

    elif args.rag_cmd == "reembed":
        from rag.embed import reembed_all
        count = reembed_all(version=args.version)
        print(f"✅ Re-embedded {count} documents")

    elif args.rag_cmd == "search":
        from rag.search import semantic_search

        date_from = None
        if args.since:
            date_from = _date.fromisoformat(args.since)

        results = semantic_search(
            query=args.query,
            ticker=args.ticker,
            doc_type=args.doc_type,
            section=args.section,
            date_from=date_from,
            top_k=args.top,
            min_similarity=args.min_sim,
        )

        print(f"\nSearch results for: {args.query}")
        print(f"{'─'*60}")
        for r in results:
            print(f"\n[{r.similarity:.3f}] {r.doc_id} ({r.doc_type})")
            print(f"Section: {r.section_label}")
            content = r.content[:200].replace("\n", " ")
            print(f"  {content}...")

    elif args.rag_cmd == "hybrid-search":
        from rag.search import hybrid_search

        date_from = None
        if args.since:
            date_from = _date.fromisoformat(args.since)

        results = hybrid_search(
            query=args.query,
            ticker=args.ticker,
            doc_type=args.doc_type,
            section=args.section,
            date_from=date_from,
            top_k=args.top,
            vector_weight=args.vector_weight,
            bm25_weight=args.bm25_weight,
        )

        print(f"\nHybrid search results for: {args.query}")
        print(f"Weights: vector={args.vector_weight}, bm25={args.bm25_weight}")
        print(f"{'─'*60}")
        for r in results:
            print(f"\n[{r.similarity:.4f}] {r.doc_id} ({r.doc_type})")
            print(f"Section: {r.section_label}")
            content = r.content[:200].replace("\n", " ")
            print(f"  {content}...")

    elif args.rag_cmd == "migrate":
        from rag.schema import run_migrations
        run_migrations()
        print("✅ RAG migrations complete")

    elif args.rag_cmd == "status":
        from rag.search import get_rag_stats
        try:
            stats = get_rag_stats()
            print(f"\n{'═'*40}")
            print("RAG STATUS")
            print(f"{'═'*40}")
            print(f"Documents: {stats.document_count}")
            print(f"Chunks: {stats.chunk_count}")
            print(f"Model: {stats.embed_model}")
            print(f"Version: {stats.embed_version}")
            if stats.doc_types:
                print("\nBy Type:")
                for dtype, count in sorted(stats.doc_types.items(), key=lambda x: -x[1]):
                    print(f"  {dtype:<25} {count:>4}")
            if stats.tickers:
                print(f"\nTickers: {', '.join(stats.tickers[:10])}")
        except Exception as e:
            print(f"❌ RAG unavailable: {e}")

    elif args.rag_cmd == "list":
        from rag.search import list_documents
        docs = list_documents(limit=50)
        print(f"\n{'doc_id':<30} {'type':<20} {'ticker':<8} {'chunks'}")
        print(f"{'─'*70}")
        for d in docs:
            print(f"{d['doc_id']:<30} {d['doc_type']:<20} {d.get('ticker') or '—':<8} {d['chunk_count']}")

    elif args.rag_cmd == "show":
        from rag.search import get_document_chunks
        chunks = get_document_chunks(args.doc_id)
        if not chunks:
            print(f"Document not found: {args.doc_id}")
            return
        print(f"\nChunks for {args.doc_id}:")
        for c in chunks:
            print(f"\n[{c['section_label']}] ({c['content_tokens']} tokens)")
            print(c["content"][:300])
            if len(c["content"]) > 300:
                print("...")

    elif args.rag_cmd == "delete":
        from rag.embed import delete_document
        success = delete_document(args.doc_id)
        if success:
            print(f"✅ Deleted {args.doc_id}")
        else:
            print(f"❌ Document not found: {args.doc_id}")

    elif args.rag_cmd == "validate":
        print("⚠️ Validation not yet implemented")

    else:
        print("Unknown rag command. Try: rag init, rag embed, rag search, rag status")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Nexus Light v2.2")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("analyze"); p.add_argument("ticker"); p.add_argument("--type", default="stock", choices=["earnings","stock","postmortem"])
    p = sub.add_parser("execute"); p.add_argument("analysis_file")
    p = sub.add_parser("pipeline"); p.add_argument("ticker"); p.add_argument("--type", default="stock", choices=["earnings","stock"]); p.add_argument("--no-execute", action="store_true")
    p = sub.add_parser("watchlist"); p.add_argument("--auto-execute", action="store_true")
    p = sub.add_parser("scan"); p.add_argument("--scanner")
    sub.add_parser("run-due")
    sub.add_parser("review")
    sub.add_parser("earnings-check")
    sub.add_parser("status")
    sub.add_parser("health", help="Check all service health")
    sub.add_parser("db-init")

    p = sub.add_parser("stock"); p.add_argument("action", choices=["add","enable","disable","set-state","list"])
    p.add_argument("ticker", nargs="?"); p.add_argument("--state", choices=["analysis","paper","live"])
    p.add_argument("--tags", nargs="*"); p.add_argument("--priority", type=int)
    p.add_argument("--earnings-date"); p.add_argument("--comment")

    p = sub.add_parser("settings", help="View or update settings")
    p.add_argument("action", choices=["list", "get", "set"], nargs="?", default="list")
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.add_argument("--category")

    # ─── Graph Commands ───────────────────────────────────────────────────────────
    graph_parser = sub.add_parser("graph", help="Knowledge graph commands")
    graph_sub = graph_parser.add_subparsers(dest="graph_cmd")

    graph_sub.add_parser("init", help="Initialize Neo4j schema")
    graph_sub.add_parser("reset", help="Wipe graph (dev only)")

    p = graph_sub.add_parser("extract", help="Extract from document")
    p.add_argument("file", nargs="?", help="File to extract")
    p.add_argument("--dir", help="Directory to extract")
    p.add_argument("--extractor", default="ollama", choices=["ollama", "claude-api", "openrouter"])
    p.add_argument("--dry-run", action="store_true", help="Preview without committing")

    p = graph_sub.add_parser("reextract", help="Re-extract documents")
    p.add_argument("--all", action="store_true")
    p.add_argument("--since", type=str, help="Date (YYYY-MM-DD)")
    p.add_argument("--version", type=str, help="Extraction version")

    graph_sub.add_parser("status", help="Show graph statistics")

    p = graph_sub.add_parser("search", help="Search around ticker")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--depth", type=int, default=2)

    p = graph_sub.add_parser("peers", help="Find sector peers")
    p.add_argument("ticker", help="Ticker symbol")

    p = graph_sub.add_parser("risks", help="Find known risks")
    p.add_argument("ticker", help="Ticker symbol")

    p = graph_sub.add_parser("biases", help="Show bias history")
    p.add_argument("--name", help="Filter by bias name")

    p = graph_sub.add_parser("query", help="Raw Cypher query")
    p.add_argument("cypher", help="Cypher query string")

    graph_sub.add_parser("dedupe", help="Merge duplicate entities")
    graph_sub.add_parser("validate", help="Check constraint violations")

    p = graph_sub.add_parser("retry", help="Retry pending commits")
    p.add_argument("--limit", type=int, default=10, help="Max items to retry")

    # ─── RAG Commands ─────────────────────────────────────────────────────────────
    rag_parser = sub.add_parser("rag", help="RAG/embedding commands")
    rag_sub = rag_parser.add_subparsers(dest="rag_cmd")

    rag_sub.add_parser("init", help="Initialize pgvector schema")
    rag_sub.add_parser("reset", help="Drop and recreate tables (dev only)")

    p = rag_sub.add_parser("embed", help="Embed document")
    p.add_argument("file", nargs="?", help="File to embed")
    p.add_argument("--dir", help="Directory to embed")
    p.add_argument("--force", action="store_true", help="Re-embed even if unchanged")

    p = rag_sub.add_parser("reembed", help="Re-embed documents")
    p.add_argument("--all", action="store_true")
    p.add_argument("--version", type=str, help="Embed version")

    p = rag_sub.add_parser("search", help="Semantic search")
    p.add_argument("query", help="Search query")
    p.add_argument("--ticker", help="Filter by ticker")
    p.add_argument("--type", dest="doc_type", help="Filter by doc type")
    p.add_argument("--section", help="Filter by section")
    p.add_argument("--since", type=str, help="Date filter (YYYY-MM-DD)")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--min-sim", type=float, default=0.3, help="Min similarity")

    p = rag_sub.add_parser("hybrid-search", help="Hybrid BM25 + vector search")
    p.add_argument("query", help="Search query")
    p.add_argument("--ticker", help="Filter by ticker")
    p.add_argument("--type", dest="doc_type", help="Filter by doc type")
    p.add_argument("--section", help="Filter by section")
    p.add_argument("--since", type=str, help="Date filter (YYYY-MM-DD)")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--vector-weight", type=float, default=0.7, help="Vector weight (default 0.7)")
    p.add_argument("--bm25-weight", type=float, default=0.3, help="BM25 weight (default 0.3)")

    p = rag_sub.add_parser("migrate", help="Run schema migrations")

    rag_sub.add_parser("status", help="Show embedding statistics")
    rag_sub.add_parser("list", help="List embedded documents")

    p = rag_sub.add_parser("show", help="Show document chunks")
    p.add_argument("doc_id", help="Document ID")

    p = rag_sub.add_parser("delete", help="Delete document")
    p.add_argument("doc_id", help="Document ID")

    rag_sub.add_parser("validate", help="Check for orphaned chunks")

    args = parser.parse_args()

    with NexusDB() as db:
        # Initialize settings from DB for all commands
        global cfg
        cfg = Settings(db)
        sys.modules[__name__].__dict__['cfg'] = cfg

        if args.cmd == "db-init":
            db.init_schema(); print("✅ Schema initialized")

        elif args.cmd == "analyze":
            r = run_analysis(db, args.ticker.upper(), AnalysisType(args.type))
            if r: print(f"File: {r.filepath}\nGate: {'PASS' if r.gate_passed else 'FAIL'}\nRec: {r.recommendation} ({r.confidence}%)")

        elif args.cmd == "execute":
            p = Path(args.analysis_file)
            if not p.exists(): print(f"Not found: {p}"); sys.exit(1)
            r = run_execution(db, p); print(f"Order: {r.order_placed} | {r.reason}")

        elif args.cmd == "pipeline":
            run_pipeline(db, args.ticker.upper(), AnalysisType(args.type), auto_execute=not args.no_execute)

        elif args.cmd == "watchlist":
            run_watchlist(db, args.auto_execute)

        elif args.cmd == "scan":
            run_scanners(db, args.scanner)

        elif args.cmd == "run-due":
            run_due_schedules(db)

        elif args.cmd == "review":
            run_analysis(db, "PORTFOLIO", AnalysisType.REVIEW)

        elif args.cmd == "earnings-check":
            run_earnings_check(db)

        elif args.cmd == "status":
            show_status(db)

        elif args.cmd == "health":
            _check_all_health()

        elif args.cmd == "stock":
            if args.action == "list":
                print(f"\n{'Ticker':<8} {'State':<10} {'Pri':<4} {'Earnings':<12} {'Tags'}")
                print("─"*60)
                for s in db.get_enabled_stocks():
                    tags = ','.join(s.tags[:3]) if s.tags else ''
                    earn = str(s.next_earnings_date) if s.next_earnings_date else '—'
                    print(f"{s.ticker:<8} {s.state:<10} {s.priority:<4} {earn:<12} {tags}")
            elif args.action == "add" and args.ticker:
                kw = {}
                if args.state: kw['state'] = args.state
                if args.tags: kw['tags'] = args.tags
                if args.priority: kw['priority'] = args.priority
                if args.comment: kw['comments'] = args.comment
                if args.earnings_date: kw['next_earnings_date'] = args.earnings_date
                s = db.upsert_stock(args.ticker.upper(), **kw)
                print(f"✅ {s.ticker if s else args.ticker.upper()}")
            elif args.action in ("enable","disable") and args.ticker:
                db.upsert_stock(args.ticker.upper(), is_enabled=(args.action=="enable"))
                print(f"✅ {args.ticker.upper()} {'enabled' if args.action=='enable' else 'disabled'}")
            elif args.action == "set-state" and args.ticker and args.state:
                db.upsert_stock(args.ticker.upper(), state=args.state)
                print(f"✅ {args.ticker.upper()} → {args.state}")

        elif args.cmd == "settings":
            if args.action == "list":
                all_settings = db.get_all_settings()
                cat = args.category
                print(f"\n{'Key':<35} {'Value':<25}")
                print("─"*60)
                for k, v in sorted(all_settings.items()):
                    print(f"{k:<35} {str(v):<25}")
            elif args.action == "get" and args.key:
                val = db.get_setting(args.key)
                if val is not None:
                    print(f"{args.key} = {val}")
                else:
                    print(f"Setting '{args.key}' not found")
            elif args.action == "set" and args.key and args.value:
                # Try to parse as JSON, fall back to string
                import json as _json
                try:
                    parsed_val = _json.loads(args.value)
                except _json.JSONDecodeError:
                    parsed_val = args.value
                db.set_setting(args.key, parsed_val)
                print(f"✅ {args.key} = {parsed_val}")
                print("  (takes effect on next service tick)")

        # ─── Graph Commands ───────────────────────────────────────────────────────────
        elif args.cmd == "graph":
            _handle_graph_command(args)

        # ─── RAG Commands ─────────────────────────────────────────────────────────────
        elif args.cmd == "rag":
            _handle_rag_command(args)

        else:
            parser.print_help()


if __name__ == "__main__":
    main()
