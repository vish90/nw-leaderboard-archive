#!/bin/bash
# One-shot processing of a capture session zip from Nw_Capture_App:
#   1. mutation rotation -> mutations-data/ + docs/mutations.json
#   2. uuid -> name directory + visited leaderboard pages (process_batch.py)
#   3. harvest every finished week not yet in leaderboard-data/, using the
#      accessToken from the zip's tokenservice response (held in memory only,
#      never written to disk)
#   4. apply names, rebuild docs/data.json, commit the data, push
#
# Usage:
#   bash scripts/process_capture.sh ~/Desktop/week192_20261013_213554.zip
#   bash scripts/process_capture.sh capture.zip --paste /tmp/mutations.txt
#       (raw Discord mutations post for the new week; capture entries win)
#   bash scripts/process_capture.sh capture.zip --no-push     # commit only
#   bash scripts/process_capture.sh capture.zip --no-commit   # leave changes unstaged
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

ZIP=""
PASTE=""
DO_COMMIT=1
DO_PUSH=1
while (( $# )); do
  case "$1" in
    --no-push) DO_PUSH=0 ;;
    --no-commit) DO_COMMIT=0; DO_PUSH=0 ;;
    --paste) PASTE="$2"; shift ;;
    -h|--help) sed -n 2,17p "${BASH_SOURCE[0]}"; exit 0 ;;
    *) ZIP="$1" ;;
  esac
  shift
done

if [[ -z "$ZIP" || ! -f "$ZIP" ]]; then
  echo "usage: $0 <capture.zip> [--paste mutations.txt] [--no-push|--no-commit]" >&2
  exit 1
fi
if [[ -n "$PASTE" && ! -f "$PASTE" ]]; then
  echo "paste file not found: $PASTE" >&2
  exit 1
fi
ZIP="$(cd "$(dirname "$ZIP")" && pwd)/$(basename "$ZIP")"
cd "$ROOT"

step() { echo; echo "=== $* ==="; }

step "1/4 mutation rotation"
python3 "$HERE/extract_mutations_from_capture.py" "$ZIP"
if [[ -n "$PASTE" ]]; then
  # The Discord post is for the week the capture was taken in (the week
  # that just started), same week the capture's rotation lands in.
  paste_week=$(python3 - "$ZIP" "$HERE" <<'PY'
import json, sys, zipfile
sys.path.insert(0, sys.argv[2])
from extract_mutations_from_capture import week_for
with zipfile.ZipFile(sys.argv[1]) as zf:
    print(week_for(json.loads(zf.read("summary.json"))["first_started_ms"]))
PY
)
  echo "adding Discord paste as week $paste_week"
  python3 "$HERE/parse_mutations.py" --week "$paste_week" --raw-file "$PASTE"
fi
python3 "$HERE/build_mutations_data.py"

step "2/4 name directory + visited pages"
python3 "$HERE/process_batch.py" "$ZIP"

step "3/4 leaderboard harvest"
# Prints "<capture_week> <expires_epoch_s>" on line 1 and the token on line 2.
token_info=$(python3 - "$ZIP" "$HERE" <<'PY'
import json, sys, zipfile
sys.path.insert(0, sys.argv[2])
from extract_mutations_from_capture import week_for

with zipfile.ZipFile(sys.argv[1]) as zf:
    names = zf.namelist()
    summary = json.loads(zf.read("summary.json"))
    tok = [n for n in names if n.startswith("tokenservice/") and n.endswith("_tokens.resp.json")]
    if not tok:
        sys.exit("no tokenservice response in this capture")
    resp = json.loads(zf.read(sorted(tok)[-1]))

print(week_for(summary["first_started_ms"]), resp["accessTokenExpirationDate"] // 1000)
print(resp["accessToken"])
PY
)
if [[ $? -ne 0 || -z "$token_info" ]]; then
  echo "could not read token from capture, skipping harvest"
  harvested=()
else
  read -r capture_week expires_at <<< "$(sed -n 1p <<< "$token_info")"
  export NW_AUTH_TOKEN="$(sed -n 2p <<< "$token_info")"
  unset token_info
  now=$(date +%s)
  echo "capture taken in week $capture_week; token expires $(date -r "$expires_at" '+%Y-%m-%d %H:%M %Z')"

  last_week=$(ls "$ROOT"/leaderboard-data/week_*.json | sed -E 's/.*week_([0-9]+)\.json/\1/' | sort -n | tail -1)
  harvested=()
  if (( now >= expires_at )); then
    echo "token already expired, skipping harvest (capture a fresh session)"
  elif (( last_week + 1 > capture_week - 1 )); then
    echo "leaderboard-data already has every finished week (last=$last_week)"
  else
    # Only finished weeks: the capture week itself is still in progress.
    for (( w = last_week + 1; w <= capture_week - 1; w++ )); do
      echo "harvesting week $w"
      if ! python3 "$HERE/nw_leaderboard_harvest.py" --start-week "$w" --end-week "$w" \
           --skip-existing --output-dir "$ROOT/leaderboard-data"; then
        echo "harvest failed for week $w"
        break
      fi
      week_file="$ROOT/leaderboard-data/week_${w}.json"
      has_data=$(python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
print(1 if any((lb.get('leaderboardEntries') or []) for lb in d.values()) else 0)
" "$week_file" 2>/dev/null)
      if [[ "$has_data" == "1" ]]; then
        harvested+=("$w")
      else
        echo "week $w has no entries yet, discarding"
        rm -f "$week_file"
        break
      fi
    done
  fi
  unset NW_AUTH_TOKEN
fi

step "4/4 apply names + rebuild site data"
python3 "$HERE/apply_name_directory.py" --directory "$ROOT/name_directory.json" --leaderboard-dir "$ROOT/leaderboard-data"
python3 "$HERE/build_site_data.py"

if (( DO_COMMIT )); then
  git add leaderboard-data docs/data.json mutations-data docs/mutations.json name_directory.json visited_pages.txt
  if git diff --cached --quiet; then
    echo "nothing changed, no commit"
    exit 0
  fi
  if (( ${#harvested[@]} )); then
    msg="Add week ${harvested[*]} leaderboard data from $(basename "$ZIP")"
  else
    msg="Process capture $(basename "$ZIP")"
  fi
  git commit -m "$msg"
  (( DO_PUSH )) && git push
fi

echo
echo "done. harvested weeks: ${harvested[*]:-none}"
git status --short
