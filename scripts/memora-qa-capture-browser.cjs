// Exercise real Chromium MediaRecorder with synthetic fixture, never getUserMedia.
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('../frontend/node_modules/playwright');
let browser;
(async () => {
 const root=path.resolve(__dirname,'..');
 browser=await chromium.launch({headless:true, executablePath:process.env.MEMORA_QA_BROWSER});
 const page=await browser.newPage();
 const input=fs.readFileSync(path.join(root,'backend/test/fixtures/memora/english.wav')).toString('base64');
 const result=await page.evaluate(async input => {
  const context=new AudioContext({sampleRate:48000});
  const bytes=Uint8Array.from(atob(input), c=>c.charCodeAt(0));
  const buffer=await context.decodeAudioData(bytes.buffer);
  const source=context.createBufferSource();source.buffer=buffer;
  const destination=context.createMediaStreamDestination();source.connect(destination);
  const mimeType=['audio/webm;codecs=opus','audio/mp4','audio/webm'].find(t=>MediaRecorder.isTypeSupported(t));
  const recorder=new MediaRecorder(destination.stream, mimeType?{mimeType}:{});
  const chunks=[];recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
  const finished=new Promise(resolve=>{recorder.onstop=resolve});
  source.onended=()=>{if(recorder.state!=='inactive')recorder.stop()};
  const transitions=[];
  recorder.start(1000);source.start();await context.resume();transitions.push(recorder.state);
  await new Promise(resolve=>setTimeout(resolve,2500));
  recorder.pause();await context.suspend();await new Promise(resolve=>setTimeout(resolve,50));transitions.push(recorder.state);
  await new Promise(resolve=>setTimeout(resolve,700));
  recorder.resume();await context.resume();await new Promise(resolve=>setTimeout(resolve,50));transitions.push(recorder.state);
  await finished;
  const blob=new Blob(chunks,{type:recorder.mimeType});
  const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob)});
  const meta={mime:recorder.mimeType,bitrate:recorder.audioBitsPerSecond,chunks:chunks.length,sourceDuration:buffer.duration,transitions};
  await context.close();return {...meta,encoded};
 },input);
 fs.mkdirSync(path.join(root,'.memora/capture-qa'),{recursive:true});
 fs.writeFileSync(path.join(root,'.memora/capture-qa/browser-pause-resume.webm'),Buffer.from(result.encoded,'base64'));
 delete result.encoded;
 fs.writeFileSync(path.join(root,'agents/logs/capture-browser.json'),JSON.stringify(result,null,2));
 console.log(JSON.stringify(result));await browser.close();
})().catch(async error=>{console.error(error.message);if(browser)await browser.close();process.exitCode=1});
