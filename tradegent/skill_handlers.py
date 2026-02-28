"""
Skill invocation infrastructure for monitoring integration.

Provides handlers for both Python-only skills (free) and Claude Code skills (paid).
Tracks all invocations for cost monitoring and debugging.

Skills implemented:
- detected-position: Claude Code or Python (creates trade entry for externally-added positions)
- options-management: Claude Code or Python (manages expiring options)
- fill-analysis: Python only (analyzes fill quality)
- position-close-review: Python only (reviews closed positions, queues full review)
- expiration-review: Python + optional Claude (reviews expired options)
"""

import logging
import re
import subprocess
from datetime import datetime
from decimal import Decimal
from typing import Any

log = logging.getLogger(__name__)


# =============================================================================
# Logging Helpers
# =============================================================================

def _get_today_skill_cost(db) -> float:
    """Get total Claude Code cost for today."""
    with db.conn.cursor() as cur:
        cur.execute("""
            SELECT COALESCE(SUM(cost_estimate), 0)
            FROM nexus.skill_invocations
            WHERE invocation_type = 'claude_code'
            AND started_at >= CURRENT_DATE
            AND status = 'completed'
        """)
        return float(cur.fetchone()[0])


def _log_skill_start(
    db,
    skill_name: str,
    ticker: str | None,
    invocation_type: str,
    cost_estimate: float = 0,
    trigger_source: str | None = None,
    task_id: int | None = None
) -> int:
    """Log skill invocation start. Returns invocation ID."""
    with db.conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nexus.skill_invocations
            (skill_name, ticker, invocation_type, cost_estimate, trigger_source, task_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (skill_name, ticker, invocation_type, cost_estimate, trigger_source, task_id))
        inv_id = cur.fetchone()["id"]
        db.conn.commit()
        return inv_id


def _log_skill_complete(db, invocation_id: int, output_path: str | None):
    """Log skill invocation completion."""
    with db.conn.cursor() as cur:
        cur.execute("""
            UPDATE nexus.skill_invocations
            SET status = 'completed', completed_at = NOW(), output_path = %s
            WHERE id = %s
        """, (output_path, invocation_id))
        db.conn.commit()


def _log_skill_error(db, invocation_id: int, error_message: str):
    """Log skill invocation error."""
    with db.conn.cursor() as cur:
        cur.execute("""
            UPDATE nexus.skill_invocations
            SET status = 'failed', completed_at = NOW(), error_message = %s
            WHERE id = %s
        """, (error_message[:1000], invocation_id))  # Truncate long errors
        db.conn.commit()


# =============================================================================
# Context Parsing Helpers
# =============================================================================

def _parse_detected_position_prompt(prompt: str) -> dict:
    """Parse position detection prompt into context dict.

    Expected formats:
    - "Position detected: NVDA +100 @ $145.00"
    - "Position detected: NVDA +100"
    """
    context = {"size": 0, "price": 0.0, "source": "position_monitor"}

    # Match pattern: "TICKER +/-SIZE @ $PRICE"
    match = re.search(r'([A-Z]+)\s+([+-]?\d+)\s*(?:@\s*\$?([\d.]+))?', prompt)
    if match:
        context["ticker"] = match.group(1)
        context["size"] = abs(int(match.group(2)))
        if match.group(3):
            context["price"] = float(match.group(3))

    return context


def _extract_output_path(result: str) -> str | None:
    """Extract output file path from Claude Code result.

    Looks for patterns like:
    - "Saved to tradegent_knowledge/knowledge/..."
    - "Output: /path/to/file.yaml"
    """
    patterns = [
        r'[Ss]aved to\s+([^\s]+\.yaml)',
        r'[Oo]utput:\s+([^\s]+\.yaml)',
        r'(tradegent_knowledge/knowledge/[^\s]+\.yaml)',
    ]

    for pattern in patterns:
        match = re.search(pattern, result)
        if match:
            return match.group(1)

    return None


