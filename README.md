# New World Mutated Dungeon Leaderboard Archive

Personal archive of New World's mutated-dungeon leaderboards (score and clear-time
categories, top 100 per week/dungeon), scraped ahead of the game's shutdown.
Player display names are resolved from DTLS capture sessions where possible;
entries without a resolved name are marked `unresolved`.

## Layout

- `leaderboard-data/` — one JSON file per week (`week_N.json`), each containing
  every dungeon/category leaderboard scraped for that week, with `entityId`
  (raw UUIDs) and, where resolved, `name`/`names`.
- `name_directory.json` — accumulated `uuid -> displayName` map built from
  DTLS capture sessions.
- `visited_pages.txt` — week/dungeon/category pages already captured, so the
  priority tool doesn't re-suggest them.
- `mutations-data/` — one JSON file per week (`week_N.json`) summarizing that
  week's active mutation rotation (dungeons, Mutation/Promotion/Curse names,
  inferred element), parsed from the Nysa PVE Discord server's
  `current-mutations` channel.
- `scripts/` — the processing pipeline (see below).
- `docs/` — static site for browsing the archive (filters, sorting, player
  search), served directly via GitHub Pages. To run it locally instead, open
  `docs/index.html` via a local server (not `file://`, since it `fetch()`s
  `data.json`), e.g.:
  ```
  cd docs && python3 -m http.server 8000
  ```
  then visit `http://localhost:8000`.

## Pipeline scripts

- `nw_leaderboard_harvest.py` — scrapes the leaderboard score/rank API for a
  range of weeks (requires a fresh `x-amzn-token`, which is short-lived).
- `decode_dtls_ledger.py` — decodes a captured DTLS ledger (`ledger.bin`) into
  per-message JSONL. Originally from Coldzer0's
  [Aeternum-World](https://github.com/Coldzer0/Aeternum-World) project.
- `extract_name_directory.py` — scans a decoded ledger for `uuid -> name`
  pairs and merges them into `name_directory.json`.
- `apply_name_directory.py` — annotates `leaderboard-data/*.json` with names
  from the directory.
- `coverage_report.py` — ranks which week/dungeon/category pages to capture
  next for the biggest marginal gain in resolved names (greedy set-cover).
- `mark_done.py` — marks a page as already-captured so it stops being
  suggested (e.g. once remaining gaps are confirmed to be deleted accounts).
- `process_batch.py` — end-to-end: given one or more capture-session zips,
  decodes, extracts names, auto-detects which page(s) were viewed (from the
  session's HTTPS capture) and marks them done, then applies everything and
  prints an updated coverage report.
- `build_site_data.py` — flattens `leaderboard-data/*.json` into
  `docs/data.json` for the static site. Re-run after any pipeline update.
- `weekly_update.sh` — end-to-end weekly score update: harvests the next
  week (if a fresh token is in `nw_auth_token.txt`), applies the name
  directory, rebuilds `docs/data.json`, commits, and pushes. Run via a
  Tuesday-night launchd job; reports outcomes to Discord.
- `extract_mutations_from_capture.py` — pulls the live mutation rotation out
  of capture-session zips. Right after login the game server sends the
  client a list of mutated expeditions as CRC32-hashed IDs (GameModeId,
  element category, promotion, curse); this decodes the DTLS ledger, maps
  the hashes back to names, dates the capture to a week, and merges into
  `mutations-data/week_N.json`. `weekly_update.sh` runs it on the last 8
  days of zips in `$NW_CAPTURE_DIR` (default `~/Downloads/harvestedCaptures`).
- `fetch_discord_history.py` / `import_discord_mutations.py` — history
  from week 26 on: pull a channel where the "New World Mutations" bot posts
  (via a read-only bot; raw pulls stay in the gitignored
  `mutations-data/raw/`) and import the bot's structured embeds.
  `mutations-data/week_N.json` holds one entry per dungeon (in 2023,
  dungeons in the same week had different mutations), each tagged with its
  source; when sources disagree, capture beats discord beats paste.
  `build_mutations_data.py` also adds inferred `carryover` entries: when a
  dungeon has scores in week N but no entry, and was mutated in week N-1
  (mid-week patch restarts sometimes left the old rotation running), N-1's
  entry is carried forward. The site labels these "from week N-1".
- `parse_mutations.py` / `build_mutations_data.py` / `add_mutation_week.sh` —
  fallback for weeks with no capture: parse a copy-pasted "New World
  Mutations" Discord post into the same format
  (`pbpaste | bash scripts/add_mutation_week.sh <week>`). Curse tiers are
  dropped (always II at mutation tier 3) and dungeon names are mapped to
  the site's canonical names.
  Theming follows whichever week is selected in the site's Week filter
  (not just the latest week), since different dungeons can carry
  different mutations in the same week. Icons and colors in
  `docs/assets/mutation-icons/` are the actual in-game mutator icons and
  `BackgroundColor` values, pulled from
  [nw-buddy-data](https://github.com/giniedp/nw-buddy-data)'s
  `javelindata_elementalmutations.json` / `_promotionmutations.json` /
  `_cursemutations.json` datatables (extracted New World game assets, not
  covered by nw-buddy's own MIT license). Curses have no per-curse color
  in the game data, so they share one neutral tone.

## Updating

Scores (normally automatic, see `weekly_update.sh`):
```
python3 scripts/nw_leaderboard_harvest.py --start-week N --end-week N --skip-existing
python3 scripts/apply_name_directory.py
python3 scripts/build_site_data.py
```

Names, after processing new DTLS captures:
```
python3 scripts/process_batch.py path/to/new_capture.zip
python3 scripts/build_site_data.py
```

Mutations, after copying the week's post from Discord:
```
pbpaste | bash scripts/add_mutation_week.sh <week>
```
