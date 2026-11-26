const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '../../Assets/WebGLTemplates/RoadGame/TemplateData/mobile-display.js'), 'utf8');

class Events {
  constructor() { this.events = new Map(); }
  addEventListener(type, handler) {
    if (!this.events.has(type)) this.events.set(type, []);
    this.events.get(type).push(handler);
  }
  dispatch(type, properties = {}) {
    const event = { type, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...properties };
    for (const handler of [...(this.events.get(type) || [])]) handler(event);
    if (typeof this['on' + type] === 'function') this['on' + type](event);
    return event;
  }
}

class Element extends Events {
  constructor() {
    super();
    this.attributes = new Map(); this.styles = new Map(); this.classes = new Set();
    this.open = false; this.hidden = false; this.disabled = false; this.focusCount = 0;
    this.classList = {
      toggle: (name, enabled) => enabled ? this.classes.add(name) : this.classes.delete(name),
      contains: (name) => this.classes.has(name)
    };
    this.style = { setProperty: (name, value) => this.styles.set(name, value), getPropertyValue: (name) => this.styles.get(name) };
  }
  setAttribute(name, value) { this.attributes.set(name, value); if (name === 'open') this.open = true; }
  removeAttribute(name) { this.attributes.delete(name); if (name === 'open') this.open = false; }
  hasAttribute(name) { return this.attributes.has(name); }
  getAttribute(name) { return this.attributes.get(name); }
  focus() { this.focusCount++; }
  click() { if (!this.disabled) this.dispatch('click'); }
}

