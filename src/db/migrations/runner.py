"""Run SQL migration files against the database."""

import os
import glob
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent


def run_migrations():
    """Execute all .sql migration files in order."""
    uri = os.environ.get("DATABASE_URI")
    if not uri:
        raise RuntimeError("DATABASE_URI not set")

    sql_files = sorted(glob.glob(str(MIGRATIONS_DIR / "*.sql")))
    if not sql_files:
        print("No migration files found.")
        return

    with psycopg.connect(uri, autocommit=True) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                filename VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        for sql_file in sql_files:
            filename = os.path.basename(sql_file)
            cursor = conn.execute(
                "SELECT 1 FROM _migrations WHERE filename = %s", (filename,)
            )
            if cursor.fetchone():
                print(f"  SKIP {filename} (already applied)")
                continue

            print(f"  APPLY {filename}...")
            with open(sql_file, "r") as f:
                sql = f.read()
            conn.execute(sql)
            conn.execute(
                "INSERT INTO _migrations (filename) VALUES (%s)", (filename,)
            )
            print(f"  DONE {filename}")

    print("All migrations complete.")


if __name__ == "__main__":
    run_migrations()
