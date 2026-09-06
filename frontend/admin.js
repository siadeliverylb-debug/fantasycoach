const gateMessageEl = document.getElementById("admin-gate-message");
const contentEl = document.getElementById("admin-content");
const summaryCardsEl = document.getElementById("admin-summary-cards");
const tableBodyEl = document.getElementById("admin-table-body");
const maintenanceToggleBtnEl = document.getElementById("maintenance-toggle-btn");
const maintenanceStatusEl = document.getElementById("maintenance-status");

function fmtUsd(n) {
  return `$${n.toFixed(2)}`;
}

function summaryCard(label, value, extraClass) {
  const div = document.createElement("div");
  div.className = `admin-summary-card${extraClass ? ` ${extraClass}` : ""}`;
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

async function loadAdminUsage() {
  let rows;
  try {
    const res = await fetch("/api/admin/usage");
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
    if (!res.ok) throw new Error((await res.json()).detail || "Failed to load usage.");
    rows = await res.json();
  } catch (err) {
    gateMessageEl.textContent = `Error: ${err.message}`;
    gateMessageEl.hidden = false;
    return;
  }

  contentEl.hidden = false;

  const totalRevenue = rows.reduce((sum, r) => sum + r.revenue_usd, 0);
  const totalCost = rows.reduce((sum, r) => sum + r.api_cost_usd, 0);
  const totalCreditValue = rows.reduce((sum, r) => sum + r.credit_value_usd, 0);
  const totalPurchased = rows.reduce((sum, r) => sum + r.credits_purchased, 0);
  const totalSpent = rows.reduce((sum, r) => sum + r.lifetime_credits_spent, 0);
  const netMargin = totalRevenue - totalCost;

  summaryCardsEl.innerHTML = "";
  summaryCardsEl.appendChild(summaryCard("Total users", rows.length.toLocaleString()));
  summaryCardsEl.appendChild(summaryCard("Total revenue (real $)", fmtUsd(totalRevenue)));
  summaryCardsEl.appendChild(summaryCard("Total API cost (tokens)", fmtUsd(totalCost)));
  summaryCardsEl.appendChild(
    summaryCard(
      "Net profit / loss",
      `${netMargin >= 0 ? "+" : ""}${fmtUsd(netMargin)}`,
      netMargin >= 0 ? "admin-summary-card-positive" : "admin-summary-card-negative"
    )
  );
  summaryCardsEl.appendChild(summaryCard("Credits purchased (all-time)", totalPurchased.toLocaleString()));
  summaryCardsEl.appendChild(summaryCard("Credits spent (all-time)", totalSpent.toLocaleString()));
  summaryCardsEl.appendChild(
    summaryCard("Est. value of free/bonus credits redeemed", fmtUsd(totalCreditValue), "admin-summary-card-muted")
  );

  tableBodyEl.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    const margin = r.revenue_usd - r.api_cost_usd;
    const emailCell = document.createElement("td");
    emailCell.textContent = r.email + (r.is_admin ? " (admin)" : "");
    tr.appendChild(emailCell);

    const teamNameCell = document.createElement("td");
    teamNameCell.textContent = r.team_name
      ? `${r.team_name}${r.manager_name ? ` (${r.manager_name})` : ""}`
      : "-";
    tr.appendChild(teamNameCell);

    const freeTransfersCell = document.createElement("td");
    freeTransfersCell.textContent = typeof r.free_transfers === "number" ? String(r.free_transfers) : "-";
    tr.appendChild(freeTransfersCell);

    const teamIdCell = document.createElement("td");
    teamIdCell.textContent = r.team_id || "-";
    tr.appendChild(teamIdCell);

    const teamIdActionCell = document.createElement("td");
    const teamIdInput = document.createElement("input");
    teamIdInput.type = "text";
    teamIdInput.inputMode = "numeric";
    teamIdInput.placeholder = "team id";
    teamIdInput.value = r.team_id || "";
    teamIdInput.className = "admin-credit-input";
    const teamIdSaveBtn = document.createElement("button");
    teamIdSaveBtn.type = "button";
    teamIdSaveBtn.className = "link-btn";
    teamIdSaveBtn.textContent = "Set";
    teamIdSaveBtn.addEventListener("click", async () => {
      const newTeamId = teamIdInput.value.trim() || null;
      if (newTeamId !== null && !/^\d+$/.test(newTeamId)) {
        alert("Team ID must be numeric.");
        return;
      }
      teamIdSaveBtn.disabled = true;
      try {
        const res = await fetch("/api/admin/team-id", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: r.id, team_id: newTeamId }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || "Failed to update.");
        teamIdCell.textContent = newTeamId || "-";
        teamIdSaveBtn.textContent = "Saved";
        setTimeout(() => { teamIdSaveBtn.textContent = "Set"; }, 1500);
      } catch (err) {
        alert(err.message);
      } finally {
        teamIdSaveBtn.disabled = false;
      }
    });
    teamIdActionCell.appendChild(teamIdInput);
    teamIdActionCell.appendChild(teamIdSaveBtn);
    tr.appendChild(teamIdActionCell);

    const cells = [
      new Date(r.created_at).toLocaleDateString(),
      r.is_golden ? `🏆 until ${new Date(r.golden_until).toLocaleDateString()}` : "-",
      String(r.credits),
      String(r.credits_purchased),
      String(r.lifetime_credits_spent),
      fmtUsd(r.revenue_usd),
      fmtUsd(r.credit_value_usd),
      `${r.input_tokens.toLocaleString()} / ${r.output_tokens.toLocaleString()}`,
      String(r.call_count),
      fmtUsd(r.api_cost_usd),
      `${margin >= 0 ? "+" : ""}${fmtUsd(margin)}`,
    ];
    for (const text of cells) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }

    const actionTd = document.createElement("td");
    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.value = r.credits;
    input.className = "admin-credit-input";
    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "link-btn";
    saveBtn.textContent = "Set";
    saveBtn.addEventListener("click", async () => {
      const newCredits = parseInt(input.value, 10);
      if (Number.isNaN(newCredits) || newCredits < 0) return;
      saveBtn.disabled = true;
      try {
        const res = await fetch("/api/admin/credits", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: r.id, credits: newCredits }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || "Failed to update.");
        saveBtn.textContent = "Saved";
        setTimeout(() => { saveBtn.textContent = "Set"; }, 1500);
      } catch (err) {
        alert(err.message);
      } finally {
        saveBtn.disabled = false;
      }
    });
    actionTd.appendChild(input);
    actionTd.appendChild(saveBtn);
    tr.appendChild(actionTd);

    tableBodyEl.appendChild(tr);
  }
}

