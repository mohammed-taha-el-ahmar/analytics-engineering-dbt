const dbBadge = document.getElementById("dbBadge");
const catalogList = document.getElementById("catalogList");
const askForm = document.getElementById("askForm");
const askBtn = document.getElementById("askBtn");
const questionInput = document.getElementById("question");
const output = document.getElementById("output");
const emptyState = document.getElementById("emptyState");
const errorBox = document.getElementById("errorBox");
const trail = document.getElementById("trail");
const sqlBlock = document.getElementById("sqlBlock");
const explanation = document.getElementById("explanation");
const resultLabel = document.getElementById("resultLabel");
const resultTable = document.getElementById("resultTable");

async function loadCatalog() {
  try {
    const res = await fetch("/api/catalog");
    const data = await res.json();
    dbBadge.textContent = data.db_target === "snowflake" ? "snowflake · prod" : "duckdb · demo";

    catalogList.innerHTML = "";
    data.marts.forEach((mart) => {
      const item = document.createElement("div");
      item.className = "catalog-item";
      item.innerHTML = `
        <div class="catalog-item-name">${escapeHtml(mart.name)}</div>
        <div class="catalog-item-desc">${escapeHtml(mart.description || "No description.")}</div>
        <div class="catalog-item-cols">${mart.columns.map(escapeHtml).join(", ")}</div>
      `;
      catalogList.appendChild(item);
    });
  } catch (err) {
    dbBadge.textContent = "offline";
    catalogList.textContent = "Could not load catalog.";
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

function renderTrail(history) {
  trail.innerHTML = "";
  history.forEach((h) => {
    const pill = document.createElement("span");
    pill.className = `trail-pill ${h.status === "ok" ? "ok" : "fail"}`;
    pill.title = h.detail;
    pill.textContent = `${h.attempt}: ${h.status === "ok" ? "executed" : h.status}`;
    trail.appendChild(pill);
  });
}

function renderTable(columns, rows) {
  if (!rows.length) {
    resultTable.innerHTML = "<tr><td>No rows returned.</td></tr>";
    return;
  }
  const thead = `<thead><tr>${columns.map((c) => `<th>${escapeHtml(c)}</th>`).join("")}</tr></thead>`;
  const tbody = `<tbody>${rows
    .map((row) => `<tr>${row.map((v) => `<td>${escapeHtml(v)}</td>`).join("")}</tr>`)
    .join("")}</tbody>`;
  resultTable.innerHTML = thead + tbody;
}

askForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  askBtn.disabled = true;
  askBtn.textContent = "Running…";
  errorBox.hidden = true;
  emptyState.hidden = true;

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();

    if (!res.ok) {
      output.hidden = true;
      errorBox.hidden = false;
      errorBox.textContent = data.error || "Something went wrong.";
      return;
    }

    output.hidden = false;
    renderTrail(data.history || []);
    sqlBlock.textContent = data.sql;
    explanation.textContent = data.explanation;
    resultLabel.textContent = `result · ${data.rows.length} row${data.rows.length === 1 ? "" : "s"} · ${data.attempts} attempt${data.attempts === 1 ? "" : "s"}`;
    renderTable(data.columns, data.rows);
  } catch (err) {
    output.hidden = true;
    errorBox.hidden = false;
    errorBox.textContent = "Request failed — is the agent service running?";
  } finally {
    askBtn.disabled = false;
    askBtn.textContent = "Run";
  }
});

loadCatalog();
