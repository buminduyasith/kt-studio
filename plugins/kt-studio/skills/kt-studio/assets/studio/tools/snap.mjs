// Takes pictures of a local HTML page (a storyboard, a code tour) so the agent can look at what it built
// before a person does. Long pages are cut into tiles that stay readable.
//
// Usage: node tools/snap.mjs <page.html | http://url> <out-dir> [--width 1440] [--tile 1800]
// Writes <out-dir>/snap-01.png, snap-02.png, ... and prints their paths. Also prints page errors.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i === -1 ? fallback : Number(args.splice(i, 2)[1]);
};
const width = opt('width', 1440);
const tile = opt('tile', 1800);
const [target, outDir] = args;
if (!target || !outDir) {
  console.error('usage: node tools/snap.mjs <page.html | url> <out-dir> [--width 1440] [--tile 1800]');
  process.exit(1);
}
const url = /^https?:/.test(target) ? target : pathToFileURL(path.resolve(target)).href;
const { chromium } = createRequire(path.join(process.cwd(), 'package.json'))('playwright');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width, height: tile } });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
// Web fonts may be offline: give them a moment, never fail on them.
await page.goto(url, { waitUntil: 'load', timeout: 30_000 }).catch((e) => errors.push(e.message));
await page.waitForTimeout(800);
const height = await page.evaluate(() => document.documentElement.scrollHeight);
mkdirSync(outDir, { recursive: true });
for (let y = 0, n = 1; y < height; y += tile, n++) {
  const file = path.join(outDir, `snap-${String(n).padStart(2, '0')}.png`);
  await page.screenshot({ path: file, fullPage: true, clip: { x: 0, y, width, height: Math.min(tile, height - y) } });
  console.log(file);
}
await browser.close();
for (const e of errors) console.log(`page error: ${e}`);
console.log(`${Math.ceil(height / tile)} tiles, page ${width}x${height}`);
