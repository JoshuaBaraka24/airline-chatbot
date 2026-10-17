/* Shared page chrome: header, footer, logo, login state and theme.
   Exposes window.KQSite and window.KQTheme. Load after api.js. */
(function () {
  "use strict";

  const THEME_KEY = "kq-chat-theme";

  const ICONS = {
    contrast: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="22" height="22"><path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 18V4a8 8 0 0 1 0 16z"/></svg>',
    menu: '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="24" height="24"><path fill="currentColor" d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"/></svg>',
  };

  // ---------- theme (shared with the chat widget) ----------

  const themeListeners = [];
  function storedTheme() {
    try {
      const value = localStorage.getItem(THEME_KEY);
      if (value !== null) return JSON.parse(value);
    } catch (_) { /* storage unavailable */ }
    return Boolean(window.matchMedia && window.matchMedia("(prefers-contrast: more)").matches);
  }
  function setTheme(highContrast, persist = true) {
    if (highContrast) document.documentElement.dataset.theme = "high-contrast";
    else delete document.documentElement.dataset.theme;
    if (persist) {
      try { localStorage.setItem(THEME_KEY, JSON.stringify(highContrast)); } catch (_) { /* ignore */ }
    }
    themeListeners.forEach((fn) => fn(highContrast));
  }
  window.KQTheme = {
    isHighContrast: () => document.documentElement.dataset.theme === "high-contrast",
    set: setTheme,
    toggle: () => setTheme(!window.KQTheme.isHighContrast()),
    onChange: (fn) => themeListeners.push(fn),
  };
  setTheme(storedTheme(), false);

  // ---------- header and footer ----------

  const page = document.body.dataset.page || "home";

  function navLink(href, label, key, extra = "") {
    const current = key === page ? ' aria-current="page"' : "";
    return `<li><a class="nav__link" href="${href}"${current}>${label}${extra}</a></li>`;
  }

  function renderHeader(user) {
    const slot = document.getElementById("site-header");
    if (!slot) return;
    const links = [
      navLink("index.html", "Home", "home"),
      navLink("flight-status.html", "Flight status", "status"),
      navLink("destinations.html", "Destinations", "destinations"),
      navLink("travel-info.html", "Travel info", "info"),
      navLink("assistant.html", "Virtual Assistant", "assistant", ' <span class="pill-new">New</span>'),
    ];
    if (user && user.role === "passenger") links.push(navLink("account.html", "My bookings", "account"));
    if (user && user.role === "admin") links.push(navLink("admin.html", "Staff dashboard", "admin"));

    const account = user
      ? `<span class="user-chip"><span class="user-chip__avatar" aria-hidden="true"></span>
           <span class="user-chip__name"></span></span>
         <button type="button" class="btn btn--light btn--small" id="logout-btn">Log out</button>`
      : `<a class="btn btn--gold btn--small" href="login.html" id="login-link">Log in</a>`;

    slot.outerHTML = `
      <header class="site-header">
        <div class="container site-header__bar">
          <a class="brand" href="index.html" aria-label="Kenya Airways, home">
            <span class="brand__badge"><img class="brand__logo" src="assets/logo.svg" alt="" width="180" height="41"></span>
            <span class="brand__product">Virtual<br>Assistant</span>
          </a>
          <nav class="nav" id="site-nav" aria-label="Main" data-open="false">
            <ul class="nav__list">${links.join("")}</ul>
          </nav>
          <div class="header-actions">
            <button type="button" class="header-icon-btn" id="theme-toggle" aria-pressed="false" title="High contrast">
              ${ICONS.contrast}<span class="visually-hidden">High contrast</span>
            </button>
            ${account}
            <button type="button" class="header-icon-btn menu-toggle" id="menu-toggle"
                    aria-expanded="false" aria-controls="site-nav" title="Menu">
              ${ICONS.menu}<span class="visually-hidden">Menu</span>
            </button>
          </div>
        </div>
      </header>`;

    if (user) {
      // User-supplied text is set with textContent, never inserted as HTML
      document.querySelector(".user-chip__name").textContent = user.name;
      document.querySelector(".user-chip__avatar").textContent =
        user.name.split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
      document.getElementById("logout-btn").addEventListener("click", async () => {
        try { await window.KQApi.logout(); } catch (_) { /* session may already be gone */ }
        clearChat();
        window.location.href = "index.html";
      });
    }

    const themeButton = document.getElementById("theme-toggle");
    const syncTheme = (on) => themeButton.setAttribute("aria-pressed", String(on));
    syncTheme(window.KQTheme.isHighContrast());
    window.KQTheme.onChange(syncTheme);
    themeButton.addEventListener("click", window.KQTheme.toggle);

    const nav = document.getElementById("site-nav");
    const menu = document.getElementById("menu-toggle");
    menu.addEventListener("click", () => {
      const open = nav.dataset.open !== "true";
      nav.dataset.open = String(open);
      menu.setAttribute("aria-expanded", String(open));
    });
  }

  function renderFooter(user) {
    const slot = document.getElementById("site-footer");
    if (!slot) return;
    slot.outerHTML = `
      <footer class="site-footer">
        <div class="container site-footer__grid">
          <div>
            <img class="site-footer__logo" src="assets/logo.svg" alt="Kenya Airways" width="180" height="41">
            <p>The Virtual Assistant helps with flight status, bookings, check-in and baggage, 24 hours a day.
               Prefer to talk to someone? Call <a href="tel:+254203274747">+254 20 327 4747</a>.</p>
          </div>
          <div>
            <h2>Travel</h2>
            <ul>
              <li><a href="flight-status.html">Flight status</a></li>
              <li><a href="destinations.html">Destinations</a></li>
              <li><a href="travel-info.html">Baggage &amp; check-in</a></li>
              <li><a href="assistant.html">Virtual Assistant</a></li>
            </ul>
          </div>
          <div>
            <h2>Account</h2>
            <ul>
              ${user
                ? `<li><a href="${user.role === "admin" ? "admin.html" : "account.html"}">${user.role === "admin" ? "Staff dashboard" : "My bookings"}</a></li>`
                : `<li><a href="login.html">Log in</a></li>
                   <li><a href="login.html#register">Create an account</a></li>`}
              <li><a href="about.html">About this prototype &amp; credits</a></li>
              <li><a href="/docs">API documentation</a></li>
            </ul>
          </div>
        </div>
        <p class="site-footer__note">
          Prototype of the Kenya Airways Virtual Assistant, developed for Kenya Airways as a Strathmore University
          ICS Project II. Flights, bookings and accounts shown are sample data for demonstration.
          The Kenya Airways name and logo are trademarks of Kenya Airways PLC. <a href="about.html">Photo credits</a>
        </p>
      </footer>`;
  }

  // ---------- current user ----------

  /** Forget the stored chat so the next person on this browser starts fresh. */
  function clearChat() {
    try {
      ["kq-chat-session", "kq-chat-transcript", "kq-chat-open"].forEach((key) => sessionStorage.removeItem(key));
    } catch (_) { /* storage unavailable */ }
  }

  const ready = window.KQApi.me()
    .catch(() => null)
    .then((user) => {
      renderHeader(user);
      renderFooter(user);
      return user;
    });

  // "Ask the assistant" shortcuts on any page: data-ask sends an intent payload with a
  // friendly label, data-chat sends the text as typed.
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-ask], [data-chat]");
    if (!trigger || !window.KQChat) return;
    if (trigger.dataset.ask) window.KQChat.open(trigger.dataset.ask, trigger.dataset.label);
    else window.KQChat.open(trigger.dataset.chat);
  });

  window.KQSite = {
    ready,
    clearChat,
    /** Redirect to login when nobody (or the wrong role) is logged in. */
    async requireRole(role) {
      const user = await ready;
      if (!user) {
        window.location.replace(`login.html?next=${encodeURIComponent(page === "admin" ? "admin.html" : "account.html")}`);
        return null;
      }
      if (role && user.role !== role) {
        window.location.replace(user.role === "admin" ? "admin.html" : "account.html");
        return null;
      }
      return user;
    },
    formatDateTime(value) {
      return new Intl.DateTimeFormat("en-GB", {
        weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
      }).format(new Date(value));
    },
    formatTime(value) {
      return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
    },
    /** Arrival time, with "+1" when it lands on a later day than it departs. */
    formatArrival(departure, arrival) {
      const days = Math.round((new Date(arrival).setHours(0, 0, 0, 0) - new Date(departure).setHours(0, 0, 0, 0)) / 86400000);
      return window.KQSite.formatTime(arrival) + (days > 0 ? ` +${days}` : "");
    },
    statusBadge(status) {
      const labels = {
        on_time: ["On time", "ok"], delayed: ["Delayed", "warn"], cancelled: ["Cancelled", "down"],
        departed: ["Departed", "ok"], landed: ["Landed", "ok"],
        confirmed: ["Confirmed", "ok"], checked_in: ["Checked in", "ok"],
        active: ["Active", "ok"], escalated: ["Escalated", "down"], closed: ["Closed", ""],
      };
      const [label, tone] = labels[status] || [status, ""];
      const badge = document.createElement("span");
      badge.className = `badge${tone ? " badge--" + tone : ""}`;
      badge.textContent = label;
      return badge;
    },
  };
})();
