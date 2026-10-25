/** Temporary-service diagnostic: synthetic auth + draft meeting, no audio/model calls. */
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { readFile } from "node:fs/promises";
const base = process.env.MEMORA_UI_URL;
const account = JSON.parse(
  await readFile(process.env.MEMORA_TEST_CREDENTIALS, "utf8"),
);
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
});
const page = await browser.newPage();
let stage = "start";
const errors = [];
page.on("console", (m) => {
  if (m.type() === "error") console.log("CONSOLE " + stage + " " + m.text());
});
page.on("pageerror", (e) => {
  const item = {
    stage,
    url: new URL(page.url()).pathname,
    message: e.message,
    stack: e.stack,
  };
  errors.push(item);
  console.log(JSON.stringify(item));
});
try {
  const login = await page.request.post(base + "/api/auth/login", {
    headers: { Origin: base },
    data: account,
  });
  if (!login.ok()) throw Error("Synthetic diagnostic auth failed");
  await page.goto(base + "/");
  await page.waitForTimeout(1000);
  for (const path of ["/", "/profil", "/parametres", "/"]) {
    stage = "hardload " + path;
    await page.goto(base + path);
    await page.waitForTimeout(1000);
  }
  stage = "draftcreation";
  await page
    .getByRole("button", { name: "Nouvelle réunion", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("textbox")
    .fill("Diagnostic hydratation synthétique");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Enregistrer", exact: true })
    .click();
  await page.waitForURL(/\/reunions\//);
  await page.waitForTimeout(500);
  stage = "draftreload";
  await page.reload();
  await page.waitForTimeout(1000);
  stage = "dashboardSPA";
  await page.getByRole("link", { name: "Mes réunions", exact: true }).click();
  await page.waitForURL(base + "/");
  stage = "profileSPA";
  await page.locator("button.account-trigger").click();
  await page.getByRole("menuitem", { name: /Modifier mon profil/ }).click();
  await page.waitForURL(base + "/profil");
  await page.waitForTimeout(1000);
  stage = "profilereload";
  await page.reload();
  await page.waitForTimeout(1000);
  console.log("DIAGNOSTIC ERRORS " + errors.length);
  assert.equal(errors.length, Number(process.env.MEMORA_EXPECT_HYDRATION_ERRORS || 0));
} finally {
  await browser.close();
}
