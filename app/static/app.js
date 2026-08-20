const state = {
  focusables: [],
  focusedIndex: 0,
  activeInput: null,
  keyboardMode: "text",
  keyboardLanguage: "en",
  parentPin: "",
  editableConfig: null,
  pendingApprovalVideo: null,
};

const views = {
  home: document.querySelector("#home"),
  youtube: document.querySelector("#youtube"),
  settings: document.querySelector("#settings"),
};

const builtinTiles = [
  {
    label: "YouTube",
    hint: "Curated search",
    action: "youtube",
    visual: "play",
    theme: "youtube",
  },
];

const siteTileThemes = [
  { match: /wikipedia/i, visual: "W", theme: "wikipedia" },
  { match: /khan/i, visual: "K", theme: "khan" },
  { match: /disney/i, visual: "D+", theme: "disney" },
  { match: /netflix/i, visual: "N", theme: "netflix" },
  { match: /rezka/i, visual: "R", theme: "rezka" },
  { match: /orf kids|kids\.orf/i, visual: "KiDS", theme: "orf-kids" },
  { match: /orf live|on\.orf/i, visual: "ORF", theme: "orf-live" },
];

const keyboardLayouts = {
  text: {
    en: [
      ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
      ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
      ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
      ["z", "x", "c", "v", "b", "n", "m"],
      ["RU", "Back", "Space", "Clear", "Hide", "Enter"],
    ],
    ru: [
      ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
      ["й", "ц", "у", "к", "е", "н", "г", "ш", "щ", "з"],
      ["ф", "ы", "в", "а", "п", "р", "о", "л", "д"],
      ["я", "ч", "с", "м", "и", "т", "ь", "б", "ю"],
      ["EN", "Back", "Space", "Clear", "Hide", "Enter"],
    ],
  },
  numeric: [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["Clear", "0", "Back"],
    ["Enter", "Hide"],
  ],
};

function showView(name) {
  Object.entries(views).forEach(([key, node]) => node.classList.toggle("active", key === name));
  hideKeyboard();
  refreshFocus();
}

function openSettings() {
  showView("settings");
  loadNetworkInfo();
}

function refreshFocus() {
  const pageFocusables = [...document.querySelectorAll(".view.active button, .view.active input, .view.active .tile")];
  const keyboardFocusables = document.querySelector("#keyboard").hidden
    ? []
    : [...document.querySelectorAll("#keyboard button")];
  state.focusables = [...pageFocusables, ...keyboardFocusables];
  state.focusedIndex = Math.min(state.focusedIndex, Math.max(state.focusables.length - 1, 0));
  setFocus(state.focusedIndex);
}

function setFocus(index) {
  state.focusables.forEach((item) => item.classList.remove("focus"));
  const target = state.focusables[index];
  if (!target) return;
  state.focusedIndex = index;
  target.classList.add("focus");
  target.focus({ preventScroll: true });
}

function moveFocus(delta) {
  if (!state.focusables.length) return;
  const next = (state.focusedIndex + delta + state.focusables.length) % state.focusables.length;
  setFocus(next);
}

async function loadTiles() {
  const response = await fetch("/api/sites");
  const sites = await response.json();
  const tiles = [
    ...builtinTiles,
    ...sites.map((site) => ({
      label: site.label,
      hint: site.domain,
      action: "site",
      url: site.url,
      ...tileVisualForSite(site),
    })),
  ];
  const container = document.querySelector("#tiles");
  container.innerHTML = "";
  tiles.forEach((tile) => {
    const button = document.createElement("button");
    button.className = `tile tile-${tile.theme}`;
    button.type = "button";
    button.innerHTML = `
      <span class="tile-art" aria-hidden="true">
        <span class="tile-symbol">${escapeHtml(tile.visual)}</span>
      </span>
      <span class="tile-copy">
        <strong>${escapeHtml(tile.label)}</strong>
        <small>${escapeHtml(tile.hint)}</small>
      </span>
    `;
    button.addEventListener("click", () => handleTile(tile));
    container.appendChild(button);
  });
  refreshFocus();
}

function tileVisualForSite(site) {
  const source = `${site.label} ${site.domain} ${site.url}`;
  const known = siteTileThemes.find((item) => item.match.test(source));
  if (known) return known;
  const letter = (site.label || site.domain || "?").trim().charAt(0).toUpperCase() || "?";
  return { visual: letter, theme: "default" };
}

