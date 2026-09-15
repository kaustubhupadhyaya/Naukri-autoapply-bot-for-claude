/* Passive in-page recorder, injected by the watcher (Page.addScriptToEvaluateOnNewDocument
   plus one Runtime.evaluate for the current document).

   Capture-phase listeners only: never preventDefault / stopPropagation, never touches the
   DOM. Events go out through the CDP binding window.__nkw, which disappears when the watcher
   detaches; calls are then silently dropped. isTrusted separates real input from synthetic
   JS clicks/events (the resume-upload and Save-click debates hinged on exactly that). */
(function () {
  if (window.__nkwRec) return;
  window.__nkwRec = true;

  function send(o) {
    try { if (typeof window.__nkw === 'function') window.__nkw(JSON.stringify(o)); } catch (e) {}
  }

  function desc(el) {
    if (!el || el.nodeType !== 1) return null;
    var c = el.className;
    c = String(c && c.baseVal !== undefined ? c.baseVal : c || '');
    var t = el.type === 'password' ? '' : (el.innerText || el.value || '');
    return {
      tag: el.tagName.toLowerCase(), id: el.id || '', cls: c.slice(0, 80),
      text: String(t).replace(/\s+/g, ' ').trim().slice(0, 80),
      type: el.type || '', name: el.name || '', role: el.getAttribute('role') || '',
      inDrawer: !!(el.closest && el.closest('[class*="chatbot"]'))
    };
  }

  ['click', 'submit'].forEach(function (t) {
    document.addEventListener(t, function (e) {
      send({t: t, trusted: e.isTrusted, el: desc(e.target), ts: Date.now()});
    }, true);
  });

  var lastInput = new WeakMap();
  document.addEventListener('input', function (e) {
    var el = e.target, now = Date.now();
    if (!el || el.type === 'password') return;
    if (now - (lastInput.get(el) || 0) < 700) return;  // throttle per element
    lastInput.set(el, now);
    send({t: 'input', trusted: e.isTrusted, el: desc(el), ts: now});
  }, true);

  document.addEventListener('change', function (e) {
    var el = e.target;
    if (!el || el.type === 'password') return;
    var o = {t: 'change', trusted: e.isTrusted, el: desc(el), ts: Date.now()};
    if (el.type === 'file') {
      o.files = el.files ? el.files.length : -1;
      o.names = el.files ? Array.prototype.map.call(el.files, function (f) { return f.name; }) : [];
    }
    send(o);
  }, true);
})();
