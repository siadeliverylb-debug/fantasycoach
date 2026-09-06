const gateMessageEl = document.getElementById("visitors-gate-message");
const contentEl = document.getElementById("visitors-content");
const summaryCardsEl = document.getElementById("visitors-summary-cards");
const countryFilterEl = document.getElementById("visitors-country-filter");
const countryTableBodyEl = document.getElementById("visitors-country-table-body");
const dayTableBodyEl = document.getElementById("visitors-day-table-body");
const pathTableBodyEl = document.getElementById("visitors-path-table-body");
const clearMyVisitsBtnEl = document.getElementById("clear-my-visits-btn");
const clearMyVisitsStatusEl = document.getElementById("clear-my-visits-status");

function summaryCard(label, value) {
  const div = document.createElement("div");
  div.className = "admin-summary-card";
  const valueEl = document.createElement("div");
  valueEl.className = "admin-summary-card-value";
  valueEl.textContent = value;
  const labelEl = document.createElement("div");
  labelEl.className = "admin-summary-card-label";
  labelEl.textContent = label;
  div.appendChild(valueEl);
  div.appendChild(labelEl);
  return div;
}

function fillTable(bodyEl, rows, cellsFn) {
  bodyEl.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    for (const text of cellsFn(r)) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }
    bodyEl.appendChild(tr);
  }
}

async function loadVisitorStats() {
  let data;
  try {
    const params = new URLSearchParams({ days: "30" });
    if (countryFilterEl.value) params.set("country", countryFilterEl.value);
    const res = await fetch(`/api/admin/visitors?${params}`);
    if (res.status === 403) {
      gateMessageEl.textContent = "Admin access required. This account isn't an admin.";
      gateMessageEl.hidden = false;
      return;
    }
    if (res.status === 401) {
      gateMessageEl.innerHTML = 'Not logged in. <a href="/">Go to the app</a> and log in first.';
      gateMessageEl.hidden = false;
      return;
    }
    if (!res.ok) throw new Error((await res.json()).detail || "Failed to load visitor stats.");
    data = await res.json();
  } catch (err) {
    gateMessageEl.textContent = `Error: ${err.message}`;
    gateMessageEl.hidden = false;
    return;
  }

  contentEl.hidden = false;

  summaryCardsEl.innerHTML = "";
  summaryCardsEl.appendChild(summaryCard("Total visits (all-time)", data.total_visits.toLocaleString()));
  summaryCardsEl.appendChild(summaryCard("Unique visitors (all-time)", data.total_unique_visitors.toLocaleString()));
  summaryCardsEl.appendChild(summaryCard("Visits (last 30 days)", data.recent_visits.toLocaleString()));
  summaryCardsEl.appendChild(
    summaryCard("Unique visitors (last 30 days)", data.recent_unique_visitors.toLocaleString())
  );

  fillTable(countryTableBodyEl, data.by_country, (r) => [r.country, String(r.visits), String(r.unique_visitors)]);
  fillTable(dayTableBodyEl, data.by_day, (r) => [r.day, String(r.visits), String(r.unique_visitors)]);
  fillTable(pathTableBodyEl, data.by_path, (r) => [
    r.path === "/" ? "/ (home)" : r.path,
    String(r.visits),
    String(r.unique_visitors),
  ]);

  const previousValue = countryFilterEl.value;
  countryFilterEl.innerHTML = '<option value="">All countries</option>';
  for (const r of data.by_country) {
    const opt = document.createElement("option");
    opt.value = r.country;
    opt.textContent = r.country;
    countryFilterEl.appendChild(opt);
  }
  countryFilterEl.value = previousValue;
}

countryFilterEl.addEventListener("change", loadVisitorStats);

clearMyVisitsBtnEl.addEventListener("click", async () => {
  clearMyVisitsBtnEl.disabled = true;
  try {
    const res = await fetch("/api/admin/visitors/clear-mine", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to clear.");
    clearMyVisitsStatusEl.textContent = `Removed ${data.deleted} visit${data.deleted === 1 ? "" : "s"}.`;
    await loadVisitorStats();
  } catch (err) {
    alert(err.message);
  } finally {
    clearMyVisitsBtnEl.disabled = false;
  }
});

loadVisitorStats();
