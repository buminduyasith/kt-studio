// Keeps actions on the words that describe them. A scene's voice starts at narration.mark(); inside the
// scene, an action waits for its word ("click Send request" clicks as "Send" is spoken) instead of running
// as fast as the script can. Word times come from demos/<demo>.beats.json (tools/beats.mjs).
//
//   const sync = createSync(page, narration, cursor);
//   const s = await sync.say('A1-05');                 // waits for the page to settle, then the voice starts
//   await s.type(page.getByLabel('Reason'), 'Family trip', 'reason');
//   await s.click(page.getByRole('button', { name: 'Send request' }), 'Send');
//   await s.end();                                     // the rest of the voice line, then the pause
//
// Every cue is logged to <argo dir>/cues.jsonl. check_sync.py reports cues the script reached too late.
//
// Patch takes (scripts/patch.py, `stage.sh --patch`): when demos/<demo>.patch.json names a range of scenes,
// only those are recorded for real. Every scene before the range runs fast (no voice, quick pointer, no
// waiting for words), so the app and the code tour reach exactly the state the delivered video had there;
// the scenes after it run fast too. The cue log marks where the range starts, so patch.py can cut the new
// stretch out of this take and splice it into the delivered video.
import { appendFileSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import type { Locator, Page } from '@playwright/test';
import { demoType, type createHumanCursor } from '@argo-video/cli';
import { CALM, PAUSE_AFTER_POINT, TYPE_MS } from './pacing';

type Cursor = Awaited<ReturnType<typeof createHumanCursor>>;
type Word = { text: string; start: number; end: number };
type Beats = Record<string, { text: string; clipMs: number; speechMs: [number, number]; source: string; words: Word[] }>;
type Narration = { mark(scene: string): void; durationFor(scene: string, options?: { leadOutMs?: number }): number };
export type Move = { durationMs?: number; dwellMs?: number; afterMs?: number };
/** A spoken word or words; `{ word, nth: 2 }` for the second time it is said. */
export type Cue = string | { word: string; nth?: number };
const cueOf = (cue: Cue) => (typeof cue === 'string' ? { word: cue, nth: 1 } : { word: cue.word, nth: cue.nth ?? 1 });

/** The click lands this long after the word starts, so the viewer hears the word, then sees the click. */
export const LAND_AFTER_WORD_MS = 120;

/** Clicking into a field before typing: typing starts soon after the click. */
export const INTO_FIELD = { ...CALM, afterMs: 100 };

/** A short hop to the next field or button, for lines that name several actions close together. */
export const HOP = { durationMs: 450, dwellMs: 120, afterMs: 120 };

/** Where the pointer lands inside a control (Argo's default): in the padding, off the label. */
const AIM = { x: 0.08, y: 0.78 };

const norm = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}']/gu, '');

/** Pointer moves in the fast part of a patch take: quick, but the same targets in the same order. */
const FAST: Move = { durationMs: 80, dwellMs: 20, afterMs: 60 };
/** The silent mark where a patch take's recorded range starts (no voice line has this name). */
export const PATCH_IN = 'kt-patch-in';
/** After the fast part, the page settles (scrolls, notes, highlights finish) before the recorded range starts. */
const SETTLE_BEFORE_PATCH_MS = 1_800;

type Patch = { first: string; last: string; order: string[] };
let patchCache: Patch | null | undefined;
/** The patch range of this take, or null for an ordinary take (demos/<demo>.patch.json, written by stage.sh --patch). */
export function patchRange(): Patch | null {
  if (patchCache !== undefined) return patchCache;
  const file = path.resolve('demos', `${process.env.ARGO_DEMO_NAME ?? ''}.patch.json`);
  patchCache = existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) as Patch : null;
  return patchCache;
}
const orderOf = (scene: string) => patchRange()?.order.indexOf(scene) ?? -1;
/** True when this take is a patch take and the scene is outside its range: it runs fast and is not recorded. */
export function patchSkips(scene: string): boolean {
  const p = patchRange();
  if (!p) return false;
  const i = orderOf(scene);
  if (i < 0) throw new Error(`sync: scene ${scene} is not in the patch order (demos/<demo>.patch.json); re-stage the patch`);
  return i < orderOf(p.first) || i > orderOf(p.last);
}
/** The scene just before the patch range: its end is where the recorded range starts. */
const lastBeforePatch = (scene: string) => {
  const p = patchRange();
  return !!p && orderOf(scene) === orderOf(p.first) - 1;
};

