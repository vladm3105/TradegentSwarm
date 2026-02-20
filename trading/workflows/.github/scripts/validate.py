#!/usr/bin/env python3
"""
Validate trading knowledge documents against JSON schemas.
Used by GitHub Actions before syncing to RAG+Graph.
"""

import sys
import json
import yaml
from pathlib import Path
from jsonschema import validate, ValidationError

# Schema mapping based on document path
SCHEMA_MAP = {
    'earnings': 'earnings-analysis.json',
    'analysis': 'stock-analysis.json',
    'trades': 'trade-journal.json',
    'strategies': 'strategy.json',
    'tickers': 'ticker.json',
    'ticker-profiles': 'ticker.json',
    'learnings': 'learning.json',
    'research': 'research.json',
    'watchlist': 'watchlist.json',
    'scanners': 'scanner-config.json',
    'reviews': 'post-trade-review.json',
}

# Schema directory - try multiple locations
SCHEMA_DIRS = [
    Path('trading/schemas'),
    Path('trading/workflows/.lightrag/schemas'),
    Path('.lightrag/schemas'),
]

def load_schema(schema_name: str) -> dict:
    """Load JSON schema from trading/schemas/ or fallback locations."""
    for schema_dir in SCHEMA_DIRS:
        schema_path = schema_dir / schema_name
        if schema_path.exists():
            with open(schema_path) as f:
                return json.load(f)
    raise FileNotFoundError(f"Schema not found: {schema_name} (searched: {SCHEMA_DIRS})")

def get_schema_for_path(file_path: str) -> str | None:
    """Determine which schema to use based on file path."""
    path = Path(file_path)
    parts = path.parts
    
    # Get the top-level directory
    if len(parts) < 2:
        return None
    
    top_dir = parts[0]
    return SCHEMA_MAP.get(top_dir)

def validate_document(file_path: str) -> tuple[bool, str]:
    """
    Validate a single document.
    Returns (success, message).
    """
    path = Path(file_path)
    
    # Skip non-yaml files
    if path.suffix not in ('.yaml', '.yml'):
        return True, f"Skipped (not YAML): {file_path}"
    
    # Get schema
    schema_name = get_schema_for_path(file_path)
    if not schema_name:
        return True, f"Skipped (no schema): {file_path}"
    
    try:
        # Load document
        with open(path) as f:
            doc = yaml.safe_load(f)
        
        if doc is None:
            return False, f"Empty document: {file_path}"
        
        # Load and validate against schema
        schema = load_schema(schema_name)
        validate(instance=doc, schema=schema)
        
        return True, f"✓ Valid: {file_path}"
        
    except yaml.YAMLError as e:
        return False, f"✗ YAML error in {file_path}: {e}"
    except ValidationError as e:
        return False, f"✗ Schema validation failed for {file_path}: {e.message}"
    except Exception as e:
        return False, f"✗ Error processing {file_path}: {e}"

def main():
    """Validate all provided files."""
    if len(sys.argv) < 2:
        print("Usage: validate.py <file1> [file2] ...")
        sys.exit(0)
    
    files = sys.argv[1:]
    results = []
    
    for file_path in files:
        file_path = file_path.strip()
        if not file_path:
            continue
        success, message = validate_document(file_path)
        results.append((success, message))
        print(message)
    
    # Summary
    total = len(results)
    passed = sum(1 for success, _ in results if success)
    failed = total - passed
    
    print(f"\n{'='*50}")
    print(f"Validation complete: {passed}/{total} passed")
    
    if failed > 0:
        print(f"❌ {failed} document(s) failed validation")
        sys.exit(1)
    else:
        print("✅ All documents valid")
        sys.exit(0)

if __name__ == '__main__':
    main()
