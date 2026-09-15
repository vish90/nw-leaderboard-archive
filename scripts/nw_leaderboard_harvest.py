#!/usr/bin/env python3
"""Harvest New World mutated-dungeon leaderboards, week 187 down to week 1.

Endpoint structure, headers, and dungeon list were reverse engineered from
real captures taken with the NW Capture App (extended with an
WinHttpAddRequestHeaders hook) while the leaderboard screen was open
in-game. The auth token the client sends (x-amzn-token) is short-lived and
account-bound, so it's never hardcoded here -- supply it either via the
NW_AUTH_TOKEN environment variable, or by pasting it (and nothing else)
into nw_auth_token.txt next to this script. Since the token is short-lived,
you'll still need to refresh whichever one you use with a value from a
recent capture periodically.
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HOST = "eu-central-1.client.stats-service.amazongames.com"
BASE_URL = f"https://{HOST}/new-world/pc/leaderboards"

# Confirmed from capture (11 mutated-dungeon expeditions active that week).
DUNGEONS = [
    "DungeonBrimstoneSands00",
    "DungeonCutlassKeys00",
    "DungeonEbonscale00",
    "DungeonEdengrove00",
    "DungeonFirstLight01",
    "DungeonGreatCleave00",
    "DungeonGreatCleave01",
    "DungeonReekwater00",
    "DungeonRestlessShores01",
    "DungeonShatterMtn00",
    "DungeonShatteredObelisk",
]

# Confirmed from capture.
METRICS = [
    "top-group-expedition-score",
    "min-dungeon-group-gold-medal-expedition-clear-time",
]

TIER = 3
PAGE_SIZE = 100
MAX_PAGES = 10  # safety cap on pagination per leaderboard
MAX_RETRIES = 5

# Static values confirmed from capture (not secrets).
USER_AGENT = "aws-sdk-cpp/1.7.193 Windows/10.0.22621.4036 AMD64 MSVC/1936"
API_VERSION = "2022-08-22T23:45:34Z"

TOKEN_FILE = Path(__file__).resolve().parent / "nw_auth_token.txt"


def load_token():
    token = os.environ.get("NW_AUTH_TOKEN")
    if token:
        return token.strip()
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    sys.exit(
        f"No auth token found. Either export NW_AUTH_TOKEN, or paste a fresh "
        f"x-amzn-token value (and nothing else) into {TOKEN_FILE} -- the "
        "token is short-lived, so capture and run close together."
    )


def build_headers():
    token = load_token()
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "x-amz-api-version": API_VERSION,
        "x-amzn-token": token,
    }


HEADERS = None


def fetch_json(url, attempt=1):
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code in (401, 403):
            sys.exit(
                f"HTTP {e.code} on {url} -- NW_AUTH_TOKEN is expired or invalid. "
                "Capture a fresh token and re-export NW_AUTH_TOKEN."
            )
        if e.code == 429 or e.code >= 500:
            if attempt > MAX_RETRIES:
                print(f"    giving up after {MAX_RETRIES} retries: {url} -> {e.code}", file=sys.stderr)
                return None
            retry_after = e.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else min(60, 2 ** attempt) + random.uniform(0, 1)
            print(f"    {e.code} on attempt {attempt}, backing off {wait:.1f}s: {url}", file=sys.stderr)
            time.sleep(wait)
            return fetch_json(url, attempt + 1)
        print(f"    HTTP {e.code} (not retrying): {url}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        if attempt > MAX_RETRIES:
            print(f"    giving up after {MAX_RETRIES} retries: {url} -> {e}", file=sys.stderr)
            return None
        wait = min(60, 2 ** attempt) + random.uniform(0, 1)
        print(f"    network error on attempt {attempt}, backing off {wait:.1f}s: {e}", file=sys.stderr)
        time.sleep(wait)
        return fetch_json(url, attempt + 1)


def fetch_leaderboard(metric, dungeon, week, delay, jitter):
    entries = []
    leaderboard_size = None
    is_backed_up = None
    for page in range(1, MAX_PAGES + 1):
        path = f"{metric}.{dungeon}.{TIER}.w{week}"
        url = f"{BASE_URL}/{path}?pageNumber={page}&pageSize={PAGE_SIZE}"
        data = fetch_json(url)
        time.sleep(delay + random.uniform(0, jitter))
        if data is None:
            break
        page_entries = data.get("leaderboardEntries") or []
        entries.extend(page_entries)
        leaderboard_size = data.get("leaderboardSize", leaderboard_size)
        is_backed_up = data.get("isBackedUp", is_backed_up)
        if len(page_entries) < PAGE_SIZE:
            break
    return {
        "leaderboardEntries": entries,
        "leaderboardSize": leaderboard_size,
        "isBackedUp": is_backed_up,
    }


def harvest_week(week, delay, jitter):
    week_result = {}
    for dungeon in DUNGEONS:
        for metric in METRICS:
            key = f"{metric}.{dungeon}"
            print(f"  fetching {key} w{week}")
            week_result[key] = fetch_leaderboard(metric, dungeon, week, delay, jitter)
    return week_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-week", type=int, default=187)
    parser.add_argument("--end-week", type=int, default=1)
    parser.add_argument("--output-dir", default="./leaderboard-data")
    parser.add_argument("--delay", type=float, default=1.5, help="base seconds between requests")
    parser.add_argument("--jitter", type=float, default=1.0, help="extra random seconds added to delay")
    parser.add_argument("--week-delay", type=float, default=3.0, help="extra pause between weeks")
    parser.add_argument("--skip-existing", action="store_true", help="skip weeks that already have an output file")
    args = parser.parse_args()

    global HEADERS
    HEADERS = build_headers()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for week in range(args.start_week, args.end_week - 1, -1):
        out_path = out_dir / f"week_{week}.json"
        if args.skip_existing and out_path.exists():
            print(f"week {week}: output exists, skipping")
            continue

        print(f"week {week}: harvesting")
        week_result = harvest_week(week, args.delay, args.jitter)

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(week_result, f, indent=2)
        print(f"week {week}: saved -> {out_path}")

        time.sleep(args.week_delay + random.uniform(0, args.jitter))

    print("done")


if __name__ == "__main__":
    main()
