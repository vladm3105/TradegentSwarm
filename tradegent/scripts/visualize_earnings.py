#!/usr/bin/env python3
"""
Earnings Analysis SVG Visualization Generator

Generates professional SVG dashboard from v2.4/v2.5 earnings analysis YAML files.

Usage:
    python scripts/visualize_earnings.py <analysis.yaml>
    python scripts/visualize_earnings.py <analysis.yaml> --output custom.svg
"""

import sys
import argparse
import json
import math
from pathlib import Path
from datetime import datetime

import yaml


def load_analysis(file_path: str) -> dict:
    """Load and parse YAML analysis file."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


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


def generate_svg(data: dict, source_file: str = '') -> str:
    """Generate SVG visualization for earnings analysis."""

    # Extract data with safe defaults
    meta = data.get('_meta', {})
    doc_id = meta.get('id', '')
    ticker = data.get('ticker', meta.get('ticker', 'N/A'))
    earnings_date = data.get('earnings_date', '')
    earnings_time = data.get('earnings_time', 'AMC')
    days_to_earnings = data.get('days_to_earnings', 0)
    current_price = data.get('current_price', 0)
    analysis_date = data.get('analysis_date', meta.get('created', ''))
    version = str(meta.get('version', '2.5'))

    # Decision/recommendation
    decision = data.get('decision', {})
    recommendation = decision.get('recommendation', data.get('recommendation', 'NEUTRAL'))

    # Confidence
    probability = data.get('probability', {})
    confidence_pct = probability.get('confidence_pct', decision.get('confidence_pct', 50))
    p_beat = probability.get('final_probability', {}).get('p_beat', 50)

    # Scenarios
    scenarios = data.get('scenarios', {})
    ev = scenarios.get('expected_value', data.get('expected_value', 0))

    # Historical moves
    historical = data.get('historical_moves', {})
    avg_move = historical.get('average_move_pct', 0)
    implied_move = historical.get('current_implied_move_pct', data.get('preparation', {}).get('implied_move', {}).get('percentage', 0))

    # Beat history
    prep = data.get('preparation', {})
    beat_history = prep.get('beat_history', {})
    beat_rate = beat_history.get('beat_rate', 0)
    beats = beat_history.get('beats', 0)
    misses = beat_history.get('misses', 0)

    # Consensus estimates
    estimates = prep.get('current_estimates', {})
    consensus_eps = estimates.get('consensus_eps', 0)
    consensus_rev = estimates.get('consensus_revenue_b', 0)

    # Bull/Bear case
    bull_case = data.get('bull_case_analysis', {})
    bear_case = data.get('bear_case_analysis', {})
    bull_strength = bull_case.get('strength', 5)
    bear_strength = bear_case.get('strength', 5)

    # Do Nothing Gate - at root level, not under decision
    do_nothing = data.get('do_nothing_gate', {})
    gate_result = do_nothing.get('gate_result', 'FAIL')
    gate_passed = gate_result == 'PASS'
    gate_criteria = do_nothing.get('criteria', {})

    # Technical
    technical = data.get('technical', {})
    tech_score = technical.get('technical_score', 5)
    rsi = technical.get('momentum', {}).get('rsi', 50)

    # Sentiment
    sentiment = data.get('sentiment', {})
    sentiment_score = sentiment.get('sentiment_score', 5)
    overall_sentiment = sentiment.get('overall_sentiment', 'neutral')

    # Expectations
    expectations = data.get('expectations_assessment', {})
    priced_for_perfection = expectations.get('priced_for_perfection', False)
    sell_the_news_risk = expectations.get('sell_the_news_risk', 'medium')

    # Colors
    rec_bg, rec_text = get_recommendation_color(recommendation)

    # Scenario colors
    scenario_colors = {
        'strong_beat': '#2f9e44',
        'modest_beat': '#51cf66',
        'modest_miss': '#ff8787',
        'strong_miss': '#c92a2a'
    }

    # Calculate scenario pie chart
    pie_data = []
    start_angle = 0
    for scenario_key in ['strong_beat', 'modest_beat', 'modest_miss', 'strong_miss']:
        scenario = scenarios.get(scenario_key, {})
        prob = scenario.get('probability', 0)
        if prob > 0:
            pie_data.append({
                'key': scenario_key,
                'prob': prob,
                'move': scenario.get('move_pct', 0),
                'color': scenario_colors.get(scenario_key, '#868e96'),
                'start': start_angle,
                'end': start_angle + (prob / 100 * 360)
            })
            start_angle += (prob / 100 * 360)

    # Build SVG
    svg_parts = []

    # Header
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 700" width="420" height="700">
  <defs>
    <style>
      .title {{ font: bold 18px system-ui, sans-serif; fill: #212529; }}
      .subtitle {{ font: 12px system-ui, sans-serif; fill: #495057; }}
      .label {{ font: 11px system-ui, sans-serif; fill: #495057; }}
      .value {{ font: bold 13px system-ui, sans-serif; fill: #212529; }}
      .small {{ font: 10px system-ui, sans-serif; fill: #868e96; }}
      .metric-label {{ font: 10px system-ui, sans-serif; fill: #868e96; }}
      .metric-value {{ font: bold 14px system-ui, sans-serif; fill: #212529; }}
      .section-title {{ font: bold 11px system-ui, sans-serif; fill: #495057; text-transform: uppercase; letter-spacing: 0.5px; }}
      .scenario-label {{ font: 10px system-ui, sans-serif; fill: #212529; }}
      .scenario-prob {{ font: bold 11px system-ui, sans-serif; }}
    </style>
  </defs>

  <!-- Background -->
  <rect width="420" height="700" fill="#f8f9fa" rx="8"/>

  <!-- Header -->
  <rect x="10" y="10" width="400" height="70" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>

  <!-- Ticker and Earnings Date -->
  <text x="20" y="35" class="title">{escape_xml(ticker)} Earnings Analysis</text>
  <text x="20" y="52" class="subtitle">Earnings: {escape_xml(earnings_date)} {escape_xml(earnings_time)} (T-{days_to_earnings})</text>
  <text x="20" y="68" class="small">v{escape_xml(version)} | {escape_xml(str(analysis_date)[:10])}</text>

  <!-- Recommendation Badge -->
  <rect x="300" y="20" width="100" height="50" fill="{rec_bg}" rx="6"/>
  <text x="350" y="42" text-anchor="middle" fill="{rec_text}" font-size="11" font-weight="bold">{escape_xml(recommendation)}</text>
  <text x="350" y="58" text-anchor="middle" fill="{rec_text}" font-size="12">{confidence_pct}% conf</text>
''')

    # Price and Key Metrics Row
    svg_parts.append(f'''
  <!-- Price Section -->
  <rect x="10" y="90" width="195" height="60" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="108" class="metric-label">Current Price</text>
  <text x="20" y="130" class="metric-value" font-size="20">${current_price:.2f}</text>
  <text x="20" y="143" class="small">Implied Move: ±{implied_move:.1f}%</text>

  <!-- P(Beat) Section -->
  <rect x="215" y="90" width="195" height="60" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="225" y="108" class="metric-label">Probability of Beat</text>
  <text x="225" y="130" class="metric-value" font-size="20">{p_beat:.0f}%</text>
  <text x="225" y="143" class="small">Beat Streak: {beats}/{beats+misses} ({beat_rate:.0f}%)</text>
''')

    # Scenario Pie Chart
    svg_parts.append('''
  <!-- Scenarios Section -->
  <rect x="10" y="160" width="400" height="140" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="180" class="section-title">SCENARIO ANALYSIS</text>
''')

    # Draw pie chart
    cx, cy, r = 80, 235, 45
    for pd in pie_data:
        if pd['prob'] > 0:
            start_rad = math.radians(pd['start'] - 90)
            end_rad = math.radians(pd['end'] - 90)
            large_arc = 1 if pd['prob'] > 50 else 0
            x1 = cx + r * math.cos(start_rad)
            y1 = cy + r * math.sin(start_rad)
            x2 = cx + r * math.cos(end_rad)
            y2 = cy + r * math.sin(end_rad)
            svg_parts.append(f'''  <path d="M {cx},{cy} L {x1:.1f},{y1:.1f} A {r},{r} 0 {large_arc},1 {x2:.1f},{y2:.1f} Z" fill="{pd['color']}"/>''')

    # Scenario legend
    legend_y = 195
    for pd in pie_data:
        label = pd['key'].replace('_', ' ').title()
        move_prefix = '+' if pd['move'] > 0 else ''
        svg_parts.append(f'''
  <rect x="150" y="{legend_y}" width="10" height="10" fill="{pd['color']}" rx="2"/>
  <text x="165" y="{legend_y + 9}" class="scenario-label">{escape_xml(label)}</text>
  <text x="260" y="{legend_y + 9}" class="scenario-prob" fill="{pd['color']}">{pd['prob']:.0f}%</text>
  <text x="295" y="{legend_y + 9}" class="small">({move_prefix}{pd['move']:.0f}%)</text>''')
        legend_y += 18

    # Expected Value
    ev_color = '#2f9e44' if ev > 0 else '#c92a2a' if ev < 0 else '#868e96'
    ev_prefix = '+' if ev > 0 else ''
    svg_parts.append(f'''
  <text x="350" y="235" class="metric-label" text-anchor="middle">Expected Value</text>
  <text x="350" y="260" class="metric-value" text-anchor="middle" fill="{ev_color}" font-size="18">{ev_prefix}{ev:.2f}%</text>
''')

    # Historical Moves
    quarters = historical.get('quarters', [])[:6]
    svg_parts.append('''
  <!-- Historical Moves -->
  <rect x="10" y="310" width="400" height="100" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="330" class="section-title">HISTORICAL POST-EARNINGS MOVES</text>
''')

    bar_x = 30
    bar_width = 55
    for q in quarters:
        move = q.get('move_pct', 0)
        bar_height = min(abs(move) * 3, 50)
        bar_color = '#51cf66' if move >= 0 else '#ff6b6b'
        bar_y = 375 if move >= 0 else 375
        if move >= 0:
            bar_y = 375 - bar_height
        svg_parts.append(f'''
  <rect x="{bar_x}" y="{bar_y}" width="{bar_width - 5}" height="{bar_height}" fill="{bar_color}" rx="2"/>
  <text x="{bar_x + (bar_width-5)/2}" y="395" text-anchor="middle" class="small">{q.get('quarter', '')[:7]}</text>
  <text x="{bar_x + (bar_width-5)/2}" y="{bar_y - 3 if move >= 0 else bar_y + bar_height + 10}" text-anchor="middle" class="small">{'+' if move > 0 else ''}{move:.1f}%</text>''')
        bar_x += bar_width

    svg_parts.append(f'''
  <text x="380" y="365" text-anchor="end" class="metric-label">Avg Move</text>
  <text x="380" y="380" text-anchor="end" class="value">{avg_move:.1f}%</text>
''')

    # Do Nothing Gate
    gate_color = '#51cf66' if gate_passed else '#ff6b6b'
    svg_parts.append(f'''
  <!-- Do Nothing Gate -->
  <rect x="10" y="420" width="195" height="100" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="440" class="section-title">DO NOTHING GATE</text>
  <rect x="140" y="428" width="55" height="18" fill="{gate_color}" rx="3"/>
  <text x="167" y="441" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">{gate_result}</text>
''')

    # Gate criteria - read directly from do_nothing_gate (not nested criteria)
    criteria_y = 460
    criteria_items = [
        ('EV > 5%', do_nothing.get('ev_passes', False)),
        ('Conf > 60%', do_nothing.get('confidence_passes', False)),
        ('R:R > 2:1', do_nothing.get('rr_passes', False)),
        ('Edge exists', do_nothing.get('edge_exists', False)),
    ]
    for label, passed in criteria_items:
        icon = '✓' if passed else '✗'
        color = '#51cf66' if passed else '#ff6b6b'
        svg_parts.append(f'''  <text x="25" y="{criteria_y}" fill="{color}" font-size="12">{icon}</text>
  <text x="40" y="{criteria_y}" class="label">{escape_xml(label)}</text>''')
        criteria_y += 16

    # Bull/Bear Strength
    svg_parts.append(f'''
  <!-- Bull/Bear Strength -->
  <rect x="215" y="420" width="195" height="100" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="225" y="440" class="section-title">CASE STRENGTH</text>

  <text x="225" y="465" class="label">Bull Case</text>
  <rect x="285" y="455" width="100" height="12" fill="#e9ecef" rx="2"/>
  <rect x="285" y="455" width="{bull_strength * 10}" height="12" fill="#51cf66" rx="2"/>
  <text x="390" y="465" class="small">{bull_strength}/10</text>

  <text x="225" y="490" class="label">Bear Case</text>
  <rect x="285" y="480" width="100" height="12" fill="#e9ecef" rx="2"/>
  <rect x="285" y="480" width="{bear_strength * 10}" height="12" fill="#ff6b6b" rx="2"/>
  <text x="390" y="490" class="small">{bear_strength}/10</text>
''')

    # Expectations & Sentiment
    perf_color = '#ff6b6b' if priced_for_perfection else '#51cf66'
    stn_risk_colors = {'high': '#ff6b6b', 'medium': '#ffd43b', 'low': '#51cf66'}
    stn_color = stn_risk_colors.get(sell_the_news_risk, '#868e96')

    svg_parts.append(f'''
  <!-- Expectations -->
  <rect x="10" y="530" width="195" height="70" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="550" class="section-title">EXPECTATIONS</text>
  <text x="20" y="572" class="label">Priced for Perfection:</text>
  <text x="140" y="572" class="value" fill="{perf_color}">{'YES' if priced_for_perfection else 'NO'}</text>
  <text x="20" y="590" class="label">Sell-the-News Risk:</text>
  <text x="140" y="590" class="value" fill="{stn_color}">{escape_xml(sell_the_news_risk.upper())}</text>

  <!-- Technical & Sentiment -->
  <rect x="215" y="530" width="195" height="70" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="225" y="550" class="section-title">TECHNICALS & SENTIMENT</text>
  <text x="225" y="572" class="label">Technical Score:</text>
  <text x="330" y="572" class="value">{tech_score}/10</text>
  <text x="225" y="590" class="label">Sentiment:</text>
  <text x="330" y="590" class="value">{escape_xml(overall_sentiment.replace('_', ' ').title())}</text>
''')

    # Consensus Estimates
    svg_parts.append(f'''
  <!-- Consensus -->
  <rect x="10" y="610" width="400" height="50" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="630" class="section-title">CONSENSUS ESTIMATES</text>
  <text x="20" y="650" class="label">EPS: <tspan class="value">${consensus_eps:.2f}</tspan></text>
  <text x="120" y="650" class="label">Revenue: <tspan class="value">${consensus_rev:.1f}B</tspan></text>
  <text x="250" y="650" class="label">RSI: <tspan class="value">{rsi}</tspan></text>
  <text x="320" y="650" class="label">IV Rank: <tspan class="value">{prep.get('implied_move', {}).get('iv_rank', 'N/A')}</tspan></text>
''')

    # Footer - show just filename for cleaner display
    source_name = Path(source_file).name if source_file else ''
    svg_parts.append(f'''
  <!-- Footer -->
  <text x="210" y="685" text-anchor="middle" class="small">Source: {escape_xml(source_name)}</text>
</svg>''')

    return '\n'.join(svg_parts)


def main():
    parser = argparse.ArgumentParser(description='Generate earnings analysis SVG')
    parser.add_argument('input', help='Path to earnings YAML file')
    parser.add_argument('--output', '-o', help='Output SVG path')
    parser.add_argument('--json', action='store_true', help='Output path as JSON')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Load data
    data = load_analysis(str(input_path))

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.svg')

    # Generate SVG
    svg_content = generate_svg(data, str(input_path))

    # Write output
    output_path.write_text(svg_content)

    if args.json:
        print(json.dumps({'svg_path': str(output_path)}))
    else:
        print(f"Generated: {output_path}")


if __name__ == '__main__':
    main()
