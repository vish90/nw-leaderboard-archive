#!/usr/bin/env python3
"""Parse a raw copy-paste of the Nysa PVE "current-mutations" Discord post
into a compact summary: which dungeons are currently mutated, and the shared
Mutation/Promotion/Curse names for this week's rotation.

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
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MUTATIONS_DIR = ROOT / "mutations-data"

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

    return {
        "dungeons": dungeons,
        "mutation": mutation,
        "promotion": promotion,
        "curse": curse,
        "element": infer_element(mutation, " ".join(mutation_body)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--raw-file", help="path to the raw pasted text (default: stdin)")
    args = parser.parse_args()

    if args.raw_file:
        text = Path(args.raw_file).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    result = parse(text)
    result["week"] = args.week

    if not result["dungeons"] or not (result["mutation"] and result["promotion"] and result["curse"] and result["element"]):
        print(
            "warning: parse looks incomplete -- check the pasted text matches the "
            "expected bot format",
            file=sys.stderr,
        )

    MUTATIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MUTATIONS_DIR / f"week_{args.week}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"-> saved {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