# =============================================================================
# Claude Code CLI Invocation
# =============================================================================

def call_claude_code(
    prompt: str,
    allowed_tools: list[str] | None = None,
    timeout: int = 300
) -> str:
    """Call Claude Code CLI with a prompt.

    Args:
        prompt: The task prompt for Claude Code
        allowed_tools: List of tool patterns to allow (e.g., ["mcp__ib-mcp__*"])
        timeout: Timeout in seconds (default 5 minutes)

    Returns:
        Claude Code output as string

    Raises:
        subprocess.TimeoutExpired: If execution exceeds timeout
        subprocess.CalledProcessError: If Claude Code returns non-zero exit
    """
    cmd = ["claude", "--print", "--dangerously-skip-permissions"]

    if allowed_tools:
        for tool in allowed_tools:
            cmd.extend(["--allowedTools", tool])

    cmd.extend(["--prompt", prompt])

    log.info(f"Invoking Claude Code: {prompt[:100]}...")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd="/opt/data/tradegent_swarm"
    )

    if result.returncode != 0:
        log.error(f"Claude Code failed: {result.stderr}")
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )

    return result.stdout


# =============================================================================
# Skill Invocation Entry Points
# =============================================================================

def invoke_skill_python(db, skill_name: str, context: dict, task_id: int | None = None) -> dict:
    """Invoke skill using Python implementation (free).

    Args:
        db: NexusDB instance
        skill_name: Name of the skill to invoke
        context: Context dict with ticker and other parameters
        task_id: Optional task ID for tracking

    Returns:
        Result dict from the skill handler
    """
    invocation_id = _log_skill_start(
        db, skill_name, context.get("ticker"), "python",
        trigger_source=context.get("source"), task_id=task_id
    )

    try:
        # Import handlers dynamically to avoid circular imports
        handlers = _get_python_handlers()

        handler = handlers.get(skill_name)
        if not handler:
            raise ValueError(f"No Python handler for skill: {skill_name}")

        result = handler(db, context)
        _log_skill_complete(db, invocation_id, result.get("output_path"))
        return result

    except Exception as e:
        _log_skill_error(db, invocation_id, str(e))
        raise


def invoke_skill_claude(db, skill_name: str, context: dict, task_id: int | None = None) -> dict:
    """Invoke skill using Claude Code CLI (costs $0.20-0.45).

    Args:
        db: NexusDB instance
        skill_name: Name of the skill to invoke
        context: Context dict with ticker and other parameters
        task_id: Optional task ID for tracking

    Returns:
        Result dict with output and output_path

    Raises:
        ValueError: If daily cost limit reached
    """
    # Check daily cost limit
    today_cost = _get_today_skill_cost(db)
    limit = float(db.get_setting("skill_daily_cost_limit", "5.00"))

    if today_cost >= limit:
        log.warning(f"Skill cost limit reached: ${today_cost:.2f} >= ${limit:.2f}")
        raise ValueError(f"Daily skill cost limit reached (${today_cost:.2f} >= ${limit:.2f})")

    invocation_id = _log_skill_start(
        db, skill_name, context.get("ticker"), "claude_code",
        cost_estimate=0.30, trigger_source=context.get("source"), task_id=task_id
    )

    try:
        # Build prompt with context
        prompt = _build_skill_prompt(skill_name, context)

        # Call Claude Code CLI
        result = call_claude_code(
            prompt=prompt,
            allowed_tools=["mcp__ib-mcp__*", "rag_*", "graph_*", "Write", "Read"],
            timeout=300
        )

        output_path = _extract_output_path(result)
        _log_skill_complete(db, invocation_id, output_path)
        return {"output": result, "output_path": output_path}

    except Exception as e:
        _log_skill_error(db, invocation_id, str(e))
        raise


