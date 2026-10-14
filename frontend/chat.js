/* Chat widget client: talks to the FastAPI gateway (backend/main.py).
   All bot text is inserted with textContent, never innerHTML. */
(function () {
  "use strict";

  const API_BASE = window.KQ_CHAT_API_BASE || "";
  const HEALTH_INTERVAL_MS = 30000;
  const STORAGE = {
    session: "kq-chat-session",
    transcript: "kq-chat-transcript",
    open: "kq-chat-open",
    theme: "kq-chat-theme",
    tts: "kq-chat-tts",
  };
  const WELCOME = {
    text: "Hello! I'm the Kenya Airways virtual assistant. How can I help you today?",
    buttons: [
      { title: "Flight Status", payload: "/check_flight_status" },
      { title: "Baggage", payload: "/baggage_policy" },
      { title: "Change Booking", payload: "/change_booking" },
      { title: "Check-In", payload: "/check_in_procedure" },
    ],
  };

  const $ = (id) => document.getElementById(id);
  const el = {
    launcher: $("chat-launcher"),
    panel: $("chat-panel"),
    log: $("chat-log"),
    typing: $("chat-typing"),
    form: $("chat-form"),
    input: $("chat-input"),
    send: $("send-btn"),
    mic: $("mic-btn"),
    tts: $("tts-toggle"),
    contrast: $("contrast-toggle"),
    restart: $("restart-btn"),
    close: $("close-btn"),
    status: $("chat-status"),
    statusText: $("chat-status-text"),
  };

  let busy = false;
  let healthTimer = null;
  let lastFailedMessage = null;

  // ---------- storage helpers (storage can be unavailable, e.g. private mode) ----------

  function load(store, key, fallback) {
    try {
      const value = store.getItem(key);
      return value === null ? fallback : JSON.parse(value);
    } catch (_) {
      return fallback;
    }
  }

  function save(store, key, value) {
    try {
      if (value === null) store.removeItem(key);
      else store.setItem(key, JSON.stringify(value));
    } catch (_) { /* non-essential */ }
  }

  let senderId = load(sessionStorage, STORAGE.session, null);
  let transcript = load(sessionStorage, STORAGE.transcript, []);

  // ---------- rendering ----------

  function scrollToBottom() {
    el.log.scrollTop = el.log.scrollHeight;
  }

  function renderMessage({ from, text, buttons }, { interactive = true } = {}) {
    if (text) {
      const bubble = document.createElement("p");
      bubble.className = `msg msg--${from}`;
      const speaker = document.createElement("span");
      speaker.className = "visually-hidden";
      speaker.textContent = from === "user" ? "You said: " : from === "bot" ? "Assistant: " : "";
      bubble.append(speaker, document.createTextNode(text));
      el.log.append(bubble);
    }
    if (buttons && buttons.length) {
      const list = document.createElement("ul");
      list.className = "quick-replies";
      list.setAttribute("aria-label", "Suggested replies");
      for (const button of buttons) {
        const item = document.createElement("li");
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip";
        chip.textContent = button.title;
        chip.disabled = !interactive;
        chip.addEventListener("click", () => {
          list.querySelectorAll("button").forEach((b) => (b.disabled = true));
          sendMessage(button.payload, button.title);
        });
        item.append(chip);
        list.append(item);
      }
      el.log.append(list);
    }
    scrollToBottom();
  }

  function addMessage(message) {
    renderMessage(message);
    transcript.push(message);
    save(sessionStorage, STORAGE.transcript, transcript);
  }

  function renderError(text, retryable) {
    const box = document.createElement("div");
    box.className = "msg msg--error";
    box.setAttribute("role", "alert");
    box.textContent = text;
    if (retryable) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "chip chip--inline";
      retry.textContent = "Try again";
      retry.addEventListener("click", () => {
        box.remove();
        if (lastFailedMessage) sendMessage(lastFailedMessage.payload, lastFailedMessage.display, { echo: false });
      });
      box.append(retry);
    }
    el.log.append(box);
    scrollToBottom();
  }

  function restoreTranscript() {
    el.log.replaceChildren();
    if (!transcript.length) {
      addMessage({ from: "bot", ...WELCOME });
      return;
    }
    // Earlier quick replies are shown but no longer clickable, except the latest set
    transcript.forEach((message, index) =>
      renderMessage(message, { interactive: index === transcript.length - 1 })
    );
  }

  function setBusy(value) {
    busy = value;
    el.typing.hidden = !value;
    el.send.disabled = value;
    el.log.setAttribute("aria-busy", String(value));
    if (value) scrollToBottom();
  }

  // ---------- API ----------

  async function sendMessage(payload, display = payload, { echo = true } = {}) {
    if (busy || !payload.trim()) return;
    if (echo) addMessage({ from: "user", text: display });
    setBusy(true);
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(senderId ? { message: payload, sender_id: senderId } : { message: payload }),
      });
      if (response.status === 422) {
        renderError("Sorry, that message couldn't be sent. Please keep it under 500 characters.", false);
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      senderId = data.sender_id;
      save(sessionStorage, STORAGE.session, senderId);
      lastFailedMessage = null;
      setOnline(true);

      if (!data.messages.length) {
        addMessage({ from: "bot", text: "Sorry, I don't have an answer for that. Type 'agent' to reach a person." });
      }
      for (const message of data.messages) {
        addMessage({ from: "bot", text: message.text, buttons: message.buttons });
        if (ttsEnabled() && message.text) window.KQVoice.speak(message.text);
      }
    } catch (error) {
      lastFailedMessage = { payload, display };
      setOnline(false);
      renderError("The assistant is temporarily unavailable. Please check your connection and try again.", true);
    } finally {
      setBusy(false);
      el.input.focus();
    }
  }

  function setOnline(online) {
    el.status.dataset.state = online ? "online" : "offline";
    el.statusText.textContent = online ? "Online" : "Offline";
  }

  async function checkHealth() {
    try {
      const response = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
      setOnline(response.ok);
    } catch (_) {
      setOnline(false);
    }
  }

  async function restartConversation() {
    window.KQVoice.cancelSpeech();
    if (senderId) {
      fetch(`${API_BASE}/api/chat/${senderId}/end`, { method: "POST" }).catch(() => {});
    }
    senderId = null;
    transcript = [];
    save(sessionStorage, STORAGE.session, null);
    save(sessionStorage, STORAGE.transcript, null);
    restoreTranscript();
    el.input.focus();
  }

  // ---------- panel open / close ----------

  function openChat() {
    el.panel.hidden = false;
    el.launcher.setAttribute("aria-expanded", "true");
    save(sessionStorage, STORAGE.open, true);
    if (!el.log.childElementCount) restoreTranscript();
    checkHealth();
    healthTimer = setInterval(checkHealth, HEALTH_INTERVAL_MS);
    el.input.focus();
  }

  function closeChat() {
    el.panel.hidden = true;
    el.launcher.setAttribute("aria-expanded", "false");
    save(sessionStorage, STORAGE.open, null);
    clearInterval(healthTimer);
    window.KQVoice.stopListening();
    window.KQVoice.cancelSpeech();
    el.launcher.focus();
  }

  // ---------- accessibility preferences ----------

  function applyTheme(highContrast) {
    if (highContrast) document.documentElement.dataset.theme = "high-contrast";
    else delete document.documentElement.dataset.theme;
    el.contrast.setAttribute("aria-pressed", String(highContrast));
  }

  function ttsEnabled() {
    return el.tts.getAttribute("aria-pressed") === "true";
  }

  const prefersMoreContrast = window.matchMedia && window.matchMedia("(prefers-contrast: more)").matches;
  applyTheme(load(localStorage, STORAGE.theme, prefersMoreContrast));
  el.contrast.addEventListener("click", () => {
    const next = el.contrast.getAttribute("aria-pressed") !== "true";
    applyTheme(next);
    save(localStorage, STORAGE.theme, next);
  });

  if (window.KQVoice.synthesisSupported) {
    el.tts.setAttribute("aria-pressed", String(load(localStorage, STORAGE.tts, false)));
    el.tts.addEventListener("click", () => {
      const next = !ttsEnabled();
      el.tts.setAttribute("aria-pressed", String(next));
      save(localStorage, STORAGE.tts, next);
      if (!next) window.KQVoice.cancelSpeech();
    });
  } else {
    el.tts.hidden = true;
  }

  // ---------- voice input ----------

  if (window.KQVoice.recognitionSupported) {
    el.mic.hidden = false;
    el.mic.addEventListener("click", () => {
      if (el.mic.getAttribute("aria-pressed") === "true") {
        window.KQVoice.stopListening();
        return;
      }
      el.mic.setAttribute("aria-pressed", "true");
      el.input.placeholder = "Listening…";
      window.KQVoice.listen({
        onInterim: (text) => (el.input.value = text),
        onFinal: (text) => {
          el.input.value = "";
          sendMessage(text);
        },
        onError: (error) => {
          if (error === "not-allowed" || error === "service-not-allowed") {
            renderError("Microphone access was blocked. Allow it in your browser settings to speak your message.", false);
          }
        },
        onEnd: () => {
          el.mic.setAttribute("aria-pressed", "false");
          el.input.placeholder = "Type your message…";
        },
      });
    });
  }

  // ---------- events ----------

  el.launcher.addEventListener("click", openChat);
  el.close.addEventListener("click", closeChat);
  el.restart.addEventListener("click", restartConversation);
  el.panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeChat();
  });
  el.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = el.input.value.trim();
    if (!text) return;
    el.input.value = "";
    sendMessage(text);
  });

  // Reopen after a page reload if a conversation was in progress and the panel was open
  if (senderId && load(sessionStorage, STORAGE.open, false)) openChat();
})();
