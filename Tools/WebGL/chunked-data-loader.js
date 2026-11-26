/* Reassemble hashed Unity files on static hosts with a per-file size limit. */
(function (root) {
  'use strict';

  function install(config, manifest, env = root) {
    const originalFetch = env.fetch;
    const previousCacheControl = config.cacheControl;
    const base = env.document.baseURI;
    const files = new Map(Object.entries(manifest.files).map(([name, file]) =>
      [new URL(name, base).href, file]));
    const absolute = (value) => new URL(typeof value === 'string' || value instanceof URL ? value : value.url, base).href;

    config.cacheControl = function (url) {
      if (files.has(absolute(url))) return 'no-store';
      if (previousCacheControl) return previousCacheControl(url);
      return url === config.dataUrl || (config.primaryDataUrls || []).includes(url) ||
        (config.secondaryDataUrls || []).includes(url) || /\.bundle/.test(url) ? 'must-revalidate' : 'no-store';
    };

    const wrappedFetch = async function (input, init = {}) {
      const file = files.get(absolute(input));
      const method = (init.method || input.method || 'GET').toUpperCase();
      if (!file || method !== 'GET') return originalFetch.call(env, input, init);
      // Let the browser inflate as bytes arrive. Unity's gzip fallback first buffers the entire compressed file,
      // then its worker holds both output chunks and a second flattened copy of the decoded file.
      let inflater;
      if (Number.isSafeInteger(file.uncompressedBytes) && file.uncompressedBytes > 0 &&
          typeof env.DecompressionStream === 'function') {
        try { inflater = new env.DecompressionStream('gzip'); } catch (_) { /* Keep Unity's fallback when unsupported. */ }
      }
      const abort = new AbortController();
      const signal = init.signal || input.signal;
      let reader, index = 0, partBytes = 0, total = 0;
      const onAbort = () => abort.abort(signal.reason);
      const cleanup = () => signal && signal.removeEventListener('abort', onAbort);
      if (signal) {
        if (signal.aborted) throw signal.reason || new DOMException('Aborted', 'AbortError');
        signal.addEventListener('abort', onAbort, { once: true });
      }
      const body = new ReadableStream({
        async pull(controller) {
          try {
            if (abort.signal.aborted) throw abort.signal.reason || new DOMException('Aborted', 'AbortError');
            while (index < file.parts.length) {
              const part = file.parts[index];
              if (!reader) {
                const response = await originalFetch.call(env, new URL(part.url, base).href,
                  { ...init, method: 'GET', signal: abort.signal });
                if (response.status !== 200 || !response.body) throw new Error('Unable to load Unity part: ' + part.url + ' (HTTP ' + response.status + ')');
                reader = response.body.getReader();
                partBytes = 0;
              }
              const result = await reader.read();
              if (result.done) {
                reader.releaseLock();
                reader = null;
                if (partBytes !== part.bytes) throw new Error('Truncated Unity part: ' + part.url);
                index++;
                continue;
              }
              partBytes += result.value.byteLength;
              total += result.value.byteLength;
              if (partBytes > part.bytes || total > file.bytes) throw new Error('Oversized Unity part: ' + part.url);
              controller.enqueue(result.value);
              return;
            }
            if (total !== file.bytes) throw new Error('Unity data size mismatch');
            cleanup();
            controller.close();
          } catch (error) {
            cleanup();
            abort.abort(error);
            if (reader) await reader.cancel(error).catch(() => {});
            controller.error(error);
          }
        },
        async cancel(reason) {
          cleanup();
          abort.abort(reason);
          if (reader) await reader.cancel(reason);
        }
      });
      return new Response(inflater ? body.pipeThrough(inflater) : body, { status: 200, headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Length': String(inflater ? file.uncompressedBytes : file.bytes),
        'Cache-Control': 'no-store'
        // No Content-Encoding: the native path is already decoded, and the legacy path uses Unity's gzip marker.
      } });
    };
    env.fetch = wrappedFetch;
    return function restore() {
      if (env.fetch === wrappedFetch) env.fetch = originalFetch;
      if (previousCacheControl === undefined) delete config.cacheControl;
      else config.cacheControl = previousCacheControl;
    };
  }

  async function run(config, manifest, start, env = root) {
    const restore = install(config, manifest, env);
    try { return await start(); } finally { restore(); }
  }
  root.RoadGameChunkedData = { install, run };
  if (typeof module !== 'undefined') module.exports = root.RoadGameChunkedData;
})(typeof window !== 'undefined' ? window : globalThis);
