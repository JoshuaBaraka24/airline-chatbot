/* Shared page chrome: header, footer, logo, login state and theme.
   Exposes window.KQSite and window.KQTheme. Load after api.js. */
(function () {
  "use strict";

  const THEME_KEY = "kq-chat-theme";
  // Drop the official Kenya Airways logo here (see assets/README.md)
  const LOGO_URL = "assets/logo.png";

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

  function navLink(href, label, key) {
    const current = key === page ? ' aria-current="page"' : "";
    return `<li><a class="nav__link" href="${href}"${current}>${label}</a></li>`;
  }

  function renderHeader(user) {
    const slot = document.getElementById("site-header");
    if (!slot) return;
    const links = [
      navLink("index.html", "Home", "home"),
      navLink("index.html#flight-status", "Flight status", "status"),
      navLink("index.html#travel-info", "Travel info", "info"),
    ];
    if (user && user.role === "passenger") links.push(navLink("account.html", "My bookings", "account"));
    if (user && user.role === "admin") links.push(navLink("admin.html", "Staff dashboard", "admin"));

    const account = user
      ? `<span class="user-chip"><span class="user-chip__avatar" aria-hidden="true"></span>
           <span class="user-chip__name"></span></span>
         <button type="button" class="btn btn--light btn--small" id="logout-btn">Log out</button>`
      : `<a class="btn btn--light btn--small" href="login.html" id="login-link">Log in</a>`;

    slot.outerHTML = `
      <header class="site-header">
        <div class="container site-header__bar">
          <a class="brand" href="index.html" aria-label="Kenya Airways virtual assistant, home">
            <span class="brand__mark" id="brand-mark" aria-hidden="true">KQ</span>
            <span class="brand__name">Kenya Airways<span class="brand__tagline">The Pride of Africa · Virtual Assistant</span></span>
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

    loadLogo();
  }

  function loadLogo() {
    const mark = document.getElementById("brand-mark");
    const logo = new Image();
    logo.onload = () => {
      logo.className = "brand__logo brand__logo--on-light";
      logo.alt = "";
      mark.replaceWith(logo);
    };
    logo.src = LOGO_URL; // if the file is missing, the "KQ" mark stays
  }

  function renderFooter(user) {
    const slot = document.getElementById("site-footer");
    if (!slot) return;
    slot.outerHTML = `
      <footer class="site-footer">
        <div class="container site-footer__grid">
          <div>
            <h2>Kenya Airways Virtual Assistant</h2>
            <p>Help with flight status, bookings, check-in and baggage, 24 hours a day.
               Prefer to talk to someone? Call <a href="tel:+254203274747">+254 20 327 4747</a>.</p>
          </div>
          <div>
            <h2>Help</h2>
            <ul>
              <li><a href="index.html#flight-status">Flight status</a></li>
              <li><a href="index.html#travel-info">Baggage &amp; check-in</a></li>
              <li><a href="account.html">My bookings</a></li>
            </ul>
          </div>
          <div>
            <h2>Account</h2>
            <ul>
              ${user
                ? `<li><a href="${user.role === "admin" ? "admin.html" : "account.html"}">${user.role === "admin" ? "Staff dashboard" : "My bookings"}</a></li>`
                : `<li><a href="login.html">Log in</a></li>
                   <li><a href="login.html#register">Create an account</a></li>`}
              <li><a href="/docs">API documentation</a></li>
            </ul>
          </div>
        </div>
        <p class="site-footer__note">
          Student project (ICS Project II) for demonstration only. Not affiliated with or endorsed by Kenya Airways.
          The Kenya Airways name and logo belong to Kenya Airways PLC.
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
