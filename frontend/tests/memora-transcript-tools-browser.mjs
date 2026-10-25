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
    `import React from 'react';import {createRoot} from 'react-dom/client';import {SpeakerTools} from ${JSON.stringify(join(root,"src/features/memora/speaker-tools.tsx"))};import {PlaybackTools} from ${JSON.stringify(join(root,"src/features/memora/playback-tools.tsx"))};const segments=[{id:'s1',speaker:'Intervenant non identifié',start:0,end:10,text:'Discussion synthétique de démonstration.'},{id:'s2',speaker:'Intervenant 2',start:10,end:20,text:'Deuxième passage.'}];createRoot(document.getElementById('root')).render(<div className="theme"><main><h1>Transcription</h1><p className="intro">Outils de lecture et gestion des intervenants</p><audio controls/><PlaybackTools getAudio={()=>document.querySelector('audio')} segments={segments} selectedStart={null} onPosition={()=>{}} english={false}/><SpeakerTools segments={segments} version={1} guest={false} english={false} busy={false} canSeparate={true} run={async()=>true}/></main></div>);`,
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
  browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,headless:true});
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://memora.test/**',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));await page.goto('https://memora.test');
  const globals=await readFile(join(root,'src/app/globals.css'),'utf8');
  const light=globals.match(/:root \{[\s\S]*?\}/)[0];const dark=globals.match(/:root\[data-theme="dark"\] \{[\s\S]*?\}/)[0];
  await page.addStyleTag({content:light+dark+'*{box-sizing:border-box}body{margin:0;background:var(--background);color:var(--ink);font-family:Arial,sans-serif}main{max-width:980px;padding:28px;margin:auto}h1{font-size:24px;margin:0 0 8px}.intro{font-size:13px;color:var(--muted);margin:0 0 24px}audio{width:100%;height:40px}button,input,select{font:inherit}'+await readFile(join(root,'src/features/memora/transcript-tools.module.css'),'utf8')});
  const workspaceCss=(await readFile(join(root,'src/features/memora/workspace-frame.module.css'),'utf8')).replace(/:global\(([^)]+)\)/g,'$1');
  await page.addStyleTag({content:workspaceCss});
  await page.addScriptTag({path:join(folder,'bundle.js')});await page.locator('summary').click();
  const results=[];
  for(const width of [1200,390])for(const theme of ['light','dark']){
    await page.setViewportSize({width,height:1000});await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    assert.equal(await page.locator('main').count(),1);assert.equal(await page.locator('h1').count(),1);
    const measured=await page.evaluate(()=>{const block=document.querySelector('details');const g=document.querySelector('.renameGrid');return {background:getComputedStyle(block).backgroundColor,color:getComputedStyle(block).color,columns:getComputedStyle(g).gridTemplateColumns,overflow:document.documentElement.scrollWidth>innerWidth};});
    assert.equal(measured.overflow,false);assert.equal(measured.background,theme==='dark'?'rgb(33, 31, 48)':'rgb(255, 255, 255)');assert.equal(measured.columns.split(' ').length,width===390?1:2);
    await page.screenshot({path:join(root,'../agents/logs',`transcript-tools-workspace-${width}-${theme}.png`),fullPage:true});results.push({width,theme,...measured});
  }
  assert.deepEqual(errors,[]);console.log(JSON.stringify({checks:4,results,browserErrors:errors},null,2));
}finally{if(browser)await browser.close();await rm(folder,{recursive:true,force:true});}
