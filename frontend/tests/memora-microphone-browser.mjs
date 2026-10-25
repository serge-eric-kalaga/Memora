/** Standalone React media tests: synthetic APIs by default, real Chromium codec with --real-codec and fake input. */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
const require = createRequire(import.meta.url);
const { webpack } = require("next/dist/compiled/webpack/webpack");
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const folder = await mkdtemp(join(tmpdir(), "memora-microphone-browser-"));
const realCodec = process.argv.includes("--real-codec");
let browser;
try {
  const loader = join(folder, "typescript-loader.cjs");
  await writeFile(
    loader,
    `const ts=require(${JSON.stringify(require.resolve("typescript"))});module.exports=function(source){return ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;};`,
  );
  const cssLoader = join(folder, "css-loader.cjs");
  await writeFile(
    cssLoader,
    `module.exports=function(source){const names=[...source.matchAll(/\\.([a-zA-Z][a-zA-Z0-9_-]*)/g)].map(m=>m[1]);return 'module.exports='+JSON.stringify(Object.fromEntries(names.map(n=>[n,n])))+';';};`,
  );
  const entry = join(folder, "entry.tsx");
  await writeFile(
    entry,
    `import React,{useState} from 'react';import {createRoot} from 'react-dom/client';import {MicrophoneCheck} from ${JSON.stringify(join(root, "src/features/memora/microphone-check.tsx"))};const target=createRoot(document.getElementById('root'));function App({language,disabled}){const[id,setId]=useState('');return <MicrophoneCheck disabled={disabled} language={language} selectedDeviceId={id} onDeviceChange={setId} onActiveChange={active=>window.__active.push(active)}/>;}window.__mount=(language='fr',disabled=false)=>target.render(<App language={language} disabled={disabled}/>);window.__unmount=()=>target.unmount();`,
  );
  await new Promise((resolve, reject) => {
    const compiler = webpack({
      mode: "development",
      devtool: false,
      target: "web",
      entry,
      output: { path: folder, filename: "bundle.js" },
      resolve: {
        extensions: [".tsx", ".ts", ".js"],
        modules: [join(root, "node_modules")],
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
          ? reject(error || Error(stats.toString({ all: false, errors: true })))
          : resolve(),
      ),
    );
  });
  browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    headless: true,
    args: realCodec
      ? [
          "--use-fake-device-for-media-stream",
          "--use-fake-ui-for-media-stream",
          `--use-file-for-fake-audio-capture=${resolve(root, "../backend/test/fixtures/memora/mixed-native.wav")}`,
        ]
      : ["--disable-gpu"],
  });
  const context = await browser.newContext(
    realCodec ? { permissions: ["microphone"] } : {},
  );
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  if (realCodec) {
    let posts = 0;
    page.on("request", (request) => {
      if (request.method() === "POST") posts++;
    });
    // All document requests are fulfilled in process; this reserved .test origin
    // only provides a secure browser context. No external server receives audio.
    await page.route("https://memora.test/**", (route) =>
      route.fulfill({
        contentType: "text/html",
        body: '<html><body><div id="root"></div></body></html>',
      }),
    );
    await page.goto("https://memora.test/");
    await page.evaluate(() => {
      window.__active = [];
      window.__realStreams = [];
      const original = navigator.mediaDevices.getUserMedia.bind(
        navigator.mediaDevices,
      );
      navigator.mediaDevices.getUserMedia = async (constraints) => {
        const stream = await original(constraints);
        window.__realStreams.push(stream);
        return stream;
      };
    });
    await page.addScriptTag({
      content: await readFile(join(folder, "bundle.js"), "utf8"),
    });
    await page.evaluate(() => window.__mount());
    await page
      .getByRole("button", { name: "Tester le microphone", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Arrêter le test", exact: true })
      .waitFor();
    await page
      .getByRole("button", {
        name: "Enregistrer un échantillon (10 s max.)",
        exact: true,
      })
      .click();
    await page.waitForTimeout(1200);
    await page
      .getByRole("button", { name: "Terminer l’échantillon", exact: true })
      .click();
    await page.locator("audio").waitFor();
    await page.locator("audio").evaluate(async (audio) => {
      await audio.play();
    });
    await page.waitForFunction(() => {
      const audio = document.querySelector("audio");
      return audio && audio.currentTime > 0.15 && !audio.error;
    });
    await page.locator("audio").evaluate((audio) => audio.pause());
    console.log(
      "PASS Real Chromium MediaRecorder sample decodes and plays from a local blob with synthetic input",
    );
    await page
      .getByRole("button", { name: "Arrêter le test", exact: true })
      .click();
    assert.equal(
      await page.evaluate(() =>
        window.__realStreams.every((stream) =>
          stream.getTracks().every((track) => track.readyState === "ended"),
        ),
      ),
      true,
    );
    assert.equal(posts, 0);
    await page.evaluate(() => window.__unmount());
    assert.deepEqual(errors, []);
    console.log(
      "PASS Real microphone tracks stop; no sample upload and no unhandled browser exception",
    );
  } else {
    await page.setContent('<html><body><div id="root"></div></body></html>');
    await page.evaluate(() => {
      window.__active = [];
      window.__calls = 0;
      window.__stops = 0;
      window.__closed = 0;
      window.__level = 0.03;
      window.__urls = 0;
      window.__revoked = 0;
      window.__streams = [];
      window.__mode = "ok";
      const create = URL.createObjectURL.bind(URL),
        revoke = URL.revokeObjectURL.bind(URL);
      URL.createObjectURL = (blob) => {
        window.__urls++;
        return create(blob);
      };
      URL.revokeObjectURL = (url) => {
        window.__revoked++;
        revoke(url);
      };
      class Track {
        onended = null;
        onmute = null;
        onunmute = null;
        stop() {
          window.__stops++;
        }
      }
      const stream = () => {
        const track = new Track();
        const value = {
          getTracks: () => [track],
          getAudioTracks: () => [track],
        };
        window.__streams.push(value);
        return value;
      };
      const media = new EventTarget();
      media.enumerateDevices = async () => [
        {
          kind: "audioinput",
          deviceId: "mic-one",
          label: "Synthetic microphone",
        },
      ];
      media.getUserMedia = async (constraints) => {
        window.__calls++;
        window.__constraints = constraints;
        if (window.__mode === "denied")
          throw new DOMException("Synthetic refusal", "NotAllowedError");
        if (window.__mode === "missing")
          throw new DOMException("Synthetic absence", "NotFoundError");
        if (window.__mode === "pending")
          return new Promise((resolve) => {
            window.__resolvePermission = () => resolve(stream());
          });
        return stream();
      };
      Object.defineProperty(navigator, "mediaDevices", {
        value: media,
        configurable: true,
      });
      window.AudioContext = class {
        state = "running";
        resume() {
          return Promise.resolve();
        }
        close() {
          window.__closed++;
          this.state = "closed";
          return Promise.resolve();
        }
        createMediaStreamSource() {
          return { connect() {}, disconnect() {} };
        }
        createAnalyser() {
          return {
            fftSize: 2048,
            getFloatTimeDomainData(buffer) {
              buffer.fill(window.__level);
            },
            disconnect() {},
          };
        }
      };
      window.MediaRecorder = class {
        static isTypeSupported() {
          return true;
        }
        state = "inactive";
        mimeType = "audio/webm";
        start() {
          this.state = "recording";
        }
        stop() {
          this.state = "inactive";
          queueMicrotask(() => {
            this.ondataavailable?.({
              data: new Blob(["synthetic audio"], { type: this.mimeType }),
            });
            this.onstop?.();
          });
        }
      };
    });
    await page.addScriptTag({
      content: await readFile(join(folder, "bundle.js"), "utf8"),
    });
    await page.evaluate(() => window.__mount());
    await page
      .getByRole("button", { name: "Tester le microphone", exact: true })
      .waitFor();
    assert.equal(await page.evaluate(() => window.__calls), 0);
    console.log("PASS Mount/enumeration never activates microphone");
    await page
      .getByLabel("Entrée audio", { exact: true })
      .selectOption("mic-one");
    await page
      .getByRole("button", { name: "Tester le microphone", exact: true })
      .click();
    await page.getByText("Microphone actif", { exact: true }).waitFor();
    assert.equal(
      await page.evaluate(() => window.__constraints.audio.deviceId.exact),
      "mic-one",
    );
    assert.ok((await page.evaluate(() => window.__active)).includes(true));
    console.log(
      "PASS Explicit activation uses the selected exact input and reports active",
    );
    await page.evaluate(() => {
      window.__level = 1;
    });
    await page
      .getByRole("status")
      .filter({ hasText: "Saturation possible" })
      .waitFor();
    await page.evaluate(() => {
      window.__level = 0;
    });
    await page
      .getByRole("status")
      .filter({ hasText: "Signal très faible ou silence" })
      .waitFor();
    console.log(
      "PASS Synthetic clipped signal and sustained silence produce honest warnings",
    );
    await page
      .getByRole("button", {
        name: "Enregistrer un échantillon (10 s max.)",
        exact: true,
      })
      .click();
    await page
      .getByRole("button", { name: "Terminer l’échantillon", exact: true })
      .click();
    await page.locator("audio").waitFor();
    assert.match(await page.locator("audio").getAttribute("src"), /^blob:/);
    await page
      .getByRole("button", { name: "Arrêter le test", exact: true })
      .click();
    assert.equal(await page.evaluate(() => window.__stops), 1);
    assert.equal(await page.evaluate(() => window.__closed), 1);
    assert.equal(await page.locator("audio").count(), 1);
    await page
      .getByRole("button", { name: "Effacer l’échantillon", exact: true })
      .click();
    assert.equal(await page.evaluate(() => window.__revoked), 1);
    console.log(
      "PASS Sample exposes local replay, stopping releases tracks/context, discard revokes URL",
    );
    await page.evaluate(() => {
      window.__mode = "denied";
    });
    await page
      .getByRole("button", { name: "Tester le microphone", exact: true })
      .click();
    await page.getByRole("alert").filter({ hasText: "Accès refusé" }).waitFor();
    assert.equal(await page.evaluate(() => window.__active.at(-1)), false);
    await page.evaluate(() => {
      window.__mode = "missing";
    });
    await page
      .getByRole("button", { name: "Tester le microphone", exact: true })
      .click();
    await page
      .getByRole("alert")
      .filter({ hasText: "Aucun microphone" })
      .waitFor();
    console.log(
      "PASS Permission refusal and missing input are visible, with inactive callback",
    );
    await page.evaluate(() => {
      window.__mode = "pending";
    });
    await page
      .getByRole("button", { name: "Tester le microphone", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Autorisation en attente…", exact: true })
      .waitFor();
    assert.equal(await page.evaluate(() => window.__active.at(-1)), true);
    await page
      .getByRole("button", { name: "Arrêter le test", exact: true })
      .click();
    await page.evaluate(() => window.__resolvePermission());
    await page.waitForFunction(() => window.__stops === 2);
    assert.equal(await page.evaluate(() => window.__active.at(-1)), false);
    console.log(
      "PASS Pending permission can be cancelled and a late stream is immediately stopped",
    );
    await page.evaluate(() => {
      window.__mode = "ok";
    });
    await page
      .getByRole("button", { name: "Tester le microphone", exact: true })
      .click();
    await page.getByText("Microphone actif", { exact: true }).waitFor();
    await page.evaluate(() =>
      window.__streams.at(-1).getAudioTracks()[0].onended(),
    );
    await page.getByRole("alert").filter({ hasText: "déconnecté" }).waitFor();
    assert.equal(await page.evaluate(() => window.__stops), 3);
    assert.equal(await page.evaluate(() => window.__active.at(-1)), false);
    console.log(
      "PASS Device disconnection stops the test and releases the input",
    );
    await page
      .getByRole("button", { name: "Tester le microphone", exact: true })
      .click();
    await page.getByText("Microphone actif", { exact: true }).waitFor();

    await page
      .getByRole("button", {
        name: "Enregistrer un échantillon (10 s max.)",
        exact: true,
      })
      .click();
    await page
      .getByRole("button", { name: "Terminer l’échantillon", exact: true })
      .click();
    await page.locator("audio").waitFor();
    await page.evaluate(() => window.__mount("en"));
    await page
      .getByRole("heading", { name: "Check your microphone", exact: true })
      .waitFor();
    await page.getByLabel("Audio input", { exact: true }).waitFor();
    await page.getByLabel("Listen to your sample", { exact: true }).waitFor();
    console.log(
      "PASS English interface retains named input, sample player and controls",
    );
    await page.evaluate(() => window.__mount("en", true));
    await page
      .getByText("Testing is disabled while the meeting is recording.", {
        exact: true,
      })
      .waitFor();
    await page.waitForFunction(() => window.__stops === 4);
    assert.equal(await page.evaluate(() => window.__active.at(-1)), false);
    console.log(
      "PASS Parent disabled state releases an active test before meeting capture",
    );
    await page.evaluate(() => window.__unmount());
    assert.equal(await page.evaluate(() => window.__stops), 4);
    assert.equal(await page.evaluate(() => window.__urls), 2);
    assert.equal(await page.evaluate(() => window.__revoked), 2);
    assert.deepEqual(errors, []);
    console.log(
      "PASS Unmount revokes the remaining sample URL with no browser exceptions",
    );
  }
} finally {
  if (browser) await browser.close();
  await rm(folder, { recursive: true, force: true });
}