const promoCreateFormEl = document.getElementById("promo-create-form");
const promoCreditsInputEl = document.getElementById("promo-credits-input");
const promoCreateResultEl = document.getElementById("promo-create-result");
const promoTableBodyEl = document.getElementById("promo-table-body");

async function loadPromoCodes() {
  const res = await fetch("/api/admin/promo-codes");
  if (!res.ok) return;
  const codes = await res.json();
  promoTableBodyEl.innerHTML = "";
  for (const c of codes) {
    const tr = document.createElement("tr");
    const status = c.redeemed_at ? `Used by ${c.redeemed_by_email}` : "Unused";
    for (const text of [c.code, String(c.credits), new Date(c.created_at).toLocaleDateString(), status]) {
      const td = document.createElement("td");
      td.textContent = text;
      tr.appendChild(td);
    }

    const actionTd = document.createElement("td");
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "link-btn";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      if (!confirm(`Delete promo code ${c.code}? This can't be undone.`)) return;
      deleteBtn.disabled = true;
      try {
        const res = await fetch(`/api/admin/promo-codes/${encodeURIComponent(c.code)}`, { method: "DELETE" });
        if (!res.ok) throw new Error((await res.json()).detail || "Failed to delete.");
        tr.remove();
      } catch (err) {
        alert(err.message);
        deleteBtn.disabled = false;
      }
    });
    actionTd.appendChild(deleteBtn);
    tr.appendChild(actionTd);

    promoTableBodyEl.appendChild(tr);
  }
}

promoCreateFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const credits = parseInt(promoCreditsInputEl.value, 10);
  if (Number.isNaN(credits) || credits <= 0) return;
  try {
    const res = await fetch("/api/admin/promo-codes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credits }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to create code.");
    promoCreateResultEl.textContent = `Code created: ${data.code} (${data.credits} credits)`;
    loadPromoCodes();
  } catch (err) {
    promoCreateResultEl.textContent = `Error: ${err.message}`;
  }
});

function setMaintenanceUi(enabled) {
  maintenanceToggleBtnEl.textContent = enabled ? "Disable maintenance mode" : "Enable maintenance mode";
  maintenanceStatusEl.textContent = enabled ? "Maintenance mode is ON - chat and draft advice are paused." : "";
  maintenanceStatusEl.className = `admin-maintenance-status ${enabled ? "on" : ""}`;
}

async function loadMaintenanceMode() {
  try {
    const res = await fetch("/api/admin/maintenance");
    if (!res.ok) return;
    const data = await res.json();
    setMaintenanceUi(data.enabled);
  } catch {
    // best-effort - leave the button at its default label
  }
}

maintenanceToggleBtnEl.addEventListener("click", async () => {
  const enabling = maintenanceToggleBtnEl.textContent === "Enable maintenance mode";
  maintenanceToggleBtnEl.disabled = true;
  try {
    const res = await fetch("/api/admin/maintenance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: enabling }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to update.");
    setMaintenanceUi(data.enabled);
  } catch (err) {
    alert(err.message);
  } finally {
    maintenanceToggleBtnEl.disabled = false;
  }
});

loadAdminUsage();
loadPromoCodes();
loadMaintenanceMode();
