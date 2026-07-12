const adminState = {
  pin: sessionStorage.getItem("kidPortalAdminPin") || "",
  config: null,
  activeTab: localStorage.getItem("kidPortalAdminTab") || "overview",
};

const loginCard = document.querySelector("#login-card");
const adminPanel = document.querySelector("#admin-panel");
const loginStatus = document.querySelector("#login-status");
const saveStatus = document.querySelector("#save-status");
const saveBar = document.querySelector(".save-bar");
const saveButton = document.querySelector("#save-config");
const configTabs = new Set(["playback", "youtube", "websites"]);

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
  const usedMinutes = Math.floor((data.usage?.used_seconds || 0) / 60);
  const remainingMinutes = Math.ceil((data.usage?.remaining_seconds || 0) / 60);
  document.querySelector("#viewing-used").textContent = `${usedMinutes} min`;
  document.querySelector("#viewing-remaining").textContent = `${remainingMinutes} min remaining`;
  renderNetwork(data.network);
  renderNetworkAccess(data.network_access, data.network);
  renderStorage(data.storage);
  renderMonitoring(data.monitoring);
  renderHistory(data.history);
  renderSettings();
  renderSites();
  renderConfigList("allowed_keywords", "#allowed-keywords");
  renderConfigList("blocked_keywords", "#blocked-keywords");
  renderConfigList("approval_keywords", "#approval-keywords");
  renderConfigList("allowed_channels", "#allowed-channels");
  renderConfigList("blocked_channels", "#blocked-channels");
  renderConfigList("blocked_categories", "#blocked-categories");
  activateTab(adminState.activeTab);
}

function activateTab(tabName) {
  const target = document.querySelector(`[data-tab-panel="${tabName}"]`) ? tabName : "overview";
  adminState.activeTab = target;
  localStorage.setItem("kidPortalAdminTab", target);
  document.querySelectorAll("[data-tab-target]").forEach((button) => {
    const active = button.dataset.tabTarget === target;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
    const active = panel.dataset.tabPanel === target;
    panel.hidden = !active;
    panel.classList.toggle("is-active", active);
  });
  if (saveButton && saveBar) {
    const saveable = configTabs.has(target);
    saveButton.hidden = !saveable;
    saveBar.hidden = target === "overview";
  }
}

function renderNetworkAccess(networkAccess, network = null) {
  const toggle = document.querySelector("#content-lan-toggle");
  if (!toggle) return;
  toggle.checked = Boolean(networkAccess?.content_lan_enabled);
  const contentLink = document.querySelector("#content-lan-url");
  const firstAddress = network?.addresses?.[0];
  if (!contentLink || !firstAddress) return;
  contentLink.href = firstAddress.portal_url;
  contentLink.textContent = firstAddress.portal_url;
}

function renderNetwork(network) {
  const list = document.querySelector("#network-list");
  list.innerHTML = "";
  if (!network.addresses?.length) {
    list.innerHTML = '<p class="empty">No LAN address detected.</p>';
    return;
  }
  network.addresses.forEach((item) => {
    const adminUrl = `http://${item.address}/`;
    const card = document.createElement("article");
    card.className = "network-card";
    card.innerHTML = `
      <strong>${escapeHtml(item.address)}</strong>
      <a href="${escapeHtml(adminUrl)}" target="_blank" rel="noreferrer">${escapeHtml(adminUrl)}</a>
      <code>${escapeHtml(item.ssh_target)}</code>
    `;
    list.appendChild(card);
  });
}

function renderStorage(storage) {
  const list = document.querySelector("#storage-list");
  if (!storage) {
    list.innerHTML = '<p class="empty">Storage unavailable.</p>';
    return;
  }
  list.innerHTML = `
    <article class="stat-card">
      <span>Free</span>
      <strong>${escapeHtml(formatBytes(storage.free_bytes))}</strong>
      <small>${escapeHtml(storage.path)}</small>
    </article>
    <article class="stat-card">
      <span>Used</span>
      <strong>${escapeHtml(String(storage.percent_used))}%</strong>
      <small>${escapeHtml(formatBytes(storage.used_bytes))}</small>
    </article>
  `;
}