function handleTile(tile) {
  if (tile.action === "youtube") {
    showView("youtube");
    loadYouTubeStatus();
    loadSearchHistory();
  }
  if (tile.action === "settings") openSettings();
  if (tile.action === "site") window.location.href = tile.url;
}

async function searchYouTube(event) {
  event.preventDefault();
  const query = document.querySelector("#youtube-query").value.trim();
  if (!query) return;
  hideKeyboard();
  refreshFocus();
  const results = document.querySelector("#youtube-results");
  const status = document.querySelector("#youtube-status");
  document.querySelector("#view-approval-panel").hidden = true;
  state.pendingApprovalVideo = null;
  results.innerHTML = "";
  status.textContent = "Searching...";
  try {
    const response = await fetch(`/api/youtube/search?q=${encodeURIComponent(query)}`);
    if (!response.ok) {
      let detail = `Search failed: ${response.status}`;
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (error) {
        detail = `Search failed: ${response.status}`;
      }
      throw new Error(detail);
    }
    const data = await response.json();
    loadSearchHistory();
    status.textContent = data.notice || `${data.results.length} filtered results`;
    if (!data.results.length) {
      results.innerHTML = '<p class="empty-state">No allowed results found.</p>';
    }
    data.results.forEach((item) => {
      const isAllowed = item.decision === "ALLOW";
      const needsApproval = item.decision === "REQUIRE_PARENT_APPROVAL";
      const card = document.createElement(isAllowed || needsApproval ? "button" : "article");
      const decisionClass = item.decision === "BLOCK" ? "block" : item.decision === "REQUIRE_PARENT_APPROVAL" ? "approval" : "";
      const thumbnail = item.video.thumbnail_url
        ? `<img src="${escapeHtml(proxiedThumbnailUrl(item.video.thumbnail_url))}" alt="" loading="lazy">`
        : '<span class="thumbnail-placeholder">No preview</span>';
      card.className = `result-card ${isAllowed ? "playable" : ""} ${needsApproval ? "approval-needed" : ""}`;
      if (isAllowed || needsApproval) {
        card.type = "button";
      }
      if (isAllowed) {
        card.addEventListener("click", () => openVideo(item.video.video_id));
      }
      if (needsApproval) {
        card.addEventListener("click", () => requestViewApproval(item.video));
      }
      card.innerHTML = `
        <span class="video-thumbnail">
          ${thumbnail}
          <span class="decision ${decisionClass}">${item.decision}</span>
        </span>
        <span class="result-copy">
          <h3>${escapeHtml(item.video.title)}</h3>
          <p>${escapeHtml(item.video.channel_title)}</p>
          <small>${escapeHtml(item.reasons.join(", "))}</small>
        </span>
      `;
      results.appendChild(card);
    });
  } catch (error) {
    status.textContent = error.message || "Search failed. Check YouTube API configuration.";
  }
  refreshFocus();
}

async function loadYouTubeStatus() {
  const badge = document.querySelector("#youtube-mode");
  try {
    const response = await fetch("/api/youtube/status");
    if (!response.ok) throw new Error(`Status failed: ${response.status}`);
    const data = await response.json();
    badge.textContent = data.mode;
    badge.classList.toggle("live", data.mode === "live");
  } catch (error) {
    badge.textContent = "unknown";
    badge.classList.remove("live");
  }
}

async function loadSearchHistory() {
  const container = document.querySelector("#search-history");
  const clearButton = document.querySelector("#clear-history");
  try {
    const response = await fetch("/api/youtube/history");
    if (!response.ok) throw new Error(`History failed: ${response.status}`);
    const data = await response.json();
    container.innerHTML = "";
    clearButton.hidden = true;
    if (!data.items.length) {
      container.innerHTML = '<p class="history-empty">No searches yet</p>';
      refreshFocus();
      return;
    }
    data.items.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "history-chip";
      button.setAttribute("aria-label", `${item.query}, ${item.mode}, ${item.result_count} results`);
      button.innerHTML = `<span>${escapeHtml(item.query)}</span><small>${escapeHtml(item.mode)} - ${item.result_count} results</small>`;
      button.addEventListener("click", () => runHistorySearch(item.query));
      container.appendChild(button);
    });
  } catch (error) {
    container.innerHTML = '<p class="history-empty">History unavailable</p>';
  }
  refreshFocus();
}

