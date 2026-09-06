const referralCode = new URLSearchParams(location.search).get("ref");

const authSectionEl = document.getElementById("auth-section");
const appSectionEl = document.getElementById("app-section");
const tabLoginEl = document.getElementById("tab-login");
const tabSignupEl = document.getElementById("tab-signup");
const authFormEl = document.getElementById("auth-form");
const authEmailEl = document.getElementById("auth-email");
const authPasswordEl = document.getElementById("auth-password");
const authPasswordToggleEl = document.getElementById("auth-password-toggle");
const authTeamIdEl = document.getElementById("auth-team-id");
const authTeamIdHelpBtnEl = document.getElementById("auth-team-id-help-btn");
const authTeamIdHelpEl = document.getElementById("auth-team-id-help");
const authTeamPreviewEl = document.getElementById("auth-team-preview");
const authSubmitEl = document.getElementById("auth-submit");
const authAgreeRowEl = document.getElementById("auth-agree-row");
const authAgreeEl = document.getElementById("auth-agree");
const authErrorEl = document.getElementById("auth-error");

const accountEmailEl = document.getElementById("account-email");
const accountCreditsEl = document.getElementById("account-credits");
const buySmallEl = document.getElementById("buy-small");
const buyMediumEl = document.getElementById("buy-medium");
const buyLargeEl = document.getElementById("buy-large");
const buyGoldenEl = document.getElementById("buy-golden");
const goldenBadgeEl = document.getElementById("golden-badge");
const logoutBtnEl = document.getElementById("logout-btn");
const inviteBtnEl = document.getElementById("invite-btn");
const adminBtnEl = document.getElementById("admin-btn");
const promoFormEl = document.getElementById("promo-form");
const promoCodeInputEl = document.getElementById("promo-code-input");
const promoStatusEl = document.getElementById("promo-status");

const chatEl = document.getElementById("chat");
const suggestedQuestionsEl = document.getElementById("suggested-questions");
const formEl = document.getElementById("form");
const inputEl = document.getElementById("input");
const teamFormEl = document.getElementById("team-form");
const teamIdEl = document.getElementById("team-id");
const teamFormSaveBtnEl = document.getElementById("team-save-btn");
const teamStatusEl = document.getElementById("team-status");
const showFormationBtnEl = document.getElementById("show-formation-btn");
const squadSectionEl = document.getElementById("squad-section");
const squadPlaceholderEl = document.getElementById("squad-placeholder");
const squadContentEl = document.getElementById("squad-content");
const squadTeamNameEl = document.getElementById("squad-team-name");
const squadStatBadgesEl = document.getElementById("squad-stat-badges");
const squadMetaEl = document.getElementById("squad-meta");
const squadNoteEl = document.getElementById("squad-note");
const squadChipsEl = document.getElementById("squad-chips");
const pitchEl = document.getElementById("pitch");
const benchEl = document.getElementById("bench");
const gameweekBarEl = document.getElementById("gameweek-bar");
const colorModeSelectEl = document.getElementById("color-mode-select");
const squadViewToggleEl = document.getElementById("squad-view-toggle");
const squadViewLiveBtnEl = document.getElementById("squad-view-live-btn");
const squadViewNextBtnEl = document.getElementById("squad-view-next-btn");

const draftBtnEl = document.getElementById("draft-btn");
const draftToolbarEl = document.getElementById("draft-toolbar");
const draftBudgetEl = document.getElementById("draft-budget");
const draftTransferCostEl = document.getElementById("draft-transfer-cost");
const draftAdviceBtnEl = document.getElementById("draft-advice-btn");
const draftFreeTransfersEl = document.getElementById("draft-free-transfers");
const draftChipSelectEl = document.getElementById("draft-chip-select");
const draftPreviewEl = document.getElementById("draft-preview");
const draftPreviewSummaryEl = document.getElementById("draft-preview-summary");
const draftPreviewCostEl = document.getElementById("draft-preview-cost");
const draftPreviewPitchEl = document.getElementById("draft-preview-pitch");
const draftPreviewBenchEl = document.getElementById("draft-preview-bench");
const draftApplyBtnEl = document.getElementById("draft-apply-btn");
const draftPreviewCloseEl = document.getElementById("draft-preview-close");
const draftSaveBtnEl = document.getElementById("draft-save-btn");
const draftCancelBtnEl = document.getElementById("draft-cancel-btn");
const draftSearchPanelEl = document.getElementById("draft-search-panel");
const draftSearchTitleEl = document.getElementById("draft-search-title");
const draftSearchInputEl = document.getElementById("draft-search-input");
const draftSearchResultsEl = document.getElementById("draft-search-results");
const draftSearchCloseEl = document.getElementById("draft-search-close");

const pointsBreakdownPopoverEl = document.getElementById("points-breakdown-popover");
const pointsBreakdownTitleEl = document.getElementById("points-breakdown-title");
const pointsBreakdownBodyEl = document.getElementById("points-breakdown-body");
const pointsBreakdownCloseEl = document.getElementById("points-breakdown-close");

function hidePointsBreakdown() {
  pointsBreakdownPopoverEl.hidden = true;
}

function showPointsBreakdown(anchorEl, p) {
  pointsBreakdownTitleEl.textContent = `${p.name} - GW points`;
  pointsBreakdownBodyEl.innerHTML = "";
  for (const stat of p.gw_points_breakdown) {
    const row = document.createElement("div");
    row.className = "points-breakdown-row";
    const label = document.createElement("span");
    label.textContent = stat.value > 1 || stat.label === "Minutes played" ? `${stat.label} (${stat.value})` : stat.label;
    const value = document.createElement("span");
    value.className = `points-breakdown-value ${stat.points < 0 ? "negative" : ""}`;
    value.textContent = `${stat.points >= 0 ? "+" : ""}${stat.points}`;
    row.appendChild(label);
    row.appendChild(value);
    pointsBreakdownBodyEl.appendChild(row);
  }
  if (p.multiplier > 1) {
    const row = document.createElement("div");
    row.className = "points-breakdown-row points-breakdown-total";
    const label = document.createElement("span");
    label.textContent = `${p.multiplier === 3 ? "Triple captain" : "Captain"} ×${p.multiplier}`;
    const value = document.createElement("span");
    value.textContent = `${p.gw_points} → ${p.gw_points_scored}`;
    row.appendChild(label);
    row.appendChild(value);
    pointsBreakdownBodyEl.appendChild(row);
  } else {
    const row = document.createElement("div");
    row.className = "points-breakdown-row points-breakdown-total";
    const label = document.createElement("span");
    label.textContent = "Total";
    const value = document.createElement("span");
    // Bench players carry multiplier 0, so gw_points_scored (raw * multiplier)
    // is always 0 regardless of how they're actually doing live - show the
    // player's real live score (gw_points) instead for anyone not starting.
    value.textContent = `${p.multiplier > 0 ? p.gw_points_scored : p.gw_points}`;
    row.appendChild(label);
    row.appendChild(value);
    pointsBreakdownBodyEl.appendChild(row);
  }

  pointsBreakdownPopoverEl.hidden = false;
  const rect = anchorEl.getBoundingClientRect();
  const popRect = pointsBreakdownPopoverEl.getBoundingClientRect();
  let left = rect.left + window.scrollX;
  let top = rect.bottom + window.scrollY + 6;
  if (left + popRect.width > window.scrollX + document.documentElement.clientWidth - 8) {
    left = window.scrollX + document.documentElement.clientWidth - popRect.width - 8;
  }
  pointsBreakdownPopoverEl.style.left = `${Math.max(8, left)}px`;
  pointsBreakdownPopoverEl.style.top = `${top}px`;
}

pointsBreakdownCloseEl.addEventListener("click", hidePointsBreakdown);
document.addEventListener("click", (e) => {
  if (!pointsBreakdownPopoverEl.hidden && !pointsBreakdownPopoverEl.contains(e.target)) {
    hidePointsBreakdown();
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") hidePointsBreakdown();
});

const history = [];
let authMode = "login"; // "login" | "signup"

function loadTeamId() {
  try {
    return localStorage.getItem("fplTeamId") || "";
  } catch {
    return "";
  }
}

teamIdEl.value = loadTeamId();

teamFormEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const value = teamIdEl.value.trim();
  try {
    if (value) {
      localStorage.setItem("fplTeamId", value);
    } else {
      localStorage.removeItem("fplTeamId");
    }
  } catch {
    // localStorage unavailable (private browsing, blocked site data) - ignore
  }
  teamStatusEl.textContent = "Saved";
  setTimeout(() => { teamStatusEl.textContent = ""; }, 2000);
  loadSquad();
});

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

