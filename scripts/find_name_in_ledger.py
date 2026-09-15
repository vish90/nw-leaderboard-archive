#!/usr/bin/env python3
"""Search a decoded DTLS ledger (decoded_session.jsonl, from decode_dtls_ledger.py)
for known-plaintext strings (e.g. a player display name) inside the raw
payload_hex bytes of each carrier message.

Usage:
    python3 find_name_in_ledger.py decoded_session.jsonl "Content King" "SomeFriendName"

Prints only small matched snippets (record index, channel, byte offset, and
a short hex/ascii window around the match) -- not the whole file -- so you
can share just the relevant lines instead of your full session capture.
"""

import json
import sys

CONTEXT_BYTES = 24


def search_encodings(name):
    return {
        "utf-8": name.encode("utf-8"),
        "utf-16le": name.encode("utf-16-le"),
    }


def hexdump_window(data, start, end):
    window = data[max(0, start - CONTEXT_BYTES):min(len(data), end + CONTEXT_BYTES)]
    return window.hex()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    needles = sys.argv[2:]
    encoded_needles = []
    for name in needles:
        for enc_name, enc_bytes in search_encodings(name).items():
            encoded_needles.append((name, enc_name, enc_bytes))

    match_count = 0
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            for msg in rec.get("messages", []) or []:
                payload_hex = msg.get("payload_hex")
                if not payload_hex:
                    continue
                data = bytes.fromhex(payload_hex)
                for name, enc_name, needle in encoded_needles:
                    idx = data.find(needle)
                    if idx != -1:
                        match_count += 1
                        window = hexdump_window(data, idx, idx + len(needle))
                        print(f"line {line_no} channel={msg.get('channel')} "
                              f"seq={msg.get('seq')} name={name!r} enc={enc_name} "
                              f"offset={idx} payload_len={len(data)}")
                        print(f"  context_hex: {window}")
                        print()

    print(f"done. {match_count} match(es) found.", file=sys.stderr)


if __name__ == "__main__":
    main()
