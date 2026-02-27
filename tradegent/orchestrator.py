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

import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

# Load .env file before any database connections
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

from db_layer import IBScanner, NexusDB, Schedule, Stock

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

# ─── Observability (OpenTelemetry) ────────────────────────────────────────────
# Initialize tracing with GenAI semantic conventions
# See: docs/observability/ for full documentation

try:
    from observability import (
        init_tracing,
        LLMSpan,
        PipelineSpan,
        ToolCallSpan,
        GenAISystem,
        FinishReason,
        TradegentMetrics,
    )

    # Initialize tracing (reads OTEL_* env vars)
    init_tracing()
    _otel_metrics = TradegentMetrics()
    _otel_enabled = True
    log.info("OpenTelemetry tracing initialized")
except ImportError:
    _otel_enabled = False
    _otel_metrics = None
    log.debug("Observability module not available, tracing disabled")


class Settings:
    """
    Hot-reloadable settings from PostgreSQL.
    Call refresh() to pull latest values — no restart required.
    Falls back to env vars → hardcoded defaults if DB unavailable.
    """

    def __init__(self, db: Optional["NexusDB"] = None):
        self._cache: dict = {}
        self._last_refresh: datetime | None = None
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

    def _get(self, key: str, env_key: str | None = None, default: Any = None) -> Any:
        """Get setting: DB cache → env var → default."""
        # DB cache first
        if key in self._cache:
            return self._cache[key]
        # Env var fallback
        if env_key and os.getenv(env_key):
            return os.getenv(env_key)
        return default

    def _get_bool(self, key: str, env_key: str | None = None, default: bool = False) -> bool:
        """Get a boolean setting with safe coercion (handles string 'false')."""
        val = self._get(key, env_key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    # ─── Accessors ───────────────────────────────────────────────────

    @property
    def claude_cmd(self) -> str:
        return self._get("claude_cmd", "CLAUDE_CMD", "claude")

    @property
    def claude_timeout(self) -> int:
        return int(self._get("claude_timeout_seconds", "CLAUDE_TIMEOUT", 600))

    @property
    def allowed_tools_analysis(self) -> str:
        return self._get(
            "allowed_tools_analysis",
            None,
            "mcp__ib-mcp__*,WebSearch,mcp__brave-search__*,mcp__trading-rag__*,mcp__trading-graph__*",
        )

    @property
    def allowed_tools_execution(self) -> str:
        return self._get(
            "allowed_tools_execution",
            None,
            "mcp__ib-mcp__*,mcp__trading-rag__*,mcp__trading-graph__*",
        )

    @property
    def allowed_tools_scanner(self) -> str:
        return self._get("allowed_tools_scanner", None, "mcp__ib-mcp__*")

    @property
    def ib_account(self) -> str:
        return self._get("ib_account", "IB_ACCOUNT", "DU_PAPER")

    @property
    def kb_ingest_enabled(self) -> bool:
        """Enable ingestion to RAG (pgvector) and Graph (Neo4j) after analysis."""
        return self._get_bool("kb_ingest_enabled", None, True)

    @property
    def max_daily_analyses(self) -> int:
        return int(self._get("max_daily_analyses", "MAX_DAILY_ANALYSES", 15))

    @property
    def max_daily_executions(self) -> int:
        return int(self._get("max_daily_executions", "MAX_DAILY_EXECUTIONS", 5))

    @property
    def max_concurrent_runs(self) -> int:
        return int(self._get("max_concurrent_runs", None, 2))

    @property
    def auto_execute_enabled(self) -> bool:
        return self._get_bool("auto_execute_enabled", None, False)

    @property
    def scanners_enabled(self) -> bool:
        return self._get_bool("scanners_enabled", None, True)

    @property
    def kb_query_enabled(self) -> bool:
        """Enable RAG+Graph context injection during analysis."""
        return self._get_bool("kb_query_enabled", None, True)

    @property
    def dry_run_mode(self) -> bool:
        return self._get_bool("dry_run_mode", None, True)

    @property
    def four_phase_analysis_enabled(self) -> bool:
        """Enable 4-phase workflow: fresh → index → retrieve → synthesize."""
        return self._get_bool("four_phase_analysis_enabled", None, True)

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

    @property
    def scheduler_poll_seconds(self) -> int:
        return int(self._get("scheduler_poll_seconds", None, 60))

    @property
    def earnings_check_hours(self) -> list[int]:
        val = self._get("earnings_check_hours", None, [6, 7])
        return val if isinstance(val, list) else [6, 7]

    @property
    def earnings_lookback_days(self) -> int:
        return int(self._get("earnings_lookback_days", None, 21))

    @property
    def analyses_dir(self) -> Path:
        return BASE_DIR / self._get("analyses_dir", None, "analyses")

    @property
    def trades_dir(self) -> Path:
        return BASE_DIR / self._get("trades_dir", None, "trades")

    @property
    def logs_dir(self) -> Path:
        return BASE_DIR / self._get("logs_dir", None, "logs")

    @property
    def git_push_enabled(self) -> bool:
        """Enable automatic git push after saving analysis files."""
        return self._get_bool("git_push_enabled", None, True)

    @property
    def knowledge_repo_path(self) -> Path:
        """Path to the tradegent_knowledge repo."""
        return Path(self._get("knowledge_repo_path", None, "/opt/data/tradegent_swarm/tradegent_knowledge"))

    @property
    def auto_viz_enabled(self) -> bool:
        """Auto-generate SVG visualization after analysis."""
        return self._get_bool("auto_viz_enabled", None, True)

    @property
    def auto_watchlist_chain(self) -> bool:
        """Auto-add WATCH recommendations to watchlist."""
        return self._get_bool("auto_watchlist_chain", None, True)

    @property
    def scanner_auto_route(self) -> bool:
        """Auto-route scanner results to analysis/watchlist."""
        return self._get_bool("scanner_auto_route", None, True)

    @property
    def task_queue_enabled(self) -> bool:
        """Enable async task queue processing."""
        return self._get_bool("task_queue_enabled", None, True)


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
    parsed_json: dict | None = None


@dataclass
class SynthesisContext:
    """Historical context for Phase 4 synthesis."""
    ticker: str
    past_analyses: list[dict]      # From RAG semantic search (enriched)
    graph_context: dict            # From TradingGraph.get_ticker_context()
    bias_warnings: list[dict]      # From get_bias_warnings()
    strategy_recommendations: list[dict]  # From get_strategy_recommendations()
    has_history: bool = False      # True if any past analyses found
    history_count: int = 0         # Number of past analyses
    has_graph_data: bool = False   # True if graph context populated

    @property
    def is_first_analysis(self) -> bool:
        """True if this is the first analysis for this ticker."""
        return not self.has_history and not self.has_graph_data


# Confidence adjustment rules for Phase 4 synthesis
CONFIDENCE_MODIFIERS = {
    "no_history": -10,             # No past analyses: reduce 10%
    "sparse_history": -5,          # Only 1-2 past analyses: reduce 5%
    "no_graph_context": -5,        # No graph data: reduce 5%
    "bias_warning_each": -3,       # Per bias warning: reduce 3%
    "bias_warning_max": -15,       # Max penalty for biases
    "pattern_confirms": +5,        # Current aligns with history: add 5%
    "pattern_contradicts": -10,    # Current contradicts history: reduce 10%
}


@dataclass
class ExecutionResult:
    analysis_path: Path
    order_placed: bool
    order_details: dict | None = None
    reason: str = ""
    filepath: Path | None = None
    raw_output: str = ""


# ─── Prompt Builders ─────────────────────────────────────────────────────────


def build_analysis_prompt(
    ticker: str, analysis_type: AnalysisType, stock: Stock | None = None, kb_enabled: bool = True
) -> str:
    """Build Stage 1 prompt, enriched with stock metadata from DB and KB context."""

    stock_ctx = ""
    if stock:
        stock_ctx = f"""
STOCK CONTEXT (from database):
- Ticker: {stock.ticker} ({stock.name or "N/A"})
- Sector: {stock.sector or "N/A"}
- State: {stock.state} | Priority: {stock.priority}/10
- Earnings: {stock.next_earnings_date or "Unknown"} ({"confirmed" if stock.earnings_confirmed else "unconfirmed"})
- Beat History: {stock.beat_history or "Unknown"}
- Open Position: {stock.has_open_position} ({stock.position_state or "none"})
- Max Position Size: {stock.max_position_pct}%
- Tags: {", ".join(stock.tags) if stock.tags else "none"}
- Notes: {stock.comments or "none"}
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
        return """You are a systematic portfolio manager performing a comprehensive review.

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


def build_execution_prompt(
    analysis_path: Path, analysis_content: str, stock: Stock | None = None
) -> str:
    """Build Stage 2 prompt for trade execution."""

    ticker = analysis_path.stem.split("_")[0]
    stock_ctx = ""
    if stock:
        state_map = {
            "analysis": "\n⚠️ CRITICAL: Stock in ANALYSIS state — DO NOT PLACE ORDERS. Log recommendation only.",
            "paper": f"\n✅ Stock in PAPER state — place orders on paper account {cfg.ib_account}.",
            "live": "\n🔴 Stock in LIVE state — requires additional confirmation. DO NOT auto-execute.",
        }
        stock_ctx = f"""
STOCK STATE FROM DATABASE:
- State: {stock.state}{state_map.get(stock.state, "")}
- Max Position: {stock.max_position_pct}%
- Open Position: {stock.has_open_position} ({stock.position_state or "none"})
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
    "stock_state": "{stock.state if stock else "unknown"}",
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


# ─── Git Push ────────────────────────────────────────────────────────────────


def git_push_analysis(filepath: Path, commit_message: str | None = None) -> bool:
    """
    Push analysis file to GitHub repository.

    Args:
        filepath: Path to the analysis file (should be in tradegent_knowledge)
        commit_message: Optional custom commit message

    Returns:
        True if push succeeded, False otherwise
    """
    if not cfg.git_push_enabled:
        log.debug("Git push disabled (git_push_enabled=false)")
        return False

    # Only push files in the knowledge repo
    try:
        rel_path = filepath.relative_to(cfg.knowledge_repo_path)
    except ValueError:
        log.debug(f"File not in knowledge repo, skipping git push: {filepath}")
        return False

    repo_path = cfg.knowledge_repo_path

    if not commit_message:
        # Generate commit message from filename
        filename = filepath.stem
        commit_message = f"Add analysis: {filename}"

    try:
        # Git add
        result = subprocess.run(
            ["git", "add", str(rel_path)],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log.warning(f"Git add failed: {result.stderr}")
            return False

        # Git commit
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                log.debug("Nothing to commit (file unchanged)")
                return True
            log.warning(f"Git commit failed: {result.stderr}")
            return False

        # Git push with SSH fix for conda environment
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = "LD_LIBRARY_PATH= /usr/bin/ssh"

        result = subprocess.run(
            ["git", "push"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if result.returncode != 0:
            log.warning(f"Git push failed: {result.stderr}")
            return False

        log.info(f"  ✓ Pushed to GitHub: {rel_path}")
        return True

    except subprocess.TimeoutExpired:
        log.warning("Git operation timed out")
        return False
    except Exception as e:
        log.warning(f"Git push error: {e}")
        return False


# ─── Core Functions ──────────────────────────────────────────────────────────


def call_claude_code(
    prompt: str,
    allowed_tools: str,
    label: str,
    timeout: int | None = None,
    phase: int | None = None,
    phase_name: str | None = None,
    analysis_type: str | None = None,
) -> str:
    """
    Execute a Claude Code CLI call with OpenTelemetry tracing.

    Traces include GenAI semantic conventions for LLM observability.
    """
    timeout = timeout or cfg.claude_timeout

    # Extract ticker from label (e.g., "ANALYZE-NVDA" -> "NVDA")
    ticker = label.split("-")[1] if "-" in label else "UNKNOWN"

    if cfg.dry_run_mode:
        log.info(f"[{label}] DRY RUN — would call Claude Code ({len(prompt)} char prompt)")
        return ""

    # Create LLM span if observability is enabled
    if _otel_enabled:
        return _call_claude_code_traced(
            prompt, allowed_tools, label, timeout, ticker, phase, phase_name, analysis_type
        )
    else:
        return _call_claude_code_untraced(prompt, allowed_tools, label, timeout)


def _call_claude_code_traced(
    prompt: str,
    allowed_tools: str,
    label: str,
    timeout: int,
    ticker: str,
    phase: int | None,
    phase_name: str | None,
    analysis_type: str | None,
) -> str:
    """Execute Claude Code call with OpenTelemetry tracing."""
    with LLMSpan(
        operation="chat",
        system=GenAISystem.CLAUDE_CODE,
        model="claude-sonnet-4-20250514",
        ticker=ticker,
        analysis_type=analysis_type,
        phase=phase,
        phase_name=phase_name,
        allowed_tools=allowed_tools,
    ) as span:
        log.info(f"[{label}] Calling Claude Code...")

        cmd = [
            cfg.claude_cmd,
            "--print",
            "--dangerously-skip-permissions",
            "--allowedTools",
            allowed_tools,
            "-p",
            prompt,
        ]
        span.set_subprocess_cmd(cmd)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(BASE_DIR),
            )

            if result.returncode != 0:
                log.error(f"[{label}] Error (rc={result.returncode}): {result.stderr[:500]}")
                span.set_finish_reason(FinishReason.ERROR)
                return ""

            # Record metrics
            span.set_output_length(len(result.stdout))
            span.set_finish_reason(FinishReason.STOP)

            # Record to Prometheus metrics
            if _otel_metrics and phase is not None:
                _otel_metrics.record_llm_call(
                    duration_ms=span.metrics.duration_ms,
                    input_tokens=span.metrics.input_tokens,
                    output_tokens=span.metrics.output_tokens,
                    ticker=ticker,
                    analysis_type=analysis_type or "unknown",
                    phase=phase,
                )

            log.info(f"[{label}] Completed ({len(result.stdout)} chars)")
            return result.stdout

        except subprocess.TimeoutExpired:
            log.error(f"[{label}] Timed out after {timeout}s")
            span.set_finish_reason(FinishReason.ERROR)
            return ""

        except FileNotFoundError:
            log.error(f"[{label}] 'claude' CLI not found in PATH")
            span.set_finish_reason(FinishReason.ERROR)
            return ""


def _call_claude_code_untraced(
    prompt: str, allowed_tools: str, label: str, timeout: int
) -> str:
    """Execute Claude Code call without tracing (fallback)."""
    log.info(f"[{label}] Calling Claude Code...")
    try:
        result = subprocess.run(
            [
                cfg.claude_cmd,
                "--print",
                "--dangerously-skip-permissions",
                "--allowedTools",
                allowed_tools,
                "-p",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(BASE_DIR),
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


def parse_json_block(text: str) -> dict | None:
    """Extract the last JSON block from output."""
    # Try fenced JSON blocks first
    pattern = r"```json\s*\n(.*?)\n\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if not matches:
        # Fallback: find balanced braces containing "ticker"
        # Handles nested objects like {"candidates": [{...}]}
        for i in range(len(text) - 1, -1, -1):
            if text[i] == "}":
                depth = 0
                for j in range(i, -1, -1):
                    if text[j] == "}":
                        depth += 1
                    elif text[j] == "{":
                        depth -= 1
                    if depth == 0:
                        candidate = text[j : i + 1]
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


# ─── 4-Phase Workflow Functions ───────────────────────────────────────────────


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
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

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


def _phase1_fresh_analysis(
    db: "NexusDB",
    ticker: str,
    analysis_type: AnalysisType,
    schedule_id: int | None = None,
) -> AnalysisResult | None:
    """
    Phase 1: Run analysis WITHOUT historical context injection.

    This produces an unbiased analysis that can be compared to history.
    """
    timestamp = datetime.now().strftime("%Y%m%dT%H%M")
    filepath = cfg.analyses_dir / f"{ticker}_{analysis_type.value}_{timestamp}.md"
    stock = db.get_stock(ticker) if ticker != "PORTFOLIO" else None

    log.info(f"[P1] Fresh analysis for {ticker} (kb_enabled=False)")

    # KEY CHANGE: kb_enabled=False for unbiased analysis
    prompt = build_analysis_prompt(ticker, analysis_type, stock, kb_enabled=False)
    output = call_claude_code(
        prompt,
        cfg.allowed_tools_analysis,
        f"ANALYZE-{ticker}",
        phase=1,
        phase_name="Fresh_analysis",
        analysis_type=analysis_type.value,
    )

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


def _phase2_dual_ingest(filepath: Path) -> dict:
    """
    Phase 2: Index to BOTH Graph (Neo4j) AND RAG (pgvector).

    This is the fix for the current kb_ingest_analysis() which only calls RAG.
    Handles both YAML files (from tradegent_knowledge/knowledge/) and Markdown files (from analyses/).
    """
    results = {"graph": None, "rag": None, "doc_id": None, "errors": []}

    if not cfg.kb_ingest_enabled:
        log.debug("[P2] KB ingest disabled, skipping")
        return results

    log.info(f"[P2] Dual ingest: {filepath.name}")

    # Determine file type and extract info
    is_markdown = filepath.suffix.lower() in (".md", ".markdown")
    doc_id = filepath.stem  # e.g., "AAPL_stock_20260220T1754"

    # Extract ticker from filename (assumes TICKER_type_timestamp format)
    ticker = None
    parts = doc_id.split("_")
    if parts:
        ticker = parts[0].upper()

    # Determine doc_type from filename
    doc_type = "analysis"
    if len(parts) >= 2:
        doc_type = parts[1]  # e.g., "stock" or "earnings"

    if is_markdown:
        # Read Markdown content for text-based embedding
        try:
            content = filepath.read_text()
        except Exception as e:
            results["errors"].append(f"Read: {e}")
            log.warning(f"[P2] Failed to read file: {e}")
            return results

        # RAG embedding using embed_text for Markdown
        try:
            from rag.embed import embed_text

            result = embed_text(
                text=content,
                doc_id=doc_id,
                doc_type=doc_type,
                ticker=ticker,
            )
            results["rag"] = {"chunks": result.chunk_count}
            results["doc_id"] = result.doc_id
            log.info(f"[P2] RAG embedded (text): {result.chunk_count} chunks")
        except ImportError:
            results["errors"].append("RAG: module not available")
            log.warning("[P2] RAG module not available")
        except Exception as e:
            results["errors"].append(f"RAG: {e}")
            log.warning(f"[P2] RAG embedding failed: {e}")

        # Graph extraction using extract_text for Markdown
        try:
            from graph.extract import extract_text

            result = extract_text(
                text=content,
                doc_type=doc_type,
                doc_id=doc_id,
            )
            results["graph"] = {
                "entities": len(result.entities),
                "relations": len(result.relations),
            }
            log.info(f"[P2] Graph indexed (text): {len(result.entities)} entities, {len(result.relations)} relations")
        except ImportError:
            results["errors"].append("Graph: module not available")
            log.warning("[P2] Graph module not available")
        except Exception as e:
            results["errors"].append(f"Graph: {e}")
            log.warning(f"[P2] Graph extraction failed: {e}")
    else:
        # YAML files use document-based functions
        # RAG embedding (do first to get doc_id)
        try:
            from rag.embed import embed_document

            result = embed_document(str(filepath))
            results["rag"] = {"chunks": result.chunk_count}
            results["doc_id"] = result.doc_id
            log.info(f"[P2] RAG embedded: {result.chunk_count} chunks")
        except ImportError:
            results["errors"].append("RAG: module not available")
            log.warning("[P2] RAG module not available")
        except Exception as e:
            results["errors"].append(f"RAG: {e}")
            log.warning(f"[P2] RAG embedding failed: {e}")

        # Graph extraction
        try:
            from graph.extract import extract_document

            result = extract_document(str(filepath), commit=True)
            results["graph"] = {
                "entities": len(result.entities),
                "relations": len(result.relations),
            }
            log.info(f"[P2] Graph indexed: {len(result.entities)} entities, {len(result.relations)} relations")
        except ImportError:
            results["errors"].append("Graph: module not available")
            log.warning("[P2] Graph module not available")
        except Exception as e:
            results["errors"].append(f"Graph: {e}")
            log.warning(f"[P2] Graph extraction failed: {e}")

    # Push any pending changes to GitHub
    if cfg.git_push_enabled:
        git_push_knowledge_repo()

    return results


def git_push_knowledge_repo(commit_message: str | None = None) -> bool:
    """
    Push all pending changes in the knowledge repo to GitHub.

    This handles YAML files saved by Claude Code skills.
    """
    if not cfg.git_push_enabled:
        return False

    repo_path = cfg.knowledge_repo_path
    if not repo_path.exists():
        log.debug(f"Knowledge repo not found: {repo_path}")
        return False

    try:
        # Check for changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if not result.stdout.strip():
            log.debug("[Git] No changes to push")
            return True

        # Count changes
        changes = [l for l in result.stdout.strip().split("\n") if l.strip()]
        log.info(f"[Git] {len(changes)} file(s) to push")

        # Git add all changes
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            log.warning(f"[Git] Add failed: {result.stderr}")
            return False

        # Generate commit message
        if not commit_message:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            commit_message = f"Auto-commit analyses ({ts})"

        # Git commit
        result = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                return True
            log.warning(f"[Git] Commit failed: {result.stderr}")
            return False

        # Git push with SSH fix
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = "LD_LIBRARY_PATH= /usr/bin/ssh"

        result = subprocess.run(
            ["git", "push"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if result.returncode != 0:
            log.warning(f"[Git] Push failed: {result.stderr}")
            return False

        log.info(f"  ✓ Pushed {len(changes)} file(s) to GitHub")
        return True

    except subprocess.TimeoutExpired:
        log.warning("[Git] Operation timed out")
        return False
    except Exception as e:
        log.warning(f"[Git] Error: {e}")
        return False


def _enrich_past_analyses(vector_results: list, db: "NexusDB") -> list[dict]:
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

        # Try to get recommendation/confidence from analysis_results
        try:
            with db.conn.cursor() as cur:
                # Query by ticker and date pattern
                cur.execute(
                    """
                    SELECT recommendation, confidence
                    FROM nexus.analysis_results
                    WHERE ticker = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (result.ticker,),
                )
                row = cur.fetchone()
                if row:
                    base["recommendation"] = row["recommendation"]
                    base["confidence"] = row["confidence"]
                else:
                    base["recommendation"] = "N/A"
                    base["confidence"] = "N/A"
        except Exception:
            base["recommendation"] = "N/A"
            base["confidence"] = "N/A"

        enriched.append(base)

    return enriched


