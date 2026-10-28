// Draws the exact icons from tools/loot_icons.html into web/assets/loot.png and adds the new cells to loot.json.
// Usage: node tools/loot_icons.js [--preview out.png]. Needs Playwright with Chromium; not part of the game.
const fs = require('fs'), path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT || '/opt/node22/lib/node_modules/playwright');
const ROOT = path.resolve(__dirname, '..'), PNG = path.join(ROOT, 'web/assets/loot.png'), JSON_ = path.join(ROOT, 'web/assets/loot.json');
const KEYS = ['w_pm', 'w_sks', 'w_svd', 'w_pkm', 'vatnik', 'peacoat', 'vest', 'crackers', 'tea', 'bandage', 'nails'];
(async () => {
  const meta = JSON.parse(fs.readFileSync(JSON_, 'utf8'));
  // Keys already in the atlas keep their cell; new ones take the free cells after the last used one.
  const used = new Set(Object.values(meta.items).map(c => c.x + ',' + c.y));
  const free = []; const img = fs.readFileSync(PNG), w = img.readUInt32BE(16), h = img.readUInt32BE(20);
  for (let y = 0; y < h; y += 64) for (let x = 0; x < w; x += 64) if (!used.has(x + ',' + y)) free.push([x, y]);
  const cells = KEYS.map(k => { if (!meta.items[k]) { const [x, y] = free.shift(); meta.items[k] = { x, y, w: 64, h: 64 }; } return [k, meta.items[k].x, meta.items[k].y]; });
  const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
  const page = await browser.newPage();
  await page.goto('file://' + path.join(__dirname, 'loot_icons.html'));
  const out = process.argv.indexOf('--preview');
  if (out > 0) {
    const url = await page.evaluate(([k, raw]) => raw ? window.raw(k) : window.preview(k), [KEYS, process.argv.includes('--raw')]);
    fs.writeFileSync(process.argv[out + 1], Buffer.from(url.split(',')[1], 'base64'));
  } else {
    const url = await page.evaluate(([a, c]) => window.build(a, c), ['data:image/png;base64,' + img.toString('base64'), cells]);
    fs.writeFileSync(PNG, Buffer.from(url.split(',')[1], 'base64'));
    fs.writeFileSync(JSON_, JSON.stringify(meta, null, 1) + '\n');
    console.log('drawn:', KEYS.join(', '));
  }
  await browser.close();
})();
