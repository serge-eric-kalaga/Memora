import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
const source = await readFile(
  new URL(
    "../src/features/memora/microphone-check.helpers.ts",
    import.meta.url,
  ),
  "utf8",
);
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2022,
  },
}).outputText;
const { microphoneMetrics, microphoneError, releaseMicrophoneResources } =
  await import(
    `data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`
  );

test("silence and empty buffers produce finite zero level, not clipping", () => {
  for (const samples of [new Float32Array(2048), []]) {
    assert.deepEqual(microphoneMetrics(samples), {
      rms: 0,
      peak: 0,
      dbfs: -60,
      level: 0,
      clipping: false,
    });
  }
});
test("synthetic sine RMS is amplitude/sqrt(2) and level increases with signal", () => {
  const sine = Float32Array.from(
    { length: 2048 },
    (_, i) => 0.2 * Math.sin((2 * Math.PI * i) / 32),
  );
  const result = microphoneMetrics(sine);
  assert.ok(Math.abs(result.rms - 0.2 / Math.sqrt(2)) < 1e-6);
  assert.equal(result.clipping, false);
  assert.ok(result.level > microphoneMetrics(sine.map((v) => v / 10)).level);
});
test("positive and negative near-full-scale samples warn of possible clipping", () => {
  assert.equal(microphoneMetrics([0, 0.99]).clipping, true);
  assert.equal(microphoneMetrics([0, -1]).clipping, true);
  assert.equal(microphoneMetrics([0, 0.9]).clipping, false);
  assert.equal(microphoneMetrics([NaN, Infinity]).level, 0);
});
test("permission, missing device and busy-device errors are actionable in both languages", () => {
  assert.match(microphoneError("NotAllowedError", "fr"), /Autorisez/);
  assert.match(microphoneError("NotAllowedError", "en"), /Allow microphone/);
  assert.match(microphoneError("NotFoundError", "fr"), /Branchez/);
  assert.match(microphoneError("OverconstrainedError", "en"), /selected input/);
  assert.match(microphoneError("NotReadableError", "en"), /other apps/);
  assert.match(microphoneError("Unsupported", "fr"), /localhost ou HTTPS/);
  assert.ok(microphoneError("UnknownFailure", "en"));
});
test("cleanup stops recording, all tracks and graph/context exactly once, and cancels animation", async () => {
  const calls = [];
  const track = () => ({
    onended: () => {},
    onmute: () => {},
    onunmute: () => {},
    stop() {
      calls.push("track");
    },
  });
  const tracks = [track(), track()];
  const resources = {
    frame: 4,
    recorder: {
      state: "recording",
      stop() {
        calls.push("recorder");
      },
    },
    source: {
      disconnect() {
        calls.push("source");
      },
    },
    analyser: {
      disconnect() {
        calls.push("analyser");
      },
    },
    stream: { getTracks: () => tracks },
    context: {
      state: "running",
      close() {
        calls.push("context");
        return Promise.resolve();
      },
    },
  };
  const cancel = (id) => calls.push(`frame${id}`);
  releaseMicrophoneResources(resources, cancel);
  releaseMicrophoneResources(resources, cancel);
  await Promise.resolve();
  assert.deepEqual(calls, [
    "frame4",
    "recorder",
    "source",
    "analyser",
    "track",
    "track",
    "context",
  ]);
  assert.ok(Object.values(resources).every((v) => v === null));
  assert.ok(
    tracks.every(
      (t) => t.onended === null && t.onmute === null && t.onunmute === null,
    ),
  );
});
test("cleanup survives an already-ended recorder and disconnected nodes", async () => {
  let stopped = 0;
  const resources = {
    frame: null,
    recorder: {
      state: "recording",
      stop() {
        throw Error("ended");
      },
    },
    source: {
      disconnect() {
        throw Error("disconnected");
      },
    },
    analyser: null,
    stream: {
      getTracks: () => [
        {
          stop() {
            stopped++;
          },
        },
      ],
    },
    context: { state: "running", close: () => Promise.reject(Error("closed")) },
  };
  releaseMicrophoneResources(resources, () => {});
  await Promise.resolve();
  assert.equal(stopped, 1);
  assert.equal(resources.stream, null);
});
