#!/usr/bin/env python3
"""Annotate harvested leaderboard-data/week_*.json files with known player
names, using a uuid -> name directory built by extract_name_directory.py.

Group entries (entityId is several UUIDs joined by "_", one per party
member) get a "names" list aligned to the UUID order, with null for any
UUID not yet in the directory. Solo entries get a "name" field the same
way. entityId is left untouched so nothing is lost for UUIDs we can't
resolve yet.

Usage:
    python3 apply_name_directory.py --directory name_directory.json --leaderboard-dir ./leaderboard-data
"""

import argparse
import glob
import json


def annotate_entry(entry, directory):
    eid = entry.get("entityId")
    if not eid:
        return
    parts = eid.split("_")
    names = [directory.get(p) for p in parts]
    if len(parts) == 1:
        entry["name"] = names[0]
    else:
        entry["names"] = names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", default="name_directory.json")
    parser.add_argument("--leaderboard-dir", default="./leaderboard-data")
    args = parser.parse_args()

    with open(args.directory, encoding="utf-8") as f:
        directory = json.load(f)

    total_resolved = 0
    total_entries = 0
    for path in glob.glob(f"{args.leaderboard_dir}/week_*.json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for key, lb in data.items():
            for entry in (lb.get("leaderboardEntries") or []):
                total_entries += 1
                annotate_entry(entry, directory)
                resolved = entry.get("name") or [n for n in (entry.get("names") or []) if n]
                if resolved:
                    total_resolved += 1

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    print(f"annotated {total_entries} entries, {total_resolved} had at least one resolved name")


if __name__ == "__main__":
    main()
