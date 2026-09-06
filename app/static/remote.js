const state = {
  pin: sessionStorage.getItem("kidPortalRemotePin") || "",
  busy: false,
};

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
  setStatus(remoteStatus, "Ready");
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
  await postJson("/api/admin/state", { pin });
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
    if (error.message.includes("Invalid PIN") || error.message.includes("locked")) {
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

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  unlock(pinInput.value.trim());
});

document.querySelector("#lock-remote").addEventListener("click", () => {
  sessionStorage.removeItem("kidPortalRemotePin");
  state.pin = "";
  showLogin("Remote locked");
});

document.querySelectorAll("[data-key]").forEach((button) => {
  button.addEventListener("click", () => sendKey(button.dataset.key, button));
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
  sendKey(key);
});

if (state.pin) {
  unlock(state.pin);
} else {
  showLogin();
}
