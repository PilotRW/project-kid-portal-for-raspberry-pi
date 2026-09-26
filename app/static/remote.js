const state = {
  pin: sessionStorage.getItem("kidPortalRemotePin") || "",
  busy: false,
  pointerBusy: false,
  controlMode: localStorage.getItem("kidPortalRemoteMode") === "cursor" ? "cursor" : "navigation",
};

let pointerRepeatDelay = null;
let pointerRepeatTimer = null;

const login = document.querySelector("#remote-login");
const panel = document.querySelector("#remote-panel");
const loginForm = document.querySelector("#login-form");
const loginStatus = document.querySelector("#login-status");
const remoteStatus = document.querySelector("#remote-status");
const pinInput = document.querySelector("#pin");
const typeForm = document.querySelector("#type-form");
const textInput = document.querySelector("#remote-text");

function setStatus(node, message, isError = false) {
  node.textContent = message;
  node.classList.toggle("is-error", isError);
}

function showPanel() {
  login.hidden = true;
  panel.hidden = false;
  applyControlMode(state.controlMode);
}

function showLogin(message = "") {
  panel.hidden = true;
  login.hidden = false;
  pinInput.value = "";
  pinInput.focus();
  setStatus(loginStatus, message);
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let message = "Request failed";
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json();
}

async function verifyPin(pin) {
  await postJson("/api/remote/unlock", { pin });
}

async function unlock(pin) {
  setStatus(loginStatus, "Checking PIN...");
  try {
    await verifyPin(pin);
    state.pin = pin;
    sessionStorage.setItem("kidPortalRemotePin", pin);
    showPanel();
  } catch (error) {
    sessionStorage.removeItem("kidPortalRemotePin");
    state.pin = "";
    setStatus(loginStatus, error.message, true);
  }
}

async function sendKey(key, sourceButton = null) {
  if (!state.pin || state.busy) return;
  state.busy = true;
  sourceButton?.classList.add("is-pressed");
  setStatus(remoteStatus, "Sending...");
  try {
    await postJson("/api/remote/key", { pin: state.pin, key });
    setStatus(remoteStatus, "Sent");
  } catch (error) {
    if (error.message.includes("Invalid remote PIN") || error.message.includes("locked")) {
      sessionStorage.removeItem("kidPortalRemotePin");
      state.pin = "";
      showLogin(error.message);
    } else {
      setStatus(remoteStatus, error.message, true);
    }
  } finally {
    window.setTimeout(() => sourceButton?.classList.remove("is-pressed"), 120);
    state.busy = false;
  }
}

async function sendText(text) {
  const trimmed = text.trim();
  if (!trimmed || !state.pin) return;
  setStatus(remoteStatus, "Typing...");
  try {
    await postJson("/api/remote/type", { pin: state.pin, text: trimmed });
    textInput.value = "";
    setStatus(remoteStatus, "Text sent");
  } catch (error) {
    setStatus(remoteStatus, error.message, true);
  }
}

async function sendPointer(action, sourceButton = null) {
  if (!state.pin || state.pointerBusy) return;
  state.pointerBusy = true;
  sourceButton?.classList.add("is-pressed");
  try {
    await postJson("/api/remote/pointer", { pin: state.pin, action });
    setStatus(remoteStatus, action === "click" ? "Clicked" : "Cursor moved");
  } catch (error) {
    if (error.message.includes("Invalid remote PIN") || error.message.includes("locked")) {
      sessionStorage.removeItem("kidPortalRemotePin");
      state.pin = "";
      showLogin(error.message);
    } else {
      setStatus(remoteStatus, error.message, true);
    }
  } finally {
    window.setTimeout(() => sourceButton?.classList.remove("is-pressed"), 90);
    state.pointerBusy = false;
  }
}

function applyControlMode(mode) {
  state.controlMode = mode === "cursor" ? "cursor" : "navigation";
  localStorage.setItem("kidPortalRemoteMode", state.controlMode);
  panel.dataset.controlMode = state.controlMode;
  document.querySelectorAll("[data-control-mode]").forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.controlMode === state.controlMode ? "true" : "false");
  });
  setStatus(remoteStatus, state.controlMode === "cursor" ? "Cursor mode" : "Navigation mode");
}

function stopPointerRepeat() {
  window.clearTimeout(pointerRepeatDelay);
  window.clearInterval(pointerRepeatTimer);
  pointerRepeatDelay = null;
  pointerRepeatTimer = null;
}

function startPointerRepeat(button) {
  const action = button.dataset.pointer;
  if (state.controlMode !== "cursor" || !action) return;
  button.dataset.pointerHandled = "true";
  sendPointer(action, button);
  if (action === "click") return;
  pointerRepeatDelay = window.setTimeout(() => {
    pointerRepeatTimer = window.setInterval(() => sendPointer(action, button), 95);
  }, 280);
}

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  unlock(pinInput.value.trim());
});

document.querySelector("#lock-remote").addEventListener("click", () => {
  sessionStorage.removeItem("kidPortalRemotePin");
  state.pin = "";
  showLogin("Remote locked");
});

document.querySelectorAll("[data-control-mode]").forEach((button) => {
  button.addEventListener("click", () => applyControlMode(button.dataset.controlMode));
});

document.querySelectorAll("[data-key], [data-pointer]").forEach((button) => {
  button.addEventListener("pointerdown", (event) => {
    if (state.controlMode !== "cursor" || !button.dataset.pointer) return;
    event.preventDefault();
    startPointerRepeat(button);
  });
  ["pointerup", "pointercancel", "pointerleave"].forEach((eventName) => {
    button.addEventListener(eventName, stopPointerRepeat);
  });
  button.addEventListener("click", (event) => {
    if (state.controlMode === "cursor" && button.dataset.pointer) {
      event.preventDefault();
      if (button.dataset.pointerHandled === "true") {
        delete button.dataset.pointerHandled;
        return;
      }
      sendPointer(button.dataset.pointer, button);
      return;
    }
    if (button.dataset.key) sendKey(button.dataset.key, button);
  });
});

typeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendText(textInput.value);
});

document.addEventListener("keydown", (event) => {
  const targetIsInput = event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement;
  if (targetIsInput && event.target !== document.body) return;
  const map = {
    ArrowUp: "up",
    ArrowDown: "down",
    ArrowLeft: "left",
    ArrowRight: "right",
    Enter: "ok",
    Escape: "back",
    Backspace: "back",
    " ": "play_pause",
  };
  const key = map[event.key];
  if (!key || panel.hidden) return;
  event.preventDefault();
  const pointerAction = key === "ok" ? "click" : key;
  if (state.controlMode === "cursor" && ["up", "down", "left", "right", "click"].includes(pointerAction)) {
    sendPointer(pointerAction);
  } else {
    sendKey(key);
  }
});

if (state.pin) {
  unlock(state.pin);
} else {
  showLogin();
}
