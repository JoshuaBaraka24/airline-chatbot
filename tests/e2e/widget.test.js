// Browser test of the chat widget (keyboard use, quick replies, confirmation, outage,
// reload, XSS, mobile layout) with axe-core WCAG 2.1 AA audits.
// Requires the full stack running and a freshly seeded database (python database/init_db.py).
// Usage: npm install && npm test   [-- <baseUrl> <screenshotDir>]
const puppeteer = require("puppeteer-core");
const fs = require("fs");
const path = require("path");
const axeSource = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");

const BASE = process.argv[2] || "http://127.0.0.1:8000";
const SHOTS = process.argv[3] || path.join(__dirname, "screenshots");
fs.mkdirSync(SHOTS, { recursive: true });
const CHROME = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const results = [];
const check = (name, ok, detail = "") => results.push({ name, ok, detail });

async function lastBotTexts(page, n = 3) {
  return page.$$eval(".msg--bot", (els, n) => els.slice(-n).map((e) => e.textContent.replace(/^Assistant: /, "")), n);
}

async function waitForReply(page, previousCount) {
  await page.waitForFunction(
    (c) => document.querySelectorAll(".msg--bot, .msg--error").length > c && document.getElementById("chat-typing").hidden,
    { timeout: 30000 }, previousCount
  );
}

async function send(page, text) {
  const before = await page.$$eval(".msg--bot, .msg--error", (e) => e.length);
  await page.type("#chat-input", text);
  await page.keyboard.press("Enter");
  await waitForReply(page, before);
}

async function clickChip(page, title) {
  const before = await page.$$eval(".msg--bot, .msg--error", (e) => e.length);
  const chips = await page.$$(".chip:not([disabled])");
  for (const chip of chips) {
    if ((await chip.evaluate((c) => c.textContent)) === title) {
      await chip.click();
      await waitForReply(page, before);
      return true;
    }
  }
  return false;
}