function runHistorySearch(query) {
  const input = document.querySelector("#youtube-query");
  input.value = query;
  input.form.requestSubmit();
}

async function clearSearchHistory() {
  await fetch("/api/youtube/history", { method: "DELETE" });
  loadSearchHistory();
}

function requestViewApproval(video) {
  if (video.video_id.startsWith("demo-")) {
    document.querySelector("#youtube-status").textContent = "Demo result cannot be played. Configure YOUTUBE_API_KEY for live videos.";
    return;
  }
  state.pendingApprovalVideo = video;
  document.querySelector("#view-approval-title").textContent = video.title;
  document.querySelector("#view-approval-pin").value = "";
  document.querySelector("#view-approval-panel").hidden = false;
  document.querySelector("#youtube-status").textContent = "Enter the separate viewing PIN.";
  refreshFocus();
}

function cancelViewApproval() {
  state.pendingApprovalVideo = null;
  document.querySelector("#view-approval-pin").value = "";
  document.querySelector("#view-approval-panel").hidden = true;
  document.querySelector("#youtube-status").textContent = "";
  hideKeyboard();
  refreshFocus();
}

async function unlockViewApproval(event) {
  event.preventDefault();
  hideKeyboard();
  refreshFocus();
  if (!state.pendingApprovalVideo) return;
  const pin = document.querySelector("#view-approval-pin").value.trim();
  const response = await fetch("/api/youtube/approval/unlock", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin, video_id: state.pendingApprovalVideo.video_id }),
  });
  if (!response.ok) {
    document.querySelector("#youtube-status").textContent = "Invalid viewing PIN.";
    return;
  }
  const data = await response.json();
  window.location.href = data.watch_url;
}

async function loadNetworkInfo() {
  const container = document.querySelector("#network-info");
  container.innerHTML = '<p class="history-empty">Checking network...</p>';
  try {
    const response = await fetch("/api/system/network");
    if (!response.ok) throw new Error(`Network info failed: ${response.status}`);
    const data = await response.json();
    container.innerHTML = "";
    const host = document.createElement("div");
    host.className = "network-host";
    host.textContent = `Host: ${data.hostname}`;
    container.appendChild(host);
    data.addresses.forEach((item) => {
      const card = document.createElement("article");
      card.className = "network-card";
      card.innerHTML = `
        <strong>${escapeHtml(item.address)}</strong>
        <span>${escapeHtml(item.portal_url)}</span>
        <code>${escapeHtml(item.ssh_target)}</code>
      `;
      container.appendChild(card);
    });
  } catch (error) {
    container.innerHTML = '<p class="history-empty">Network info unavailable</p>';
  }
  refreshFocus();
}

function openVideo(videoId) {
  if (videoId.startsWith("demo-")) {
    document.querySelector("#youtube-status").textContent = "Demo result cannot be played. Configure YOUTUBE_API_KEY for live videos.";
    return;
  }
  window.location.href = `/youtube/watch/${encodeURIComponent(videoId)}`;
}

function proxiedThumbnailUrl(url) {
  return `/api/youtube/thumbnail?url=${encodeURIComponent(url)}`;
}

async function unlockSettings(event) {
  event.preventDefault();
  hideKeyboard();
  refreshFocus();
  const pin = document.querySelector("#pin").value;
  const response = await fetch("/api/parent/unlock", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin }),
  });
  const status = document.querySelector("#settings-status");
  if (!response.ok) {
    status.textContent = "Invalid PIN.";
    return;
  }
  state.parentPin = pin;
  status.textContent = "Parent settings unlocked.";
  document.querySelector("#parent-panel").hidden = false;
  await loadParentConfig();
  await loadParentStorage();
  await loadParentWifiStatus();
  await loadParentUsage();
  await loadParentMonitoring();
  await loadParentHistorySummary();
  refreshFocus();
}

async function loadParentConfig() {
  const response = await fetch("/api/config");
  state.editableConfig = await response.json();
  renderParentConfig();
}

function renderParentConfig() {
  renderFilterSettings();
  renderSites();
  renderConfigList("allowed_keywords", "#allowed-keywords");
  renderConfigList("blocked_keywords", "#blocked-keywords");
  renderConfigList("approval_keywords", "#approval-keywords");
  renderConfigList("allowed_channels", "#allowed-channels");
  renderConfigList("blocked_channels", "#blocked-channels");
  renderConfigList("blocked_categories", "#blocked-categories");
  renderDisplaySettings();
  refreshFocus();
}

