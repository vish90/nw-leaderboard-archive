#!/usr/bin/env python3
"""Batch-process incoming capture session zips from helpers.

For each zip: unzips it, finds dtls/ledger.bin, decodes it, and merges
the resulting names into name_directory.json. Also scans the zip's
stats-service HTTPS capture (if present) for which leaderboard page(s)
were actually viewed, and marks those done in visited_pages.txt so
coverage_report.py stops re-suggesting them. After all zips are
processed, applies the combined directory to leaderboard-data and
prints an updated coverage report.

Usage:
    python3 process_batch.py /path/to/incoming/*.zip
    python3 process_batch.py --incoming-dir ~/Desktop/helper_captures
"""

import argparse
import glob
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECODE_SCRIPT = HERE / "decode_dtls_ledger.py"
EXTRACT_SCRIPT = HERE / "extract_name_directory.py"
APPLY_SCRIPT = HERE / "apply_name_directory.py"
REPORT_SCRIPT = HERE / "coverage_report.py"
DIRECTORY_PATH = HERE / "name_directory.json"
LEADERBOARD_DIR = HERE / "leaderboard-data"
VISITED_FILE = HERE / "visited_pages.txt"

LEADERBOARD_PATH_RE = re.compile(
    r"leaderboards/([a-z-]+)\.(Dungeon[A-Za-z0-9]+)\.\d+\.w(\d+)"
)


def find_visited_pages(extract_dir: Path) -> set:
    pages = set()
    for meta_path in extract_dir.rglob("*stats-service.amazongames.com*/*.meta.json"):
        try:
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        path = meta.get("path", "")
        m = LEADERBOARD_PATH_RE.search(path)
        if m:
            metric, dungeon_id, week = m.groups()
            pages.add(f"week_{week}:{metric}.{dungeon_id}")
    return pages


def mark_pages_visited(pages: set) -> int:
    if not pages:
        return 0
    existing = set()
    if VISITED_FILE.exists():
        existing = {l.strip() for l in VISITED_FILE.read_text(encoding="utf-8").splitlines() if l.strip()}
    new_pages = pages - existing
    if new_pages:
        with VISITED_FILE.open("a", encoding="utf-8") as f:
            for p in sorted(new_pages):
                f.write(p + "\n")
    return len(new_pages)


def process_zip(zip_path: Path, work_dir: Path) -> bool:
    extract_dir = work_dir / zip_path.stem
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)

    ledgers = list(extract_dir.rglob("ledger.bin"))
    if not ledgers:
        print(f"  ! no ledger.bin found in {zip_path.name}, skipping")
        return False

    for ledger in ledgers:
        decoded_path = work_dir / f"{zip_path.stem}_decoded.jsonl"
        print(f"  decoding {ledger} -> {decoded_path.name}")
        rc = subprocess.call([
            sys.executable, str(DECODE_SCRIPT), str(ledger), "--out", str(decoded_path)
        ])
        if rc != 0:
            print(f"  ! decode failed for {ledger}")
            continue

        print(f"  extracting names from {decoded_path.name}")
        subprocess.call([
            sys.executable, str(EXTRACT_SCRIPT), str(decoded_path), "--out", str(DIRECTORY_PATH)
        ])

    pages = find_visited_pages(extract_dir)
    if pages:
        newly_marked = mark_pages_visited(pages)
        print(f"  found {len(pages)} page(s) viewed this session, {newly_marked} newly marked done:")
        for p in sorted(pages):
            print(f"    {p}")
    else:
        print(f"  ! no leaderboard HTTPS calls found in this zip -- can't auto-mark visited, "
              f"verify manually and use mark_done.py if needed")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zips", nargs="*", help="capture session zip files")
    parser.add_argument("--incoming-dir", help="process every *.zip in this directory")
    args = parser.parse_args()

    zip_paths = [Path(p) for p in args.zips]
    if args.incoming_dir:
        zip_paths += [Path(p) for p in glob.glob(f"{args.incoming_dir}/*.zip")]

    if not zip_paths:
        print("no zip files given")
        return

    with tempfile.TemporaryDirectory(prefix="nw_batch_") as tmp:
        work_dir = Path(tmp)
        for zp in zip_paths:
            print(f"=== {zp.name} ===")
            if not zp.is_file():
                print(f"  ! not found: {zp}")
                continue
            process_zip(zp, work_dir)

    print()
    print("=== applying combined directory to leaderboard-data ===")
    subprocess.call([
        sys.executable, str(APPLY_SCRIPT),
        "--directory", str(DIRECTORY_PATH),
        "--leaderboard-dir", str(LEADERBOARD_DIR),
    ])

    print()
    print("=== updated coverage report ===")
    subprocess.call([
        sys.executable, str(REPORT_SCRIPT),
        "--leaderboard-dir", str(LEADERBOARD_DIR),
        "--top-pages", "20", "--top-uuids", "0",
    ])


if __name__ == "__main__":
    main()
