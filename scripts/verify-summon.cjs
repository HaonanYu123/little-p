// Integration checks using the real local service and real Windows desktop pet.
const { chromium } = require('../output/qa-tools/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const root = 'http://127.0.0.1:8086';
async function status() { return (await fetch(root + '/api/pet/status')).json(); }
async function waitState(test) {
  for (let i = 0; i < 60; i++) { const s = await status(); if (test(s)) return s; await new Promise(r => setTimeout(r, 120)); }
  throw new Error('Desktop state did not synchronize');
}
(async () => {
  const results = [], errors = [];
  const check = (name, passed) => { assert.ok(passed, name); results.push(name); };
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(root, { waitUntil: 'networkidle' });
    check('Pink renderer uses the oval head-only asset', await page.locator('#stage .robot-texture').getAttribute('href').then(s => s.endsWith('/pink-head-soft-oval.png')));
    check('Pink viewBox and sketch contain no lower body', await page.locator('#stage svg').getAttribute('viewBox') === '-38 -78 316 302' && await page.locator('#stage .pink-sketch-outline path').count() === 3);
    await page.locator('#summonPet').click();
    const pet = await waitState(s => s.active && s.ready && s.state.character === 'pink-robot');
    await page.waitForFunction(() => !document.getElementById('summonPet').disabled && document.getElementById('toast').textContent.includes('已来到桌面'));
    check('Summon button launches a real ready desktop process', pet.pid > 0 && await page.locator('#toast').textContent().then(s => s.includes('已来到桌面')));
    check('Desktop pet is half its previous width and height', pet.native_size?.[0] === 155 && pet.native_size?.[1] === 155);
    await page.locator('#summonPet').click();
    check('Repeated summons reuse the same process', (await status()).pid === pet.pid);
    await page.evaluate(() => EG_MAIN.setEmotion('13'));
    await waitState(s => s.state.emotion === '13');
    check('Web expression updates reach desktop', true);
    await page.locator('.cast[data-character="robot"]').click();
    await waitState(s => s.state.character === 'robot');
    check('Classic character synchronizes to desktop', true);
    await page.locator('.cast[data-character="pink-robot"]').click();
    await waitState(s => s.state.character === 'pink-robot');
    await page.locator('#sketchToggle').check();
    await waitState(s => s.state.sketch);
    check('Sketch mode synchronizes', true);
    await page.locator('#sketchToggle').uncheck();
    await waitState(s => !s.state.sketch);
    await page.locator('#langToggle').click();
    await waitState(s => s.state.lang === 'en');
    check('Language synchronizes', true);
    await page.locator('#langToggle').click();
    await waitState(s => s.state.lang === 'zh');
    await page.locator('#themeToggle').click();
    await waitState(s => s.state.theme === 'dark');
    check('Theme synchronizes', true);
    await page.locator('#themeToggle').click();
    await page.evaluate(() => EG_MAIN.setEmotion('02'));
    await waitState(s => s.state.emotion === '02' && s.state.theme === 'light');
    await page.waitForTimeout(3700);
    await page.screenshot({ path: 'output/head-and-summon-desktop.png' });
    await page.setViewportSize({ width: 390, height: 844 });
    check('Summon control remains visible on mobile with no horizontal overflow', await page.locator('#summonPet').isVisible() && await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: 'output/head-and-summon-mobile.png' });
    const invalid = await fetch(root + '/api/pet/summon', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ character: 'unknown' }) });
    check('Invalid launch arguments rejected', invalid.status === 400);
    const crossOrigin = await fetch(root + '/api/pet/summon', { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: 'https://example.com' }, body: JSON.stringify({ character: 'pink-robot' }) });
    check('Unrelated website cannot invoke the launcher', crossOrigin.status === 403);
    await browser.close();
    check('Desktop pet continues after the browser closes', (await status()).active && (await status()).pid === pet.pid);
    check('No page exceptions', errors.length === 0);
    const report = { passed: results.length, results, errors, desktop_pid: pet.pid };
    fs.writeFileSync('output/summon-verification.json', JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