function renderMonitoring(monitoring) {
  const list = document.querySelector("#monitoring-list");
  if (!monitoring) {
    list.innerHTML = '<p class="empty">Monitoring unavailable.</p>';
    return;
  }
  const temperature = Number.isFinite(monitoring.temperature_c)
    ? `${monitoring.temperature_c.toFixed(1)} C`
    : "n/a";
  const throttled = monitoring.throttled_state || "n/a";
  const processRows = monitoring.top_processes?.length
    ? monitoring.top_processes.map((process) => `
    <article class="process-card">
      <strong title="${escapeHtml(process.args)}">${escapeHtml(process.command)}</strong>
      <span>${escapeHtml(process.cpu_percent.toFixed(1))}% CPU</span>
      <span>${escapeHtml(process.memory_percent.toFixed(1))}% RAM</span>
    </article>
  `).join("")
    : '<p class="empty">Process list unavailable.</p>';
  list.innerHTML = `
    <section class="monitoring-metrics">
      <article class="stat-card">
        <span>Temperature</span>
        <strong>${escapeHtml(temperature)}</strong>
        <small>CPU / SoC</small>
      </article>
      <article class="stat-card">
        <span>Throttling</span>
        <strong>${escapeHtml(throttled)}</strong>
        <small>0x0 is healthy</small>
      </article>
    </section>
    ${processRows}
  `;
}

function renderSettings() {
  document.querySelector("#daily-minutes").value = adminState.config.limits.daily_minutes;
  document.querySelector("#unrestricted-minutes-input").value = adminState.config.parent.default_unrestricted_minutes;
  document.querySelector("#max-duration-seconds").value = adminState.config.filtering.max_duration_seconds || "";
  document.querySelector("#youtube-max-results").value = adminState.config.youtube.max_results;
  document.querySelector("#youtube-safe-search").value = adminState.config.youtube.safe_search;
  document.querySelector("#youtube-region-code").value = adminState.config.youtube.region_code;
  document.querySelector("#default-decision").value = adminState.config.filtering.default_decision || "REQUIRE_PARENT_APPROVAL";
  document.querySelector("#view-pin").value = "";
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

function clampInteger(selector, min, max, fallback) {
  const value = Number.parseInt(document.querySelector(selector).value, 10);
  if (!Number.isFinite(value)) return fallback;
  return Math.min(Math.max(value, min), max);
}

function syncSettings() {
  adminState.config.limits.daily_minutes = clampInteger("#daily-minutes", 1, 1440, 90);
  adminState.config.parent.default_unrestricted_minutes = clampInteger("#unrestricted-minutes-input", 1, 240, 30);
  adminState.config.filtering.max_duration_seconds = clampInteger("#max-duration-seconds", 1, 86400, 3600);
  adminState.config.youtube.max_results = clampInteger("#youtube-max-results", 1, 25, 20);
  adminState.config.youtube.safe_search = document.querySelector("#youtube-safe-search").value;
  adminState.config.youtube.region_code = document.querySelector("#youtube-region-code").value.trim().toUpperCase() || "US";
  adminState.config.filtering.default_decision = document.querySelector("#default-decision").value;
}

function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = Number(bytes) || 0;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const digits = value >= 10 || unitIndex === 0 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[unitIndex]}`;
}

async function saveConfig() {
  saveStatus.textContent = "Saving...";
  syncSettings();
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

async function startTerminalMode() {
  saveStatus.textContent = "Starting terminal mode...";
  try {
    await postJson("/api/parent/terminal/start", { pin: adminState.pin });
    saveStatus.textContent = "Terminal mode starting on Raspberry Pi display.";
  } catch (error) {
    saveStatus.textContent = "Terminal mode failed.";
  }
}

async function returnToKiosk() {
  saveStatus.textContent = "Returning to kiosk...";
  try {
    await postJson("/api/parent/kiosk/start", { pin: adminState.pin });
    saveStatus.textContent = "Kiosk starting.";
  } catch (error) {
    saveStatus.textContent = "Kiosk start failed.";
  }
}

async function updateContentLanAccess(event) {
  const toggle = event.target;
  const enabled = toggle.checked;
  toggle.disabled = true;
  saveStatus.textContent = enabled ? "Opening content port 8080..." : "Closing content port 8080...";
  try {
    const state = await postJson("/api/parent/network-access", { pin: adminState.pin, enabled });
    renderNetworkAccess(state, null);
    saveStatus.textContent = state.content_lan_enabled ? "Content port 8080 is open on LAN." : "Content port 8080 is closed on LAN.";
  } catch (error) {
    toggle.checked = !enabled;
    saveStatus.textContent = "Network access update failed.";
  } finally {
    toggle.disabled = false;
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
document.querySelector("#exit-to-terminal").addEventListener("click", startTerminalMode);
document.querySelector("#return-to-kiosk").addEventListener("click", returnToKiosk);
document.querySelector("#content-lan-toggle").addEventListener("change", updateContentLanAccess);
document.querySelector("#clear-history").addEventListener("click", async () => {
  await postJson("/api/admin/youtube/history/clear", { pin: adminState.pin });
  await loadAdminState();
});

document.querySelector(".tab-nav").addEventListener("click", (event) => {
  const button = event.target.closest("[data-tab-target]");
  if (!button) return;
  activateTab(button.dataset.tabTarget);
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
