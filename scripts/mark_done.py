#!/usr/bin/env python3
"""Mark a leaderboard page as done so coverage_report.py stops suggesting it,
even if it still has unresolved slots (e.g. deleted accounts that will never
resolve). Copy the "key:" line printed under each ranked page in
coverage_report.py's output and pass it here.

Usage:
    python3 mark_done.py "week_50:top-group-expedition-score.DungeonReekwater00"
"""
import sys
from pathlib import Path

VISITED_FILE = Path(__file__).resolve().parent / "visited_pages.txt"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    page_key = sys.argv[1].strip()
    existing = set()
    if VISITED_FILE.exists():
        existing = {l.strip() for l in VISITED_FILE.read_text(encoding="utf-8").splitlines() if l.strip()}

    if page_key in existing:
        print(f"already marked done: {page_key}")
        return

    with VISITED_FILE.open("a", encoding="utf-8") as f:
        f.write(page_key + "\n")
    print(f"marked done: {page_key}")


if __name__ == "__main__":
    main()
