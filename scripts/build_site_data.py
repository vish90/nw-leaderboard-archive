#!/usr/bin/env python3
"""Flatten leaderboard-data/*.json into one consolidated dataset for the
static site (site/data.json). Run this after any pipeline update
(apply_name_directory.py, mark_done.py, etc.) to refresh the site.

Usage:
    python3 build_site_data.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LEADERBOARD_DIR = ROOT / "leaderboard-data"
OUT_PATH = ROOT / "site" / "data.json"

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

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"rows": rows, "dungeons": dungeons, "weeks": weeks}, f)

    print(f"wrote {len(rows)} rows, {len(dungeons)} dungeons, {len(weeks)} weeks -> {OUT_PATH}")


if __name__ == "__main__":
    main()
