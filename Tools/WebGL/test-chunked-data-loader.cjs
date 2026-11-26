const { test } = require('node:test');
const assert = require('node:assert/strict');
const { gzipSync } = require('node:zlib');
const { install, run } = require('./chunked-data-loader.js');
const base = 'https://game.example/';
const manifest = { files: { 'Build/hash.data.unityweb': { bytes: 5, parts: [
  { url: 'Build/hash.part000.bin', bytes: 3 }, { url: 'Build/hash.part001.bin', bytes: 2 }
] } } };
// Existing cases exercise Unity's compressed fallback even when this Node version has a native inflater.
const make = (fetch) => ({ fetch, document: { baseURI: base }, DecompressionStream: undefined });
const config = () => ({ dataUrl: 'Build/hash.data.unityweb' });

function gzipFixture() {
  const payload = Buffer.alloc(128 * 1024);
  let random = 0x78563412;
  for (let i = 0; i < payload.length; i++) {
    random ^= random << 13; random ^= random >>> 17; random ^= random << 5;
    payload[i] = random & 255;
  }
  payload.write('UnityWebData1.0\0');
  const gzip = gzipSync(payload);
  // Unity puts this gzip comment in its fallback files; it must survive splits through the header too.
  const header = Buffer.from(gzip.subarray(0, 10));
  header[3] |= 16;
  const compressed = Buffer.concat([header, Buffer.from('UnityWeb Compressed Content (gzip)\0'), gzip.subarray(10)]);
  const lengths = [3, 14, 29, 4093, 16381];
  const parts = [];
  for (let offset = 0, index = 0; offset < compressed.length; index++) {
    const bytes = compressed.subarray(offset, offset + (lengths[index] || 16381));
    parts.push({ url: 'Build/native.part' + index + '.bin', bytes: bytes.length, data: bytes });
    offset += bytes.length;
  }
  const file = { bytes: compressed.length, uncompressedBytes: payload.length,
    parts: parts.map(({ url, bytes }) => ({ url, bytes })) };
  return { payload, compressed, parts, file, manifest: { files: { 'Build/hash.data.unityweb': file } } };
}

test('native gzip streams decoded Unity bytes across part/header boundaries with exact progress length', async () => {
  const fixture = gzipFixture(), calls = [];
  const fetch = async (url) => {
    calls.push(url);
    const part = fixture.parts.find((p) => new URL(p.url, base).href === url);
    const response = new Response(part ? part.data : 'unrelated');
    response.arrayBuffer = () => { throw new Error('Parts must be streamed, never buffered with arrayBuffer()'); };
    return response;
  };
  const env = make(fetch), cfg = config();
  env.DecompressionStream = DecompressionStream;
  const previousCacheControl = () => 'immutable';
  cfg.cacheControl = previousCacheControl;
  const restore = install(cfg, fixture.manifest, env);
  try {
    const response = await env.fetch(cfg.dataUrl);
    assert.equal(response.headers.get('Content-Length'), String(fixture.payload.length));
    assert.equal(response.headers.get('Content-Encoding'), null);
    assert.equal(cfg.cacheControl(cfg.dataUrl), 'no-store');
    assert.equal(cfg.cacheControl('unrelated'), 'immutable');
    const output = new Uint8Array(Number(response.headers.get('Content-Length')));
    const reader = response.body.getReader(), progress = [];
    let loaded = 0;
    for (;;) {
      const next = await reader.read();
      if (next.done) break;
      output.set(next.value, loaded);
      loaded += next.value.length;
      progress.push(loaded);
    }
    assert.equal(loaded, output.length);
    assert.deepEqual(Buffer.from(output), fixture.payload);
    assert.ok(progress.length > 1 && progress[0] < loaded);
    assert.ok(progress.every((n, i) => i === 0 || n > progress[i - 1]));
    assert.deepEqual(calls, fixture.parts.map((p) => new URL(p.url, base).href));
    await env.fetch('unrelated');
    assert.equal(calls.at(-1), 'unrelated');
  } finally { restore(); }
  assert.equal(env.fetch, fetch);
  assert.equal(cfg.cacheControl, previousCacheControl);
});

test('unsupported gzip constructor preserves the compressed Unity fallback and its original length', async () => {
  const fixture = gzipFixture();
  let attempts = 0;
  const env = make(async (url) => new Response(fixture.parts.find((p) => new URL(p.url, base).href === url).data));
  env.DecompressionStream = class { constructor() { attempts++; throw new TypeError('gzip unavailable'); } };
  const restore = install(config(), fixture.manifest, env);
  try {
    const response = await env.fetch('Build/hash.data.unityweb');
    assert.equal(response.headers.get('Content-Length'), String(fixture.compressed.length));
    assert.equal(response.headers.get('Content-Encoding'), null);
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), fixture.compressed);
    assert.equal(attempts, 1);
  } finally { restore(); }
});

test('native gzip is skipped without a trustworthy decoded length', async () => {
  let attempts = 0;
  const env = make(async (url) => new Response(url.endsWith('000.bin') ? new Uint8Array([1, 2, 3]) : new Uint8Array([4, 5])));
  env.DecompressionStream = class { constructor() { attempts++; throw new Error('must not construct'); } };
  const restore = install(config(), manifest, env);
  try {
    assert.deepEqual(new Uint8Array(await (await env.fetch('Build/hash.data.unityweb')).arrayBuffer()), new Uint8Array([1, 2, 3, 4, 5]));
    assert.equal(attempts, 0);
  } finally { restore(); }
});

