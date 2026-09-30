#!/usr/bin/env python3
"""Extract the live mutation rotation from capture-session zips.

Right after login the game server sends the client a message listing every
currently-mutated expedition as four big-endian CRC32 hashes of lowercase
string IDs: (GameModeId, element CategoryWildcard, PromotionMutationId,
CurseMutationId) -- e.g. ("dungeonedengrove00", "voi", "indomitable",
"frenzied"). This decodes each zip's DTLS ledger, finds those tuples, works
out which week the capture was taken in, and merges the result into
mutations-data/week_N.json (same schema as parse_mutations.py).

Usage:
    python3 extract_mutations_from_capture.py capture1.zip capture2.zip
    python3 extract_mutations_from_capture.py --dir ~/Downloads/harvestedCaptures --since-days 8
"""
import argparse
import datetime
import json
import os
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_site_data import DUNGEON_NAMES  # noqa: E402
from parse_mutations import MUTATION_NAME_ELEMENT, make_expedition, merge_week  # noqa: E402

DECODER = HERE / "decode_dtls_ledger.py"

# Week 190's rotation began Tuesday 2026-09-22; resets are weekly. The exact
# reset hour isn't known precisely, but captures on either side of the last
# few resets are consistent with ~05:00 UTC.
WEEK_ANCHOR = datetime.datetime(2026, 9, 22, 5, 0, tzinfo=datetime.timezone.utc)
WEEK_ANCHOR_NUMBER = 190

ELEMENT_CATEGORY = {"fir": "fire", "ice": "ice", "voi": "void", "nat": "nature"}
ELEMENT_TO_MUTATION = {v: k.capitalize() for k, v in MUTATION_NAME_ELEMENT.items()}
PROMOTIONS = ["Savage", "Barbaric", "Oppressive", "Indomitable"]
CURSES = ["Frenzied", "Fiendish", "Desiccated", "Censored"]


def crc(s):
    return zlib.crc32(s.lower().encode()) & 0xFFFFFFFF


DUNGEON_BY_HASH = {crc(gid): name for gid, name in DUNGEON_NAMES.items()}
ELEMENT_BY_HASH = {crc(cat): element for cat, element in ELEMENT_CATEGORY.items()}
PROMOTION_BY_HASH = {crc(p): p for p in PROMOTIONS}
CURSE_BY_HASH = {crc(c): c for c in CURSES}


def week_for(ts_ms):
    ts = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc)
    return WEEK_ANCHOR_NUMBER + (ts - WEEK_ANCHOR) // datetime.timedelta(days=7)


def scan_decoded(decoded_path):
    found = []
    with open(decoded_path, encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            for msg in record.get("messages") or []:
                payload_hex = msg.get("payload_hex")
                if not payload_hex:
                    continue
                b = bytes.fromhex(payload_hex)
                for i in range(len(b) - 15):
                    d, e, p, c = struct.unpack(">IIII", b[i:i + 16])
                    if d in DUNGEON_BY_HASH and e in ELEMENT_BY_HASH and p in PROMOTION_BY_HASH and c in CURSE_BY_HASH:
                        found.append((
                            record["ts_ms"],
                            DUNGEON_BY_HASH[d],
                            ELEMENT_BY_HASH[e],
                            PROMOTION_BY_HASH[p],
                            CURSE_BY_HASH[c],
                        ))
    return found


def scan_zip(zip_path):
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(td)
        ledgers = list(Path(td).rglob("ledger.bin"))
        results = []
        for ledger in ledgers:
            decoded = Path(td) / f"{ledger.parent.name}_decoded.jsonl"
            rc = subprocess.run(
                [sys.executable, str(DECODER), str(ledger), "--out", str(decoded)],
                capture_output=True,
            ).returncode
            if rc != 0 or not decoded.exists():
                print(f"  ! decode failed for {ledger} in {zip_path.name}", file=sys.stderr)
                continue
            results.extend(scan_decoded(decoded))
        return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("zips", nargs="*", help="capture session zip files")
    parser.add_argument("--dir", help="scan every .zip in this directory")
    parser.add_argument("--since-days", type=float, help="with --dir, only zips modified in the last N days")
    args = parser.parse_args()

    zips = [Path(z) for z in args.zips]
    if args.dir:
        cutoff = None
        if args.since_days is not None:
            cutoff = datetime.datetime.now().timestamp() - args.since_days * 86400
        for p in sorted(Path(os.path.expanduser(args.dir)).glob("*.zip")):
            if cutoff is None or p.stat().st_mtime >= cutoff:
                zips.append(p)
    if not zips:
        print("no capture zips to scan")
        return

    hits = []
    for z in zips:
        zip_hits = scan_zip(z)
        print(f"{z.name}: {len({h[1:] for h in zip_hits})} mutated expedition(s)")
        hits.extend(zip_hits)

    by_week = defaultdict(dict)
    for ts_ms, dungeon, element, promotion, curse in sorted(hits):
        by_week[week_for(ts_ms)][dungeon] = make_expedition(
            dungeon, ELEMENT_TO_MUTATION[element], promotion, curse, "capture", element=element
        )

    for week in sorted(by_week):
        result, conflicts = merge_week(week, list(by_week[week].values()))
        for dungeon, prev, new in conflicts:
            print(f"  ! week {week} {dungeon}: {prev['source']} said "
                  f"{prev['mutation']}/{prev['promotion']}/{prev['curse']}, capture says "
                  f"{new['mutation']}/{new['promotion']}/{new['curse']} -- using capture", file=sys.stderr)
        summary = "; ".join(f"{e['dungeon']}: {e['mutation']}/{e['promotion']}/{e['curse']}"
                            for e in result["expeditions"] if e["source"] == "capture")
        print(f"week {week}: {summary}")


if __name__ == "__main__":
    main()