def _phase3_retrieve_history(
    ticker: str,
    analysis_type: AnalysisType,
    current_doc_id: str | None = None,
    db: "NexusDB | None" = None,
) -> SynthesisContext:
    """
    Phase 3: Retrieve historical context AFTER indexing current analysis.

    This ensures we don't bias the fresh analysis but still have history for synthesis.
    """
    log.info(f"[P3] Retrieving history for {ticker} (exclude={current_doc_id})")

    try:
        from rag.hybrid import get_hybrid_context, get_bias_warnings, get_strategy_recommendations

        hybrid = get_hybrid_context(
            ticker=ticker,
            query=f"{analysis_type.value} analysis historical patterns",
            analysis_type=analysis_type.value,
            exclude_doc_id=current_doc_id,  # Exclude just-indexed document
        )

        # Filter out current analysis (belt and suspenders)
        filtered_results = [
            r for r in hybrid.vector_results
            if r.doc_id != current_doc_id
        ]

        # Enrich with recommendation/confidence from database
        if db:
            past_analyses = _enrich_past_analyses(filtered_results, db)
        else:
            past_analyses = [r.to_dict() for r in filtered_results]

        # Get bias warnings
        bias_warnings = get_bias_warnings(ticker)

        # Get strategy recommendations
        strategy_recs = get_strategy_recommendations(ticker)

        # Determine history availability
        has_history = len(past_analyses) > 0
        has_graph = bool(
            hybrid.graph_context
            and hybrid.graph_context.get("_status") != "empty"
            and (hybrid.graph_context.get("peers") or hybrid.graph_context.get("risks"))
        )

        log.info(f"[P3] Found {len(past_analyses)} past analyses, graph={has_graph}")

        return SynthesisContext(
            ticker=ticker,
            past_analyses=past_analyses,
            graph_context=hybrid.graph_context,
            bias_warnings=bias_warnings,
            strategy_recommendations=strategy_recs,
            has_history=has_history,
            history_count=len(past_analyses),
            has_graph_data=has_graph,
        )

    except ImportError:
        log.warning("[P3] RAG/Graph modules not available")
        return SynthesisContext(
            ticker=ticker,
            past_analyses=[],
            graph_context={},
            bias_warnings=[],
            strategy_recommendations=[],
            has_history=False,
            history_count=0,
            has_graph_data=False,
        )
    except Exception as e:
        log.warning(f"[P3] Failed to retrieve history: {e}")
        return SynthesisContext(
            ticker=ticker,
            past_analyses=[],
            graph_context={},
            bias_warnings=[],
            strategy_recommendations=[],
            has_history=False,
            history_count=0,
            has_graph_data=False,
        )


def _check_pattern_consistency(current_rec: str, past_analyses: list[dict]) -> str:
    """
    Check if current recommendation aligns with historical patterns.

    Returns: "confirms", "contradicts", or "neutral"
    """
    from collections import Counter

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
    if not hist_sentiments:
        return "neutral"

    sentiment_counts = Counter(hist_sentiments)
    majority_sentiment = sentiment_counts.most_common(1)[0][0]

    if current_sentiment == majority_sentiment:
        return "confirms"
    elif current_sentiment != "neutral" and majority_sentiment != "neutral":
        # Both have direction but different
        return "contradicts"
    else:
        return "neutral"