function renderDisplaySettings() {
  const displayMode = document.querySelector("#display-mode");
  if (displayMode) displayMode.value = state.editableConfig.display?.mode || "1080p";
}

function renderFilterSettings() {
  document.querySelector("#daily-minutes").value = state.editableConfig.limits.daily_minutes;
  document.querySelector("#unrestricted-minutes").value = state.editableConfig.parent.default_unrestricted_minutes;
  document.querySelector("#max-duration-seconds").value = state.editableConfig.filtering.max_duration_seconds || "";
  document.querySelector("#youtube-max-results").value = state.editableConfig.youtube.max_results;
  document.querySelector("#youtube-safe-search").value = state.editableConfig.youtube.safe_search;
  document.querySelector("#youtube-region-code").value = state.editableConfig.youtube.region_code;
  document.querySelector("#default-decision").value = state.editableConfig.filtering.default_decision || "REQUIRE_PARENT_APPROVAL";
  document.querySelector("#view-pin").value = "";
}

function syncFilterSettings() {
  state.editableConfig.limits.daily_minutes = clampInteger("#daily-minutes", 1, 1440, 90);
  state.editableConfig.parent.default_unrestricted_minutes = clampInteger("#unrestricted-minutes", 1, 240, 30);
  state.editableConfig.filtering.max_duration_seconds = clampInteger("#max-duration-seconds", 1, 86400, 3600);
  state.editableConfig.youtube.max_results = clampInteger("#youtube-max-results", 1, 25, 20);
  state.editableConfig.youtube.safe_search = normalizeSafeSearch(document.querySelector("#youtube-safe-search").value);
  state.editableConfig.youtube.region_code = normalizeRegionCode(document.querySelector("#youtube-region-code").value);
  state.editableConfig.filtering.default_decision = normalizeDecision(document.querySelector("#default-decision").value);
  renderFilterSettings();
}

function clampInteger(selector, min, max, fallback) {
  const rawValue = document.querySelector(selector).value.trim();
  const value = Number.parseInt(rawValue, 10);
  if (!Number.isFinite(value)) return fallback;
  return Math.min(Math.max(value, min), max);
}

function normalizeSafeSearch(value) {
  const normalized = value.trim().toLowerCase();
  return ["none", "moderate", "strict"].includes(normalized) ? normalized : "strict";
}

function normalizeRegionCode(value) {
  const normalized = value.trim().toUpperCase();
  return /^[A-Z]{2}$/.test(normalized) ? normalized : "US";
}

function normalizeDecision(value) {
  const normalized = value.trim().toUpperCase();
  return ["ALLOW", "BLOCK", "REQUIRE_PARENT_APPROVAL"].includes(normalized)
    ? normalized
    : "REQUIRE_PARENT_APPROVAL";
}

async function loadParentStorage() {
  const container = document.querySelector("#storage-info");
  container.innerHTML = '<p class="history-empty">Checking storage...</p>';
  const response = await fetch("/api/parent/storage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin }),
  });
  if (!response.ok) {
    container.innerHTML = '<p class="history-empty">Storage unavailable</p>';
    return;
  }
  const data = await response.json();
  container.innerHTML = `
    <article class="storage-card">
      <strong>${escapeHtml(formatBytes(data.free_bytes))}</strong>
      <span>Free on ${escapeHtml(data.path)}</span>
    </article>
    <article class="storage-card">
      <strong>${escapeHtml(formatBytes(data.used_bytes))}</strong>
      <span>${escapeHtml(String(data.percent_used))}% used</span>
    </article>
    <article class="storage-card">
      <strong>${escapeHtml(formatBytes(data.total_bytes))}</strong>
      <span>Total capacity</span>
    </article>
  `;
  refreshFocus();
}

async function applyDisplayMode() {
  const status = document.querySelector("#display-status");
  const mode = document.querySelector("#display-mode").value;
  status.textContent = `Switching display to ${mode}...`;
  const response = await fetch("/api/parent/display", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin, mode }),
  });
  if (!response.ok) {
    status.textContent = await responseDetail(response, "Display mode update failed.");
    return;
  }
  const data = await response.json();
  if (!state.editableConfig.display) state.editableConfig.display = {};
  state.editableConfig.display.mode = mode;
  status.textContent = data.current_resolution
    ? `Display switched to ${data.current_resolution}.`
    : `Display mode saved: ${data.configured_mode}.`;
  refreshFocus();
}

