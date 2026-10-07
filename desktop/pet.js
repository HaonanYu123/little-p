(function () {
  'use strict';
  var state = { character: 'pink-robot', emotion: '02', sketch: false, lang: 'zh', theme: 'light' };
  var bridge = null, engine = null, hintTimer = 0, down = null, dragged = false;
  var pet = document.getElementById('pet'), hint = document.getElementById('hint');
  function say(text) { clearTimeout(hintTimer); hint.textContent = text; hint.classList.add('show'); hintTimer = setTimeout(function () { hint.classList.remove('show'); }, 2800); }
  function changed() { if (bridge) bridge.changed(JSON.stringify(state)); }
  function apply(next) {
    var oldCharacter = state.character;
    Object.assign(state, next);
    if (!engine || oldCharacter !== state.character) {
      if (engine) engine.destroy();
      engine = MoodMates.create(pet, { character: state.character, emotion: state.emotion, idle: { standbyAfter: 60000, sleepAfter: 180000 } });
      engine.on('change', function (event) { state.emotion = event.id; changed(); });
      engine.on('tips', function (event) { say(event.text); });
      engine.on('error', function (event) { say(event.message); });
      window.PET_ENGINE = engine;
    } else if (engine.emotionId !== state.emotion) engine.setEmotion(state.emotion);
    engine.setStyle({ sketch: state.sketch ? 1 : 0 });
    document.documentElement.lang = state.lang === 'en' ? 'en' : 'zh-CN';
    document.documentElement.setAttribute('data-theme', state.theme);
    document.body.classList.toggle('dark', state.theme === 'dark');
    document.getElementById('dismiss').title = state.lang === 'en' ? 'Dismiss Little P' : '收起小 P';
    engine.resetIdle();
  }
  window.applyPetState = apply;
  window.petNext = function (delta) { var ids = MoodMates.config.list().map(function (d) { return d.id; }); engine.setEmotion(ids[(ids.indexOf(engine.emotionId) + delta + ids.length) % ids.length]); };
  window.connectDesktopBridge = function () {
    new QWebChannel(qt.webChannelTransport, function (channel) {
      bridge = channel.objects.desktop;
      bridge.initialState(function (json) {
        apply(JSON.parse(json));
        bridge.catalogReady(JSON.stringify(MoodMates.config.list().map(function (d) {
          return { id: d.id, name: d.name, en: d.en && d.en.name || d.name, group: d.group, eye: d.pool && d.pool[0] || 'calm' };
        })));
        bridge.stateChanged.connect(function (json) { apply(JSON.parse(json)); });
        bridge.ready();
        say(state.lang === 'en' ? 'Scroll to switch · Right-click for expressions' : '滚轮切换 · 右键选表情');
      });
    });
  };
  pet.addEventListener('pointerdown', function (event) {
    if (event.button !== 0) return;
    down = { x: event.screenX, y: event.screenY }; dragged = false;
    pet.setPointerCapture(event.pointerId); engine.resetIdle();
    if (bridge) bridge.dragStart();
  });
  pet.addEventListener('pointermove', function (event) {
    if (down) {
      if (Math.abs(event.screenX - down.x) + Math.abs(event.screenY - down.y) > 5) { dragged = true; pet.classList.add('dragging'); }
      if (dragged && bridge) bridge.dragMove();
    } else {
      var r = pet.getBoundingClientRect();
      engine.setGaze((event.clientX - r.left - r.width / 2) / (r.width * .6), (event.clientY - r.top - r.height / 2) / (r.height * .6));
    }
  });
  function end(event) {
    if (!down) return;
    if (bridge) bridge.dragEnd();
    if (!dragged && event.type === 'pointerup') { if (engine.celebrate) engine.celebrate(1); else engine.signature(1); }
    down = null; pet.classList.remove('dragging');
  }
  pet.addEventListener('pointerup', end); pet.addEventListener('pointercancel', end);
  pet.addEventListener('contextmenu', function (event) { event.preventDefault(); if (bridge) bridge.showMenu(); });
  pet.addEventListener('wheel', function (event) { event.preventDefault(); window.petNext(event.deltaY > 0 ? 1 : -1); }, { passive: false });
  document.getElementById('dismiss').addEventListener('click', function () { if (bridge) bridge.dismiss(); });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && bridge) bridge.dismiss();
    if (event.key === 'ArrowLeft') window.petNext(-1);
    if (event.key === 'ArrowRight') window.petNext(1);
  });
  apply(state);
})();
