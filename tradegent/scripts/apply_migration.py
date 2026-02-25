#!/usr/bin/env python3
"""Apply database migrations with transaction safety."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def apply_migration(migration_id: str):
    """Apply a specific migration file with full transaction."""
    from db_layer import NexusDB

    migrations_dir = Path(__file__).parent.parent / "db" / "migrations"

    if not migrations_dir.exists():
        print(f"ERROR: Migrations directory not found: {migrations_dir}")
        return False

    # Find migration file
    pattern = f"{migration_id}*.sql"
    files = list(migrations_dir.glob(pattern))
    if not files:
        print(f"ERROR: No migration found matching {pattern}")
        return False

    migration_file = files[0]
    print(f"Applying: {migration_file.name}")

    sql = migration_file.read_text()

    with NexusDB() as db:
        try:
            # Execute in transaction
            with db.conn.cursor() as cur:
                cur.execute(sql)
            db.conn.commit()
            print(f"OK: Migration {migration_id} applied successfully")
            return True
        except Exception as e:
            db.conn.rollback()
            error_msg = str(e)
            if "already applied" in error_msg:
                print(f"SKIP: Migration {migration_id} already applied")
                return True
            print(f"ERROR: {e}")
            return False


def list_migrations():
    """List all available and applied migrations."""
    from db_layer import NexusDB

    migrations_dir = Path(__file__).parent.parent / "db" / "migrations"
    available = sorted(migrations_dir.glob("*.sql"))

    print("Available migrations:")
    for f in available:
        print(f"  - {f.name}")

    print("\nApplied migrations:")
    try:
        with NexusDB() as db:
            with db.conn.cursor() as cur:
                cur.execute("SELECT id, applied_at FROM nexus.migrations ORDER BY id")
                for row in cur.fetchall():
                    print(f"  - {row['id']} (applied: {row['applied_at']})")
    except Exception as e:
        print(f"  (could not query: {e})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python apply_migration.py <migration_id|list>")
        print("Example: python apply_migration.py 003")
        print("         python apply_migration.py list")
        sys.exit(1)

    if sys.argv[1] == "list":
        list_migrations()
    else:
        success = apply_migration(sys.argv[1])
        sys.exit(0 if success else 1)
