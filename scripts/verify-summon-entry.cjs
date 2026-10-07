// Exercise the in-page pet on hosted, localhost and direct-file entry points.
const { chromium } = require('../output/qa-tools/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '..');

(async () => {
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-gpu', '--disable-features=RendererCodeIntegrity']
  });
  const results = [], errors = [];
  try {
    const context = await browser.newContext();
    const serveStatic = async route => {
      const pathname = new URL(route.request().url()).pathname;
      const file = path.join(root, pathname === '/' ? 'index.html' : pathname);
      const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml' };
      await route.fulfill({ body: fs.readFileSync(file), contentType: mime[path.extname(file)] || 'application/octet-stream' });
    };
    await context.route('https://preview.example/**', serveStatic);
    await context.route('http://127.0.0.1:5500/**', serveStatic);

    for (const source of [
      'https://preview.example/',
      'http://127.0.0.1:5500/',
      pathToFileURL(path.join(root, 'index.html')).href
    ]) {
      const page = await context.newPage();
      const requests = [];
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => requests.push(request.url()));
      await page.goto(source);
      await page.waitForFunction(() => window.EG_MAIN && document.querySelectorAll('.cell').length === 32);
      await page.locator('#summonPet').click();
      await page.locator('#webPet').waitFor({ state: 'visible' });
      assert.ok(await page.locator('#webPetCanvas svg').count());
      assert.equal(requests.filter(url => url.startsWith('littlep://')).length, 0);
      assert.equal(requests.filter(url => url.includes('/api/pet/')).length, 0);
      assert.ok(await page.locator('#toast').evaluate(node => node.classList.contains('show')));

      const before = await page.locator('#webPet').boundingBox();
      const handle = await page.locator('#webPetHandle').boundingBox();
      await page.mouse.move(handle.x + 20, handle.y + 18);
      await page.mouse.down();
      await page.mouse.move(Math.max(20, handle.x - 50), Math.max(20, handle.y - 40));
      await page.mouse.up();
      const after = await page.locator('#webPet').boundingBox();
      assert.ok(before.x !== after.x || before.y !== after.y);

      await page.locator('#webPetClose').click();
      await page.waitForTimeout(300);
      assert.equal(await page.locator('#webPet').isHidden(), true);
      results.push(source.startsWith('file:')
        ? 'Direct HTML summons an in-page pet'
        : source.includes('127.0.0.1')
          ? 'Local preview summons an in-page pet'
          : 'Hosted page summons an in-page pet');
      await page.close();
    }

    assert.deepEqual(errors, []);
    results.push('No installer protocol, local API requests or page exceptions are required');
    const report = { passed: results.length, results, errors };
    fs.writeFileSync(path.join(root, 'output/summon-entry-verification.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
