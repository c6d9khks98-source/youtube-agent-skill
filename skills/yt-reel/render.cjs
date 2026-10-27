// render.cjs - turn one effects/*.html page into a transparent PNG sequence.
//
//   node render.cjs <page.html> <params.json> <fps> <seconds> <outdir>
//
// Each page exposes window.seek(t) and draws itself for time t, so every frame is deterministic.
// seconds = 0 renders a single still (frame_0000.png). Called by reel.py; needs Playwright.
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const [page, params, fps, seconds, outdir] = process.argv.slice(2);
  fs.mkdirSync(outdir, { recursive: true });
  const browser = await chromium.launch();
  const tab = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  const hash = encodeURIComponent(fs.readFileSync(params, 'utf8'));
  await tab.goto('file://' + path.resolve(page) + '#' + hash);
  await tab.evaluate(() => document.fonts.ready);
  const n = Math.max(1, Math.round(Number(seconds) * Number(fps)));
  for (let i = 0; i < n; i++) {
    await tab.evaluate(t => window.seek(t), i / Number(fps));
    await tab.screenshot({ path: path.join(outdir, `frame_${String(i).padStart(4, '0')}.png`),
                           omitBackground: true });
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
