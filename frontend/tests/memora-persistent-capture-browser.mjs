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
  const sessionStub=join(folder,'session.tsx'), languageStub=join(folder,'language.ts'), textStub=join(folder,'text.ts'), linkStub=join(folder,'link.tsx'), apiStub=join(folder,'api.ts');
  await writeFile(sessionStub,`import{useSyncExternalStore}from'react';export const sessionChannel='memora-synthetic-session',sessionSource='synthetic-owner-tab';export function useSession(){return {data:useSyncExternalStore(window.__subscribe,()=>window.__owner)?{username:window.__owner}:null};}`);
  await writeFile(languageStub,`export function useI18n(){return {language:'fr'};}`);
  await writeFile(textStub,`export function useMemoraText(){return x=>x;}`);
  await writeFile(linkStub,`import React from'react';export default function Link({href,children,...props}){return <a href={href} {...props} onClick={e=>{e.preventDefault();window.__navigate(href);}}>{children}</a>;}`);
  await writeFile(apiStub,`export function clock(n){return String(n);}export async function api(path,options={}){window.__requests.push({path,method:options.method||'GET',size:options.body instanceof Blob?options.body.size:0,body:typeof options.body==='string'?JSON.parse(options.body):null});if(path.endsWith('/finalize'))window.__finalized=true;return {supported:false,active:false};}`);
  const entry = join(folder, 'entry.tsx');
  await writeFile(entry,`import React,{useState}from'react';import{createRoot}from'react-dom/client';import{CaptureProvider,CaptureSlot}from ${JSON.stringify(join(root,'src/features/memora/capture-session.tsx'))};window.__owner='synthetic';const listeners=new Set();window.__subscribe=f=>{listeners.add(f);return()=>listeners.delete(f)};window.__logout=()=>{window.__owner=null;listeners.forEach(f=>f());};window.__login=()=>{window.__owner='synthetic';listeners.forEach(f=>f());};function App(){const[route,setRoute]=useState('/reunions/one');window.__navigate=setRoute;const id=route.split('/').pop();const meeting={id,title:'Réunion synthétique '+id,mode:'recording',version:0,state:'draft',transcription_language:'fr',chunks:[],settings:{max_duration_minutes:120}};return <CaptureProvider><nav>{['/reunions/one','/reunions','/profil','/parametres','/reunions/two'].map(r=><button key={r} onClick={()=>setRoute(r)}>{r}</button>)}</nav><h1>{route}</h1>{route.startsWith('/reunions/')&&<CaptureSlot key={id} meeting={meeting} refresh={async()=>{window.__refreshes++;}} onCaptureState={x=>window.__lastState=x}/>}</CaptureProvider>;}createRoot(document.getElementById('root')).render(<App/>);`);
  await new Promise((resolve, reject) => {
    const compiler = webpack({
      mode: "development",
      devtool: false,
      target: "web",
      entry,
      output: { path: folder, filename: "bundle.js" },
      plugins:[new webpack.NormalModuleReplacementPlugin(/^\.\/api$/,apiStub),new webpack.NormalModuleReplacementPlugin(/^\.\/i18n$/,textStub)],
      resolve: {
        alias:{"@/features/auth/hooks":sessionStub,"@/lib/i18n/use-i18n":languageStub,"next/link":linkStub},
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
  browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,headless:true,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--autoplay-policy=no-user-gesture-required']});
  const context=await browser.newContext({permissions:['microphone']});const page=await context.newPage();page.setDefaultTimeout(15000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://memora.test/**',r=>r.fulfill({contentType:'text/html',body:'<div id="root"></div>'}));await page.goto('https://memora.test');
  await page.evaluate(()=>{
    window.__requests=[];window.__refreshes=0;window.__streams=[];window.__gum=0;window.__stops=0;window.__starts=0;
    const get=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia=async c=>{window.__gum++;const stream=await get(c);window.__streams.push(stream);for(const track of stream.getTracks()){const stop=track.stop.bind(track);track.stop=()=>{window.__stops++;stop();};}if(window.__delay)await new Promise(resolve=>window.__resolveAcquisition=resolve);return stream;};
    const start=MediaRecorder.prototype.start;MediaRecorder.prototype.start=function(...args){window.__starts++;return start.apply(this,args);};
  });
  await page.addScriptTag({path:join(folder,'bundle.js')});
  await page.getByRole('button',{name:'Enregistrer',exact:true}).click();await page.getByRole('button',{name:'Pause',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>window.__gum),1);
  for(const route of ['/reunions','/profil','/parametres','/reunions/two']){
    await page.getByRole('button',{name:route,exact:true}).click();await page.getByTestId('persistent-capture-bar').waitFor();
    assert.deepEqual(await page.evaluate(()=>({gum:window.__gum,stops:window.__stops,live:window.__streams[0].getTracks()[0].readyState})),{gum:1,stops:0,live:'live'});
  }console.log('PASS four route unmounts preserve one native MediaRecorder stream');
  await page.getByTestId('persistent-capture-bar').getByRole('button',{name:'Pause',exact:true}).click();await page.getByRole('button',{name:'Reprendre',exact:true}).click();
  await page.getByRole('link',{name:'Retour à la réunion'}).click();await page.getByRole('button',{name:'Pause',exact:true}).waitFor();assert.equal(await page.evaluate(()=>window.__gum),1);console.log('PASS bar pause/resume/return without reacquisition');
  await page.waitForFunction(()=>window.__requests.some(r=>r.path.includes('/chunks?')&&r.size>0),null,{timeout:15000});console.log('PASS real codec blob persisted IndexedDB then confirmed through stub transport');
  await page.getByRole('button',{name:'/profil',exact:true}).click();await page.getByTestId('persistent-capture-bar').getByRole('button',{name:'Terminer et analyser',exact:true}).click();await page.waitForFunction(()=>window.__finalized);assert.equal(await page.evaluate(()=>window.__streams[0].getTracks()[0].readyState),'ended');console.log('PASS finalize from bar flushes real chunks and stops owned capture');
  // Expiry can happen while username remains unchanged in cached auth state.
  await page.getByRole('button',{name:'/reunions/two',exact:true}).click();await page.getByRole('button',{name:'Enregistrer',exact:true}).click();await page.getByRole('button',{name:'Pause',exact:true}).waitFor();
  await page.evaluate(()=>window.dispatchEvent(new Event('session-expired')));await page.waitForFunction(()=>window.__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));console.log('PASS session-expired stops tracks even with cached same username');
  await page.getByRole('button',{name:'/profil',exact:true}).click();await page.getByRole('button',{name:'/reunions/two',exact:true}).click();
  await page.getByRole('button',{name:'Enregistrer',exact:true}).click();await page.getByRole('button',{name:'Pause',exact:true}).waitFor();
  await page.evaluate(()=>{const channel=new BroadcastChannel('memora-synthetic-session');channel.postMessage({source:'other-tab',kind:'login'});setTimeout(()=>channel.close(),100);});await page.waitForFunction(()=>window.__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));console.log('PASS cross-tab account event stops tracks with same username');
  await page.getByRole('button',{name:'/profil',exact:true}).click();
  // New recording, then logout: active capture must end, not remain in global provider.
  await page.getByRole('button',{name:'/reunions/two',exact:true}).click();await page.getByRole('button',{name:'Enregistrer',exact:true}).click();await page.getByRole('button',{name:'Pause',exact:true}).waitFor();await page.evaluate(()=>window.__logout());await page.waitForFunction(()=>window.__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));console.log('PASS logout stops active parent tracks');
  await page.evaluate(()=>{window.__login();window.__navigate('/reunions/three');});
  await page.getByRole('button',{name:'Tester le microphone',exact:true}).click();await page.getByRole('button',{name:'Arrêter le test',exact:true}).waitFor();
  await page.getByRole('button',{name:'/profil',exact:true}).click();await page.waitForFunction(()=>window.__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));
  await page.evaluate(()=>window.__navigate('/reunions/three'));await page.getByRole('button',{name:'Enregistrer',exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Enregistrer',exact:true}).isEnabled(),true);console.log('PASS navigation stops microphone precheck and permits return');
  await page.evaluate(()=>window.__delay=true);const startsBefore=await page.evaluate(()=>window.__starts);
  await page.getByRole('button',{name:'Enregistrer',exact:true}).click();await page.waitForFunction(()=>Boolean(window.__resolveAcquisition));
  await page.evaluate(()=>window.__logout());await page.waitForTimeout(100);await page.evaluate(()=>window.__resolveAcquisition());
  await page.waitForFunction(()=>window.__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));
  await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>window.__starts),startsBefore);console.log('PASS late getUserMedia after logout is stopped without recorder start');
  assert.deepEqual(errors,[]);console.log('PASS zero browser exceptions');
}finally{if(browser)await browser.close();await rm(folder,{recursive:true,force:true});}
