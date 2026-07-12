const adminState = {
  pin: sessionStorage.getItem("kidPortalAdminPin") || "",
  config: null,
};

const loginCard = document.querySelector("#login-card");
const adminPanel = document.querySelector("#admin-panel");
const loginStatus = document.querySelector("#login-status");
const saveStatus = document.querySelector("#save-status");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[char]));
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`${url} failed: ${response.status}`);
  return response.json();
}

async function loadAdminState() {
  const data = await postJson("/api/admin/state", { pin: adminState.pin });
  adminState.config = data.config;
  renderState(data);
  loginCard.hidden = true;
  adminPanel.hidden = false;
  sessionStorage.setItem("kidPortalAdminPin", adminState.pin);
}

function renderState(data) {
  document.querySelector("#host-name").textContent = data.network.hostname || "Portal";
  document.querySelector("#youtube-mode").textContent = data.youtube.mode || "unknown";
  document.querySelector("#youtube-source").textContent = data.youtube.configured ? "API key configured" : "Demo mode";
  document.querySelector("#daily-limit").textContent = data.config.limits.daily_minutes;
  document.querySelector("#unrestricted-minutes").textContent = data.config.parent.default_unrestricted_minutes;
  renderNetwork(data.network);
  renderHistory(data.history);
  renderSites();
  renderConfigList("allowed_keywords", "#allowed-keywords");
  renderConfigList("blocked_keywords", "#blocked-keywords");
  renderConfigList("allowed_channels", "#allowed-channels");
  renderConfigList("blocked_channels", "#blocked-channels");
}

function renderNetwork(network) {
  const list = document.querySelector("#network-list");
  list.innerHTML = "";
  if (!network.addresses?.length) {
    list.innerHTML = '<p class="empty">No LAN address detected.</p>';
    return;
  }
  network.addresses.forEach((item) => {
    const card = document.createElement("article");
    card.className = "network-card";
    card.innerHTML = `
      <strong>${escapeHtml(item.address)}</strong>
      <span>${escapeHtml(item.portal_url)}</span>
      <code>${escapeHtml(item.ssh_target)}</code>
    `;
    list.appendChild(card);
  });
}

function renderHistory(items) {
  const list = document.querySelector("#history-list");
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = '<p class="empty">No searches yet.</p>';
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "history-card";
    card.innerHTML = `
      <strong>${escapeHtml(item.query)}</strong>
      <span>${escapeHtml(item.mode)} - ${item.result_count} results</span>
    `;
    list.appendChild(card);
  });
}

function renderSites() {
  const list = document.querySelector("#site-list");
  list.innerHTML = "";
  adminState.config.allowed_sites.forEach((site, index) => {
    const card = document.createElement("article");
    card.className = "item-card";
    card.innerHTML = `
      <strong>${escapeHtml(site.label)}</strong>
      <button type="button" data-remove-site="${index}">Remove</button>
      <span>${escapeHtml(site.domain)} - ${escapeHtml(site.url)}</span>
    `;
    list.appendChild(card);
  });
}

function renderConfigList(field, selector) {
  const list = document.querySelector(selector);
  list.innerHTML = "";
  const values = adminState.config.filtering[field];
  if (!values.length) {
    list.innerHTML = '<p class="empty">Empty.</p>';
    return;
  }
  values.forEach((value, index) => {
    const card = document.createElement("article");
    card.className = "item-card";
    card.innerHTML = `
      <strong>${escapeHtml(value)}</strong>
      <button type="button" data-remove-field="${field}" data-remove-index="${index}">Remove</button>
    `;
    list.appendChild(card);
  });
}

function addUniqueConfigValue(field, value) {
  const normalized = value.trim();
  if (!normalized) return;
  const list = adminState.config.filtering[field];
  if (!list.some((item) => item.toLowerCase() === normalized.toLowerCase())) list.push(normalized);
}

async function saveConfig() {
  saveStatus.textContent = "Saving...";
  const viewPin = document.querySelector("#view-pin").value.trim();
  if (viewPin && !/^\d{4,12}$/.test(viewPin)) {
    saveStatus.textContent = "Viewing PIN must be 4-12 digits.";
    return;
  }
  const response = await fetch("/api/parent/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: adminState.pin, config: adminState.config, view_pin: viewPin || null }),
  });
  saveStatus.textContent = response.ok ? "Saved." : "Save failed.";
  if (response.ok) {
    document.querySelector("#view-pin").value = "";
    await loadAdminState();
  }
}

function lockAdmin() {
  adminState.pin = "";
  adminState.config = null;
  sessionStorage.removeItem("kidPortalAdminPin");
  adminPanel.hidden = true;
  loginCard.hidden = false;
  document.querySelector("#pin").value = "";
  loginStatus.textContent = "Locked.";
}

document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  adminState.pin = document.querySelector("#pin").value;
  loginStatus.textContent = "Unlocking...";
  try {
    await loadAdminState();
    loginStatus.textContent = "";
  } catch (error) {
    sessionStorage.removeItem("kidPortalAdminPin");
    loginStatus.textContent = "Invalid PIN or portal unavailable.";
  }
});

document.querySelector("#refresh-state").addEventListener("click", () => loadAdminState());
document.querySelector("#lock-admin").addEventListener("click", lockAdmin);
document.querySelector("#save-config").addEventListener("click", saveConfig);
document.querySelector("#clear-history").addEventListener("click", async () => {
  await postJson("/api/admin/youtube/history/clear", { pin: adminState.pin });
  await loadAdminState();
});

document.querySelector("#site-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!adminState.config) return;
  const label = document.querySelector("#site-label").value.trim();
  const domain = document.querySelector("#site-domain").value.trim();
  const url = document.querySelector("#site-url").value.trim();
  if (!label || !domain || !url) return;
  adminState.config.allowed_sites.push({ label, domain, url });
  event.target.reset();
  renderSites();
});

document.querySelector("#site-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-site]");
  if (!button || !adminState.config) return;
  adminState.config.allowed_sites.splice(Number(button.dataset.removeSite), 1);
  renderSites();
});

document.querySelectorAll("[data-list-form]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!adminState.config) return;
    const input = form.querySelector("input");
    addUniqueConfigValue(form.dataset.listForm, input.value);
    input.value = "";
    renderConfigList(form.dataset.listForm, `#${form.closest(".rule-panel").querySelector(".item-list").id}`);
  });
});

document.querySelector(".rules-grid").addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-field]");
  if (!button || !adminState.config) return;
  const field = button.dataset.removeField;
  adminState.config.filtering[field].splice(Number(button.dataset.removeIndex), 1);
  renderConfigList(field, `#${button.closest(".item-list").id}`);
});

if (adminState.pin) {
  loadAdminState().catch(() => sessionStorage.removeItem("kidPortalAdminPin"));
}
