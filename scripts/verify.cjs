// Start the local server, then: node scripts/verify.cjs
const { chromium } = require('../output/qa-tools/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  fs.mkdirSync('output', { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [], results = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('response', r => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });
    const check = (name, ok) => { assert.ok(ok, name); results.push(name); };
    const state = () => page.evaluate(() => ({ emotion: EG_MAIN.emotionId, tour: EG_MAIN.touring, cells: document.querySelectorAll('.cell').length, open: document.body.classList.contains('stage-open') }));
    await page.goto('http://127.0.0.1:8086', { waitUntil: 'networkidle' });
    await page.waitForFunction(() => window.EG_MAIN && document.querySelectorAll('.cell').length === 32);
    check('Two P characters and all 32 expressions', JSON.stringify(await page.evaluate(() => MoodMates.characters.list().map(c => c.id))) === JSON.stringify(['robot', 'pink-robot']) && (await state()).cells === 32);
    check('Desktop shows all 32 in an 8 by 4 grid without a horizontal rail', await page.evaluate(() => {
      const grid = document.querySelector('#thumbFlow'), zone = document.querySelector('#thumbZone');
      const boxes = [...grid.children].map(el => el.getBoundingClientRect());
      return getComputedStyle(grid).display === 'grid' && new Set(boxes.map(r => r.x)).size === 8 && new Set(boxes.map(r => r.y)).size === 4 && boxes.every(r => r.left >= 0 && r.right <= innerWidth) && zone.scrollWidth <= zone.clientWidth && document.documentElement.scrollWidth <= innerWidth;
    }));
    check('Original full-width Hero and drawn background are restored', await page.locator('#hero').evaluate(el => el.getBoundingClientRect().width === innerWidth && el.getBoundingClientRect().height >= 620) && await page.locator('#heroField').evaluate(el => el.width > 0 && el.getContext('2d').getImageData(0, 0, el.width, el.height).data.some((v, i) => i % 4 === 3 && v > 0)) && await page.locator('#heroBot svg').count() === 1);
    check('Redundant copy and horizontal view controls stay removed', await page.locator('#modeAlbum, .gallery-hint, .stage-eyebrow, .emo-desc, .hero-sub, .hero-bottom').count() === 0);
    await page.locator('#heroCta').click();
    await page.waitForFunction(() => scrollY > 0 && document.querySelector('#thumbFlow').getBoundingClientRect().bottom <= innerHeight + 1);
    check('Hero button reaches the complete expression grid', await page.locator('#thumbFlow .cell').count() === 32);
    await page.screenshot({ path: 'output/desktop.png', fullPage: true });
    check('Both transparent textures decode', await page.evaluate(async () => {
      const urls = [...new Set([...document.querySelectorAll('image.robot-texture')].map(i => i.getAttribute('href')))];
      for (const url of urls) {
        const img = new Image(); img.src = url; await img.decode();
        const canvas = document.createElement('canvas'); canvas.width = img.naturalWidth; canvas.height = img.naturalHeight;
        const ctx = canvas.getContext('2d'); ctx.drawImage(img, 0, 0);
        if (ctx.getImageData(0, 0, 1, 1).data[3] !== 0) return false;
      }
      return urls.length === 2;
    }));
    const ids = await page.evaluate(() => MoodMates.config.list().map(d => d.id));
    for (const character of ['pink-robot', 'robot']) {
      await page.locator(`.cast[data-character="${character}"]`).click();
      for (const id of ids) {
        await page.evaluate(id => EG_MAIN.setEmotion(id), id);
        await page.waitForTimeout(75);
        assert.equal((await state()).emotion, id, `${character}: ${id}`);
        assert.equal(await page.locator('#stage svg').getAttribute('data-emotion'), id);
        assert.ok(await page.locator('#stage svg').evaluate(svg => !/NaN|Infinity|undefined/.test(svg.innerHTML)), `${character}: invalid SVG ${id}`);
      }
      check(`${character}: all 32 states render and Hero follows character`, (await state()).cells === 32 && await page.locator('#heroBot .robot-texture').getAttribute('href').then(href => href.includes(character === 'pink-robot' ? 'pink-head' : 'robot-shell')));
    }
    await page.locator('.cast[data-character="pink-robot"]').click();
    await page.locator('.cell[data-emotion="10"]').click();
    check('Click opens the chosen expression and focuses its close button', (await state()).emotion === '10' && (await state()).open && await page.locator('#stageClose').evaluate(el => el === document.activeElement));
    await page.keyboard.press('ArrowRight');
    check('Arrow navigation', (await state()).emotion === '11');
    await page.keyboard.press('Tab');
    check('Modal keyboard focus stays in the preview', await page.evaluate(() => !!document.activeElement.closest('.stage-zone')));
    await page.keyboard.press('Escape');
    check('Escape restores grid focus', !(await state()).open && await page.locator('.cell[data-emotion="10"]').evaluate(el => el === document.activeElement));
    await page.locator('#tourInterval').selectOption('1500');
    await page.locator('#tourToggle').check();
    check('Autoplay starts and opens preview', (await state()).tour && (await state()).open);
    const before = (await state()).emotion;
    await page.waitForTimeout(1750);
    check('Autoplay advances', (await state()).emotion !== before);
    await page.locator('#stageClose').click();
    check('Closing preview stops autoplay and restores all 32 expressions', !(await state()).tour && !(await state()).open && !(await page.locator('#tourToggle').isChecked()) && (await state()).cells === 32);
    await page.locator('#sketchToggle').check();
    await page.waitForTimeout(550);
    check('Sketch applies to the stage and all 32 grid cells', await page.locator('#stage .robot-texture').evaluate(el => el.style.display === 'none') && await page.locator('#thumbFlow .robot-texture').evaluateAll(els => els.length === 32 && els.every(el => el.style.display === 'none')));
    check('Pink screen and sketch use the subtle oval geometry', await page.locator('#thumbFlow .pink-oval-screen').first().evaluate(el => { const r = el.getBBox(); return r.width / r.height > 1.08 && r.width / r.height < 1.25; }) && await page.locator('#heroBot .robot-texture').getAttribute('href').then(href => href.endsWith('/pink-head-soft-oval.png')));
    await page.screenshot({ path: 'output/sketch.png', fullPage: true });
    await page.locator('#sketchToggle').uncheck();
    await page.evaluate(() => EG_MAIN.handleAIMessage({ emotionId: '30', tips: '正在思考' }));
    check('Engine API still updates expression and tips', (await state()).emotion === '30' && await page.locator('#tips').textContent() === '正在思考');
    await page.locator('#themeToggle').click();
    await page.locator('#langToggle').click();
    check('Dark theme and English labels', await page.getAttribute('html', 'data-theme') === 'dark' && await page.locator('.cell[data-emotion="10"]').textContent().then(t => t.includes('Happy')));
    await page.screenshot({ path: 'output/dark-english.png', fullPage: true });
    await page.evaluate(() => {
      const key = 'xiaop.studio.prefs.v1';
      const prefs = JSON.parse(localStorage.getItem(key)); prefs.mode = 'album';
      localStorage.setItem(key, JSON.stringify(prefs));
    });
    await page.reload({ waitUntil: 'networkidle' });
    check('Legacy album preference migrates to the full grid while keeping theme and language', await page.getAttribute('html', 'data-theme') === 'dark' && await page.getAttribute('html', 'lang') === 'en' && await page.locator('#thumbFlow').evaluate(el => getComputedStyle(el).display === 'grid') && (await state()).cells === 32 && await page.evaluate(() => !('mode' in JSON.parse(localStorage.getItem('xiaop.studio.prefs.v1')))));
    await page.locator('#themeToggle').click();
    await page.locator('#langToggle').click();
    await page.evaluate(() => EG_MAIN.setEmotion('02'));
    for (const width of [1024, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      check(`${width}px: all 32 cells wrap without horizontal overflow`, await page.evaluate(() => document.querySelectorAll('.cell').length === 32 && document.documentElement.scrollWidth <= innerWidth && document.querySelector('#thumbZone').scrollWidth <= document.querySelector('#thumbZone').clientWidth));
    }
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: 'output/mobile.png', fullPage: true });
    await page.locator('.cell[data-emotion="14"]').click();
    check('Mobile preview fits viewport', await page.locator('.stage-block').evaluate(el => { const r = el.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight; }));
    await page.screenshot({ path: 'output/mobile-preview.png' });
    await page.keyboard.press('Escape');
    check('No JS exceptions or failed requests', errors.length === 0);
    const report = { passed: results.length, results, errors };
    fs.writeFileSync('output/verification.json', JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
