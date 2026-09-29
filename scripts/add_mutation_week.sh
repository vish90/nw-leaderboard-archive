#!/bin/bash
# Record this week's mutation rotation from a copy-pasted Nysa PVE
# "current-mutations" Discord post, and publish it to the site.
#
# Usage:
#   pbpaste | bash scripts/add_mutation_week.sh 191
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

WEEK="${1:-}"
if [[ -z "$WEEK" ]]; then
  echo "usage: pbpaste | bash scripts/add_mutation_week.sh <week_number>" >&2
  exit 1
fi

python3 "$HERE/parse_mutations.py" --week "$WEEK"
python3 "$HERE/build_mutations_data.py"

cd "$ROOT"
git add "mutations-data/week_${WEEK}.json" docs/mutations.json
git commit -m "Add week ${WEEK} mutation info"
git push