/**
 * Argo's cursor moves in ~16 ms steps and every step costs a browser round trip on top, so a 700 ms move
 * really takes about 1.4 s on a laptop. This pointer measures that cost on each move and asks for a
 * shorter duration, so the travel takes the time the script planned and the click lands on its word.
 */
function createPointer(page: Page, cursor: Cursor) {
  let stepMs = 16;      // learned: extra time per step of the cursor path
  let clickMs = 130;    // learned: locator.click with a 90 ms press, until the click event fires
  const FIXED_MS = 40;  // show the glyph, scroll into view, read the box
  // Argo's path: min(64, max(18, d / 16)) points, one sleep of d / moves after each move.
  const moves = (d: number) => Math.max(2, Math.min(64, Math.max(18, Math.round(d / 16)))) - 1;
  /** Duration to ask Argo for, so the move really takes `wantMs` (the longest d that fits). */
  const ask = (wantMs: number) => {
    for (let d = wantMs; d > 60; d -= 10) if (d + FIXED_MS + moves(d) * stepMs <= wantMs) return d;
    return 60;
  };
  // Learn from ordinary moves and clicks only: one that waited (a scroll, a disabled button) would
  // make every later action land early.
  const ease = (old: number, seen: number, max: number) => (seen >= 0 && seen <= max ? old * 0.5 + seen * 0.5 : old);

  /** Scrolls an off-screen target into view smoothly. Argo's cursor would jump the page there, which
   *  reads as a cut on video. Waits until the target stops moving. */
  async function reveal(target: Locator) {
    const box = await target.boundingBox();
    const view = page.viewportSize() ?? { width: 1920, height: 1080 };
    if (!box || (box.y >= 40 && box.y + box.height <= view.height - 40 && box.x >= 0 && box.x + box.width <= view.width)) return;
    await target.evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' }));
    let last = '';
    for (let i = 0, still = 0; i < 40 && still < 3; i++) {
      await page.waitForTimeout(50);
      const b = await target.boundingBox();
      const at = b ? `${Math.round(b.x)},${Math.round(b.y)}` : '';
      still = at === last ? still + 1 : 0;
      last = at;
    }
  }

  async function travel(target: Locator, wantMs: number) {
    await reveal(target);
    const d = ask(wantMs);
    const t0 = Date.now();
    await cursor.moveTo(target, { durationMs: d, target: AIM });
    stepMs = ease(stepMs, (Date.now() - t0 - d - FIXED_MS) / moves(d), 60);
  }

  /** Draws a look-alike of a native <select> list under the field (the real one never shows on video)
   *  and returns the index of the option to pick: exact value or label first, then a label that contains it. */
  const openList = (select: Locator, option: string) => select.evaluate((el, want) => {
    const s = el as HTMLSelectElement;
    const r = s.getBoundingClientRect();
    const cs = getComputedStyle(s);
    const options = [...s.options];
    const lower = want.toLowerCase();
    let pick = options.findIndex((o) => o.value === want || o.text.trim() === want);
    if (pick < 0) pick = options.findIndex((o) => o.text.toLowerCase().includes(lower));
    if (pick < 0) return -1;
    const list = document.createElement('div');
    list.id = 'kt-options';
    const bg = cs.backgroundColor === 'rgba(0, 0, 0, 0)' ? '#fff' : cs.backgroundColor;
    Object.assign(list.style, { position: 'fixed', left: `${r.left}px`, top: `${r.bottom + 4}px`, minWidth: `${r.width}px`,
      zIndex: '2147483646', background: bg, color: cs.color, font: cs.font, border: '1px solid rgba(127,127,127,.35)',
      borderRadius: '8px', boxShadow: '0 12px 32px rgba(0,0,0,.22)', padding: '4px', pointerEvents: 'none',
      opacity: '0', transition: 'opacity 120ms ease-out' });
    options.forEach((o, i) => {
      const item = document.createElement('div');
      item.dataset.ktOption = String(i);
      item.textContent = o.text;
      Object.assign(item.style, { padding: '8px 12px', borderRadius: '6px', whiteSpace: 'nowrap',
        background: o.selected ? 'rgba(59,130,246,.14)' : 'transparent' });
      list.appendChild(item);
    });
    document.body.appendChild(list);
    requestAnimationFrame(() => { list.style.opacity = '1'; });
    return pick;
  }, option);

  const closeList = () => page.evaluate(() => {
    const list = document.getElementById('kt-options');
    if (!list) return;
    list.style.opacity = '0';
    setTimeout(() => list.remove(), 150);
  });

  return {
    /** Time from the call until the click fires, for a move. */
    landsAfter: (move: Move) => (move.durationMs ?? 700) + (move.dwellMs ?? 200) + clickMs,
    /** Time from the call until a choose() picks its option. */
    picksAfter: (move: Move) => (move.durationMs ?? 700) + (move.dwellMs ?? 200) + 150 + (HOP.durationMs + HOP.dwellMs + 90),
    move: (target: Locator, move: Move = CALM) => travel(target, move.durationMs ?? 700),
    scroll: reveal,
    /** Time from the call until a choose() list is open. */
    opensAfter: (move: Move) => (move.durationMs ?? 700) + (move.dwellMs ?? 200),
    async choose(select: Locator, option: string, move: Move = CALM, beforePick?: () => Promise<void>) {
      await travel(select, move.durationMs ?? 700);
      await page.waitForTimeout(move.dwellMs ?? 200);
      const index = await openList(select, option);
      if (index < 0) throw new Error(`sync: the list has no option "${option}"`);
      await page.waitForTimeout(150);
      if (beforePick) await beforePick();
      const item = page.locator(`#kt-options [data-kt-option="${index}"]`);
      await travel(item, HOP.durationMs);
      await item.evaluate((el) => {
        el.parentElement?.querySelectorAll<HTMLElement>('[data-kt-option]').forEach((i) => { i.style.background = 'transparent'; });
        (el as HTMLElement).style.background = 'rgba(59,130,246,.28)';
      });
      await page.waitForTimeout(HOP.dwellMs + 90);
      await select.selectOption({ index });
      await closeList();
      await page.waitForTimeout(move.afterMs ?? 300);
    },
    async click(target: Locator, move: Move = CALM) {
      await travel(target, move.durationMs ?? 700);
      await page.waitForTimeout(move.dwellMs ?? 200);
      const box = await target.boundingBox();
      const t0 = Date.now();
      // Through the locator, so Playwright still checks the element is ready (like Argo's own click).
      await target.click({ position: box ? { x: box.width * AIM.x, y: box.height * AIM.y } : undefined, delay: 90 });
      clickMs = ease(clickMs, Date.now() - t0, 400);
      await page.waitForTimeout(move.afterMs ?? 300);
    },
  };
}

