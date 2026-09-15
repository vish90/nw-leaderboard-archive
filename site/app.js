const MAX_RENDERED_ROWS = 500;

let DATA = { rows: [], dungeons: [], weeks: [] };
let sortKey = "value";
let sortDir = "desc";

const dungeonFilter = document.getElementById("dungeon-filter");
const weekFilter = document.getElementById("week-filter");
const metricFilter = document.getElementById("metric-filter");
const playerSearch = document.getElementById("player-search");
const resolvedOnly = document.getElementById("resolved-only");
const resultInfo = document.getElementById("result-info");
const rowsBody = document.getElementById("rows");
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

function getFiltered() {
  const dungeon = dungeonFilter.value;
  const week = weekFilter.value ? parseInt(weekFilter.value, 10) : null;
  const metric = metricFilter.value;
  const query = playerSearch.value.trim();
  const onlyResolved = resolvedOnly.checked;

  return DATA.rows.filter(r => {
    if (dungeon && r.dungeon !== dungeon) return false;
    if (week !== null && r.week !== week) return false;
    if (metric && r.metric !== metric) return false;
    if (!rowMatchesPlayer(r, query)) return false;
    if (onlyResolved && !r.players.some(p => p)) return false;
    return true;
  });
}

function sortRows(rows) {
  const dir = sortDir === "asc" ? 1 : -1;
  return rows.slice().sort((a, b) => {
    let av = a[sortKey];
    let bv = b[sortKey];
    if (sortKey === "dungeon" || sortKey === "metric") {
      av = (av || "").toLowerCase();
      bv = (bv || "").toLowerCase();
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    }
    av = av === null || av === undefined ? -Infinity : av;
    bv = bv === null || bv === undefined ? -Infinity : bv;
    return (av - bv) * dir;
  });
}

function render() {
  const filtered = getFiltered();
  const sorted = sortRows(filtered);
  const shown = sorted.slice(0, MAX_RENDERED_ROWS);
  const query = playerSearch.value.trim().toLowerCase();

  resultInfo.textContent = filtered.length > MAX_RENDERED_ROWS
    ? `Showing first ${MAX_RENDERED_ROWS.toLocaleString()} of ${filtered.length.toLocaleString()} matching rows -- narrow your filters to see more`
    : `${filtered.length.toLocaleString()} matching row${filtered.length === 1 ? "" : "s"}`;

  rowsBody.textContent = "";
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

    const dungeonTd = document.createElement("td");
    dungeonTd.textContent = row.dungeon;
    tr.appendChild(dungeonTd);

    const metricTd = document.createElement("td");
    metricTd.textContent = row.metric === "time" ? "Clear time" : "Score";
    tr.appendChild(metricTd);

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

    rowsBody.appendChild(tr);
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

function setupSortHeaders() {
  document.querySelectorAll("th.sortable").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      if (sortKey === key) {
        sortDir = sortDir === "asc" ? "desc" : "asc";
      } else {
        sortKey = key;
        sortDir = key === "rank" ? "asc" : "desc";
      }
      document.querySelectorAll("th.sortable").forEach(t => t.classList.remove("sort-active"));
      th.classList.add("sort-active");
      render();
    });
  });
}

function setupFilterListeners() {
  [dungeonFilter, weekFilter, metricFilter, resolvedOnly].forEach(el =>
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
    setupSortHeaders();
    setupFilterListeners();
    render();
  })
  .catch(err => {
    subtitle.textContent = "Failed to load data.json: " + err.message;
  });
