/** Mounted real React chat, synthetic HTTP answers only; no AI/main services. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createServer } from "node:http";
import { chromium } from "@playwright/test";
const require = createRequire(import.meta.url);
const { webpack } = require("next/dist/compiled/webpack/webpack");
const root = resolve(import.meta.dirname, "..");
const temp = await mkdtemp(join(tmpdir(), "memora-chat-"));
let server, browser;
try {
  const loader = join(temp, "loader.cjs");
  await writeFile(
    loader,
    `const ts=require(${JSON.stringify(require.resolve("typescript"))});module.exports=s=>ts.transpileModule(s,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;`,
  );
  const cssLoader = join(temp, "css.cjs");
  await writeFile(
    cssLoader,
    `module.exports=s=>'const style=document.createElement("style");style.textContent='+JSON.stringify(s)+';document.head.append(style);export default '+JSON.stringify(Object.fromEntries([...s.matchAll(/\\.([a-zA-Z][\\w-]*)/g)].map(m=>[m[1],m[1]])))+';';`,
  );
  const i18n = join(temp, "i18n.ts");
  await writeFile(i18n, 'export const useI18n=()=>({language:"fr"});');
  const entry = join(temp, "entry.tsx");
  await writeFile(
    entry,
    `import React,{useState}from'react';import{createRoot}from'react-dom/client';import{MeetingChat}from ${JSON.stringify(join(root, "src/features/memora/meeting-chat.tsx"))};function App(){const[id,setId]=useState('a');const[v,setV]=useState(1);const[scope,setScope]=useState('transcript');window.__scope=setScope;const[history,setHistory]=useState([]);window.__history=setHistory;window.__version=setV;window.__meeting=setId;return <MeetingChat id={id} access={{}} contextScope={scope} currentVersion={v} segments={[{id:'s1',start:65,end:70,text:'Source synthétique vérifiable',speaker:'Intervenant 1'}]} history={history} seek={(start,version)=>window.__seek={start,version}}/>;}createRoot(document.getElementById('root')).render(<App/>);`,
  );
  await new Promise((done, fail) => {
    const compiler = webpack({
      mode: "development",
      devtool: false,
      entry,
      output: { path: temp, filename: "bundle.js" },
      resolve: {
        extensions: [".tsx", ".ts", ".js"],
        modules: [join(root, "node_modules")],
        alias: { "@/lib/i18n/use-i18n": i18n },
      },
      module: {
        rules: [
          { test: /\.tsx?$/, use: loader },
          { test: /\.css$/, use: cssLoader },
        ],
      },
    });
    compiler.run((error, stats) =>
      compiler.close(() =>
        error || stats.hasErrors()
          ? fail(error || Error(stats.toString({ all: false, errors: true })))
          : done(),
      ),
    );
  });
  const bundle = await readFile(join(temp, "bundle.js"));
  server = createServer((request, response) => {
    if (request.url === "/bundle.js") {
      response.setHeader("content-type", "text/javascript; charset=utf-8");
      response.end(bundle);
    } else {
      response.end(
        '<html><head><style>body{margin:0;padding:20px;--ink:#232336;--muted:#6f7085;--green:#6550df;--line:#e8e8f0;--surface:#fff;--background:#f7f8fb;--soft:#f2efff;font-family:Arial}*{box-sizing:border-box}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>',
      );
    }
  });
  await new Promise((done) => server.listen(0, "127.0.0.1", done));
  browser = await chromium.launch({
    headless: true,
    executablePath:
      process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
      "/Users/kalagasergeeric/Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell",
  });
  const page = await browser.newPage({
    viewport: { width: 1100, height: 900 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let mode = "ok",
    requests = [];
  await page.route("**/mapi/meetings/*/chat", async (route) => {
    requests.push(JSON.parse(route.request().postData()));
    if (mode === "slow") await new Promise((done) => setTimeout(done, 250));
    await route
      .fulfill({
        status: mode === "error" ? 503 : 200,
        contentType: "application/json",
        body: JSON.stringify(
          mode === "error"
            ? { detail: "Indisponibilité synthétique" }
            : {
                answer: "Réponse synthétique <script>unsafe</script>",
                id: "synthetic-answer",
                created: 1700000000,
                history_omitted: 1,
                version: 1,
                sources: ["s1"],
              },
        ),
      })
      .catch(() => {});
  });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  const input = page.getByRole("textbox", {
    name: "Votre question",
    exact: true,
  });
  await input.waitFor();
  await page
    .getByRole("button", {
      name: "Quelles décisions avons-nous prises ?",
      exact: true,
    })
    .click();
  assert.equal(
    await input.inputValue(),
    "Quelles décisions avons-nous prises ?",
  );
  await input.fill("Question ligne1");
  await input.press("Shift+Enter");
  await input.press("a");
  assert.match(await input.inputValue(), /\n/);
  await input.press("Enter");
  await page
    .getByText("Réponse synthétique <script>unsafe</script>", { exact: true })
    .waitFor();
  assert.equal(requests.length, 1);
  assert.equal(await page.locator("script").count(), 1);
  await page
    .getByRole("button", { name: "Écouter la source 01:05", exact: true })
    .click();
  assert.deepEqual(await page.evaluate(() => window.__seek), {
    start: 65,
    version: 1,
  });
  console.log(
    "PASS Suggestions, multiline Enter/ShiftEnter, safe answer and timed source navigation",
  );
  await page.evaluate(() => window.__version(2));
  await page.getByText("v1 · Ancienne source", { exact: true }).waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Écouter la source 01:05", exact: true })
      .count(),
    0,
  );
  console.log(
    "PASS Transcript version changes disable old citations without deleting answers",
  );
  mode = "error";
  await input.fill("Question à relancer");
  await input.press("Enter");
  await page.getByRole("alert").waitFor();
  assert.equal(await input.inputValue(), "Question à relancer");
  mode = "ok";
  await page.getByRole("button", { name: "Réessayer", exact: true }).click();
  await page.waitForFunction(
    () => document.querySelector("textarea").value === "",
  );
  console.log("PASS Failed request remains retryable without losing question");
  await page.evaluate(() => {
    window.__meeting("b");
    window.__history([
      {
        version: 2,
        question: "Historique serveur",
        answer: "Réponse restaurée",
        sources: [],
      },
    ]);
  });
  await page.getByText("Réponse restaurée", { exact: true }).waitFor();
  assert.equal(
    await page
      .getByText("Réponse synthétique <script>unsafe</script>", { exact: true })
      .count(),
    0,
  );
  console.log(
    "PASS Meeting identity resets local conversation; refreshed server history remains visible",
  );
  mode = "slow";
  await input.fill("Question annulée");
  await input.press("Enter");
  await page.getByRole("status").waitFor();
  await page.evaluate(() => window.__version(3));
  await page.waitForTimeout(400);
  assert.equal(
    await page
      .getByText("Réponse synthétique <script>unsafe</script>", { exact: true })
      .count(),
    0,
  );
  assert.ok(
    await page
      .getByRole("button", { name: "Poser la question", exact: true })
      .isEnabled(),
  );
  console.log("PASS Version change aborts pending answer and unlocks composer");
  await page.evaluate(() => {
    window.__history([]);
    window.__scope("report:restricted");
  });
  await page
    .getByRole("heading", {
      name: "Que souhaitez-vous retrouver ?",
      exact: true,
    })
    .waitFor();
  assert.equal(await input.inputValue(), "");
  assert.equal(
    await page.getByText("Réponse restaurée", { exact: true }).count(),
    0,
  );
  console.log(
    "PASS Context permission boundary resets local answers and draft",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  assert.ok(await page.locator("textarea").isVisible());
  await page.screenshot({
    path: resolve(root, "../agents/logs/meeting-chat-mobile.png"),
  });
  assert.deepEqual(errors, []);
  console.log("PASS Responsive mobile composer and no browser exceptions");
} finally {
  await browser?.close();
  if (server) {
    server.closeAllConnections();
    await new Promise((done) => server.close(done));
  }
  await rm(temp, { recursive: true, force: true });
}