async function loadParentWifiStatus() {
  const container = document.querySelector("#wifi-status");
  container.textContent = "Checking Wi-Fi...";
  const response = await fetch("/api/parent/wifi/status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin }),
  });
  if (!response.ok) {
    container.textContent = "Wi-Fi status unavailable.";
    return;
  }
  const data = await response.json();
  container.textContent = data.connection
    ? `Connected: ${data.connection} (${data.state})`
    : `Wi-Fi state: ${data.state}`;
}

async function scanParentWifi() {
  const status = document.querySelector("#wifi-status");
  const list = document.querySelector("#wifi-list");
  status.textContent = "Scanning Wi-Fi...";
  list.innerHTML = "";
  const response = await fetch("/api/parent/wifi/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin }),
  });
  if (!response.ok) {
    status.textContent = await responseDetail(response, "Wi-Fi scan failed.");
    refreshFocus();
    return;
  }
  const data = await response.json();
  if (!data.networks.length) {
    status.textContent = "No Wi-Fi networks found.";
    refreshFocus();
    return;
  }
  status.textContent = `${data.networks.length} Wi-Fi networks found.`;
  data.networks.forEach((network) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "wifi-network";
    button.innerHTML = `
      <strong>${escapeHtml(network.ssid)}</strong>
      <span>${network.signal}%</span>
      <small>${escapeHtml(network.connected ? "Connected" : network.security)}</small>
    `;
    button.addEventListener("click", () => {
      document.querySelector("#wifi-ssid").value = network.ssid;
      document.querySelector("#wifi-password").value = "";
      status.textContent = `Selected ${network.ssid}.`;
      refreshFocus();
    });
    list.appendChild(button);
  });
  refreshFocus();
}

async function connectParentWifi(event) {
  event.preventDefault();
  hideKeyboard();
  refreshFocus();
  const status = document.querySelector("#wifi-status");
  const ssid = document.querySelector("#wifi-ssid").value.trim();
  const password = document.querySelector("#wifi-password").value;
  if (!ssid) {
    status.textContent = "Select or enter SSID.";
    return;
  }
  status.textContent = `Connecting to ${ssid}...`;
  const response = await fetch("/api/parent/wifi/connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin, ssid, password: password || null }),
  });
  if (!response.ok) {
    status.textContent = await responseDetail(response, "Wi-Fi connection failed.");
    return;
  }
  const data = await response.json();
  status.textContent = data.message || "Wi-Fi connection request sent.";
  document.querySelector("#wifi-password").value = "";
  await loadParentWifiStatus();
}

async function loadParentUsage() {
  const container = document.querySelector("#usage-info");
  container.innerHTML = '<p class="history-empty">Checking viewing activity...</p>';
  const response = await fetch("/api/usage/status");
  if (!response.ok) {
    container.innerHTML = '<p class="history-empty">Viewing activity unavailable</p>';
    return;
  }
  const usage = await response.json();
  const usedMinutes = Math.floor(usage.used_seconds / 60);
  const remainingMinutes = Math.ceil(usage.remaining_seconds / 60);
  container.innerHTML = `
    <article class="storage-card">
      <strong>${escapeHtml(String(usedMinutes))} min</strong>
      <span>Used today</span>
    </article>
    <article class="storage-card">
      <strong>${escapeHtml(String(remainingMinutes))} min</strong>
      <span>Remaining</span>
    </article>
    <article class="storage-card">
      <strong>${usage.limit_reached ? "Stop" : "OK"}</strong>
      <span>Playback limit</span>
    </article>
  `;
  refreshFocus();
}

