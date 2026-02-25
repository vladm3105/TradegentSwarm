#!/usr/bin/env python3
"""
Stock Analysis SVG Visualization Generator

Generates professional SVG dashboard from v2.6 stock analysis YAML files.

Usage:
    python scripts/visualize_analysis.py <analysis.yaml>
    python scripts/visualize_analysis.py <analysis.yaml> --output custom.svg
    python scripts/visualize_analysis.py <analysis.yaml> --json  # Return path as JSON
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
import xml.etree.ElementTree as ET

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
        'WATCH': ('#ffd43b', '#212529'),
        'NO_POSITION': ('#495057', '#ffd43b'),
        'AVOID': ('#ff6b6b', '#fff'),
        'STRONG_SELL': ('#c92a2a', '#fff'),
    }
    return colors.get(rec.upper(), ('#495057', '#ffd43b'))


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


def get_scenario_prob(scenario: dict) -> float:
    """Get scenario probability as percentage (0-100)."""
    prob = scenario.get('probability_pct', scenario.get('probability', 0))
    if isinstance(prob, (int, float)) and prob <= 1:
        return prob * 100
    return prob


def get_scenario_return(scenario: dict) -> float:
    """Get scenario target return percentage."""
    return scenario.get('target_return_pct', scenario.get('return_pct', 0))


def get_scenario_target(scenario: dict) -> float:
    """Get scenario target price."""
    return scenario.get('target_price', scenario.get('price_target', 0))


def generate_svg(data: dict, source_file: str = '') -> str:
    """Generate SVG visualization from analysis data (light theme with pie chart)."""

    # Extract data with safe defaults (v2.6 structure)
    meta = data.get('_meta', {})
    doc_id = meta.get('id', '')
    ticker = data.get('ticker', meta.get('ticker', 'N/A'))
    company_name = data.get('company_name', meta.get('company_name', ''))
    analysis_date = data.get('analysis_date', meta.get('created', ''))
    version = str(meta.get('version', '2.6'))

    # Root level fields
    recommendation = data.get('recommendation', 'N/A')
    confidence_obj = data.get('confidence', {})
    confidence = confidence_obj.get('level', 0) if isinstance(confidence_obj, dict) else confidence_obj
    current_price = data.get('current_price', 0)

    # Summary for expected value and rationale
    summary = data.get('summary', {})

    # Setup section contains 52-week range and other key metrics (v2.6)
    setup = data.get('setup', {})
    high_52w = setup.get('fifty_two_week_high', 0)
    low_52w = setup.get('fifty_two_week_low', 0)

    # Fallback to technical if setup not available
    if not high_52w or not low_52w:
        technical = data.get('technical', {})
        key_levels = technical.get('key_levels', {})
        high_52w = high_52w or key_levels.get('52w_high', current_price * 1.5 if current_price else 0)
        low_52w = low_52w or key_levels.get('52w_low', current_price * 0.7 if current_price else 0)

    # Get percentages from setup or calculate
    pct_from_high = setup.get('distance_from_ath_pct', 0)
    pct_from_low = setup.get('distance_from_52w_low_pct', 0)
    if not pct_from_high and high_52w and current_price:
        pct_from_high = ((current_price - high_52w) / high_52w) * 100
    if not pct_from_low and low_52w and current_price:
        pct_from_low = ((current_price - low_52w) / low_52w) * 100

    ytd_return = setup.get('ytd_return_pct', 0)
    next_earnings = setup.get('next_earnings_date', '')
    days_to_earnings = setup.get('days_to_earnings', '')

    # Key metrics from fundamentals and setup
    fundamentals = data.get('fundamentals', {})
    valuation = fundamentals.get('valuation', {})
    forward_pe = setup.get('pe_forward', valuation.get('forward_pe', valuation.get('pe_forward', valuation.get('pe_ratio', 'N/A'))))
    market_cap_b = setup.get('market_cap_b', 0)
    if market_cap_b:
        market_cap = f"${market_cap_b}B"
    else:
        quality = fundamentals.get('quality', {})
        market_cap = quality.get('market_cap', valuation.get('market_cap', 'N/A'))

    # Do Nothing Gate (v2.6 structure)
    gate = data.get('do_nothing_gate', {})
    gate_result = gate.get('gate_result', 'FAIL')
    ev_check = gate.get('ev_passes', False)
    confidence_check = gate.get('confidence_passes', False)
    rr_check = gate.get('rr_passes', False)
    edge_check = gate.get('edge_exists', False)
    criteria_passed = gate.get('gates_passed', sum([ev_check, confidence_check, rr_check, edge_check]))

    # Gate logic:
    # - gate_result "FAIL" means trade criteria failed → Do Nothing Gate PASSES (don't trade)
    # - gate_result "PASS" means trade criteria passed → Open Trade Gate PASSES (can trade)
    do_nothing_passes = gate_result != 'PASS'  # If trade criteria fail, "do nothing" is correct
    open_trade_passes = gate_result == 'PASS'  # If trade criteria pass, "open trade" is correct

    # Gate actual values
    ev_actual = gate.get('ev_actual', 0)
    confidence_actual = gate.get('confidence_actual', confidence)
    rr_actual = gate.get('rr_actual', 'N/A')
    edge_reasoning = gate.get('edge_reasoning', '')

    # Scenarios (v2.6 uses strong_bull, base_bull, base_bear, strong_bear)
    scenarios = data.get('scenarios', {})
    strong_bull = scenarios.get('strong_bull', scenarios.get('bull_case', {}))
    base_bull = scenarios.get('base_bull', scenarios.get('base_case', {}))
    base_bear = scenarios.get('base_bear', scenarios.get('bear_case', {}))
    strong_bear = scenarios.get('strong_bear', scenarios.get('disaster_case', {}))

    # Get expected value
    expected_value = scenarios.get('expected_value', summary.get('expected_value_pct', 0))
    if isinstance(expected_value, dict):
        expected_value = expected_value.get('total', 0)

    # Comparable companies
    comparables = data.get('comparable_companies', {})
    peers = comparables.get('peers', [])
    discount_pct = comparables.get('discount_to_median_pct', 0)

    # Subject company valuation
    subject = comparables.get('subject', {})
    subject_pe = subject.get('pe_forward', forward_pe)
    subject_ps = subject.get('ps_ratio', valuation.get('ps_ratio', 'N/A'))
    subject_ev_ebitda = subject.get('ev_ebitda', valuation.get('ev_ebitda', 'N/A'))

    # Median values
    median = comparables.get('median', {})
    median_pe = median.get('pe_forward', 'N/A')
    median_ps = median.get('ps_ratio', 'N/A')
    median_ev_ebitda = median.get('ev_ebitda', 'N/A')

    # Steel-man cases
    bull_case = data.get('bull_case_analysis', {})
    bear_case = data.get('bear_case_analysis', {})
    base_case = data.get('base_case_analysis', {})
    bull_strength = bull_case.get('strength', bull_case.get('overall_strength', 5))
    bear_strength = bear_case.get('strength', bear_case.get('overall_strength', 5))
    base_strength = base_case.get('strength', base_case.get('overall_strength', 6))

    # Threats (v2.6 structure)
    threats = data.get('threat_assessment', {})
    # v2.6 uses primary_concern (structural/cyclical/moderate) as threat level
    primary_concern = threats.get('primary_concern', '').upper()
    threat_level = primary_concern if primary_concern in ['STRUCTURAL', 'CYCLICAL', 'ELEVATED'] else threats.get('threat_level', 'MODERATE')

    # Extract threat details from structural_threat or cyclical_weakness
    structural = threats.get('structural_threat', {})
    cyclical = threats.get('cyclical_weakness', {})

    if structural.get('exists', False):
        primary_threat = structural.get('description', '')
        threat_details = structural.get('moat_erosion_evidence', [])
    elif cyclical.get('exists', False):
        primary_threat = cyclical.get('description', f"Cyclical weakness - {cyclical.get('cycle_phase', '')}")
        threat_details = cyclical.get('recovery_catalysts', [])
    else:
        primary_threat = threats.get('primary_threat', threats.get('threat_summary', '')[:60])
        threat_details = threats.get('threat_details', [])

    # Liquidity
    liquidity = data.get('liquidity_analysis', {})
    liquidity_score = liquidity.get('liquidity_score', 5)
    adv_dollars = liquidity.get('adv_dollars', 0)
    bid_ask_spread = liquidity.get('bid_ask_spread_pct', 0)

    # Bias
    bias = data.get('bias_check', {})
    biases_detected = []
    if isinstance(bias, dict):
        if 'biases_detected' in bias:
            biases_detected = bias['biases_detected']
        else:
            for bias_type in ['recency_bias', 'confirmation_bias', 'anchoring', 'overconfidence',
                             'loss_aversion', 'fomo', 'value_trap_blindness', 'contrarian_trap']:
                bias_info = bias.get(bias_type, {})
                if isinstance(bias_info, dict) and bias_info.get('detected', False):
                    risk = bias_info.get('risk_level', 'MEDIUM')
                    biases_detected.append({'name': bias_type.replace('_', ' ').title(), 'risk': risk})

    # Alternative strategies
    alt_strategies = data.get('alternative_strategies', {})
    alternatives = []
    if isinstance(alt_strategies, dict):
        strategies = alt_strategies.get('strategies', [])
        for strat in strategies:
            if isinstance(strat, dict):
                alternatives.append(strat.get('strategy', 'N/A'))
            else:
                alternatives.append(str(strat))
    if not alternatives:
        alternatives = data.get('alternative_actions', summary.get('alternative_actions', []))

    # Meta-learning / Key Insights (v2.6 structure)
    meta_learning = data.get('meta_learning', {})
    pattern_identified = meta_learning.get('pattern_identified', '')
    comparison_to_past = meta_learning.get('comparison_to_past', '')

    # Extract key data source insights
    data_sources = meta_learning.get('data_source_effectiveness', [])
    high_predictive_sources = [s for s in data_sources if s.get('actual_predictive') == 'high']
    key_source_insight = ''
    if high_predictive_sources:
        src = high_predictive_sources[0]
        key_source_insight = f"{src.get('source', '')}: {src.get('notes', '')}"

    # Extract first sentence from comparison_to_past for display
    comparison_summary = ''
    if comparison_to_past:
        # Get first sentence or first 60 chars
        first_sentence = str(comparison_to_past).split('.')[0]
        comparison_summary = first_sentence[:55] if len(first_sentence) > 55 else first_sentence

    # === NEW: Additional data for gap filling ===

    # News Age Check
    news_age = data.get('news_age_check', {})
    news_items = news_age.get('items', [])[:3]
    fresh_catalyst = news_age.get('fresh_catalyst_exists', False)
    stale_news_risk = news_age.get('stale_news_risk', False)

    # Data Quality
    data_quality = data.get('data_quality', {})
    limitations = data_quality.get('limitations', [])[:2]

    # Post Mortem
    post_mortem = data.get('post_mortem', {})
    prior_analysis = post_mortem.get('prior_analysis', {})
    prior_rec = prior_analysis.get('recommendation', '')
    prior_confidence = prior_analysis.get('confidence', 0)

    # Catalyst
    catalyst = data.get('catalyst', {})
    catalyst_type = catalyst.get('type', '')
    catalyst_date = catalyst.get('date', '')
    catalyst_description = catalyst.get('description', '')[:50]

    # Market Environment
    market_env = data.get('market_environment', {})
    market_trend = market_env.get('trend', '')
    sector_trend = market_env.get('sector_trend', '')

    # Fundamentals - growth and margins
    growth = fundamentals.get('growth', {})
    rev_growth = growth.get('revenue_growth_yoy', 'N/A')
    eps_growth = growth.get('eps_growth_yoy', 'N/A')
    profitability = fundamentals.get('profitability', {})
    gross_margin = profitability.get('gross_margin', 'N/A')
    operating_margin = profitability.get('operating_margin', 'N/A')

    # Sentiment Details
    sentiment = data.get('sentiment', {})
    analyst_ratings = sentiment.get('analyst_ratings', {})
    buy_count = analyst_ratings.get('buy', 0)
    hold_count = analyst_ratings.get('hold', 0)
    sell_count = analyst_ratings.get('sell', 0)
    short_interest = sentiment.get('short_interest', {})
    short_pct = short_interest.get('pct_float', 0)
    options_pos = sentiment.get('options_positioning', {})
    put_call_ratio = options_pos.get('put_call_ratio', 'N/A')
    unusual_activity = options_pos.get('unusual_activity', '')

    # Trade Plan
    trade_plan = data.get('trade_plan', {})
    has_trade = trade_plan.get('trade', False)
    entry_config = trade_plan.get('entry', {})
    entry_price = entry_config.get('price', 0)
    entry_size_pct = entry_config.get('size_pct_portfolio', 0)
    stop_config = trade_plan.get('stop_loss', {})
    stop_price = stop_config.get('price', 0)
    targets_config = trade_plan.get('targets', {})
    target_1 = targets_config.get('target_1', 0)
    target_2 = targets_config.get('target_2', 0)

    # Options Strategy
    options_strategy = data.get('options_strategy', {})
    opt_structure = options_strategy.get('structure', '')
    opt_strikes = options_strategy.get('strikes', [])
    opt_expiry = options_strategy.get('expiry', '')
    opt_max_risk = options_strategy.get('max_risk', 0)

    # Alert Levels
    alert_levels = data.get('alert_levels', {})
    price_alerts = alert_levels.get('price_alerts', [])[:3]
    event_alerts = alert_levels.get('event_alerts', [])[:2]

    # Falsification
    falsification = data.get('falsification', {})
    thesis_invalid_if = falsification.get('thesis_invalid_if', '')[:100]
    bull_wrong_if = falsification.get('bull_thesis_wrong_if', [])[:2]

    # Thesis Reversal
    thesis_reversal = data.get('thesis_reversal', {})
    flip_conditions = thesis_reversal.get('conditions_to_flip', [])[:2]
    what_changes_mind = thesis_reversal.get('what_would_change_mind', '')[:80]

    # Scoring
    scoring = data.get('scoring', {})
    overall_score = scoring.get('overall_score', 0)

    # Grade
    grade = data.get('grade', {})
    letter_grade = grade.get('grade', '') if isinstance(grade, dict) else str(grade)

    # Rationale
    rationale = data.get('rationale', summary.get('narrative', ''))
    if isinstance(rationale, str):
        rationale_text = rationale[:200]
    else:
        rationale_text = ''

    # Watchlist Trigger
    watchlist_trigger = data.get('watchlist_trigger', '')

    # Action Items
    action_items = data.get('action_items', {})
    immediate_actions = action_items.get('immediate', [])[:3]

    # Recommendation colors
    rec_bg, rec_text = get_recommendation_color(recommendation)

    # Calculate price position in 52-week range (0-100%)
    if high_52w != low_52w:
        price_pct = ((current_price - low_52w) / (high_52w - low_52w)) * 100
    else:
        price_pct = 50

    # Calculate pie chart segments (circumference = 2 * pi * r = 502.65 for r=80)
    circumference = 502.65
    prob_sb = get_scenario_prob(strong_bull)
    prob_bb = get_scenario_prob(base_bull)
    prob_bear = get_scenario_prob(base_bear)
    prob_disaster = get_scenario_prob(strong_bear)

    # Stroke-dasharray calculations for pie chart
    seg_sb = prob_sb / 100 * circumference
    seg_bb = prob_bb / 100 * circumference
    seg_bear = prob_bear / 100 * circumference
    seg_disaster = prob_disaster / 100 * circumference

    offset_sb = 0
    offset_bb = -seg_sb
    offset_bear = -(seg_sb + seg_bb)
    offset_disaster = -(seg_sb + seg_bb + seg_bear)

    # Build SVG (Light Theme) - 5 rows + footer = 1020px height
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!--
  Stock Analysis Visualization v{version}
  Source: {escape_xml(source_file)}
  Document ID: {escape_xml(doc_id)}
  Generated: {escape_xml(analysis_date)}
-->
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1400" font-family="Arial, sans-serif">
  <defs>
    <linearGradient id="headerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#1a1a2e"/>
      <stop offset="100%" style="stop-color:#16213e"/>
    </linearGradient>
    <linearGradient id="bearGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#ff6b6b"/>
      <stop offset="100%" style="stop-color:#c92a2a"/>
    </linearGradient>
    <linearGradient id="bullGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#51cf66"/>
      <stop offset="100%" style="stop-color:#2f9e44"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.3"/>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="1200" height="1400" fill="#f8f9fa"/>

  <!-- Header -->
  <rect x="0" y="0" width="1200" height="100" fill="url(#headerGrad)"/>
  <text x="40" y="55" font-size="42" font-weight="bold" fill="#fff">{escape_xml(ticker)}</text>
  <text x="{60 + len(ticker) * 28}" y="55" font-size="24" fill="#adb5bd">{escape_xml(company_name)}</text>
  <text x="40" y="80" font-size="14" fill="#868e96">Stock Analysis v{version} | {escape_xml(analysis_date)}</text>

  <!-- Recommendation Badge -->
  <rect x="900" y="25" width="260" height="50" rx="25" fill="{rec_bg}" filter="url(#shadow)"/>
  <text x="1030" y="58" font-size="20" font-weight="bold" fill="{rec_text}" text-anchor="middle">{escape_xml(recommendation)}</text>

  <!-- Price Info Box -->
  <rect x="40" y="120" width="350" height="160" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="60" y="150" font-size="14" fill="#868e96">Current Price</text>
  <text x="60" y="185" font-size="36" font-weight="bold" fill="#212529">${current_price:.2f}</text>
  <text x="60" y="215" font-size="14" fill="#868e96">52-Week Range</text>

  <!-- Price Range Bar -->
  <rect x="60" y="230" width="310" height="12" rx="6" fill="#e9ecef"/>
  <rect x="60" y="230" width="{price_pct * 3.1:.0f}" height="12" rx="6" fill="#ff6b6b"/>
  <circle cx="{60 + price_pct * 3.1:.0f}" cy="236" r="8" fill="#228be6" stroke="#fff" stroke-width="2"/>
  <text x="330" y="215" font-size="10" fill="#228be6" text-anchor="end">{pct_from_low:.0f}% from low</text>
  <text x="60" y="260" font-size="12" fill="#868e96">${low_52w:.2f}</text>
  <text x="330" y="260" font-size="12" fill="#868e96" text-anchor="end">${high_52w:.2f}</text>

  <!-- Key Metrics Box -->
  <rect x="410" y="120" width="350" height="160" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="430" y="150" font-size="16" font-weight="bold" fill="#212529">Key Metrics</text>

  <text x="430" y="180" font-size="13" fill="#868e96">Forward P/E</text>
  <text x="560" y="180" font-size="13" font-weight="bold" fill="#212529">{escape_xml(str(forward_pe))}x</text>
  <text x="620" y="180" font-size="11" fill="#51cf66">({discount_pct:+.0f}% vs peers)</text>

  <text x="430" y="205" font-size="13" fill="#868e96">Market Cap</text>
  <text x="560" y="205" font-size="13" font-weight="bold" fill="#212529">{escape_xml(str(market_cap))}</text>

  <text x="430" y="230" font-size="13" fill="#868e96">YTD Return</text>
  <text x="560" y="230" font-size="13" font-weight="bold" fill="{'#ff6b6b' if ytd_return < 0 else '#51cf66'}">{ytd_return:+.1f}%</text>

  <text x="430" y="255" font-size="13" fill="#868e96">Next Earnings</text>
  <text x="560" y="255" font-size="13" font-weight="bold" fill="#212529">{escape_xml(str(next_earnings)[:6])}</text>
  <text x="620" y="255" font-size="11" fill="#868e96">({escape_xml(str(days_to_earnings))} days)</text>

  <!-- Gate Decision Box -->
  <rect x="780" y="120" width="380" height="160" rx="10" fill="#fff" filter="url(#shadow)"/>

  <!-- Two gate badges side by side -->
  <text x="800" y="145" font-size="11" fill="#868e96">Do Nothing Gate</text>
  <rect x="800" y="150" width="80" height="22" rx="11" fill="{get_gate_color(do_nothing_passes)}"/>
  <text x="840" y="165" font-size="10" font-weight="bold" fill="#fff" text-anchor="middle">{'PASS' if do_nothing_passes else 'FAIL'}</text>

  <text x="900" y="145" font-size="11" fill="#868e96">Open Trade Gate</text>
  <rect x="900" y="150" width="80" height="22" rx="11" fill="{get_gate_color(open_trade_passes)}"/>
  <text x="940" y="165" font-size="10" font-weight="bold" fill="#fff" text-anchor="middle">{'PASS' if open_trade_passes else 'FAIL'}</text>

  <!-- Criteria summary -->
  <text x="1000" y="145" font-size="11" fill="#868e96">Criteria</text>
  <rect x="1000" y="150" width="70" height="22" rx="11" fill="{'#51cf66' if criteria_passed >= 4 else '#ffd43b' if criteria_passed >= 3 else '#ff6b6b'}"/>
  <text x="1035" y="165" font-size="10" font-weight="bold" fill="#fff" text-anchor="middle">{criteria_passed}/4</text>

  <!-- Gate criteria details -->
  <text x="800" y="195" font-size="12" fill="#868e96">Expected Value &gt;5%</text>
  <text x="980" y="195" font-size="12" fill="#212529">{ev_actual:.1f}%</text>
  <circle cx="1040" cy="191" r="8" fill="{get_gate_color(ev_check)}"/>
  <text x="1040" y="195" font-size="10" fill="#fff" text-anchor="middle">{'✓' if ev_check else '✗'}</text>

  <text x="800" y="218" font-size="12" fill="#868e96">Confidence &gt;60%</text>
  <text x="980" y="218" font-size="12" fill="#212529">{confidence_actual}%</text>
  <circle cx="1040" cy="214" r="8" fill="{get_gate_color(confidence_check)}"/>
  <text x="1040" y="218" font-size="10" fill="#fff" text-anchor="middle">{'✓' if confidence_check else '✗'}</text>

  <text x="800" y="241" font-size="12" fill="#868e96">Risk:Reward &gt;2:1</text>
  <text x="980" y="241" font-size="12" fill="#212529">{escape_xml(str(rr_actual))}</text>
  <circle cx="1040" cy="237" r="8" fill="{get_gate_color(rr_check)}"/>
  <text x="1040" y="241" font-size="10" fill="#fff" text-anchor="middle">{'✓' if rr_check else '✗'}</text>

  <text x="800" y="264" font-size="12" fill="#868e96">Edge Not Priced</text>
  <text x="980" y="264" font-size="12" fill="#212529">{'Yes' if edge_check else 'No'}</text>
  <circle cx="1040" cy="260" r="8" fill="{get_gate_color(edge_check)}"/>
  <text x="1040" y="264" font-size="10" fill="#fff" text-anchor="middle">{'✓' if edge_check else '✗'}</text>

  <!-- Scenario Analysis -->
  <rect x="40" y="300" width="540" height="280" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="60" y="330" font-size="16" font-weight="bold" fill="#212529">Scenario Analysis</text>
  <text x="500" y="330" font-size="14" fill="#868e96" text-anchor="end">EV: {expected_value:.1f}%</text>

  <!-- Scenario bars -->
  <text x="60" y="370" font-size="12" fill="#212529">Strong Bull ({prob_sb:.0f}%)</text>
  <rect x="200" y="358" width="{prob_sb * 1.5:.0f}" height="20" rx="4" fill="#2f9e44"/>
  <text x="{210 + prob_sb * 1.5:.0f}" y="372" font-size="12" fill="#2f9e44">{get_scenario_return(strong_bull):+.1f}% → ${get_scenario_target(strong_bull):.0f}</text>

  <text x="60" y="410" font-size="12" fill="#212529">Base Bull ({prob_bb:.0f}%)</text>
  <rect x="200" y="398" width="{prob_bb * 1.2:.0f}" height="20" rx="4" fill="#51cf66"/>
  <text x="{210 + prob_bb * 1.2:.0f}" y="412" font-size="12" fill="#51cf66">{get_scenario_return(base_bull):+.1f}% → ${get_scenario_target(base_bull):.0f}</text>

  <text x="60" y="450" font-size="12" fill="#212529">Base Bear ({prob_bear:.0f}%)</text>
  <rect x="200" y="438" width="{prob_bear * 0.7:.0f}" height="20" rx="4" fill="#ff8787"/>
  <text x="{210 + prob_bear * 0.7:.0f}" y="452" font-size="12" fill="#ff6b6b">{get_scenario_return(base_bear):+.1f}% → ${get_scenario_target(base_bear):.0f}</text>

  <text x="60" y="490" font-size="12" fill="#212529">Strong Bear ({prob_disaster:.0f}%)</text>
  <rect x="200" y="478" width="{prob_disaster * 1.6:.0f}" height="20" rx="4" fill="#c92a2a"/>
  <text x="{210 + prob_disaster * 1.6:.0f}" y="492" font-size="12" fill="#c92a2a">{get_scenario_return(strong_bear):+.1f}% → ${get_scenario_target(strong_bear):.0f}</text>

  <!-- Probability pie chart -->
  <circle cx="480" cy="440" r="80" fill="none" stroke="#e9ecef" stroke-width="30"/>
  <!-- Strong Bull segment -->
  <circle cx="480" cy="440" r="80" fill="none" stroke="#2f9e44" stroke-width="30"
          stroke-dasharray="{seg_sb:.1f} {circumference - seg_sb:.1f}" stroke-dashoffset="{offset_sb:.1f}" transform="rotate(-90 480 440)"/>
  <!-- Base Bull segment -->
  <circle cx="480" cy="440" r="80" fill="none" stroke="#51cf66" stroke-width="30"
          stroke-dasharray="{seg_bb:.1f} {circumference - seg_bb:.1f}" stroke-dashoffset="{offset_bb:.1f}" transform="rotate(-90 480 440)"/>
  <!-- Base Bear segment -->
  <circle cx="480" cy="440" r="80" fill="none" stroke="#ff8787" stroke-width="30"
          stroke-dasharray="{seg_bear:.1f} {circumference - seg_bear:.1f}" stroke-dashoffset="{offset_bear:.1f}" transform="rotate(-90 480 440)"/>
  <!-- Strong Bear segment -->
  <circle cx="480" cy="440" r="80" fill="none" stroke="#c92a2a" stroke-width="30"
          stroke-dasharray="{seg_disaster:.1f} {circumference - seg_disaster:.1f}" stroke-dashoffset="{offset_disaster:.1f}" transform="rotate(-90 480 440)"/>
  <text x="480" y="435" font-size="14" font-weight="bold" fill="#212529" text-anchor="middle">EV</text>
  <text x="480" y="455" font-size="18" font-weight="bold" fill="#212529" text-anchor="middle">{expected_value:.1f}%</text>

  <!-- Comparable Companies -->
  <rect x="600" y="300" width="560" height="280" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="620" y="330" font-size="16" font-weight="bold" fill="#212529">Comparable Companies</text>
  <text x="1080" y="330" font-size="12" fill="{'#51cf66' if discount_pct < 0 else '#ff6b6b'}" text-anchor="end">{ticker} at {abs(discount_pct):.0f}% {'discount' if discount_pct < 0 else 'premium'}</text>

  <!-- Table header -->
  <rect x="620" y="345" width="520" height="25" fill="#f1f3f5"/>
  <text x="640" y="362" font-size="11" font-weight="bold" fill="#495057">Ticker</text>
  <text x="740" y="362" font-size="11" font-weight="bold" fill="#495057">P/E Fwd</text>
  <text x="830" y="362" font-size="11" font-weight="bold" fill="#495057">P/S</text>
  <text x="910" y="362" font-size="11" font-weight="bold" fill="#495057">EV/EBITDA</text>
  <text x="1020" y="362" font-size="11" font-weight="bold" fill="#495057">Mkt Cap</text>

  <!-- Subject row (highlighted) -->
  <rect x="620" y="372" width="520" height="28" fill="#fff3bf"/>
  <text x="640" y="390" font-size="12" font-weight="bold" fill="#212529">{escape_xml(ticker)}</text>
  <text x="740" y="390" font-size="12" fill="#212529">{escape_xml(str(subject_pe))}</text>
  <text x="830" y="390" font-size="12" fill="#212529">{escape_xml(str(subject_ps))}</text>
  <text x="910" y="390" font-size="12" fill="#212529">{escape_xml(str(subject_ev_ebitda))}</text>
  <text x="1020" y="390" font-size="12" fill="#212529">{escape_xml(str(market_cap))}</text>
'''

    # Add peer rows
    y_offset = 420
    for i, peer in enumerate(peers[:4]):  # Max 4 peers
        peer_ticker = peer.get('ticker', 'N/A')
        peer_pe = peer.get('pe_forward', peer.get('forward_pe', 'N/A'))
        peer_ps = peer.get('ps_ratio', 'N/A')
        peer_ev = peer.get('ev_ebitda', 'N/A')
        peer_cap = peer.get('market_cap', 'N/A')
        svg += f'''  <text x="640" y="{y_offset}" font-size="12" fill="#495057">{escape_xml(str(peer_ticker))}</text>
  <text x="740" y="{y_offset}" font-size="12" fill="#495057">{escape_xml(str(peer_pe))}</text>
  <text x="830" y="{y_offset}" font-size="12" fill="#495057">{escape_xml(str(peer_ps))}</text>
  <text x="910" y="{y_offset}" font-size="12" fill="#495057">{escape_xml(str(peer_ev))}</text>
  <text x="1020" y="{y_offset}" font-size="12" fill="#495057">{escape_xml(str(peer_cap))}</text>
'''
        y_offset += 28

    # Median row
    svg += f'''  <!-- Median row -->
  <rect x="620" y="515" width="520" height="25" fill="#e9ecef"/>
  <text x="640" y="532" font-size="11" font-weight="bold" fill="#495057">MEDIAN</text>
  <text x="740" y="532" font-size="11" font-weight="bold" fill="#495057">{escape_xml(str(median_pe))}</text>
  <text x="830" y="532" font-size="11" font-weight="bold" fill="#495057">{escape_xml(str(median_ps))}</text>
  <text x="910" y="532" font-size="11" font-weight="bold" fill="#495057">{escape_xml(str(median_ev_ebitda))}</text>

  <!-- Threat Assessment -->
  <rect x="40" y="600" width="360" height="140" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="60" y="630" font-size="16" font-weight="bold" fill="#212529">Threat Assessment</text>
  <rect x="280" y="612" width="100" height="26" rx="13" fill="{'#c92a2a' if threat_level == 'STRUCTURAL' else '#ff6b6b' if threat_level == 'ELEVATED' else '#ffd43b'}"/>
  <text x="330" y="630" font-size="11" font-weight="bold" fill="#fff" text-anchor="middle">{escape_xml(threat_level)}</text>

  <text x="60" y="660" font-size="12" fill="#495057">{escape_xml(str(primary_threat)[:40])}</text>
'''

    # Threat details
    y_td = 680
    for detail in threat_details[:3]:
        svg += f'''  <text x="60" y="{y_td}" font-size="11" fill="#868e96">• {escape_xml(str(detail)[:45])}</text>
'''
        y_td += 18

    svg += f'''
  <!-- Bull/Bear Strength -->
  <rect x="420" y="600" width="360" height="140" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="440" y="630" font-size="16" font-weight="bold" fill="#212529">Case Strength</text>

  <!-- Bull bar -->
  <text x="440" y="660" font-size="12" fill="#495057">Bull Case</text>
  <rect x="520" y="648" width="200" height="16" rx="4" fill="#e9ecef"/>
  <rect x="520" y="648" width="{bull_strength * 20}" height="16" rx="4" fill="#51cf66"/>
  <text x="730" y="660" font-size="12" fill="#495057">{bull_strength}/10</text>

  <!-- Base bar -->
  <text x="440" y="690" font-size="12" fill="#495057">Base Case</text>
  <rect x="520" y="678" width="200" height="16" rx="4" fill="#e9ecef"/>
  <rect x="520" y="678" width="{base_strength * 20}" height="16" rx="4" fill="#ffd43b"/>
  <text x="730" y="690" font-size="12" fill="#495057">{base_strength}/10</text>

  <!-- Bear bar -->
  <text x="440" y="720" font-size="12" fill="#495057">Bear Case</text>
  <rect x="520" y="708" width="200" height="16" rx="4" fill="#e9ecef"/>
  <rect x="520" y="708" width="{bear_strength * 20}" height="16" rx="4" fill="#ff6b6b"/>
  <text x="730" y="720" font-size="12" fill="#495057">{bear_strength}/10</text>

  <!-- Alternative Actions -->
  <rect x="800" y="600" width="360" height="140" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="820" y="630" font-size="16" font-weight="bold" fill="#212529">Alternative Actions</text>
'''

    # Alternative actions
    y_alt = 660
    for alt in alternatives[:3]:
        svg += f'''  <circle cx="835" cy="{y_alt - 5}" r="6" fill="#228be6"/>
  <text x="850" y="{y_alt}" font-size="12" fill="#495057">{escape_xml(str(alt)[:35])}</text>
'''
        y_alt += 30

    svg += f'''
  <!-- Liquidity Score -->
  <rect x="40" y="760" width="200" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="60" y="790" font-size="14" font-weight="bold" fill="#212529">Liquidity</text>
  <text x="60" y="820" font-size="28" font-weight="bold" fill="{'#51cf66' if liquidity_score >= 7 else '#ffd43b' if liquidity_score >= 5 else '#ff6b6b'}">{liquidity_score}/10</text>
  <text x="60" y="840" font-size="11" fill="#868e96">ADV: ${format_number(adv_dollars)} | Spread: {bid_ask_spread:.2f}%</text>

  <!-- Confidence -->
  <rect x="260" y="760" width="200" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="280" y="790" font-size="14" font-weight="bold" fill="#212529">Confidence</text>
  <text x="280" y="820" font-size="28" font-weight="bold" fill="{'#51cf66' if confidence >= 60 else '#ffd43b'}">{confidence}%</text>
  <text x="280" y="840" font-size="11" fill="#868e96">{'Above' if confidence >= 60 else 'Below'} 60% threshold</text>

  <!-- Biases Checked -->
  <rect x="480" y="760" width="280" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="500" y="790" font-size="14" font-weight="bold" fill="#212529">Biases Detected</text>
'''

    # Bias details
    y_bias = 815
    if biases_detected:
        for b in biases_detected[:3]:
            if isinstance(b, dict):
                name = b.get('name', 'Unknown')
                risk = b.get('risk', 'MEDIUM')
            else:
                name = str(b)
                risk = 'MEDIUM'
            color = '#ff6b6b' if risk == 'HIGH' else '#ffd43b'
            svg += f'''  <text x="500" y="{y_bias}" font-size="11" fill="{color}">• {escape_xml(name)} ({risk})</text>
'''
            y_bias += 18
    else:
        svg += '''  <text x="500" y="815" font-size="11" fill="#51cf66">No significant biases detected</text>
'''

    # Action items for Next Steps box
    action_items = data.get('action_items', {})
    immediate_actions = action_items.get('immediate', [])
    post_review_date = meta_learning.get('post_analysis_review_date', '')

    svg += f'''
  <!-- Next Steps -->
  <rect x="780" y="760" width="380" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="800" y="790" font-size="14" font-weight="bold" fill="#212529">Next Steps</text>
  <text x="800" y="815" font-size="12" fill="#495057">Review Date: <tspan font-weight="bold">{escape_xml(str(post_review_date)[:20])}</tspan></text>
  <text x="800" y="838" font-size="11" fill="#868e96">• {escape_xml(str(immediate_actions[0])[:45]) if immediate_actions else 'See analysis'}</text>
  <text x="800" y="855" font-size="11" fill="#868e96">• {escape_xml(str(immediate_actions[1])[:45]) if len(immediate_actions) > 1 else ''}</text>

  <!-- ROW 5: Meta-Learning -->
  <rect x="40" y="880" width="380" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="60" y="910" font-size="14" font-weight="bold" fill="#212529">Pattern Identified</text>
  <text x="60" y="935" font-size="16" font-weight="bold" fill="#228be6">{escape_xml(str(pattern_identified)[:40]) if pattern_identified else 'None'}</text>
  <text x="60" y="960" font-size="11" fill="#868e96">{escape_xml(str(comparison_summary)[:55])}</text>

  <!-- Data Source Effectiveness -->
  <rect x="440" y="880" width="360" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="460" y="910" font-size="14" font-weight="bold" fill="#212529">Data Source Effectiveness</text>
'''

    # Add data source rows
    y_src = 935
    for src in data_sources[:2]:
        src_name = src.get('source', '')[:20]
        predictive = src.get('actual_predictive', 'medium')
        notes = src.get('notes', '')[:35]
        color = '#51cf66' if predictive == 'high' else '#ffd43b' if predictive == 'medium' else '#868e96'
        svg += f'''  <text x="460" y="{y_src}" font-size="11" fill="{color}">• {escape_xml(src_name)}: {escape_xml(notes)}</text>
'''
        y_src += 20

    svg += f'''
  <!-- Comparison to Past -->
  <rect x="820" y="880" width="340" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="840" y="910" font-size="14" font-weight="bold" fill="#212529">Historical Comparison</text>
'''
    # Word wrap comparison text into 3 lines of ~45 chars
    comp_text = str(comparison_to_past).replace('\n', ' ').strip()
    comp_words = comp_text.split()
    comp_lines = []
    current_line = []
    for word in comp_words:
        current_line.append(word)
        if len(' '.join(current_line)) > 42:
            comp_lines.append(' '.join(current_line[:-1]))
            current_line = [word]
    if current_line:
        comp_lines.append(' '.join(current_line))

    svg += f'''  <text x="840" y="935" font-size="11" fill="#495057">{escape_xml(comp_lines[0]) if comp_lines else ''}</text>
  <text x="840" y="953" font-size="11" fill="#868e96">{escape_xml(comp_lines[1]) if len(comp_lines) > 1 else ''}</text>
  <text x="840" y="971" font-size="10" fill="#868e96">{escape_xml(comp_lines[2]) if len(comp_lines) > 2 else ''}</text>

  <!-- ROW 6: News & Data, Fundamentals, Sentiment -->

  <!-- News & Data Quality -->
  <rect x="40" y="1000" width="380" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="60" y="1030" font-size="14" font-weight="bold" fill="#212529">News &amp; Data Quality</text>
  <circle cx="350" cy="1025" r="8" fill="{'#51cf66' if fresh_catalyst else '#ffd43b'}"/>
  <text x="370" y="1030" font-size="11" fill="{'#51cf66' if fresh_catalyst else '#ffd43b'}">{'Fresh' if fresh_catalyst else 'Stale'}</text>
'''

    # Add news items
    y_news = 1055
    for item in news_items[:3]:
        if isinstance(item, dict):
            headline = item.get('headline', item.get('title', ''))[:40]
            age = item.get('age_hours', item.get('age', 'N/A'))
        else:
            headline = str(item)[:40]
            age = 'N/A'
        svg += f'''  <text x="60" y="{y_news}" font-size="10" fill="#495057">• {escape_xml(headline)} ({age}h)</text>
'''
        y_news += 16

    # Add limitations
    if limitations:
        svg += f'''  <text x="60" y="1090" font-size="10" fill="#868e96">Limits: {escape_xml(str(limitations[0])[:50])}</text>
'''

    svg += f'''
  <!-- Fundamentals Growth -->
  <rect x="440" y="1000" width="360" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="460" y="1030" font-size="14" font-weight="bold" fill="#212529">Fundamentals</text>

  <text x="460" y="1055" font-size="12" fill="#868e96">Revenue Growth YoY</text>
  <text x="620" y="1055" font-size="12" font-weight="bold" fill="{'#51cf66' if isinstance(rev_growth, (int, float)) and rev_growth > 0 else '#ff6b6b'}">{escape_xml(str(rev_growth))}{'%' if isinstance(rev_growth, (int, float)) else ''}</text>

  <text x="460" y="1075" font-size="12" fill="#868e96">EPS Growth YoY</text>
  <text x="620" y="1075" font-size="12" font-weight="bold" fill="{'#51cf66' if isinstance(eps_growth, (int, float)) and eps_growth > 0 else '#ff6b6b'}">{escape_xml(str(eps_growth))}{'%' if isinstance(eps_growth, (int, float)) else ''}</text>

  <text x="460" y="1095" font-size="12" fill="#868e96">Gross Margin</text>
  <text x="620" y="1095" font-size="12" fill="#212529">{escape_xml(str(gross_margin))}{'%' if isinstance(gross_margin, (int, float)) else ''}</text>

  <text x="700" y="1055" font-size="12" fill="#868e96">Op Margin</text>
  <text x="760" y="1055" font-size="12" fill="#212529">{escape_xml(str(operating_margin))}{'%' if isinstance(operating_margin, (int, float)) else ''}</text>

  <!-- Sentiment Details -->
  <rect x="820" y="1000" width="340" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="840" y="1030" font-size="14" font-weight="bold" fill="#212529">Sentiment Details</text>

  <text x="840" y="1055" font-size="11" fill="#868e96">Analyst Ratings:</text>
  <text x="925" y="1055" font-size="11" fill="#51cf66">{buy_count}B</text>
  <text x="955" y="1055" font-size="11" fill="#ffd43b">{hold_count}H</text>
  <text x="985" y="1055" font-size="11" fill="#ff6b6b">{sell_count}S</text>

  <text x="840" y="1075" font-size="11" fill="#868e96">Short Interest:</text>
  <text x="925" y="1075" font-size="11" fill="{'#ff6b6b' if short_pct > 10 else '#495057'}">{short_pct:.1f}% of float</text>

  <text x="840" y="1095" font-size="11" fill="#868e96">P/C Ratio:</text>
  <text x="905" y="1095" font-size="11" fill="#495057">{escape_xml(str(put_call_ratio))}</text>
  <text x="1000" y="1095" font-size="10" fill="#228be6">{escape_xml(str(unusual_activity)[:20])}</text>

  <!-- ROW 7: Trade Plan, Alerts, Falsification -->

  <!-- Trade Plan or Pass Reasoning -->
  <rect x="40" y="1120" width="380" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="60" y="1150" font-size="14" font-weight="bold" fill="#212529">{'Trade Plan' if has_trade else 'No Trade - Pass'}</text>
'''

    if has_trade:
        svg += f'''  <text x="60" y="1175" font-size="12" fill="#868e96">Entry:</text>
  <text x="110" y="1175" font-size="12" font-weight="bold" fill="#212529">${entry_price:.2f} ({entry_size_pct:.1f}% port)</text>

  <text x="60" y="1195" font-size="12" fill="#868e96">Stop:</text>
  <text x="110" y="1195" font-size="12" font-weight="bold" fill="#ff6b6b">${stop_price:.2f}</text>

  <text x="200" y="1195" font-size="12" fill="#868e96">Targets:</text>
  <text x="260" y="1195" font-size="12" font-weight="bold" fill="#51cf66">${target_1:.0f} / ${target_2:.0f}</text>

  <text x="60" y="1212" font-size="10" fill="#228be6">{escape_xml(str(opt_structure)[:40]) if opt_structure else 'Stock position'}</text>
'''
    else:
        # Show why passing
        pass_reasons = []
        if not ev_check:
            pass_reasons.append(f"EV {ev_actual:.1f}% below threshold")
        if not confidence_check:
            pass_reasons.append(f"Confidence {confidence_actual}% too low")
        if not rr_check:
            pass_reasons.append(f"R:R {rr_actual} insufficient")
        if not edge_check:
            pass_reasons.append("Edge already priced in")
        for i, reason in enumerate(pass_reasons[:3]):
            svg += f'''  <text x="60" y="{1175 + i*20}" font-size="11" fill="#ff6b6b">• {escape_xml(reason)}</text>
'''

    svg += f'''
  <!-- Alert Levels -->
  <rect x="440" y="1120" width="360" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="460" y="1150" font-size="14" font-weight="bold" fill="#212529">Alert Levels</text>
'''

    # Price alerts
    y_alert = 1175
    for alert in price_alerts[:3]:
        if isinstance(alert, dict):
            price = alert.get('price', alert.get('level', 0))
            action = alert.get('action', alert.get('description', ''))[:25]
        else:
            price = alert
            action = ''
        svg += f'''  <text x="460" y="{y_alert}" font-size="11" fill="#495057">${price:.2f} → {escape_xml(action)}</text>
'''
        y_alert += 18

    # Event alerts
    for event in event_alerts[:2]:
        if isinstance(event, dict):
            desc = event.get('event', event.get('description', ''))[:35]
        else:
            desc = str(event)[:35]
        svg += f'''  <text x="460" y="{y_alert}" font-size="10" fill="#228be6">📅 {escape_xml(desc)}</text>
'''
        y_alert += 16

    svg += f'''
  <!-- Falsification Criteria -->
  <rect x="820" y="1120" width="340" height="100" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="840" y="1150" font-size="14" font-weight="bold" fill="#212529">Falsification</text>
  <text x="840" y="1175" font-size="11" fill="#495057">Thesis invalid if:</text>
'''

    # Falsification details
    if thesis_invalid_if:
        # Word wrap the invalidation condition
        words = thesis_invalid_if.split()
        lines_f = []
        curr = []
        for w in words:
            curr.append(w)
            if len(' '.join(curr)) > 38:
                lines_f.append(' '.join(curr[:-1]))
                curr = [w]
        if curr:
            lines_f.append(' '.join(curr))

        y_f = 1190
        for line in lines_f[:2]:
            svg += f'''  <text x="840" y="{y_f}" font-size="10" fill="#ff6b6b">{escape_xml(line)}</text>
'''
            y_f += 14

    for i, cond in enumerate(bull_wrong_if[:2]):
        svg += f'''  <text x="840" y="{1190 + 14 * (2 + i)}" font-size="10" fill="#868e96">• {escape_xml(str(cond)[:38])}</text>
'''

    svg += f'''
  <!-- ROW 8: Rationale Text Box -->
  <rect x="40" y="1240" width="1120" height="120" rx="10" fill="#fff" filter="url(#shadow)"/>
  <text x="60" y="1270" font-size="14" font-weight="bold" fill="#212529">Rationale</text>
'''

    # Word wrap rationale into multiple lines
    rationale_full = str(rationale_text).replace('\n', ' ').strip()
    r_words = rationale_full.split()
    r_lines = []
    r_curr = []
    for w in r_words:
        r_curr.append(w)
        if len(' '.join(r_curr)) > 120:
            r_lines.append(' '.join(r_curr[:-1]))
            r_curr = [w]
    if r_curr:
        r_lines.append(' '.join(r_curr))

    y_rat = 1295
    for line in r_lines[:4]:
        svg += f'''  <text x="60" y="{y_rat}" font-size="11" fill="#495057">{escape_xml(line)}</text>
'''
        y_rat += 18

    # Add watchlist trigger if present
    if watchlist_trigger:
        svg += f'''  <text x="60" y="1350" font-size="11" fill="#228be6">Watchlist Trigger: {escape_xml(str(watchlist_trigger)[:80])}</text>
'''

    svg += f'''
  <!-- Footer -->
  <rect x="0" y="1380" width="1200" height="20" fill="#1a1a2e"/>
  <text x="40" y="1394" font-size="9" fill="#868e96">Source: {escape_xml(source_file.split('/')[-1]) if source_file else doc_id}</text>
  <text x="1160" y="1394" font-size="9" fill="#868e96" text-anchor="end">Tradegent v{version} | {escape_xml(analysis_date)}</text>
</svg>'''

    return svg


def main():
    parser = argparse.ArgumentParser(description='Generate SVG visualization from stock analysis YAML')
    parser.add_argument('input', help='Path to analysis YAML file')
    parser.add_argument('--output', '-o', help='Output SVG path (default: same as input with .svg extension)')
    parser.add_argument('--json', action='store_true', help='Output result as JSON')

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.with_suffix('.svg')

    try:
        # Load analysis
        data = load_analysis(input_path)

        # Validate it's a v2.6 analysis
        version = str(data.get('_meta', {}).get('version', ''))
        if not version.startswith('2.'):
            print(f"Warning: Analysis version {version} may not be fully compatible", file=sys.stderr)

        # Generate SVG with source file reference
        svg_content = generate_svg(data, source_file=str(input_path))

        # Validate SVG (XML parsing check)
        try:
            ET.fromstring(svg_content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid SVG generated: {e}")

        # Write output
        with open(output_path, 'w') as f:
            f.write(svg_content)

        if args.json:
            print(json.dumps({
                'success': True,
                'input': str(input_path),
                'output': str(output_path),
                'size_bytes': len(svg_content),
                'ticker': data.get('ticker', data.get('_meta', {}).get('ticker', 'unknown')),
                'version': version
            }))
        else:
            print(f"Generated: {output_path} ({len(svg_content):,} bytes)")

    except Exception as e:
        if args.json:
            print(json.dumps({'success': False, 'error': str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
