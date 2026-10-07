/* 小 P：经典 / 粉色头部外壳 + 实时 SVG 眼睛 + 状态专属特效。
 * 复用 MoodMates 的眼形、32 状态、自动播放和共享时钟，无新增 rAF。 */
(function () {
  'use strict';
  var MM = window.MoodMates;
  var textureUrl = new URL('../assets/robot/robot-shell.png', document.currentScript.src).href;
  var pinkTextureUrl = new URL('../assets/robot/pink-head-soft-oval.png', document.currentScript.src).href;
  var serial = 0, NS = 'http://www.w3.org/2000/svg';
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  // ID -> 特效皮肤与灯色；实体外壳始终保持参考图的白色材质。
  var states = {
    '00': ['sleep', '#83bad0'], '01': ['boot', '#9eefff'], '02': ['idle', '#aeffff'],
    '03': ['radar', '#8feaff'], '04': ['idle', '#a4d4e8'], '05': ['boot', '#87efff'],
    '06': ['sleep', '#7aa4bd'], '07': ['boot', '#8feaff'],
    '10': ['joy', '#94ffe4'], '11': ['question', '#c5b4ff'], '12': ['sad', '#87acff'],
    '13': ['surprise', '#d4fbff'], '14': ['shy', '#ffb6df'], '15': ['sleep', '#91abc5'],
    '16': ['scan', '#8befff'], '17': ['alert', '#ffbd82'], '18': ['idle', '#b3bedc'],
    '19': ['joy', '#96ffe1'], '20': ['question', '#c7b0ff'], '21': ['alert', '#ff7b82'],
    '30': ['radar', '#87edff'], '31': ['receive', '#8effe4'], '32': ['busy', '#82dcff'],
    '33': ['done', '#83ffcc'], '34': ['error', '#ff788b'], '35': ['listen', '#92f5ff'],
    '36': ['network', '#86dfff'], '37': ['radar', '#b5c4ff'], '38': ['refuse', '#ffb790'],
    '39': ['speak', '#8dffe9'], '40': ['scan', '#80e8ff'], '41': ['off', '#78909c']
  };
  var descriptions = {
    sleep: ['低功耗耳灯、细线睡眼与缓慢呼吸；睡眠时有 Z 字漂浮', 'Low-power ear lights, sleepy eyes and a slow breath'],
    boot: ['面屏扫描线逐行点亮，双眼交错睁开，像系统正在启动', 'A boot scan lights the screen while eyes wake in alternation'],
    idle: ['耳灯轻轻呼吸，发光双眼随状态改变，并追随鼠标注视', 'Breathing ear lights and expressive glowing eyes that follow the pointer'],
    radar: ['头顶全息雷达旋转，三个运算光点依次点亮', 'A rotating holographic radar with three computation lights'],
    joy: ['发光笑眼轻轻跳动，薄荷色能量星点在周围闪耀', 'Bouncing smile eyes and mint energy sparkles'],
    question: ['双眼一大一小，头顶悬浮问号，紫色耳灯慢闪', 'Uneven eyes, a floating question mark and violet ear lights'],
    sad: ['蓝色灯光减弱，视线低垂，一滴像素泪缓缓落下', 'Dim blue lights, a lowered gaze and a falling pixel tear'],
    surprise: ['双眼瞬间放大，外壳泛起柔光，极光带从身后掠过', 'Wide eyes, luminous shell edges and an aurora sweep'],
    shy: ['粉色耳灯与像素腮红，目光轻轻躲向一侧', 'Pink ear lights, pixel blush and a shy sideways gaze'],
    scan: ['细扫描线连续扫过面屏，双眼保持专注', 'A continuous screen scan with focused eyes'],
    alert: ['警示耳灯快速闪烁，三角警示标记与头部轻颤同步', 'Flashing warning ears and a warning triangle with a nervous shiver'],
    receive: ['全息光带向外壳汇聚，耳灯亮起，双眼轻轻点头', 'Holographic ribbons gather at the shell with an acknowledging nod'],
    busy: ['运算光点循环跳动，面屏扫描线持续运行', 'Cycling computation lights and an active screen scan'],
    done: ['绿色完成勾亮起，极光带掠过外壳，发光星尘缓缓散开', 'A green completion check, aurora ribbons and drifting luminous stardust'],
    error: ['红色耳灯闪烁，面屏短暂故障偏移，浮现错误叉号', 'Red warning pulses, a brief screen glitch and an error cross'],
    listen: ['耳灯像监听信号一样脉冲，面屏显示细音频波形', 'Listening ear pulses with a soft audio waveform'],
    network: ['连接光点沿头顶弧线跳动，扫描线同步加载', 'Connection dots travel along an arc with a loading scan'],
    refuse: ['摇头拒绝，琥珀色限制标记与耳灯同步亮起', 'A firm head shake and an amber restriction glyph'],
    speak: ['面屏音频波形随回复律动，青色耳灯同步脉冲', 'A rhythmic reply waveform with matching cyan ear pulses'],
    off: ['耳灯渐暗，眼睛缩成静止细线，关闭动态特效', 'Ear lights dim, eyes close to still lines and effects power down']
  };
  window.RobotFace = {
    describe: function (id, lang) {
      var s = states[id]; return s ? descriptions[s[0]][lang === 'en' ? 1 : 0] : '';
    }
  };
  var overrides = {};
  Object.keys(states).forEach(function (id) {
    overrides[id] = { eyes: { both: { color: states[id][1] } } };
  });
  var robotDef = {
    id: 'robot', name: '经典小 P', en: { name: 'Classic P' }, industry: 'classic',
    body: { type: 'puff', r: 0.91 }, face: { x: 0, y: 0, sx: 1, sy: 1, eye: 1 },
    eyeStyle: { dx: 34, cy: 133, w: 32, h: 57, taper: 0.5, bend: 0 },
    eyeShapes: {
      happy: { w: 34, h: 6, bend: 0.35, taper: 0.5 },
      happy2: { w: 35, h: 7, bend: 0.3, taper: 0.5 },
      closed: { w: 30, h: 4, bend: -0.1, taper: 0.5 },
      closed2: { w: 30, h: 4, bend: 0.1, taper: 0.5 }
    },
    palette: { body: '#edf4fa', eye: '#aeffff', gloss: 0, states: {} },
    // 通用五官层默认会生成椭圆腮红；机器人只使用面屏两侧的像素腮红。
    features: { blush: false }, emotions: overrides
  };
  MM.characters.register(robotDef);
  var pinkOverrides = {};
  Object.keys(states).forEach(function (id) {
    pinkOverrides[id] = { eyes: { both: { color: ['idle', 'joy', 'shy', 'receive', 'done'].indexOf(states[id][0]) >= 0 ? '#ff8dcc' : states[id][1] } } };
  });
  MM.characters.register(Object.assign({}, robotDef, {
    _resolved: null,
    id: 'pink-robot', name: '蝴蝶结小 P', en: { name: 'Ribbon P' }, industry: 'ribbon',
    eyeStyle: { dx: 31, cy: 116, w: 27, h: 46, taper: 0.5, bend: 0 },
    palette: { body: '#ffc4d5', eye: '#ff8dcc', gloss: 0, states: {} },
    emotions: pinkOverrides
  }));
  function node(tag, attrs) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (key) { n.setAttribute(key, attrs[key]); }); return n;
  }
  function show(n, on) { n.style.display = on ? '' : 'none'; }
  var createBase = MM.createBall;
  MM.createBall = function (container, opts) {
    if (opts.character.id !== 'robot' && opts.character.id !== 'pink-robot') return createBase(container, opts);
    var pink = opts.character.id === 'pink-robot';
    // 关闭通用云朵/星星特效，只复用原渲染器的眼睛和身体姿态。
    var ball = createBase(container, Object.assign({}, opts, { lite: true }));
    var svg = ball.svg, body = svg.querySelector('.mm-body'), defs = svg.querySelector('defs');
    var groundShadow = pink ? svg.querySelector('ellipse') : null;
    svg.classList.add('robot-svg');
    if (pink) { svg.classList.add('pink-robot-svg'); svg.setAttribute('viewBox', '-38 -78 316 302'); }
    var paths = Array.prototype.filter.call(body.children, function (n) { return n.localName === 'path'; });
    var head = paths[0], ao = paths[1], eyes = paths.slice(2, 4);
    var shellId = 'robot-shell-' + serial++;
    var shell = node('image', { id: shellId, href: pink ? pinkTextureUrl : textureUrl, x: pink ? -14 : 0, y: pink ? -70 : 0, width: pink ? 282.15 : 240, height: pink ? 282.15 : 240, class: 'robot-texture' });
    body.insertBefore(shell, head);
    var shellOutline = 'M27 104 C26 62 64 29 120 29 C176 29 214 62 213 104 L214 156 C211 191 178 218 120 218 C62 218 29 191 26 156 Z';
    var screenOutline = 'M43 126 C43 90 72 72 120 72 C168 72 197 90 197 126 L193 159 C187 183 163 198 120 198 C77 198 53 183 47 159 Z';
    // Match the oval glass in pink-head-soft-oval.png; this path also clips live effects.
    if (pink) screenOutline = 'M126 54 C168 54 201 79 201 116 C201 153 168 177 126 177 C84 177 52 153 52 116 C52 79 84 54 126 54 Z';
    head.setAttribute('d', shellOutline);
    var screen = node('path', { d: screenOutline, fill: '#09121d', stroke: '#61788e', 'stroke-width': 1.5 });
    if (pink) screen.setAttribute('class', 'pink-oval-screen');
    body.insertBefore(screen, ao);
    var pinkOutline = null;
    if (pink) {
      pinkOutline = node('g', { fill: 'none', 'stroke-width': 1.5, class: 'pink-sketch-outline' });
      [
        'M108 10C78-68 30-83 9-64C-11-44-19-5 4 18C35 41 69 34 108 10ZM125 10C157-62 208-80 230-57C251-26 246 3 231 23C207 45 155 30 125 10ZM106 4Q119-12 130 4L130 26Q119 34 106 24Z',
        'M125 24C181 24 226 64 226 115C226 163 186 198 125 198C65 198 25 163 25 115C25 64 69 24 125 24Z',
        'M34 98C18 91 10 108 10 130C10 151 18 167 35 166M216 99C231 93 244 109 244 135C244 157 233 169 216 168'
      ].forEach(function (d) { pinkOutline.appendChild(node('path', { d: d })); });
      body.insertBefore(pinkOutline, shell);
    }
    var clipId = 'robot-screen-' + serial++, clip = node('clipPath', { id: clipId });
    clip.appendChild(node('path', { d: screenOutline })); defs.appendChild(clip);
    var glowId = 'robot-glow-' + serial++;
    var filter = node('filter', { id: glowId, x: '-100%', y: '-100%', width: '300%', height: '300%' });
    filter.appendChild(node('feGaussianBlur', { in: 'SourceGraphic', stdDeviation: 2.5, result: 'blur' }));
    var merge = node('feMerge');
    merge.appendChild(node('feMergeNode', { in: 'blur' }));
    merge.appendChild(node('feMergeNode', { in: 'SourceGraphic' })); filter.appendChild(merge); defs.appendChild(filter);
    var screenFx = node('g', { 'clip-path': 'url(#' + clipId + ')', 'pointer-events': 'none' }); body.appendChild(screenFx);
    var scan = node('rect', { x: 45, y: 90, width: 150, height: 2, opacity: 0.4 }); screenFx.appendChild(scan);
    var blush = node('path', { d: 'M58 157h12m-12 5h12m112-5h-12m12 5h-12', fill: 'none', 'stroke-width': 2.5, opacity: 0.65 }); screenFx.appendChild(blush);
    if (pink) { blush.setAttribute('d', 'M77 149l-4 6m11-6l-4 6m11-6l-4 6m63-6l-4 6m11-6l-4 6m11-6l-4 6'); blush.setAttribute('stroke-linecap', 'round'); }
    var tear = node('path', { d: 'M71 149l-4 7 4 5 4-5Z' }); screenFx.appendChild(tear);
    var wave = node('path', { fill: 'none', 'stroke-width': 2, 'stroke-linecap': 'round' }); screenFx.appendChild(wave);
    var glyph = node('path', { transform: pink ? 'translate(0 -10)' : '', fill: 'none', 'stroke-width': 2.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }); screenFx.appendChild(glyph);
    var ears = node('g', { fill: 'none', 'stroke-width': 2.4, filter: 'url(#' + glowId + ')' });
    ears.appendChild(node('path', { d: pink ? 'M25 108 Q18 137 25 161' : 'M26 109 Q17 143 26 177' }));
    ears.appendChild(node('path', { d: pink ? 'M232 108 Q239 137 232 161' : 'M214 109 Q223 143 214 177' })); body.appendChild(ears);
    var radar = node('g', { fill: 'none', 'stroke-width': 1.2 });
    radar.appendChild(node('ellipse', { cx: 120, cy: 21, rx: 42, ry: 11, opacity: 0.3 }));
    var sweep = node('path', { d: 'M120 21L159 17', opacity: 0.85 }); radar.appendChild(sweep);
    var radarDot = node('circle', { r: 2.5 }); radar.appendChild(radarDot); body.appendChild(radar);
    var dots = node('g'), dotNodes = [];
    for (var i = 0; i < 3; i++) { var d = node('circle', { cx: 110 + 10 * i, cy: pink ? 170 : 180, r: 2 }); dots.appendChild(d); dotNodes.push(d); }
    screenFx.appendChild(dots);
    var question = node('text', { x: 181, y: 40, 'font-size': 25, 'font-weight': 700, 'font-family': 'sans-serif' }); question.textContent = '?'; body.appendChild(question);
    var zzz = node('text', { x: 182, y: 42, 'font-size': 17, 'font-family': 'sans-serif', 'font-weight': 700 }); zzz.textContent = 'z Z'; body.appendChild(zzz);
    // 点击签名：后景极光、贴着真实外壳的边缘光、带拖尾的星尘。
    // 光带保持开放曲线，放在外壳后方，不穿过眼睛和黑色面屏。
    var aurora = node('g', { class: 'robot-aurora', 'pointer-events': 'none' });
    svg.insertBefore(aurora, body);
    var mistId = 'robot-mist-' + serial++;
    var mistGradient = node('radialGradient', { id: mistId });
    mistGradient.appendChild(node('stop', { offset: '0', 'stop-color': '#8cefff', 'stop-opacity': 0.42 }));
    mistGradient.appendChild(node('stop', { offset: '0.52', 'stop-color': '#8584ff', 'stop-opacity': 0.2 }));
    mistGradient.appendChild(node('stop', { offset: '1', 'stop-color': '#8584ff', 'stop-opacity': 0 })); defs.appendChild(mistGradient);
    var mist = node('circle', { cx: 112, cy: 126, r: 148, fill: 'url(#' + mistId + ')' }); aurora.appendChild(mist);
    var ribbons = [];
    for (var ri = 0; ri < (opts.lite ? 2 : 3); ri++) {
      var gradientId = 'robot-ribbon-' + serial++;
      var gradient = node('linearGradient', { id: gradientId, gradientUnits: 'userSpaceOnUse' });
      gradient.appendChild(node('stop', { offset: '0', 'stop-color': '#8b79ff', 'stop-opacity': 0 }));
      gradient.appendChild(node('stop', { offset: '0.38', 'stop-color': '#9d92ff', 'stop-opacity': 0.6 }));
      var colorStop = node('stop', { offset: '0.78', 'stop-color': '#8eefff' }); gradient.appendChild(colorStop);
      var endStop = node('stop', { offset: '1', 'stop-color': '#f4ffff' }); gradient.appendChild(endStop); defs.appendChild(gradient);
      var wrap = node('g'); aurora.appendChild(wrap);
      var haze = node('path', { fill: 'none', stroke: 'url(#' + gradientId + ')', 'stroke-width': 5.2, filter: 'url(#' + glowId + ')', opacity: 0.38 });
      var line = node('path', { fill: 'none', stroke: 'url(#' + gradientId + ')', 'stroke-width': ri === 0 ? 1.45 : 0.85, 'stroke-linecap': 'round' });
      var tip = node('circle', { r: ri === 0 ? 1.65 : 1.1, fill: '#edffff', filter: 'url(#' + glowId + ')' });
      wrap.appendChild(haze); wrap.appendChild(line); wrap.appendChild(tip);
      ribbons.push({ wrap: wrap, haze: haze, line: line, tip: tip, gradient: gradient, colorStop: colorStop, endStop: endStop });
    }
    var rimId = 'robot-rim-' + serial++;
    var rimFilter = node('filter', { id: rimId, x: '-15%', y: '-15%', width: '130%', height: '130%' });
    rimFilter.appendChild(node('feMorphology', { in: 'SourceAlpha', operator: 'dilate', radius: 1.1, result: 'expanded' }));
    rimFilter.appendChild(node('feComposite', { in: 'expanded', in2: 'SourceAlpha', operator: 'out', result: 'edge' }));
    rimFilter.appendChild(node('feGaussianBlur', { in: 'edge', stdDeviation: 0.85, result: 'softEdge' }));
    var rimColor = node('feFlood', { 'flood-color': '#abfaff', result: 'light' }); rimFilter.appendChild(rimColor);
    rimFilter.appendChild(node('feComposite', { in: 'light', in2: 'softEdge', operator: 'in' })); defs.appendChild(rimFilter);
    var rim = node('use', { href: '#' + shellId, filter: 'url(#' + rimId + ')', 'pointer-events': 'none' }); body.insertBefore(rim, shell);
    var sparks = node('g', { 'pointer-events': 'none' }); svg.appendChild(sparks);
    var particles = [], joyNodes = [];
    var status = '02', effectAt = -Infinity, strength = 1, loaded = false, failed = false, previousPose;
    shell.addEventListener('load', function () { loaded = true; if (previousPose) ball.applyPose(previousPose); });
    shell.addEventListener('error', function () { failed = true; if (previousPose) ball.applyPose(previousPose); });
    ball.setEmotion = function (id) {
      status = states[id] ? id : '02'; svg.setAttribute('data-emotion', status);
      effectAt = -Infinity;
      particles.forEach(function (p) { p.node.remove(); }); particles = [];
      if (status === '13' || status === '31') effectAt = performance.now();
    };
    function burst(count) {
      if (opts.lite || reduced.matches) return;
      var color = states[status][1], now = performance.now(), amount = Math.min(count || 18, 36 - particles.length);
      var onLight = document.documentElement.getAttribute('data-theme') === 'light';
      for (var p = 0; p < amount; p++) {
        var angle = Math.PI * 2 * p / amount + Math.random() * 0.25;
        var n = node('g', { class: 'robot-stardust', filter: 'url(#' + glowId + ')' });
        var tail = node('path', { d: 'M0 0L-5 0', fill: 'none', stroke: onLight ? MM.util.shade(color, -0.38) : color, 'stroke-width': 0.75, opacity: 0.45 });
        n.appendChild(tail);
        n.appendChild(node('circle', { r: 0.6 + Math.random() * 0.65, fill: onLight ? '#7785bc' : p % 3 === 0 ? '#eee9ff' : '#dcffff' }));
        if (p % 5 === 0) n.appendChild(node('path', { d: 'M-2.5 0H2.5M0-2.5V2.5', stroke: onLight ? '#7785bc' : '#efffff', 'stroke-width': 0.45, fill: 'none' }));
        sparks.appendChild(n);
        particles.push({ node: n, tail: tail, angle: angle, at: now, speed: 12 + Math.random() * 25, radius: 108 + Math.random() * 15 });
      }
    }
    ball.signature = function (s) { strength = Math.max(0.5, Math.min(s || 1, 1.25)); effectAt = performance.now(); burst(18); return true; };
    ball.signatureComplete = true; ball.burst = burst;
    var applyBase = ball.applyPose;
    ball.applyPose = function (pose) {
      previousPose = pose; applyBase(pose);
      var sketch = pose.body.sketch > 0.5;
      if (groundShadow && !sketch) groundShadow.setAttribute('transform', 'translate(0 -13) ' + (groundShadow.getAttribute('transform') || ''));
      // 加载前/失败时保留可用的原生壳体，线稿模式切换成原生轮廓。
      show(shell, !sketch && !failed); show(head, sketch || !loaded || failed);
      show(screen, sketch || !loaded || failed); show(ao, false);
      if (pinkOutline) { show(pinkOutline, sketch || !loaded || failed); show(head, false); }
      var ink = document.documentElement.getAttribute('data-theme') === 'light' ? '#394761' : '#cce7f0';
      if (pinkOutline) pinkOutline.setAttribute('stroke', ink);
      screen.setAttribute('fill', sketch ? 'none' : '#09121d');
      screen.setAttribute('stroke', sketch ? ink : '#61788e');
      screen.style.stroke = sketch ? ink : '#61788e';
      head.setAttribute('stroke', sketch ? ink : 'none');
      if (sketch) head.style.stroke = ink;
      var now = performance.now(), t = reduced.matches ? 0 : now / 1000;
      var state = states[status], mode = state[0], color = pink && ['idle', 'joy', 'shy', 'receive', 'done'].indexOf(mode) >= 0 ? '#ff8dcc' : state[1];
      var elapsed = (now - effectAt) / 1800;
      var signatureOn = !reduced.matches && elapsed >= 0 && elapsed < 1;
      var envelope = signatureOn ? Math.pow(Math.sin(Math.PI * elapsed), 0.85) : 0;
      var sleep = mode === 'sleep', off = mode === 'off', alarm = mode === 'alert' || mode === 'error';
      var pulse = alarm ? 0.45 + 0.55 * Math.pow(Math.sin(t * 7), 2) : 0.55 + 0.25 * Math.sin(t * 2.2);
      ears.setAttribute('stroke', sketch ? ink : color);
      ears.setAttribute('filter', sketch ? 'none' : 'url(#' + glowId + ')');
      ears.setAttribute('opacity', signatureOn ? Math.min(1, pulse + envelope * 0.45) : off ? 0.12 : sleep ? 0.25 : pulse);
      eyes.forEach(function (eye, index) {
        eye.setAttribute('filter', sketch ? 'none' : 'url(#' + glowId + ')');
        eye.setAttribute('stroke', sketch ? ink : 'none');
        if (sketch) eye.style.stroke = ink;
        eye.setAttribute('opacity', off ? 0.18 : sleep ? 0.5 : 1);
        if (mode === 'error' && !reduced.matches && Math.sin(t * 30) > 0.85) {
          eye.setAttribute('transform', eye.getAttribute('transform') + ' translate(' + (index ? -2 : 2) + ' 0)');
        }
      });
      show(scan, ['boot', 'scan', 'busy', 'network'].indexOf(mode) >= 0); scan.setAttribute('fill', color);
      scan.setAttribute('y', (pink ? 60 : 88) + (t * (mode === 'scan' ? 42 : 25) % (pink ? 110 : 102)));
      show(radar, mode === 'radar' || mode === 'network'); radar.setAttribute('stroke', color); radarDot.setAttribute('fill', color);
      var a = t * (mode === 'network' ? 3 : 1.5), dx = Math.cos(a) * 40, dy = Math.sin(a) * 10;
      sweep.setAttribute('d', 'M120 21L' + (120 + dx).toFixed(2) + ' ' + (21 + dy).toFixed(2));
      radarDot.setAttribute('cx', 120 + dx); radarDot.setAttribute('cy', 21 + dy);
      show(dots, ['radar', 'busy', 'boot', 'network'].indexOf(mode) >= 0); dots.setAttribute('fill', color);
      dotNodes.forEach(function (d, i) { d.setAttribute('opacity', 0.25 + 0.75 * Math.pow(Math.sin(t * 3 - i), 2)); });
      show(wave, mode === 'listen' || mode === 'speak'); wave.setAttribute('stroke', color);
      var waveY = pink ? 169 : 177;
      var wavePath = 'M87 ' + waveY;
      for (var w = 0; w <= 16; w++) wavePath += 'L' + (87 + w * 4) + ' ' + (waveY + Math.sin(w * 1.7 + t * 8) * (mode === 'speak' ? 6 : 2.5) * Math.sin(Math.PI * w / 16)).toFixed(2);
      wave.setAttribute('d', wavePath);
      show(blush, mode === 'shy' || pink && (mode === 'idle' || mode === 'joy')); blush.setAttribute('stroke', color);
      show(tear, mode === 'sad'); tear.setAttribute('fill', color); tear.setAttribute('transform', 'translate(0 ' + ((t * 10) % 22).toFixed(2) + ')');
      show(question, mode === 'question'); question.setAttribute('fill', color); question.setAttribute('transform', 'translate(0 ' + (Math.sin(t * 2) * 3).toFixed(2) + ')');
      show(zzz, sleep && status !== '15'); zzz.setAttribute('fill', color); zzz.setAttribute('transform', 'translate(0 ' + (-Math.sin(t) * 4).toFixed(2) + ')');
      show(glyph, ['done', 'error', 'alert', 'refuse'].indexOf(mode) >= 0); glyph.setAttribute('stroke', color);
      glyph.setAttribute('d', mode === 'done' ? 'M111 177l6 6 13-14' : mode === 'error' ? 'M114 170l12 12m0-12l-12 12' : mode === 'refuse' ? 'M110 176h20' : 'M120 166l12 19h-24ZM120 173v5m0 3v.2');
      show(aurora, signatureOn); show(rim, signatureOn && loaded && !sketch && !failed);
      if (signatureOn) {
        var progress = mode === 'receive' ? 1 - elapsed : elapsed;
        var eased = 1 - Math.pow(1 - progress, 3);
        var lightTheme = document.documentElement.getAttribute('data-theme') === 'light';
        aurora.setAttribute('opacity', envelope * strength);
        aurora.setAttribute('transform', 'translate(' + pose.body.x.toFixed(2) + ' ' + pose.body.y.toFixed(2) + ')');
        mist.setAttribute('opacity', (lightTheme ? 0.6 : 0.9) * envelope);
        rim.setAttribute('opacity', 0.8 * envelope);
        rimColor.setAttribute('flood-color', color);
        ribbons.forEach(function (r, index) {
          var phase = -2.6 + index * 2.15 + eased * (index % 2 ? -2.6 : 3.2);
          var arcLength = (1.35 + index * 0.22) * (0.55 + envelope * 0.45);
          var radius = 119 + index * 6 + eased * 9;
          var d = '', start, end;
          for (var k = 0; k <= 28; k++) {
            var angle = phase - arcLength + arcLength * k / 28;
            var organicRadius = radius + Math.sin(angle * 2 + index) * 4;
            var x = 120 + Math.cos(angle) * organicRadius;
            var y = 125 + Math.sin(angle) * organicRadius * 0.91 + Math.sin(angle * 3 + eased * 2) * 3;
            d += (k ? 'L' : 'M') + x.toFixed(2) + ' ' + y.toFixed(2);
            if (!k) start = [x, y]; if (k === 28) end = [x, y];
          }
          r.line.setAttribute('d', d); r.haze.setAttribute('d', d);
          r.tip.setAttribute('cx', end[0]); r.tip.setAttribute('cy', end[1]);
          r.gradient.setAttribute('x1', start[0]); r.gradient.setAttribute('y1', start[1]);
          r.gradient.setAttribute('x2', end[0]); r.gradient.setAttribute('y2', end[1]);
          r.colorStop.setAttribute('stop-color', lightTheme ? MM.util.shade(color, -0.35) : color);
          r.endStop.setAttribute('stop-color', lightTheme ? '#607ba9' : '#f4ffff');
          r.tip.setAttribute('fill', lightTheme ? '#607ba9' : '#edffff');
          r.wrap.setAttribute('opacity', index === 0 ? 0.95 : index === 1 ? 0.65 : 0.45);
        });
      }
      particles = particles.filter(function (p) {
        var age = (now - p.at) / 1000;
        if (age > 1.65 || reduced.matches) { p.node.remove(); return false; }
        var radius = p.radius + p.speed * (1 - Math.exp(-age * 1.8));
        var angle = p.angle + age * 0.18;
        var x = 120 + Math.cos(angle) * radius, y = 125 + Math.sin(angle) * radius * 0.91 - age * 7;
        p.node.setAttribute('transform', 'translate(' + x.toFixed(2) + ' ' + y.toFixed(2) + ') rotate(' + (angle * 180 / Math.PI).toFixed(1) + ')');
        p.tail.setAttribute('d', 'M0 0L' + (-2.5 - age * 2.5).toFixed(2) + ' 0');
        p.node.setAttribute('opacity', Math.min(1, age * 8) * Math.pow(Math.max(0, 1 - age / 1.65), 1.5)); return true;
      });
      if (mode === 'joy' && !opts.lite && !reduced.matches) {
        if (!joyNodes.length) {
          for (var j = 0; j < 6; j++) { var star = node('path', { d: 'M-3 0H3M0-3V3', stroke: color, 'stroke-width': 1.4 }); sparks.appendChild(star); joyNodes.push(star); }
        }
        joyNodes.forEach(function (n, j) {
          var theta = j * Math.PI / 3 + t * 0.2;
          n.setAttribute('transform', 'translate(' + (120 + 112 * Math.cos(theta)).toFixed(2) + ' ' + (125 + 85 * Math.sin(theta)).toFixed(2) + ')');
          n.setAttribute('opacity', 0.25 + 0.6 * Math.pow(Math.sin(t * 2 + j), 2));
        });
      } else if (joyNodes.length) { joyNodes.forEach(function (n) { n.remove(); }); joyNodes = []; }
    };
    ball.setEmotion(opts.emotion || '02'); return ball;
  };
})();