test('cancel of a native decoded stream aborts its active part without fetching the next part', { timeout: 3000 }, async () => {
  const fixture = gzipFixture();
  let signal, cancelled = false, calls = 0, finishPull, onCancelled;
  const cancellation = new Promise((resolve) => { onCancelled = resolve; });
  const env = make(async (_, options) => {
    calls++; signal = options.signal;
    return new Response(new ReadableStream({
      start(controller) { controller.enqueue(fixture.compressed.subarray(0, 4096)); },
      pull() { return new Promise((resolve) => { finishPull = resolve; }); },
      cancel() { cancelled = true; if (finishPull) finishPull(); onCancelled(); }
    }));
  });
  env.DecompressionStream = DecompressionStream;
  const file = { bytes: fixture.compressed.length + 1, uncompressedBytes: fixture.payload.length,
    parts: [{ url: 'Build/active.bin', bytes: fixture.compressed.length }, { url: 'Build/never.bin', bytes: 1 }] };
  const restore = install(config(), { files: { 'Build/hash.data.unityweb': file } }, env);
  try {
    const reader = (await env.fetch('Build/hash.data.unityweb')).body.getReader();
    const first = await reader.read();
    assert.ok(first.value.length > 0 && first.value.length < fixture.payload.length);
    await reader.cancel('test');
    await cancellation;
    assert.equal(signal.aborted, true);
    assert.equal(cancelled, true);
    assert.equal(calls, 1);
  } finally { restore(); }
});

test('native gzip corruption rejects instead of refetching or silently falling back', async () => {
  const fixture = gzipFixture(), bad = Buffer.from(fixture.compressed);
  bad[bad.length - 8] ^= 1; // gzip CRC
  let calls = 0;
  const env = make(async () => { calls++; return new Response(bad); });
  env.DecompressionStream = DecompressionStream;
  const file = { bytes: bad.length, uncompressedBytes: fixture.payload.length,
    parts: [{ url: 'Build/corrupt.bin', bytes: bad.length }] };
  const restore = install(config(), { files: { 'Build/hash.data.unityweb': file } }, env);
  try {
    await assert.rejects((await env.fetch('Build/hash.data.unityweb')).arrayBuffer());
    assert.equal(calls, 1);
  } finally { restore(); }
});

test('byte order, known-length streaming progress, scoped fetch and cache, restoration', async () => {
  const calls = [];
  const fetch = async (url) => { calls.push(url); return new Response(url.endsWith('000.bin') ? new Uint8Array([1, 2, 3]) : new Uint8Array([4, 5])); };
  const env = make(fetch), cfg = config();
  const restore = install(cfg, manifest, env);
  assert.equal(cfg.cacheControl(cfg.dataUrl), 'no-store');
  const response = await env.fetch(cfg.dataUrl);
  assert.equal(response.headers.get('Content-Length'), '5');
  assert.equal(response.headers.get('Content-Encoding'), null);
  const reader = response.body.getReader();
  const bytes = [], progress = [];
  for (;;) { const next = await reader.read(); if (next.done) break; bytes.push(...next.value); progress.push(bytes.length); }
  assert.deepEqual(bytes, [1, 2, 3, 4, 5]);
  assert.deepEqual(progress, [3, 5]);
  assert.deepEqual(calls, [base + 'Build/hash.part000.bin', base + 'Build/hash.part001.bin']);
  await env.fetch('unrelated');
  assert.equal(calls.at(-1), 'unrelated');
  restore();
  assert.equal(env.fetch, fetch);
  assert.equal(cfg.cacheControl, undefined);
});

for (const [name, response, pattern] of [
  ['missing', () => new Response('', { status: 404 }), /HTTP 404/],
  ['truncated', () => new Response(new Uint8Array([1, 2])), /Truncated/],
  ['oversized', () => new Response(new Uint8Array([1, 2, 3, 4])), /Oversized/]
]) test(name + ' chunk rejects instead of silently loading wrong data', async () => {
  const env = make(async () => response()), cfg = config();
  const restore = install(cfg, manifest, env);
  await assert.rejects((await env.fetch(cfg.dataUrl)).arrayBuffer(), pattern);
  restore();
});

test('cancel aborts active part and stops fetching subsequent parts', async () => {
  let signal, cancelled = false, calls = 0;
  const env = make(async (_, options) => {
    calls++; signal = options.signal;
    return new Response(new ReadableStream({ pull(controller) { controller.enqueue(new Uint8Array([1])); }, cancel() { cancelled = true; } }));
  });
  const restore = install(config(), manifest, env);
  const reader = (await env.fetch('Build/hash.data.unityweb')).body.getReader();
  await reader.read();
  await reader.cancel('test');
  assert.equal(signal.aborted, true);
  assert.equal(cancelled, true);
  assert.equal(calls, 1);
  restore();
});

test('AbortSignal rejects an active download', async () => {
  const control = new AbortController();
  const env = make(async (_, options) => new Promise((_, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason))));
  const restore = install(config(), manifest, env);
  const response = await env.fetch('Build/hash.data.unityweb', { signal: control.signal });
  const pending = response.arrayBuffer();
  control.abort(new Error('stopped'));
  await assert.rejects(pending, /stopped/);
  restore();
});

test('startup success, async rejection and sync exception always restore fetch', async () => {
  for (const start of [() => 42, () => Promise.reject(new Error('async')), () => { throw new Error('sync'); }]) {
    const fetch = async () => new Response(''), env = make(fetch), cfg = config();
    try { await run(cfg, manifest, start, env); } catch (_) {}
    assert.equal(env.fetch, fetch);
    assert.equal(cfg.cacheControl, undefined);
  }
});
