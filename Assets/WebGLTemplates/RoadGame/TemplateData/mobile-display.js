/* Display controls for the page around Unity; no game, audio or save state is changed. */
(function (window) {
  'use strict';
  const document = window.document;
  const root = document.documentElement;
  const button = document.getElementById('fullscreen-button');
  const help = document.getElementById('display-help');
  const helpClose = document.getElementById('display-help-close');
  const media = (query) => window.matchMedia ? window.matchMedia(query) : null;
  const coarse = media('(pointer: coarse)');
  const narrow = media('(max-width: 650px)');
  const standalone = media('(display-mode: standalone)');
  const fullscreenMode = media('(display-mode: fullscreen)');
  let isReady = false, denied = false, pending = null, frame = null;

  const mobile = () => !!(coarse && coarse.matches) ||
    (narrow ? narrow.matches : window.innerWidth <= 650);
  const nativeFullscreen = () => !!(document.fullscreenElement || document.webkitFullscreenElement ||
    document.webkitCurrentFullScreenElement || document.webkitIsFullScreen);
  const isStandalone = () => !!(window.navigator.standalone || (standalone && standalone.matches) ||
    (fullscreenMode && fullscreenMode.matches) || nativeFullscreen());
  const request = () => typeof root.requestFullscreen === 'function' ? root.requestFullscreen :
    typeof root.webkitRequestFullscreen === 'function' ? root.webkitRequestFullscreen : root.webkitRequestFullScreen;
  const exit = () => typeof document.exitFullscreen === 'function' ? document.exitFullscreen :
    typeof document.webkitExitFullscreen === 'function' ? document.webkitExitFullscreen : document.webkitCancelFullScreen;

  function refresh() {
    const active = nativeFullscreen();
    root.classList.toggle('mobile-game', mobile());
    root.classList.toggle('standalone-game', isStandalone());
    root.classList.toggle('native-fullscreen', active);
    const viewport = window.visualViewport;
    const useViewport = viewport && Math.abs(viewport.scale - 1) < 0.001;
    for (const axis of ['width', 'height']) {
      const value = useViewport && viewport[axis] > 0 ? viewport[axis] :
        window[axis === 'width' ? 'innerWidth' : 'innerHeight'];
      if (Number.isFinite(value) && value > 0) root.style.setProperty('--roadgame-' + axis, value + 'px');
    }
    if (button) {
      const label = active ? 'Выйти из полноэкранного режима' :
        denied || typeof request() !== 'function' ? 'Как открыть на весь экран' : 'На весь экран';
      button.title = label;
      button.setAttribute('aria-label', label);
      button.setAttribute('aria-pressed', String(active));
      button.disabled = !isReady;
    }
  }

  function schedule() {
    if (frame !== null) return;
    const enqueue = window.requestAnimationFrame ? window.requestAnimationFrame.bind(window) :
      (callback) => window.setTimeout(callback, 0);
    frame = enqueue(() => { frame = null; refresh(); });
  }

  function helpIsOpen() {
    return help && !help.hidden && (help.open || help.hasAttribute('open'));
  }

  function helpClosed() {
    if (help) help.hidden = true;
    if (button && isReady && typeof button.focus === 'function') button.focus();
  }

  function closeHelp() {
    if (!helpIsOpen()) return;
    if (typeof help.close === 'function') {
      try { help.close(); } catch (_) { /* Attribute fallback below also works without dialog support. */ }
    }
    help.removeAttribute('open');
    helpClosed();
  }

  function showHelp() {
    if (!help || helpIsOpen()) return;
    help.hidden = false;
    if (typeof help.showModal === 'function') {
      try { help.showModal(); } catch (_) { help.setAttribute('open', ''); }
    } else help.setAttribute('open', '');
    if (helpClose && typeof helpClose.focus === 'function') helpClose.focus();
  }

  function fail(action) {
    if (pending !== action) return;
    pending = null;
    denied = true;
    refresh();
    if (action.manual) showHelp();
  }

  function invoke(target, method, manual) {
    if (typeof method !== 'function') { if (manual) showHelp(); return; }
    const action = { manual };
    pending = action;
    let result;
    // This call must stay synchronous inside the Play/click user activation, before Unity starts loading.
    try { result = method.call(target); } catch (_) { fail(action); return; }
    if (result && typeof result.then === 'function') {
      Promise.resolve(result).then(() => {
        if (pending === action) pending = null;
        refresh();
      }, () => fail(action));
    }
  }

  function start() {
    refresh();
    if (mobile() && !isStandalone()) invoke(root, request(), false);
  }

  function ready() { isReady = true; refresh(); }

  if (button) button.onclick = (event) => {
    if (event) event.preventDefault();
    if (!isReady) return;
    if (nativeFullscreen()) invoke(document, exit(), true);
    else invoke(root, request(), true);
  };
  if (helpClose) helpClose.addEventListener('click', closeHelp);
  if (help) {
    help.addEventListener('cancel', (event) => { event.preventDefault(); closeHelp(); });
    help.addEventListener('close', helpClosed);
  }
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && helpIsOpen()) { event.preventDefault(); closeHelp(); }
  });
  const changed = () => { pending = null; denied = false; refresh(); };
  document.addEventListener('fullscreenchange', changed);
  document.addEventListener('webkitfullscreenchange', changed);
  const error = () => { if (pending) fail(pending); };
  document.addEventListener('fullscreenerror', error);
  document.addEventListener('webkitfullscreenerror', error);
  window.addEventListener('resize', schedule);
  window.addEventListener('orientationchange', schedule);
  if (window.visualViewport) window.visualViewport.addEventListener('resize', schedule);
  for (const query of [coarse, narrow, standalone, fullscreenMode]) {
    if (!query) continue;
    if (typeof query.addEventListener === 'function') query.addEventListener('change', schedule);
    else if (typeof query.addListener === 'function') query.addListener(schedule);
  }
  window.RoadGameDisplay = { start, ready, refresh };
  refresh();
})(window);
