/* Biotide homepage scenes. Page-local: the scroll-craft engine stays untouched.
   Everything here reads an act's --sc-p and writes opacity, a clip and text only. */

/* The site header is sticky; landing.css keeps every pinned stage below it. */
(function () {
  var head = document.querySelector('.site-header');
  function set() { document.documentElement.style.setProperty('--hdr', (head ? head.getBoundingClientRect().height : 0).toFixed(1) + 'px'); }
  set();
  addEventListener('resize', set);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(set);
})();

/* ------------------------------------------------ the month, as the app draws it --
   The three curves are revealed by a clip that grows with the scroll; a cursor rides
   the drawing edge with the date above it, like the app's chart. Check-ins, the fit
   and the best days switch on as the edge passes them; the weakest curve fades once
   the fit is shown. The still phone's screen follows (opacity only). */
(function () {
  'use strict';
  var act = document.querySelector('.how-act');
  if (!act) return;
  var wrap = act.querySelector('.cyc-wrap');
  var svg = act.querySelector('.cyc');
  var reveal = act.querySelector('.cyc__reveal');
  var cursor = act.querySelector('.cyc__cursor');
  var date = act.querySelector('.cyc__date');
  var marks = Array.prototype.slice.call(act.querySelectorAll('[data-at]'));
  var screens = Array.prototype.slice.call(act.querySelectorAll('.how-screen'));
  var steps = Array.prototype.slice.call(act.querySelectorAll('.how-step'));
  var WARP = JSON.parse(wrap.getAttribute('data-warp'));       // [[act progress, share drawn], ...]
  var START = new Date(wrap.getAttribute('data-start') + 'T12:00:00');
  var DAYS = +wrap.getAttribute('data-days');
  var WEIGHT = +wrap.getAttribute('data-weight');
  var fmt = new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  var W = 1000, last = -1;
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function drawn(p) {
    if (p <= WARP[0][0]) return WARP[0][1];
    for (var k = 1; k < WARP.length; k++) {
      if (p <= WARP[k][0]) { var a = WARP[k - 1], b = WARP[k]; return a[1] + (p - a[0]) / (b[0] - a[0]) * (b[1] - a[1]); }
    }
    return 1;
  }
  act.classList.add('is-live');
  function frame() {
    var p = parseFloat(act.style.getPropertyValue('--sc-p')) || 0;
    if (Math.abs(p - last) > 0.0004) {
      last = p;
      var f = clamp(drawn(p), 0, 1);
      reveal.setAttribute('width', (f * W + 10).toFixed(1));
      var x = (f * W).toFixed(1);
      cursor.setAttribute('x1', x); cursor.setAttribute('x2', x);
      cursor.style.opacity = f > 0.002 && f < 0.998 ? 1 : 0;
      var day = new Date(START.getTime() + Math.round(f * DAYS) * 86400000);
      var txt = fmt.format(day);
      if (date.textContent !== txt) date.textContent = txt;
      marks.forEach(function (m) {
        var until = m.getAttribute('data-until');
        m.classList.toggle('is-on', p >= +m.getAttribute('data-at') && (until === null || p < +until));
      });
      svg.classList.toggle('is-weighted', p >= WEIGHT);
      var top = 0;
      screens.forEach(function (s, i) {
        var o = i === 0 ? 1 : clamp((p - +s.getAttribute('data-from')) / 0.03, 0, 1);
        s.style.opacity = o.toFixed(3);
        if (o >= 0.5) top = i;
      });
      // only the screen on top is announced (the ones beneath stay at full opacity under it)
      screens.forEach(function (s, i) { s.setAttribute('aria-hidden', i === top ? 'false' : 'true'); });
      var on = +screens[top].getAttribute('data-step');
      steps.forEach(function (s, i) { s.classList.toggle('is-on', i === on); });
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
