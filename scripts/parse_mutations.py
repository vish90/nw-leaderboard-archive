#!/usr/bin/env python3
"""Parse a raw copy-paste of a "New World Mutations" bot post into per-dungeon
entries in mutations-data/week_N.json. Also holds the shared helpers
(canonical names, per-dungeon entry format, source-priority merge) used by
the capture and Discord importers.

The bot's post pads each section header (dungeon name, "Mutation: X",
"Promotion: Y", "Curse: Z") with trailing U+2800 (braille blank) characters
for Discord alignment -- that padding is what marks a line as a header, so
this only needs to scan for lines ending in it.

Usage:
    python3 parse_mutations.py --week 191 --raw-file /tmp/mutation_paste.txt
    pbpaste | python3 parse_mutations.py --week 191
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MUTATIONS_DIR = ROOT / "mutations-data"

sys.path.insert(0, str(HERE))
from build_site_data import DUNGEON_NAMES  # noqa: E402


def _dungeon_key(name):
    name = name.lower()
    name = re.sub(r"^the\s+", "", name)
    name = re.sub(r"['’]s\b", "", name)
    return re.sub(r"['’\s]", "", name)


_CANONICAL_DUNGEONS = {_dungeon_key(n): n for n in DUNGEON_NAMES.values()}


def canonical_dungeon(name):
    # The bot's names drift from the site's ("Tempest's Heart", "The Dynasty
    # Shipyard", "Black Powder"); map them onto build_site_data's names.
    return _CANONICAL_DUNGEONS.get(_dungeon_key(name), name)


def strip_tier(name):
    # Mutation tier 3 curses are always tier II, so the suffix carries no info.
    return re.sub(r"\s+(I|II|III|IV)$", "", name) if name else name

PAD_CHAR = "⠀"

# New World only has four Mutation archetypes, each with a fixed in-game name;
# "fire"/"ice"/"void"/"nature" are just the casual names for what they are.
# This is the primary way to resolve an element -- exact and doesn't depend on
# perk wording holding steady.
MUTATION_NAME_ELEMENT = {
    "hellfire": "fire",
    "icebound": "ice",
    "eternal": "void",
    "overgrown": "nature",
}

# Fallback for a Mutation name not in the table above: the perk text always
# calls out its damage type in plain language (e.g. "...dealing 70% base Fire
# damage..."), so the element can be inferred from that body text without
# storing the full perk descriptions. Checked in order; first match wins.
ELEMENT_KEYWORDS = [
    ("fire", ("fire",)),
    ("ice", ("ice", "frost", "frozen")),
    ("void", ("void", "corrupt")),
    ("nature", ("nature", "poison", "blight")),
]


def infer_element(mutation_name, body_text):
    if mutation_name:
        known = MUTATION_NAME_ELEMENT.get(mutation_name.strip().lower())
        if known:
            return known

    lowered = body_text.lower()
    for element, keywords in ELEMENT_KEYWORDS:
        if any(k in lowered for k in keywords):
            return element
    return None


def parse(text):
    dungeons = []
    mutation = promotion = curse = None
    mutation_body = []
    state = None  # only 'mutation' body text is collected, for element inference

    for raw_line in text.splitlines():
        stripped = raw_line.rstrip()
        if stripped.endswith(PAD_CHAR):
            label = stripped.rstrip(PAD_CHAR).strip()
            if not label:
                continue
            state = None
            if label.startswith("Mutation:"):
                mutation = label.split(":", 1)[1].strip()
                state = "mutation"
            elif label.startswith("Promotion:"):
                promotion = label.split(":", 1)[1].strip()
            elif label.startswith("Curse:"):
                curse = label.split(":", 1)[1].strip()
            else:
                dungeons.append(label)
        elif state == "mutation":
            mutation_body.append(stripped)

    element = infer_element(mutation, " ".join(mutation_body))
    return [
        make_expedition(d, mutation, promotion, curse, "paste", element=element)
        for d in dungeons
    ]


# Several sources can describe the same week; when they disagree about a
# dungeon, the more authoritative one wins. Game captures are the server's
# own data; the Discord bot is a human re-typing it; a paste is a copy of that.
SOURCE_PRIORITY = {"paste": 0, "discord": 1, "capture": 2}


def make_expedition(dungeon, mutation, promotion, curse, source, element=None):
    return {
        "dungeon": canonical_dungeon(dungeon),
        "mutation": mutation,
        "promotion": strip_tier(promotion),
        "curse": strip_tier(curse),
        "element": element or infer_element(mutation, ""),
        "source": source,
    }


def merge_week(week, expeditions):
    """Merge per-dungeon entries into mutations-data/week_N.json.

    Returns (result, conflicts) where conflicts lists dungeons whose combo
    differed between sources."""
    out_path = MUTATIONS_DIR / f"week_{week}.json"
    by_dungeon = {}
    if out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            for e in json.load(f).get("expeditions", []):
                by_dungeon[e["dungeon"]] = e

    def combo(x):
        return (x["mutation"], x["promotion"], x["curse"])

    conflicts = []
    for e in expeditions:
        prev = by_dungeon.get(e["dungeon"])
        if prev:
            if combo(prev) != combo(e):
                conflicts.append((e["dungeon"], prev, e))
            if SOURCE_PRIORITY[prev["source"]] > SOURCE_PRIORITY[e["source"]]:
                continue
        by_dungeon[e["dungeon"]] = e

    result = {"week": week, "expeditions": sorted(by_dungeon.values(), key=lambda e: e["dungeon"])}
    MUTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return result, conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--raw-file", help="path to the raw pasted text (default: stdin)")
    args = parser.parse_args()

    if args.raw_file:
        text = Path(args.raw_file).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    expeditions = parse(text)
    if not expeditions or not all(e["mutation"] and e["promotion"] and e["curse"] and e["element"] for e in expeditions):
        print(
            "warning: parse looks incomplete -- check the pasted text matches the "
            "expected bot format",
            file=sys.stderr,
        )

    result, conflicts = merge_week(args.week, expeditions)
    for dungeon, prev, new in conflicts:
        print(f"  ! {dungeon}: existing {prev['source']} entry differs from paste", file=sys.stderr)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
