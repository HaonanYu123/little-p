// Exercise hosted/file entry points without requiring an installed protocol handler.
const { chromium } = require('../output/qa-tools/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '..');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const results = [], errors = [];
  try {
    const context = await browser.newContext();
    await context.route('https://preview.example/**', async route => {
      const pathname = new URL(route.request().url()).pathname;
      const file = path.join(root, pathname === '/' ? 'index.html' : pathname);
      const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml' };
      await route.fulfill({ body: fs.readFileSync(file), contentType: mime[path.extname(file)] || 'application/octet-stream' });
    });
    for (const source of ['https://preview.example/', pathToFileURL(path.join(root, 'index.html')).href]) {
      const page = await context.newPage();
      const requests = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => requests.push(request.url()));
      await page.goto(source);
      await page.waitForFunction(() => window.EG_MAIN && document.querySelectorAll('.cell').length === 32);
      await page.locator('#summonPet').click();
      await page.waitForTimeout(300);
      const protocol = requests.find(url => url.startsWith('littlep://summon?'));
      assert.ok(protocol);
      const values = new URL(protocol).searchParams;
      assert.equal(values.get('character'), 'pink-robot');
      assert.equal(values.get('emotion'), '02');
      assert.equal(requests.filter(url => url.includes('/api/pet/')).length, 0);
      assert.ok((await page.locator('#toast').textContent()).includes('正在打开 Little P'));
      assert.equal(await page.locator('#summonPet').isEnabled(), true);
      results.push(source.startsWith('file:') ? 'Direct HTML uses littlep:// protocol' : 'Hosted preview uses littlep:// protocol');
      await page.close();
    }
    assert.deepEqual(errors, []);
    results.push('No erroneous local API requests or page exceptions from published origins');
    const report = { passed: results.length, results, errors };
    fs.writeFileSync(path.join(root, 'output/summon-entry-verification.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
