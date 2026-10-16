// Browser test of the web portal: home page, login/registration, My bookings,
// personalised chat, role-based access and the staff dashboard, with axe-core audits.
// Requires the full stack and a freshly seeded database (python database/init_db.py).
// Usage: npm run test:portal   [-- <baseUrl> <screenshotDir>]
const path = require("path");
const h = require("./helpers");

const BASE = process.argv[2] || "http://127.0.0.1:8000";
const SHOTS = process.argv[3] || path.join(__dirname, "screenshots");
const report = h.createReport();
const { check } = report;

async function login(page, email, password) {
  await page.goto(`${BASE}/login.html`, { waitUntil: "networkidle0" });
  await page.type("#login-email", email);
  await page.type("#login-password", password);
  await Promise.all([page.waitForNavigation({ waitUntil: "networkidle0" }), page.click("#login-form button[type=submit]")]);
}

async function logout(page) {
  await page.waitForSelector("#logout-btn");
  await Promise.all([page.waitForNavigation({ waitUntil: "networkidle0" }), page.click("#logout-btn")]);
}

(async () => {
  const { browser, page, consoleErrors } = await h.launch();
  await page.goto(BASE, { waitUntil: "networkidle0" });
  await page.evaluate(() => { sessionStorage.clear(); localStorage.clear(); });

  // ---------- Home page (guest) ----------
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector(".site-header");
  check("header shows Log in for guests", await page.$("#login-link"));
  check("footer carries the not-affiliated notice", (await page.$eval(".site-footer__note", (e) => e.textContent)).includes("Not affiliated"));
  await page.type("#status-input", "kq202");
  await page.click("#status-form button");
  await page.waitForSelector(".flight-row");
  const rows = await page.$$eval(".flight-row", (els) => els.map((e) => e.textContent));
  check("flight status search lists KQ202 departures", rows.length === 2 && rows[0].includes("Nairobi → Dubai") && rows[0].includes("Delayed"), rows.join(" | "));
  await page.$eval("#status-input", (e) => (e.value = ""));
  await page.type("#status-input", "hello");
  await page.click("#status-form button");
  check("invalid flight number explained", (await page.$eval("#status-message", (e) => e.textContent)).includes("like KQ101"));
  await h.axe(page, report, "home");
  await h.shot(page, SHOTS, "portal-1-home.png");

  const before = await h.botCount(page);
  await page.click('[data-ask="/baggage_policy"]');
  await page.waitForSelector("#chat-panel:not([hidden])");
  await h.waitForReply(page, before);
  check("help tile opens the assistant with the topic", /baggage allowance/i.test(await h.lastBot(page)));
  check("guest booking question asks for a reference", /provide your booking reference/i.test(await h.sendChat(page, "I want to cancel my booking")));
  await h.sendChat(page, "never mind");
  check("guest asking for an agent is escalated", /connecting you to a Kenya Airways agent/i.test(await h.sendChat(page, "agent")));

  // ---------- Access control ----------
  await page.goto(`${BASE}/account.html`, { waitUntil: "networkidle0" });
  check("My bookings redirects guests to login", page.url().includes("login.html?next=account.html"));

  // ---------- Login errors and registration ----------
  await page.type("#login-email", "john@email.com");
  await page.type("#login-password", "wrong-password1");
  await page.click("#login-form button[type=submit]");
  await page.waitForSelector("#auth-error:not([hidden])");
  check("wrong password shows an error", (await page.$eval("#auth-error", (e) => e.textContent)).includes("Incorrect email or password"));
  await h.axe(page, report, "login");
  await h.shot(page, SHOTS, "portal-2-login.png");

  await page.click("#tab-register");
  await page.type("#register-name", "Wanjiru Njeri");
  await page.type("#register-email", `wanjiru.${Date.now()}@example.com`);
  await page.type("#register-password", "short");
  await page.click("#register-form button[type=submit]");
  await page.waitForFunction(() => document.getElementById("auth-error").textContent.includes("8 characters"));
  check("weak password explained", true);
  await page.$eval("#register-password", (e) => (e.value = ""));
  await page.type("#register-password", "safari2026");
  await Promise.all([page.waitForNavigation({ waitUntil: "networkidle0" }), page.click("#register-form button[type=submit]")]);
  await page.waitForSelector("#bookings[aria-busy=false]");
  check("new account lands on My bookings", page.url().endsWith("/account.html"));
  check("new account sees the empty state", !(await page.$eval("#bookings-empty", (e) => e.hidden)));
  check("header greets the new passenger", (await page.$eval(".user-chip__name", (e) => e.textContent)) === "Wanjiru Njeri");
  await logout(page);
  check("logout returns to Log in", await page.$("#login-link"));

  // ---------- Passenger: My bookings and personalised chat ----------
  await login(page, "john@email.com", "Passenger@2026");
  await page.waitForSelector(".booking");
  const cards = await page.$$eval(".booking", (els) => els.map((e) => e.textContent));
  check("John sees only booking BK001", cards.length === 1 && cards[0].includes("BK001") && cards[0].includes("Mombasa"), cards.join(" | "));
  check("chat from the previous user was cleared", (await page.evaluate(() => sessionStorage.getItem("kq-chat-transcript"))) === null);
  await h.axe(page, report, "my bookings");
  await h.shot(page, SHOTS, "portal-3-account.png");

  let reply = await (async () => {
    const n = await h.botCount(page);
    await page.click(".booking__actions .btn--secondary"); // "Cancel booking"
    await h.waitForReply(page, n);
    return h.lastBot(page);
  })();
  check("Cancel booking button starts a cancellation for BK001", /BK001 for John Mwangi/.test(reply), reply.slice(0, 80));
  reply = await h.clickChip(page, "No");
  check("declining keeps the booking", /has not been cancelled/.test(reply), reply);

  reply = await h.sendChat(page, "I want to cancel my booking");
  check("logged-in passenger is greeted by name", /^John, which booking/.test(reply), reply);
  const chips = await page.$$eval(".chip:not([disabled])", (els) => els.map((e) => e.textContent));
  check("their bookings are offered as buttons", chips.length === 1 && chips[0].startsWith("BK001 · KQ101 Nairobi → Mombasa"), chips.join(" | "));
  reply = await h.clickChip(page, "BK001");
  check("choosing a booking button goes to confirmation", /Are you sure you want to cancel it/.test(reply), reply.slice(0, 80));
  reply = await h.clickChip(page, "Yes");
  check("confirming cancels the booking", /BK001 has been cancelled/.test(reply), reply);
  await h.shot(page, SHOTS, "portal-4-chat.png");
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector(".booking");
  check("My bookings shows the cancellation", (await page.$eval(".booking__status", (e) => e.textContent)) === "Cancelled");

  await page.goto(`${BASE}/admin.html`, { waitUntil: "networkidle0" });
  check("passengers cannot open the staff dashboard", page.url().endsWith("/account.html"));
  await logout(page);

  // ---------- Staff dashboard ----------
  await login(page, "admin@kq-demo.local", "Admin@2026");
  check("staff login lands on the dashboard", page.url().endsWith("/admin.html"));
  await page.waitForFunction(() => document.getElementById("stat-total").textContent !== "–");
  const stat = (id) => page.$eval(`#${id}`, (e) => Number(e.textContent));
  check("statistics count the conversations", (await stat("stat-total")) >= 2 && (await stat("stat-escalated")) >= 1);
  const tableText = await page.$eval("#conversation-rows", (e) => e.textContent);
  check("log links John's conversation to his account", tableText.includes("John Mwangi"));
  check("intent chart rendered", (await page.$$("#intent-bars li")).length > 0);

  await page.select("#status-filter", "escalated");
  await page.waitForFunction(() => document.getElementById("log-status").textContent.includes("shown"));
  const statuses = await page.$$eval("#conversation-rows .badge", (els) => els.map((e) => e.textContent));
  check("status filter shows only escalated chats", statuses.length >= 1 && statuses.every((s) => s === "Escalated"), statuses.join(","));
  await h.axe(page, report, "staff dashboard");
  await h.shot(page, SHOTS, "portal-5-admin.png");

  await page.click("#conversation-rows .btn--secondary");
  await page.waitForSelector("#transcript[open] .transcript__line");
  const lines = await page.$$eval(".transcript__line", (els) => els.map((e) => e.textContent));
  check("transcript shows the guest's request for an agent", lines.some((l) => l.startsWith("agent")) && lines.some((l) => l.includes("connecting you")), lines.slice(0, 4).join(" | "));
  await h.axe(page, report, "transcript dialog");
  await page.click("#transcript-close");

  const escalatedBefore = await stat("stat-escalated");
  await page.click("#conversation-rows .btn--primary");
  await page.waitForFunction((n) => Number(document.getElementById("stat-escalated").textContent) === n - 1, { timeout: 10000 }, escalatedBefore);
  check("Mark resolved clears the escalation", true);

  await page.click("#theme-toggle");
  check("header high-contrast toggle works", await page.evaluate(() => document.documentElement.dataset.theme === "high-contrast"));
  await h.axe(page, report, "dashboard, high contrast");
  await h.shot(page, SHOTS, "portal-6-admin-contrast.png");
  await page.click("#theme-toggle");
  await logout(page);

  // ---------- Phone layout ----------
  await page.setViewport({ width: 390, height: 844, isMobile: true });
  await page.goto(BASE, { waitUntil: "networkidle0" });
  check("menu is collapsed on phones", await page.$eval("#site-nav", (e) => getComputedStyle(e).display === "none"));
  await page.click("#menu-toggle");
  check("menu button opens the navigation", await page.$eval("#site-nav", (e) => getComputedStyle(e).display !== "none")
    && (await page.$eval("#menu-toggle", (e) => e.getAttribute("aria-expanded"))) === "true");
  check("no horizontal scroll on phones", await page.evaluate(() => document.documentElement.scrollWidth <= 390));
  await h.axe(page, report, "home on phone");
  await h.shot(page, SHOTS, "portal-7-mobile.png");

  const csp = consoleErrors.filter((e) => /Content Security Policy/i.test(e));
  check("no CSP violations", csp.length === 0, csp.join(" | "));
  // Expected: 401/404 responses (login failure, missing optional logo file)
  const other = consoleErrors.filter((e) => !/Content Security Policy|Failed to load resource/i.test(e));
  check("no other console errors", other.length === 0, other.join(" | "));

  await browser.close();
  process.exit(report.finish() ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
