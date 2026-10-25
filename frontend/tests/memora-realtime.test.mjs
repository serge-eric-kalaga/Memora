import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import ts from "typescript";
const source = (await readFile(new URL("../src/features/memora/realtime-client.ts", import.meta.url), "utf8")).replace(/import .* from "\.\/api";\n/, "");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 } }).outputText;
const pause = () => new Promise((resolve) => setImmediate(resolve));
function harness(status = 200) {
  let now = 0, next = 0;
  const timers = new Map(), requests = [], controllers = [];
  const events = new EventTarget();
  const schedule = (fn, delay, repeat) => {
    const id = ++next;
    timers.set(id, { fn, at: now + delay, repeat });
    return id;
  };
  const context = vm.createContext({
    exports: {}, AbortController, TextDecoder, Math,
    navigator: { onLine: true }, window: events,
    accessHeaders: (a) => a.token ? { "X-Share-Token": a.token, "X-Share-Password": a.password } : {},
    setTimeout: (fn, delay) => schedule(fn, delay), setInterval: (fn, delay) => schedule(fn, delay, delay),
    clearTimeout: (id) => timers.delete(id), clearInterval: (id) => timers.delete(id),
    fetch: async (url, init) => {
      requests.push({ url, init });
      const body = new ReadableStream({ start(controller) {
        controllers.push(controller);
        init.signal.addEventListener("abort", () => { try { controller.close(); } catch {} });
      } });
      return new Response(body, { status, headers: { "content-type": "text/event-stream" } });
    },
  });
  vm.runInContext(code, context);
  return {
    subscribe: context.exports.subscribeUpdates, requests, timers,
    send: (frame) => controllers.at(-1).enqueue(new TextEncoder().encode(frame)),
    async advance(ms) {
      now += ms;
      for (const [id, timer] of [...timers]) if (timer.at <= now) {
        if (timer.repeat) timer.at = now + timer.repeat; else timers.delete(id);
        timer.fn();
      }
      await pause();
    },
  };
}
test("one shared stream, split frames, coalescing, heartbeat without polling", async () => {
  const h = harness(); let a = 0, b = 0;
  const closeA = h.subscribe("meeting", { token: "private-token", password: "private-password" }, () => a++);
  const closeB = h.subscribe("meeting", { token: "private-token", password: "private-password" }, () => b++);
  await pause();
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].url, "/mapi/events?meeting=meeting");
  assert.equal(h.requests[0].init.headers["X-Share-Password"], "private-password");
  h.send("event: ref"); await pause();
  h.send("resh\ndata: {}\n\nevent: refresh\ndata: {}\n\n"); await pause(); await h.advance(200);
  assert.deepEqual([a, b], [1, 1]);
  h.send(": heartbeat\n\n"); await pause(); await h.advance(8000);
  assert.deepEqual([a, b], [1, 1]); assert.equal(h.requests.length, 1);
  closeA(); assert.equal(h.requests[0].init.signal.aborted, false);
  closeB(); await pause();
  assert.equal(h.requests[0].init.signal.aborted, true); assert.equal(h.timers.size, 0);
});
test("reconnect and fallback stops after stream recovery", async () => {
  const h = harness(); let count = 0;
  const close = h.subscribe(undefined, {}, () => count++);
  await pause(); h.send("event: unavailable\ndata: {}\n\n"); await pause(); await h.advance(200);
  assert.equal(count, 1);
  await h.advance(2000); assert.equal(h.requests.length, 2);
  h.send("event: refresh\ndata: {}\n\n"); await pause(); await h.advance(200);
  assert.equal(count, 2); await h.advance(16000); assert.equal(count, 2);
  close(); await pause(); assert.equal(h.timers.size, 0);
});
test("revoked stream refreshes access once then stops", async () => {
  const h = harness(404); let count = 0;
  const close = h.subscribe("meeting", {}, () => count++);
  await pause(); await h.advance(200); await h.advance(60000);
  assert.equal(count, 1); assert.equal(h.requests.length, 1);
  close(); assert.equal(h.timers.size, 0);
});
test("unavailable PostgreSQL uses bounded reconnect and 15-second fallback", async () => {
  const h = harness(503); let count = 0;
  const close = h.subscribe(undefined, {}, () => count++);
  await pause(); await h.advance(15000); await h.advance(200);
  assert.equal(count, 1); assert.ok(h.requests.length >= 2);
  close(); await pause(); assert.equal(h.timers.size, 0);
});
