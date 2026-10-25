/** Real React/WebAudio/MediaRecorder and real tab visibility; synthetic Wake Lock/HTTP lease. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { createServer } from "node:http";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
const require = createRequire(import.meta.url);
const { webpack } = require("next/dist/compiled/webpack/webpack");
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = resolve(root, "../.agents/logs");
const temporary = await mkdtemp(join(tmpdir(), "memora-continuity-test-"));
const hookPath = join(root, "src/features/memora/use-recording-continuity.ts");
const hookSource = await readFile(hookPath, "utf8");
const hash = (value) => createHash("sha256").update(value).digest("hex");
const hookSha = hash(hookSource);
const events = [];
let backendMode = "supported";
let releasePendingHeartbeat;
let browser;
let chromeProcess;
let server;
try {
  const loader = join(temporary, "loader.cjs");
  await writeFile(
    loader,
    `const ts=require(${JSON.stringify(require.resolve("typescript"))});module.exports=function(source){return ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;};`,
  );
  const snapshot = join(temporary, "hook.ts");
  await writeFile(
    snapshot,
    hookSource.replace(
      'from "./api"',
      `from ${JSON.stringify(join(root, "src/features/memora/api.ts"))}`,
    ),
  );
  const entry = join(temporary, "entry.tsx");
  await writeFile(
    entry,
    `import React,{useRef,useState} from 'react';import{createRoot}from'react-dom/client';import{useRecordingContinuity}from'./hook';
function App(){const recorder=useRef(null);const audio=useRef(null);const[state,setState]=useState('idle');const protection=useRecordingContinuity('synthetic-continuity',state,recorder,m=>window.__warnings.push(m),false);
async function start(){const context=new AudioContext();await context.resume();const oscillator=context.createOscillator();oscillator.frequency.value=440;const gain=context.createGain();gain.gain.value=.1;const destination=context.createMediaStreamDestination();oscillator.connect(gain);gain.connect(destination);oscillator.start();audio.current={context,oscillator,stream:destination.stream};const media=new MediaRecorder(destination.stream,{mimeType:'audio/webm;codecs=opus',audioBitsPerSecond:128000});const request=media.requestData.bind(media),pause=media.pause.bind(media),stop=media.stop.bind(media);media.requestData=()=>{window.__flushes++;request();};media.pause=()=>{window.__pauses++;pause();};media.stop=()=>{window.__stops++;stop();};media.ondataavailable=e=>{window.__bytes+=e.data.size;window.__chunks++;};recorder.current=media;window.__recorder=media;media.start(100);setState('recording');}
function stop(){if(recorder.current&&recorder.current.state!=='inactive')recorder.current.stop();audio.current?.stream.getTracks().forEach(t=>t.stop());audio.current?.oscillator.stop();void audio.current?.context.close();setState('idle');}
return <><button onClick={()=>void start()} disabled={state!=='idle'}>Start synthetic capture</button><button onClick={stop} disabled={state==='idle'}>Stop capture</button><button onClick={()=>{recorder.current.pause();setState('paused');}} disabled={state!=='recording'}>Pause capture</button><button onClick={()=>{recorder.current.resume();setState('recording');}} disabled={state!=='paused'}>Resume capture</button><output id="state">{state}</output><output id="protection">{protection}</output></>;}const target=createRoot(document.getElementById('root'));target.render(<App/>);window.__unmount=()=>target.unmount();`,
  );
  await new Promise((resolve, reject) => {
    const compiler = webpack({
      mode: "development",
      devtool: false,
      target: "web",
      entry,
      output: { path: temporary, filename: "bundle.js" },
      resolve: {
        extensions: [".tsx", ".ts", ".js"],
        modules: [join(root, "node_modules")],
      },
      module: { rules: [{ test: /\.tsx?$/, use: loader }] },
    });
    compiler.run((error, stats) =>
      compiler.close(() =>
        error || stats.hasErrors()
          ? reject(error || Error(stats.toString({ all: false, errors: true })))
          : resolve(),
      ),
    );
  });
  const bundle = await readFile(join(temporary, "bundle.js"));
  server = createServer(async (request, response) => {
    if (request.url.endsWith("/capture-awake")) {
      let body = "";
      for await (const chunk of request) body += chunk;
      const data = JSON.parse(body);
      events.push({ ...data, at: Date.now() });
      if (data.active && backendMode === "pending")
        await new Promise((resolve) => {
          releasePendingHeartbeat = resolve;
        });
      if (backendMode === "failed") {
        response.writeHead(503, { "content-type": "application/json" });
        response.end('{"detail":"Synthetic unsupported service"}');
        return;
      }
      response.writeHead(200, { "content-type": "application/json" });
      response.end(
        JSON.stringify({
          supported: backendMode !== "unsupported",
          active: data.active && backendMode !== "unsupported",
        }),
      );
      return;
    }
    if (request.url === "/bundle.js") {
      response.writeHead(200, { "content-type": "text/javascript" });
      response.end(bundle);
      return;
    }
    response.writeHead(200, { "content-type": "text/html" });
    response.end('<html><body><div id="root"></div></body></html>');
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const executable =
    process.env.MEMORA_CONTINUITY_CHROMIUM ||
    "/Users/kalagasergeeric/Library/Caches/ms-playwright/chromium-1248/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing";
  // Attach to our own empty-profile Chrome with noDefaults so Playwright does
  // not force all tabs focused/visible. Never attach to a user's browser.
  const profile = join(temporary, "chrome-profile");
  chromeProcess = spawn(
    executable,
    [
      `--user-data-dir=${profile}`,
      "--remote-debugging-address=127.0.0.1",
      "--remote-debugging-port=0",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-gpu",
      "--autoplay-policy=no-user-gesture-required",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  let debugPort;
  for (let attempt = 0; attempt < 100; attempt++) {
    if (chromeProcess.exitCode !== null)
      throw Error("Temporary Chrome stopped");
    try {
      debugPort = Number(
        (await readFile(join(profile, "DevToolsActivePort"), "utf8")).split(
          "\n",
        )[0],
      );
      break;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  assert.ok(debugPort);
  browser = await chromium.connectOverCDP(`http://127.0.0.1:${debugPort}`, {
    noDefaults: true,
  });
  const context = browser.contexts()[0];
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(base);
  await page.evaluate(() => {
    window.__warnings = [];
    window.__bytes = 0;
    window.__chunks = 0;
    window.__flushes = 0;
    window.__pauses = 0;
    window.__stops = 0;
    window.__locks = [];
    window.__wakeRequests = 0;
    window.__wakeMode = "supported";
    window.__visibility = [];
    class Lock extends EventTarget {
      released = false;
      async release() {
        if (!this.released) {
          this.released = true;
          this.dispatchEvent(new Event("release"));
        }
      }
    }
    const wake = {
      request: async () => {
        window.__wakeRequests++;
        if (window.__wakeMode === "denied")
          throw new DOMException("Synthetic denial", "NotAllowedError");
        if (window.__wakeMode === "pending")
          return new Promise((resolve) => {
            window.__resolveWake = () => {
              const lock = new Lock();
              window.__locks.push(lock);
              resolve(lock);
            };
          });
        const lock = new Lock();
        window.__locks.push(lock);
        return lock;
      },
    };
    window.__fakeWake = wake;
    Object.defineProperty(navigator, "wakeLock", {
      value: wake,
      configurable: true,
    });
    document.addEventListener("visibilitychange", () => {
      window.__visibility.push(document.visibilityState);
      if (document.hidden)
        window.__locks.forEach((lock) => {
          void lock.release();
        });
    });
  });
  await page.addScriptTag({ url: base + "/bundle.js" });
  await page
    .getByRole("button", { name: "Start synthetic capture", exact: true })
    .click();
  await page.waitForFunction(
    () => window.__recorder?.state === "recording" && window.__bytes > 0,
  );
  await page.waitForFunction(
    () => document.querySelector("#protection").textContent === "native",
  );
  assert.ok(events.some((entry) => entry.active));
  assert.equal(await page.evaluate(() => window.__wakeRequests), 1);
  console.log(
    "PASS Real synthetic WebAudio/MediaRecorder starts, fake screen lock acquired, active HTTP lease acknowledged",
  );
  const other = await context.newPage();
  await other.goto(base + "/other");
  // Playwright normally forces every tab focused/visible. Disable that default
  // override, then switch actual tabs; never inject document.hidden/events.
  const session1 = await context.newCDPSession(page);
  const session2 = await context.newCDPSession(other);
  await session1.send("Emulation.setFocusEmulationEnabled", { enabled: false });
  await session2.send("Emulation.setFocusEmulationEnabled", { enabled: false });
  await other.bringToFront();
  await page.waitForFunction(
    () => document.visibilityState === "hidden",
    null,
    { polling: 100 },
  );
  const hidden = await page.evaluate(() => ({
    bytes: window.__bytes,
    flushes: window.__flushes,
    state: window.__recorder.state,
    pauses: window.__pauses,
    stops: window.__stops,
  }));
  await new Promise((resolve) => setTimeout(resolve, 2200));
  const background = await page.evaluate(() => ({
    bytes: window.__bytes,
    state: window.__recorder.state,
    pauses: window.__pauses,
    stops: window.__stops,
  }));
  assert.equal(background.state, "recording");
  assert.ok(background.bytes > hidden.bytes);
  assert.equal(background.pauses, 0);
  assert.equal(background.stops, 0);
  assert.ok(hidden.flushes >= 1);
  await page.bringToFront();
  await page.waitForFunction(
    () => document.visibilityState === "visible" && window.__wakeRequests >= 2,
    null,
    { polling: 100 },
  );
  assert.ok(await page.evaluate(() => window.__flushes >= 2));
  console.log(
    "PASS Real tab background/return keeps recorder recording and byte progress, flushes data, reacquires released wake lock",
  );
  await page
    .getByRole("button", { name: "Pause capture", exact: true })
    .click();
  const pausedFlushes = await page.evaluate(() => window.__flushes);
  await other.bringToFront();
  await page.waitForFunction(() => document.hidden, null, { polling: 100 });
  await page.bringToFront();
  await page.waitForFunction(() => !document.hidden, null, { polling: 100 });
  assert.equal(await page.evaluate(() => window.__recorder.state), "paused");
  assert.equal(await page.evaluate(() => window.__flushes), pausedFlushes);
  await page
    .getByRole("button", { name: "Resume capture", exact: true })
    .click();
  await page.getByRole("button", { name: "Stop capture", exact: true }).click();
  await page.waitForFunction(() =>
    window.__locks.every((lock) => lock.released),
  );
  await new Promise((resolve) => setTimeout(resolve, 150));
  assert.equal(events.at(-1).active, false);
  console.log(
    "PASS Paused capture stays paused on real tab changes; stopping releases all screen locks and HTTP lease",
  );
  for (const scenario of ["unsupported", "denied"]) {
    backendMode = scenario === "unsupported" ? "unsupported" : "failed";
    await page.evaluate((scenario) => {
      window.__wakeMode = scenario;
      Object.defineProperty(navigator, "wakeLock", {
        value: scenario === "unsupported" ? undefined : window.__fakeWake,
        configurable: true,
      });
    }, scenario);
    const previous = await page.evaluate(() => window.__bytes);
    await page
      .getByRole("button", { name: "Start synthetic capture", exact: true })
      .click();
    await page.waitForFunction(
      (previous) =>
        window.__recorder.state === "recording" && window.__bytes > previous,
      previous,
    );
    await page.waitForFunction(
      () => document.querySelector("#protection").textContent === "none",
    );
    await page
      .getByRole("button", { name: "Stop capture", exact: true })
      .click();
    console.log(
      `PASS ${scenario} screen/native protection degrades gracefully while real recorder continues`,
    );
  }
  backendMode = "pending";
  await page.evaluate(() => {
    window.__wakeMode = "pending";
    Object.defineProperty(navigator, "wakeLock", {
      value: window.__fakeWake,
      configurable: true,
    });
  });
  const countBefore = events.length;
  await page
    .getByRole("button", { name: "Start synthetic capture", exact: true })
    .click();
  await page.waitForFunction(() => typeof window.__resolveWake === "function");
  for (let attempt = 0; !releasePendingHeartbeat && attempt < 100; attempt++)
    await new Promise((resolve) => setTimeout(resolve, 20));
  assert.ok(releasePendingHeartbeat);
  await page.getByRole("button", { name: "Stop capture", exact: true }).click();
  backendMode = "supported";
  releasePendingHeartbeat();
  await page.evaluate(() => window.__resolveWake());
  await page.waitForFunction(() =>
    window.__locks.every((lock) => lock.released),
  );
  for (
    let attempt = 0;
    events.at(-1)?.active !== false && attempt < 100;
    attempt++
  )
    await new Promise((resolve) => setTimeout(resolve, 20));
  assert.deepEqual(
    events.slice(countBefore).map((entry) => entry.active),
    [true, false],
  );
  console.log(
    "PASS Pending wake/HTTP acquisition finishes into release after stop, without abandoned leases",
  );
  await page.evaluate(() => window.__unmount());
  assert.deepEqual(errors, []);
  const result = {
    hook_sha256: hookSha,
    hook_disk_sha256_after: hash(await readFile(hookPath, "utf8")),
    real_tab_visibility: await page.evaluate(() => window.__visibility),
    real_media_bytes: await page.evaluate(() => window.__bytes),
    real_request_data_flushes: await page.evaluate(() => window.__flushes),
    fake_wake_requests: await page.evaluate(() => window.__wakeRequests),
    heartbeat_events: events,
    browser_errors: errors,
    physical_microphone: false,
    machine_sleep_tested: false,
  };
  await writeFile(
    join(output, "recording-continuity-browser.json"),
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log(
    "PASS No browser exceptions; actual visibility transitions and resource/byte evidence recorded",
  );
} finally {
  if (releasePendingHeartbeat) releasePendingHeartbeat();
  if (browser) await browser.close();
  if (chromeProcess) {
    chromeProcess.kill("SIGTERM");
    await new Promise((resolve) =>
      chromeProcess.exitCode !== null
        ? resolve()
        : chromeProcess.once("exit", resolve),
    );
  }
  if (server) {
    server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  }
  await rm(temporary, { recursive: true, force: true });
}
