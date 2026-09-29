#!/usr/bin/env python3
"""Flatten mutations-data/week_*.json into docs/mutations.json for the
static site. Run after parse_mutations.py.

Usage:
    python3 build_mutations_data.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MUTATIONS_DIR = ROOT / "mutations-data"
OUT_PATH = ROOT / "docs" / "mutations.json"

WEEK_RE = re.compile(r"week_(\d+)\.json$")


def main():
    weeks = {}
    for path in sorted(MUTATIONS_DIR.glob("week_*.json")):
        m = WEEK_RE.search(path.name)
        if not m:
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        weeks[m.group(1)] = data

    latest_week = max((d["week"] for d in weeks.values()), default=None)

    out = {"weeks": weeks, "latestWeek": latest_week}
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"wrote {len(weeks)} week(s), latestWeek={latest_week} -> {OUT_PATH}")


if __name__ == "__main__":
    main()
