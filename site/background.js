/* A paper-like line field. Animation runs only while a gesture is settling. */
(function () {
  'use strict';
  var hero = document.getElementById('hero');
  var canvas = document.getElementById('heroField');
  var ctx = canvas && canvas.getContext('2d');
  if (!ctx) return;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  var width = 0, height = 0, frame = 0, lastFrame = 0;
  var visible = true, pointerDown = false;
  var target = { x: 0, y: 0, strength: 0 };
  var pointer = { x: 0, y: 0, strength: 0 };
  var ripples = [];

  function canAnimate() { return visible && !document.hidden && !reduced.matches; }
  function pause() { cancelAnimationFrame(frame); frame = 0; }
  function wake() {
    if (!canAnimate()) { if (reduced.matches) draw(performance.now()); return; }
    if (!frame) frame = requestAnimationFrame(tick);
  }
  function resize() {
    var box = hero.getBoundingClientRect();
    width = box.width; height = box.height;
    var dpr = Math.min(window.devicePixelRatio || 1, 1.75);
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    target.x = pointer.x = width * .68;
    target.y = pointer.y = height * .55;
    draw(performance.now()); wake();
  }
  function draw(now) {
    ctx.clearRect(0, 0, width, height);
    var dark = document.documentElement.getAttribute('data-theme') === 'dark';
    var rows = width < 600 ? 30 : 46, columns = width < 600 ? 38 : 70;
    var radius = Math.min(width * .3, 220), radiusSquared = radius * radius;
    ripples = reduced.matches ? [] : ripples.filter(function (r) { return now - r.at < 1800; });
    for (var row = 0; row < rows; row++) {
      var band = row / (rows - 1);
      ctx.beginPath();
      for (var col = 0; col <= columns; col++) {
        var x = width * (col / columns * 1.16 - .08);
        var u = x / width;
        var y = height * (.50 + band * .65
          - .32 * Math.exp(-Math.pow((u - .80) / .40, 2))
          + .07 * Math.sin(u * 5 + band * 2.6));
        var dx = x - pointer.x, dy = y - pointer.y;
        var influence = Math.exp(-(dx * dx + dy * dy) / radiusSquared);
        y += pointer.strength * influence * (dy * .23 + Math.sin(u * 8 + band * 3) * 32);
        ripples.forEach(function (r) {
          var distance = Math.hypot(x - r.x, y - r.y);
          var age = (now - r.at) / 1000;
          var ring = Math.exp(-Math.pow((distance - age * 210) / 100, 2));
          y += Math.sin(distance * .035 - age * 8) * ring * 15 * Math.pow(1 - age / 1.8, 2);
        });
        if (!col) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      var accent = row === 12 || row === 27;
      ctx.strokeStyle = accent ? (dark ? '#b5a288' : '#a48d6b') : (dark ? '#a7ada4' : '#70766d');
      ctx.globalAlpha = accent ? .30 : row % 4 === 0 ? .23 : .11;
      ctx.lineWidth = accent ? 1 : .75;
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
  function tick(now) {
    frame = 0;
    if (!canAnimate()) return;
    if (now - lastFrame < 30) { frame = requestAnimationFrame(tick); return; }
    lastFrame = now;
    pointer.x += (target.x - pointer.x) * .14;
    pointer.y += (target.y - pointer.y) * .14;
    pointer.strength += (target.strength - pointer.strength) * .14;
    draw(now);
    if (Math.abs(target.x - pointer.x) > .1 || Math.abs(target.y - pointer.y) > .1
      || Math.abs(target.strength - pointer.strength) > .002 || ripples.length) wake();
  }
  function move(event) {
    if (reduced.matches || (event.pointerType === 'touch' && !pointerDown)) return;
    var box = hero.getBoundingClientRect();
    target.x = event.clientX - box.left;
    target.y = event.clientY - box.top;
    target.strength = 1;
    wake();
  }
  hero.addEventListener('pointermove', move, { passive: true });
  hero.addEventListener('pointerleave', function () { target.strength = 0; wake(); });
  hero.addEventListener('pointerdown', function (event) {
    if (event.button !== 0 || event.target.closest('button, a, #heroBot')) return;
    pointerDown = true;
    if (reduced.matches) return;
    move(event);
    if (ripples.length >= 4) ripples.shift();
    ripples.push({ x: target.x, y: target.y, at: performance.now() });
    wake();
  }, { passive: true });
  function end(event) {
    pointerDown = false;
    if (event.pointerType === 'touch') { target.strength = 0; wake(); }
  }
  window.addEventListener('pointerup', end, { passive: true });
  window.addEventListener('pointercancel', end, { passive: true });
  document.addEventListener('visibilitychange', function () { if (document.hidden) pause(); else wake(); });
  new MutationObserver(function () { draw(performance.now()); wake(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  if ('ResizeObserver' in window) new ResizeObserver(resize).observe(hero);
  else window.addEventListener('resize', resize, { passive: true });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) { visible = entries[0].isIntersecting; if (visible) wake(); else pause(); }).observe(hero);
  }
  function motionChanged() {
    pause(); target.strength = pointer.strength = 0; ripples = [];
    draw(performance.now()); wake();
  }
  if (reduced.addEventListener) reduced.addEventListener('change', motionChanged);
  else reduced.addListener(motionChanged);
  resize();
})();
