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

## Updating

After processing new captures:
```
python3 scripts/process_batch.py path/to/new_capture.zip
python3 scripts/build_site_data.py
```