async function loadParentMonitoring() {
  const container = document.querySelector("#monitoring-info");
  container.innerHTML = '<p class="history-empty">Checking processes...</p>';
  const response = await fetch("/api/parent/monitoring", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin }),
  });
  if (!response.ok) {
    container.innerHTML = '<p class="history-empty">Monitoring unavailable</p>';
    return;
  }
  const data = await response.json();
  const hottest = data.hottest_process;
  const rows = data.top_processes.map((process) => `
    <article class="process-row">
      <strong>${escapeHtml(process.command)}</strong>
      <span>${escapeHtml(String(process.pid))}</span>
      <span>${escapeHtml(process.user)}</span>
      <span>${escapeHtml(process.cpu_percent.toFixed(1))}% CPU</span>
      <span>${escapeHtml(process.memory_percent.toFixed(1))}% RAM</span>
    </article>
  `).join("");
  container.innerHTML = `
    <article class="monitor-card">
      <span>Highest load</span>
      <strong>${hottest ? escapeHtml(hottest.command) : "n/a"}</strong>
      <small>${hottest ? `${escapeHtml(hottest.cpu_percent.toFixed(1))}% CPU - PID ${escapeHtml(String(hottest.pid))}` : "No process data"}</small>
    </article>
    <div class="process-list">${rows}</div>
  `;
  refreshFocus();
}

async function loadParentHistorySummary() {
  const container = document.querySelector("#parent-history-info");
  const response = await fetch("/api/youtube/history");
  if (!response.ok) {
    container.textContent = "History unavailable";
    return;
  }
  const data = await response.json();
  container.textContent = `${data.items.length} saved searches`;
  refreshFocus();
}

async function clearParentHistory() {
  const status = document.querySelector("#settings-status");
  status.textContent = "Clearing history...";
  const response = await fetch("/api/admin/youtube/history/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin }),
  });
  status.textContent = response.ok ? "Search history cleared." : "History clear failed.";
  if (response.ok) {
    await loadSearchHistory();
    await loadParentHistorySummary();
  }
}

async function startTerminalMode() {
  const status = document.querySelector("#settings-status");
  status.textContent = "Switching to terminal...";
  const response = await fetch("/api/parent/terminal/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin }),
  });
  status.textContent = response.ok ? "Terminal mode starting." : "Terminal mode failed.";
}

async function startKioskMode() {
  const status = document.querySelector("#settings-status");
  status.textContent = "Starting kiosk...";
  const response = await fetch("/api/parent/kiosk/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin }),
  });
  status.textContent = response.ok ? "Kiosk starting." : "Kiosk start failed.";
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

function renderSites() {
  const container = document.querySelector("#site-list");
  container.innerHTML = "";
  state.editableConfig.allowed_sites.forEach((site, index) => {
    const item = document.createElement("article");
    item.className = "admin-item";
    item.innerHTML = `
      <strong>${escapeHtml(site.label)}</strong>
      <span>${escapeHtml(site.domain)}</span>
      <button type="button" data-remove-site="${index}">Remove</button>
    `;
    container.appendChild(item);
  });
  container.querySelectorAll("[data-remove-site]").forEach((button) => {
    button.addEventListener("click", () => {
      state.editableConfig.allowed_sites.splice(Number(button.dataset.removeSite), 1);
      renderParentConfig();
    });
  });
}

function renderConfigList(field, selector) {
  const container = document.querySelector(selector);
  container.innerHTML = "";
  state.editableConfig.filtering[field].forEach((value, index) => {
    const item = document.createElement("article");
    item.className = "admin-item compact";
    item.innerHTML = `
      <strong>${escapeHtml(value)}</strong>
      <button type="button" data-remove-field="${field}" data-remove-index="${index}">Remove</button>
    `;
    container.appendChild(item);
  });
  container.querySelectorAll("[data-remove-field]").forEach((button) => {
    button.addEventListener("click", () => {
      const fieldName = button.dataset.removeField;
      state.editableConfig.filtering[fieldName].splice(Number(button.dataset.removeIndex), 1);
      renderParentConfig();
    });
  });
}

function addUniqueConfigValue(field, value) {
  const normalized = value.trim();
  if (!normalized) return;
  const list = state.editableConfig.filtering[field];
  if (!list.some((item) => item.toLowerCase() === normalized.toLowerCase())) {
    list.push(normalized);
  }
}

async function saveParentConfig() {
  const status = document.querySelector("#settings-status");
  syncFilterSettings();
  const viewPin = document.querySelector("#view-pin").value.trim();
  if (viewPin && !/^\d{4,12}$/.test(viewPin)) {
    status.textContent = "Viewing PIN must be 4-12 digits.";
    return;
  }
  status.textContent = "Saving rules...";
  const response = await fetch("/api/parent/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pin: state.parentPin, config: state.editableConfig, view_pin: viewPin || null }),
  });
  status.textContent = response.ok ? "Rules saved." : "Save failed.";
  if (response.ok) {
    document.querySelector("#view-pin").value = "";
    loadTiles();
  }
}