function parseAdviceTags(text) {
  const re = /\{\{player:([^:}]+):([A-Z]+):(buy|sell|captain)\}\}/g;
  const tags = [];
  let match;
  while ((match = re.exec(text)) !== null) {
    tags.push({ name: match[1], position: match[2], action: match[3] });
  }
  return tags;
}

// Turns the raw {{player:...}} tags in a reply into distinct, user-selectable
// changes: a sell+buy pair in the same reply is one "transfer" (both sides
// resolved together), a lone sell opens the search overlay for the user to
// pick their own replacement, a lone buy can't be auto-applied (no player to
// drop is known) so it's shown but disabled, and each captain tag is its own
// directly-applicable change.
function buildAdviceChangeItems(tags) {
  const items = [];
  const sells = tags.filter((t) => t.action === "sell");
  const buys = tags.filter((t) => t.action === "buy");
  const captains = tags.filter((t) => t.action === "captain");
  const usedBuys = new Set();

  for (const sell of sells) {
    const buy = buys.find((b) => !usedBuys.has(b));
    if (buy) {
      usedBuys.add(buy);
      items.push({ type: "transfer", label: `Sell ${sell.name} → Buy ${buy.name}`, sell, buy });
    } else {
      items.push({ type: "sell-only", label: `Sell ${sell.name} (you'll pick the replacement)`, sell });
    }
  }
  for (const buy of buys) {
    if (usedBuys.has(buy)) continue;
    items.push({
      type: "buy-only",
      label: `Buy ${buy.name} (can't auto-apply - no player to drop was specified)`,
      disabled: true,
    });
  }
  for (const captain of captains) {
    items.push({ type: "captain", label: `Captain ${captain.name}`, captain });
  }
  return items;
}

function addAdviceFollowUp(replyText) {
  const items = buildAdviceChangeItems(parseAdviceTags(replyText));

  const div = document.createElement("div");
  div.className = "msg assistant advice-followup";

  const reminder = document.createElement("p");
  reminder.className = "advice-followup-reminder";
  reminder.textContent =
    "Remember: this won't change your real team - make any transfers or " +
    "captain/lineup changes yourself on the official FPL app.";
  div.appendChild(reminder);

  const checkboxRefs = [];
  if (items.length) {
    const list = document.createElement("div");
    list.className = "advice-followup-choices";
    for (const item of items) {
      const label = document.createElement("label");
      label.className = "advice-followup-choice";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = !item.disabled;
      checkbox.disabled = !!item.disabled;
      label.appendChild(checkbox);
      const span = document.createElement("span");
      span.textContent = item.label;
      label.appendChild(span);
      list.appendChild(label);
      checkboxRefs.push({ checkbox, item });
    }
    div.appendChild(list);
  }

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "advice-followup-btn";
  btn.textContent = items.length ? "Apply selected & open draft" : "Show in draft formation";
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    // If a draft is already open (from a manual edit or an earlier chat
    // question this session), keep building on it instead of reloading from
    // the server and silently discarding those unsaved changes.
    if (!draftMode) {
      await enterDraftMode();
      if (!draftMode) {
        btn.disabled = false;
        return;
      }
    }

    let openedSearchForSell = false;
    for (const { checkbox, item } of checkboxRefs) {
      if (!checkbox.checked) continue;

      if (item.type === "captain") {
        const player = draftSquad.find((p) => p.name.toLowerCase() === item.captain.name.toLowerCase());
        if (player) {
          // The captain must be a starter - draftMakeCaptain silently skips
          // anyone benched, so swap them into the XI first (same position,
          // to keep the formation legal) if that's where they currently are.
          if (player.multiplier === 0) {
            const starterSamePosition = draftSquad.find(
              (p) => p.position === player.position && p.multiplier > 0
            );
            if (starterSamePosition) draftPerformSwap(player.element, starterSamePosition.element);
          }
          draftMakeCaptain(player.element);
        }
      } else if (item.type === "transfer") {
        const sellPlayer = draftSquad.find((p) => p.name.toLowerCase() === item.sell.name.toLowerCase());
        if (sellPlayer) {
          try {
            const res = await fetch(
              `/api/players/search?q=${encodeURIComponent(item.buy.name)}` +
              `&position=${encodeURIComponent(item.buy.position)}`
            );
            const data = await res.json();
            const bestMatch = (data.players || [])[0];
            if (bestMatch) {
              draftTransferElement = sellPlayer.element;
              draftApplyTransfer(bestMatch);
            }
          } catch {
            // best-effort - leave this one for the user to apply manually
          }
        }
      } else if (item.type === "sell-only" && !openedSearchForSell) {
        const sellPlayer = draftSquad.find((p) => p.name.toLowerCase() === item.sell.name.toLowerCase());
        if (sellPlayer) {
          draftOpenTransfer(sellPlayer.element);
          openedSearchForSell = true;
        }
      }
    }
    squadSectionEl.scrollIntoView({ behavior: "smooth", block: "start" });
    div.remove();
  });
  div.appendChild(btn);

  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

function addPendingMessage(text) {
  const div = document.createElement("div");
  div.className = "msg assistant pending";
  const label = document.createElement("span");
  label.textContent = text;
  const dots = document.createElement("span");
  dots.className = "typing-dots";
  dots.innerHTML = "<span></span><span></span><span></span>";
  div.appendChild(label);
  div.appendChild(dots);
  chatEl.appendChild(div);
  chatEl.scrollTop = chatEl.scrollHeight;
  return div;
}

const PLAYER_TAG_RE = /\{\{player:([^:}]+):([A-Z]+):(buy|sell|captain)\}\}/g;

function playerChip(name, position, action) {
  const chip = document.createElement("span");
  chip.className = "chat-player-chip";

  const shirt = document.createElement("span");
  shirt.className = `shirt mini-shirt pos-${position}`;
  shirt.innerHTML = jerseySvgMarkup(16, 15).svg;
  chip.appendChild(shirt);

  const label = document.createElement("span");
  label.className = "chat-player-name";
  label.textContent = name;
  chip.appendChild(label);

  if (action === "captain") {
    const badge = document.createElement("span");
    badge.className = "chat-player-captain-badge";
    badge.textContent = "C";
    chip.appendChild(badge);
  } else {
    const arrow = document.createElement("span");
    arrow.className = `chat-player-arrow ${action}`;
    arrow.textContent = action === "sell" ? "▼" : "▲";
    chip.appendChild(arrow);
  }

  return chip;
}

