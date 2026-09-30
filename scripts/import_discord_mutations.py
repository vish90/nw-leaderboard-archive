#!/usr/bin/env python3
"""Import "New World Mutations" bot posts from a raw Discord channel pull
(fetch_discord_history.py output) into per-dungeon mutations-data/week_N.json.

The bot's post format changed over time, but always in fixed fields:
  - 2023: one embed per dungeon; the combo is in custom-emoji field names
    like <:Mutation_Hellfire_5CC:...>, <:Promotion_Oppressive:...>,
    <:Curse_Desiccated_Fire:...>, so dungeons can differ within a week.
  - 2024+: embed titles "Mutation: X", "Promotion: Y", "Curse: Z II (Elem)"
    alongside one embed per dungeon, all sharing that combo.
Posts are dated to a week by timestamp (same anchor as the capture
extractor); a later post in the same week overrides an earlier one for the
same dungeon (corrections, mid-week re-rotations).

Usage:
    python3 import_discord_mutations.py mutations-data/raw/nysa_current_mutations.json
"""
import argparse
import datetime
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_site_data import DUNGEON_NAMES  # noqa: E402
from extract_mutations_from_capture import week_for  # noqa: E402
from parse_mutations import canonical_dungeon, make_expedition, merge_week  # noqa: E402

KNOWN_DUNGEONS = set(DUNGEON_NAMES.values())
MUTATIONS = {"Hellfire", "Icebound", "Eternal", "Overgrown"}
PROMOTIONS = {"Savage", "Barbaric", "Oppressive", "Indomitable"}
CURSES = {"Frenzied", "Fiendish", "Desiccated", "Censored"}


def clean(title):
    return (title or "").replace("⠀", "").strip()


def parse_message(msg):
    dungeons, combo = [], {}
    for embed in msg.get("embeds") or []:
        title = clean(embed.get("title"))
        header = re.match(r"(Mutation|Promotion|Curse):\s*([A-Za-z]+)", title)
        if header:
            combo[header.group(1).lower()] = header.group(2)
            continue
        dungeon = canonical_dungeon(title)
        if dungeon not in KNOWN_DUNGEONS:
            continue
        dungeons.append(dungeon)
        for field in embed.get("fields") or []:
            for kind in ("Mutation", "Promotion", "Curse"):
                emoji = re.search(rf"<:{kind}_([A-Za-z]+)", field.get("name", ""))
                if emoji:
                    combo[kind.lower()] = emoji.group(1)
    if not (dungeons and combo.get("mutation") in MUTATIONS
            and combo.get("promotion") in PROMOTIONS and combo.get("curse") in CURSES):
        return []
    return [
        make_expedition(d, combo["mutation"], combo["promotion"], combo["curse"], "discord")
        for d in dungeons
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("raw_json")
    args = parser.parse_args()

    messages = json.loads(Path(args.raw_json).read_text(encoding="utf-8"))
    bot_posts = sorted((m for m in messages if m["author"].get("bot")), key=lambda m: int(m["id"]))

    by_week = defaultdict(dict)
    unparsed = 0
    for msg in bot_posts:
        expeditions = parse_message(msg)
        if not expeditions:
            unparsed += 1
            continue
        ts_ms = datetime.datetime.fromisoformat(msg["timestamp"]).timestamp() * 1000
        for e in expeditions:
            by_week[week_for(ts_ms)][e["dungeon"]] = e

    for week in sorted(by_week):
        _, conflicts = merge_week(week, list(by_week[week].values()))
        for dungeon, prev, new in conflicts:
            print(f"  ! week {week} {dungeon}: {prev['source']} says "
                  f"{prev['mutation']}/{prev['promotion']}/{prev['curse']}, discord says "
                  f"{new['mutation']}/{new['promotion']}/{new['curse']}", file=sys.stderr)

    weeks = sorted(by_week)
    print(f"{len(bot_posts)} bot posts ({unparsed} unparsed) -> {len(weeks)} weeks, "
          f"{weeks[0] if weeks else '-'}..{weeks[-1] if weeks else '-'}")


if __name__ == "__main__":
    main()