async function responseDetail(response, fallback) {
  try {
    const payload = await response.json();
    return payload.detail || fallback;
  } catch (error) {
    return fallback;
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[char]));
}

function showKeyboard(input) {
  const keyboard = document.querySelector("#keyboard");
  const alreadyOpenForInput = !keyboard.hidden && state.activeInput === input;
  if (alreadyOpenForInput) return;
  state.activeInput = input;
  state.keyboardMode = keyboardModeForInput(input);
  document.body.classList.add("keyboard-open");
  keyboard.hidden = false;
  renderKeyboard();
  refreshFocus();
}

function hideKeyboard() {
  document.body.classList.remove("keyboard-open");
  document.querySelector("#keyboard").hidden = true;
  state.activeInput = null;
}

function renderKeyboard() {
  const keys = document.querySelector("#keyboard-keys");
  const preview = document.querySelector("#keyboard-preview");
  const input = state.activeInput;
  preview.textContent = input ? input.value || input.placeholder : "";
  keys.innerHTML = "";
  const layout = state.keyboardMode === "text"
    ? keyboardLayouts.text[state.keyboardLanguage]
    : keyboardLayouts.numeric;
  layout.forEach((row) => {
    const rowNode = document.createElement("div");
    rowNode.className = "keyboard-row";
    if (row.some((key) => ["Space", "Enter", "Hide", "Clear", "Back", "RU", "EN"].includes(key))) {
      rowNode.classList.add("keyboard-row-actions");
    }
    row.forEach((key) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "keyboard-key";
      button.dataset.key = key;
      button.textContent = key;
      if (["Space", "Clear", "Enter", "Hide", "RU", "EN"].includes(key)) {
        button.classList.add("wide");
      }
      if (["RU", "EN"].includes(key)) {
        button.classList.add("language-key");
      }
      if (key === "Space") {
        button.classList.add("space-key");
      }
      if (key === "Enter") {
        button.classList.add("enter-key");
      }
      button.addEventListener("click", () => pressKeyboardKey(key));
      rowNode.appendChild(button);
    });
    keys.appendChild(rowNode);
  });
}

function pressKeyboardKey(key) {
  const input = state.activeInput;
  if (!input) return;
  if (key === "Hide") {
    hideKeyboard();
    refreshFocus();
    return;
  }
  if (key === "RU" || key === "EN") {
    state.keyboardLanguage = key === "RU" ? "ru" : "en";
    renderKeyboard();
    refreshFocus();
    return;
  }
  if (key === "Enter") {
    if (input.form) {
      input.form.requestSubmit();
    } else {
      hideKeyboard();
      refreshFocus();
    }
    return;
  }
  if (key === "Back") {
    input.value = input.value.slice(0, -1);
  } else if (key === "Clear") {
    input.value = "";
  } else if (key === "Space") {
    input.value += " ";
  } else {
    input.value += key;
  }
  renderKeyboard();
  refreshFocus();
}

function shouldUseKeyboard(input) {
  if (!(input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement)) return false;
  if (input.disabled || input.readOnly) return false;
  if (input.dataset.keyboard === "off") return false;
  if (input instanceof HTMLTextAreaElement) return true;
  return !["button", "checkbox", "color", "file", "hidden", "image", "radio", "range", "reset", "submit"].includes(input.type);
}

function keyboardModeForInput(input) {
  if (input.dataset.keyboard) return input.dataset.keyboard;
  if (input.inputMode === "numeric" || input.type === "number" || input.type === "tel") return "numeric";
  return "text";
}

function bindKeyboardInput(input) {
  if (!shouldUseKeyboard(input) || input.dataset.keyboardBound === "true") return;
  input.dataset.keyboardBound = "true";
  input.addEventListener("focus", () => showKeyboard(input));
  input.addEventListener("click", () => showKeyboard(input));
  input.addEventListener("input", renderKeyboard);
}

