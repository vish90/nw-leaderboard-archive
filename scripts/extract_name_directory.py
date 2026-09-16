#!/usr/bin/env python3
"""Scan a decoded DTLS ledger (decoded_session.jsonl, from decode_dtls_ledger.py)
for uuid -> displayName records and build a directory.

Two wire shapes are matched:
  1. [0x05][16 raw uuid bytes][1-byte length][name bytes]
     (seen for self/nearby entity records)
  2. [36-char dash-formatted uuid ASCII string][1-byte length][name bytes]
     (seen for bulk leaderboard-view name resolution -- much higher yield;
     this is the one that fires when a leaderboard page is opened/scrolled,
     resolving every entity id shown on screen in one broadcast)

Usage:
    python3 extract_name_directory.py decoded_session.jsonl --out name_directory.json
"""

import argparse
import json
import re

UUID_STR_RE = re.compile(
    rb"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def format_uuid(raw):
    h = raw.hex()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def add_hit(directory, hits, uid, name):
    uid = uid.lower()
    directory.setdefault(uid, {}).setdefault(name, 0)
    directory[uid][name] += 1
    hits[0] += 1


def decode_name(name_bytes):
    """Decode a length-prefixed name field as UTF-8 (not ASCII-only), so
    accented/non-Latin characters (e.g. Zenon d Cittium) aren't silently
    dropped. The length prefix is a byte count, so multi-byte UTF-8
    sequences are already correctly bounded by the slice; only the
    decode/validation step needs to be Unicode-aware. Rejects control
    characters but otherwise allows any printable Unicode."""
    try:
        name = name_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not name or not name.strip():
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        return None
    return name


def scan_payload_raw_uuid(data, directory, hits):
    n = len(data)
    i = 0
    while i < n - 17:
        if data[i] == 0x05:
            uuid_bytes = data[i + 1:i + 17]
            j = i + 17
            length = data[j]
            if 3 <= length <= 40 and j + 1 + length <= n:
                name_bytes = data[j + 1:j + 1 + length]
                name = decode_name(name_bytes)
                if name:
                    add_hit(directory, hits, format_uuid(uuid_bytes), name)
        i += 1


def scan_payload_string_uuid(data, directory, hits):
    for m in UUID_STR_RE.finditer(data):
        end = m.end()
        if end >= len(data):
            continue
        length = data[end]
        if 2 <= length <= 24 and end + 1 + length <= len(data):
            name_bytes = data[end + 1:end + 1 + length]
            name = decode_name(name_bytes)
            if name:
                add_hit(directory, hits, m.group().decode("ascii"), name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger_jsonl")
    parser.add_argument("--out", default="name_directory.json")
    parser.add_argument("--fresh", action="store_true",
                         help="start empty instead of merging into an existing --out file")
    args = parser.parse_args()

    directory = {}
    existing_count = 0
    if not args.fresh:
        try:
            with open(args.out, encoding="utf-8") as f:
                for uid, name in json.load(f).items():
                    directory[uid] = {name: 1}
                    existing_count += 1
        except FileNotFoundError:
            pass

    hits = [0]
    line_count = 0
    with open(args.ledger_jsonl, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for msg in rec.get("messages", []) or []:
                payload_hex = msg.get("payload_hex")
                if not payload_hex:
                    continue
                data = bytes.fromhex(payload_hex)
                scan_payload_raw_uuid(data, directory, hits)
                scan_payload_string_uuid(data, directory, hits)

    resolved = {uid: max(names, key=names.get) for uid, names in directory.items()}

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(resolved, f, indent=2, sort_keys=True)

    new_count = len(resolved) - existing_count
    print(f"scanned {line_count} lines, {hits[0]} raw hits, "
          f"{len(resolved)} distinct uuids total ({existing_count} carried over, "
          f"~{new_count} new) -> {args.out}")


if __name__ == "__main__":
    main()
