const MAX_RENDERED_ROWS = 300;

let DATA = { rows: [], dungeons: [], weeks: [] };
let MUTATIONS = { weeks: {}, latestWeek: null };

const ELEMENT_LABELS = { fire: "Fire", ice: "Ice", void: "Void", nature: "Nature" };

// Colors are the game's own ElementalMutationStaticData / PromotionMutation
// BackgroundColor values (per Hellfire/Icebound/Eternal/Overgrown and
// Savage/Barbaric/Oppressive/Indomitable), not guessed. Curses have no
// per-curse color in the game data, so they share one neutral tone.
const ELEMENT_COLORS = {
  fire: "rgb(92, 26, 26)",
  ice: "rgb(32, 68, 81)",
  void: "rgb(30, 38, 67)",
  nature: "rgb(48, 63, 34)",
};
const PROMOTION_COLORS = {
  savage: "rgb(68, 86, 60)",
  barbaric: "rgb(80, 47, 114)",
  oppressive: "rgb(100, 63, 63)",
  indomitable: "rgb(95, 69, 44)",
};
const CURSE_COLOR = "rgb(55, 55, 60)";
const KNOWN_PROMOTION_ICONS = new Set(["savage", "barbaric", "oppressive", "indomitable"]);
const KNOWN_CURSE_ICONS = new Set(["frenzied", "fiendish", "desiccated", "censored"]);

// Curse (and occasionally promotion) names carry a trailing difficulty tier
// ("Desiccated II") that isn't part of the icon's file name.
function mutationIconKey(name) {
  return (name || "")
    .replace(/\s+(I|II|III|IV)$/, "")
    .trim()
    .toLowerCase();
}

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

// Mutation theming reflects whichever week is currently selected, not just
// the latest one -- different dungeons can carry different mutations in the
// same week (especially further back in the archive), so a single "current"
// badge for all weeks would misrepresent history. With "All weeks" selected
// there's no single week context, so nothing is themed.
function currentMutation() {
  const weekVal = weekFilter.value;
  if (!weekVal) return null;
  return MUTATIONS.weeks[weekVal] || null;
}

// Dungeon names in the Discord mutation post don't always match the site's
// canonical names exactly (e.g. "Tempest's Heart" vs. "Tempest Heart",
// "The Dynasty Shipyard" vs. "Dynasty Shipyard", "Black Powder" vs.
// "Blackpowder"), so compare loosely rather than requiring an exact match.
function normalizeDungeonName(name) {
  return name
    .toLowerCase()
    .replace(/^the\s+/, "")
    .replace(/['’]s\b/g, "")
    .replace(/['’]/g, "")
    .replace(/\s+/g, "")
    .trim();
}

function mutationIncludesDungeon(mutation, dungeon) {
  const target = normalizeDungeonName(dungeon);
  return mutation.dungeons.some(d => normalizeDungeonName(d) === target);
}

function buildSectionEl(dungeon, rowsForDungeon, query) {
  const state = getSectionState(dungeon);

  const section = document.createElement("div");
  section.className = "dungeon-section";

  const mutation = currentMutation();
  const isActiveMutation = mutation && mutationIncludesDungeon(mutation, dungeon);
  if (isActiveMutation && ELEMENT_LABELS[mutation.element]) {
    section.classList.add("theme-" + mutation.element);
  }

  const header = document.createElement("div");
  header.className = "dungeon-header";
  const titleWrap = document.createElement("div");
  titleWrap.className = "dungeon-title";
  const h2 = document.createElement("h2");
  h2.textContent = dungeon;
  titleWrap.appendChild(h2);

  if (isActiveMutation) {
    const weekPill = document.createElement("span");
    weekPill.className = "week-pill";
    weekPill.textContent = `Week ${mutation.week}`;
    titleWrap.appendChild(weekPill);

    const chips = document.createElement("div");
    chips.className = "mutation-chips";

    const chipDefs = [
      { name: mutation.mutation, iconKey: mutation.element, color: ELEMENT_COLORS[mutation.element] },
      {
        name: mutation.promotion,
        iconKey: KNOWN_PROMOTION_ICONS.has(mutationIconKey(mutation.promotion)) ? mutationIconKey(mutation.promotion) : null,
        color: PROMOTION_COLORS[mutationIconKey(mutation.promotion)],
      },
      {
        name: mutation.curse,
        iconKey: KNOWN_CURSE_ICONS.has(mutationIconKey(mutation.curse)) ? mutationIconKey(mutation.curse) : null,
        color: CURSE_COLOR,
      },
    ];

    for (const def of chipDefs) {
      if (!def.name) continue;
      const chip = document.createElement("div");
      chip.className = "mutation-chip";
      if (def.iconKey) {
        const icon = document.createElement("img");
        icon.src = "assets/mutation-icons/" + def.iconKey + ".png";
        icon.alt = def.name;
        if (def.color) icon.style.background = def.color;
        chip.appendChild(icon);
      }
      const label = document.createElement("span");
      label.textContent = def.name;
      chip.appendChild(label);
      chips.appendChild(chip);
    }

    titleWrap.appendChild(chips);
  }
  header.appendChild(titleWrap);

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

const mutationsPromise = fetch("mutations.json")
  .then(r => (r.ok ? r.json() : { weeks: {}, latestWeek: null }))
  .catch(() => ({ weeks: {}, latestWeek: null }));

Promise.all([fetch("data.json").then(r => r.json()), mutationsPromise])
  .then(([data, mutations]) => {
    DATA = data;
    MUTATIONS = mutations;
    subtitle.textContent =
      `${DATA.rows.length.toLocaleString()} rows across ${DATA.weeks.length} weeks and ${DATA.dungeons.length} dungeons`;
    populateFilterOptions();
    if (DATA.weeks.length) {
      weekFilter.value = String(Math.max(...DATA.weeks));
    }
    setupFilterListeners();
    render();
  })
  .catch(err => {
    subtitle.textContent = "Failed to load data.json: " + err.message;
  });
