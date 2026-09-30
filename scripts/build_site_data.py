#!/usr/bin/env python3
"""Flatten leaderboard-data/*.json into one consolidated dataset for the
static site (docs/data.json). Run this after any pipeline update
(apply_name_directory.py, mark_done.py, etc.) to refresh the site.

Usage:
    python3 build_site_data.py
"""
import datetime
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LEADERBOARD_DIR = ROOT / "leaderboard-data"
OUT_PATH = ROOT / "docs" / "data.json"

WEEK_RE = re.compile(r"week_(\d+)\.json$")

DUNGEON_NAMES = {
    "DungeonCutlassKeys00": "Barnacles and Blackpowder",
    "DungeonBrimstoneSands00": "The Ennead",
    "DungeonEbonscale00": "Dynasty Shipyard",
    "DungeonEdengrove00": "Garden of Genesis",
    "DungeonFirstLight01": "Savage Divide",
    "DungeonReekwater00": "Lazarus Instrumentality",
    "DungeonRestlessShores01": "The Depths",
    "DungeonShatterMtn00": "Tempest Heart",
    "DungeonGreatCleave00": "Glacial Tarn",
    "DungeonGreatCleave01": "Empyrean Forge",
    "DungeonShatteredObelisk": "Starstone Barrows",
}

# Leaderboard weeks start on Tuesdays. Weeks 1-9 run from 2023-01-10; the
# leaderboard then paused for four weeks (mid-March to early April 2023), and
# from week 10 (2023-04-11) numbering is contiguous up to today. Checked
# against mutation posts: each week's mutated dungeons match its scores.
EARLY_WEEK1 = datetime.date(2023, 1, 10)
ANCHOR_WEEK, ANCHOR_DATE = 190, datetime.date(2026, 9, 22)

# Season start = day after the newworld.com/game/releases post. Season 1
# isn't on that page; it's assumed to start with week 10, right after the
# leaderboard pause that coincides with its launch window.
SEASONS = [
    (1, "Season 1", datetime.date(2023, 4, 11)),
    (2, "Blood of the Sands", datetime.date(2023, 7, 6)),
    (3, "Rise of the Angry Earth", datetime.date(2023, 10, 3)),
    (4, "Eternal Frost", datetime.date(2023, 12, 12)),
    (5, "Season of the Guardian", datetime.date(2024, 3, 30)),
    (6, "Season of Opportunity", datetime.date(2024, 10, 15)),
    (7, "Season of Conquerors", datetime.date(2025, 1, 21)),
    (8, "Season of the Divide", datetime.date(2025, 5, 13)),
    (9, "Season of the Banner", datetime.date(2025, 7, 29)),
    (10, "Nighthaven", datetime.date(2025, 10, 12)),
]
SEASON_ICON_DIR = ROOT / "docs" / "assets" / "seasons"


def week_start(week):
    if week <= 9:
        return EARLY_WEEK1 + datetime.timedelta(weeks=week - 1)
    return ANCHOR_DATE + datetime.timedelta(weeks=week - ANCHOR_WEEK)


def season_for_week(week):
    # A season that launches mid-week claims the week if it's live for most
    # of it, i.e. by the week's midpoint.
    midpoint = datetime.datetime.combine(week_start(week), datetime.time()) + datetime.timedelta(days=3.5)
    current = None
    for number, _, start in SEASONS:
        if datetime.datetime.combine(start, datetime.time()) <= midpoint:
            current = number
    return current


def main():
    rows = []
    for path in sorted(LEADERBOARD_DIR.glob("week_*.json")):
        m = WEEK_RE.search(path.name)
        week = int(m.group(1)) if m else None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for key, lb in data.items():
            metric_raw, dungeon_id = key.rsplit(".", 1)
            metric = "score" if metric_raw == "top-group-expedition-score" else "time"
            dungeon = DUNGEON_NAMES.get(dungeon_id, dungeon_id)

            for entry in (lb.get("leaderboardEntries") or []):
                names = entry.get("names")
                if names is None:
                    names = [entry.get("name")]
                rows.append({
                    "week": week,
                    "dungeon": dungeon,
                    "metric": metric,
                    "rank": entry.get("rank"),
                    "value": entry.get("value"),
                    "players": names,
                })

    dungeons = sorted(set(r["dungeon"] for r in rows))
    weeks = sorted(set(r["week"] for r in rows if r["week"] is not None))

    week_info = {
        w: {"start": week_start(w).isoformat(), "season": season_for_week(w)} for w in weeks
    }
    seasons = {
        n: {
            "name": name,
            "start": start.isoformat(),
            "icon": f"assets/seasons/s{n}.webp" if (SEASON_ICON_DIR / f"s{n}.webp").exists() else None,
        }
        for n, name, start in SEASONS
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "dungeons": dungeons, "weeks": weeks,
                   "weekInfo": week_info, "seasons": seasons}, f)

    print(f"wrote {len(rows)} rows, {len(dungeons)} dungeons, {len(weeks)} weeks -> {OUT_PATH}")


if __name__ == "__main__":
    main()
