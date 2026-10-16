/* Chat widget: injects its markup into the page and talks to the FastAPI gateway.
   Needs site.js (theme) and voice.js. Exposes window.KQChat.open(message?, label?).
   All bot and user text is inserted with textContent, never innerHTML. */
(function () {
  "use strict";

  const API_BASE = window.KQ_CHAT_API_BASE || "";
  const HEALTH_INTERVAL_MS = 30000;
  const STORAGE = {
    session: "kq-chat-session",
    transcript: "kq-chat-transcript",
    open: "kq-chat-open",
    tts: "kq-chat-tts",
    seen: "kq-assistant-seen",
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

  // Static, trusted markup for the launcher and panel
  const WIDGET_HTML = `
<button id="chat-launcher" class="launcher" type="button" aria-label="Chat with us"
        aria-haspopup="dialog" aria-controls="chat-panel" aria-expanded="false">
  <svg aria-hidden="true" viewBox="0 0 24 24" width="26" height="26" focusable="false">
    <path fill="currentColor" d="M4 4h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H8l-4 4V6a2 2 0 0 1 2-2z"/>
  </svg>
  <span class="launcher__label">Chat with us</span>
  <span class="pill-new launcher__new" id="launcher-new">New</span>
</button>

<section id="chat-panel" class="chat" role="dialog" aria-modal="false"
         aria-labelledby="chat-title" hidden>
  <header class="chat__header">
    <div class="chat__identity">
      <span class="chat__avatar" aria-hidden="true">KQ</span>
      <div>
        <h2 id="chat-title" class="chat__title">Virtual Assistant</h2>
        <p class="chat__status" id="chat-status">
          <span class="chat__status-dot" aria-hidden="true"></span>
          <span id="chat-status-text">Connecting…</span>
        </p>
      </div>
    </div>
    <div class="chat__tools">
      <button type="button" class="icon-btn" id="tts-toggle" aria-pressed="false"
              title="Read replies aloud">
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" focusable="false">
          <path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 8v8a4.5 4.5 0 0 0 2.5-4z"/>
        </svg>
        <span class="visually-hidden">Read replies aloud</span>
      </button>
      <button type="button" class="icon-btn" id="contrast-toggle" aria-pressed="false"
              title="High contrast">
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" focusable="false">
          <path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 18V4a8 8 0 0 1 0 16z"/>
        </svg>
        <span class="visually-hidden">High contrast</span>
      </button>
      <button type="button" class="icon-btn" id="restart-btn" title="Start a new conversation">
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" focusable="false">
          <path fill="currentColor" d="M17.65 6.35A8 8 0 1 0 19.73 14h-2.08A6 6 0 1 1 12 6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
        </svg>
        <span class="visually-hidden">Start a new conversation</span>
      </button>
      <button type="button" class="icon-btn" id="close-btn" title="Close chat">
        <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" focusable="false">
          <path fill="currentColor" d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
        </svg>
        <span class="visually-hidden">Close chat</span>
      </button>
    </div>
  </header>

  <div class="chat__log" id="chat-log" role="log" aria-live="polite" aria-relevant="additions"
       aria-label="Conversation" tabindex="0"></div>

  <p class="chat__typing" id="chat-typing" hidden>
    <span class="dots" aria-hidden="true"><span></span><span></span><span></span></span>
    <span class="visually-hidden">The assistant is typing</span>
  </p>

  <form class="chat__composer" id="chat-form" autocomplete="off">
    <label for="chat-input" class="visually-hidden">Type your message</label>
    <input id="chat-input" name="message" type="text" maxlength="500"
           placeholder="Type your message…" aria-describedby="chat-hint" required>
    <button type="button" class="icon-btn icon-btn--mic" id="mic-btn" aria-pressed="false"
            title="Speak your message" hidden>
      <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" focusable="false">
        <path fill="currentColor" d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/>
      </svg>
      <span class="visually-hidden">Speak your message</span>
    </button>
    <button type="submit" class="send-btn" id="send-btn">
      <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20" focusable="false">
        <path fill="currentColor" d="M2 21 23 12 2 3v7l15 2-15 2z"/>
      </svg>
      <span class="visually-hidden">Send</span>
    </button>
  </form>
  <p class="chat__hint" id="chat-hint">Press Enter to send. Type “agent” at any time to reach a person.</p>
</section>`;
  document.body.insertAdjacentHTML("beforeend", WIDGET_HTML);

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
    // Earlier suggestions no longer apply once the conversation moves on
    el.log.querySelectorAll(".quick-replies .chip").forEach((chip) => (chip.disabled = true));
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
    save(localStorage, STORAGE.seen, true);
    const badge = document.getElementById("launcher-new");
    if (badge) badge.remove();
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

  function ttsEnabled() {
    return el.tts.getAttribute("aria-pressed") === "true";
  }

  // The theme is shared with the page header (site.js)
  const syncContrast = (on) => el.contrast.setAttribute("aria-pressed", String(on));
  syncContrast(window.KQTheme.isHighContrast());
  window.KQTheme.onChange(syncContrast);
  el.contrast.addEventListener("click", window.KQTheme.toggle);

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

  if (load(localStorage, STORAGE.seen, false)) {
    const badge = document.getElementById("launcher-new");
    if (badge) badge.remove();
  }

  // Reopen after a page reload if a conversation was in progress and the panel was open
  if (senderId && load(sessionStorage, STORAGE.open, false)) openChat();

  window.KQChat = {
    /** Open the assistant, optionally sending a message (label is what the passenger sees). */
    open(message, label) {
      if (el.panel.hidden) openChat();
      if (message) sendMessage(message, label || message);
    },
    /** Forget the conversation, e.g. when a passenger logs out. */
    clear() {
      [STORAGE.session, STORAGE.transcript, STORAGE.open].forEach((key) => save(sessionStorage, key, null));
    },
  };
})();
