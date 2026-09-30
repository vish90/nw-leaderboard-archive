#!/usr/bin/env python3
"""Download a Discord channel's full message history via a bot account.

The bot needs View Channel + Read Message History on the channel, and the
Message Content intent enabled in the Developer Portal (without it, Discord
returns messages with empty content/embeds). The token is read from
DISCORD_BOT_TOKEN or scripts/discord_bot_token.txt (gitignored).

Usage:
    python3 fetch_discord_history.py 1134545637975805973 --out mutations-data/raw/nysa_current_mutations.json
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN_FILE = HERE / "discord_bot_token.txt"
API = "https://discord.com/api/v10"


def load_token():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        sys.exit(f"No bot token: set DISCORD_BOT_TOKEN or put it in {TOKEN_FILE}")
    return token


def get(path, token):
    req = urllib.request.Request(
        API + path,
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "DiscordBot (https://github.com/vish90/nw-leaderboard-archive, 1.0)",
        },
    )
    while True:
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = float(json.loads(e.read().decode("utf-8")).get("retry_after", 1))
                time.sleep(wait + 0.25)
                continue
            if e.code in (401, 403):
                sys.exit(f"HTTP {e.code}: bot token invalid, or bot can't see/read this channel")
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("channel_id")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    token = load_token()
    messages = []
    before = None
    while True:
        query = "?limit=100" + (f"&before={before}" if before else "")
        page = get(f"/channels/{args.channel_id}/messages{query}", token)
        if not page:
            break
        messages.extend(page)
        before = page[-1]["id"]
        print(f"fetched {len(messages)} messages (oldest so far {page[-1]['timestamp'][:10]})")
        time.sleep(0.5)

    messages.sort(key=lambda m: int(m["id"]))
    if messages and not any(m.get("content") or m.get("embeds") for m in messages):
        print("warning: every message has empty content and embeds -- enable the Message Content "
              "intent for the bot in the Developer Portal", file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(messages, indent=1), encoding="utf-8")
    print(f"saved {len(messages)} messages -> {out}")


if __name__ == "__main__":
    main()
