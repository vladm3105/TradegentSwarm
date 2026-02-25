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
    support = technical.get('key_levels', {}).get('support', 0)
    resistance = technical.get('key_levels', {}).get('resistance', 0)

    # Sentiment
    sentiment = data.get('sentiment', {})
    sentiment_score = sentiment.get('sentiment_score', 5)
    overall_sentiment = sentiment.get('overall_sentiment', 'neutral')
    crowded_trade = sentiment.get('crowded_trade', {})
    is_crowded = crowded_trade.get('crowded', False)

    # Expectations
    expectations = data.get('expectations_assessment', {})
    priced_for_perfection = expectations.get('priced_for_perfection', False)
    sell_the_news_risk = expectations.get('sell_the_news_risk', 'medium')

    # === NEW: Additional data extraction for gaps ===

    # News Age Check
    news_age = data.get('news_age_check', {})
    news_items = news_age.get('items', [])[:3]
    fresh_catalyst = news_age.get('fresh_catalyst_exists', False)

    # Customer Demand
    customer_demand = data.get('customer_demand', {})
    demand_signal = customer_demand.get('signal_strength', 'neutral')
    demand_signals = customer_demand.get('signals', [])[:2]

    # Estimate Revisions
    est_revisions = prep.get('estimate_revisions', {})
    revision_direction = est_revisions.get('direction', 'flat')
    revision_magnitude = est_revisions.get('magnitude', 'none')

    # Key Metric
    key_metric = prep.get('key_metric', {})
    key_metric_name = key_metric.get('name', '')
    key_metric_consensus = key_metric.get('consensus', '')

    # Bias Check
    bias_check = data.get('bias_check', {})
    biases_detected = []
    for bias_type in ['recency_bias', 'confirmation_bias', 'overconfidence', 'anchoring', 'fomo', 'loss_aversion']:
        bias_data = bias_check.get(bias_type, {})
        if bias_data.get('present', False):
            biases_detected.append((bias_type.replace('_', ' ').title(), bias_data.get('severity', 'low')))

    # Trade Plan
    trade_plan = data.get('trade_plan', {})
    has_trade = trade_plan.get('trade', False)
    entry_price = trade_plan.get('entry', {}).get('price', 0)
    stop_loss = trade_plan.get('stop_loss', {}).get('price', 0)
    target_1 = trade_plan.get('targets', {}).get('target_1', 0)
    structure_type = trade_plan.get('structure', {}).get('type', 'none')

    # Alert Levels
    alert_levels = data.get('alert_levels', {})
    price_alerts = alert_levels.get('price_alerts', [])[:2]

    # Falsification
    falsification = data.get('falsification', {})
    beat_wrong_if = falsification.get('beat_thesis_wrong_if', [])[:2]
    miss_wrong_if = falsification.get('miss_thesis_wrong_if', [])[:2]

    # Thesis Reversal
    thesis_reversal = data.get('thesis_reversal', {})
    flip_conditions = thesis_reversal.get('conditions_to_flip', [])[:2]

    # Alternative Strategies
    alternatives = data.get('alternative_strategies', {})
    alt_strategies = alternatives.get('strategies', [])[:2]

    # Action Items
    action_items = data.get('action_items', {})
    immediate_actions = action_items.get('immediate', [])[:3]
    earnings_day_actions = action_items.get('earnings_day', [])[:2]

    # Meta Learning
    meta_learning = data.get('meta_learning', {})
    new_rule = meta_learning.get('new_rule', {})
    pattern_identified = meta_learning.get('pattern_identified', '')

    # Pass Reasoning (if no trade)
    pass_reasoning = data.get('pass_reasoning', {})
    pass_reasons = pass_reasoning.get('reasons', [])[:3]

    # Rationale
    rationale = decision.get('rationale', data.get('rationale', ''))
    if isinstance(rationale, str):
        rationale_text = rationale[:300]
    else:
        rationale_text = ''

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
    svg_parts.append(f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 1100" width="420" height="1100">
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
  <rect width="420" height="1100" fill="#f8f9fa" rx="8"/>

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

    # Gate section - match stock analysis approach
    # Get actual values from do_nothing_gate
    ev_actual = do_nothing.get('ev_actual', 0)
    confidence_actual = do_nothing.get('confidence_actual', confidence_pct)
    rr_actual = do_nothing.get('rr_actual', 0)
    gates_passed = do_nothing.get('gates_passed', 0)

    ev_check = do_nothing.get('ev_passes', False)
    confidence_check = do_nothing.get('confidence_passes', False)
    rr_check = do_nothing.get('rr_passes', False)
    edge_check = do_nothing.get('edge_exists', False)

    # Gate logic (same as stock analysis)
    do_nothing_passes = gate_result != 'PASS'  # If trade criteria fail, "do nothing" is correct
    open_trade_passes = gate_result == 'PASS'  # If trade criteria pass, "open trade" is correct

    # Criteria badge color
    criteria_color = '#51cf66' if gates_passed >= 4 else '#ffd43b' if gates_passed >= 3 else '#ff6b6b'

    svg_parts.append(f'''
  <!-- Gate Section -->
  <rect x="10" y="420" width="400" height="100" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>

  <!-- Gate badges row -->
  <text x="20" y="438" class="small">Do Nothing Gate</text>
  <rect x="20" y="442" width="55" height="18" fill="{get_gate_color(do_nothing_passes)}" rx="9"/>
  <text x="47" y="455" text-anchor="middle" fill="#fff" font-size="9" font-weight="bold">{'PASS' if do_nothing_passes else 'FAIL'}</text>

  <text x="90" y="438" class="small">Open Trade Gate</text>
  <rect x="90" y="442" width="55" height="18" fill="{get_gate_color(open_trade_passes)}" rx="9"/>
  <text x="117" y="455" text-anchor="middle" fill="#fff" font-size="9" font-weight="bold">{'PASS' if open_trade_passes else 'FAIL'}</text>

  <text x="160" y="438" class="small">Criteria</text>
  <rect x="160" y="442" width="40" height="18" fill="{criteria_color}" rx="9"/>
  <text x="180" y="455" text-anchor="middle" fill="#fff" font-size="9" font-weight="bold">{gates_passed}/4</text>

  <!-- Gate criteria details -->
  <text x="220" y="445" class="small">EV &gt;5%</text>
  <text x="280" y="445" class="value">{ev_actual:.1f}%</text>
  <circle cx="320" cy="441" r="7" fill="{get_gate_color(ev_check)}"/>
  <text x="320" y="445" font-size="9" fill="#fff" text-anchor="middle">{'✓' if ev_check else '✗'}</text>

  <text x="340" y="445" class="small">Conf &gt;60%</text>
  <text x="385" y="445" class="value">{confidence_actual}%</text>

  <text x="220" y="465" class="small">R:R &gt;2:1</text>
  <text x="280" y="465" class="value">{rr_actual:.1f}:1</text>
  <circle cx="320" cy="461" r="7" fill="{get_gate_color(rr_check)}"/>
  <text x="320" y="465" font-size="9" fill="#fff" text-anchor="middle">{'✓' if rr_check else '✗'}</text>

  <text x="340" y="465" class="small">Edge</text>
  <text x="375" y="465" class="value">{'Yes' if edge_check else 'No'}</text>

  <!-- Confidence and Edge circles on right -->
  <circle cx="395" cy="441" r="7" fill="{get_gate_color(confidence_check)}"/>
  <text x="395" y="445" font-size="9" fill="#fff" text-anchor="middle">{'✓' if confidence_check else '✗'}</text>

  <circle cx="395" cy="461" r="7" fill="{get_gate_color(edge_check)}"/>
  <text x="395" y="465" font-size="9" fill="#fff" text-anchor="middle">{'✓' if edge_check else '✗'}</text>
''')

    # Bull/Bear Strength - move down since gate section is now full width
    svg_parts.append(f'''
  <!-- Bull/Bear Strength -->
  <text x="20" y="490" class="label">Bull Case</text>
  <rect x="75" y="480" width="100" height="12" fill="#e9ecef" rx="2"/>
  <rect x="75" y="480" width="{bull_strength * 10}" height="12" fill="#51cf66" rx="2"/>
  <text x="180" y="490" class="small">{bull_strength}/10</text>

  <text x="220" y="490" class="label">Bear Case</text>
  <rect x="275" y="480" width="100" height="12" fill="#e9ecef" rx="2"/>
  <rect x="275" y="480" width="{bear_strength * 10}" height="12" fill="#ff6b6b" rx="2"/>
  <text x="380" y="490" class="small">{bear_strength}/10</text>
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
  <text x="225" y="550" class="section-title">TECHNICALS &amp; SENTIMENT</text>
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

    # === NEW SECTIONS: Fill the gaps ===

    # News Age Check & Customer Demand
    demand_color = {'strong_bullish': '#2f9e44', 'bullish': '#51cf66', 'neutral': '#868e96', 'bearish': '#ff8787', 'strong_bearish': '#c92a2a'}
    svg_parts.append(f'''
  <!-- News & Demand -->
  <rect x="10" y="670" width="400" height="70" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="690" class="section-title">NEWS &amp; DEMAND</text>
  <text x="20" y="708" class="label">Fresh Catalyst:</text>
  <text x="100" y="708" class="value" fill="{'#51cf66' if fresh_catalyst else '#868e96'}">{'YES' if fresh_catalyst else 'NO'}</text>
  <text x="150" y="708" class="label">Demand Signal:</text>
  <text x="245" y="708" class="value" fill="{demand_color.get(demand_signal, '#868e96')}">{escape_xml(demand_signal.replace('_', ' ').title())}</text>
  <text x="20" y="728" class="label">Revisions:</text>
  <text x="75" y="728" class="value">{escape_xml(revision_direction.title())} ({escape_xml(revision_magnitude)})</text>
  <text x="200" y="728" class="label">Crowded:</text>
  <text x="250" y="728" class="value" fill="{'#ff6b6b' if is_crowded else '#51cf66'}">{'YES' if is_crowded else 'NO'}</text>
''')

    # Trade Plan (if exists)
    if has_trade:
        svg_parts.append(f'''
  <!-- Trade Plan -->
  <rect x="10" y="750" width="400" height="60" fill="#e7f5ff" rx="6" stroke="#74c0fc" stroke-width="1"/>
  <text x="20" y="770" class="section-title" fill="#1971c2">TRADE PLAN</text>
  <text x="20" y="790" class="label">Entry: <tspan class="value">${entry_price:.2f}</tspan></text>
  <text x="120" y="790" class="label">Stop: <tspan class="value" fill="#ff6b6b">${stop_loss:.2f}</tspan></text>
  <text x="220" y="790" class="label">Target: <tspan class="value" fill="#51cf66">${target_1:.2f}</tspan></text>
  <text x="320" y="790" class="label">Type: <tspan class="value">{escape_xml(structure_type)}</tspan></text>
''')
    else:
        svg_parts.append(f'''
  <!-- No Trade - Pass Reasoning -->
  <rect x="10" y="750" width="400" height="60" fill="#fff3cd" rx="6" stroke="#ffc107" stroke-width="1"/>
  <text x="20" y="770" class="section-title" fill="#856404">NO TRADE - REASONING</text>
''')
        reason_y = 788
        for reason in pass_reasons[:2]:
            reason_text = reason.get('reason', str(reason))[:50] if isinstance(reason, dict) else str(reason)[:50]
            svg_parts.append(f'''  <text x="20" y="{reason_y}" class="small">• {escape_xml(reason_text)}</text>''')
            reason_y += 12

    # Alert Levels
    svg_parts.append(f'''
  <!-- Alert Levels -->
  <rect x="10" y="820" width="195" height="60" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="840" class="section-title">PRICE ALERTS</text>
''')
    alert_y = 858
    for alert in price_alerts[:2]:
        price = alert.get('price', 0)
        direction = alert.get('direction', '')
        svg_parts.append(f'''  <text x="20" y="{alert_y}" class="small">${price:.0f} ({direction})</text>''')
        alert_y += 14

    # Biases Detected
    svg_parts.append(f'''
  <!-- Biases -->
  <rect x="215" y="820" width="195" height="60" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="225" y="840" class="section-title">BIASES DETECTED</text>
''')
    if biases_detected:
        bias_y = 858
        for bias_name, severity in biases_detected[:2]:
            sev_color = '#ff6b6b' if severity == 'high' else '#ffd43b' if severity == 'medium' else '#868e96'
            svg_parts.append(f'''  <text x="225" y="{bias_y}" class="small">{escape_xml(bias_name)}: <tspan fill="{sev_color}">{severity.upper()}</tspan></text>''')
            bias_y += 14
    else:
        svg_parts.append(f'''  <text x="225" y="858" class="small" fill="#51cf66">None detected ✓</text>''')

    # Falsification & Thesis Reversal
    svg_parts.append(f'''
  <!-- Falsification -->
  <rect x="10" y="890" width="400" height="70" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="910" class="section-title">FALSIFICATION CRITERIA</text>
  <text x="20" y="928" class="small" fill="#ff6b6b">Beat thesis wrong if:</text>
''')
    fals_y = 940
    for cond in beat_wrong_if[:1]:
        svg_parts.append(f'''  <text x="25" y="{fals_y}" class="small">• {escape_xml(str(cond)[:55])}</text>''')
        fals_y += 12
    svg_parts.append(f'''  <text x="210" y="928" class="small" fill="#51cf66">Miss thesis wrong if:</text>''')
    fals_y = 940
    for cond in miss_wrong_if[:1]:
        svg_parts.append(f'''  <text x="215" y="{fals_y}" class="small">• {escape_xml(str(cond)[:45])}</text>''')

    # Alternative Strategies
    svg_parts.append(f'''
  <!-- Alternatives -->
  <rect x="10" y="970" width="400" height="55" fill="#fff" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="990" class="section-title">ALTERNATIVE STRATEGIES</text>
''')
    alt_y = 1008
    for alt in alt_strategies[:2]:
        strategy = alt.get('strategy', '')[:60]
        svg_parts.append(f'''  <text x="20" y="{alt_y}" class="small">• {escape_xml(strategy)}</text>''')
        alt_y += 12

    # Rationale Text Box
    svg_parts.append(f'''
  <!-- Rationale -->
  <rect x="10" y="1035" width="400" height="45" fill="#f1f3f5" rx="6" stroke="#dee2e6" stroke-width="1"/>
  <text x="20" y="1052" class="section-title">RATIONALE</text>
  <text x="20" y="1068" class="small">{escape_xml(rationale_text[:100])}...</text>
''')

    # Footer - show just filename for cleaner display
    source_name = Path(source_file).name if source_file else ''
    svg_parts.append(f'''
  <!-- Footer -->
  <text x="210" y="1095" text-anchor="middle" class="small">Source: {escape_xml(source_name)}</text>
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