/**
 * options.ignore: requests the voice need not wait for (analytics, a socket fallback); steady polling is ignored anyway.
 * options.allowInRehearsal: requests a rehearsal (KT_DRY=1) may send although they are not GET (a read-only POST API).
 */
export function createSync(page: Page, narration: Narration, cursor?: Cursor, options: { ignore?: RegExp; allowInRehearsal?: RegExp } = {}) {
  const demo = process.env.ARGO_DEMO_NAME ?? '';
  const file = path.resolve('demos', `${demo}.beats.json`);
  const beats: Beats = existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : {};
  if (!existsSync(file)) console.warn(`sync: ${file} not found; run node tools/beats.mjs ${demo}. Cues fall back to the scene start.`);
  // Beats made from an older voice line would put every cue in the wrong place: stop early instead.
  const scenesFile = path.resolve('demos', `${demo}.scenes.json`);
  if (existsSync(file) && existsSync(scenesFile)) {
    const stale = (JSON.parse(readFileSync(scenesFile, 'utf8')) as { scene: string; text?: string }[])
      .filter((s) => s.text?.trim() && beats[s.scene]?.text !== s.text).map((s) => s.scene);
    if (stale.length) throw new Error(`sync: beats are out of date for ${stale.join(', ')}. Run: npx argo tts generate demos/${demo}.scenes.json && node tools/beats.mjs ${demo}`);
  }
  const log = path.join(process.env.ARGO_OUTPUT_DIR ?? '.', 'cues.jsonl');
  writeFileSync(log, '');
  // Argo keeps these private; they are the same clock the voice is placed on.
  const timeline = narration as unknown as { startTime: number; getPlacements(): { scene: string; startMs: number }[]; timings: Map<string, number> };
  const now = () => Date.now() - timeline.startTime;
  const voiceStart = (scene: string) => timeline.getPlacements().find((p) => p.scene === scene)?.startMs ?? timeline.timings.get(scene) ?? now();
  const pointer = cursor ? createPointer(page, cursor) : null;
  const needPointer = () => {
    if (!pointer) throw new Error('sync: pass the cursor to createSync() to click or move');
    return pointer;
  };

  // Requests in flight, so a voice line never starts while the page is still loading what it talks about.
  // Polling (the same path at a steady rhythm, like a badge refreshed every few seconds) never ends, so it
  // is recognised and ignored, as is anything matching options.ignore.
  type Req = { resourceType(): string; url(): string };
  let inFlight = 0;
  let lastChange = Date.now();
  const counted = new WeakSet<object>();
  const seen = new Map<string, number[]>();
  const polling = (url: string) => {
    let key = url;
    try { key = new URL(url).pathname; } catch { /* keep the raw url */ }
    const times = [...(seen.get(key) ?? []), Date.now()].slice(-5);
    seen.set(key, times);
    if (times.length < 4) return false;
    const gaps = times.slice(1).map((t, i) => t - times[i]);
    const mean = gaps.reduce((a, b) => a + b, 0) / gaps.length;
    return mean >= 200 && gaps.every((g) => Math.abs(g - mean) <= mean * 0.3);
  };
  page.on('request', (r: Req) => {
    if (!['fetch', 'xhr', 'document'].includes(r.resourceType())) return;
    if (options.ignore?.test(r.url()) || (r.resourceType() !== 'document' && polling(r.url()))) return;
    counted.add(r);
    inFlight++;
    lastChange = Date.now();
  });
  const done = (r: Req) => {
    if (!counted.has(r)) return;
    inFlight = Math.max(0, inFlight - 1);
    lastChange = Date.now();
  };
  page.on('requestfinished', done);
  page.on('requestfailed', done);

  // A rehearsal (KT_DRY=1) writes nothing, whatever the script does: requests that could change data are
  // stopped and logged. Reads sent as POST (a GraphQL query) pass; so does options.allowInRehearsal.
  if (process.env.KT_DRY === '1') {
    void page.route('**/*', (route) => {
      const request = route.request();
      const method = request.method();
      const body = request.postData() ?? '';
      const read = ['GET', 'HEAD', 'OPTIONS'].includes(method)
        || /^\s*\{?\s*"?query"?\s*:\s*"\s*(query\b|\{)/.test(body)
        || options.allowInRehearsal?.test(request.url());
      if (read) return route.continue();
      appendFileSync(log, JSON.stringify({ blocked: `${method} ${request.url()}` }) + '\n');
      return route.abort('blockedbyclient');
    });
  }

  // Native dialogs (alert, confirm, prompt, "leave this page?") are drawn by the browser outside the
  // page: they never show on video, and Playwright dismisses them unless someone answers. This is the
  // page's only dialog handler (do not add your own). By default it accepts, and shows alert and
  // confirm messages as a look-alike for a moment. s.confirm() shows a confirm properly, OK and all.
  let dialogMode: 'default' | 'peek' | 'accept' = 'default';
  let lastMessage = '';
  page.on('dialog', async (dialog) => {
    lastMessage = dialog.message();
    if (dialogMode === 'peek') return dialog.dismiss();
    await dialog.accept(dialog.type() === 'prompt' ? dialog.defaultValue() : undefined);
    if (dialogMode === 'default' && (dialog.type() === 'alert' || dialog.type() === 'confirm')) {
      if (dialog.type() === 'confirm') console.warn('sync: a confirm() was accepted without being shown. Use s.confirm(button, word) to show it.');
      void showDialog(dialog.type(), lastMessage).then(() => page.waitForTimeout(1_800)).then(closeDialog).catch(() => {});
    }
  });
  const showDialog = (kind: string, message: string) => page.evaluate(({ kind, message }) => {
    document.getElementById('kt-dialog')?.remove();
    const box = document.createElement('div');
    box.id = 'kt-dialog';
    Object.assign(box.style, { position: 'fixed', top: '16px', left: '50%', transform: 'translateX(-50%)', width: '448px',
      background: '#fff', color: '#202124', borderRadius: '8px', padding: '20px 24px 16px', zIndex: '2147483647',
      boxShadow: '0 4px 24px rgba(0,0,0,.28), 0 0 0 1px rgba(0,0,0,.06)', font: '14px/1.45 system-ui, -apple-system, sans-serif',
      pointerEvents: 'none', opacity: '0', transition: 'opacity 120ms ease-out' });
    const button = (label: string, primary: boolean) => `<span ${primary ? 'data-kt-ok' : ''} style="display:inline-block;padding:7px 18px;border-radius:4px;`
      + (primary ? 'background:#1a73e8;color:#fff;' : 'border:1px solid #dadce0;color:#1a73e8;') + `font-weight:500">${label}</span>`;
    box.innerHTML = `<div style="font-weight:500;font-size:15px">${location.host} says</div>`
      + `<div style="margin:12px 0 18px;white-space:pre-wrap"></div>`
      + `<div style="display:flex;justify-content:flex-end;gap:8px">${kind === 'confirm' ? button('Cancel', false) : ''}${button('OK', true)}</div>`;
    (box.children[1] as HTMLElement).textContent = message;
    document.documentElement.appendChild(box);
    requestAnimationFrame(() => { box.style.opacity = '1'; });
  }, { kind, message });
  const closeDialog = () => page.evaluate(() => {
    const box = document.getElementById('kt-dialog');
    if (!box) return;
    box.style.opacity = '0';
    setTimeout(() => box.remove(), 150);
  });

  /** Waits until no request has been in flight for `quietMs`, at most `maxMs` (a page that polls never goes quiet). */
  let warnedBusy = false;
  async function settle(quietMs = 400, maxMs = 4_000) {
    const until = Date.now() + maxMs;
    while (Date.now() < until && (inFlight > 0 || Date.now() - lastChange < quietMs)) await page.waitForTimeout(50);
    if (Date.now() >= until && !warnedBusy) {
      warnedBusy = true;
      console.warn(`sync: the page did not go quiet within ${maxMs} ms (polling?). Wait for the element you need, and use say(scene, { settle: false }).`);
    }
  }

  function findSpan(scene: string, phrase: string, nth: number) {
    const words = beats[scene]?.words ?? [];
    const want = phrase.split(/\s+/).map(norm).filter(Boolean);
    let seen = 0;
    for (let i = 0; i + want.length <= words.length; i++) {
      if (want.every((w, k) => norm(words[i + k].text) === w) && ++seen === nth) return { first: words[i], last: words[i + want.length - 1] };
    }
    return null;
  }

  const findWord = (scene: string, phrase: string, nth: number) => findSpan(scene, phrase, nth)?.first ?? null;

  let patchStarted = false;
  /** The cue of a scene outside a patch range: same calls, no voice, no waiting for words, a quick pointer. */
  function fastCue(scene: string) {
    const fastEnd = async () => {
      if (!lastBeforePatch(scene)) return;
      await page.waitForTimeout(SETTLE_BEFORE_PATCH_MS);
      patchStarted = true;
      // A silent mark: Argo cuts everything before the first mark (less 0.2 s) from the video, and without
      // this the first mark would be the range's first line, after its navigation: the join needs the
      // frames from here on.
      narration.mark(PATCH_IN);
      appendFileSync(log, JSON.stringify({ patch: 'in', after: scene, ms: now() }) + '\n');
    };
    return {
      at: async (_cue: Cue, _options: { lead?: number } = {}) => {},
      has: (cue: Cue) => findWord(scene, cueOf(cue).word, cueOf(cue).nth) !== null,
      when: (_cue: Cue) => null as { start: number; end: number } | null,
      click: (target: Locator, _phrase?: Cue, _move: Move = CALM) => needPointer().click(target, FAST),
      move: (target: Locator, _phrase?: Cue, _move: Move = CALM) => needPointer().move(target, FAST),
      choose: (select: Locator, option: string, _phrase?: Cue, _options: { pickOn?: Cue; move?: Move } = {}) =>
        needPointer().choose(select, option, FAST),
      async confirm(button: Locator, _phrase?: Cue, _okPhrase?: Cue, _move: Move = CALM) {
        dialogMode = 'accept';
        await needPointer().click(button, FAST);
        dialogMode = 'default';
      },
      scroll: (target: Locator, _phrase?: Cue) => needPointer().scroll(target),
      async type(target: Locator, text: string, _phrase: Cue, _msPerChar = TYPE_MS, _move: Move = INTO_FIELD) {
        await needPointer().click(target, FAST);
        await demoType(page, target, text, 5);
      },
      end: (_pause: number | { leadOutMs?: number } = PAUSE_AFTER_POINT) => fastEnd(),
      left: (_pause: number | { leadOutMs?: number } = PAUSE_AFTER_POINT) => 1,
    };
  }

  async function say(scene: string, options: { settle?: boolean } = {}) {
    if (patchSkips(scene)) {
      if (options.settle !== false) await settle(200, 2_000);
      return fastCue(scene);
    }
    if (patchRange() && !patchStarted) {
      // The range starts at the first scene of the part: the take records it from the beginning.
      patchStarted = true;
      appendFileSync(log, JSON.stringify({ patch: 'in', after: null, ms: 0 }) + '\n');
    }
    if (options.settle !== false) await settle();
    narration.mark(scene);

    /** Waits until `lead` ms before `phrase` is spoken. Returns at once (and logs it) when that moment has passed. */
    async function at(cue: Cue, { lead = 0 } = {}) {
      const { word: phrase, nth } = cueOf(cue);
      const word = findWord(scene, phrase, nth);
      if (!word) {
        console.warn(`sync: "${phrase}" is not in the voice line of ${scene}${beats[scene] ? '' : ' (no beats)'}`);
        appendFileSync(log, JSON.stringify({ scene, phrase: nth > 1 ? `${phrase}#${nth}` : phrase, missing: true }) + '\n');
        return;
      }
      const wordMs = Math.round(voiceStart(scene) + word.start * 1000);
      const actMs = Math.round(wordMs - lead);
      const calledMs = now();
      const lateMs = Math.max(0, calledMs - actMs);
      appendFileSync(log, JSON.stringify({ scene, phrase: nth > 1 ? `${phrase}#${nth}` : phrase, wordMs, actMs, calledMs, lateMs }) + '\n');
      if (lateMs > 300) console.warn(`sync: ${scene} "${phrase}" is ${lateMs} ms late: the actions before it take longer than the voice`);
      if (actMs > calledMs) await page.waitForTimeout(actMs - calledMs);
    }

    return {
      at,
      /** True when the phrase is in this scene's voice line. */
      has: (cue: Cue) => findWord(scene, cueOf(cue).word, cueOf(cue).nth) !== null,
      /** When the phrase is said, in seconds from the start of this scene's clip, or null when it is not. */
      when: (cue: Cue) => {
        const span = findSpan(scene, cueOf(cue).word, cueOf(cue).nth);
        return span ? { start: span.first.start, end: span.last.end ?? span.last.start } : null;
      },
      /** Moves the cursor and clicks so the click lands on the word (or at once, without a word). */
      async click(target: Locator, phrase?: Cue, move: Move = CALM) {
        if (phrase) await at(phrase, { lead: needPointer().landsAfter(move) - LAND_AFTER_WORD_MS });
        await needPointer().click(target, move);
      },
      /** Moves the cursor so it arrives on the word (or at once, without a word). */
      async move(target: Locator, phrase?: Cue, move: Move = CALM) {
        if (phrase) await at(phrase, { lead: (move.durationMs ?? 700) - LAND_AFTER_WORD_MS });
        await needPointer().move(target, move);
      },
      /** Picks an option of a native <select> on the word, with a visible list (see choose() in the pointer). */
      async choose(select: Locator, option: string, phrase?: Cue, { pickOn, move = CALM }: { pickOn?: Cue; move?: Move } = {}) {
        if (!pickOn) {
          if (phrase) await at(phrase, { lead: needPointer().picksAfter(move) - LAND_AFTER_WORD_MS });
          return needPointer().choose(select, option, move);
        }
        // Open the list on `phrase`, keep it open while the voice talks about it, pick on `pickOn`.
        if (phrase) await at(phrase, { lead: needPointer().opensAfter(move) });
        await needPointer().choose(select, option, move, () => at(pickOn, { lead: HOP.durationMs + HOP.dwellMs + 90 - LAND_AFTER_WORD_MS }));
      },
      /**
       * A button that asks with the browser's confirm(). Clicks it on `phrase` (the app asks; the answer is
       * held back), shows the question as a look-alike, clicks OK on `okPhrase` (or after a moment to
       * read it), then runs the button again with the answer yes, without moving the mouse.
       */
      async confirm(button: Locator, phrase?: Cue, okPhrase?: Cue, move: Move = CALM) {
        if (phrase) await at(phrase, { lead: needPointer().landsAfter(move) - LAND_AFTER_WORD_MS });
        lastMessage = '';
        dialogMode = 'peek';
        await needPointer().click(button, { ...move, afterMs: 120 });
        dialogMode = 'default';
        if (!lastMessage) throw new Error('sync: confirm(): that click did not open a confirm() dialog');
        await showDialog('confirm', lastMessage);
        const ok = page.locator('#kt-dialog [data-kt-ok]');
        if (okPhrase) await at(okPhrase, { lead: needPointer().landsAfter(HOP) - LAND_AFTER_WORD_MS });
        else await page.waitForTimeout(900);
        await needPointer().move(ok, HOP);
        await page.waitForTimeout(HOP.dwellMs + 90);
        await closeDialog();
        dialogMode = 'accept';
        // A form that submits may navigate away while this returns: that is success.
        await button.evaluate((el) => (el as HTMLElement).click())
          .catch((err) => { if (!/context was destroyed|navigat/i.test(String(err))) throw err; });
        dialogMode = 'default';
        await page.waitForTimeout(move.afterMs ?? 300);
      },
      /** Scrolls a target into view smoothly, on the word (clicks and moves already do this themselves). */
      async scroll(target: Locator, phrase?: Cue) {
        if (phrase) await at(phrase);
        await needPointer().scroll(target);
      },
      /** Clicks the field on the word, then types. */
      async type(target: Locator, text: string, phrase: Cue, msPerChar = TYPE_MS, move: Move = INTO_FIELD) {
        await at(phrase, { lead: needPointer().landsAfter(move) - LAND_AFTER_WORD_MS });
        await needPointer().click(target, move);
        await demoType(page, target, text, msPerChar);
      },
      /** The rest of the voice line, then the pause after the point: measured from the last spoken sound,
       *  so the pause is exactly that long (the clip's own trailing silence is not added on top). */
      async end(pause: number | { leadOutMs?: number } = PAUSE_AFTER_POINT) {
        await page.waitForTimeout(left(pause));
        // Where the scene ends (after its pause, before the next scene's navigation): patch.py cuts here.
        appendFileSync(log, JSON.stringify({ scene, endMs: now() }) + '\n');
      },
      /** Milliseconds until the scene should end, as end() waits: the length for showOverlay(page, id, s.left()). */
      left,
    };

    function left(pause: number | { leadOutMs?: number } = PAUSE_AFTER_POINT) {
      const leadOutMs = typeof pause === 'number' ? pause : pause.leadOutMs ?? 1_500;
      const b = beats[scene];
      if (!b) return narration.durationFor(scene, { leadOutMs });
      const start = voiceStart(scene);
      // Never before the clip ends, or Argo would push the next line later than its mark.
      const until = Math.max(start + b.speechMs[1] + leadOutMs, start + b.clipMs + 100);
      return Math.max(0, Math.round(until - now()));
    }
  }

  return {
    say,
    settle,
    /** A click with the calibrated pointer, not tied to a word (housekeeping before a line). */
    click: (target: Locator, move: Move = CALM) => needPointer().click(target, move),
    move: (target: Locator, move: Move = CALM) => needPointer().move(target, move),
    choose: (select: Locator, option: string, move: Move = CALM) => needPointer().choose(select, option, move),
    scroll: (target: Locator) => needPointer().scroll(target),
  };
}

export type SceneCue = Awaited<ReturnType<ReturnType<typeof createSync>['say']>>;
