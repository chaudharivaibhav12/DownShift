import puppeteer from "puppeteer-core";
import { STEPS, INTRO } from "../src/lib/tour.js";

/* Drives the guided tour in a real browser against the dev server.
   Run: npm run dev, then npm run walkthrough */
const CHROME = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE = process.env.BASE_URL || "http://localhost:5173";
const fail = [];
const ok = (c, m) => { console.log(`  ${c ? "PASS" : "FAIL"}  ${m}`); if (!c) fail.push(m); };

const browser = await puppeteer.launch({ executablePath: CHROME, headless: "new",
  args: ["--no-sandbox", "--disable-gpu"], defaultViewport: { width: 1440, height: 900 } });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const ignorable = (t) => /webgl/i.test(t) || /favicon/i.test(t) || /404 \(Not Found\)/.test(t);
page.on("console", (m) => m.type() === "error" && !ignorable(m.text()) && errors.push(m.text()));

await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await page.waitForSelector(".shell", { timeout: 15000 });
await new Promise((r) => setTimeout(r, 1500));

console.log("\n1. first visit opens the intro");
ok(await page.$eval("h2", (e) => e.textContent) === INTRO.title, `intro titled "${INTRO.title}"`);
ok((await page.$$('[role="dialog"]')).length === 1, "exactly one dialog");
ok(await page.$eval(".scrim", (e) => getComputedStyle(e).backgroundColor) !== "rgba(0, 0, 0, 0)",
   "scrim actually dims the page");

console.log("\n2. walking the steps");
await page.evaluate(() => [...document.querySelectorAll("button")].find((b) => b.textContent.trim() === "Start tour").click());
await new Promise((r) => setTimeout(r, 400));

for (let i = 0; i < STEPS.length; i++) {
  const s = STEPS[i];
  const seen = await page.evaluate(() => {
    const tip = document.querySelector(".tip");
    return tip && { title: tip.querySelector("h3")?.textContent, count: tip.querySelector(".count")?.textContent,
                    rect: tip.getBoundingClientRect().toJSON() };
  });
  ok(seen?.title === s.title, `step ${i + 1} shows "${s.title}"`);
  ok(seen?.count === `${i + 1} of ${STEPS.length}`, `  counter reads "${i + 1} of ${STEPS.length}"`);

  const target = await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    return el && { r: el.getBoundingClientRect().toJSON(), visible: el.offsetParent !== null || el.tagName === "ASIDE" };
  }, s.target);
  ok(!!target, `  target ${s.target} exists in the DOM`);
  ok(target?.r.width > 0 && target?.r.height > 0, "  target has a real box to spotlight");

  const vp = await page.viewport();
  ok(seen && seen.rect.left >= 0 && seen.rect.top >= 0 &&
     seen.rect.left + seen.rect.width <= vp.width + 1 && seen.rect.top + seen.rect.height <= vp.height + 1,
     "  tooltip is fully on screen");

  const spot = await page.evaluate(() => {
    const s = document.querySelector(".scrim.spot");
    return s && s.getBoundingClientRect().toJSON();
  });
  ok(!!spot, "  spotlight is positioned");
  if (spot && target) {
    const near = Math.abs(spot.left - (target.r.left - 6)) < 3 && Math.abs(spot.top - (target.r.top - 6)) < 3;
    ok(near, "  spotlight sits over the target");
  }

  await page.evaluate(() => [...document.querySelectorAll(".tip button")].pop().click());
  await new Promise((r) => setTimeout(r, 700));
}

console.log("\n3. after the tour");
ok((await page.$$(".tip")).length === 0, "tour closed on Done");
ok(await page.evaluate(() => localStorage.getItem("downshift.tour.seen")) === "1", "marked seen");
await page.reload({ waitUntil: "domcontentloaded" });
await page.waitForSelector(".shell");
await new Promise((r) => setTimeout(r, 1200));
ok((await page.$$('[role="dialog"]')).length === 0, "does not reopen on the next visit");
await page.evaluate(() => document.querySelector(".help").click());
await new Promise((r) => setTimeout(r, 300));
ok(await page.$eval("h2", (e) => e.textContent).catch(() => null) === INTRO.title, "? button reopens it");

console.log("\n4. console errors");
ok(errors.length === 0, `no page errors (${errors.length}) [WebGL/favicon ignored: headless has no GPU]`);
errors.slice(0, 5).forEach((e) => console.log("      " + e.slice(0, 160)));

await browser.close();
console.log(`\n${fail.length ? fail.length + " FAILED" : "ALL CHECKS PASSED"}`);
process.exit(fail.length ? 1 : 0);
