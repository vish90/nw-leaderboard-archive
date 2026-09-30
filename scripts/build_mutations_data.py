#!/usr/bin/env python3
"""Flatten mutations-data/week_*.json into docs/mutations.json for the
static site, adding inferred "carryover" entries.

Mid-week patches sometimes restarted servers and moved the rotation off its
Tuesday slot, so the previous rotation hung on into the new week: a dungeon
has scores in week N but no entry for N, while it was mutated in week N-1.
Those runs were done under N-1's mutation, so its entry is carried forward
(tagged source "carryover"). This is derived here rather than stored, so
mutations-data/ only ever holds sourced data.

Usage:
    python3 build_mutations_data.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MUTATIONS_DIR = ROOT / "mutations-data"
LEADERBOARD_DIR = ROOT / "leaderboard-data"
OUT_PATH = ROOT / "docs" / "mutations.json"

WEEK_RE = re.compile(r"week_(\d+)\.json$")

sys.path.insert(0, str(HERE))
from build_site_data import DUNGEON_NAMES  # noqa: E402


def load_weeks(directory):
    weeks = {}
    for path in directory.glob("week_*.json"):
        m = WEEK_RE.search(path.name)
        if m:
            with open(path, encoding="utf-8") as f:
                weeks[int(m.group(1))] = json.load(f)
    return weeks


def scored_dungeons(leaderboard_week):
    return {
        DUNGEON_NAMES.get(key.rsplit(".", 1)[1], key.rsplit(".", 1)[1])
        for key, lb in leaderboard_week.items()
        if lb.get("leaderboardEntries")
    }


def main():
    weeks = load_weeks(MUTATIONS_DIR)
    leaderboards = load_weeks(LEADERBOARD_DIR)

    carried = 0
    for week_num in sorted(leaderboards):
        prev = weeks.get(week_num - 1)
        if not prev:
            continue
        current = weeks.setdefault(week_num, {"week": week_num, "expeditions": []})
        have = {e["dungeon"] for e in current["expeditions"]}
        for entry in prev["expeditions"]:
            if entry["source"] == "carryover":
                continue
            if entry["dungeon"] in scored_dungeons(leaderboards[week_num]) - have:
                current["expeditions"].append({**entry, "source": "carryover"})
                carried += 1
        if not current["expeditions"]:
            del weeks[week_num]

    latest_week = max(weeks, default=None)
    out = {"weeks": {str(w): weeks[w] for w in sorted(weeks)}, "latestWeek": latest_week}
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"wrote {len(weeks)} week(s) ({carried} carryover entries), latestWeek={latest_week} -> {OUT_PATH}")


if __name__ == "__main__":
    main()
