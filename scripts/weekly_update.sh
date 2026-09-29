#!/bin/bash
# Weekly leaderboard fetch: harvests the next week (if a fresh token is
# present), rebuilds the site data, commits, and pushes. Always reports the
# outcome to Discord. Meant to be run unattended (e.g. via launchd); safe to
# run manually too.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"

WEBHOOK_FILE="$HERE/discord_webhook.txt"
TOKEN_FILE="$HERE/nw_auth_token.txt"
LOG_FILE="$HERE/weekly_update.log"
STEPS_URL="https://app.notion.com/p/3e996b1771628124b10dd8facde7694b?pvs=204"

log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG_FILE"
}

notify() {
  local msg="$1"
  if [[ -f "$WEBHOOK_FILE" ]]; then
    python3 -c '
import json, sys, urllib.request
msg, url = sys.argv[1], sys.argv[2]
data = json.dumps({"content": msg}).encode()
headers = {"Content-Type": "application/json", "User-Agent": "nw-leaderboard-archive-bot/1.0"}
req = urllib.request.Request(url, data=data, headers=headers, method="POST")
try:
    urllib.request.urlopen(req, timeout=15)
except Exception as e:
    print(f"discord notify failed: {e}", file=sys.stderr)
' "$msg" "$(cat "$WEBHOOK_FILE")" >> "$LOG_FILE" 2>&1
  fi
}

last_week=$(ls "$ROOT"/leaderboard-data/week_*.json 2>/dev/null | sed -E 's/.*week_([0-9]+)\.json/\1/' | sort -n | tail -1)
if [[ -z "$last_week" ]]; then
  log "no existing week files found, aborting"
  notify "NW leaderboard update: couldn't find any existing week_*.json files, aborting."
  exit 1
fi
next_week=$((last_week + 1))
log "last local week=$last_week, attempting week=$next_week"

if [[ ! -s "$TOKEN_FILE" ]]; then
  log "no token file present"
  notify "NW leaderboard update: week $next_week is ready to fetch, but there's no auth token in scripts/nw_auth_token.txt. Steps: $STEPS_URL"
  exit 0
fi

harvest_out=$(python3 "$HERE/nw_leaderboard_harvest.py" --start-week "$next_week" --end-week "$next_week" --skip-existing --output-dir "$ROOT/leaderboard-data" 2>&1)
harvest_status=$?
echo "$harvest_out" >> "$LOG_FILE"

if [[ $harvest_status -ne 0 ]]; then
  log "harvest failed (exit $harvest_status)"
  notify "NW leaderboard update: harvest for week $next_week failed (token likely expired/invalid). Steps: $STEPS_URL
Details: $(echo "$harvest_out" | tail -3)"
  exit 1
fi

week_file="$ROOT/leaderboard-data/week_${next_week}.json"
if [[ ! -f "$week_file" ]]; then
  log "no output file written for week $next_week"
  notify "NW leaderboard update: harvest ran but produced no file for week $next_week. Check $LOG_FILE."
  exit 1
fi

has_data=$(python3 -c "
import json
d = json.load(open('$week_file'))
print(1 if any((lb.get('leaderboardEntries') or []) for lb in d.values()) else 0)
")

if [[ "$has_data" != "1" ]]; then
  log "week $next_week returned no entries, likely not published yet"
  rm -f "$week_file"
  notify "NW leaderboard update: week $next_week isn't live on the leaderboard API yet. Will try again next scheduled run."
  exit 0
fi

python3 "$HERE/apply_name_directory.py" --directory "$ROOT/name_directory.json" --leaderboard-dir "$ROOT/leaderboard-data" >> "$LOG_FILE" 2>&1
python3 "$HERE/build_site_data.py" >> "$LOG_FILE" 2>&1

git add "leaderboard-data/week_${next_week}.json" docs/data.json
git commit -m "Add week ${next_week} leaderboard data" >> "$LOG_FILE" 2>&1
git push >> "$LOG_FILE" 2>&1
push_status=$?

if [[ $push_status -ne 0 ]]; then
  log "push failed"
  notify "NW leaderboard update: week $next_week harvested and committed locally, but the push to GitHub failed. Check $LOG_FILE."
  exit 1
fi

log "week $next_week published"
notify "NW leaderboard update: week $next_week harvested and published to the site."
