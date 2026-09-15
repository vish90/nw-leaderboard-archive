const MAX_RENDERED_ROWS = 300;

let DATA = { rows: [], dungeons: [], weeks: [] };

// Per-dungeon UI state: which metric tab is active, and current sort.
const sectionState = {}; // dungeon -> { metric: 'score'|'time', sortKey, sortDir }

function getSectionState(dungeon) {
  if (!sectionState[dungeon]) {
    sectionState[dungeon] = { metric: "score", sortKey: "rank", sortDir: "asc" };
  }
  return sectionState[dungeon];
}

const dungeonFilter = document.getElementById("dungeon-filter");
const weekFilter = document.getElementById("week-filter");
const playerSearch = document.getElementById("player-search");
const resolvedOnly = document.getElementById("resolved-only");
const sectionsEl = document.getElementById("sections");
const subtitle = document.getElementById("subtitle");

function formatValue(value, metric) {
  if (value === null || value === undefined) return "";
  if (metric === "time") {
    const mins = Math.floor(value / 60);
    const secs = value % 60;
    return mins + ":" + String(secs).padStart(2, "0");
  }
  return value.toLocaleString();
}

function rowMatchesPlayer(row, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  return row.players.some(p => p && p.toLowerCase().includes(q));
}

function baseFiltered() {
  const dungeon = dungeonFilter.value;
  const week = weekFilter.value ? parseInt(weekFilter.value, 10) : null;
  const query = playerSearch.value.trim();
  const onlyResolved = resolvedOnly.checked;

  return DATA.rows.filter(r => {
    if (dungeon && r.dungeon !== dungeon) return false;
    if (week !== null && r.week !== week) return false;
    if (!rowMatchesPlayer(r, query)) return false;
    if (onlyResolved && !r.players.some(p => p)) return false;
    return true;
  });
}

function sortRows(rows, sortKey, sortDir) {
  const dir = sortDir === "asc" ? 1 : -1;
  return rows.slice().sort((a, b) => {
    let av = a[sortKey];
    let bv = b[sortKey];
    av = av === null || av === undefined ? -Infinity : av;
    bv = bv === null || bv === undefined ? -Infinity : bv;
    return (av - bv) * dir;
  });
}

function buildSectionEl(dungeon, rowsForDungeon, query) {
  const state = getSectionState(dungeon);

  const section = document.createElement("div");
  section.className = "dungeon-section";

  const header = document.createElement("div");
  header.className = "dungeon-header";
  const h2 = document.createElement("h2");
  h2.textContent = dungeon;
  header.appendChild(h2);

  const tabs = document.createElement("div");
  tabs.className = "tabs";
  ["score", "time"].forEach(m => {
    const btn = document.createElement("button");
    btn.className = "tab" + (state.metric === m ? " active" : "");
    btn.textContent = m === "time" ? "Clear Time" : "Score";
    btn.addEventListener("click", () => {
      state.metric = m;
      render();
    });
    tabs.appendChild(btn);
  });
  header.appendChild(tabs);
  section.appendChild(header);

  const metricRows = rowsForDungeon.filter(r => r.metric === state.metric);
  const sorted = sortRows(metricRows, state.sortKey, state.sortDir);
  const shown = sorted.slice(0, MAX_RENDERED_ROWS);

  const info = document.createElement("div");
  info.className = "result-info";
  info.textContent = metricRows.length > MAX_RENDERED_ROWS
    ? `Showing first ${MAX_RENDERED_ROWS} of ${metricRows.length.toLocaleString()} rows`
    : `${metricRows.length.toLocaleString()} row${metricRows.length === 1 ? "" : "s"}`;
  section.appendChild(info);

  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const columns = [
    { key: "rank", label: "Rank" },
    { key: "value", label: state.metric === "time" ? "Time" : "Score" },
    { key: "week", label: "Week" },
    { key: null, label: "Players" },
  ];
  columns.forEach(col => {
    const th = document.createElement("th");
    th.textContent = col.label;
    if (col.key) {
      th.className = "sortable" + (state.sortKey === col.key ? " sort-active" : "");
      th.addEventListener("click", () => {
        if (state.sortKey === col.key) {
          state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
        } else {
          state.sortKey = col.key;
          state.sortDir = col.key === "rank" ? "asc" : "desc";
        }
        render();
      });
    }
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  for (const row of shown) {
    const tr = document.createElement("tr");

    const rankTd = document.createElement("td");
    rankTd.textContent = row.rank ?? "";
    tr.appendChild(rankTd);

    const valTd = document.createElement("td");
    valTd.textContent = formatValue(row.value, row.metric);
    tr.appendChild(valTd);

    const weekTd = document.createElement("td");
    weekTd.textContent = row.week ?? "";
    tr.appendChild(weekTd);

    const playersTd = document.createElement("td");
    row.players.forEach((p, i) => {
      if (i > 0) playersTd.appendChild(document.createTextNode(", "));
      const span = document.createElement("span");
      if (!p) {
        span.className = "unresolved";
        span.textContent = "unresolved";
      } else {
        span.className = "player" + (query && p.toLowerCase().includes(query) ? " match" : "");
        span.textContent = p;
      }
      playersTd.appendChild(span);
    });
    tr.appendChild(playersTd);

    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  section.appendChild(table);

  return section;
}

function render() {
  const filtered = baseFiltered();
  const query = playerSearch.value.trim().toLowerCase();

  const byDungeon = new Map();
  for (const r of filtered) {
    if (!byDungeon.has(r.dungeon)) byDungeon.set(r.dungeon, []);
    byDungeon.get(r.dungeon).push(r);
  }

  const dungeonsToShow = DATA.dungeons.filter(d => byDungeon.has(d));

  sectionsEl.textContent = "";
  for (const dungeon of dungeonsToShow) {
    sectionsEl.appendChild(buildSectionEl(dungeon, byDungeon.get(dungeon), query));
  }

  if (dungeonsToShow.length === 0) {
    const empty = document.createElement("p");
    empty.className = "result-info";
    empty.textContent = "No matching rows.";
    sectionsEl.appendChild(empty);
  }
}

function populateFilterOptions() {
  for (const d of DATA.dungeons) {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = d;
    dungeonFilter.appendChild(opt);
  }
  for (const w of DATA.weeks) {
    const opt = document.createElement("option");
    opt.value = w;
    opt.textContent = "Week " + w;
    weekFilter.appendChild(opt);
  }
}

function setupFilterListeners() {
  [dungeonFilter, weekFilter, resolvedOnly].forEach(el =>
    el.addEventListener("change", render)
  );
  playerSearch.addEventListener("input", render);
}

fetch("data.json")
  .then(r => r.json())
  .then(data => {
    DATA = data;
    subtitle.textContent =
      `${DATA.rows.length.toLocaleString()} rows across ${DATA.weeks.length} weeks and ${DATA.dungeons.length} dungeons`;
    populateFilterOptions();
    setupFilterListeners();
    render();
  })
  .catch(err => {
    subtitle.textContent = "Failed to load data.json: " + err.message;
  });