// Renders Claude's reply text into `container`, turning any
// {{player:Name:POS:sell|buy}} tags into inline jersey+arrow chips. Only
// ever inserts model text as text nodes (never innerHTML), so it's safe
// regardless of what the model outputs.
function renderAssistantText(container, text) {
  container.textContent = "";
  let lastIndex = 0;
  let match;
  PLAYER_TAG_RE.lastIndex = 0;
  while ((match = PLAYER_TAG_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      container.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
    }
    const [, name, position, action] = match;
    container.appendChild(playerChip(name, position, action));
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    container.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

function setAuthMode(mode) {
  authMode = mode;
  tabLoginEl.classList.toggle("active", mode === "login");
  tabSignupEl.classList.toggle("active", mode === "signup");
  authSubmitEl.textContent = mode === "login" ? "Log in" : "Sign up";
  authPasswordEl.autocomplete = mode === "login" ? "current-password" : "new-password";
  authTeamIdEl.hidden = mode !== "signup";
  authTeamIdEl.required = mode === "signup";
  authTeamIdHelpBtnEl.hidden = mode !== "signup";
  authTeamIdHelpEl.hidden = true;
  authAgreeRowEl.hidden = mode !== "signup";
  authAgreeEl.checked = false;
  authErrorEl.textContent = "";
  authTeamPreviewEl.hidden = true;
  authTeamPreviewEl.textContent = "";
}

authTeamIdHelpBtnEl.addEventListener("click", () => {
  authTeamIdHelpEl.hidden = !authTeamIdHelpEl.hidden;
});

let teamPreviewDebounce = null;

authTeamIdEl.addEventListener("input", () => {
  clearTimeout(teamPreviewDebounce);
  const teamId = authTeamIdEl.value.trim();
  if (!teamId) {
    authTeamPreviewEl.hidden = true;
    return;
  }
  teamPreviewDebounce = setTimeout(async () => {
    try {
      const res = await fetch(`/api/team-preview?team_id=${encodeURIComponent(teamId)}`);
      if (!res.ok) {
        authTeamPreviewEl.textContent = "Couldn't find a team with that ID - double-check it.";
        authTeamPreviewEl.className = "auth-team-preview auth-team-preview-error";
        authTeamPreviewEl.hidden = false;
        return;
      }
      const data = await res.json();
      authTeamPreviewEl.textContent =
        `Is this you? ${data.team_name || "Unnamed team"}` +
        (data.manager_name ? ` (${data.manager_name})` : "");
      authTeamPreviewEl.className = "auth-team-preview auth-team-preview-ok";
      authTeamPreviewEl.hidden = false;
    } catch {
      authTeamPreviewEl.hidden = true;
    }
  }, 500);
});

tabLoginEl.addEventListener("click", () => setAuthMode("login"));
tabSignupEl.addEventListener("click", () => setAuthMode("signup"));

authPasswordToggleEl.addEventListener("click", () => {
  const showing = authPasswordEl.type === "text";
  authPasswordEl.type = showing ? "password" : "text";
  authPasswordToggleEl.setAttribute("aria-label", showing ? "Show password" : "Hide password");
  authPasswordToggleEl.classList.toggle("password-toggle-active", !showing);
});

let currentUserId = null;
let currentUserIsAdmin = false;

function showApp(account) {
  authSectionEl.hidden = true;
  appSectionEl.hidden = false;
  currentUserId = account.id;
  currentUserIsAdmin = !!account.is_admin;
  accountEmailEl.textContent = account.email;
  adminBtnEl.hidden = !currentUserIsAdmin;
  setCredits(account.credits);
  setGoldenBadge(account.is_golden, account.golden_until);

  // Non-admin accounts are locked to their own registered FPL team - the
  // backend rejects lookups for any other team_id, so the field is read-only
  // and always reflects the account's team rather than implying it's free-form.
  // Admins can still browse any team (matches the backend's admin bypass).
  if (currentUserIsAdmin) {
    if (account.team_id && !loadTeamId()) {
      try {
        localStorage.setItem("fplTeamId", account.team_id);
      } catch {
        // localStorage unavailable - ignore
      }
    }
    teamIdEl.value = loadTeamId() || account.team_id || "";
    teamIdEl.readOnly = false;
    teamFormSaveBtnEl.hidden = false;
  } else {
    teamIdEl.value = account.team_id || "";
    teamIdEl.readOnly = true;
    teamFormSaveBtnEl.hidden = true;
    try {
      localStorage.setItem("fplTeamId", account.team_id || "");
    } catch {
      // localStorage unavailable - ignore
    }
  }

  loadSquad();
  renderSuggestedQuestions();
}

const SUGGESTED_QUESTIONS = [
  "Who should I captain this gameweek?",
  "Any injury news for my squad?",
  "Should I use my Wildcard now?",
  "Who's my best transfer target?",
  "Is my bench order OK?",
];

function renderSuggestedQuestions() {
  if (history.length > 0) return;
  suggestedQuestionsEl.innerHTML = "";
  for (const question of SUGGESTED_QUESTIONS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "suggested-question-btn";
    btn.textContent = question;
    btn.addEventListener("click", () => {
      inputEl.value = question;
      formEl.requestSubmit();
    });
    suggestedQuestionsEl.appendChild(btn);
  }
}

function setGoldenBadge(isGolden, goldenUntil) {
  document.body.classList.toggle("golden-active", !!isGolden);
  if (!isGolden) {
    goldenBadgeEl.hidden = true;
    return;
  }
  goldenBadgeEl.hidden = false;
  const until = goldenUntil ? new Date(goldenUntil).toLocaleDateString() : "";
  goldenBadgeEl.textContent = `🏆 Golden Boot${until ? ` until ${until}` : ""}`;
}

function showAuth() {
  authSectionEl.hidden = false;
  appSectionEl.hidden = true;
}

function setCredits(credits) {
  accountCreditsEl.textContent = currentUserIsAdmin
    ? "Admin (unlimited)"
    : `🪙 ${credits} credit${credits === 1 ? "" : "s"}`;
}

async function checkAuth() {
  try {
    const res = await fetch("/api/me");
    if (res.ok) {
      showApp(await res.json());
    } else {
      showAuth();
    }
  } catch {
    showAuth();
  }
}

authFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  requestNotificationPermission(); // tied to this click so the browser will actually prompt
  authErrorEl.textContent = "";

  if (authMode === "signup" && !authAgreeEl.checked) {
    authErrorEl.textContent = "Please confirm you understand the advice disclaimer to sign up.";
    return;
  }

  const teamId = authTeamIdEl.value.trim();
  if (authMode === "signup" && !/^\d+$/.test(teamId)) {
    authErrorEl.textContent = "Please enter your numeric FPL Team ID to sign up.";
    return;
  }

  const email = authEmailEl.value.trim();
  const password = authPasswordEl.value;
  const payload =
    authMode === "signup" ? { email, password, team_id: teamId, ref: referralCode } : { email, password };

  try {
    const res = await fetch(`/api/${authMode === "login" ? "login" : "signup"}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }
    authPasswordEl.value = "";
    showApp(data);
  } catch (err) {
    authErrorEl.textContent = err.message;
  }
});

logoutBtnEl.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" });
  history.length = 0;
  chatEl.innerHTML = "";
  showAuth();
});

inviteBtnEl.addEventListener("click", async () => {
  if (!currentUserId) return;
  const link = `${location.origin}/?ref=${currentUserId}`;
  try {
    await navigator.clipboard.writeText(link);
    const original = inviteBtnEl.textContent;
    inviteBtnEl.textContent = "Link copied!";
    setTimeout(() => { inviteBtnEl.textContent = original; }, 2000);
  } catch {
    prompt("Copy your invite link:", link);
  }
});

promoFormEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const code = promoCodeInputEl.value.trim();
  if (!code) return;
  promoStatusEl.textContent = "";
  try {
    const res = await fetch("/api/redeem-promo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not redeem code.");
    promoCodeInputEl.value = "";
    promoStatusEl.textContent = `+${data.credits_added} credits added!`;
    promoStatusEl.className = "promo-status promo-status-success";
    setCredits(data.credits);
  } catch (err) {
    promoStatusEl.textContent = err.message;
    promoStatusEl.className = "promo-status promo-status-error";
  }
});

// ---------------------------------------------------------------------------
// Billing
// ---------------------------------------------------------------------------

async function goToCheckout(pack) {
  try {
    const res = await fetch("/api/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pack }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not start checkout.");
    window.location.href = data.url;
  } catch (err) {
    alert(err.message);
  }
}

buySmallEl.addEventListener("click", () => goToCheckout("small"));
buyMediumEl.addEventListener("click", () => goToCheckout("medium"));
buyLargeEl.addEventListener("click", () => goToCheckout("large"));
buyGoldenEl.addEventListener("click", () => goToCheckout("golden"));

// ---------------------------------------------------------------------------
// Formation / squad pitch view
// ---------------------------------------------------------------------------

// Kit identity by club short code - general public knowledge of each club's
// colors, not any club's actual crest/kit artwork. `secondary` renders as a
// contrast sleeve color; `pattern: "stripes"` renders primary/secondary as
// body stripes instead, for clubs whose identity actually is stripes - this
// pairing (plus stripes) is what keeps otherwise similar reds/blues/whites
// (e.g. ARS vs LIV vs NFO, or FUL vs LEE vs TOT) visually distinct.
const TEAM_KITS = {
  ARS: { primary: "#EF0107", secondary: "#FFFFFF" },
  AVL: { primary: "#670E36", secondary: "#9CC7EA" },
  BOU: { primary: "#DA020E", secondary: "#000000", pattern: "stripes" },
  BRE: { primary: "#E30613", secondary: "#FFFFFF", pattern: "stripes" },
  BHA: { primary: "#0057B8", secondary: "#FFFFFF", pattern: "stripes" },
  BUR: { primary: "#6C1D45", secondary: "#5CB8E4" },
  CHE: { primary: "#034694", secondary: "#FFFFFF" },
  CRY: { primary: "#1B458F", secondary: "#C4122E", pattern: "stripes" },
  EVE: { primary: "#003399", secondary: "#FFFFFF" },
  FUL: { primary: "#FFFFFF", secondary: "#000000" },
  HUL: { primary: "#F18A00", secondary: "#000000", pattern: "stripes" },
  IPS: { primary: "#0044A9", secondary: "#FFFFFF" },
  LEE: { primary: "#FFFFFF", secondary: "#FFD200" },
  LEI: { primary: "#003090", secondary: "#FDBE11" },
  LIV: { primary: "#C8102E", secondary: "#00B2A9" },
  MCI: { primary: "#6CABDD", secondary: "#1C2C5B" },
  MUN: { primary: "#DA291C", secondary: "#000000" },
  NEW: { primary: "#241F20", secondary: "#FFFFFF", pattern: "stripes" },
  NFO: { primary: "#DD0000", secondary: "#FFFFFF" },
  SOU: { primary: "#D71920", secondary: "#FFFFFF", pattern: "stripes" },
  SUN: { primary: "#EB172F", secondary: "#FFFFFF", pattern: "stripes" },
  TOT: { primary: "#FFFFFF", secondary: "#132257" },
  WHU: { primary: "#7A263A", secondary: "#1BB1E7" },
  WOL: { primary: "#FDB913", secondary: "#231F20" },
  COV: { primary: "#78B9E7", secondary: "#0C1C8C" },
  MID: { primary: "#DC1414" },
  WBA: { primary: "#122F67", secondary: "#FFFFFF", pattern: "stripes" },
  SHU: { primary: "#EE2737", secondary: "#FFFFFF", pattern: "stripes" },
  LUT: { primary: "#F36C21", secondary: "#002D62" },
  NOR: { primary: "#FFF200", secondary: "#00A650" },
};

function getColorMode() {
  try {
    return localStorage.getItem("fplColorMode") || "position";
  } catch {
    return "position";
  }
}

const SHIRT_BODY_PATH = "M16,3 Q24,9 32,3 L36,8 L43,12 L38,20 L34,16 L34,42 L14,42 L14,16 L10,20 L5,12 L12,8 Z";
// The two sleeve panels are sub-regions of SHIRT_BODY_PATH's own outline
// (shoulder -> cuff -> underarm -> back to the torso edge) - overlaying them
// in a second color can't leak outside the shirt silhouette.
const SHIRT_SLEEVE_RIGHT_PATH = "M32,3 L36,8 L43,12 L38,20 L34,16 Z";
const SHIRT_SLEEVE_LEFT_PATH = "M16,3 L12,8 L5,12 L10,20 L14,16 Z";
let _jerseyPatternCounter = 0;

// Builds the shirt SVG and returns the body fill to apply via the --shirt-fill
// CSS var (a solid color, an id'd <pattern> reference for a striped kit, or
// undefined to leave the caller's default/position-based fill alone).
function jerseySvgMarkup(width, height, kit) {
  let defs = "";
  let sleeves = "";
  let fill;
  if (kit && kit.pattern === "stripes" && kit.secondary) {
    const patternId = `stripe-${_jerseyPatternCounter++}`;
    defs =
      `<defs><pattern id="${patternId}" width="7" height="44" patternUnits="userSpaceOnUse">` +
      `<rect width="7" height="44" fill="${kit.primary}" />` +
      `<rect width="3.5" height="44" fill="${kit.secondary}" />` +
      "</pattern></defs>";
    fill = `url(#${patternId})`;
  } else if (kit) {
    fill = kit.primary;
    if (kit.secondary) {
      sleeves =
        `<path class="shirt-sleeve" fill="${kit.secondary}" d="${SHIRT_SLEEVE_RIGHT_PATH}" />` +
        `<path class="shirt-sleeve" fill="${kit.secondary}" d="${SHIRT_SLEEVE_LEFT_PATH}" />`;
    }
  }
  const svg =
    `<svg class="shirt-svg" viewBox="0 0 48 44" width="${width}" height="${height}">` +
    defs +
    `<path class="shirt-body" d="${SHIRT_BODY_PATH}" />` +
    sleeves +
    '<path class="shirt-sheen" d="M12,8 L16,3 Q24,9 32,3 L36,8 L30,12 Q24,15 18,12 Z" />' +
    '<path class="shirt-collar" d="M16,3 Q24,9 32,3" />' +
    "</svg>";
  return { svg, fill };
}

function playerCard(p, editControls) {
  const card = document.createElement("div");
  card.className = "player-card";

  const shirt = document.createElement("div");
  shirt.className = `shirt pos-${p.position}`;
  if (getColorMode() === "club") {
    shirt.classList.add("club-mode");
    const { svg, fill } = jerseySvgMarkup(40, 38, TEAM_KITS[p.team_short]);
    shirt.style.setProperty("--shirt-fill", fill || "#888888");
    shirt.innerHTML = svg;
  } else {
    shirt.innerHTML = jerseySvgMarkup(40, 38).svg;
  }
  card.appendChild(shirt);

  if (p.is_captain || p.is_vice_captain) {
    const badge = document.createElement("span");
    badge.className = "captain-badge";
    badge.textContent = p.is_captain ? "C" : "V";
    card.appendChild(badge);
  }

  if (p.status && p.status !== "a") {
    const badge = document.createElement("span");
    const severity = p.status === "d" ? "doubtful" : "unavailable";
    badge.className = `status-icon ${severity}`;
    const labels = { d: "Doubtful", i: "Injured", s: "Suspended", u: "Unavailable" };
    let title = labels[p.status] || "Status unknown";
    if (p.status === "d" && typeof p.chance_of_playing_next_round === "number") {
      title += ` - ${p.chance_of_playing_next_round}% chance of playing`;
    }
    if (p.news) title += `: ${p.news}`;
    badge.title = title;
    badge.innerHTML =
      '<svg viewBox="0 0 24 24" width="15" height="15">' +
      '<path d="M9,1 L15,1 Q16,1 16,2 L16,9 L23,9 Q24,9 24,10 L24,14 Q24,15 23,15 L16,15 L16,22 Q16,23 15,23 L9,23 Q8,23 8,22 L8,15 L1,15 Q0,15 0,14 L0,10 Q0,9 1,9 L8,9 L8,2 Q8,1 9,1 Z" />' +
      "</svg>";
    card.appendChild(badge);
  }

  if (typeof p.gw_points_scored === "number") {
    // Bench players carry multiplier 0, so gw_points_scored (raw * multiplier)
    // is always 0 regardless of how they're actually doing live - show the
    // player's real live score (gw_points) instead for anyone not starting.
    const displayPoints = p.multiplier > 0 ? p.gw_points_scored : p.gw_points;
    const pts = document.createElement("span");
    pts.className = "player-points";
    const statusClass =
      p.fixture_status === "finished" ? "status-finished" : p.fixture_status === "live" ? "status-live" : "status-not-started";
    pts.classList.add(statusClass);
    pts.textContent = `${displayPoints}`;
    const statusLabel =
      p.fixture_status === "finished" ? "Match ended" : p.fixture_status === "live" ? "Match live" : "Not started yet";
    pts.title =
      (p.multiplier > 1
        ? `${p.gw_points} pts × ${p.multiplier} (captain) = ${p.gw_points_scored}`
        : `${displayPoints} pts this gameweek`) + ` · ${statusLabel}`;
    if (p.gw_points_breakdown && p.gw_points_breakdown.length) {
      pts.classList.add("has-breakdown");
      pts.addEventListener("click", (e) => {
        e.stopPropagation();
        showPointsBreakdown(pts, p);
      });
    }
    card.appendChild(pts);
  }

  const name = document.createElement("div");
  name.className = "player-name";
  name.textContent = p.name;
  if (p.team_short) {
    const team = document.createElement("span");
    team.className = "player-team";
    team.textContent = ` ${p.team_short}`;
    name.appendChild(team);
  }
  card.appendChild(name);

  if (p.next_fixture) {
    const fixture = document.createElement("div");
    fixture.className = "player-fixture";
    fixture.textContent = p.next_fixture;
    card.appendChild(fixture);
  }

  if (typeof p.price_m === "number") {
    const price = document.createElement("div");
    let trend = "unchanged";
    if (p.price_change_m > 0) trend = "risen";
    else if (p.price_change_m < 0) trend = "fallen";
    price.className = `player-price ${trend}`;
    price.textContent = `£${p.price_m.toFixed(1)}m`;
    if (trend !== "unchanged") {
      price.title = `${trend === "risen" ? "Up" : "Down"} £${Math.abs(p.price_change_m).toFixed(1)}m since season start`;
    }
    card.appendChild(price);
  }

  if (editControls) {
    const controls = document.createElement("div");
    controls.className = "draft-controls";

    if (editControls.isStarter) {
      const cBtn = document.createElement("button");
      cBtn.type = "button";
      cBtn.className = `draft-control-btn ${p.is_captain ? "active" : ""}`;
      cBtn.textContent = "C";
      cBtn.title = "Make captain";
      cBtn.addEventListener("click", () => editControls.onCaptain(p.element));
      controls.appendChild(cBtn);

      const vBtn = document.createElement("button");
      vBtn.type = "button";
      vBtn.className = `draft-control-btn ${p.is_vice_captain ? "active" : ""}`;
      vBtn.textContent = "V";
      vBtn.title = "Make vice-captain";
      vBtn.addEventListener("click", () => editControls.onVice(p.element));
      controls.appendChild(vBtn);
    } else {
      const startBtn = document.createElement("button");
      startBtn.type = "button";
      startBtn.className = `draft-control-btn ${editControls.isSelected ? "active" : ""}`;
      startBtn.textContent = editControls.isSelected ? "✕" : "↑";
      startBtn.title = editControls.isSelected ? "Cancel substitution" : "Substitute in";
      startBtn.addEventListener("click", () => editControls.onSwap(p.element));
      controls.appendChild(startBtn);
    }

    const tBtn = document.createElement("button");
    tBtn.type = "button";
    tBtn.className = "draft-control-btn transfer";
    tBtn.textContent = "⇄";
    tBtn.title = "Transfer out";
    tBtn.addEventListener("click", () => editControls.onTransfer(p.element));
    controls.appendChild(tBtn);

    card.appendChild(controls);
  }

  return card;
}

let currentSquadGameweek = null;
let lastSquadData = null;

function renderSquad(data) {
  currentSquadGameweek = data.gameweek;
  lastSquadData = data;

  squadTeamNameEl.textContent = `${data.team_name} (${data.manager_name})`;
  // Weighted by multiplier (FPL already sets this correctly per pick), so a
  // captain's fixture counts as 2 "slots" (3 if Triple Captain is active) and
  // bench players only count when Bench Boost is active (multiplier 1
  // instead of 0) - not a flat headcount.
  const totalSlots = data.squad.reduce((sum, p) => sum + (p.multiplier || 0), 0);
  const remainingSlots = data.squad.reduce(
    (sum, p) => sum + (p.fixture_status !== "finished" ? p.multiplier || 0 : 0),
    0
  );
  squadStatBadgesEl.innerHTML = `
    <div class="squad-stat-badge live">
      <span class="squad-stat-value">${data.gameweek_points}</span>
      <span class="squad-stat-label">GW${data.gameweek} pts (live)</span>
    </div>
    <div class="squad-stat-badge live">
      <span class="squad-stat-value">${data.overall_points}</span>
      <span class="squad-stat-label">Overall pts (live)</span>
    </div>
    <div class="squad-stat-badge" title="Weighted by multiplier - your captain counts double (triple with Triple Captain), and bench players only count while Bench Boost is active.">
      <span class="squad-stat-value">${remainingSlots}/${totalSlots}</span>
      <span class="squad-stat-label">Still to play</span>
    </div>`;
  squadMetaEl.innerHTML =
    `Rank: ${data.overall_rank?.toLocaleString() ?? "-"}` +
    `<br>Squad value: £${data.squad_value_m?.toFixed(1)}m · Bank: £${data.bank_m?.toFixed(1)}m · Total budget: £${data.total_budget_m?.toFixed(1)}m`;
  squadNoteEl.textContent =
    `Showing your GW${data.gameweek} squad - this rolls over to GW${data.gameweek + 1} unless you've ` +
    `made transfers on the official FPL site since then (FPL doesn't expose a team's picks before its deadline).`;

  squadChipsEl.innerHTML = "";
  for (const chip of data.chips || []) {
    const pill = document.createElement("span");
    pill.className = `chip-pill ${chip.used ? "used" : "unused"}`;
    pill.textContent = chip.used ? `${chip.name}: Used (GW${chip.used_gameweek})` : `${chip.name}: Available`;
    squadChipsEl.appendChild(pill);
  }
  if (data.active_chip) {
    const active = document.createElement("span");
    active.className = "chip-pill active";
    const activeName = (data.chips || []).find((c) => c.key === data.active_chip)?.name || data.active_chip;
    active.textContent = `${activeName} active this gameweek`;
    squadChipsEl.appendChild(active);
  }

  const starters = data.squad.filter((p) => p.multiplier > 0);
  const bench = data.squad.filter((p) => p.multiplier === 0);

  pitchEl.innerHTML = "";
  for (const pos of ["FWD", "MID", "DEF", "GKP"]) {
    const players = starters.filter((p) => p.position === pos);
    if (!players.length) continue;
    const row = document.createElement("div");
    row.className = "pitch-row";
    players.forEach((p) => row.appendChild(playerCard(p)));
    pitchEl.appendChild(row);
  }

  benchEl.innerHTML = "";
  bench.forEach((p) => benchEl.appendChild(playerCard(p)));

  squadPlaceholderEl.hidden = true;
  squadContentEl.hidden = false;
}

function showSquadPlaceholder(message) {
  squadContentEl.hidden = true;
  squadPlaceholderEl.hidden = false;
  squadPlaceholderEl.textContent = message;
}

let squadViewMode = "live"; // "live" | "next"

function setSquadViewMode(mode) {
  squadViewMode = mode;
  squadViewLiveBtnEl.classList.toggle("active", mode === "live");
  squadViewNextBtnEl.classList.toggle("active", mode === "next");
}

async function loadSquad() {
  const teamId = loadTeamId();
  if (!teamId) {
    showSquadPlaceholder("Save your FPL Team ID above to see your formation.");
    return;
  }
  setSquadViewMode("live");
  showSquadPlaceholder("Loading your formation...");
  try {
    const res = await fetch(`/api/my-squad?team_id=${encodeURIComponent(teamId)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not load your squad.");
    renderSquad(data);
  } catch (err) {
    showSquadPlaceholder(err.message);
  }
}

function renderNextGwSquad(data) {
  squadStatBadgesEl.innerHTML = "";
  const freeTransfersText =
    typeof data.free_transfers === "number"
      ? ` · ${data.free_transfers} free transfer${data.free_transfers === 1 ? "" : "s"} available`
      : "";
  squadMetaEl.innerHTML =
    `Planning for GW${data.gameweek} - not yet played${freeTransfersText}` +
    `<br>Squad value: £${(data.total_budget_m - data.bank_m).toFixed(1)}m · Bank: £${data.bank_m?.toFixed(1)}m · Total budget: £${data.total_budget_m?.toFixed(1)}m`;
  squadNoteEl.textContent = data.saved
    ? `This is your saved plan for GW${data.gameweek} - not yet made on the official FPL site.`
    : `No changes planned yet for GW${data.gameweek} - showing your current squad carried forward. Click "Edit Draft" to plan transfers.`;

  squadChipsEl.innerHTML = "";
  for (const chip of data.chips || []) {
    const pill = document.createElement("span");
    pill.className = `chip-pill ${chip.used ? "used" : "unused"}`;
    pill.textContent = chip.used ? `${chip.name}: Used (GW${chip.used_gameweek})` : `${chip.name}: Available`;
    squadChipsEl.appendChild(pill);
  }

  const starters = data.squad.filter((p) => p.multiplier > 0);
  const bench = data.squad.filter((p) => p.multiplier === 0);

  pitchEl.innerHTML = "";
  for (const pos of ["FWD", "MID", "DEF", "GKP"]) {
    const players = starters.filter((p) => p.position === pos);
    if (!players.length) continue;
    const row = document.createElement("div");
    row.className = "pitch-row";
    players.forEach((p) => row.appendChild(playerCard(p)));
    pitchEl.appendChild(row);
  }

  benchEl.innerHTML = "";
  bench.forEach((p) => benchEl.appendChild(playerCard(p)));
}

async function loadNextGwSquad() {
  const teamId = loadTeamId();
  if (!teamId) return;
  squadContentEl.hidden = false;
  squadPlaceholderEl.hidden = true;
  squadStatBadgesEl.innerHTML = "";
  squadMetaEl.textContent = "Loading your next gameweek plan...";
  squadNoteEl.textContent = "";
  squadChipsEl.innerHTML = "";
  pitchEl.innerHTML = "";
  benchEl.innerHTML = "";
  try {
    const res = await fetch(`/api/draft?team_id=${encodeURIComponent(teamId)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not load your next gameweek plan.");
    renderNextGwSquad(data);
  } catch (err) {
    squadMetaEl.textContent = `Error: ${err.message}`;
  }
}

showFormationBtnEl.addEventListener("click", loadSquad);

squadViewLiveBtnEl.addEventListener("click", () => {
  if (squadViewMode === "live") return;
  setSquadViewMode("live");
  if (lastSquadData) renderSquad(lastSquadData);
  else loadSquad();
});

squadViewNextBtnEl.addEventListener("click", () => {
  if (squadViewMode === "next") return;
  setSquadViewMode("next");
  loadNextGwSquad();
});

// Live points update continuously while matches are played (backend refreshes
// its own cache every ~60s) - poll on the same cadence so the Live tab stays
// current without the user needing to hit "Refresh Formation". Silent: re-runs
// the same render used on load, no placeholder/flicker in between.
async function refreshLiveSquadIfVisible() {
  if (squadViewMode !== "live" || draftMode) return;
  const teamId = loadTeamId();
  if (!teamId) return;
  try {
    const res = await fetch(`/api/my-squad?team_id=${encodeURIComponent(teamId)}`);
    if (!res.ok) return;
    const data = await res.json();
    renderSquad(data);
  } catch {
    // best-effort background refresh - a failed tick just tries again next time
  }
}
setInterval(refreshLiveSquadIfVisible, 60000);

// ---------------------------------------------------------------------------
// Draft formation editor
// ---------------------------------------------------------------------------

let draftMode = false;
let draftSquad = null;
let draftOriginalSquad = null;
let draftTotalBudget = null;
let draftBankM = null;
let draftTeamIdValue = null;
let draftGameweekValue = null;
let draftTransferElement = null;

function draftSquadValueM() {
  return draftSquad.reduce((sum, p) => sum + p.price_m, 0);
}

function updateDraftBudgetDisplay() {
  const squadValue = draftSquadValueM();
  const total = squadValue + draftBankM;
  const over = total > draftTotalBudget + 0.05;
  draftBudgetEl.textContent =
    `Squad £${squadValue.toFixed(1)}m + Bank £${draftBankM.toFixed(1)}m = £${total.toFixed(1)}m ` +
    `(limit £${draftTotalBudget.toFixed(1)}m)`;
  draftBudgetEl.className = `draft-budget ${over ? "over" : ""}`;
  draftSaveBtnEl.disabled = over;

  const changesCount = draftOriginalSquad
    ? draftSquad.filter((p) => !draftOriginalSquad.some((op) => op.element === p.element)).length
    : 0;
  const freeTransfers = parseInt(draftFreeTransfersEl.value, 10) || 0;
  const chip = draftChipSelectEl.value;
  const chipCoversCost = chip === "wildcard" || chip === "freehit";
  const hits = Math.max(0, changesCount - freeTransfers);
  const cost = chipCoversCost ? 0 : hits * 4;

  let transferText = `${changesCount} transfer${changesCount === 1 ? "" : "s"} made`;
  if (changesCount > 0) {
    if (chipCoversCost) {
      transferText += ` · free (${chip === "wildcard" ? "Wildcard" : "Free Hit"} covers it)`;
    } else if (cost > 0) {
      transferText += ` · ${freeTransfers} free available · costs -${cost} pts`;
    } else {
      transferText += ` · within your ${freeTransfers} free transfer${freeTransfers === 1 ? "" : "s"}`;
    }
  }
  draftTransferCostEl.textContent = transferText;
  draftTransferCostEl.className = `draft-transfer-cost ${cost > 0 ? "penalty" : ""}`;
}

const BENCH_POSITION_ORDER = { GKP: 0, DEF: 1, MID: 2, FWD: 3 };

let draftSubSelection = null; // element id of the bench player currently being placed, or null

function renderDraftPitch() {
  const starters = draftSquad.filter((p) => p.multiplier > 0);
  const bench = draftSquad
    .filter((p) => p.multiplier === 0)
    .sort((a, b) => BENCH_POSITION_ORDER[a.position] - BENCH_POSITION_ORDER[b.position]);

  pitchEl.innerHTML = "";
  for (const pos of ["FWD", "MID", "DEF", "GKP"]) {
    const players = starters.filter((p) => p.position === pos);
    if (!players.length) continue;
    const row = document.createElement("div");
    row.className = "pitch-row";
    players.forEach((p) => {
      const card = playerCard(p, {
        isStarter: true,
        onCaptain: draftMakeCaptain,
        onVice: draftMakeVice,
        onTransfer: draftOpenTransfer,
      });
      if (draftSubSelection && draftIsValidSubTarget(p)) {
        card.classList.add("sub-target");
        const arrow = document.createElement("button");
        arrow.type = "button";
        arrow.className = "draft-sub-arrow";
        arrow.textContent = "↓";
        arrow.title = "Swap in here";
        arrow.addEventListener("click", () => {
          draftPerformSwap(draftSubSelection, p.element);
          draftSubSelection = null;
          renderDraftPitch();
        });
        card.appendChild(arrow);
      }
      row.appendChild(card);
    });
    pitchEl.appendChild(row);
  }

  benchEl.innerHTML = "";
  bench.forEach((p) => {
    const card = playerCard(p, {
      isStarter: false,
      isSelected: p.element === draftSubSelection,
      onSwap: draftToggleSubSelection,
      onTransfer: draftOpenTransfer,
    });
    if (p.element === draftSubSelection) card.classList.add("sub-selected");
    benchEl.appendChild(card);
  });

  updateDraftBudgetDisplay();
}

function draftMakeCaptain(element) {
  for (const p of draftSquad) {
    if (p.multiplier === 0) continue;
    p.is_captain = p.element === element;
    if (p.is_captain) p.is_vice_captain = false;
  }
  renderDraftPitch();
}

function draftMakeVice(element) {
  for (const p of draftSquad) {
    if (p.multiplier === 0) continue;
    p.is_vice_captain = p.element === element;
    if (p.is_vice_captain) p.is_captain = false;
  }
  renderDraftPitch();
}

function draftPerformSwap(benchElement, starterElement) {
  const benchPlayer = draftSquad.find((p) => p.element === benchElement);
  const starter = draftSquad.find((p) => p.element === starterElement);
  if (!benchPlayer || !starter) return;
  const benchMultiplier = benchPlayer.multiplier;
  benchPlayer.multiplier = starter.multiplier;
  starter.multiplier = benchMultiplier;
  // a benched player can't stay captain/vice - clear and let the user reassign
  benchPlayer.is_captain = false;
  benchPlayer.is_vice_captain = false;
  starter.is_captain = false;
  starter.is_vice_captain = false;
  renderDraftPitch();
}

function draftFormationCounts(squad) {
  const starters = squad.filter((p) => p.multiplier > 0 && p.position !== "GKP");
  return {
    DEF: starters.filter((p) => p.position === "DEF").length,
    MID: starters.filter((p) => p.position === "MID").length,
    FWD: starters.filter((p) => p.position === "FWD").length,
  };
}

function isValidFormation(counts) {
  return counts.DEF >= 3 && counts.DEF <= 5 && counts.MID >= 2 && counts.MID <= 5 && counts.FWD >= 1 && counts.FWD <= 3;
}

function draftToggleSubSelection(benchElement) {
  draftSubSelection = draftSubSelection === benchElement ? null : benchElement;
  renderDraftPitch();
}

function draftIsValidSubTarget(starter) {
  const benchPlayer = draftSquad.find((p) => p.element === draftSubSelection);
  if (!benchPlayer) return false;

  // The keeper slot is fixed - only the other GK can ever fill it, same as real FPL.
  if (benchPlayer.position === "GKP") return starter.position === "GKP";
  if (starter.position === "GKP") return false;

  // Outfield subs can cross positions and change your formation, same as real FPL,
  // as long as the resulting shape stays within 3-5 DEF, 2-5 MID, 1-3 FWD.
  const preview = draftSquad.map((p) => {
    if (p.element === draftSubSelection) return { ...p, multiplier: starter.multiplier };
    if (p.element === starter.element) return { ...p, multiplier: benchPlayer.multiplier };
    return p;
  });
  return isValidFormation(draftFormationCounts(preview));
}

function draftOpenTransfer(element) {
  const target = draftSquad.find((p) => p.element === element);
  if (!target) return;
  draftTransferElement = element;
  draftSearchTitleEl.textContent = `Replace ${target.name} (${target.position})`;
  draftSearchInputEl.hidden = false;
  draftSearchInputEl.value = "";
  draftSearchResultsEl.innerHTML = "";
  draftSearchPanelEl.hidden = false;
  draftSearchInputEl.focus();
}

let draftSearchDebounce = null;
draftSearchInputEl.addEventListener("input", () => {
  clearTimeout(draftSearchDebounce);
  const q = draftSearchInputEl.value.trim();
  if (q.length < 2) {
    draftSearchResultsEl.innerHTML = "";
    return;
  }
  draftSearchDebounce = setTimeout(async () => {
    const target = draftSquad.find((p) => p.element === draftTransferElement);
    const position = target ? target.position : "";
    try {
      const res = await fetch(
        `/api/players/search?q=${encodeURIComponent(q)}&position=${encodeURIComponent(position)}`
      );
      const data = await res.json();
      renderDraftSearchResults(data.players || []);
    } catch {
      draftSearchResultsEl.innerHTML = "";
    }
  }, 300);
});

function renderDraftSearchResults(players) {
  draftSearchResultsEl.innerHTML = "";
  if (!players.length) {
    draftSearchResultsEl.textContent = "No matches.";
    return;
  }
  for (const p of players) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "draft-search-result";
    row.textContent = `${p.web_name} (${p.team_short}) - £${p.price_m.toFixed(1)}m`;
    row.addEventListener("click", () => draftApplyTransfer(p));
    draftSearchResultsEl.appendChild(row);
  }
}

function draftApplyTransfer(newPlayer) {
  const idx = draftSquad.findIndex((p) => p.element === draftTransferElement);
  if (idx === -1) return;
  const old = draftSquad[idx];
  draftSquad[idx] = {
    element: newPlayer.id,
    name: newPlayer.web_name,
    team_short: newPlayer.team_short,
    position: old.position,
    price_m: newPlayer.price_m,
    price_change_m: 0,
    is_captain: old.is_captain,
    is_vice_captain: old.is_vice_captain,
    multiplier: old.multiplier,
    next_fixture: null,
    status: newPlayer.status,
    chance_of_playing_next_round: newPlayer.chance_of_playing_next_round,
    news: newPlayer.news,
  };
  draftSearchPanelEl.hidden = true;
  renderDraftPitch();
}

draftSearchCloseEl.addEventListener("click", () => {
  draftSearchPanelEl.hidden = true;
  draftSearchInputEl.hidden = false;
});

async function enterDraftMode() {
  const teamId = loadTeamId();
  if (!teamId) {
    alert("Save your FPL Team ID above first.");
    return;
  }
  try {
    const res = await fetch(`/api/draft?team_id=${encodeURIComponent(teamId)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not load draft.");

    draftSquad = data.squad.map((p) => ({ ...p }));
    draftOriginalSquad = data.squad.map((p) => ({ ...p }));
    draftTotalBudget = data.total_budget_m;
    draftBankM = data.bank_m;
    draftTeamIdValue = data.team_id;
    draftGameweekValue = data.gameweek;
    if (typeof data.free_transfers === "number") {
      draftFreeTransfersEl.value = data.free_transfers;
    }
    draftMode = true;

    draftBtnEl.hidden = true;
    showFormationBtnEl.hidden = true;
    squadViewToggleEl.hidden = true;
    draftToolbarEl.hidden = false;
    draftPreviewEl.hidden = true;
    lastDraftPreviewData = null;
    renderDraftPitch();
  } catch (err) {
    alert(err.message);
  }
}

function exitDraftMode() {
  draftMode = false;
  draftSquad = null;
  draftOriginalSquad = null;
  draftToolbarEl.hidden = true;
  draftPreviewEl.hidden = true;
  lastDraftPreviewData = null;
  draftBtnEl.hidden = false;
  showFormationBtnEl.hidden = false;
  squadViewToggleEl.hidden = false;
  loadSquad();
}

draftBtnEl.addEventListener("click", enterDraftMode);
draftCancelBtnEl.addEventListener("click", exitDraftMode);

draftFreeTransfersEl.addEventListener("input", () => {
  if (draftMode) updateDraftBudgetDisplay();
});
draftChipSelectEl.addEventListener("change", () => {
  if (draftMode) updateDraftBudgetDisplay();
});

function draftPicksPayload() {
  return draftSquad.map((p) => ({
    element: p.element,
    multiplier: p.multiplier,
    is_captain: p.is_captain,
    is_vice_captain: p.is_vice_captain,
  }));
}

let lastDraftPreviewData = null;

function previewPlayerCard(p) {
  const card = playerCard(p);
  if (p.swapped) card.classList.add("swapped");
  return card;
}

function renderDraftPreview(data) {
  lastDraftPreviewData = data;
  draftPreviewSummaryEl.textContent = data.summary;

  const chip = draftChipSelectEl.value;
  const freeTransfers = parseInt(draftFreeTransfersEl.value, 10) || 0;
  const chipCoversCost = chip === "wildcard" || chip === "freehit";
  const hits = Math.max(0, data.changes_count - freeTransfers);
  const cost = chipCoversCost ? 0 : hits * 4;

  let costText = `${data.changes_count} change${data.changes_count === 1 ? "" : "s"}`;
  if (data.changes_count > 0) {
    if (chipCoversCost) {
      costText += ` · Free (${chip === "wildcard" ? "Wildcard" : "Free Hit"} covers it)`;
    } else if (cost > 0) {
      costText += ` · ${freeTransfers} free transfer${freeTransfers === 1 ? "" : "s"} available · Costs -${cost} pts`;
    } else {
      costText += ` · Within your ${freeTransfers} free transfer${freeTransfers === 1 ? "" : "s"}`;
    }
  }
  draftPreviewCostEl.textContent = costText;
  draftPreviewCostEl.className = `draft-preview-cost ${cost > 0 ? "penalty" : ""}`;

  const starters = data.proposed_squad.filter((p) => p.multiplier > 0);
  const bench = data.proposed_squad.filter((p) => p.multiplier === 0);

  draftPreviewPitchEl.innerHTML = "";
  for (const pos of ["FWD", "MID", "DEF", "GKP"]) {
    const players = starters.filter((p) => p.position === pos);
    if (!players.length) continue;
    const row = document.createElement("div");
    row.className = "pitch-row";
    players.forEach((p) => row.appendChild(previewPlayerCard(p)));
    draftPreviewPitchEl.appendChild(row);
  }

  draftPreviewBenchEl.innerHTML = "";
  bench.forEach((p) => draftPreviewBenchEl.appendChild(previewPlayerCard(p)));

  draftPreviewEl.hidden = false;
  draftPreviewEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

draftAdviceBtnEl.addEventListener("click", async () => {
  if (!confirm("Get a draft review? This always costs 2 credits.")) return;

  draftAdviceBtnEl.disabled = true;
  const originalLabel = draftAdviceBtnEl.textContent;
  draftAdviceBtnEl.textContent = "Reviewing... (~15-30s)";

  try {
    const res = await fetch("/api/draft/advice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team_id: draftTeamIdValue,
        gameweek: draftGameweekValue,
        picks: draftPicksPayload(),
        bank_m: draftBankM,
      }),
    });
    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || "Could not review draft.");
      return;
    }

    renderDraftPreview(data);
    setCredits(data.credits);
  } catch (err) {
    alert(err.message);
  } finally {
    draftAdviceBtnEl.disabled = false;
    draftAdviceBtnEl.textContent = originalLabel;
  }
});

draftApplyBtnEl.addEventListener("click", () => {
  if (!lastDraftPreviewData) return;
  draftSquad = lastDraftPreviewData.proposed_squad.map((p) => ({ ...p }));
  draftPreviewEl.hidden = true;
  renderDraftPitch();
});

draftPreviewCloseEl.addEventListener("click", () => {
  draftPreviewEl.hidden = true;
});

draftSaveBtnEl.addEventListener("click", async () => {
  const picks = draftPicksPayload();
  draftSaveBtnEl.disabled = true;
  try {
    const res = await fetch("/api/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        team_id: draftTeamIdValue,
        gameweek: draftGameweekValue,
        picks,
        bank_m: draftBankM,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Could not save draft.");
    draftBudgetEl.textContent = "Draft saved.";
  } catch (err) {
    alert(err.message);
  } finally {
    draftSaveBtnEl.disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = "";
  suggestedQuestionsEl.innerHTML = "";
  addMessage("user", text);
  history.push({ role: "user", content: text });

  const pending = addPendingMessage("Thinking...");
  formEl.querySelector("button").disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, team_id: loadTeamId() || null }),
    });

    if (res.status === 401) {
      showAuth();
      return;
    }

    const data = await res.json();

    if (!res.ok) {
      pending.textContent = data.detail || `Server error: ${res.status}`;
      pending.className = "msg assistant limit";
      history.pop(); // don't count the failed turn toward context
      return;
    }

    renderAssistantText(pending, data.reply);
    pending.className = "msg assistant";
    history.push({ role: "assistant", content: data.reply });
    setCredits(data.credits);
    if (data.is_advice) addAdviceFollowUp(data.reply);
  } catch (err) {
    // A SyntaxError here means the response body wasn't valid JSON (e.g. a
    // dropped connection mid-deploy, or a proxy timeout page) - show a plain
    // "try again" instead of surfacing that raw parser error to the user.
    pending.textContent =
      err instanceof SyntaxError ? "Connection issue - please try again." : `Error: ${err.message}`;
    pending.className = "msg assistant";
    history.pop();
  } finally {
    formEl.querySelector("button").disabled = false;
  }
});

// ---------------------------------------------------------------------------
// Gameweek banner
// ---------------------------------------------------------------------------

const DEADLINE_ALERT_MS = 3 * 60 * 60 * 1000; // 3 hours

let deadlineTimestamp = null;
let deadlineIso = null;
let lastHandledLapseDeadline = null;
let deadlineLapsePollTimer = null;
let currentGwName = null;
let windowStartTimestamp = null;
let countdownIntervalId = null;

function requestNotificationPermission() {
  if ("Notification" in window && Notification.permission === "default") {
    Notification.requestPermission();
  }
}

function hasNotifiedForDeadline(iso) {
  try {
    return localStorage.getItem("fplNotifiedDeadline") === iso;
  } catch {
    return false;
  }
}

function markNotifiedForDeadline(iso) {
  try {
    localStorage.setItem("fplNotifiedDeadline", iso);
  } catch {
    // ignore - notification will just fire again next load, not harmful
  }
}

async function loadGameweek() {
  try {
    const res = await fetch("/api/gameweek");
    if (!res.ok) return;
    const data = await res.json();

    const deadline = new Date(data.deadline_time);
    deadlineTimestamp = deadline.getTime();
    deadlineIso = data.deadline_time;
    currentGwName = data.name;
    windowStartTimestamp = data.window_start ? new Date(data.window_start).getTime() : null;

    const formatted = deadline.toLocaleString(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });

    gameweekBarEl.innerHTML = `
      <div class="gw-card">
        <div class="gw-top">
          <svg class="league-badge" viewBox="0 0 24 28" width="20" height="23">
            <path d="M12,1 L22,5 L22,14 Q22,22.5 12,27 Q2,22.5 2,14 L2,5 Z" />
            <circle class="league-badge-ball" cx="12" cy="13.5" r="5.2" />
            <path class="league-badge-pentagon" d="M12,10 L14.5,11.8 L13.6,14.7 L10.4,14.7 L9.5,11.8 Z" />
          </svg>
          <span class="gw-name">${data.name}</span>
          <span class="gw-deadline-label">Deadline: ${formatted}</span>
        </div>
        <div class="gw-countdown-grid">
          <div class="gw-unit"><span class="gw-num" id="gw-d">00</span><span class="gw-unit-label">Days</span></div>
          <div class="gw-sep">:</div>
          <div class="gw-unit"><span class="gw-num" id="gw-h">00</span><span class="gw-unit-label">Hrs</span></div>
          <div class="gw-sep">:</div>
          <div class="gw-unit"><span class="gw-num" id="gw-m">00</span><span class="gw-unit-label">Min</span></div>
          <div class="gw-sep">:</div>
          <div class="gw-unit"><span class="gw-num" id="gw-s">00</span><span class="gw-unit-label">Sec</span></div>
        </div>
        <div class="gw-progress">
          <div class="gw-progress-fill" id="gw-progress-fill"></div>
          <div class="gw-ball" id="gw-ball" title="Current position toward the deadline">⚽</div>
        </div>
      </div>`;

    if (countdownIntervalId) clearInterval(countdownIntervalId);
    updateCountdown();
    countdownIntervalId = setInterval(updateCountdown, 1000);
  } catch {
    // non-critical banner - fail silently
  }
}

function updateCountdown() {
  const dEl = document.getElementById("gw-d");
  const hEl = document.getElementById("gw-h");
  const mEl = document.getElementById("gw-m");
  const sEl = document.getElementById("gw-s");
  const fillEl = document.getElementById("gw-progress-fill");
  const ballEl = document.getElementById("gw-ball");
  if (!dEl || deadlineTimestamp === null) return;

  const diffMs = deadlineTimestamp - Date.now();
  if (diffMs <= 0) {
    gameweekBarEl.querySelector(".gw-deadline-label").textContent = "Deadline passed";
    clearInterval(countdownIntervalId);
    // FPL locks in the new gameweek's picks right at the deadline - refresh the
    // formation panel once so it picks up whatever squad/transfers were actually
    // saved, without the user needing to click "Refresh Formation" themselves.
    // Guarded so this fires once per deadline, not on every poll while the
    // upstream gameweek data is still showing the same lapsed deadline.
    if (lastHandledLapseDeadline !== deadlineTimestamp) {
      lastHandledLapseDeadline = deadlineTimestamp;
      setTimeout(loadSquad, 10000);
    }
    // Poll for the next deadline, backing off to once a minute instead of every
    // 5s so we don't hammer the API while waiting on the next gameweek to open.
    if (!deadlineLapsePollTimer) {
      deadlineLapsePollTimer = setTimeout(() => {
        deadlineLapsePollTimer = null;
        loadGameweek();
      }, 60000);
    }
    return;
  }

  const totalSeconds = Math.floor(diffMs / 1000);
  const pad = (n) => String(n).padStart(2, "0");
  dEl.textContent = pad(Math.floor(totalSeconds / 86400));
  hEl.textContent = pad(Math.floor((totalSeconds % 86400) / 3600));
  mEl.textContent = pad(Math.floor((totalSeconds % 3600) / 60));
  sEl.textContent = pad(totalSeconds % 60);

  const card = gameweekBarEl.querySelector(".gw-card");
  if (diffMs <= DEADLINE_ALERT_MS) {
    card?.classList.add("alert");
    if (deadlineIso && !hasNotifiedForDeadline(deadlineIso)) {
      markNotifiedForDeadline(deadlineIso);
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("FPL deadline approaching", {
          body: `${currentGwName} deadline is under 3 hours away - make sure your team is set!`,
        });
      }
    }
  } else {
    card?.classList.remove("alert");
  }

  let pct = 0;
  if (windowStartTimestamp !== null) {
    const total = deadlineTimestamp - windowStartTimestamp;
    const elapsed = Date.now() - windowStartTimestamp;
    pct = Math.min(100, Math.max(0, (elapsed / total) * 100));
  }
  if (fillEl) fillEl.style.width = `${pct}%`;
  if (ballEl) ballEl.style.left = `${pct}%`;
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

colorModeSelectEl.value = getColorMode();
colorModeSelectEl.addEventListener("change", () => {
  try {
    localStorage.setItem("fplColorMode", colorModeSelectEl.value);
  } catch {
    // ignore - just won't persist across reloads
  }
  if (draftMode) {
    renderDraftPitch();
    if (!draftPreviewEl.hidden && lastDraftPreviewData) renderDraftPreview(lastDraftPreviewData);
  } else if (lastSquadData) {
    renderSquad(lastSquadData);
  }
});

setAuthMode("login");
checkAuth();
loadGameweek();
