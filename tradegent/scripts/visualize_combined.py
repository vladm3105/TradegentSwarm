#!/usr/bin/env python3
"""
Combined Stock + Earnings Analysis SVG Visualization Generator

Generates professional SVG dashboard combining stock and earnings analysis.
Auto-detects if earnings analysis exists and creates appropriate layout.

Usage:
    python scripts/visualize_combined.py TICKER
    python scripts/visualize_combined.py TICKER --output custom.svg
    python scripts/visualize_combined.py --stock stock.yaml --earnings earnings.yaml
"""

import sys
import argparse
import json
import math
from pathlib import Path
from datetime import datetime
from typing import Optional

import yaml


def load_analysis(file_path: str) -> dict:
    """Load and parse YAML analysis file."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


def find_latest_analysis(ticker: str, analysis_type: str) -> Optional[Path]:
    """Find the latest analysis file for a ticker."""
    base_path = Path(__file__).parent.parent.parent / "tradegent_knowledge" / "knowledge" / "analysis"
    folder = base_path / analysis_type

    if not folder.exists():
        return None

    files = sorted(folder.glob(f"{ticker}_*.yaml"), reverse=True)
    return files[0] if files else None


def get_recommendation_color(rec: str) -> tuple:
    """Get background and text colors for recommendation badge."""
    colors = {
        'STRONG_BUY': ('#2f9e44', '#fff'),
        'BUY': ('#51cf66', '#212529'),
        'BULLISH': ('#51cf66', '#212529'),
        'WATCH': ('#ffd43b', '#212529'),
        'NEUTRAL': ('#868e96', '#fff'),
        'NO_POSITION': ('#495057', '#ffd43b'),
        'BEARISH': ('#ff8787', '#212529'),
        'AVOID': ('#ff6b6b', '#fff'),
        'STRONG_SELL': ('#c92a2a', '#fff'),
    }
    return colors.get(rec.upper().replace(' ', '_'), ('#495057', '#ffd43b'))


def get_gate_color(passed: bool) -> str:
    """Get color for gate result."""
    return '#51cf66' if passed else '#ff6b6b'


def escape_xml(text: str) -> str:
    """Escape XML special characters."""
    if not text:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def format_number(value, prefix='', suffix='', decimals=2) -> str:
    """Format number with prefix/suffix."""
    if value is None:
        return 'N/A'
    if isinstance(value, str):
        return value
    if abs(value) >= 1e9:
        return f"{prefix}{value/1e9:.1f}B{suffix}"
    if abs(value) >= 1e6:
        return f"{prefix}{value/1e6:.1f}M{suffix}"
    if abs(value) >= 1e3:
        return f"{prefix}{value/1e3:.1f}K{suffix}"
    return f"{prefix}{value:.{decimals}f}{suffix}"


def generate_stock_only_svg(stock_data: dict, source_file: str = '') -> str:
    """Generate stock-only SVG (delegates to existing script logic)."""
    # Import and use existing visualize_analysis logic
    from visualize_analysis import generate_svg
    return generate_svg(stock_data, source_file)


def generate_combined_svg(stock_data: dict, earnings_data: dict,
                          stock_file: str = '', earnings_file: str = '') -> str:
    """Generate combined stock + earnings SVG visualization."""

    # ═══════════════════════════════════════════════════════════════════════════
    # EXTRACT STOCK DATA
    # ═══════════════════════════════════════════════════════════════════════════
    s_meta = stock_data.get('_meta', {})
    ticker = stock_data.get('ticker', s_meta.get('ticker', 'N/A'))
    company_name = stock_data.get('company_name', ticker)
    s_version = str(s_meta.get('version', '2.6'))

    # Stock decision
    s_decision = stock_data.get('decision', {})
    s_recommendation = s_decision.get('recommendation', stock_data.get('recommendation', 'NEUTRAL'))
    s_confidence = s_decision.get('confidence_pct', 50)

    # Stock price
    s_price = stock_data.get('current_price', 0)
    s_valuation = stock_data.get('valuation', {})
    forward_pe = s_valuation.get('forward_pe', 'N/A')
    market_cap = s_valuation.get('market_cap_b', 0)

    # Stock gate
    s_gate = stock_data.get('do_nothing_gate', {})
    s_gate_result = s_gate.get('gate_result', 'FAIL')
    s_gates_passed = s_gate.get('gates_passed', 0)
    s_ev = s_gate.get('ev_actual', 0)

    # Stock scenarios
    s_scenarios = stock_data.get('scenarios', {})
    s_expected_value = s_scenarios.get('expected_value', 0)
    if isinstance(s_expected_value, dict):
        s_expected_value = s_expected_value.get('total', 0)

    # ═══════════════════════════════════════════════════════════════════════════
    # EXTRACT EARNINGS DATA
    # ═══════════════════════════════════════════════════════════════════════════
    e_meta = earnings_data.get('_meta', {})
    e_version = str(e_meta.get('version', '2.5'))

    earnings_date = earnings_data.get('earnings_date', '')
    earnings_time = earnings_data.get('earnings_time', 'AMC')
    days_to_earnings = earnings_data.get('days_to_earnings', 0)

    # Earnings decision
    e_decision = earnings_data.get('decision', {})
    e_recommendation = e_decision.get('recommendation', earnings_data.get('recommendation', 'NEUTRAL'))
    e_confidence = e_decision.get('confidence_pct', earnings_data.get('probability', {}).get('confidence_pct', 50))

    # Earnings probability
    probability = earnings_data.get('probability', {})
    p_beat = probability.get('final_probability', {}).get('p_beat', 50)

    # Beat history
    prep = earnings_data.get('preparation', {})
    beat_history = prep.get('beat_history', {})
    beats = beat_history.get('beats', 0)
    misses = beat_history.get('misses', 0)
    beat_rate = beat_history.get('beat_rate', 0)

    # Implied move
    implied_move = earnings_data.get('historical_moves', {}).get('current_implied_move_pct',
                   prep.get('implied_move', {}).get('percentage', 0))

    # Earnings gate
    e_gate = earnings_data.get('do_nothing_gate', {})
    e_gate_result = e_gate.get('gate_result', 'FAIL')
    e_gates_passed = e_gate.get('gates_passed', 0)
    e_ev = earnings_data.get('scenarios', {}).get('expected_value', 0)

    # Earnings scenarios
    e_scenarios = earnings_data.get('scenarios', {})

    # Historical moves
    historical = earnings_data.get('historical_moves', {})
    quarters = historical.get('quarters', [])[:4]
    avg_move = historical.get('average_move_pct', 0)

    # Expectations
    expectations = earnings_data.get('expectations_assessment', {})
    priced_for_perfection = expectations.get('priced_for_perfection', False)
    sell_the_news_risk = expectations.get('sell_the_news_risk', 'medium')

    # ═══════════════════════════════════════════════════════════════════════════
    # GENERATE COMBINED SVG (1200 x 800)
    # ═══════════════════════════════════════════════════════════════════════════

    s_rec_bg, s_rec_text = get_recommendation_color(s_recommendation)
    e_rec_bg, e_rec_text = get_recommendation_color(e_recommendation)

    # Gate logic
    s_do_nothing_passes = s_gate_result != 'PASS'
    s_open_trade_passes = s_gate_result == 'PASS'
    e_do_nothing_passes = e_gate_result != 'PASS'
    e_open_trade_passes = e_gate_result == 'PASS'

    svg_parts = []

    # ─── HEADER ────────────────────────────────────────────────────────────────
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 800" width="1200" height="800">
  <defs>
    <style>
      .title {{ font: bold 24px system-ui, sans-serif; fill: #212529; }}
      .subtitle {{ font: 14px system-ui, sans-serif; fill: #495057; }}
      .section-title {{ font: bold 12px system-ui, sans-serif; fill: #495057; text-transform: uppercase; letter-spacing: 0.5px; }}
      .label {{ font: 11px system-ui, sans-serif; fill: #495057; }}
      .value {{ font: bold 13px system-ui, sans-serif; fill: #212529; }}
      .small {{ font: 10px system-ui, sans-serif; fill: #868e96; }}
      .metric-label {{ font: 10px system-ui, sans-serif; fill: #868e96; }}
      .metric-value {{ font: bold 16px system-ui, sans-serif; fill: #212529; }}
    </style>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.1"/>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="1200" height="800" fill="#f8f9fa" rx="8"/>

  <!-- Header -->
  <rect x="20" y="20" width="1160" height="80" fill="#fff" rx="8" filter="url(#shadow)"/>
  <text x="40" y="55" class="title">{escape_xml(ticker)} Combined Analysis</text>
  <text x="40" y="75" class="subtitle">{escape_xml(company_name)} | Stock v{s_version} + Earnings v{e_version}</text>

  <!-- Earnings countdown -->
  <rect x="400" y="35" width="150" height="50" fill="#e7f5ff" rx="6" stroke="#74c0fc" stroke-width="1"/>
  <text x="475" y="55" text-anchor="middle" font-size="11" fill="#1971c2">EARNINGS</text>
  <text x="475" y="72" text-anchor="middle" font-size="14" font-weight="bold" fill="#1864ab">{earnings_date} {earnings_time} (T-{days_to_earnings})</text>

  <!-- Stock Recommendation Badge -->
  <rect x="900" y="30" width="120" height="60" fill="{s_rec_bg}" rx="8"/>
  <text x="960" y="50" text-anchor="middle" fill="{s_rec_text}" font-size="10">STOCK</text>
  <text x="960" y="68" text-anchor="middle" fill="{s_rec_text}" font-size="14" font-weight="bold">{escape_xml(s_recommendation)}</text>
  <text x="960" y="82" text-anchor="middle" fill="{s_rec_text}" font-size="11">{s_confidence}%</text>

  <!-- Earnings Recommendation Badge -->
  <rect x="1040" y="30" width="120" height="60" fill="{e_rec_bg}" rx="8"/>
  <text x="1100" y="50" text-anchor="middle" fill="{e_rec_text}" font-size="10">EARNINGS</text>
  <text x="1100" y="68" text-anchor="middle" fill="{e_rec_text}" font-size="14" font-weight="bold">{escape_xml(e_recommendation)}</text>
  <text x="1100" y="82" text-anchor="middle" fill="{e_rec_text}" font-size="11">{e_confidence}%</text>
''')

    # ─── LEFT COLUMN: STOCK ANALYSIS ───────────────────────────────────────────
    svg_parts.append(f'''
  <!-- LEFT COLUMN: STOCK ANALYSIS -->
  <rect x="20" y="120" width="570" height="320" fill="#fff" rx="8" filter="url(#shadow)"/>
  <text x="40" y="145" class="section-title">STOCK ANALYSIS</text>

  <!-- Price and Valuation -->
  <text x="40" y="175" class="metric-label">Current Price</text>
  <text x="40" y="200" class="metric-value" font-size="24">${s_price:.2f}</text>

  <text x="180" y="175" class="metric-label">Forward P/E</text>
  <text x="180" y="200" class="metric-value">{forward_pe}x</text>

  <text x="280" y="175" class="metric-label">Market Cap</text>
  <text x="280" y="200" class="metric-value">${market_cap:.1f}B</text>

  <!-- Stock Gate Section -->
  <text x="40" y="235" class="section-title">GATES</text>

  <text x="40" y="260" class="small">Do Nothing</text>
  <rect x="40" y="265" width="60" height="20" fill="{get_gate_color(s_do_nothing_passes)}" rx="10"/>
  <text x="70" y="279" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">{'PASS' if s_do_nothing_passes else 'FAIL'}</text>

  <text x="120" y="260" class="small">Open Trade</text>
  <rect x="120" y="265" width="60" height="20" fill="{get_gate_color(s_open_trade_passes)}" rx="10"/>
  <text x="150" y="279" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">{'PASS' if s_open_trade_passes else 'FAIL'}</text>

  <text x="200" y="260" class="small">Criteria</text>
  <rect x="200" y="265" width="45" height="20" fill="{'#51cf66' if s_gates_passed >= 4 else '#ffd43b' if s_gates_passed >= 3 else '#ff6b6b'}" rx="10"/>
  <text x="222" y="279" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">{s_gates_passed}/4</text>

  <text x="280" y="275" class="label">EV: <tspan class="value" fill="{'#51cf66' if s_expected_value > 0 else '#ff6b6b'}">{s_expected_value:+.1f}%</tspan></text>

  <!-- Stock Scenarios -->
  <text x="40" y="310" class="section-title">SCENARIOS</text>
''')

    # Stock scenario bars
    stock_scenarios = [
        ('Strong Bull', s_scenarios.get('strong_bull', {}).get('probability', 0), s_scenarios.get('strong_bull', {}).get('move_pct', 0), '#2f9e44'),
        ('Base Bull', s_scenarios.get('base_bull', {}).get('probability', 0), s_scenarios.get('base_bull', {}).get('move_pct', 0), '#51cf66'),
        ('Base Bear', s_scenarios.get('base_bear', {}).get('probability', 0), s_scenarios.get('base_bear', {}).get('move_pct', 0), '#ff8787'),
        ('Strong Bear', s_scenarios.get('strong_bear', {}).get('probability', 0), s_scenarios.get('strong_bear', {}).get('move_pct', 0), '#c92a2a'),
    ]

    y = 330
    for name, prob, move, color in stock_scenarios:
        bar_width = min(prob * 2, 200)
        svg_parts.append(f'''
  <text x="40" y="{y}" class="small">{name}</text>
  <rect x="120" y="{y-10}" width="{bar_width}" height="14" fill="{color}" rx="3"/>
  <text x="{130 + bar_width}" y="{y}" class="small">{prob:.0f}% ({move:+.0f}%)</text>''')
        y += 25

    # ─── RIGHT COLUMN: EARNINGS ANALYSIS ───────────────────────────────────────
    svg_parts.append(f'''
  <!-- RIGHT COLUMN: EARNINGS ANALYSIS -->
  <rect x="610" y="120" width="570" height="320" fill="#fff" rx="8" filter="url(#shadow)"/>
  <text x="630" y="145" class="section-title">EARNINGS ANALYSIS</text>

  <!-- Beat Probability and History -->
  <text x="630" y="175" class="metric-label">P(Beat)</text>
  <text x="630" y="200" class="metric-value" font-size="24">{p_beat:.0f}%</text>

  <text x="730" y="175" class="metric-label">Beat Streak</text>
  <text x="730" y="200" class="metric-value">{beats}/{beats+misses}</text>
  <text x="730" y="215" class="small">({beat_rate:.0f}% rate)</text>

  <text x="850" y="175" class="metric-label">Implied Move</text>
  <text x="850" y="200" class="metric-value">±{implied_move:.1f}%</text>

  <text x="970" y="175" class="metric-label">Avg Historical</text>
  <text x="970" y="200" class="metric-value">{avg_move:.1f}%</text>

  <!-- Earnings Gate Section -->
  <text x="630" y="235" class="section-title">GATES</text>

  <text x="630" y="260" class="small">Do Nothing</text>
  <rect x="630" y="265" width="60" height="20" fill="{get_gate_color(e_do_nothing_passes)}" rx="10"/>
  <text x="660" y="279" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">{'PASS' if e_do_nothing_passes else 'FAIL'}</text>

  <text x="710" y="260" class="small">Open Trade</text>
  <rect x="710" y="265" width="60" height="20" fill="{get_gate_color(e_open_trade_passes)}" rx="10"/>
  <text x="740" y="279" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">{'PASS' if e_open_trade_passes else 'FAIL'}</text>

  <text x="790" y="260" class="small">Criteria</text>
  <rect x="790" y="265" width="45" height="20" fill="{'#51cf66' if e_gates_passed >= 4 else '#ffd43b' if e_gates_passed >= 3 else '#ff6b6b'}" rx="10"/>
  <text x="812" y="279" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">{e_gates_passed}/4</text>

  <text x="870" y="275" class="label">EV: <tspan class="value" fill="{'#51cf66' if e_ev > 0 else '#ff6b6b'}">{e_ev:+.2f}%</tspan></text>

  <!-- Earnings Scenarios -->
  <text x="630" y="310" class="section-title">SCENARIOS</text>
''')

    # Earnings scenario bars
    earnings_scenarios = [
        ('Strong Beat', e_scenarios.get('strong_beat', {}).get('probability', 0), e_scenarios.get('strong_beat', {}).get('move_pct', 0), '#2f9e44'),
        ('Modest Beat', e_scenarios.get('modest_beat', {}).get('probability', 0), e_scenarios.get('modest_beat', {}).get('move_pct', 0), '#51cf66'),
        ('Modest Miss', e_scenarios.get('modest_miss', {}).get('probability', 0), e_scenarios.get('modest_miss', {}).get('move_pct', 0), '#ff8787'),
        ('Strong Miss', e_scenarios.get('strong_miss', {}).get('probability', 0), e_scenarios.get('strong_miss', {}).get('move_pct', 0), '#c92a2a'),
    ]

    y = 330
    for name, prob, move, color in earnings_scenarios:
        bar_width = min(prob * 2, 200)
        svg_parts.append(f'''
  <text x="630" y="{y}" class="small">{name}</text>
  <rect x="720" y="{y-10}" width="{bar_width}" height="14" fill="{color}" rx="3"/>
  <text x="{730 + bar_width}" y="{y}" class="small">{prob:.0f}% ({move:+.0f}%)</text>''')
        y += 25

    # ─── BOTTOM: EXPECTATIONS & HISTORICAL ─────────────────────────────────────
    perf_color = '#ff6b6b' if priced_for_perfection else '#51cf66'
    stn_colors = {'high': '#ff6b6b', 'medium': '#ffd43b', 'low': '#51cf66'}
    stn_color = stn_colors.get(sell_the_news_risk, '#868e96')

    svg_parts.append(f'''
  <!-- BOTTOM ROW -->
  <rect x="20" y="460" width="380" height="140" fill="#fff" rx="8" filter="url(#shadow)"/>
  <text x="40" y="485" class="section-title">EXPECTATIONS</text>

  <text x="40" y="515" class="label">Priced for Perfection:</text>
  <text x="180" y="515" class="value" fill="{perf_color}">{'YES' if priced_for_perfection else 'NO'}</text>

  <text x="40" y="540" class="label">Sell-the-News Risk:</text>
  <text x="180" y="540" class="value" fill="{stn_color}">{escape_xml(sell_the_news_risk.upper())}</text>

  <text x="40" y="565" class="label">Implied vs Historical:</text>
  <text x="180" y="565" class="value">{'Above' if implied_move > avg_move else 'Below'} avg</text>

  <text x="40" y="590" class="label">Days to Earnings:</text>
  <text x="180" y="590" class="value">{days_to_earnings}</text>

  <!-- Historical Moves Chart -->
  <rect x="420" y="460" width="380" height="140" fill="#fff" rx="8" filter="url(#shadow)"/>
  <text x="440" y="485" class="section-title">HISTORICAL EARNINGS MOVES</text>
''')

    # Historical bars
    bar_x = 450
    bar_width = 70
    for q in quarters[:4]:
        move = q.get('move_pct', 0)
        bar_height = min(abs(move) * 4, 60)
        bar_color = '#51cf66' if move >= 0 else '#ff6b6b'
        bar_y = 555 if move >= 0 else 555
        if move >= 0:
            bar_y = 555 - bar_height
        svg_parts.append(f'''
  <rect x="{bar_x}" y="{bar_y}" width="{bar_width - 10}" height="{bar_height}" fill="{bar_color}" rx="3"/>
  <text x="{bar_x + (bar_width-10)/2}" y="575" text-anchor="middle" class="small">{q.get('quarter', '')[:7]}</text>
  <text x="{bar_x + (bar_width-10)/2}" y="{bar_y - 5 if move >= 0 else bar_y + bar_height + 12}" text-anchor="middle" class="small">{'+' if move > 0 else ''}{move:.1f}%</text>''')
        bar_x += bar_width

    # ─── COMBINED RECOMMENDATION ───────────────────────────────────────────────
    # Determine combined recommendation
    combined_rec = "NEUTRAL"
    combined_color = "#868e96"

    if s_open_trade_passes and e_open_trade_passes:
        combined_rec = "ALIGNED - TRADE"
        combined_color = "#2f9e44"
    elif s_open_trade_passes and not e_open_trade_passes:
        combined_rec = "STOCK ONLY"
        combined_color = "#ffd43b"
    elif not s_open_trade_passes and e_open_trade_passes:
        combined_rec = "EARNINGS ONLY"
        combined_color = "#ffd43b"
    else:
        combined_rec = "NO TRADE"
        combined_color = "#ff6b6b"

    svg_parts.append(f'''
  <!-- Combined Recommendation -->
  <rect x="820" y="460" width="360" height="140" fill="#fff" rx="8" filter="url(#shadow)"/>
  <text x="840" y="485" class="section-title">COMBINED RECOMMENDATION</text>

  <rect x="840" y="500" width="320" height="50" fill="{combined_color}" rx="8"/>
  <text x="1000" y="532" text-anchor="middle" fill="#fff" font-size="18" font-weight="bold">{combined_rec}</text>

  <text x="840" y="575" class="label">Stock Gate: <tspan class="value">{'PASS' if s_open_trade_passes else 'FAIL'}</tspan></text>
  <text x="1000" y="575" class="label">Earnings Gate: <tspan class="value">{'PASS' if e_open_trade_passes else 'FAIL'}</tspan></text>

  <text x="840" y="595" class="small">Combined EV: {s_expected_value + e_ev:.2f}% | Risk overlap assessed</text>
''')

    # ─── FOOTER ────────────────────────────────────────────────────────────────
    svg_parts.append(f'''
  <!-- Footer -->
  <text x="20" y="620" class="small">Sources: {Path(stock_file).name if stock_file else 'stock'} + {Path(earnings_file).name if earnings_file else 'earnings'}</text>
  <text x="1180" y="620" text-anchor="end" class="small">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</text>

  <!-- Warning if gates conflict -->
  {f'<rect x="20" y="630" width="1160" height="25" fill="#fff3cd" rx="4"/><text x="600" y="648" text-anchor="middle" font-size="11" fill="#856404">⚠️ Gates conflict: Review both analyses carefully before trading</text>' if (s_open_trade_passes != e_open_trade_passes) else ''}

</svg>''')

    return '\n'.join(svg_parts)


def main():
    parser = argparse.ArgumentParser(description='Generate combined stock + earnings SVG')
    parser.add_argument('ticker', nargs='?', help='Ticker symbol (auto-finds latest analyses)')
    parser.add_argument('--stock', help='Path to stock analysis YAML')
    parser.add_argument('--earnings', help='Path to earnings analysis YAML')
    parser.add_argument('--output', '-o', help='Output SVG path')
    parser.add_argument('--json', action='store_true', help='Output path as JSON')
    args = parser.parse_args()

    # Find or load analyses
    stock_file = None
    earnings_file = None
    stock_data = None
    earnings_data = None

    if args.stock:
        stock_file = Path(args.stock)
        stock_data = load_analysis(str(stock_file))

    if args.earnings:
        earnings_file = Path(args.earnings)
        earnings_data = load_analysis(str(earnings_file))

    if args.ticker and not args.stock:
        stock_file = find_latest_analysis(args.ticker, 'stock')
        if stock_file:
            stock_data = load_analysis(str(stock_file))
        else:
            print(f"Error: No stock analysis found for {args.ticker}", file=sys.stderr)
            sys.exit(1)

    if args.ticker and not args.earnings:
        earnings_file = find_latest_analysis(args.ticker, 'earnings')
        if earnings_file:
            earnings_data = load_analysis(str(earnings_file))

    if not stock_data:
        print("Error: Stock analysis required. Provide --stock or ticker.", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    ticker = stock_data.get('ticker', args.ticker or 'UNKNOWN')
    timestamp = datetime.now().strftime('%Y%m%dT%H%M')

    if args.output:
        output_path = Path(args.output)
    elif earnings_data:
        # Combined output goes to a combined folder
        base = Path(__file__).parent.parent.parent / "tradegent_knowledge" / "knowledge" / "analysis" / "combined"
        base.mkdir(parents=True, exist_ok=True)
        output_path = base / f"{ticker}_{timestamp}_combined.svg"
    else:
        # Stock-only output
        output_path = stock_file.with_suffix('.svg') if stock_file else Path(f"{ticker}_{timestamp}.svg")

    # Generate SVG
    if earnings_data:
        svg_content = generate_combined_svg(
            stock_data, earnings_data,
            str(stock_file) if stock_file else '',
            str(earnings_file) if earnings_file else ''
        )
        viz_type = "combined"
    else:
        # No earnings data - generate stock only
        svg_content = generate_stock_only_svg(stock_data, str(stock_file) if stock_file else '')
        viz_type = "stock-only"

    # Write output
    output_path.write_text(svg_content)

    if args.json:
        print(json.dumps({
            'svg_path': str(output_path),
            'type': viz_type,
            'stock_file': str(stock_file) if stock_file else None,
            'earnings_file': str(earnings_file) if earnings_file else None
        }))
    else:
        print(f"Generated ({viz_type}): {output_path}")


if __name__ == '__main__':
    main()