function setup(options = {}) {
  const root = new Element(), button = new Element(), help = new Element(), close = new Element();
  button.textContent = 'existing SVG'; help.hidden = true;
  help.showModalCount = 0;
  if (options.dialog !== false) {
    help.showModal = function () { this.showModalCount++; this.setAttribute('open', ''); this.hidden = false; };
    help.close = function () { this.removeAttribute('open'); this.dispatch('close'); };
  }
  const elements = { 'fullscreen-button': button, 'display-help': help, 'display-help-close': close };
  const document = new Events();
  document.documentElement = root;
  document.getElementById = (id) => elements[id] || null;
  const window = new Events();
  window.document = document;
  window.navigator = { standalone: !!options.navigatorStandalone };
  window.innerWidth = options.width || 390; window.innerHeight = options.height || 844;
  if (options.viewport !== false) {
    window.visualViewport = new Events();
    Object.assign(window.visualViewport, { width: window.innerWidth, height: 700, scale: 1 }, options.viewport);
  }
  const media = new Map();
  for (const [query, matches] of [
    ['(pointer: coarse)', !!options.coarse],
    ['(max-width: 650px)', window.innerWidth <= 650],
    ['(display-mode: standalone)', !!options.standalone],
    ['(display-mode: fullscreen)', !!options.fullscreenMode]
  ]) {
    const entry = new Events(); entry.matches = matches;
    if (options.legacyMedia) {
      entry.addListener = (handler) => Events.prototype.addEventListener.call(entry, 'change', handler);
      entry.addEventListener = undefined;
    }
    media.set(query, entry);
  }
  window.matchMedia = (query) => media.get(query);
  let nextFrame = 0;
  const frames = new Map(), requests = [], exits = [], order = [];
  window.requestAnimationFrame = (handler) => { frames.set(++nextFrame, handler); return nextFrame; };
  const webkit = options.api === 'webkit';
  if (options.api) {
    root[webkit ? 'webkitRequestFullscreen' : 'requestFullscreen'] = function () {
      requests.push(this); order.push('request');
      if (options.failure === 'throw') throw new Error('Denied synchronously');
      if (options.failure === 'reject') return Promise.reject(new Error('Denied asynchronously'));
      if (options.failure === 'event') return undefined;
      document[webkit ? 'webkitFullscreenElement' : 'fullscreenElement'] = root;
      document.dispatch(webkit ? 'webkitfullscreenchange' : 'fullscreenchange');
      return webkit ? undefined : Promise.resolve();
    };
    document[webkit ? 'webkitExitFullscreen' : 'exitFullscreen'] = function () {
      exits.push(this);
      document[webkit ? 'webkitFullscreenElement' : 'fullscreenElement'] = null;
      document.dispatch(webkit ? 'webkitfullscreenchange' : 'fullscreenchange');
      return webkit ? undefined : Promise.resolve();
    };
  }
  vm.runInNewContext(script, { window });
  return { root, button, help, close, document, window, media, requests, exits, frames, order,
    display: window.RoadGameDisplay,
    flushFrames() { const jobs = [...frames.values()]; frames.clear(); jobs.forEach((handler) => handler()); },
    setMedia(query, matches) { const entry = media.get(query); entry.matches = matches; entry.dispatch('change'); }
  };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test('mobile Play requests document root fullscreen synchronously inside its gesture; ready owns button enablement', async () => {
  const f = setup({ api: 'standard', coarse: true });
  assert.equal(f.button.disabled, true);
  f.order.push('play'); f.display.start(); f.order.push('after');
  assert.deepEqual(f.order, ['play', 'request', 'after']);
  assert.deepEqual(f.requests, [f.root]);
  assert.equal(f.button.disabled, true);
  assert.equal(f.root.classList.contains('mobile-game'), true);
  assert.equal(f.root.classList.contains('native-fullscreen'), true);
  assert.equal(f.root.classList.contains('standalone-game'), true);
  f.display.ready();
  assert.equal(f.button.disabled, false);
  assert.equal(f.button.getAttribute('aria-label'), 'Выйти из полноэкранного режима');
  assert.equal(f.button.getAttribute('aria-pressed'), 'true');
  assert.equal(f.button.textContent, 'existing SVG');
  f.button.click();
  assert.deepEqual(f.exits, [f.document]);
  assert.equal(f.root.classList.contains('native-fullscreen'), false);
  assert.equal(f.root.classList.contains('standalone-game'), false);
  assert.equal(f.button.title, 'На весь экран');
  await tick();
});

test('desktop does not automatically enter fullscreen; explicit ready button still does', () => {
  const f = setup({ api: 'standard', width: 1200 });
  f.display.start(); f.button.click();
  assert.equal(f.requests.length, 0);
  assert.equal(f.root.classList.contains('mobile-game'), false);
  f.display.ready(); f.button.click();
  assert.deepEqual(f.requests, [f.root]);
});

test('coarse wide display and narrow non-coarse display both count as mobile', () => {
  for (const options of [{ coarse: true, width: 1000 }, { coarse: false, width: 390 }]) {
    const f = setup({ ...options, api: 'standard' });
    f.display.start();
    assert.deepEqual(f.requests, [f.root]);
    assert.equal(f.root.classList.contains('mobile-game'), true);
  }
});

test('navigator standalone and standalone/fullscreen display modes skip automatic requests', () => {
  for (const flag of ['navigatorStandalone', 'standalone', 'fullscreenMode']) {
    const f = setup({ api: 'standard', [flag]: true });
    f.display.start();
    assert.equal(f.requests.length, 0);
    assert.equal(f.root.classList.contains('standalone-game'), true);
    assert.equal(f.root.classList.contains('native-fullscreen'), false);
  }
});

test('unsupported fullscreen never opens help during startup; explicit button and close/Escape do', () => {
  const f = setup();
  f.display.start(); f.display.ready();
  assert.equal(f.help.showModalCount, 0);
  assert.equal(f.button.title, 'Как открыть на весь экран');
  f.button.click();
  assert.equal(f.help.showModalCount, 1);
  assert.equal(f.help.open, true);
  assert.ok(f.close.focusCount > 0);
  const escape = f.document.dispatch('keydown', { key: 'Escape' });
  assert.equal(escape.defaultPrevented, true);
  assert.equal(f.help.open, false);
  assert.equal(f.help.hidden, true);
  f.button.click(); f.close.click();
  assert.equal(f.help.open, false);
  assert.ok(f.button.focusCount > 0);
});

for (const failure of ['throw', 'reject']) test(failure + ' request is safe and help remains explicit', async () => {
  const f = setup({ api: 'standard', failure });
  f.display.start(); await tick();
  assert.equal(f.help.open, false);
  assert.equal(f.help.showModalCount, 0);
  assert.equal(f.root.classList.contains('native-fullscreen'), false);
  f.display.ready(); f.button.click(); await tick();
  assert.equal(f.help.open, true);
  assert.equal(f.help.showModalCount, 1);
  assert.equal(f.button.getAttribute('aria-label'), 'Как открыть на весь экран');
  f.help.close();
  assert.equal(f.help.hidden, true);
});

test('WebKit void-return fullscreen and error events use real state and preserve explicit help policy', () => {
  const f = setup({ api: 'webkit' });
  f.display.start(); f.display.ready();
  assert.deepEqual(f.requests, [f.root]);
  assert.equal(f.root.classList.contains('native-fullscreen'), true);
  f.button.click();
  assert.deepEqual(f.exits, [f.document]);
  assert.equal(f.root.classList.contains('native-fullscreen'), false);
  const denied = setup({ api: 'webkit', failure: 'event' });
  denied.display.start(); denied.document.dispatch('webkitfullscreenerror');
  assert.equal(denied.help.open, false);
  denied.display.ready(); denied.button.click(); denied.document.dispatch('webkitfullscreenerror');
  assert.equal(denied.help.open, true);
});

test('help works without the dialog API and native cancel is handled', () => {
  const f = setup({ dialog: false });
  f.display.ready(); f.button.click();
  assert.equal(f.help.hasAttribute('open'), true);
  f.close.click();
  assert.equal(f.help.hasAttribute('open'), false);
  assert.equal(f.help.hidden, true);
  const native = setup();
  native.display.ready(); native.button.click();
  const cancel = native.help.dispatch('cancel');
  assert.equal(cancel.defaultPrevented, true);
  assert.equal(native.help.open, false);
});

test('visual viewport is used at scale 1; zoom falls back to inner size; resize/rotation events are RAF-debounced', () => {
  const f = setup({ viewport: { width: 390, height: 700.5 } });
  assert.equal(f.root.style.getPropertyValue('--roadgame-height'), '700.5px');
  assert.equal(f.root.style.getPropertyValue('--roadgame-width'), '390px');
  f.window.visualViewport.height = 620;
  f.window.visualViewport.dispatch('resize');
  f.window.dispatch('resize'); f.window.dispatch('orientationchange');
  assert.equal(f.frames.size, 1);
  assert.equal(f.root.style.getPropertyValue('--roadgame-height'), '700.5px');
  f.flushFrames();
  assert.equal(f.root.style.getPropertyValue('--roadgame-height'), '620px');
  f.window.visualViewport.scale = 2;
  f.display.refresh();
  assert.equal(f.root.style.getPropertyValue('--roadgame-height'), '844px');
  f.window.visualViewport.scale = 1;
  Object.assign(f.window.visualViewport, { width: 844, height: 335 });
  f.window.innerWidth = 844; f.window.innerHeight = 390;
  f.setMedia('(max-width: 650px)', false); f.window.dispatch('orientationchange');
  f.flushFrames();
  assert.equal(f.root.style.getPropertyValue('--roadgame-width'), '844px');
  assert.equal(f.root.style.getPropertyValue('--roadgame-height'), '335px');
  assert.equal(f.root.classList.contains('mobile-game'), false);
});

test('legacy media listeners, inner-size fallback and fullscreen exit events refresh state without auto requests', () => {
  const f = setup({ legacyMedia: true, viewport: false, width: 1200 });
  assert.equal(f.root.style.getPropertyValue('--roadgame-height'), '844px');
  f.setMedia('(pointer: coarse)', true); f.setMedia('(display-mode: standalone)', true); f.flushFrames();
  assert.equal(f.root.classList.contains('mobile-game'), true);
  assert.equal(f.root.classList.contains('standalone-game'), true);
  assert.equal(f.requests.length, 0);
  f.document.fullscreenElement = f.root; f.document.dispatch('fullscreenchange');
  assert.equal(f.root.classList.contains('native-fullscreen'), true);
  f.document.fullscreenElement = null; f.document.dispatch('fullscreenchange');
  assert.equal(f.root.classList.contains('native-fullscreen'), false);
  assert.equal(f.root.classList.contains('standalone-game'), true);
});