def _build_skill_prompt(skill_name: str, context: dict) -> str:
    """Build prompt for Claude Code skill invocation."""
    ticker = context.get("ticker", "UNKNOWN")

    prompts = {
        "detected-position": f"""
Invoke the detected-position skill for {ticker}.

Context:
- Position Size: {context.get('size', 'unknown')}
- Entry Price: ${context.get('price', 'unknown')}
- Detection Source: {context.get('source', 'position_monitor')}

Follow the detected-position skill workflow:
1. Get position details from IB MCP
2. Search for related analysis/watchlist entries
3. Determine if planned (watchlist) or unplanned entry
4. Create trade-journal entry
5. Set stop loss and targets
6. Save to tradegent_knowledge/knowledge/trades/
""",
        "options-management": f"""
Invoke the options-management skill for {ticker}.

Context:
- Days to Expiration: {context.get('dte', 'unknown')}
- Current Status: {context.get('status', 'unknown')}
- Trigger: {context.get('trigger', 'expiration_warning')}

Follow the options-management skill workflow:
1. Get all options positions from IB MCP
2. Analyze ITM/OTM status and Greeks
3. Generate recommendations (hold/close/roll/exercise)
4. For rolls, calculate cost/credit
5. Output summary with action items
""",
        "expiration-review": f"""
Invoke the expiration-review skill for {ticker}.

Context:
- Outcome: {context.get('outcome', 'unknown')}
- P&L: ${context.get('pnl', 'unknown')}

Extract lessons learned from this options trade:
1. What went right or wrong?
2. Was timing appropriate?
3. Was strike selection correct?
4. What would you do differently?
""",
    }

    return prompts.get(skill_name, f"Invoke {skill_name} skill for {ticker}")


def _get_python_handlers() -> dict:
    """Get mapping of skill names to Python handler functions.

    Returns dict lazily to avoid circular imports at module load time.
    """
    return {
        "fill-analysis": python_fill_analysis,
        "position-close-review": python_position_close_review,
        "expiration-review": python_expiration_review,
        "detected-position": python_detected_position_basic,
        "options-management": python_options_summary,
    }


# =============================================================================
# Python Skill Handlers
# =============================================================================

