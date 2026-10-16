// Shared helpers for the browser tests.
const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-core");

const axeSource = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
const CHROME = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";

function createReport() {
  const results = [];
  return {
    check(name, ok, detail = "") {
      results.push({ name, ok: Boolean(ok), detail });
    },
    finish() {
      for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail && !r.ok ? "  -> " + r.detail : ""}`);
      const failed = results.filter((r) => !r.ok).length;
      console.log(`\n${results.length - failed}/${results.length} checks passed`);
      return failed;
    },
  };
}

async function launch() {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: "new", args: ["--no-sandbox"] });
  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
  page.on("pageerror", (e) => consoleErrors.push(String(e)));
  await page.setViewport({ width: 1280, height: 900 });
  return { browser, page, consoleErrors };
}

async function axe(page, report, label) {
  await page.evaluate(axeSource);
  const { violations } = await page.evaluate(() =>
    axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] } })
  );
  report.check(`axe WCAG 2.1 AA (${label})`, violations.length === 0,
    violations.map((v) => `${v.id} [${v.impact}] x${v.nodes.length}: ${v.nodes[0].target.join(" ")}`).join("; "));
}

const botCount = (page) => page.$$eval(".msg--bot, .msg--error", (e) => e.length);

async function waitForReply(page, previous) {
  await page.waitForFunction(
    (c) => document.querySelectorAll(".msg--bot, .msg--error").length > c && document.getElementById("chat-typing").hidden,
    { timeout: 30000 }, previous
  );
}

async function lastBot(page) {
  return page.$$eval(".msg--bot", (els) => (els.length ? els[els.length - 1].textContent.replace(/^Assistant: /, "") : ""));
}

async function sendChat(page, text) {
  const before = await botCount(page);
  await page.type("#chat-input", text);
  await page.keyboard.press("Enter");
  await waitForReply(page, before);
  return lastBot(page);
}

async function clickChip(page, startsWith) {
  const before = await botCount(page);
  const chips = await page.$$(".chip:not([disabled])");
  for (const chip of chips) {
    if ((await chip.evaluate((c) => c.textContent)).startsWith(startsWith)) {
      await chip.click();
      await waitForReply(page, before);
      return lastBot(page);
    }
  }
  return null;
}

async function shot(page, dir, name) {
  fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, name), fullPage: true });
}

module.exports = { createReport, launch, axe, botCount, waitForReply, lastBot, sendChat, clickChip, shot };
