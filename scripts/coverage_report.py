#!/usr/bin/env python3
"""Rank which leaderboard pages (week + dungeon + category) to browse next
-- with a DTLS capture running -- for the biggest marginal gain in name
coverage across the whole harvested archive.

Uses a greedy set-cover: repeatedly pick the page whose still-unresolved
UUIDs account for the most total unresolved row-appearances across the
*entire* archive (not just that page), since resolving a UUID on one page
fills in every other page it also appears on.

Usage:
    python3 coverage_report.py --leaderboard-dir ./leaderboard-data --top-pages 20
"""

import argparse
import glob
import json
import re
from collections import defaultdict

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


def friendly_page(page):
    week, key = page.split(":", 1)
    metric, dungeon_id = key.rsplit(".", 1)
    dungeon = DUNGEON_NAMES.get(dungeon_id, dungeon_id)
    metric_label = "score" if metric == "top-group-expedition-score" else "clear-time"
    return f"{week} / {dungeon} / {metric_label}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leaderboard-dir", default="./leaderboard-data")
    parser.add_argument("--top-pages", type=int, default=20)
    parser.add_argument("--top-uuids", type=int, default=10,
                         help="also show this many raw highest-appearance unresolved uuids")
    parser.add_argument("--visited-file", default="visited_pages.txt",
                         help="pages listed here (one raw page key per line) are excluded from "
                              "the ranked suggestions even if they still have unresolved slots "
                              "(e.g. deleted accounts that will never resolve)")
    args = parser.parse_args()

    visited = set()
    try:
        with open(args.visited_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    visited.add(line)
    except FileNotFoundError:
        pass

    uuid_total_count = defaultdict(int)
    page_uuids = defaultdict(lambda: defaultdict(int))
    total_uuids = set()
    resolved_uuids = set()

    for path in glob.glob(f"{args.leaderboard_dir}/week_*.json"):
        m = WEEK_RE.search(path)
        week = m.group(1) if m else "?"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for key, lb in data.items():
            page = f"week_{week}:{key}"
            for entry in (lb.get("leaderboardEntries") or []):
                eid = entry.get("entityId")
                if not eid:
                    continue
                names = entry.get("names")
                if names is None:
                    names = [entry.get("name")]
                parts = eid.split("_")
                for part, name in zip(parts, names):
                    total_uuids.add(part)
                    if name:
                        resolved_uuids.add(part)
                    else:
                        uuid_total_count[part] += 1
                        page_uuids[page][part] += 1

    print(f"total distinct uuids: {len(total_uuids)}")
    print(f"resolved: {len(resolved_uuids)} ({100*len(resolved_uuids)/max(1,len(total_uuids)):.1f}%)")
    print(f"unresolved: {len(total_uuids) - len(resolved_uuids)}")
    print()

    print(f"top {args.top_uuids} unresolved uuids by raw appearance count:")
    for uid, count in sorted(uuid_total_count.items(), key=lambda kv: -kv[1])[:args.top_uuids]:
        print(f"  {uid}  appears {count}x")
    print()

    if visited:
        print(f"({len(visited)} pages excluded as already-visited, from {args.visited_file})")
        print()

    # Greedy set-cover over pages.
    remaining_pages = {p: u for p, u in page_uuids.items() if p not in visited}
    already_resolved = set()
    total_unresolved_rows = sum(uuid_total_count.values())
    cumulative = 0

    print(f"top {args.top_pages} pages to browse next, ranked by marginal coverage gain:")
    for rank in range(1, args.top_pages + 1):
        best_page, best_gain, best_new_uuids = None, -1, None
        for page, uuids in remaining_pages.items():
            new_uuids = [u for u in uuids if u not in already_resolved]
            gain = sum(uuid_total_count[u] for u in new_uuids)
            if gain > best_gain:
                best_page, best_gain, best_new_uuids = page, gain, new_uuids

        if best_page is None or best_gain <= 0:
            break

        already_resolved.update(best_new_uuids)
        cumulative += best_gain
        del remaining_pages[best_page]

        pct = 100 * cumulative / max(1, total_unresolved_rows)
        print(f"  {rank:2d}. {friendly_page(best_page):55s} +{best_gain:5d} rows "
              f"({len(best_new_uuids)} new uuids)  cumulative {pct:.1f}% of remaining")
        print(f"      key: {best_page}")


if __name__ == "__main__":
    main()