def python_detected_position_basic(db, context: dict) -> dict:
    """Basic Python handler for detected positions.

    Creates a minimal trade entry in the database for externally-detected positions.
    """
    ticker = context.get("ticker")
    size = context.get("size", 0)
    price = context.get("price", 0)

    if not ticker:
        log.warning("No ticker in detected position context")
        return {"status": "error", "error": "No ticker provided"}

    # Create minimal trade entry
    with db.conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nexus.trades (
                ticker, entry_date, entry_price, entry_size, entry_type,
                status, thesis, source_analysis, source_type
            ) VALUES (
                %s, NOW(), %s, %s, 'stock',
                'open', 'Externally detected position - needs review', 'position_monitor', 'detected'
            ) RETURNING id
        """, (ticker.upper(), price, size))
        trade_id = cur.fetchone()["id"]
        db.conn.commit()

    log.info(f"Created basic trade entry {trade_id} for detected {ticker} position")
    return {"trade_id": trade_id, "status": "created_basic"}


def python_options_summary(db, context: dict) -> dict:
    """Basic Python handler for options summary.

    Lists options positions with basic metrics without AI analysis.
    """
    from options_utils import parse_option_symbol

    # Get positions from IB via existing method
    try:
        from ib_client import IBClient
        ib = IBClient()
        positions = ib.get_positions()
    except Exception as e:
        log.warning(f"Could not get IB positions: {e}")
        positions = []

    options_positions = []
    for pos in positions:
        symbol = pos.get("symbol", "")
        parsed = parse_option_symbol(symbol)
        if parsed:
            options_positions.append({
                "symbol": symbol,
                "underlying": parsed.underlying,
                "expiration": parsed.expiration.isoformat(),
                "strike": float(parsed.strike),
                "option_type": parsed.option_type,
                "size": pos.get("position", 0),
                "avg_cost": pos.get("avgCost", 0),
                "days_to_expiry": parsed.days_to_expiry,
            })

    log.info(f"Options summary: {len(options_positions)} positions found")
    for opt in options_positions:
        log.info(f"  {opt['symbol']}: {opt['size']} @ ${opt['avg_cost']:.2f}, DTE: {opt['days_to_expiry']}")

    return {"positions": options_positions, "status": "summary_only", "count": len(options_positions)}


def python_fill_analysis(db, context: dict) -> dict:
    """Analyze fill quality.

    Calculates slippage and grades the execution quality.
    """
    ticker = context.get("ticker")
    order_id = context.get("order_id")

    # Get executions from IB
    try:
        from ib_client import IBClient
        ib = IBClient()
        executions = ib.get_executions()
    except Exception as e:
        log.warning(f"Could not get IB executions: {e}")
        return {"status": "error", "error": str(e)}

    # Find relevant execution
    execution = None
    for ex in executions:
        if order_id and str(ex.get("orderId")) == str(order_id):
            execution = ex
            break
        elif ticker and ex.get("symbol") == ticker:
            execution = ex
            break

    if not execution:
        log.warning(f"No execution found for {ticker or order_id}")
        return {"status": "not_found"}

    # Calculate metrics
    fill_price = Decimal(str(execution.get("avgPrice", 0)))
    exec_ticker = execution.get("symbol", ticker)

    # Get current quote for spread calculation
    try:
        quote = ib.get_stock_price(exec_ticker)
    except Exception:
        quote = None

    if quote:
        bid = Decimal(str(quote.get("bid", 0)))
        ask = Decimal(str(quote.get("ask", 0)))
        mid = (bid + ask) / 2 if bid and ask else fill_price

        slippage = fill_price - mid
        slippage_pct = (slippage / mid * 100) if mid else Decimal("0")

        # Grade
        if abs(slippage_pct) < Decimal("0.1"):
            grade = "A"
        elif abs(slippage_pct) < Decimal("0.25"):
            grade = "B"
        elif abs(slippage_pct) < Decimal("0.5"):
            grade = "C"
        elif abs(slippage_pct) < Decimal("1.0"):
            grade = "D"
        else:
            grade = "F"
    else:
        slippage = Decimal("0")
        slippage_pct = Decimal("0")
        grade = "N/A"

    result = {
        "ticker": exec_ticker,
        "fill_price": float(fill_price),
        "slippage": float(slippage),
        "slippage_pct": float(slippage_pct),
        "grade": grade,
        "status": "analyzed"
    }

    log.info(f"Fill analysis: {result['ticker']} @ ${result['fill_price']:.2f}, "
             f"slippage {result['slippage_pct']:.2f}%, grade {grade}")

    # Update trade if exists and entry_price is missing
    with db.conn.cursor() as cur:
        cur.execute("""
            UPDATE nexus.trades
            SET entry_price = %s
            WHERE ticker = %s AND status = 'open'
            AND (entry_price IS NULL OR entry_price = 0)
        """, (float(fill_price), result["ticker"]))
        db.conn.commit()

    return result


def python_position_close_review(db, context: dict) -> dict:
    """Review closed position and queue full review if significant.

    A trade is significant if:
    - P&L > $100 (either direction)
    - Holding period > 3 days
    """
    ticker = context.get("ticker")

    if not ticker:
        return {"status": "error", "error": "No ticker provided"}

    # Find the most recently closed trade
    with db.conn.cursor() as cur:
        cur.execute("""
            SELECT id, entry_price, entry_size, entry_date, exit_date, exit_price,
                   pnl_dollars, pnl_pct
            FROM nexus.trades
            WHERE ticker = %s AND status = 'closed'
            ORDER BY exit_date DESC NULLS LAST
            LIMIT 1
        """, (ticker.upper(),))
        row = cur.fetchone()

    if not row:
        log.warning(f"No closed trade found for {ticker}")
        return {"status": "not_found"}

    trade = dict(row)
    trade_id = trade["id"]
    entry_date = trade["entry_date"]
    pnl_dollars = float(trade["pnl_dollars"] or 0)
    pnl_pct = float(trade["pnl_pct"] or 0)

    # Calculate holding period
    if entry_date:
        holding_days = (datetime.now(entry_date.tzinfo) - entry_date).days
    else:
        holding_days = 0

    # Determine if significant
    is_significant = abs(pnl_dollars) > 100 or holding_days > 3

    result = {
        "trade_id": trade_id,
        "ticker": ticker,
        "pnl_dollars": pnl_dollars,
        "pnl_pct": pnl_pct,
        "holding_days": holding_days,
        "is_significant": is_significant,
        "status": "reviewed"
    }

    log.info(f"Position close review: {ticker} P&L ${pnl_dollars:.2f} ({pnl_pct:.1f}%), "
             f"held {holding_days} days, significant={is_significant}")

    # Queue full review if significant
    if is_significant:
        task_id = db.queue_task(
            task_type="post_trade_review",
            ticker=ticker,
            prompt=f"Review closed {ticker} trade: ${pnl_dollars:.2f} ({pnl_pct:.1f}%)",
            priority=6,
            cooldown_key=f"post_trade_review:{ticker}",
            cooldown_hours=24
        )
        if task_id:
            log.info(f"  -> Queued post-trade review (task {task_id})")
            result["queued_review"] = task_id
        else:
            log.info(f"  -> Post-trade review already queued (cooldown)")

    return result


def python_expiration_review(db, context: dict) -> dict:
    """Review expired option and calculate final P&L.

    Handles different expiration outcomes:
    - expired_worthless (long): -premium paid
    - expired_worthless (short): +premium received
    - assigned/exercised: requires more complex calculation
    """
    ticker = context.get("ticker")  # This might be the full OCC symbol

    if not ticker:
        return {"status": "error", "error": "No ticker provided"}

    from options_utils import parse_option_symbol

    parsed = parse_option_symbol(ticker)
    underlying = parsed.underlying if parsed else ticker

    # Find the trade
    with db.conn.cursor() as cur:
        # Try to find by full_symbol first (for options), then by ticker
        cur.execute("""
            SELECT id, entry_price, entry_size, entry_type, exit_reason,
                   is_credit, option_multiplier
            FROM nexus.trades
            WHERE (full_symbol = %s OR ticker = %s) AND status = 'closed'
            AND exit_reason IN ('expired_worthless', 'assigned', 'exercised')
            ORDER BY exit_date DESC
            LIMIT 1
        """, (ticker, ticker))
        row = cur.fetchone()

    if not row:
        log.warning(f"No expired trade found for {ticker}")
        return {"status": "not_found"}

    trade = dict(row)
    trade_id = trade["id"]
    entry_price = float(trade["entry_price"] or 0)
    entry_size = float(trade["entry_size"] or 0)
    entry_type = trade["entry_type"]
    exit_reason = trade["exit_reason"]
    is_credit = trade.get("is_credit", False)
    multiplier = int(trade.get("option_multiplier") or 100)

    # Calculate P&L based on outcome
    if exit_reason == "expired_worthless":
        if is_credit or entry_type in ("short_call", "short_put"):
            # Short option expired worthless = keep premium
            pnl = entry_price * entry_size * multiplier
        else:
            # Long option expired worthless = lose premium
            pnl = -entry_price * entry_size * multiplier
    else:
        # Assignment/exercise - would need more data (strike, current price)
        pnl = 0  # Placeholder - actual P&L should be calculated by expiration_monitor

    result = {
        "trade_id": trade_id,
        "ticker": ticker,
        "underlying": underlying,
        "outcome": exit_reason,
        "pnl": pnl,
        "is_credit": is_credit,
        "status": "reviewed"
    }

    log.info(f"Expiration review: {ticker} {exit_reason}, P&L ${pnl:.2f}")

    return result