def _calculate_adjusted_confidence(
    original_confidence: int,
    current_recommendation: str | None,
    historical: SynthesisContext,
) -> tuple[int, dict]:
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
        total_occurrences = sum(b.get("occurrences", 1) for b in historical.bias_warnings)
        bias_penalty = min(
            total_occurrences * CONFIDENCE_MODIFIERS["bias_warning_each"],
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


def _get_pattern_description(modifiers: dict, historical: SynthesisContext) -> str:
    """Generate description of pattern alignment."""
    if historical.is_first_analysis:
        return "First analysis - establishing baseline"
    elif "pattern_confirms" in modifiers:
        return "Confirms recent historical sentiment"
    elif "pattern_contradicts" in modifiers:
        return "Contradicts recent historical sentiment"
    else:
        return "No clear pattern from history"


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
        "",
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
        ])
        if not historical.has_graph_data:
            lines.append("*No graph context available yet.*")
        lines.append("")
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
                date_val = analysis.get("date", "N/A")
                rec = analysis.get("recommendation", "N/A")
                conf = analysis.get("confidence", "N/A")
                conf_str = f"{conf}%" if isinstance(conf, (int, float)) else str(conf)
                lines.append(f"| {date_val} | {rec} | {conf_str} |")
            lines.append("")

        # Bias warnings
        if historical.bias_warnings:
            lines.extend([
                "### Bias Warnings",
                "",
            ])
            for bias in historical.bias_warnings:
                count = bias.get("occurrences", 1)
                penalty = count * CONFIDENCE_MODIFIERS["bias_warning_each"]
                bias_name = bias.get("bias", "Unknown")
                lines.append(f"- **{bias_name}**: {count} occurrences ({penalty}%)")
            lines.append("")

        # Strategy recommendations
        if historical.strategy_recommendations:
            lines.extend([
                "### Historical Strategy Performance",
                "",
            ])
            for strat in historical.strategy_recommendations[:3]:
                name = strat.get("strategy", "Unknown")
                win_rate = strat.get("win_rate", 0)
                trades = strat.get("trades", 0)
                lines.append(f"- **{name}**: {win_rate:.0%} win rate ({trades} trades)")
            lines.append("")

        # Sector peers from graph
        if historical.graph_context and historical.graph_context.get("peers"):
            peers = [p.get("peer", "") for p in historical.graph_context["peers"][:6] if p.get("peer")]
            if peers:
                lines.extend([
                    "### Sector Peers",
                    "",
                    ", ".join(peers),
                    "",
                ])

        # Known risks from graph
        if historical.graph_context and historical.graph_context.get("risks"):
            risks = [r.get("risk", "") for r in historical.graph_context["risks"][:4] if r.get("risk")]
            if risks:
                lines.extend([
                    "### Known Risks",
                    "",
                    ", ".join(risks),
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
        factor_display = factor.replace("_", " ").title()
        lines.append(f"| {factor_display} | {sign}{adjustment}% |")

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


def _phase4_synthesize(
    result: AnalysisResult,
    historical: SynthesisContext,
    db: "NexusDB | None" = None,
    run_id: int | None = None,
) -> None:
    """
    Phase 4: Compare current analysis with historical context, adjust confidence, append synthesis.
    """
    current_metrics = result.parsed_json or {}
    original_confidence = current_metrics.get("confidence", 0)
    current_recommendation = current_metrics.get("recommendation")

    log.info(f"[P4] Synthesizing {result.ticker}: original confidence={original_confidence}%")

    # Calculate adjusted confidence based on historical context
    adjusted_confidence, modifiers_applied = _calculate_adjusted_confidence(
        original_confidence=original_confidence,
        current_recommendation=current_recommendation,
        historical=historical,
    )

    # Update result object with adjusted values
    result.confidence = adjusted_confidence
    if result.parsed_json:
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
    result.filepath.write_text(existing_content + synthesis)

    # Update database with adjusted confidence (if run_id exists)
    if db and run_id:
        try:
            _update_analysis_confidence(db, run_id, adjusted_confidence, modifiers_applied)
        except Exception as e:
            log.warning(f"[P4] Failed to update DB with adjusted confidence: {e}")

    log.info(
        f"[P4] Synthesis complete: {result.ticker} confidence {original_confidence}% → {adjusted_confidence}% "
        f"(modifiers: {list(modifiers_applied.keys())})"
    )


def _update_analysis_confidence(
    db: "NexusDB",
    run_id: int,
    adjusted_confidence: int,
    modifiers: dict,
) -> bool:
    """
    Update analysis_results with adjusted confidence from Phase 4 synthesis.

    Args:
        db: Database connection
        run_id: Analysis run ID
        adjusted_confidence: Confidence after historical comparison
        modifiers: Dict of factors that affected confidence

    Returns:
        True if updated successfully
    """
    try:
        with db.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.analysis_results
                SET adjusted_confidence = %s,
                    confidence_modifiers = %s
                WHERE run_id = %s
                """,
                (adjusted_confidence, json.dumps(modifiers), run_id),
            )
        db.conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        log.warning(f"Failed to update analysis confidence: {e}")
        return False


# ─── Workflow Automation ────────────────────────────────────────────────────


@dataclass
class AnalysisChainData:
    """Data extracted from analysis for workflow chaining."""
    ticker: str
    recommendation: str
    confidence: int
    expected_value: float
    entry_price: float | None
    stop_price: float | None
    invalidation: str | None
    gate_result: str
    file_path: str


def extract_chain_data(analysis_path: Path) -> AnalysisChainData | None:
    """Extract chaining data from analysis YAML."""
    import yaml

    try:
        with open(analysis_path, 'r') as f:
            content = f.read()

        # Try to parse as YAML (our new format)
        if content.startswith('_meta:') or content.startswith('ticker:'):
            data = yaml.safe_load(content)
        else:
            # Try to extract JSON block from markdown
            parsed = parse_json_block(content)
            if not parsed:
                log.debug(f"No JSON block found in {analysis_path}")
                return None
            data = parsed

        # Extract recommendation
        recommendation = data.get('recommendation', 'NEUTRAL')

        # Extract confidence
        conf_obj = data.get('confidence', {})
        if isinstance(conf_obj, dict):
            confidence = conf_obj.get('level', 50)
        else:
            confidence = conf_obj if isinstance(conf_obj, int) else 50

        # Extract gate
        gate = data.get('do_nothing_gate', {})
        gate_result = gate.get('gate_result', 'FAIL') if isinstance(gate, dict) else 'FAIL'

        # Extract trade plan
        trade_plan = data.get('trade_plan', {})
        if isinstance(trade_plan, dict):
            entry = trade_plan.get('entry', {})
            entry_price = entry.get('price') if isinstance(entry, dict) else None
            stop = trade_plan.get('stop_loss', {})
            stop_price = stop.get('price') if isinstance(stop, dict) else None
        else:
            entry_price = None
            stop_price = None

        # Extract falsification as invalidation
        falsification = data.get('falsification', {})
        if isinstance(falsification, dict):
            invalidation = falsification.get('thesis_invalid_if', '')
        else:
            invalidation = str(falsification) if falsification else ''

        # Extract expected value
        scenarios = data.get('scenarios', {})
        if isinstance(scenarios, dict):
            ev = scenarios.get('expected_value', 0)
            if isinstance(ev, dict):
                ev = ev.get('total', 0)
        else:
            ev = 0

        return AnalysisChainData(
            ticker=data.get('ticker', ''),
            recommendation=recommendation,
            confidence=confidence,
            expected_value=float(ev) if ev else 0.0,
            entry_price=float(entry_price) if entry_price else None,
            stop_price=float(stop_price) if stop_price else None,
            invalidation=invalidation[:200] if invalidation else None,
            gate_result=gate_result,
            file_path=str(analysis_path)
        )
    except Exception as e:
        log.warning(f"Failed to extract chain data from {analysis_path}: {e}")
        return None


def _generate_visualization(ticker: str, db: "NexusDB") -> str | None:
    """Generate SVG visualization after analysis completion."""
    if not cfg.auto_viz_enabled:
        return None

    script_path = BASE_DIR / "scripts" / "visualize_combined.py"
    if not script_path.exists():
        log.debug(f"Visualization script not found: {script_path}")
        return None

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), ticker, "--json"],
            capture_output=True,
            text=True,
            cwd=str(BASE_DIR),
            timeout=60  # 60 second timeout
        )

        if result.returncode == 0:
            try:
                output = json.loads(result.stdout)
                svg_path = output.get('svg_path')
                if svg_path:
                    log.info(f"  ✓ Generated visualization: {svg_path}")
                    return svg_path
            except json.JSONDecodeError:
                # Non-JSON output, check if SVG was mentioned
                if ".svg" in result.stdout:
                    log.info(f"  ✓ Visualization generated")
                    return result.stdout.strip()
        else:
            log.warning(f"  ⚠ Visualization failed: {result.stderr[:200]}")
            return None

    except subprocess.TimeoutExpired:
        log.error("  ✗ Visualization timed out after 60s")
        return None
    except Exception as e:
        log.error(f"  ✗ Visualization error: {e}")
        return None


def _chain_to_watchlist(
    db: "NexusDB",
    ticker: str,
    analysis_path: str,
    recommendation: str,
    entry_price: float | None = None,
    invalidation: str | None = None,
) -> bool:
    """Auto-chain to watchlist when recommendation is WATCH."""
    if not cfg.auto_watchlist_chain:
        return False

    if recommendation.upper() not in ("WATCH", "WATCHLIST"):
        return False

    # Check if already in watchlist
    existing = db.get_watchlist_entry(ticker)
    if existing:
        log.info(f"  → {ticker} already in watchlist (id={existing['id']})")
        return False

    from datetime import timedelta

    entry = {
        "ticker": ticker.upper(),
        "entry_trigger": f"Price at or below ${entry_price:.2f}" if entry_price else "See analysis",
        "entry_price": entry_price,
        "invalidation": invalidation or "Thesis broken - see analysis",
        "invalidation_price": None,
        "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
        "priority": "medium",
        "source": "analysis",
        "source_analysis": analysis_path,
        "notes": None,
    }

    entry_id = db.add_watchlist_entry(entry)
    log.info(f"  → Chained to watchlist: {ticker} (id={entry_id})")
    return True


def _chain_to_post_trade_review(db: "NexusDB", trade_id: int) -> bool:
    """Auto-trigger post-trade review when position is closed."""
    if not cfg.task_queue_enabled:
        return False

    trade = db.get_trade(trade_id)
    if not trade or trade["status"] != "closed":
        return False

    if trade.get("review_status") != "pending":
        return False  # Already reviewed or in progress

    ticker = trade["ticker"]

    # Include trade_id in prompt for extraction
    prompt = f"""Perform post-trade review for {ticker}.

trade_id: {trade_id}

Trade Details:
- Entry: ${trade['entry_price']:.2f} on {trade['entry_date']}
- Exit: ${trade['exit_price']:.2f} on {trade['exit_date']}
- P/L: {trade.get('pnl_pct', 0):+.1f}%
- Reason: {trade.get('exit_reason', 'N/A')}
- Original Analysis: {trade.get('source_analysis', 'N/A')}

Follow post-trade-review skill framework (SKILL.md).
Save review to: tradegent_knowledge/knowledge/reviews/{ticker}_{datetime.now().strftime('%Y%m%dT%H%M')}.yaml"""

    task_id = db.queue_task("post_trade_review", ticker, prompt, priority=7)
    log.info(f"  → Queued post-trade review: {ticker} (task {task_id})")
    return True


def _post_analysis_workflow(
    db: "NexusDB", ticker: str, analysis_path: Path, result: "AnalysisResult"
) -> None:
    """Run post-analysis workflow: visualization, chaining, etc."""
    if ticker in ("PORTFOLIO", "SCAN"):
        return  # Skip for non-stock analyses

    log.info(f"[POST] Running post-analysis workflow for {ticker}")

    # 1. Generate visualization
    svg_path = _generate_visualization(ticker, db)

    # 2. Extract chain data
    chain_data = extract_chain_data(analysis_path)
    if not chain_data:
        # Try to get data from parsed JSON
        if result.parsed_json:
            recommendation = result.recommendation
            entry_price = result.parsed_json.get("entry_price")
            invalidation = result.parsed_json.get("rationale_summary", "")
            gate_result = "PASS" if result.gate_passed else "FAIL"
        else:
            log.debug("Could not extract chain data, skipping workflow")
            return
    else:
        recommendation = chain_data.recommendation
        entry_price = chain_data.entry_price
        invalidation = chain_data.invalidation
        gate_result = chain_data.gate_result

    # 3. Chain to watchlist if WATCH recommendation
    if recommendation.upper() in ("WATCH", "WATCHLIST"):
        _chain_to_watchlist(
            db, ticker, str(analysis_path),
            recommendation,
            entry_price,
            invalidation
        )

    # 4. Log gate result
    if gate_result == "PASS":
        log.info(f"  ✓ Gate PASS: {ticker} ready for trade execution")
    else:
        ev = chain_data.expected_value if chain_data else result.expected_value
        log.info(f"  → Gate {gate_result}: {ticker} (EV: {ev:.1f}%)")


# ─── Stage 1: Analysis ──────────────────────────────────────────────────────


def run_analysis(
    db: NexusDB, ticker: str, analysis_type: AnalysisType, schedule_id: int | None = None
) -> AnalysisResult | None:
    """
    Stage 1: Generate analysis via Claude Code.

    Uses 4-phase workflow when four_phase_analysis_enabled=True:
        Phase 1: Fresh analysis (no KB context)
        Phase 2: Dual ingest (Graph + RAG)
        Phase 3: Retrieve historical context
        Phase 4: Synthesize (compare, adjust confidence, append)

    Otherwise uses legacy workflow (KB context before analysis).
    """
    if cfg.four_phase_analysis_enabled:
        return _run_analysis_4phase(db, ticker, analysis_type, schedule_id)
    else:
        return _legacy_run_analysis(db, ticker, analysis_type, schedule_id)


def _run_analysis_4phase(
    db: NexusDB, ticker: str, analysis_type: AnalysisType, schedule_id: int | None = None
) -> AnalysisResult | None:
    """
    4-Phase analysis workflow: Fresh → Index → Retrieve → Synthesize

    This workflow produces unbiased analysis then compares with history.
    Instrumented with OpenTelemetry PipelineSpan for trace visualization.
    """
    trace_id = f"{ticker}-{datetime.now().strftime('%H%M%S')}"
    run_id = db.mark_schedule_started(schedule_id) if schedule_id else None

    log.info(f"╔═══ 4-PHASE ANALYSIS ═══ {ticker} ({analysis_type.value}) [{trace_id}]")

    # Use PipelineSpan for tracing if observability is enabled
    if _otel_enabled:
        return _run_analysis_4phase_traced(
            db, ticker, analysis_type, schedule_id, trace_id, run_id
        )
    else:
        return _run_analysis_4phase_untraced(
            db, ticker, analysis_type, schedule_id, trace_id, run_id
        )


def _run_analysis_4phase_traced(
    db: NexusDB,
    ticker: str,
    analysis_type: AnalysisType,
    schedule_id: int | None,
    trace_id: str,
    run_id: int | None,
) -> AnalysisResult | None:
    """4-Phase workflow with OpenTelemetry tracing."""
    import time

    with PipelineSpan(
        ticker=ticker,
        analysis_type=analysis_type.value,
        run_id=trace_id,
    ) as pipeline:
        try:
            # Phase 1: Fresh analysis (no KB context)
            with pipeline.phase(1, "Fresh_analysis") as phase1_span:
                log.info(f"[{trace_id}] Phase 1: Fresh analysis")
                p1_start = time.perf_counter()
                result = _phase1_fresh_analysis(db, ticker, analysis_type, schedule_id)
                p1_duration = (time.perf_counter() - p1_start) * 1000

                if _otel_metrics:
                    _otel_metrics.record_phase(1, "Fresh_analysis", p1_duration, ticker)

                if not result:
                    if run_id and schedule_id:
                        db.mark_schedule_completed(
                            schedule_id, run_id, "failed", error="Phase 1 failed: empty output"
                        )
                    log.error(f"[{trace_id}] Phase 1 failed: empty output")
                    return None

            # Phase 2: Dual ingest (Graph + RAG) WITH TIMEOUT
            with pipeline.phase(2, "Dual_ingest") as phase2_span:
                log.info(f"[{trace_id}] Phase 2: Dual ingest")
                p2_start = time.perf_counter()
                ingest_result, p2_error = _run_with_timeout(
                    _phase2_dual_ingest,
                    cfg.phase2_timeout,
                    f"{trace_id}/P2",
                    result.filepath,
                )
                p2_duration = (time.perf_counter() - p2_start) * 1000

                if _otel_metrics:
                    _otel_metrics.record_phase(2, "Dual_ingest", p2_duration, ticker)

                if p2_error:
                    log.warning(f"[{trace_id}] Phase 2 failed: {p2_error}, continuing...")
                    ingest_result = {"doc_id": None, "errors": [p2_error]}

            # Phase 3: Retrieve history WITH TIMEOUT
            with pipeline.phase(3, "Retrieve_history") as phase3_span:
                log.info(f"[{trace_id}] Phase 3: Retrieve history")
                p3_start = time.perf_counter()
                historical_context, p3_error = _run_with_timeout(
                    _phase3_retrieve_history,
                    cfg.phase3_timeout,
                    f"{trace_id}/P3",
                    ticker,
                    analysis_type,
                    ingest_result.get("doc_id") if ingest_result else None,
                    db,
                )
                p3_duration = (time.perf_counter() - p3_start) * 1000

                if _otel_metrics:
                    _otel_metrics.record_phase(3, "Retrieve_history", p3_duration, ticker)

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
            with pipeline.phase(4, "Synthesize") as phase4_span:
                log.info(f"[{trace_id}] Phase 4: Synthesize")
                p4_start = time.perf_counter()
                _, p4_error = _run_with_timeout(
                    _phase4_synthesize,
                    cfg.phase4_timeout,
                    f"{trace_id}/P4",
                    result,
                    historical_context,
                    db,
                    run_id,
                )
                p4_duration = (time.perf_counter() - p4_start) * 1000

                if _otel_metrics:
                    _otel_metrics.record_phase(4, "Synthesize", p4_duration, ticker)

                if p4_error:
                    log.warning(f"[{trace_id}] Phase 4 failed: {p4_error}, skipping synthesis")

            # Set pipeline result for trace attributes
            pipeline.set_result(
                gate_passed=result.gate_passed,
                recommendation=result.recommendation,
                confidence=result.confidence,
            )

            # Record analysis metrics
            if _otel_metrics:
                _otel_metrics.record_analysis_result(
                    ticker=ticker,
                    analysis_type=analysis_type.value,
                    gate_passed=result.gate_passed,
                    recommendation=result.recommendation,
                    confidence=result.confidence,
                )

            # Persist to DB
            if run_id and schedule_id:
                db.mark_schedule_completed(
                    schedule_id,
                    run_id,
                    "completed",
                    gate_passed=result.gate_passed,
                    recommendation=result.recommendation,
                    confidence=result.confidence,
                    expected_value=result.expected_value,
                    analysis_file=str(result.filepath),
                )

            if result.parsed_json and ticker not in ("PORTFOLIO", "SCAN"):
                try:
                    db.save_analysis_result(run_id, ticker, analysis_type.value, result.parsed_json)
                except Exception as e:
                    log.warning(f"Save analysis result failed: {e}")

            # Increment service counters
            try:
                db.increment_service_counter("analyses_total")
                db.increment_service_counter("today_analyses")
            except Exception:
                pass

            # Post-analysis workflow (visualization, chaining)
            try:
                _post_analysis_workflow(db, ticker, result.filepath, result)
            except Exception as e:
                log.warning(f"[{trace_id}] Post-analysis workflow failed: {e}")

            log.info(
                f"╚═══ 4-PHASE COMPLETE ═══ {ticker} | Gate: {'PASS' if result.gate_passed else 'FAIL'} | "
                f"Rec: {result.recommendation} | Conf: {result.confidence}% [{trace_id}]"
            )
            return result

        except Exception as e:
            log.error(f"[{trace_id}] 4-phase workflow failed: {e}")
            if run_id and schedule_id:
                db.mark_schedule_completed(
                    schedule_id, run_id, "failed", error=str(e)
                )
            raise


def _run_analysis_4phase_untraced(
    db: NexusDB,
    ticker: str,
    analysis_type: AnalysisType,
    schedule_id: int | None,
    trace_id: str,
    run_id: int | None,
) -> AnalysisResult | None:
    """4-Phase workflow without tracing (fallback)."""
    try:
        # Phase 1: Fresh analysis (no KB context)
        log.info(f"[{trace_id}] Phase 1: Fresh analysis")
        result = _phase1_fresh_analysis(db, ticker, analysis_type, schedule_id)
        if not result:
            if run_id and schedule_id:
                db.mark_schedule_completed(
                    schedule_id, run_id, "failed", error="Phase 1 failed: empty output"
                )
            log.error(f"[{trace_id}] Phase 1 failed: empty output")
            return None

        # Phase 2: Dual ingest (Graph + RAG) WITH TIMEOUT
        log.info(f"[{trace_id}] Phase 2: Dual ingest")
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
        log.info(f"[{trace_id}] Phase 3: Retrieve history")
        historical_context, p3_error = _run_with_timeout(
            _phase3_retrieve_history,
            cfg.phase3_timeout,
            f"{trace_id}/P3",
            ticker,
            analysis_type,
            ingest_result.get("doc_id") if ingest_result else None,
            db,
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
        log.info(f"[{trace_id}] Phase 4: Synthesize")
        _, p4_error = _run_with_timeout(
            _phase4_synthesize,
            cfg.phase4_timeout,
            f"{trace_id}/P4",
            result,
            historical_context,
            db,
            run_id,
        )
        if p4_error:
            log.warning(f"[{trace_id}] Phase 4 failed: {p4_error}, skipping synthesis")

        # Persist to DB
        if run_id and schedule_id:
            db.mark_schedule_completed(
                schedule_id,
                run_id,
                "completed",
                gate_passed=result.gate_passed,
                recommendation=result.recommendation,
                confidence=result.confidence,
                expected_value=result.expected_value,
                analysis_file=str(result.filepath),
            )

        if result.parsed_json and ticker not in ("PORTFOLIO", "SCAN"):
            try:
                db.save_analysis_result(run_id, ticker, analysis_type.value, result.parsed_json)
            except Exception as e:
                log.warning(f"Save analysis result failed: {e}")

        # Increment service counters
        try:
            db.increment_service_counter("analyses_total")
            db.increment_service_counter("today_analyses")
        except Exception:
            pass

        # Post-analysis workflow (visualization, chaining)
        try:
            _post_analysis_workflow(db, ticker, result.filepath, result)
        except Exception as e:
            log.warning(f"[{trace_id}] Post-analysis workflow failed: {e}")

        log.info(
            f"╚═══ 4-PHASE COMPLETE ═══ {ticker} | Gate: {'PASS' if result.gate_passed else 'FAIL'} | "
            f"Rec: {result.recommendation} | Conf: {result.confidence}% [{trace_id}]"
        )
        return result

    except Exception as e:
        log.error(f"[{trace_id}] 4-phase workflow failed: {e}")
        if run_id and schedule_id:
            db.mark_schedule_completed(
                schedule_id, run_id, "failed", error=str(e)
            )
        raise


def _legacy_run_analysis(
    db: NexusDB, ticker: str, analysis_type: AnalysisType, schedule_id: int | None = None
) -> AnalysisResult | None:
    """
    Legacy analysis workflow (pre-4-phase).

    Gets KB context BEFORE analysis, then indexes to RAG only.
    Kept for backward compatibility when four_phase_analysis_enabled=False.
    """
    timestamp = datetime.now().strftime("%Y%m%dT%H%M")
    filepath = cfg.analyses_dir / f"{ticker}_{analysis_type.value}_{timestamp}.md"
    stock = db.get_stock(ticker) if ticker != "PORTFOLIO" else None

    run_id = db.mark_schedule_started(schedule_id) if schedule_id else None

    log.info(f"═══ STAGE 1: ANALYSIS (legacy) ═══ {ticker} ({analysis_type.value})")

    prompt = build_analysis_prompt(ticker, analysis_type, stock, kb_enabled=cfg.kb_query_enabled)
    output = call_claude_code(prompt, cfg.allowed_tools_analysis, f"ANALYZE-{ticker}")

    if not output:
        if run_id and schedule_id:
            db.mark_schedule_completed(
                schedule_id, run_id, "failed", error="Claude Code returned empty"
            )
        return None

    filepath.write_text(output)
    parsed = parse_json_block(output)

    result = AnalysisResult(
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

    # Persist to DB
    if run_id and schedule_id:
        db.mark_schedule_completed(
            schedule_id,
            run_id,
            "completed",
            gate_passed=result.gate_passed,
            recommendation=result.recommendation,
            confidence=result.confidence,
            expected_value=result.expected_value,
            analysis_file=str(filepath),
        )

    if parsed and ticker not in ("PORTFOLIO", "SCAN"):
        try:
            db.save_analysis_result(run_id, ticker, analysis_type.value, parsed)
        except Exception as e:
            log.warning(f"Save analysis result failed: {e}")

    kb_ingest_analysis(
        filepath,
        {
            "ticker": ticker,
            "type": analysis_type.value,
            "date": timestamp,
            "gate_passed": result.gate_passed,
        },
    )

    # Increment service counters
    try:
        db.increment_service_counter("analyses_total")
        db.increment_service_counter("today_analyses")
    except Exception:
        pass

    # Post-analysis workflow (visualization, chaining)
    try:
        _post_analysis_workflow(db, ticker, filepath, result)
    except Exception as e:
        log.warning(f"Post-analysis workflow failed: {e}")

    log.info(
        f"Analysis: {ticker} | Gate: {'PASS' if result.gate_passed else 'FAIL'} | "
        f"Rec: {result.recommendation} | Conf: {result.confidence}%"
    )
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
        return ExecutionResult(
            analysis_path=analysis_path, order_placed=False, reason="Do Nothing gate failed"
        )

    if stock and stock.state == "analysis":
        log.info(f"{ticker} state=analysis → recommendation only")

    prompt = build_execution_prompt(analysis_path, content, stock)
    output = call_claude_code(prompt, cfg.allowed_tools_execution, f"EXECUTE-{ticker}")

    if not output:
        return ExecutionResult(
            analysis_path=analysis_path, order_placed=False, reason="Execution call failed"
        )

    parsed = parse_json_block(output)
    ts = datetime.now().strftime("%Y%m%dT%H%M")
    trade_path = cfg.trades_dir / f"{ticker}_trade_{ts}.md"
    trade_path.write_text(output)

    result = ExecutionResult(
        analysis_path=analysis_path,
        order_placed=parsed.get("action") == "ORDER_PLACED" if parsed else False,
        order_details=parsed,
        reason=parsed.get("reason", "") if parsed else "Parse failed",
        filepath=trade_path,
        raw_output=output,
    )

    if result.order_placed and parsed:
        order_id = parsed.get("order_id")

        # Create trade entry in nexus.trades
        trade = {
            "ticker": ticker,
            "entry_date": datetime.now(),
            "entry_price": parsed.get("limit_price") or parsed.get("entry_price", 0),
            "entry_size": parsed.get("quantity") or parsed.get("shares", 0),
            "entry_type": parsed.get("structure", "stock"),
            "thesis": parsed.get("reason") or parsed.get("rationale", ""),
            "source_analysis": str(analysis_path),
        }

        try:
            trade_id = db.add_trade(trade)
            log.info(f"Created trade {trade_id} for {ticker}")

            # Store order ID for reconciliation
            if order_id:
                db.update_trade_order(trade_id, str(order_id), "Submitted")
                log.info(f"Trade {trade_id} linked to order {order_id}")

            # Update stock position
            if stock:
                db.update_stock_position(ticker, True, "pending")

        except Exception as e:
            log.error(f"Failed to create trade entry: {e}")

    # Increment service counters
    try:
        db.increment_service_counter("executions_total")
        db.increment_service_counter("today_executions")
    except Exception:
        pass

    kb_ingest_analysis(
        trade_path,
        {
            "ticker": ticker,
            "type": "trade_execution",
            "date": ts,
            "order_placed": result.order_placed,
        },
    )

    log.info(f"Execution: {ticker} | {'ORDER PLACED' if result.order_placed else 'NO ORDER'}")
    return result


# ─── Pipeline Orchestration ──────────────────────────────────────────────────


def run_pipeline(
    db: NexusDB,
    ticker: str,
    analysis_type: AnalysisType,
    auto_execute: bool = True,
    schedule_id: int | None = None,
    source_scanner: str | None = None,
):
    """Full two-stage pipeline."""
    log.info(f"╔═ PIPELINE: {ticker} ({analysis_type.value}) ═╗")

    analysis = run_analysis(db, ticker, analysis_type, schedule_id)
    if not analysis:
        return

    # Add to watchlist if gate passed and not already present
    if analysis.gate_passed:
        existing = db.get_stock(ticker)
        if not existing:
            # Build tags for new watchlist entry
            tags = [f"gate_passed:{datetime.now().strftime('%Y%m%d')}"]
            if source_scanner:
                tags.append(f"scanner:{source_scanner}")
            tags.append(f"type:{analysis_type.value}")
            tags.append(f"rec:{analysis.recommendation}")

            db.upsert_stock(
                ticker,
                is_enabled=True,
                state="analysis",
                default_analysis_type=analysis_type.value,
                priority=5,  # Default priority for scanner candidates
                tags=tags,
                comments=f"Added via scanner gate pass. Rec: {analysis.recommendation}, Conf: {analysis.confidence}%",
            )
            log.info(f"  ✓ Added {ticker} to watchlist (gate PASS, rec: {analysis.recommendation})")

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
    if stock and stock.state == "analysis":
        log.info(f"{ticker} state=analysis → no execution")
        return

    run_execution(db, analysis.filepath)


def run_watchlist(db: NexusDB, auto_execute: bool = False):
    """Analyze all enabled stocks."""
    stocks = db.get_enabled_stocks()
    remaining = cfg.max_daily_analyses - db.get_today_run_count()
    log.info(f"═══ WATCHLIST: {len(stocks)} stocks, {remaining} slots remaining ═══")

    for stock in stocks[: max(0, remaining)]:
        atype = AnalysisType(stock.default_analysis_type)
        if stock.days_to_earnings is not None and stock.days_to_earnings <= 14:
            atype = AnalysisType.EARNINGS
        run_pipeline(db, stock.ticker, atype, auto_execute=auto_execute)


def run_scanners(db: NexusDB, scanner_code: str | None = None):
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
        run_id = db.start_scanner_run(scanner.scanner_code)

        try:
            output = call_claude_code(
                build_scanner_prompt(scanner),
                cfg.allowed_tools_scanner,
                f"SCAN-{scanner.scanner_code}",
            )
            if not output:
                db.complete_scanner_run(
                    run_id, "failed",
                    scanner_code=scanner.scanner_code,
                    error="Claude Code returned empty"
                )
                continue

            ts = datetime.now().strftime("%Y%m%dT%H%M")
            fp = cfg.analyses_dir / f"scanner_{scanner.scanner_code}_{ts}.md"
            fp.write_text(output)

            parsed = parse_json_block(output)
            if not parsed or "candidates" not in parsed:
                db.complete_scanner_run(
                    run_id, "completed",
                    scanner_code=scanner.scanner_code
                )
                continue

            candidates = parsed["candidates"]
            log.info(f"  {len(candidates)} candidates found")
            db.complete_scanner_run(
                run_id, "completed",
                candidates=candidates,
                scanner_code=parsed.get("scanner", scanner.scanner_code),
                scan_time=parsed.get("scan_time"),
            )

            if scanner.auto_add_to_watchlist:
                for c in candidates[: scanner.max_candidates]:
                    db.upsert_stock(
                        c["ticker"], is_enabled=True, tags=[f"scanner:{scanner.scanner_code}"]
                    )

            if scanner.auto_analyze:
                atype = AnalysisType(scanner.analysis_type)
                for c in candidates[: scanner.max_candidates]:
                    run_pipeline(db, c["ticker"], atype, auto_execute=False, source_scanner=scanner.scanner_code)

        except Exception as e:
            log.error(f"Scanner {scanner.scanner_code} failed: {e}")
            db.complete_scanner_run(
                run_id, "failed",
                scanner_code=scanner.scanner_code,
                error=str(e)
            )


@dataclass
class ScanResult:
    """Result from a scanner for routing."""
    ticker: str
    score: float
    scanner_name: str
    catalyst: str = ""


def _route_scanner_results(db: NexusDB, scanner_name: str, results: list[ScanResult]) -> dict:
    """Route scanner results based on score thresholds."""
    if not cfg.scanner_auto_route:
        return {"analyzed": 0, "watchlisted": 0, "skipped": 0}

    stats = {"analyzed": 0, "watchlisted": 0, "skipped": 0}

    # Respect concurrent limits
    max_queue = cfg.max_concurrent_runs
    queued = 0

    for result in sorted(results, key=lambda x: x.score, reverse=True):
        ticker = result.ticker
        score = result.score

        if score >= 7.5 and queued < max_queue:
            # High score -> Trigger full analysis
            analysis_type = "earnings" if "earnings" in scanner_name.lower() else "stock"

            task_id = db.queue_analysis(ticker, analysis_type, priority=int(score))
            if task_id:
                log.info(f"  → High score ({score:.1f}): Queued analysis for {ticker}")
                stats["analyzed"] += 1
                queued += 1
            else:
                log.debug(f"  → {ticker} in cooldown, skipping")
                stats["skipped"] += 1

        elif score >= 5.5:
            # Medium score -> Add to watchlist
            existing = db.get_watchlist_entry(ticker)
            if not existing:
                from datetime import timedelta
                db.add_watchlist_entry({
                    "ticker": ticker,
                    "entry_trigger": result.catalyst or "Scanner trigger",
                    "entry_price": None,
                    "invalidation": "Score drops below 5.5",
                    "invalidation_price": None,
                    "expires_at": (datetime.now() + timedelta(days=14)).isoformat(),
                    "priority": "low",
                    "source": f"scanner:{scanner_name}",
                    "source_analysis": None,
                    "notes": f"Score: {score:.1f}",
                })
                log.info(f"  → Medium score ({score:.1f}): Added {ticker} to watchlist")
                stats["watchlisted"] += 1
        else:
            stats["skipped"] += 1

    return stats


def process_task_queue(db: NexusDB, max_tasks: int = 5) -> dict:
    """
    Process pending tasks from queue.

    Returns:
        Dict with counts: {processed, succeeded, failed, skipped, retried}
    """
    results = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "retried": 0}

    if not cfg.task_queue_enabled:
        log.debug("Task queue disabled")
        return results

    # Recover stuck tasks first
    timeout = int(cfg._get("task_timeout_minutes", "scheduler", "30"))
    recovered = db.recover_stuck_tasks(timeout)
    if recovered:
        log.info(f"Recovered {recovered} stuck tasks")

    # Get pending and retryable tasks
    tasks = db.get_pending_or_retryable_tasks(limit=max_tasks)
    if not tasks:
        return results

    log.info(f"═══ TASK QUEUE: {len(tasks)} tasks ═══")

    # Get daily limits
    service_status = db.get_service_status() or {}
    today_analyses = service_status.get("today_analyses", 0)
    max_analyses = int(cfg._get("max_daily_analyses", "rate_limits", "20"))

    retry_delay = int(cfg._get("task_retry_delay_minutes", "scheduler", "15"))

    for task in tasks:
        task_id = task["id"]
        task_type = task["task_type"]
        ticker = task.get("ticker")
        is_retry = task.get("retry_count", 0) > 0

        # Check daily limits for analysis tasks
        if task_type == "analysis" and today_analyses >= max_analyses:
            log.info(f"Skipping task {task_id}: daily analysis limit reached ({today_analyses}/{max_analyses})")
            results["skipped"] += 1
            continue

        log.info(f"{'Retrying' if is_retry else 'Processing'} task {task_id}: {task_type} for {ticker or 'N/A'}")
        db.mark_task_started(task_id)

        try:
            if task_type == "analysis":
                _process_analysis_task(db, task)
                today_analyses += 1

            elif task_type == "post_trade_review":
                _process_post_trade_review_task(db, task)

            elif task_type == "detected_position":
                _process_detected_position_task(db, task)

            elif task_type == "fill_analysis":
                _process_fill_analysis_task(db, task)

            elif task_type == "position_close_review":
                _process_position_close_review_task(db, task)

            elif task_type == "options_management":
                _process_options_management_task(db, task)

            elif task_type == "expiration_review":
                _process_expiration_review_task(db, task)

            elif task_type == "post_earnings_review":
                _process_post_earnings_review_task(db, task)

            elif task_type == "report_validation":
                _process_report_validation_task(db, task)

            else:
                log.warning(f"Unknown task type: {task_type}")
                raise ValueError(f"Unknown task type: {task_type}")

            db.mark_task_completed(task_id)
            results["succeeded"] += 1
            if is_retry:
                results["retried"] += 1

        except Exception as e:
            log.error(f"Task {task_id} failed: {e}")
            db.mark_task_completed(task_id, error=str(e))

            # Schedule retry if retries remaining
            if task.get("retry_count", 0) < task.get("max_retries", 3):
                db.mark_task_for_retry(task_id, retry_delay)
                log.info(f"Task {task_id} scheduled for retry")

            results["failed"] += 1

        results["processed"] += 1

    log.info(f"Task queue results: {results}")
    return results


def _process_analysis_task(db: NexusDB, task: dict):
    """Process an analysis task."""
    ticker = task["ticker"]
    analysis_type = AnalysisType(task.get("analysis_type", "stock"))

    result = run_analysis(db, ticker, analysis_type)
    if not result:
        raise RuntimeError(f"Analysis failed for {ticker}")

    log.info(f"  ✓ Analysis complete: {ticker}")


def _process_post_trade_review_task(db: NexusDB, task: dict):
    """Process a post-trade review task."""
    ticker = task["ticker"]
    prompt = task.get("prompt", f"Post-trade review for {ticker}")

    # Extract trade_id from prompt if present
    trade_id = _extract_trade_id_from_prompt(prompt)

    # Run the review
    output = call_claude_code(prompt, cfg.allowed_tools_analysis, f"REVIEW-{ticker}")

    if not output:
        raise RuntimeError(f"Post-trade review returned no output for {ticker}")

    # Try to find the review file path in output
    review_path = _extract_review_path(output)

    # Mark trade as reviewed if we have the trade_id
    if trade_id and review_path:
        db.mark_trade_reviewed(trade_id, review_path)
        log.info(f"  ✓ Trade {trade_id} marked as reviewed: {review_path}")
    elif trade_id:
        # Mark reviewed even without path
        db.mark_trade_reviewed(trade_id, f"review_output_{ticker}_{datetime.now().strftime('%Y%m%d')}")
        log.info(f"  ✓ Trade {trade_id} marked as reviewed (no path extracted)")
    else:
        log.info(f"  ✓ Post-trade review complete: {ticker}")


def _extract_trade_id_from_prompt(prompt: str) -> int | None:
    """Extract trade ID from review prompt."""
    import re
    # Look for patterns like "trade_id: 123" or "Trade 123" or "trade 123"
    match = re.search(r'trade[_\s]?(?:id)?[:\s]*(\d+)', prompt, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_review_path(output: str) -> str | None:
    """Extract review file path from Claude output."""
    import re
    # Look for YAML file paths in knowledge directory
    patterns = [
        r'(tradegent_knowledge/knowledge/reviews/[^\s]+\.yaml)',
        r'Saved to[:\s]*([^\s]+\.yaml)',
        r'Review saved[:\s]*([^\s]+\.yaml)',
    ]
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            return match.group(1)
    return None


# ─── Skill Task Handlers (Monitoring Integration) ────────────────────────────

def _process_detected_position_task(db: NexusDB, task: dict):
    """Process detected position task.

    Triggered by position_monitor when a new position is detected externally.
    Uses Claude Code for full analysis if enabled, otherwise basic Python handler.
    """
    from skill_handlers import (
        invoke_skill_python,
        invoke_skill_claude,
        _parse_detected_position_prompt,
    )

    ticker = task["ticker"]
    prompt = task.get("prompt", "")
    task_id = task["id"]

    # Parse context from prompt
    context = _parse_detected_position_prompt(prompt)
    context["ticker"] = ticker
    context["source"] = "position_monitor"

    # Check if Claude Code is enabled
    use_claude = db.cfg._get("skill_use_claude_code", "skills", "false").lower() == "true"
    auto_create = db.cfg._get("detected_position_auto_create_trade", "skills", "true").lower() == "true"

    if use_claude:
        # Full AI analysis
        result = invoke_skill_claude(db, "detected-position", context, task_id)
        log.info(f"  ✓ Claude analysis complete for detected {ticker} position")
    elif auto_create:
        # Python fallback: create basic trade entry
        result = invoke_skill_python(db, "detected-position", context, task_id)
        log.info(f"  ✓ Basic trade entry created for detected {ticker} position")
    else:
        # Just log, don't create trade
        log.info(f"Detected position for {ticker} logged but not auto-created (setting disabled)")
        result = {"status": "logged_only"}


def _process_fill_analysis_task(db: NexusDB, task: dict):
    """Process fill analysis task (Python only).

    Triggered by order_reconciler when an order is filled.
    Analyzes fill quality: slippage, timing, execution efficiency.
    """
    from skill_handlers import invoke_skill_python

    ticker = task.get("ticker")
    prompt = task.get("prompt", "")
    task_id = task["id"]

    # Extract order_id from prompt if present
    import re
    match = re.search(r'order[_\s]?(?:id)?[:\s]*(\d+)', prompt, re.IGNORECASE)
    order_id = match.group(1) if match else None

    context = {
        "ticker": ticker,
        "order_id": order_id,
        "source": "order_reconciler"
    }

    result = invoke_skill_python(db, "fill-analysis", context, task_id)

    if result.get("status") == "analyzed":
        log.info(f"  ✓ Fill analysis: {ticker} grade {result.get('grade', 'N/A')}")
    else:
        log.info(f"  ✓ Fill analysis: {result.get('status', 'unknown')}")


def _process_position_close_review_task(db: NexusDB, task: dict):
    """Process position close review task (Python only).

    Triggered by position_monitor when a position is fully closed.
    Calculates P&L and queues full post-trade review if significant.
    """
    from skill_handlers import invoke_skill_python

    ticker = task.get("ticker")
    task_id = task["id"]

    context = {
        "ticker": ticker,
        "prompt": task.get("prompt", ""),
        "source": "position_monitor"
    }

    result = invoke_skill_python(db, "position-close-review", context, task_id)

    if result.get("is_significant"):
        log.info(f"  ✓ Position close review: {ticker} (significant, queued full review)")
    else:
        log.info(f"  ✓ Position close review: {ticker} (not significant)")


def _process_options_management_task(db: NexusDB, task: dict):
    """Process options management task.

    Triggered by expiration_monitor for expiring options, or by user request.
    Uses Claude Code for full analysis if enabled, otherwise basic Python summary.
    """
    from skill_handlers import invoke_skill_python, invoke_skill_claude

    ticker = task.get("ticker")
    prompt = task.get("prompt", "")
    task_id = task["id"]

    context = {
        "ticker": ticker,
        "trigger": "expiration_warning",
        "prompt": prompt,
        "source": "expiration_monitor"
    }

    # Options management can use Claude Code for complex roll decisions
    use_claude = db.cfg._get("skill_use_claude_code", "skills", "false").lower() == "true"

    if use_claude:
        result = invoke_skill_claude(db, "options-management", context, task_id)
        log.info(f"  ✓ Options management analysis complete for {ticker}")
    else:
        result = invoke_skill_python(db, "options-management", context, task_id)
        log.info(f"  ✓ Options summary: {result.get('count', 0)} positions")


def _process_expiration_review_task(db: NexusDB, task: dict):
    """Process expiration review task.

    Triggered by expiration_monitor when options expire.
    Always runs Python for P&L calculation, optionally uses Claude for lesson extraction.
    """
    from skill_handlers import invoke_skill_python, invoke_skill_claude

    ticker = task.get("ticker")
    task_id = task["id"]

    context = {
        "ticker": ticker,
        "prompt": task.get("prompt", ""),
        "source": "expiration_monitor"
    }

    # Always run Python for P&L calculation
    result = invoke_skill_python(db, "expiration-review", context, task_id)

    # Optionally use Claude for lesson extraction
    use_claude = db.cfg._get("skill_use_claude_code", "skills", "false").lower() == "true"
    if use_claude and result.get("status") == "reviewed":
        try:
            context["outcome"] = result.get("outcome")
            context["pnl"] = result.get("pnl")
            claude_result = invoke_skill_claude(db, "expiration-review", context, task_id)
            log.info(f"  ✓ Expiration review with lessons: {ticker}")
        except Exception as e:
            log.warning(f"Claude lesson extraction failed: {e}")
    else:
        log.info(f"  ✓ Expiration review: {ticker} {result.get('outcome', '')}")


def _process_post_earnings_review_task(db: NexusDB, task: dict):
    """Process post-earnings review task.

    Triggered by service.py when earnings have been released.
    Uses Claude to compare forecast vs actual results and generate lessons.
    """
    ticker = task.get("ticker")
    task_id = task["id"]
    prompt = task.get("prompt", "")

    # Extract analysis file from prompt if present
    analysis_file = None
    if "analysis_file:" in prompt:
        for line in prompt.split("\n"):
            if line.startswith("analysis_file:"):
                analysis_file = line.split(":", 1)[1].strip()
                break

    if not analysis_file:
        # Try to find latest earnings analysis
        analysis_file = db.get_latest_earnings_analysis(ticker)

    if not analysis_file:
        log.warning(f"No earnings analysis found for {ticker} - skipping review")
        return

    # Check if Claude mode is enabled
    use_claude = db.cfg._get("skill_use_claude_code", "skills", "false").lower() == "true"
    if not use_claude:
        log.info(f"  ⊘ Post-earnings review skipped (Claude disabled): {ticker}")
        return

    # Build context for skill invocation
    context = {
        "ticker": ticker,
        "analysis_file": analysis_file,
        "source": "earnings_release",
    }

    try:
        from skill_handlers import invoke_skill_claude

        result = invoke_skill_claude(db, "post-earnings-review", context, task_id)
        review_file = result.get("review_file")
        grade = result.get("grade", "?")

        if review_file:
            # Update lineage with review info
            lineage = db.get_active_analysis(ticker, "earnings")
            if lineage:
                db.update_lineage_status(
                    lineage["id"],
                    "reviewed",
                    post_earnings_review_file=review_file,
                    post_earnings_grade=grade,
                )

            # Update confidence calibration
            confidence = result.get("stated_confidence")
            was_correct = grade in ["A", "B"]  # A or B = good prediction
            if confidence:
                db.update_confidence_calibration(ticker, "earnings", confidence, was_correct)

            log.info(f"  ✓ Post-earnings review: {ticker} grade={grade}")
        else:
            log.warning(f"  ⚠ Post-earnings review produced no file: {ticker}")

    except Exception as e:
        log.error(f"Post-earnings review failed for {ticker}: {e}")
        raise


def _process_report_validation_task(db: NexusDB, task: dict):
    """Process report validation task.

    Triggered when:
    - New analysis is created (validate against prior)
    - Forecast expires (check if still valid)

    Uses Claude to determine: CONFIRM, SUPERSEDE, or INVALIDATE.
    """
    ticker = task.get("ticker")
    task_id = task["id"]
    prompt = task.get("prompt", "")

    # Extract files from prompt
    prior_file = None
    new_file = None
    trigger = "new_analysis"

    for line in prompt.split("\n"):
        if line.startswith("prior_file:"):
            prior_file = line.split(":", 1)[1].strip()
        elif line.startswith("new_file:"):
            new_file = line.split(":", 1)[1].strip()
        elif line.startswith("trigger:"):
            trigger = line.split(":", 1)[1].strip()

    # For expiry validation, we only have prior file
    if trigger == "forecast_expiry" and prior_file and not new_file:
        # Re-run analysis and then validate
        log.info(f"  → Forecast expired for {ticker}, triggering fresh analysis")
        # This will be handled by the normal analysis flow
        # which chains to validation automatically
        return

    if not prior_file:
        # Try to find prior active analysis
        lineage = db.get_active_analysis(ticker, "stock")
        if not lineage:
            lineage = db.get_active_analysis(ticker, "earnings")
        if lineage:
            prior_file = lineage["current_analysis_file"]

    if not prior_file:
        log.warning(f"No prior analysis found for {ticker} - skipping validation")
        return

    # Check if Claude mode is enabled
    use_claude = db.cfg._get("skill_use_claude_code", "skills", "false").lower() == "true"
    if not use_claude:
        log.info(f"  ⊘ Report validation skipped (Claude disabled): {ticker}")
        return

    # Build context for skill invocation
    context = {
        "ticker": ticker,
        "prior_file": prior_file,
        "new_file": new_file,
        "trigger": trigger,
        "source": "validation_check",
    }

    try:
        from skill_handlers import invoke_skill_claude

        result = invoke_skill_claude(db, "report-validation", context, task_id)
        validation_result = result.get("validation_result")
        validation_file = result.get("validation_file")

        if validation_result and validation_file:
            # Update lineage
            lineage = db.get_active_analysis(ticker, "stock")
            if not lineage:
                lineage = db.get_active_analysis(ticker, "earnings")

            if lineage:
                if validation_result == "INVALIDATE":
                    db.update_lineage_status(
                        lineage["id"],
                        "invalidated",
                        validation_file=validation_file,
                        validation_result=validation_result,
                    )
                    # Invalidate watchlist entry
                    invalidation_reason = result.get("reason", "Thesis invalidated by new analysis")
                    db.invalidate_watchlist_entry(ticker, invalidation_reason)

                    # Send alert if enabled
                    alerts_enabled = db.cfg._get("invalidation_alerts_enabled", "skills", "true").lower() == "true"
                    if alerts_enabled:
                        _send_invalidation_alert(ticker, validation_result, invalidation_reason)

                    log.warning(f"  ⚠ INVALIDATED: {ticker} - {invalidation_reason}")

                elif validation_result == "SUPERSEDE":
                    db.update_lineage_status(
                        lineage["id"],
                        "superseded",
                        validation_file=validation_file,
                        validation_result=validation_result,
                    )
                    log.info(f"  ✓ Validation: {ticker} SUPERSEDED")

                else:  # CONFIRM
                    db.update_lineage_status(
                        lineage["id"],
                        "confirmed",
                        validation_file=validation_file,
                        validation_result=validation_result,
                    )
                    log.info(f"  ✓ Validation: {ticker} CONFIRMED")
        else:
            log.warning(f"  ⚠ Report validation produced no result: {ticker}")

    except Exception as e:
        log.error(f"Report validation failed for {ticker}: {e}")
        raise


def _send_invalidation_alert(ticker: str, result: str, reason: str):
    """Send alert when analysis is invalidated.

    Currently logs to console. Can be extended to send email/Slack/etc.
    """
    alert_msg = f"""
╔══════════════════════════════════════════════════════════════════╗
║  ⚠️  ANALYSIS INVALIDATED                                        ║
╠══════════════════════════════════════════════════════════════════╣
║  Ticker: {ticker:<54} ║
║  Result: {result:<54} ║
║  Reason: {reason[:54]:<54} ║
╚══════════════════════════════════════════════════════════════════╝
"""
    log.warning(alert_msg)
    # TODO: Add email/Slack notification integration


def process_pending_reviews(db: NexusDB) -> int:
    """Process all trades pending review. Call from scheduler."""
    trades = db.get_trades_pending_review()
    count = 0
    for trade in trades:
        if _chain_to_post_trade_review(db, trade["id"]):
            count += 1
    return count


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
            run_pipeline(
                db,
                stock.ticker,
                AnalysisType(sched.analysis_type),
                auto_execute=sched.auto_execute,
                schedule_id=sched.id,
            )


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
        "analyze_stock": lambda s: run_analysis(
            db, s.target_ticker, AnalysisType(s.analysis_type), s.id
        )
        if s.target_ticker
        else None,
        "analyze_watchlist": lambda s: run_watchlist(db, s.auto_execute),
        "run_scanner": _run_scanner_task,
        "run_all_scanners": lambda s: run_scanners(db),
        "pipeline": lambda s: run_pipeline(
            db, s.target_ticker, AnalysisType(s.analysis_type), s.auto_execute, s.id
        )
        if s.target_ticker
        else None,
        "portfolio_review": lambda s: run_analysis(db, "PORTFOLIO", AnalysisType.REVIEW, s.id),
        "postmortem": lambda s: run_analysis(db, s.target_ticker, AnalysisType.POSTMORTEM, s.id)
        if s.target_ticker
        else None,
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
            elif sched.task_type == "custom" and sched.custom_prompt:
                output = call_claude_code(
                    sched.custom_prompt, cfg.allowed_tools_analysis, f"CUSTOM-{sched.id}"
                )
                if output:
                    ts = datetime.now().strftime("%Y%m%dT%H%M")
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

    print(f"\n{'═' * 60}")
    print("  NEXUS LIGHT - STATUS")
    print(f"{'═' * 60}")

    print(f"\n  WATCHLIST ({len(stocks)} enabled)")
    for state in ["analysis", "paper", "live"]:
        items = by_state.get(state, [])
        tickers = ", ".join(s.ticker for s in items) if items else "—"
        print(f"    {state:>10}: {tickers}")

    earnings = db.get_stocks_near_earnings()
    if earnings:
        print("\n  UPCOMING EARNINGS")
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
        status = sch.last_run_status or "never"
        print(f"    {(sch.name or '')[:40]:<40} {sch.frequency:<12} [{status}]")

    print(f"\n  TODAY: {db.get_today_run_count()} runs (limit {cfg.max_daily_analyses})")

    # Knowledge Base Status
    print("\n  KNOWLEDGE BASE")
    try:
        from graph.layer import TradingGraph

        with TradingGraph() as g:
            status = g.get_status()
            if status.get("connected"):
                if status.get("populated"):
                    print(f"    Graph: ✅ {status['node_count']} nodes, {status['edge_count']} edges")
                else:
                    print("    Graph: ⚠️  Empty (run 'graph init' and index documents)")
            else:
                print("    Graph: ❌ Not connected")
    except Exception as e:
        print(f"    Graph: ❌ {e}")

    try:
        from rag.schema import get_db_stats

        rag_stats = get_db_stats()
        if rag_stats:
            print(f"    RAG: ✅ {rag_stats.get('documents', 0)} docs, {rag_stats.get('chunks', 0)} chunks")
        else:
            print("    RAG: ⚠️  Empty")
    except Exception:
        print("    RAG: Not available")

    print(f"{'═' * 60}\n")


# ─── Graph and RAG CLI Handlers ──────────────────────────────────────────────


def _check_all_health() -> None:
    """Check health of all services: Neo4j, PostgreSQL, Ollama."""
    import requests

    print(f"\n{'═' * 50}")
    print("SERVICE HEALTH CHECK")
    print(f"{'═' * 50}\n")

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
                status = g.get_status()
                if status.get("populated"):
                    print(f"✅ Neo4j (graph): OK ({status['node_count']} nodes, {status['edge_count']} edges)")
                else:
                    print("⚠️  Neo4j (graph): EMPTY - run 'python orchestrator.py graph init' and index documents")
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
        print("✅ IB Gateway: Connected")
        ib.disconnect()
    except Exception as e:
        print(f"⚠️ IB Gateway: {e}")

    # Check pending commits
    pending_file = Path("logs/pending_commits.jsonl")
    if pending_file.exists():
        with open(pending_file) as f:
            pending_count = sum(1 for line in f if line.strip())
        if pending_count > 0:
            print(f"\n⚠️ Pending commits: {pending_count} items")
            print("   Run 'python orchestrator.py graph retry' to process")
    else:
        print("\n✅ No pending commits")

    print(f"\n{'═' * 50}\n")


def _retry_pending_commits(limit: int = 10) -> None:
    """Retry pending commits from the queue."""
    import json
    from pathlib import Path as _Path

    pending_file = _Path("logs/pending_commits.jsonl")
    if not pending_file.exists():
        print("No pending commits file found")
        return

    from graph.exceptions import ExtractionError, GraphUnavailableError
    from graph.extract import extract_document

    pending_items = []
    with open(pending_file) as f:
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
        from graph.exceptions import ExtractionError
        from graph.extract import extract_document

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
                print(
                    f"{status} {result.source_doc_id}: {len(result.entities)} entities, {len(result.relations)} relations"
                )
            except ExtractionError as e:
                print(f"❌ {f}: {e}")

    elif args.graph_cmd == "status":
        from graph.layer import TradingGraph

        try:
            with TradingGraph() as g:
                stats = g.get_stats()
                print(f"\n{'═' * 40}")
                print("KNOWLEDGE GRAPH STATUS")
                print(f"{'═' * 40}")
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
                name = (
                    r["props"].get("name")
                    or r["props"].get("symbol")
                    or r["props"].get("id")
                    or "?"
                )
                print(f"  [{labels}] {name}")

    elif args.graph_cmd == "peers":
        from graph.layer import TradingGraph

        with TradingGraph() as g:
            peers = g.get_sector_peers(args.ticker.upper())
            print(f"\nSector peers for {args.ticker.upper()}:")
            for p in peers:
                print(
                    f"  {p.get('peer', '?'):<8} {p.get('company', ''):<30} ({p.get('sector', '')})"
                )

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
                    print(
                        f"  {b.get('bias', '?')}: trade {b.get('trade_id', '?')} ({b.get('outcome', '?')})"
                    )

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
    import glob
    from datetime import date as _date

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
                    print(
                        f"✅ {result.doc_id}: {result.chunk_count} chunks ({result.duration_ms}ms)"
                    )
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
        print(f"{'─' * 60}")
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
        print(f"{'─' * 60}")
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
            print(f"\n{'═' * 40}")
            print("RAG STATUS")
            print(f"{'═' * 40}")
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
        print(f"{'─' * 70}")
        for d in docs:
            print(
                f"{d['doc_id']:<30} {d['doc_type']:<20} {d.get('ticker') or '—':<8} {d['chunk_count']}"
            )

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

    p = sub.add_parser("analyze")
    p.add_argument("ticker")
    p.add_argument("--type", default="stock", choices=["earnings", "stock", "postmortem"])
    p = sub.add_parser("execute")
    p.add_argument("analysis_file")
    p = sub.add_parser("pipeline")
    p.add_argument("ticker")
    p.add_argument("--type", default="stock", choices=["earnings", "stock"])
    p.add_argument("--no-execute", action="store_true")
    p = sub.add_parser("watchlist")
    p.add_argument("--auto-execute", action="store_true")
    p = sub.add_parser("scan")
    p.add_argument("--scanner")
    sub.add_parser("run-due")
    sub.add_parser("review")
    sub.add_parser("earnings-check")
    sub.add_parser("status")
    sub.add_parser("health", help="Check all service health")
    sub.add_parser("db-init")

    # ─── Task Queue Commands ─────────────────────────────────────────────────────
    p = sub.add_parser("process-queue", help="Process pending tasks from queue")
    p.add_argument("--max", type=int, default=5, help="Max tasks to process")

    p = sub.add_parser("queue-status", help="Show task queue status")

    # ─── Trade Commands ──────────────────────────────────────────────────────────
    trade_parser = sub.add_parser("trade", help="Trade journal management")
    trade_sub = trade_parser.add_subparsers(dest="trade_cmd")

    p = trade_sub.add_parser("add", help="Add new trade entry")
    p.add_argument("ticker", help="Stock ticker")
    p.add_argument("--price", type=float, required=True, help="Entry price")
    p.add_argument("--size", type=float, required=True, help="Position size (shares)")
    p.add_argument("--type", default="stock", choices=["stock", "call", "put", "spread"])
    p.add_argument("--thesis", help="Trade thesis")
    p.add_argument("--analysis", help="Path to source analysis")

    p = trade_sub.add_parser("close", help="Close trade")
    p.add_argument("trade_id", type=int, help="Trade ID to close")
    p.add_argument("--price", type=float, required=True, help="Exit price")
    p.add_argument("--reason", default="manual", help="Exit reason")

    p = trade_sub.add_parser("list", help="List trades")
    p.add_argument("--status", choices=["open", "closed", "all"], default="open")

    trade_sub.add_parser("pending-reviews", help="Show trades pending review")

    p = trade_sub.add_parser("detected", help="List trades from detected position increases")
    p.add_argument("--all", dest="show_all", action="store_true", help="Show all, including confirmed")

    p = trade_sub.add_parser("confirm", help="Confirm a detected trade entry")
    p.add_argument("trade_id", type=int, help="Trade ID to confirm")
    p.add_argument("--thesis", "-t", help="Add/update thesis")
    p.add_argument("--price", "-p", type=float, help="Correct entry price")

    p = trade_sub.add_parser("reject", help="Reject a detected trade entry")
    p.add_argument("trade_id", type=int, help="Trade ID to reject")
    p.add_argument("--reason", "-r", help="Reason for rejection")

    # ─── Watchlist DB Commands ───────────────────────────────────────────────────
    wl_parser = sub.add_parser("watchlist-db", help="DB-backed watchlist management")
    wl_sub = wl_parser.add_subparsers(dest="wl_cmd")

    p = wl_sub.add_parser("list", help="List watchlist entries")
    p.add_argument("--status", choices=["active", "all"], default="active")

    wl_sub.add_parser("check", help="Check for expirations and triggers")

    wl_sub.add_parser("process-expired", help="Process expired entries")

    p = wl_sub.add_parser("monitor", help="Monitor watchlist triggers")
    p.add_argument("--once", action="store_true", help="Run once and exit (don't loop)")
    p.add_argument("--interval", type=int, default=300, help="Check interval in seconds")

    wl_sub.add_parser("pending-triggers", help="Show pending triggers for active entries")

    # ─── Options Commands (IPLAN-006) ───────────────────────────────────────────
    options_parser = sub.add_parser("options", help="Options position management")
    options_sub = options_parser.add_subparsers(dest="options_cmd")

    options_sub.add_parser("list", help="List open options positions")

    p = options_sub.add_parser("expiring", help="List options expiring soon")
    p.add_argument("--days", "-d", type=int, default=7, help="Days until expiration")

    options_sub.add_parser("expired", help="List expired options needing action")

    options_sub.add_parser("process-expired", help="Auto-close expired worthless options")

    p = options_sub.add_parser("by-underlying", help="List options for underlying")
    p.add_argument("ticker", help="Underlying ticker")

    options_sub.add_parser("summary", help="Show options expiration summary")

    # ─── Review Commands (IPLAN-001) ─────────────────────────────────────────────
    review_parser = sub.add_parser("review-earnings", help="Post-earnings review management")
    review_sub = review_parser.add_subparsers(dest="review_cmd")

    p = review_sub.add_parser("run", help="Run post-earnings review for ticker")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--analysis", help="Path to specific analysis file")

    review_sub.add_parser("pending", help="List pending post-earnings reviews")

    p = review_sub.add_parser("backfill", help="Generate reviews for historical analyses")
    p.add_argument("--limit", type=int, default=10, help="Max analyses to backfill")
    p.add_argument("--dry-run", action="store_true", help="Show what would be reviewed")

    validation_parser = sub.add_parser("validate-analysis", help="Report validation management")
    validation_sub = validation_parser.add_subparsers(dest="validation_cmd")

    p = validation_sub.add_parser("run", help="Validate analysis against prior")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--new", dest="new_file", help="New analysis file")
    p.add_argument("--prior", dest="prior_file", help="Prior analysis file")

    validation_sub.add_parser("expired", help="List expired forecasts needing validation")

    p = validation_sub.add_parser("process-expired", help="Process all expired forecasts")
    p.add_argument("--dry-run", action="store_true", help="Show what would be processed")

    lineage_parser = sub.add_parser("lineage", help="Analysis lineage tracking")
    lineage_sub = lineage_parser.add_subparsers(dest="lineage_cmd")

    p = lineage_sub.add_parser("show", help="Show lineage for ticker")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--limit", type=int, default=10, help="Max entries to show")

    lineage_sub.add_parser("active", help="List all active analyses")

    lineage_sub.add_parser("invalidated", help="List invalidated analyses")

    calibration_parser = sub.add_parser("calibration", help="Confidence calibration stats")
    calibration_sub = calibration_parser.add_subparsers(dest="calibration_cmd")

    calibration_sub.add_parser("summary", help="Show calibration summary by bucket")

    p = calibration_sub.add_parser("ticker", help="Show calibration for specific ticker")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--type", dest="analysis_type", default="earnings", help="Analysis type")

    p = sub.add_parser("stock")
    p.add_argument("action", choices=["add", "enable", "disable", "set-state", "list"])
    p.add_argument("ticker", nargs="?")
    p.add_argument("--state", choices=["analysis", "paper", "live"])
    p.add_argument("--tags", nargs="*")
    p.add_argument("--priority", type=int)
    p.add_argument("--earnings-date")
    p.add_argument("--comment")

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
        sys.modules[__name__].__dict__["cfg"] = cfg

        if args.cmd == "db-init":
            db.init_schema()
            print("✅ Schema initialized")

        elif args.cmd == "analyze":
            r = run_analysis(db, args.ticker.upper(), AnalysisType(args.type))
            if r:
                print(
                    f"File: {r.filepath}\nGate: {'PASS' if r.gate_passed else 'FAIL'}\nRec: {r.recommendation} ({r.confidence}%)"
                )

        elif args.cmd == "execute":
            p = Path(args.analysis_file)
            if not p.exists():
                print(f"Not found: {p}")
                sys.exit(1)
            r = run_execution(db, p)
            print(f"Order: {r.order_placed} | {r.reason}")

        elif args.cmd == "pipeline":
            run_pipeline(
                db, args.ticker.upper(), AnalysisType(args.type), auto_execute=not args.no_execute
            )

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
                print("─" * 60)
                for s in db.get_enabled_stocks():
                    tags = ",".join(s.tags[:3]) if s.tags else ""
                    earn = str(s.next_earnings_date) if s.next_earnings_date else "—"
                    print(f"{s.ticker:<8} {s.state:<10} {s.priority:<4} {earn:<12} {tags}")
            elif args.action == "add" and args.ticker:
                kw = {}
                if args.state:
                    kw["state"] = args.state
                if args.tags:
                    kw["tags"] = args.tags
                if args.priority:
                    kw["priority"] = args.priority
                if args.comment:
                    kw["comments"] = args.comment
                if args.earnings_date:
                    kw["next_earnings_date"] = args.earnings_date
                s = db.upsert_stock(args.ticker.upper(), **kw)
                print(f"✅ {s.ticker if s else args.ticker.upper()}")
            elif args.action in ("enable", "disable") and args.ticker:
                db.upsert_stock(args.ticker.upper(), is_enabled=(args.action == "enable"))
                print(
                    f"✅ {args.ticker.upper()} {'enabled' if args.action == 'enable' else 'disabled'}"
                )
            elif args.action == "set-state" and args.ticker and args.state:
                db.upsert_stock(args.ticker.upper(), state=args.state)
                print(f"✅ {args.ticker.upper()} → {args.state}")

        # ─── Task Queue Commands ─────────────────────────────────────────────────────
        elif args.cmd == "process-queue":
            count = process_task_queue(db, max_tasks=args.max)
            print(f"✅ Processed {count} tasks")

        elif args.cmd == "queue-status":
            stats = db.get_task_queue_stats()
            pending = db.get_pending_tasks(limit=10)
            print(f"\n{'═' * 40}")
            print("TASK QUEUE STATUS")
            print(f"{'═' * 40}")
            for status, count in stats.items():
                print(f"  {status:<15} {count:>4}")
            if pending:
                print(f"\nPending Tasks (up to 10):")
                print(f"{'ID':>4} {'Type':<20} {'Ticker':<8} {'Priority'}")
                print("─" * 45)
                for t in pending:
                    print(f"{t['id']:>4} {t['task_type']:<20} {t.get('ticker') or '—':<8} {t['priority']}")

        # ─── Trade Commands ──────────────────────────────────────────────────────────
        elif args.cmd == "trade":
            if args.trade_cmd == "add":
                trade = {
                    "ticker": args.ticker.upper(),
                    "entry_date": datetime.now(),
                    "entry_price": args.price,
                    "entry_size": args.size,
                    "entry_type": args.type,
                    "thesis": args.thesis or "",
                    "source_analysis": args.analysis,
                }
                trade_id = db.add_trade(trade)
                print(f"✅ Added trade {trade_id}: {args.ticker.upper()} @ ${args.price:.2f} x {args.size}")

            elif args.trade_cmd == "close":
                trade = db.get_trade(args.trade_id)
                if not trade:
                    print(f"❌ Trade {args.trade_id} not found")
                else:
                    db.close_trade(args.trade_id, args.price, args.reason)
                    pnl_pct = ((args.price - float(trade["entry_price"])) / float(trade["entry_price"])) * 100
                    print(f"✅ Closed trade {args.trade_id}: {trade['ticker']} @ ${args.price:.2f} ({pnl_pct:+.1f}%)")
                    # Auto-chain to post-trade review
                    _chain_to_post_trade_review(db, args.trade_id)

            elif args.trade_cmd == "list":
                status = args.status
                if status == "all":
                    with db.conn.cursor() as cur:
                        cur.execute("SELECT * FROM nexus.trades ORDER BY created_at DESC LIMIT 20")
                        trades = [dict(r) for r in cur.fetchall()]
                else:
                    trades = db.get_trades_by_status(status)
                print(f"\n{'ID':>4} {'Ticker':<6} {'Entry':>10} {'Exit':>10} {'P/L':>8} {'Status':<8}")
                print("─" * 55)
                for t in trades:
                    pnl = f"{float(t.get('pnl_pct') or 0):+.1f}%" if t.get("pnl_pct") else "—"
                    exit_p = f"${float(t['exit_price']):.2f}" if t.get("exit_price") else "—"
                    print(f"{t['id']:>4} {t['ticker']:<6} ${float(t['entry_price']):>8.2f} {exit_p:>10} {pnl:>8} {t['status']:<8}")

            elif args.trade_cmd == "pending-reviews":
                trades = db.get_trades_pending_review()
                if not trades:
                    print("No trades pending review")
                else:
                    print(f"\nTrades Pending Review ({len(trades)}):")
                    print(f"{'ID':>4} {'Ticker':<6} {'P/L':>8} {'Exit Date':<20}")
                    print("─" * 45)
                    for t in trades:
                        pnl = f"{float(t.get('pnl_pct') or 0):+.1f}%"
                        exit_dt = str(t.get("exit_date", ""))[:19]
                        print(f"{t['id']:>4} {t['ticker']:<6} {pnl:>8} {exit_dt:<20}")

            elif args.trade_cmd == "detected":
                # List trades created from detected position increases
                if args.show_all:
                    trades = db.get_trades_by_source_type(["detected", "confirmed"])
                else:
                    trades = db.get_trades_by_source_type(["detected"])

                if not trades:
                    print("No detected trades pending review")
                else:
                    print(f"\nDetected Trades ({len(trades)}):")
                    print(f"{'ID':>4} {'Ticker':<6} {'Date':<12} {'Size':>8} {'Price':>10} {'Status':<10}")
                    print("─" * 60)
                    for t in trades:
                        entry_dt = t.get("entry_date")
                        date_str = entry_dt.strftime("%Y-%m-%d") if entry_dt else "—"
                        size = float(t.get("entry_size") or 0)
                        price = float(t.get("entry_price") or 0)
                        src_type = t.get("source_type", "—")
                        print(f"{t['id']:>4} {t['ticker']:<6} {date_str:<12} {size:>8.2f} ${price:>8.2f} {src_type:<10}")

            elif args.trade_cmd == "confirm":
                # Confirm a detected trade entry
                trade = db.get_trade(args.trade_id)
                if not trade:
                    print(f"Trade {args.trade_id} not found")
                elif trade.get("source_type") != "detected":
                    print(f"Trade {args.trade_id} is not a detected trade (source: {trade.get('source_type')})")
                else:
                    updates = {"source_type": "confirmed"}
                    if args.thesis:
                        updates["thesis"] = args.thesis
                    if args.price:
                        updates["entry_price"] = args.price

                    db.update_trade(args.trade_id, **updates)
                    db.complete_task_by_type("review_detected_position", trade["ticker"])
                    print(f"Confirmed trade {args.trade_id}: {trade['ticker']}")

            elif args.trade_cmd == "reject":
                # Reject a detected trade entry (archive it)
                trade = db.get_trade(args.trade_id)
                if not trade:
                    print(f"Trade {args.trade_id} not found")
                elif trade.get("source_type") != "detected":
                    print(f"Trade {args.trade_id} is not a detected trade (source: {trade.get('source_type')})")
                else:
                    reason = args.reason or "Rejected by user"
                    db.archive_trade(args.trade_id, reason=reason)
                    db.complete_task_by_type("review_detected_position", trade["ticker"])
                    print(f"Rejected and archived trade {args.trade_id}: {trade['ticker']}")

            else:
                print("Usage: trade [add|close|list|pending-reviews|detected|confirm|reject]")

        # ─── Watchlist DB Commands ───────────────────────────────────────────────────
        elif args.cmd == "watchlist-db":
            if args.wl_cmd == "list":
                if args.status == "all":
                    with db.conn.cursor() as cur:
                        cur.execute("SELECT * FROM nexus.watchlist ORDER BY priority DESC, created_at DESC")
                        entries = [dict(r) for r in cur.fetchall()]
                else:
                    entries = db.get_active_watchlist()
                print(f"\n{'ID':>4} {'Ticker':<6} {'Priority':<8} {'Expires':<12} {'Trigger':<30}")
                print("─" * 70)
                for e in entries:
                    exp = e['expires_at'].strftime('%Y-%m-%d') if e.get('expires_at') else "—"
                    trigger = (e.get('entry_trigger') or "")[:28]
                    print(f"{e['id']:>4} {e['ticker']:<6} {e.get('priority', 'med'):<8} {exp:<12} {trigger:<30}")

            elif args.wl_cmd == "check":
                # Check for expired entries
                expired = db.get_expired_watchlist()
                for entry in expired:
                    db.update_watchlist_by_id(entry['id'], 'expired')
                    print(f"  ⏰ Expired: {entry['ticker']}")
                print(f"\n✅ Processed {len(expired)} expirations")

            elif args.wl_cmd == "process-expired":
                expired = db.get_expired_watchlist()
                for entry in expired:
                    db.update_watchlist_by_id(entry['id'], 'expired')
                    print(f"  ⏰ Marked expired: {entry['ticker']}")
                print(f"\n✅ Processed {len(expired)} entries")

            elif args.wl_cmd == "monitor":
                from watchlist_monitor import WatchlistMonitor, parse_trigger, ConditionType
                from ib_client import IBClient

                ib_client = IBClient()
                if not ib_client.health_check():
                    print("❌ IB MCP server not available at localhost:8100")
                    sys.exit(1)

                price_tolerance = float(cfg._get("watchlist_price_threshold_pct", "feature_flags", "0.5"))

                def event_handler(event):
                    """Print events to console."""
                    colors = {
                        "triggered": "\033[92m",  # Green
                        "invalidated": "\033[93m",  # Yellow
                        "expired": "\033[91m",  # Red
                        "error": "\033[91m"  # Red
                    }
                    reset = "\033[0m"
                    color = colors.get(event.event_type, "")
                    print(f"{color}[{event.event_type.upper()}] {event.ticker}: {event.reason}{reset}")

                monitor = WatchlistMonitor(
                    db=db,
                    ib_client=ib_client,
                    price_tolerance_pct=price_tolerance,
                    on_event=event_handler
                )

                print(f"Starting watchlist monitor (interval: {args.interval}s)")

                if args.once:
                    results = monitor.check_entries()
                    print(f"\nResults: {results}")
                else:
                    # Loop mode
                    import time
                    try:
                        while True:
                            results = monitor.check_entries()
                            if results.triggered or results.invalidated or results.expired or results.errors:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] {results}")
                            time.sleep(args.interval)
                    except KeyboardInterrupt:
                        print("\nMonitor stopped")

            elif args.wl_cmd == "pending-triggers":
                from watchlist_monitor import parse_trigger, ConditionType

                entries = db.get_active_watchlist()
                if not entries:
                    print("No active watchlist entries")
                else:
                    print(f"\nActive Watchlist Entries ({len(entries)}):\n")
                    print(f"{'Ticker':<6} {'Parseable':<10} {'Condition':<40} {'Expires':<12}")
                    print("─" * 75)

                    for entry in entries:
                        ticker = entry["ticker"]
                        trigger_text = entry.get("entry_trigger", "")
                        condition = parse_trigger(trigger_text) if trigger_text else None

                        # Format condition
                        if condition and condition.type != ConditionType.CUSTOM:
                            cond_str = f"{condition.type.value}: {condition.value}"
                            parseable = "✓"
                        else:
                            cond_str = trigger_text[:38] + ".." if len(trigger_text) > 40 else trigger_text
                            parseable = "✗ (manual)"

                        expires = entry.get("expires_at")
                        expires_str = str(expires)[:10] if expires else "never"

                        print(f"{ticker:<6} {parseable:<10} {cond_str:<40} {expires_str:<12}")

            else:
                print("Usage: watchlist-db [list|check|process-expired|monitor|pending-triggers]")

        elif args.cmd == "settings":
            if args.action == "list":
                all_settings = db.get_all_settings()
                cat = args.category
                print(f"\n{'Key':<35} {'Value':<25}")
                print("─" * 60)
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

        # ─── Options Commands (IPLAN-006) ─────────────────────────────────────────────
        elif args.cmd == "options":
            from expiration_monitor import ExpirationMonitor

            exp_monitor = ExpirationMonitor(db)

            if args.options_cmd == "list":
                options = db.get_options_positions()
                if not options:
                    print("No open options positions")
                else:
                    print(f"\n{'ID':>4} {'Symbol':<25} {'Type':<4} {'Strike':>8} {'Expires':<12} {'Days':>5} {'Size':>6}")
                    print("─" * 75)
                    for opt in options:
                        opt_type = opt.get("option_type", "?")[0].upper()
                        strike = float(opt.get("option_strike") or 0)
                        exp_date = str(opt.get("option_expiration", ""))[:10]
                        days = opt.get("days_to_expiry", "?")
                        size = float(opt.get("current_size") or opt.get("entry_size") or 0)
                        symbol = opt.get("full_symbol") or opt.get("ticker", "?")
                        print(f"{opt['id']:>4} {symbol:<25} {opt_type:<4} ${strike:>7.2f} {exp_date:<12} {days:>5} {size:>6.0f}")

            elif args.options_cmd == "expiring":
                days = args.days
                expiring = exp_monitor.get_expiring_soon(days)
                if not expiring:
                    print(f"No options expiring within {days} days")
                else:
                    print(f"\nOptions expiring within {days} days ({len(expiring)}):\n")
                    print(f"{'ID':>4} {'Symbol':<25} {'Type':<4} {'Strike':>8} {'Expires':<12} {'Days':>5}")
                    print("─" * 65)
                    for opt in expiring:
                        opt_type = opt.get("option_type", "?")[0].upper()
                        strike = float(opt.get("option_strike") or 0)
                        exp_date = str(opt.get("option_expiration", ""))[:10]
                        days_left = opt.get("days_to_expiry", "?")
                        symbol = opt.get("full_symbol") or opt.get("ticker", "?")
                        # Highlight critical (<=3 days)
                        prefix = "⚠️ " if isinstance(days_left, int) and days_left <= 3 else "  "
                        print(f"{prefix}{opt['id']:>4} {symbol:<25} {opt_type:<4} ${strike:>7.2f} {exp_date:<12} {days_left:>5}")

            elif args.options_cmd == "expired":
                expired = exp_monitor.get_expired()
                if not expired:
                    print("No expired options needing action")
                else:
                    print(f"\nExpired options ({len(expired)}):\n")
                    print(f"{'ID':>4} {'Symbol':<25} {'Type':<4} {'Strike':>8} {'Expired':<12}")
                    print("─" * 60)
                    for opt in expired:
                        opt_type = opt.get("option_type", "?")[0].upper()
                        strike = float(opt.get("option_strike") or 0)
                        exp_date = str(opt.get("option_expiration", ""))[:10]
                        symbol = opt.get("full_symbol") or opt.get("ticker", "?")
                        print(f"{opt['id']:>4} {symbol:<25} {opt_type:<4} ${strike:>7.2f} {exp_date:<12}")

            elif args.options_cmd == "process-expired":
                # Optional: get stock prices from IB for ITM detection
                get_price_fn = None
                try:
                    from ib_client import IBClient
                    ib = IBClient()
                    if ib.health_check():
                        def get_price_fn(ticker):
                            try:
                                quote = ib.get_stock_price(ticker)
                                return quote.get("last") if quote else None
                            except Exception:
                                return None
                except Exception:
                    print("Note: IB not available, using heuristics for ITM detection")

                results = exp_monitor.process_expirations(get_stock_price_fn=get_price_fn)
                print(f"\n✅ Processed expired options:")
                print(f"   Closed worthless: {results['expired_worthless']}")
                print(f"   Queued for review (ITM): {results['needs_review']}")
                if results['errors']:
                    print(f"   Errors: {results['errors']}")

            elif args.options_cmd == "by-underlying":
                ticker = args.ticker.upper()
                options = db.get_options_positions(underlying=ticker)
                if not options:
                    print(f"No open options for {ticker}")
                else:
                    print(f"\nOptions for {ticker} ({len(options)}):\n")
                    print(f"{'ID':>4} {'Symbol':<25} {'Type':<4} {'Strike':>8} {'Expires':<12} {'Days':>5} {'Size':>6}")
                    print("─" * 75)
                    for opt in options:
                        opt_type = opt.get("option_type", "?")[0].upper()
                        strike = float(opt.get("option_strike") or 0)
                        exp_date = str(opt.get("option_expiration", ""))[:10]
                        days = opt.get("days_to_expiry", "?")
                        size = float(opt.get("current_size") or opt.get("entry_size") or 0)
                        symbol = opt.get("full_symbol") or opt.get("ticker", "?")
                        print(f"{opt['id']:>4} {symbol:<25} {opt_type:<4} ${strike:>7.2f} {exp_date:<12} {days:>5} {size:>6.0f}")

            elif args.options_cmd == "summary":
                summary = exp_monitor.get_summary()
                print(f"\n{'═' * 40}")
                print("OPTIONS EXPIRATION SUMMARY")
                print(f"{'═' * 40}")
                print(f"  Expiring today:     {summary['expiring_today']:>4}")
                print(f"  Critical (≤3 days): {summary['critical']:>4}")
                print(f"  Warning (≤7 days):  {summary['warning']:>4}")
                print(f"  Expired (action):   {summary['expired']:>4}")

            else:
                print("Usage: options [list|expiring|expired|process-expired|by-underlying|summary]")

        # ─── Review Commands (IPLAN-001) ─────────────────────────────────────────────
        elif args.cmd == "review-earnings":
            if args.review_cmd == "run":
                ticker = args.ticker.upper()
                analysis_file = args.analysis

                if not analysis_file:
                    analysis_file = db.get_latest_earnings_analysis(ticker)

                if not analysis_file:
                    print(f"❌ No earnings analysis found for {ticker}")
                else:
                    # Queue the post-earnings review task
                    prompt = f"analysis_file: {analysis_file}"
                    task_id = db.queue_task("post_earnings_review", ticker, prompt=prompt, priority=8)
                    print(f"✅ Queued post-earnings review for {ticker} (task {task_id})")
                    print(f"   Analysis: {analysis_file}")
                    print("   Run: python tradegent.py process-queue")

            elif args.review_cmd == "pending":
                pending = db.get_pending_post_earnings_reviews()
                if not pending:
                    print("No pending post-earnings reviews")
                else:
                    print(f"\nPending Post-Earnings Reviews ({len(pending)}):\n")
                    print(f"{'Ticker':<8} {'Earnings':<12} {'Analysis Date':<20} {'File'}")
                    print("─" * 80)
                    for p in pending:
                        earnings = str(p.get("earnings_date", ""))[:10]
                        analysis_dt = str(p.get("current_analysis_date", ""))[:19]
                        file_short = p.get("current_analysis_file", "")[-40:]
                        print(f"{p['ticker']:<8} {earnings:<12} {analysis_dt:<20} ...{file_short}")

            elif args.review_cmd == "backfill":
                limit = args.limit
                dry_run = args.dry_run
                unreviewed = db.get_all_unreviewed_earnings_analyses()[:limit]

                if not unreviewed:
                    print("No unreviewed earnings analyses found")
                else:
                    print(f"\n{'Backfilling' if not dry_run else 'Would backfill'} {len(unreviewed)} analyses:\n")
                    for u in unreviewed:
                        ticker = u.get("ticker")
                        file_path = u.get("current_analysis_file")
                        if dry_run:
                            print(f"  [DRY-RUN] {ticker}: {file_path}")
                        else:
                            prompt = f"analysis_file: {file_path}"
                            task_id = db.queue_task("post_earnings_review", ticker, prompt=prompt, priority=5)
                            print(f"  ✓ Queued {ticker} (task {task_id})")

                    if not dry_run:
                        print(f"\n✅ Queued {len(unreviewed)} reviews. Run: python tradegent.py process-queue")

            else:
                print("Usage: review-earnings [run|pending|backfill]")

        elif args.cmd == "validate-analysis":
            if args.validation_cmd == "run":
                ticker = args.ticker.upper()
                new_file = args.new_file
                prior_file = args.prior_file

                if not prior_file:
                    lineage = db.get_active_analysis(ticker, "stock")
                    if not lineage:
                        lineage = db.get_active_analysis(ticker, "earnings")
                    if lineage:
                        prior_file = lineage["current_analysis_file"]

                if not prior_file:
                    print(f"❌ No prior analysis found for {ticker}")
                else:
                    prompt_lines = [f"prior_file: {prior_file}"]
                    if new_file:
                        prompt_lines.append(f"new_file: {new_file}")
                    prompt_lines.append("trigger: manual")

                    task_id = db.queue_task(
                        "report_validation", ticker,
                        prompt="\n".join(prompt_lines),
                        priority=8
                    )
                    print(f"✅ Queued report validation for {ticker} (task {task_id})")
                    print(f"   Prior: {prior_file}")
                    if new_file:
                        print(f"   New: {new_file}")
                    print("   Run: python tradegent.py process-queue")

            elif args.validation_cmd == "expired":
                expired = db.get_expired_forecasts()
                if not expired:
                    print("No expired forecasts")
                else:
                    print(f"\nExpired Forecasts ({len(expired)}):\n")
                    print(f"{'Ticker':<8} {'Type':<10} {'Valid Until':<12} {'Analysis Date':<20}")
                    print("─" * 60)
                    for e in expired:
                        valid_until = str(e.get("forecast_valid_until", ""))[:10]
                        analysis_dt = str(e.get("current_analysis_date", ""))[:19]
                        print(f"{e['ticker']:<8} {e['analysis_type']:<10} {valid_until:<12} {analysis_dt:<20}")

            elif args.validation_cmd == "process-expired":
                dry_run = args.dry_run
                expired = db.get_expired_forecasts()

                if not expired:
                    print("No expired forecasts to process")
                else:
                    print(f"\n{'Processing' if not dry_run else 'Would process'} {len(expired)} expired forecasts:\n")
                    for e in expired:
                        ticker = e["ticker"]
                        prior_file = e["current_analysis_file"]
                        if dry_run:
                            print(f"  [DRY-RUN] {ticker}: {prior_file}")
                        else:
                            prompt = f"prior_file: {prior_file}\ntrigger: forecast_expiry"
                            task_id = db.queue_task("report_validation", ticker, prompt=prompt, priority=6)
                            print(f"  ✓ Queued {ticker} (task {task_id})")

                    if not dry_run:
                        print(f"\n✅ Queued {len(expired)} validations. Run: python tradegent.py process-queue")

            else:
                print("Usage: validate-analysis [run|expired|process-expired]")

        elif args.cmd == "lineage":
            if args.lineage_cmd == "show":
                ticker = args.ticker.upper()
                limit = args.limit
                lineage = db.get_analysis_lineage(ticker, limit=limit)

                if not lineage:
                    print(f"No lineage found for {ticker}")
                else:
                    print(f"\nAnalysis Lineage for {ticker} ({len(lineage)} entries):\n")
                    print(f"{'ID':>4} {'Type':<10} {'Status':<12} {'Date':<12} {'Grade':<6} {'Validation'}")
                    print("─" * 70)
                    for l in lineage:
                        status = l.get("current_status", "?")
                        date_str = str(l.get("current_analysis_date", ""))[:10]
                        grade = l.get("post_earnings_grade") or "—"
                        val_result = l.get("validation_result") or "—"
                        print(f"{l['id']:>4} {l['analysis_type']:<10} {status:<12} {date_str:<12} {grade:<6} {val_result}")

            elif args.lineage_cmd == "active":
                with db.conn.cursor() as cur:
                    cur.execute("""
                        SELECT ticker, analysis_type, current_status, current_analysis_date,
                               forecast_valid_until, earnings_date
                        FROM nexus.analysis_lineage
                        WHERE current_status = 'active'
                        ORDER BY current_analysis_date DESC
                    """)
                    active = [dict(r) for r in cur.fetchall()]

                if not active:
                    print("No active analyses")
                else:
                    print(f"\nActive Analyses ({len(active)}):\n")
                    print(f"{'Ticker':<8} {'Type':<10} {'Date':<12} {'Valid Until':<12} {'Earnings'}")
                    print("─" * 60)
                    for a in active:
                        date_str = str(a.get("current_analysis_date", ""))[:10]
                        valid = str(a.get("forecast_valid_until") or "—")[:10]
                        earnings = str(a.get("earnings_date") or "—")[:10]
                        print(f"{a['ticker']:<8} {a['analysis_type']:<10} {date_str:<12} {valid:<12} {earnings}")

            elif args.lineage_cmd == "invalidated":
                with db.conn.cursor() as cur:
                    cur.execute("""
                        SELECT ticker, analysis_type, current_status, validation_result,
                               current_analysis_date, updated_at
                        FROM nexus.analysis_lineage
                        WHERE current_status = 'invalidated'
                        ORDER BY updated_at DESC
                        LIMIT 20
                    """)
                    invalidated = [dict(r) for r in cur.fetchall()]

                if not invalidated:
                    print("No invalidated analyses")
                else:
                    print(f"\nInvalidated Analyses ({len(invalidated)}):\n")
                    print(f"{'Ticker':<8} {'Type':<10} {'Result':<12} {'Analysis Date':<12} {'Invalidated'}")
                    print("─" * 65)
                    for i in invalidated:
                        date_str = str(i.get("current_analysis_date", ""))[:10]
                        inv_date = str(i.get("updated_at", ""))[:10]
                        result = i.get("validation_result") or "—"
                        print(f"{i['ticker']:<8} {i['analysis_type']:<10} {result:<12} {date_str:<12} {inv_date}")

            else:
                print("Usage: lineage [show|active|invalidated]")

        elif args.cmd == "calibration":
            if args.calibration_cmd == "summary":
                stats = db.get_calibration_stats()
                if not stats:
                    print("No calibration data yet")
                else:
                    print(f"\nConfidence Calibration Summary:\n")
                    print(f"{'Bucket':<8} {'Total':>8} {'Correct':>8} {'Rate':>8} {'Expected':>10}")
                    print("─" * 50)
                    for s in stats:
                        bucket = s["confidence_bucket"]
                        total = s["total_predictions"]
                        correct = s["correct_predictions"]
                        actual = float(s["actual_rate"] or 0)
                        expected_low = bucket
                        expected_high = bucket + 9
                        calibrated = "✓" if expected_low <= actual <= expected_high else "✗"
                        print(f"{bucket}-{bucket+9}%{'':<2} {total:>8} {correct:>8} {actual:>7.1f}% {expected_low}-{expected_high}% {calibrated}")

            elif args.calibration_cmd == "ticker":
                ticker = args.ticker.upper()
                analysis_type = args.analysis_type
                stats = db.get_ticker_calibration(ticker, analysis_type)
                if not stats:
                    print(f"No calibration data for {ticker} ({analysis_type})")
                else:
                    print(f"\nCalibration for {ticker} ({analysis_type}):\n")
                    print(f"{'Bucket':<8} {'Total':>8} {'Correct':>8} {'Rate':>8}")
                    print("─" * 40)
                    for s in stats:
                        bucket = s["confidence_bucket"]
                        total = s["total_predictions"]
                        correct = s["correct_predictions"]
                        actual = float(s["actual_rate"] or 0)
                        print(f"{bucket}-{bucket+9}%{'':<2} {total:>8} {correct:>8} {actual:>7.1f}%")

            else:
                print("Usage: calibration [summary|ticker]")

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
