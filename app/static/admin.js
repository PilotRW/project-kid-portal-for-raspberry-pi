const adminState = {
  pin: sessionStorage.getItem("kidPortalAdminPin") || "",
  config: null,
  activeTab: localStorage.getItem("kidPortalAdminTab") || "overview",
};

const loginCard = document.querySelector("#login-card");
const adminPanel = document.querySelector("#admin-panel");
const loginStatus = document.querySelector("#login-status");
const saveStatus = document.querySelector("#save-status");
const signOutButton = document.querySelector("#sign-out-admin");
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

async function postJson(url, payload, method = "POST") {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let detail = `${url} failed: ${response.status}`;
    try {
      detail = (await response.json()).detail || detail;
    } catch (error) {
      detail = `${url} failed: ${response.status}`;
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

async function loadAdminState() {
  const data = await postJson("/api/admin/state", { pin: adminState.pin });
  adminState.config = data.config;
  renderState(data);
  loginCard.hidden = true;
  adminPanel.hidden = false;
  signOutButton.hidden = false;
  sessionStorage.setItem("kidPortalAdminPin", adminState.pin);
}

function renderState(data) {
  document.querySelector("#host-name").textContent = data.network.hostname || "Portal";
  document.querySelector("#youtube-mode").textContent = data.youtube.mode || "unknown";
  document.querySelector("#youtube-source").textContent = data.youtube.configured ? "API key configured" : "Demo mode";
  renderYouTubeKeyStatus(data.youtube);
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
  renderApprovalLog(data.approvals || []);
  renderFilterInsights(data.filter_insights || {});
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

function renderYouTubeKeyStatus(youtube) {
  const status = document.querySelector("#youtube-key-status");
  const source = document.querySelector("#youtube-key-source");
  if (!status || !source) return;
  status.textContent = youtube.configured ? "configured" : "not configured";
  source.textContent = youtube.configured ? youtube.source : "Demo mode";
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
  document.querySelector("#short-video-max-seconds").value = adminState.config.filtering.short_video_max_seconds || "";
  document.querySelector("#short-video-decision").value = adminState.config.filtering.short_video_decision || "REQUIRE_PARENT_APPROVAL";
  document.querySelector("#youtube-max-results").value = adminState.config.youtube.max_results;
  document.querySelector("#youtube-safe-search").value = adminState.config.youtube.safe_search;
  document.querySelector("#youtube-region-code").value = adminState.config.youtube.region_code;
  document.querySelector("#default-decision").value = adminState.config.filtering.default_decision || "REQUIRE_PARENT_APPROVAL";
  document.querySelector("#display-mode").value = adminState.config.display?.mode || "1080p";
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

function renderApprovalLog(items) {
  const list = document.querySelector("#approval-log-list");
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = '<p class="empty">No approved videos yet.</p>';
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "history-card";
    const reasons = item.reasons?.length ? item.reasons.join(", ") : "no filter reasons";
    card.innerHTML = `
      <strong>${escapeHtml(item.title || item.video_id)}</strong>
      <span>${escapeHtml(item.channel_title || item.channel_id || "unknown channel")} - ${escapeHtml(item.decision)} - ${escapeHtml(reasons)}</span>
      <span>${escapeHtml(formatDateTime(item.approved_at))}</span>
    `;
    list.appendChild(card);
  });
}

function renderFilterInsights(insights) {
  renderInsightList("#filter-gap-list", insights.gaps || [], "No default-allow gaps yet.");
  renderInsightList("#filter-approval-insight-list", insights.approvals || [], "No repeated approval requests yet.");
}

function renderInsightList(selector, items, emptyText) {
  const list = document.querySelector(selector);
  list.innerHTML = "";
  if (!items.length) {
    list.innerHTML = `<p class="empty">${escapeHtml(emptyText)}</p>`;
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "history-card";
    card.innerHTML = `
      <strong>${escapeHtml(item.title)}</strong>
      <span>${escapeHtml(item.channel || "unknown channel")} - ${escapeHtml(item.count)} hits</span>
      <span>${escapeHtml(formatDateTime(item.last_seen))}</span>
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
  const count = document.querySelector(`[data-rule-count="${field}"]`);
  if (count) count.textContent = String(values.length);
  const filter = document.querySelector(`[data-rule-filter="${field}"]`)?.value.trim().toLowerCase() || "";
  const visibleValues = values
    .map((value, index) => ({ value, index }))
    .filter((item) => !filter || item.value.toLowerCase().includes(filter));
  if (!visibleValues.length) {
    list.innerHTML = '<p class="empty">Empty.</p>';
    return;
  }
  visibleValues.forEach(({ value, index }) => {
    const card = document.createElement("article");
    card.className = "item-card rule-chip";
    card.innerHTML = `
      <strong>${escapeHtml(value)}</strong>
      <button type="button" aria-label="Remove ${escapeHtml(value)}" data-remove-field="${field}" data-remove-index="${index}">x</button>
    `;
    list.appendChild(card);
  });
}

function splitRuleInput(value) {
  return value
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function addUniqueConfigValues(field, value) {
  const list = adminState.config.filtering[field];
  splitRuleInput(value).forEach((normalized) => {
    if (!list.some((item) => item.toLowerCase() === normalized.toLowerCase())) list.push(normalized);
  });
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
  adminState.config.filtering.short_video_max_seconds = clampInteger("#short-video-max-seconds", 1, 600, 60);
  adminState.config.filtering.short_video_decision = document.querySelector("#short-video-decision").value;
  adminState.config.youtube.max_results = clampInteger("#youtube-max-results", 1, 25, 20);
  adminState.config.youtube.safe_search = document.querySelector("#youtube-safe-search").value;
  adminState.config.youtube.region_code = document.querySelector("#youtube-region-code").value.trim().toUpperCase() || "US";
  adminState.config.filtering.default_decision = document.querySelector("#default-decision").value;
  if (!adminState.config.display) adminState.config.display = {};
  adminState.config.display.mode = document.querySelector("#display-mode").value;
}

function formatDateTime(value) {
  if (!value) return "unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
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

async function updateSystemSoftware() {
  const button = document.querySelector("#update-system-software");
  const confirmed = window.confirm("Run Raspberry Pi software update now? This can take several minutes.");
  if (!confirmed) return;
  button.disabled = true;
  saveStatus.textContent = "Starting Raspberry Pi software update...";
  try {
    await postJson("/api/parent/software/update", { pin: adminState.pin });
    saveStatus.textContent = "Software update started. Keep the Pi powered on.";
  } catch (error) {
    saveStatus.textContent = error.message || "Software update failed to start.";
  } finally {
    button.disabled = false;
  }
}

async function applyDisplayMode() {
  const mode = document.querySelector("#display-mode").value;
  saveStatus.textContent = `Switching display to ${mode}...`;
  try {
    const state = await postJson("/api/parent/display", { pin: adminState.pin, mode });
    if (!adminState.config.display) adminState.config.display = {};
    adminState.config.display.mode = mode;
    saveStatus.textContent = state.current_resolution
      ? `Display switched to ${state.current_resolution}.`
      : `Display mode saved: ${state.configured_mode}.`;
  } catch (error) {
    saveStatus.textContent = error.message || "Display mode update failed.";
  }
}

async function saveYouTubeKey(event) {
  event.preventDefault();
  const input = document.querySelector("#youtube-api-key");
  const apiKey = input.value.trim();
  if (!apiKey) {
    saveStatus.textContent = "Paste an API key first.";
    return;
  }
  saveStatus.textContent = "Saving YouTube API key...";
  try {
    const result = await fetch("/api/parent/youtube/key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin: adminState.pin, api_key: apiKey }),
    });
    if (!result.ok) {
      let detail = "YouTube API key save failed.";
      try {
        detail = (await result.json()).detail || detail;
      } catch (error) {
        detail = "YouTube API key save failed.";
      }
      throw new Error(detail);
    }
    const data = await result.json();
    input.value = "";
    renderYouTubeKeyStatus(data.youtube);
    saveStatus.textContent = "YouTube API key saved. Search cache cleared.";
  } catch (error) {
    saveStatus.textContent = error.message || "YouTube API key save failed.";
  }
}

async function clearYouTubeKey() {
  saveStatus.textContent = "Clearing YouTube API key...";
  try {
    const data = await postJson("/api/parent/youtube/key", { pin: adminState.pin }, "DELETE");
    renderYouTubeKeyStatus(data.youtube);
    document.querySelector("#youtube-api-key").value = "";
    saveStatus.textContent = "YouTube API key cleared. Search cache cleared.";
  } catch (error) {
    saveStatus.textContent = error.message || "YouTube API key clear failed.";
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
  signOutButton.hidden = true;
  loginCard.hidden = false;
  document.querySelector("#pin").value = "";
  loginStatus.textContent = "Signed out.";
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
    loginStatus.textContent = error.status === 429 ? error.message : "Invalid PIN or portal unavailable.";
  }
});

document.querySelector("#refresh-state").addEventListener("click", () => loadAdminState());
signOutButton.addEventListener("click", lockAdmin);
document.querySelector("#save-config").addEventListener("click", saveConfig);
document.querySelector("#exit-to-terminal").addEventListener("click", startTerminalMode);
document.querySelector("#return-to-kiosk").addEventListener("click", returnToKiosk);
document.querySelector("#update-system-software").addEventListener("click", updateSystemSoftware);
document.querySelector("#apply-display-mode").addEventListener("click", applyDisplayMode);
document.querySelector("#youtube-key-form").addEventListener("submit", saveYouTubeKey);
document.querySelector("#clear-youtube-key").addEventListener("click", clearYouTubeKey);
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
    addUniqueConfigValues(form.dataset.listForm, input.value);
    input.value = "";
    renderConfigList(form.dataset.listForm, `#${form.closest(".rule-panel").querySelector(".item-list").id}`);
  });
});

document.querySelectorAll("[data-rule-filter]").forEach((input) => {
  input.addEventListener("input", () => {
    renderConfigList(input.dataset.ruleFilter, `#${input.closest(".rule-panel").querySelector(".item-list").id}`);
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
