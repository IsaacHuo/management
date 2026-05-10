#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import init_database  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the SQLite database.")
    parser.add_argument("--reset", action="store_true", help="delete the existing database before initialization")
    parser.add_argument("--no-seed", action="store_true", help="create tables without demo data")
    args = parser.parse_args()

    db_path = init_database(reset=args.reset, seed=not args.no_seed)
    print(f"Database initialized: {db_path}")


if __name__ == "__main__":
    main()

