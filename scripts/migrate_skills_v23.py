#!/usr/bin/env python3
"""
Migration script: Upgrade skill documents from v1/v2.1 to v2.3

This script adds missing v2.3 fields to existing YAML documents in
the tradegent_knowledge/knowledge/ directory while preserving existing data.

Usage:
    python scripts/migrate_skills_v23.py --dry-run  # Preview changes
    python scripts/migrate_skills_v23.py            # Apply changes

v2.3 additions:
- stock-analysis: data_quality, news_age_check, post_mortem, threat_assessment,
                  expectations_assessment, bear_case_analysis, enhanced bias_check,
                  do_nothing_gate, falsification, thesis_reversal, alert_levels,
                  alternative_strategies, trade_plan, summary, meta_learning
- earnings-analysis: historical_moves, news_age_check, expectations_assessment,
                     bear_case_analysis, enhanced bias_check, falsification, meta_learning
- research-analysis: counter_thesis, bias_check
- watchlist: thesis_reasoning, conviction, analysis_quality_check
- trade-journal: pre_trade_checklist, psychological_state, decision_quality, loss_aversion_check
- post-trade-review: data_source_effectiveness, countermeasures_needed, rule_validation
- ticker-profile: analysis_track_record, bias_history, learned_patterns, known_risks
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Any

import yaml


# Preserve YAML formatting
class PreservingDumper(yaml.SafeDumper):
    pass


def str_representer(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


PreservingDumper.add_representer(str, str_representer)


# v2.3 default structures for each document type
V23_STOCK_ANALYSIS_ADDITIONS = {
    'data_quality': {
        'sources_checked': [],
        'data_freshness': {
            'price_data': None,
            'fundamentals': None,
            'news': None,
        },
        'concerns': None,
        'recommendations': None,
    },
    'news_age_check': {
        'oldest_news_used': None,
        'age_days': None,
        'acceptable': None,
        'concerns': None,
    },
    'post_mortem': {
        'prior_analyses_found': 0,
        'analyses_reviewed': [],
        'accuracy_summary': None,
        'lessons_learned': None,
        'adjustments_made': None,
    },
    'expectations_assessment': {
        'bar_level': None,  # low / medium / high / very_high
        'reasoning': None,
        'what_beats_expectations': None,
        'what_disappoints': None,
    },
    'bear_case_analysis': {
        'summary': None,
        'strength': None,  # 1-10
        'arguments': [],
        'strongest_argument': None,
        'why_bull_wins': None,
        'conditions_where_bear_wins': None,
    },
    'threat_assessment': {
        'structural_threats': [],
        'cyclical_risks': [],
        'execution_risks': [],
        'summary': None,
    },
    'thesis_reversal': {
        'current_thesis_direction': None,
        'would_change_thesis': None,
        'reversal_triggers': None,
    },
    'bias_check': {
        'biases_detected': [],
        'pre_exit_gate': {
            'thesis_intact': None,
            'catalyst_pending': None,
            'exit_reason': None,
            'gate_result': None,
        },
        'countermeasures_applied': [],
        'estimated_cost_total': None,
    },
    'do_nothing_gate': {
        'criteria': {
            'ev_positive': None,
            'confidence_above_60': None,
            'rr_above_2': None,
            'edge_exists': None,
        },
        'pass': None,
        'pass_reasoning': None,
    },
    'falsification': {
        'conditions': [],
        'thesis_invalid_if': None,
    },
    'alert_levels': {
        'warning_triggers': None,
        'exit_triggers': None,
    },
    'alternative_strategies': [],
    'trade_plan': {
        'entry_criteria': None,
        'entry_price': None,
        'position_size_pct': None,
        'position_sizing_rationale': None,
        'stop_loss': None,
        'target_1': None,
        'target_2': None,
        'exit_criteria': None,
        'max_holding_days': None,
    },
    'summary': {
        'thesis_summary': None,
        'key_risk': None,
        'action': None,
    },
    'meta_learning': {
        'patterns_applied': [],
        'rules_tested': [],
        'new_learning': {
            'learning': None,
            'learning_type': None,
            'validation_criteria': None,
            'creates_learning_file': False,
        },
    },
}

V23_EARNINGS_ANALYSIS_ADDITIONS = {
    'historical_moves': {
        'quarters_analyzed': 8,
        'data': [],
        'pattern_summary': None,
        'expected_range': None,
    },
    'news_age_check': {
        'oldest_news_used': None,
        'age_days': None,
        'acceptable': None,
        'concerns': None,
    },
    'expectations_assessment': {
        'bar_level': None,
        'reasoning': None,
        'what_beats_expectations': None,
        'what_disappoints': None,
    },
    'bear_case_analysis': {
        'summary': None,
        'strength': None,
        'arguments': [],
        'strongest_argument': None,
        'why_bull_wins': None,
        'conditions_where_bear_wins': None,
    },
    'bias_check': {
        'biases_detected': [],
        'pre_exit_gate': {
            'thesis_intact': None,
            'catalyst_pending': None,
            'exit_reason': None,
            'gate_result': None,
        },
        'countermeasures_applied': [],
        'estimated_cost_total': None,
    },
    'falsification': {
        'conditions': [],
        'thesis_invalid_if': None,
    },
    'meta_learning': {
        'patterns_applied': [],
        'rules_tested': [],
        'new_learning': {
            'learning': None,
            'learning_type': None,
            'validation_criteria': None,
            'creates_learning_file': False,
        },
    },
}

V23_RESEARCH_ANALYSIS_ADDITIONS = {
    'counter_thesis': {
        'statement': None,
        'arguments': [],
        'strength': None,
        'why_thesis_wins': None,
        'conditions_where_counter_wins': None,
    },
    'bias_check': {
        'confirmation_bias': {
            'checked': False,
            'contrary_sources_checked': None,
            'notes': None,
        },
        'recency_bias': {
            'checked': False,
            'historical_patterns_checked': None,
            'notes': None,
        },
        'overconfidence': {
            'checked': False,
            'calibration_note': None,
            'notes': None,
        },
        'anchoring': {
            'checked': False,
            'anchor_value': None,
            'notes': None,
        },
        'both_sides_considered': False,
        'summary': None,
    },
}

V23_WATCHLIST_ADDITIONS = {
    'thesis': {
        'summary': None,
        'reasoning': None,
        'key_catalyst': None,
        'catalyst_timing': None,
        'why_not_now': None,
    },
    'conviction': {
        'level': None,
        'score': None,
        'rationale': None,
        'conditions_to_increase': [],
        'conditions_to_decrease': [],
    },
    'analysis_quality_check': {
        'do_nothing_gate_result': None,
        'bear_case_considered': None,
        'bias_check_completed': None,
        'rr_ratio': None,
        'ev_estimate': None,
    },
}

V23_TRADE_JOURNAL_ADDITIONS = {
    'pre_trade_checklist': {
        'analysis_completed': False,
        'analysis_file': None,
        'do_nothing_gate_result': None,
        'biases_flagged': None,
        'position_size_calculated': False,
        'stop_loss_defined': False,
        'targets_defined': False,
        'risk_acceptable': False,
        'checklist_complete': False,
    },
    'psychological_state': {
        'entry': {
            'overall_state': None,
            'confidence': None,
            'anxiety': None,
            'fomo': None,
            'clarity': None,
            'physical_state': None,
            'market_state': None,
            'notes': None,
        },
        'exit': {
            'overall_state': None,
            'followed_plan': None,
            'emotional_exit': None,
            'notes': None,
        },
    },
    'decision_quality': {
        'entry': {
            'process_followed': None,
            'was_rushed': None,
            'thesis_clear': None,
            'alternatives_considered': None,
            'grade': None,
            'what_would_make_A': None,
        },
        'exit': {
            'process_followed': None,
            'loss_aversion_check_passed': None,
            'emotional_decision': None,
            'grade': None,
        },
        'overall_grade': None,
        'overall_reasoning': None,
    },
    'loss_aversion_check': {
        'thesis_intact': None,
        'catalyst_pending': None,
        'exit_reason': None,
        'ev_recalculated': None,
        'gate_result': None,
        'reminder': None,
    },
    'during_trade': {
        'real_time_notes': [],
    },
}

V23_POST_TRADE_REVIEW_ADDITIONS = {
    'data_source_effectiveness': [],
    'data_source_effectiveness_summary': None,
    'countermeasures_needed': [],
    'bias_cost_total': None,
    'rule_validation': {
        'rule': None,
        'status': None,
        'validation_criteria': None,
        'occurrences_tested': None,
        'results': None,
    },
    'comparison_to_similar_trades': [],
    'comparison_to_similar_trades_summary': None,
    'creates_learning': {
        'creates_file': False,
        'learning_type': None,
        'learning_file': None,
        'learning_id': None,
    },
    'knowledge_base_updates': {
        'ticker_profile_updated': False,
        'analysis_track_record_updated': False,
        'learning_file_created': False,
        'similar_reviews_linked': False,
    },
}

V23_TICKER_PROFILE_ADDITIONS = {
    'analysis_track_record': {
        'total_analyses': 0,
        'earnings_analyses': 0,
        'stock_analyses': 0,
        'prediction_accuracy': {
            'direction': {'correct': 0, 'total': 0, 'accuracy_pct': None},
            'magnitude': {'correct': 0, 'total': 0, 'accuracy_pct': None},
            'catalyst': {'correct': 0, 'total': 0, 'accuracy_pct': None},
        },
        'earnings_predictions': {
            'beat_predicted_correct': None,
            'miss_predicted_correct': None,
            'overall_accuracy_pct': None,
        },
        'recommendation_performance': [],
        'recent_analyses': [],
        'track_record_summary': None,
    },
    'bias_history': {
        'total_bias_cost': None,
        'common_biases': [],
        'most_costly_bias': None,
        'most_frequent_bias': None,
        'bias_summary': None,
    },
    'known_risks': {
        'structural': [],
        'cyclical': [],
        'execution': [],
        'risk_summary': None,
        'abandon_thesis_if': None,
    },
    'learned_patterns': [],
}


def detect_document_type(data: dict) -> str | None:
    """Detect document type from structure or _meta."""
    # Normalize type names
    type_aliases = {
        'research': 'research-analysis',
        'stock': 'stock-analysis',
        'earnings': 'earnings-analysis',
        'trade': 'trade-journal',
        'review': 'post-trade-review',
        'profile': 'ticker-profile',
    }

    # Check _meta for explicit type declaration
    if '_meta' in data:
        meta = data['_meta']
        declared_type = meta.get('document_type') or meta.get('type')
        if declared_type:
            return type_aliases.get(declared_type, declared_type)

    # Heuristic detection based on structure
    # Earnings analysis
    if 'phase1_preparation' in data or 'earnings_date' in data:
        return 'earnings-analysis'

    # Stock analysis - multiple patterns
    if 'phase1_catalyst' in data or 'phase2_market_environment' in data:
        return 'stock-analysis'
    if 'catalyst' in data and ('technical' in data or 'market_environment' in data):
        return 'stock-analysis'
    if 'catalyst_type' in data:
        return 'stock-analysis'

    # Research analysis
    if 'research_question' in data or 'supporting_arguments' in data:
        return 'research-analysis'
    if 'thesis' in data and 'sources' in data and 'implications' in data:
        return 'research-analysis'

    # Watchlist
    if 'entry_trigger' in data and 'invalidation' in data:
        return 'watchlist'

    # Trade journal
    if 'execution' in data and ('entry' in data.get('execution', {}) or 'entry_date' in data.get('execution', {})):
        return 'trade-journal'

    # Post-trade review
    if 'thesis_accuracy' in data or 'execution_analysis' in data:
        return 'post-trade-review'

    # Ticker profile
    if 'earnings_history' in data or 'earnings_patterns' in data:
        return 'ticker-profile'
    if 'company' in data and 'your_edge' in data:
        return 'ticker-profile'

    return None


def get_current_version(data: dict) -> str:
    """Get current document version."""
    if '_meta' in data and 'version' in data['_meta']:
        return data['_meta']['version']
    return '1.0'


def deep_merge(base: dict, additions: dict) -> dict:
    """Deep merge additions into base, preserving existing values."""
    result = base.copy()
    for key, value in additions.items():
        if key not in result:
            result[key] = value
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        # If key exists and is not dict, keep existing value
    return result


def migrate_document(data: dict, doc_type: str) -> tuple[dict, list[str]]:
    """
    Migrate document to v2.3, returning updated data and list of changes.
    """
    changes = []

    # Get additions for document type
    additions_map = {
        'stock-analysis': V23_STOCK_ANALYSIS_ADDITIONS,
        'earnings-analysis': V23_EARNINGS_ANALYSIS_ADDITIONS,
        'research-analysis': V23_RESEARCH_ANALYSIS_ADDITIONS,
        'watchlist': V23_WATCHLIST_ADDITIONS,
        'trade-journal': V23_TRADE_JOURNAL_ADDITIONS,
        'post-trade-review': V23_POST_TRADE_REVIEW_ADDITIONS,
        'ticker-profile': V23_TICKER_PROFILE_ADDITIONS,
    }

    additions = additions_map.get(doc_type)
    if not additions:
        return data, ['Unknown document type, no migration available']

    # Track what we're adding
    for key in additions:
        if key not in data:
            changes.append(f'Added section: {key}')

    # Deep merge to add missing fields
    result = deep_merge(data, additions)

    # Update version in _meta
    if '_meta' not in result:
        result['_meta'] = {}
        changes.append('Added _meta section')

    old_version = result['_meta'].get('version', '1.0')
    result['_meta']['version'] = '2.3'
    result['_meta']['migrated_at'] = datetime.now().isoformat()
    result['_meta']['migrated_from'] = old_version

    if old_version != '2.3':
        changes.append(f'Updated version: {old_version} -> 2.3')

    # Add _indexing if not present
    if '_indexing' not in result:
        result['_indexing'] = {
            'rag_embed_fields': [],
            'graph_extract_fields': [],
        }
        changes.append('Added _indexing hints')

    return result, changes


def process_file(file_path: Path, dry_run: bool = True) -> tuple[bool, list[str]]:
    """
    Process a single YAML file for migration.
    Returns (success, changes_list).
    """
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            return False, ['Not a valid YAML document (not a dict)']

        doc_type = detect_document_type(data)
        if not doc_type:
            return False, ['Could not detect document type']

        current_version = get_current_version(data)
        if current_version == '2.3':
            return True, ['Already at v2.3, skipping']

        migrated, changes = migrate_document(data, doc_type)

        if not changes:
            return True, ['No changes needed']

        if not dry_run:
            with open(file_path, 'w') as f:
                yaml.dump(migrated, f, Dumper=PreservingDumper,
                         default_flow_style=False, allow_unicode=True,
                         sort_keys=False, width=120)

        return True, changes

    except yaml.YAMLError as e:
        return False, [f'YAML parse error: {e}']
    except Exception as e:
        return False, [f'Error: {e}']


def find_documents(base_path: Path) -> list[Path]:
    """Find all YAML documents in knowledge directories."""
    patterns = [
        'knowledge/analysis/**/*.yaml',
        'knowledge/trades/**/*.yaml',
        'knowledge/reviews/**/*.yaml',
        'knowledge/watchlist/**/*.yaml',
    ]

    files = []
    for pattern in patterns:
        files.extend(base_path.glob(pattern))

    # Exclude templates
    return [f for f in files if 'template' not in f.name.lower()]


def main():
    parser = argparse.ArgumentParser(
        description='Migrate trading skill documents from v1/v2.1 to v2.3'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Preview changes without modifying files'
    )
    parser.add_argument(
        '--path', '-p',
        type=Path,
        default=Path('/opt/data/tradegent_swarm/tradegent_knowledge'),
        help='Base path to tradegent_knowledge directory'
    )
    parser.add_argument(
        '--file', '-f',
        type=Path,
        help='Process single file instead of all documents'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    if args.dry_run:
        print('=== DRY RUN MODE (no files will be modified) ===\n')

    if args.file:
        files = [args.file]
    else:
        files = find_documents(args.path)

    if not files:
        print('No documents found to migrate.')
        return 0

    print(f'Found {len(files)} documents to process.\n')

    stats = {'success': 0, 'skipped': 0, 'failed': 0, 'migrated': 0}

    for file_path in sorted(files):
        rel_path = file_path.relative_to(args.path) if args.path in file_path.parents else file_path

        success, changes = process_file(file_path, dry_run=args.dry_run)

        if not success:
            stats['failed'] += 1
            print(f'FAILED: {rel_path}')
            for change in changes:
                print(f'  - {change}')
        elif 'skipping' in changes[0].lower() or 'No changes' in changes[0]:
            stats['skipped'] += 1
            if args.verbose:
                print(f'SKIP: {rel_path} ({changes[0]})')
        else:
            stats['success'] += 1
            stats['migrated'] += 1
            action = 'WOULD MIGRATE' if args.dry_run else 'MIGRATED'
            print(f'{action}: {rel_path}')
            if args.verbose:
                for change in changes:
                    print(f'  + {change}')

    print(f'\n=== Summary ===')
    print(f'Total files:  {len(files)}')
    print(f'Migrated:     {stats["migrated"]}')
    print(f'Skipped:      {stats["skipped"]}')
    print(f'Failed:       {stats["failed"]}')

    if args.dry_run and stats['migrated'] > 0:
        print(f'\nRun without --dry-run to apply changes.')

    return 0 if stats['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