document.addEventListener("keydown", (event) => {
  const targetElement = event.target;
  const isTextInput = targetElement instanceof HTMLInputElement || targetElement instanceof HTMLTextAreaElement;
  const isKeyboardOpen = !document.querySelector("#keyboard").hidden;
  if (isTextInput && !event.altKey && !event.ctrlKey && !event.metaKey) {
    if (event.key === "Escape") {
      event.preventDefault();
      if (isKeyboardOpen) {
        hideKeyboard();
        refreshFocus();
      } else {
        targetElement.blur();
        refreshFocus();
      }
      return;
    }
    if (isKeyboardOpen && ["ArrowRight", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      moveFocus(1);
      return;
    }
    if (isKeyboardOpen && ["ArrowLeft", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      moveFocus(-1);
      return;
    }
    return;
  }

  if (["ArrowRight", "ArrowDown"].includes(event.key)) {
    event.preventDefault();
    moveFocus(1);
  }
  if (["ArrowLeft", "ArrowUp"].includes(event.key)) {
    event.preventDefault();
    moveFocus(-1);
  }
  if (["Enter", " "].includes(event.key)) {
    const target = state.focusables[state.focusedIndex];
    if (target && shouldUseKeyboard(target)) {
      event.preventDefault();
      showKeyboard(target);
    } else if (target) {
      event.preventDefault();
      target.click();
    }
  }
  if (["Escape", "Backspace"].includes(event.key)) {
    event.preventDefault();
    if (!document.querySelector("#keyboard").hidden) {
      hideKeyboard();
      refreshFocus();
    } else {
      showView("home");
    }
  }
});

document.addEventListener("focusin", (event) => {
  if (shouldUseKeyboard(event.target)) bindKeyboardInput(event.target);
});
document.addEventListener("click", (event) => {
  if (shouldUseKeyboard(event.target)) bindKeyboardInput(event.target);
});
document.querySelectorAll("input, textarea").forEach((input) => {
  bindKeyboardInput(input);
});
document.querySelectorAll("[data-back]").forEach((button) => {
  button.addEventListener("click", () => showView("home"));
});
document.querySelectorAll("[data-home]").forEach((button) => {
  button.addEventListener("click", () => showView("home"));
});
document.querySelectorAll("[data-settings]").forEach((button) => {
  button.addEventListener("click", openSettings);
});
document.querySelector("#youtube-search").addEventListener("submit", searchYouTube);
document.querySelector("#view-approval-form").addEventListener("submit", unlockViewApproval);
document.querySelector("#cancel-view-approval").addEventListener("click", cancelViewApproval);
document.querySelector("#clear-history").addEventListener("click", clearSearchHistory);
document.querySelector("#refresh-network").addEventListener("click", loadNetworkInfo);
document.querySelector("#refresh-storage").addEventListener("click", loadParentStorage);
document.querySelector("#apply-display-mode").addEventListener("click", applyDisplayMode);
document.querySelector("#scan-wifi").addEventListener("click", scanParentWifi);
document.querySelector("#wifi-form").addEventListener("submit", connectParentWifi);
document.querySelector("#refresh-usage").addEventListener("click", loadParentUsage);
document.querySelector("#refresh-monitoring").addEventListener("click", loadParentMonitoring);
document.querySelector("#clear-parent-history").addEventListener("click", clearParentHistory);
document.querySelector("#exit-to-terminal").addEventListener("click", startTerminalMode);
document.querySelector("#return-to-kiosk").addEventListener("click", startKioskMode);
document.querySelector("#pin-form").addEventListener("submit", unlockSettings);
document.querySelector("#save-config").addEventListener("click", saveParentConfig);
document.querySelector("#site-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!state.editableConfig) return;
  const label = document.querySelector("#site-label").value.trim();
  const domain = document.querySelector("#site-domain").value.trim();
  const url = document.querySelector("#site-url").value.trim();
  if (!label || !domain || !url) return;
  state.editableConfig.allowed_sites.push({ label, domain, url });
  document.querySelector("#site-label").value = "";
  document.querySelector("#site-domain").value = "";
  document.querySelector("#site-url").value = "";
  renderParentConfig();
});
document.querySelectorAll("[data-list-form]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!state.editableConfig) return;
    const input = form.querySelector("input");
    addUniqueConfigValue(form.dataset.listForm, input.value);
    input.value = "";
    renderParentConfig();
  });
});
document.addEventListener("contextmenu", (event) => event.preventDefault());

async function bootPortal() {
  await loadTiles();
  if (window.location.hash === "#youtube") {
    showView("youtube");
    loadYouTubeStatus();
    loadSearchHistory();
    history.replaceState(null, "", "/");
  }
}

bootPortal();
