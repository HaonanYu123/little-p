/* Little P: a complete expression grid, click-to-preview and desktop sync. */
(function () {
  'use strict';

  var MM = window.MoodMates;
  var I = window.MM_I18N;
  var $ = function (id) { return document.getElementById(id); };

  /* ---------------- 小 P 角色适配 ---------------- */
  function allChars() { return MM.characters.list(); }
  function getChar(id) { return MM.characters.get(id); }
  function cfg() { return MM.config; }
  function rawDef(id) {
    var c = cfg();
    return c.getRaw ? c.getRaw(id) : c.get(id);
  }
  function createInst(el, opts) {
    var o = Object.assign({}, opts);
    return MM.create(el, o);
  }

  /* ---------------- 偏好读写 ---------------- */
  var PREF_KEY = 'xiaop.studio.prefs.v1';
  var prefs = { lang: 'zh', theme: 'light', character: 'pink-robot', sketch: false, tourMs: 2500 };
  try {
    Object.assign(prefs, JSON.parse(localStorage.getItem(PREF_KEY) || '{}'));
  } catch (e) { /* 偏好损坏时用默认值 */ }
  delete prefs.mode; // Migrate the retired horizontal album preference.
  if (!getChar(prefs.character)) prefs.character = 'pink-robot';
  delete prefs.variants;
  function savePrefs() {
    try { localStorage.setItem(PREF_KEY, JSON.stringify(prefs)); } catch (e) { /* 隐私模式忽略 */ }
  }

  /* ---------------- DOM 引用 ---------------- */
  var elStage = $('stage');
  var elTips = $('tips');
  var elEmoName = $('emoName');
  var elPager = $('pager');
  var elThumbFlow = $('thumbFlow');
  var elCastRow = $('castRow');
  var elToast = $('toast');
  var elTourToggle = $('tourToggle');
  var elTourInterval = $('tourInterval');
  var elSketchToggle = $('sketchToggle');
  var elLangToggle = $('langToggle');
  var elThemeToggle = $('themeToggle');
  var distribution = window.LITTLE_P_DISTRIBUTION || {};
  var elDownloadPet = $('downloadPet');
  if (distribution.downloadUrl) {
    elDownloadPet.href = distribution.downloadUrl;
    elDownloadPet.hidden = false;
  }

  /* ---------------- 站点状态 ---------------- */
  var selectedId = '02';
  var thumbs = [];            /* [{ id, def, engine, cell, nameSpan }] */
  var cellById = new Map();
  var castCards = [];         /* [{ id, btn, nameEl, ch }] */
  var main = null;
  var hero = null;
  var heroVisible = true;
  var tipsTimer = 0;
  var toastTimer = 0;
  var desktopActive = false;
  var desktopSyncTimer = 0;
  // Only the page served by the installed desktop service can use its HTTP API.
  // Static localhost previews behave like the public site and open littlep://.
  var desktopServicePage = location.protocol === 'http:' &&
    (location.hostname === '127.0.0.1' || location.hostname === 'localhost') &&
    location.port === '8086';
  var desktopApiBase = '';

  async function callDesktop(path, state) {
    var response;
    try {
      response = await fetch(desktopApiBase + path, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(state)
      });
    } catch (error) { throw new Error(I.t('summonStartServer')); }
    if (response.status === 404 || response.status === 405 || response.status === 501) {
      throw new Error(I.t('summonStartServer'));
    }
    var text, result;
    try {
      text = await response.text();
      result = JSON.parse(text);
    } catch (error) { throw new Error(I.t('summonInvalidResponse')); }
    if (!result || typeof result !== 'object') throw new Error(I.t('summonInvalidResponse'));
    if (!response.ok || !result.ok) throw new Error(result.message || I.t('summonFailed'));
    return result;
  }

  function desktopState() {
    return { character: prefs.character, emotion: selectedId, sketch: !!prefs.sketch, lang: prefs.lang, theme: prefs.theme };
  }
  function syncDesktop() {
    if (!desktopActive) return;
    clearTimeout(desktopSyncTimer);
    desktopSyncTimer = setTimeout(function () {
      callDesktop('/api/pet/state', desktopState())
        .then(function (r) { desktopActive = !!r.active; })
        .catch(function () { desktopActive = false; });
    }, 120);
  }
  $('summonPet').addEventListener('click', async function () {
    var btn = $('summonPet');
    if (!desktopServicePage) {
      var protocol = distribution.protocol || 'littlep';
      var state = desktopState();
      var query = new URLSearchParams({
        character: state.character, emotion: state.emotion,
        sketch: String(state.sketch), lang: state.lang, theme: state.theme
      });
      window.location.href = protocol + '://summon?' + query.toString();
      toast(I.t('summonOpeningApp'));
      return;
    }
    btn.disabled = true;
    btn.querySelector('[data-i18n]').textContent = I.t('summonBusy');
    try {
      await callDesktop('/api/pet/summon', desktopState());
      desktopActive = true;
      toast(I.t('summonSuccess'), 'ok');
    } catch (error) { toast(error.message || I.t('summonFailed'), 'danger'); }
    finally { btn.disabled = false; btn.querySelector('[data-i18n]').textContent = I.t('summonLabel'); }
  });

  /* ---------------- 文案工具 ---------------- */
  function dispName(def) {
    return I.lang === 'en' && def.en && def.en.name ? def.en.name : def.name;
  }
  function charName(ch) {
    return I.lang === 'en' && ch.en && ch.en.name ? ch.en.name : ch.name;
  }

  /* ---------------- Toast ---------------- */
  function toast(text, kind) {
    clearTimeout(toastTimer);
    elToast.textContent = text;
    elToast.className = 'toast show' + (kind ? ' ' + kind : '');
    toastTimer = setTimeout(function () { elToast.className = 'toast'; }, 3600);
  }

  /* ---------------- tips 气泡 ---------------- */
  function showTips(text) {
    clearTimeout(tipsTimer);
    elTips.textContent = text;
    elTips.classList.add('show');
    tipsTimer = setTimeout(function () { elTips.classList.remove('show'); }, 3200);
  }

  /* ---------------- 鼠标注视:window 级 pointermove,矩形缓存 200ms ---------------- */
  var gazeTargets = [];
  function watchGaze(engine, el) {
    gazeTargets.push({ engine: engine, el: el, rect: null, rectAt: 0 });
  }
  function unwatchGaze(el) {
    gazeTargets = gazeTargets.filter(function (t) { return t.el !== el; });
  }
  function refreshGazeRects() {
    gazeTargets.forEach(function (t) { t.rect = null; });
  }
  function clamp06(v) { return v < -0.6 ? -0.6 : (v > 0.6 ? 0.6 : v); }
  window.addEventListener('pointermove', function (e) {
    var now = performance.now();
    for (var i = 0; i < gazeTargets.length; i++) {
      var t = gazeTargets[i];
      if (!t.rect || now - t.rectAt > 200) {
        t.rect = t.el.getBoundingClientRect();
        t.rectAt = now;
      }
      var r = t.rect;
      if (!r.width || !r.height) continue;
      t.engine.setGaze(
        clamp06((e.clientX - (r.left + r.width / 2)) / r.width) / 0.6,
        clamp06((e.clientY - (r.top + r.height / 2)) / r.height) / 0.6
      );
    }
  }, { passive: true });
  document.addEventListener('pointerleave', function () {
    gazeTargets.forEach(function (t) { t.engine.clearGaze(); });
  });
  window.addEventListener('resize', refreshGazeRects, { passive: true });
  window.addEventListener('scroll', refreshGazeRects, { passive: true });

  /* ---------------- 主角色(切换角色时重建实例) ---------------- */
  function createMain(charId) {
    var emotion = main ? main.emotionId : selectedId;
    if (main) {
      main.destroy();
      unwatchGaze(elStage);
    }
    main = createInst(elStage, {
      character: charId,
      emotion: emotion,
      idle: { standbyAfter: 60000, sleepAfter: 180000 },
      label: I.t('stageLabel')
    });
    main.setStyle({ sketch: elSketchToggle.checked ? 1 : 0 });
    main.on('change', function (e) {
      selectedId = e.id;
      updateMeta(e.def);
      highlightSelected();
      syncDesktop();
    });
    main.on('tips', function (e) { showTips(e.text); });
    main.on('error', function (e) { toast(e.message, 'danger'); });
    watchGaze(main, elStage);
    window.EG_MAIN = main;   /* 控制台调试句柄 */
  }

  /* ---------------- 角色切换 ---------------- */
  function switchCharacter(charId) {
    if (!getChar(charId)) return;
    prefs.character = charId;
    savePrefs();
    if (main && main.touring) stopTourUI();
    createMain(charId);
    buildThumbs();
    updateMeta();
    highlightCast();
    buildBrand();
    buildHero();
    syncDesktop();
  }

  function highlightCast() {
    castCards.forEach(function (c) {
      c.btn.classList.toggle('selected', c.id === prefs.character);
      c.btn.setAttribute('aria-pressed', String(c.id === prefs.character));
    });
  }

  function buildCast() {
    elCastRow.innerHTML = '';
    castCards = [];
    allChars().forEach(function (ch) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cast';
      btn.dataset.character = ch.id;

      var avatar = document.createElement('div');
      avatar.className = 'cast-avatar';
      btn.appendChild(avatar);

      var nameEl = document.createElement('span');
      nameEl.className = 'cast-name';
      btn.appendChild(nameEl);

      elCastRow.appendChild(btn);

      var engine = createInst(avatar, {
        character: ch.id,
        emotion: '02',
        lite: true,
        eyeScale: 1.35,
        label: ch.name
      });
      watchGaze(engine, avatar);

      btn.addEventListener('click', function () {
        if (!engine.signature || !engine.signature(0.7)) engine.spin(1);
        if (prefs.character !== ch.id) switchCharacter(ch.id);
      });

      castCards.push({ id: ch.id, btn: btn, nameEl: nameEl, ch: ch });
    });
    relabelCast();
    highlightCast();
  }

  function relabelCast() {
    castCards.forEach(function (c) {
      c.nameEl.textContent = charName(c.ch);
      c.btn.title = charName(c.ch);
    });
  }

  /* ---------------- 元信息 + 页码 ---------------- */
  function currentDefs() {
    return cfg().list();
  }
  function selectedIndex() {
    var defs = currentDefs();
    for (var i = 0; i < defs.length; i++) if (defs[i].id === selectedId) return i;
    return -1;
  }
  function updateMeta(def) {
    if (!def) def = rawDef(selectedId);
    if (!def) return;
    elEmoName.textContent = dispName(def);
    var defs = currentDefs();
    var idx = selectedIndex();
    elPager.textContent = (idx >= 0 ? String(idx + 1).padStart(2, '0') : '--') +
      ' / ' + String(defs.length).padStart(2, '0');
  }

  function highlightSelected() {
    cellById.forEach(function (cell, id) {
      cell.classList.toggle('selected', id === selectedId);
      cell.setAttribute('aria-pressed', String(id === selectedId));
    });
  }

  /* ---------------- 陈列墙大图弹窗 ---------------- */
  var stageReturnFocus = null;
  function stageOpen() { return document.body.classList.contains('stage-open'); }
  function openStage() {
    if (stageOpen()) return;
    stageReturnFocus = document.activeElement;
    document.body.classList.add('stage-open');
    document.querySelector('.workspace').inert = true;
    $('stageClose').focus({ preventScroll: true });
    refreshGazeRects();
  }
  function closeStage() {
    if (!stageOpen()) return;
    document.body.classList.remove('stage-open');
    document.querySelector('.workspace').inert = false;
    if (main.touring) stopTourUI();
    if (stageReturnFocus && stageReturnFocus.isConnected) stageReturnFocus.focus({ preventScroll: true });
    refreshGazeRects();
  }
  $('stageClose').addEventListener('click', closeStage);
  document.querySelector('.stage-zone').addEventListener('click', function (e) {
    if (e.target === e.currentTarget) closeStage();
  });

  /* ---------------- 左右翻页 ---------------- */
  function step(delta) {
    var defs = currentDefs();
    if (!defs.length) return;
    if (main.touring) stopTourUI();
    var idx = selectedIndex();
    var next = idx < 0
      ? (delta > 0 ? 0 : defs.length - 1)
      : (idx + delta + defs.length) % defs.length;
    main.setEmotion(defs[next].id);
    openStage();
  }
  $('navPrev').addEventListener('click', function () { step(-1); });
  $('navNext').addEventListener('click', function () { step(1); });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Tab' && stageOpen()) {
      var controls = Array.from(document.querySelectorAll('.stage-zone button'));
      var index = controls.indexOf(document.activeElement);
      controls[(index + (e.shiftKey ? -1 : 1) + controls.length) % controls.length].focus();
      e.preventDefault();
      return;
    }
    var tag = e.target && e.target.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
    if (e.key === 'ArrowLeft') { step(-1); e.preventDefault(); }
    else if (e.key === 'ArrowRight') { step(1); e.preventDefault(); }
    else if (e.key === 'Escape') {
      closeStage();
    }
  });

  /* ---------------- 缩略图流(当前角色的表情墙) ---------------- */
  function buildThumbs() {
    thumbs.forEach(function (t) { t.engine.destroy(); });
    thumbs = [];
    cellById.clear();
    elThumbFlow.innerHTML = '';

    currentDefs().forEach(function (def) {
      var cell = document.createElement('button');
      cell.type = 'button';
      cell.className = 'cell';
      cell.dataset.emotion = def.id;
      cell.title = dispName(def);
      cell.setAttribute('aria-label', dispName(def));

      var thumbEl = document.createElement('div');
      thumbEl.className = 'thumb';
      cell.appendChild(thumbEl);

      var label = document.createElement('div');
      label.className = 'cell-label';
      var nameSpan = document.createElement('span');
      nameSpan.textContent = dispName(def);
      label.appendChild(nameSpan);
      cell.appendChild(label);

      /* 缩略角色:非激活(零帧成本),hover 时才注册进共享时钟播放动画 */
      var engine = createInst(thumbEl, {
        character: prefs.character,
        emotion: def.id,
        autostart: false,
        label: dispName(def) + ' ' + I.t('thumbSuffix')
      });
      if (prefs.sketch) engine.setStyle({ sketch: 1 });

      cell.addEventListener('mouseenter', function () {
        engine.setActive(true);
        engine.replay();
      });
      cell.addEventListener('mouseleave', function () {
        engine.setActive(false);
        engine.setEmotion(def.id, { auto: true });
      });
      cell.addEventListener('click', function () {
        if (main.touring) stopTourUI();
        main.setEmotion(def.id);
        openStage();
      });
      elThumbFlow.appendChild(cell);
      thumbs.push({ id: def.id, def: def, engine: engine, cell: cell, nameSpan: nameSpan });
      cellById.set(def.id, cell);
    });

    highlightSelected();
  }

  function relabelThumbs() {
    thumbs.forEach(function (t) {
      t.nameSpan.textContent = dispName(t.def);
      t.cell.title = dispName(t.def);
      t.cell.setAttribute('aria-label', dispName(t.def));
    });
  }

  /* ---------------- 主题 ---------------- */
  function setTheme(theme) {
    prefs.theme = theme === 'light' ? 'light' : 'dark';
    savePrefs();
    document.documentElement.setAttribute('data-theme', prefs.theme);
    syncDesktop();
    elThemeToggle.title = prefs.theme === 'dark' ? I.t('themeToLight') : I.t('themeToDark');
    elThemeToggle.setAttribute('aria-label', elThemeToggle.title);
  }
  elThemeToggle.addEventListener('click', function () {
    setTheme(prefs.theme === 'dark' ? 'light' : 'dark');
  });

  function applyI18n() {
    I.set(prefs.lang);
    document.documentElement.lang = prefs.lang === 'en' ? 'en' : 'zh-CN';
    document.title = I.t('docTitle');
    var nodes = document.querySelectorAll('[data-i18n]');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].textContent = I.t(nodes[i].getAttribute('data-i18n'));
    }
    elLangToggle.textContent = I.t('langBtn');
    $('navPrev').title = I.t('prevEmotion');
    $('navNext').title = I.t('nextEmotion');
    $('stageClose').title = I.t('stageClose');
    $('stageClose').setAttribute('aria-label', I.t('stageClose'));
    $('navPrev').setAttribute('aria-label', I.t('prevEmotion'));
    $('navNext').setAttribute('aria-label', I.t('nextEmotion'));
    elLangToggle.setAttribute('aria-label', prefs.lang === 'en' ? 'Switch language' : '切换语言');
    elTourInterval.setAttribute('aria-label', I.t('lblInterval'));
    elCastRow.setAttribute('aria-label', I.t('characterTitle'));
    $('heroBot').setAttribute('aria-label', charName(getChar(prefs.character)) + ' · ' + I.t('stageInteract'));
    $('thumbFlow').setAttribute('aria-label', I.t('expressionTitle') + ' · 32');
    elThemeToggle.title = prefs.theme === 'dark' ? I.t('themeToLight') : I.t('themeToDark');
    elThemeToggle.setAttribute('aria-label', elThemeToggle.title);
    relabelThumbs();
    relabelCast();
    updateMeta();
    syncDesktop();
  }
  elLangToggle.addEventListener('click', function () {
    prefs.lang = prefs.lang === 'zh' ? 'en' : 'zh';
    savePrefs();
    applyI18n();
    refreshGazeRects();
  });

  /* ---------------- 自动巡演 ---------------- */
  function restartTour() {
    var ids = currentDefs().map(function (d) { return d.id; });
    main.startTour(ids, prefs.tourMs);
  }
  function stopTourUI() {
    main.stopTour();
    elTourToggle.checked = false;
  }
  elTourToggle.addEventListener('change', function () {
    if (elTourToggle.checked) {
      restartTour();
      openStage();
    } else {
      main.stopTour();
    }
  });
  elTourInterval.addEventListener('change', function () {
    prefs.tourMs = parseInt(elTourInterval.value, 10) || 2500;
    savePrefs();
    if (main.touring) restartTour();
  });

  /* ---------------- 线稿 ---------------- */
  /* 线稿同时作用于主舞台与全部预览缩略图 */
  function applySketch() {
    var v = prefs.sketch ? 1 : 0;
    main.setStyle({ sketch: v });
    thumbs.forEach(function (t) { t.engine.setStyle({ sketch: v }); });
    syncDesktop();
  }
  elSketchToggle.addEventListener('change', function () {
    prefs.sketch = elSketchToggle.checked;
    savePrefs();
    applySketch();
  });

  /* ---------------- 品牌 LOGO 角色:顶栏迷你实例(随当前角色) ---------------- */
  var brand = null;
  function buildBrand() {
    var elBrand = $('brandBall');
    if (brand) {
      brand.destroy();
      unwatchGaze(elBrand);
    }
    brand = createInst(elBrand, {
      character: prefs.character,
      emotion: '02',
      lite: true,
      eyeScale: 1.7,
      label: 'Emotion Gallery'
    });
    watchGaze(brand, elBrand);
  }
  $('brandBall').addEventListener('click', function () {
    if (!brand) return;
    if (!brand.signature || !brand.signature(0.6)) brand.spin(1);
  });

  /* ---------------- Hero character and original background ---------------- */
  function buildHero() {
    var elHero = $('heroBot');
    if (hero) {
      hero.destroy();
      unwatchGaze(elHero);
    }
    hero = createInst(elHero, { character: prefs.character, emotion: '02', label: charName(getChar(prefs.character)) });
    hero.setStyle({ sketch: 0 });
    hero.setActive(heroVisible);
    watchGaze(hero, elHero);
  }
  $('heroBot').addEventListener('click', function () {
    if (!hero) return;
    if (!hero.signature || !hero.signature(0.8)) hero.spin(1);
  });
  $('heroCta').addEventListener('click', function () {
    $('gallery').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' });
  });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      heroVisible = entries[0].isIntersecting;
      if (hero) hero.setActive(heroVisible);
    }, { threshold: 0.05 }).observe($('hero'));
  }

  /* ---------------- 舞台交互 ---------------- */
  elStage.addEventListener('click', function () {
    if (main.celebrate) main.celebrate(1);
    else if (!main.signature || !main.signature(1)) main.spin(1);
  });

  /* 任何用户交互都重置待机计时 */
  ['pointerdown', 'keydown'].forEach(function (evt) {
    document.addEventListener(evt, function () { main.resetIdle(); }, { passive: true });
  });

  /* ---------------- 初始化 ---------------- */
  I.set(prefs.lang);
  setTheme(prefs.theme);
  elSketchToggle.checked = !!prefs.sketch;
  elTourInterval.value = String(prefs.tourMs);
  if (!elTourInterval.value) { elTourInterval.value = '2500'; prefs.tourMs = 2500; }

  createMain(prefs.character);
  buildCast();
  buildBrand();
  buildHero();
  applyI18n();
  buildThumbs();
  updateMeta();
  highlightSelected();
})();
