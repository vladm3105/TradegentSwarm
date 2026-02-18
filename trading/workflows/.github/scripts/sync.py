#!/usr/bin/env python3
"""
Sync trading knowledge documents to LightRAG.
Used by GitHub Actions after validation passes.
"""

import os
import sys
import yaml
import httpx
import asyncio
from pathlib import Path
from typing import Optional

LIGHTRAG_API_URL = os.environ.get('LIGHTRAG_API_URL', 'http://localhost:8000')
LIGHTRAG_API_KEY = os.environ.get('LIGHTRAG_API_KEY', '')

# Space mapping based on document path
SPACE_MAP = {
    'earnings': 'earnings',
    'analysis': 'analysis',
    'trades': 'trades',
    'strategies': 'strategies',
    'tickers': 'tickers',
    'learnings': 'learnings',
    'research': 'research',
}

def get_space_for_path(file_path: str) -> Optional[str]:
    """Determine LightRAG space based on file path."""
    path = Path(file_path)
    parts = path.parts
    
    if len(parts) < 2:
        return None
    
    return SPACE_MAP.get(parts[0])

def load_document(file_path: str) -> dict:
    """Load YAML document."""
    with open(file_path) as f:
        return yaml.safe_load(f)

async def sync_document(
    client: httpx.AsyncClient,
    file_path: str,
    doc: dict,
    space: str
) -> tuple[bool, str]:
    """
    Sync a single document to LightRAG.
    Returns (success, message).
    """
    doc_id = doc.get('_meta', {}).get('id')
    if not doc_id:
        return False, f"Missing _meta.id in {file_path}"
    
    # Prepare payload
    payload = {
        'id': doc_id,
        'space': space,
        'content': yaml.dump(doc, default_flow_style=False),
        'metadata': {
            'github_path': file_path,
            'type': doc.get('_meta', {}).get('type'),
            'version': doc.get('_meta', {}).get('version'),
        },
        'entity_hints': doc.get('_graph', {}).get('entities', []),
        'relation_hints': doc.get('_graph', {}).get('relations', []),
    }
    
    headers = {}
    if LIGHTRAG_API_KEY:
        headers['Authorization'] = f'Bearer {LIGHTRAG_API_KEY}'
    
    try:
        # Check if document exists
        response = await client.get(
            f"{LIGHTRAG_API_URL}/api/documents/{doc_id}",
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code == 200:
            # Update existing document
            response = await client.put(
                f"{LIGHTRAG_API_URL}/api/documents/{doc_id}",
                json=payload,
                headers=headers,
                timeout=60.0
            )
            action = "Updated"
        else:
            # Create new document
            response = await client.post(
                f"{LIGHTRAG_API_URL}/api/documents",
                json=payload,
                headers=headers,
                timeout=60.0
            )
            action = "Created"
        
        if response.status_code in (200, 201):
            return True, f"✓ {action}: {file_path} → {space}/{doc_id}"
        else:
            return False, f"✗ API error for {file_path}: {response.status_code} - {response.text}"
            
    except httpx.TimeoutException:
        return False, f"✗ Timeout syncing {file_path}"
    except httpx.RequestError as e:
        return False, f"✗ Request error for {file_path}: {e}"

async def main():
    """Sync all provided files to LightRAG."""
    if len(sys.argv) < 2:
        print("Usage: sync.py <file1> [file2] ...")
        sys.exit(0)
    
    files = sys.argv[1:]
    
    # Filter to valid YAML files with spaces
    to_sync = []
    for file_path in files:
        file_path = file_path.strip()
        if not file_path:
            continue
        
        path = Path(file_path)
        if path.suffix not in ('.yaml', '.yml'):
            print(f"Skipped (not YAML): {file_path}")
            continue
        
        space = get_space_for_path(file_path)
        if not space:
            print(f"Skipped (no space mapping): {file_path}")
            continue
        
        if not path.exists():
            print(f"Skipped (file not found): {file_path}")
            continue
        
        try:
            doc = load_document(file_path)
            to_sync.append((file_path, doc, space))
        except Exception as e:
            print(f"✗ Error loading {file_path}: {e}")
    
    if not to_sync:
        print("No documents to sync")
        sys.exit(0)
    
    # Sync documents
    results = []
    async with httpx.AsyncClient() as client:
        for file_path, doc, space in to_sync:
            success, message = await sync_document(client, file_path, doc, space)
            results.append((success, message))
            print(message)
    
    # Summary
    total = len(results)
    passed = sum(1 for success, _ in results if success)
    failed = total - passed
    
    print(f"\n{'='*50}")
    print(f"Sync complete: {passed}/{total} synced")
    
    if failed > 0:
        print(f"⚠️  {failed} document(s) failed to sync")
        # Don't fail the workflow for sync errors - documents are still in Git
        sys.exit(0)
    else:
        print("✅ All documents synced to LightRAG")
        sys.exit(0)

if __name__ == '__main__':
    asyncio.run(main())