async function axe(page, label) {
  await page.evaluate(axeSource);
  const { violations } = await page.evaluate(() =>
    axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } })
  );
  check(`axe WCAG 2.1 AA (${label})`, violations.length === 0,
    violations.map((v) => `${v.id} [${v.impact}] x${v.nodes.length}: ${v.nodes[0].target.join(" ")}`).join("; "));
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: "new", args: ["--no-sandbox"] });
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  await page.setViewport({ width: 1280, height: 800 });

  await page.goto(BASE, { waitUntil: "networkidle0" });
  await page.evaluate(() => { sessionStorage.clear(); localStorage.clear(); });
  await page.reload({ waitUntil: "networkidle0" });
  await page.screenshot({ path: path.join(SHOTS, "1-closed.png") });
  await axe(page, "page, chat closed");

  // Keyboard only: skip link -> launcher -> open
  await page.keyboard.press("Tab");
  check("first Tab focuses skip link", await page.evaluate(() => document.activeElement.className === "skip-link"));
  await page.keyboard.press("Enter");
  check("skip link moves focus to launcher", await page.evaluate(() => document.activeElement.id === "chat-launcher"));
  await page.keyboard.press("Enter");
  await page.waitForSelector("#chat-panel:not([hidden])");
  check("Enter on launcher opens panel and focuses input", await page.evaluate(() => document.activeElement.id === "chat-input"));
  await page.waitForFunction(() => document.getElementById("chat-status-text").textContent === "Online", { timeout: 10000 })
    .then(() => check("status shows Online", true)).catch(() => check("status shows Online", false));
  check("welcome message with 4 quick replies",
    (await page.$$eval(".chip", (c) => c.length)) === 4);

  // Quick reply -> multi-turn flight status
  check("quick reply 'Flight Status' sent", await clickChip(page, "Flight Status"));
  let bot = await lastBotTexts(page, 1);
  check("asks for flight number", /flight number/i.test(bot[0]), bot[0]);
  check("used quick replies are disabled", await page.$$eval(".chip", (c) => c.slice(0, 4).every((b) => b.disabled)));
  await send(page, "KQ202");
  bot = await lastBotTexts(page, 1);
  check("flight status reply rendered with line breaks", /Status: Delayed/.test(bot[0]) && bot[0].includes("\n"), bot[0].slice(0, 80));

  // Cancellation with yes/no buttons
  await send(page, "I want to cancel my booking");
  await send(page, "BK001");
  bot = await lastBotTexts(page, 1);
  check("confirmation shows booking details", /BK001.*John Mwangi/s.test(bot[0]), bot[0].slice(0, 80));
  check("No button cancels nothing", await clickChip(page, "No"));
  bot = await lastBotTexts(page, 1);
  check("booking kept", /has not been cancelled/.test(bot[0]), bot[0]);
  await axe(page, "chat open, conversation");
  await page.screenshot({ path: path.join(SHOTS, "2-conversation.png") });

  // High contrast
  await page.click("#contrast-toggle");
  check("high contrast toggled", await page.evaluate(() => document.documentElement.dataset.theme === "high-contrast"));
  await axe(page, "high contrast");
  await page.screenshot({ path: path.join(SHOTS, "3-high-contrast.png") });
  await page.click("#contrast-toggle");

  // Reload keeps the transcript and session
  const sessionBefore = await page.evaluate(() => sessionStorage.getItem("kq-chat-session"));
  const countBefore = await page.$$eval(".msg", (e) => e.length);
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector("#chat-panel:not([hidden])");
  check("transcript restored after reload",
    (await page.$$eval(".msg", (e) => e.length)) === countBefore &&
    (await page.evaluate(() => sessionStorage.getItem("kq-chat-session"))) === sessionBefore);

  // Outage: API returns 503, then recovers via Try again
  await page.setRequestInterception(true);
  let fail = true;
  const intercept = (req) => {
    if (fail && req.url().endsWith("/api/chat")) req.respond({ status: 503, contentType: "application/json", body: "{}" });
    else req.continue();
  };
  page.on("request", intercept);
  await send(page, "how many bags can I carry?");
  check("outage shows error with retry", (await page.$$eval(".msg--error .chip", (c) => c.length)) === 1);
  check("status shows Offline", (await page.$eval("#chat-status-text", (e) => e.textContent)) === "Offline");
  fail = false;
  const before = await page.$$eval(".msg--bot", (e) => e.length);
  await page.click(".msg--error .chip");
  await page.waitForFunction((c) => document.querySelectorAll(".msg--bot").length > c, { timeout: 30000 }, before);
  bot = await lastBotTexts(page, 1);
  check("retry succeeds", /baggage allowance/i.test(bot[0]), bot[0].slice(0, 60));
  page.off("request", intercept);
  await page.setRequestInterception(false);

  // XSS: markup typed by the user is shown as text
  await send(page, "<img src=x onerror=alert(1)>");
  check("user HTML rendered as text", (await page.$$("#chat-log img")).length === 0);

  // Escape closes and returns focus
  await page.focus("#chat-input");
  await page.keyboard.press("Escape");
  check("Escape closes panel and focuses launcher",
    await page.evaluate(() => document.getElementById("chat-panel").hidden && document.activeElement.id === "chat-launcher"));

  // Restart starts a new session
  await page.click("#chat-launcher");
  await page.click("#restart-btn");
  check("restart clears conversation",
    (await page.$$eval(".msg", (e) => e.length)) === 1 &&
    (await page.evaluate(() => sessionStorage.getItem("kq-chat-session"))) === null);

  // Mobile
  await page.setViewport({ width: 390, height: 844, isMobile: true });
  await page.reload({ waitUntil: "networkidle0" });
  await page.click("#chat-launcher");
  await page.waitForSelector("#chat-panel:not([hidden])");
  const box = await page.$eval("#chat-panel", (e) => e.getBoundingClientRect().toJSON());
  check("panel is full-screen on phones", box.width === 390 && box.height === 844, JSON.stringify(box));
  check("no horizontal scroll on phones", await page.evaluate(() => document.documentElement.scrollWidth <= 390));
  await page.screenshot({ path: path.join(SHOTS, "4-mobile.png") });
  await axe(page, "mobile");

  const csp = consoleErrors.filter((e) => /Content Security Policy/i.test(e));
  check("no CSP violations", csp.length === 0, csp.join(" | "));
  const other = consoleErrors.filter((e) => !/Content Security Policy|503|Failed to load resource/i.test(e));
  check("no other console errors", other.length === 0, other.join(" | "));

  await browser.close();
  for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail && !r.ok ? "  -> " + r.detail : ""}`);
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
