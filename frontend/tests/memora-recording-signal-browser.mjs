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
    `import React from 'react';import {createRoot} from 'react-dom/client';import {RecordingSignal} from ${JSON.stringify(join(root, "src/features/memora/recording-signal.tsx"))};const target=createRoot(document.getElementById('root'));window.__mount=(state='recording')=>target.render(<RecordingSignal stream={window.__stream} state={state} language="en"/>);window.__unmount=()=>target.unmount();window.__again=()=>{window.__second=createRoot(document.getElementById('root'));window.__second.render(<RecordingSignal stream={window.__stream} state='recording' language='en'/>);};`,
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
  browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,headless:true,args:['--autoplay-policy=no-user-gesture-required']});
  const page=await browser.newPage();page.setDefaultTimeout(10000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://memora.test/**',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));
  await page.goto('https://memora.test');
  await page.evaluate(async()=>{
    window.__audio=new AudioContext();const osc=window.__audio.createOscillator();window.__gain=window.__audio.createGain();window.__gain.gain.value=.25;
    const dest=window.__audio.createMediaStreamDestination();osc.connect(window.__gain).connect(dest);osc.start();await window.__audio.resume();
    window.__stream=dest.stream;window.__recorder=new MediaRecorder(dest.stream);window.__recorder.start();
  });
  await page.addStyleTag({content:await readFile(join(root,'src/features/memora/recording-signal.module.css'),'utf8')});
  await page.addScriptTag({path:join(folder,'bundle.js')});
  await page.evaluate(()=>window.__mount());
  const meter=page.locator('meter');
  await page.waitForFunction(()=>document.querySelector('meter')?.value>0);
  assert.match(await page.locator('[role=status]').innerText(),/Recording in progress/);
  const pixels=await page.locator('canvas').evaluate(c=>{const p=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<p.length;i+=4)if(p[i])n++;return n;});assert.ok(pixels>100);
  console.log('PASS real synthetic oscillator level>0 and canvas pixels',pixels);
  const centroid=()=>page.locator('canvas').evaluate(c=>{const p=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let weight=0,total=0;for(let y=0;y<c.height;y++)for(let x=0;x<c.width;x++){const a=p[(y*c.width+x)*4+3];weight+=a;total+=a*x;}return total/weight;});
  await page.evaluate(()=>window.__gain.gain.value=0);
  await page.waitForTimeout(150);const before=await centroid();await page.waitForTimeout(1100);const after=await centroid();assert.ok(after<before-5,`history must scroll left: ${before}->${after}`);console.log('PASS temporal history moves right to left',before,after);
  assert.doesNotMatch(await page.locator('body').innerText(),/dBFS|peak|technical indicator/);
  await page.evaluate(()=>window.__gain.gain.value=.25);await page.waitForFunction(()=>document.querySelector('meter').value>0);

  await page.evaluate(()=>window.__mount('paused'));await page.getByRole('status').filter({hasText:'Recording paused'}).waitFor();await page.waitForFunction(()=>document.querySelector('meter').value===0);
  assert.equal(await page.evaluate(()=>window.__recorder.state),'recording');
  const frozen=await page.locator('canvas').evaluate(c=>c.toDataURL());await page.waitForTimeout(400);assert.equal(await page.locator('canvas').evaluate(c=>c.toDataURL()),frozen);console.log('PASS visual pause freezes history and preserves parent recorder');
  await page.evaluate(()=>window.__mount());await page.waitForFunction(()=>document.querySelector('meter').value>0);console.log('PASS resume signal');
  await page.evaluate(()=>window.__gain.gain.value=1.2);await page.getByRole('status').filter({hasText:'near clipping'}).waitFor();console.log('PASS saturation warning');
  await page.evaluate(()=>window.__gain.gain.value=0);await page.getByRole('status').filter({hasText:'Very quiet for 4 seconds'}).waitFor();console.log('PASS persistent silence');
  await page.evaluate(()=>window.__stream.getAudioTracks()[0].enabled=false);await page.getByRole('status').filter({hasText:'muted or disabled'}).waitFor();console.log('PASS disabled parent track');
  await page.evaluate(()=>{window.__stream.getAudioTracks()[0].enabled=true;window.__gain.gain.value=.25;});await page.waitForFunction(()=>document.querySelector('meter').value>0);
  await page.evaluate(()=>window.__unmount());
  assert.deepEqual(await page.evaluate(()=>({track:window.__stream.getAudioTracks()[0].readyState,recorder:window.__recorder.state,context:window.__audio.state})),{track:'live',recorder:'recording',context:'running'});
  assert.deepEqual(errors,[]);console.log('PASS unmount preserves parent stream/recorder/context; zero browser errors');
  await page.evaluate(()=>window.__again());await page.waitForFunction(()=>document.querySelector('meter')?.value>0);
  await page.evaluate(()=>window.__stream.getAudioTracks()[0].stop());await page.getByRole('status').filter({hasText:'Audio input disconnected'}).waitFor();console.log('PASS ended parent track');
  await page.evaluate(()=>{window.__second.unmount();window.__recorder.stop();window.__stream.getTracks().forEach(t=>t.stop());window.__audio.close();});
} finally {if(browser)await browser.close();await rm(folder,{recursive:true,force:true});}
