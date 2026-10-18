// Drives the VS Code style tour page (ide/ide.js) in time with the narration.
// Rule that keeps voice and picture in sync: navigate BEFORE narration.mark(scene), explain after it.
import type { Page } from '@playwright/test';
import { demoType, createHumanCursor } from '@argo-video/cli';
import { CALM, PAUSE_AFTER_POINT, PAUSE_AFTER_WALK, QUICK_OPEN_MS } from './pacing';
import { HOP, patchSkips, type Cue, type SceneCue } from './sync';

export type Ranges = [number, number][];
export type Cursor = Awaited<ReturnType<typeof createHumanCursor>>;
// The Argo narration fixture; only mark, durationFor and sceneDuration are used here.
export type Narration = {
  mark(scene: string): void;
  durationFor(scene: string, options?: { leadOutMs?: number; leadInMs?: number }): number;
  sceneDuration(scene: string): number;
};

declare global {
  interface Window {
    TOUR: { repos: Record<string, { dir: string }> };
    ide: {
      open(repo: string, path: string): Promise<void>;
      focus(ranges: Ranges, note?: string, options?: { offset?: number; ms?: number }): Promise<void>;
      unfocus(): void;
      flow(journey: string, step: string | null): void;
      welcome(title: string, sub: string): void;
      showPalette(): void;
      scrollTreeTo(id: string): Promise<void>;
      linkToken(line: number, token: string): void;
      tip(id: string, text: string): void;
      clearTips(): void;
      sequence(name: string): void;
      rank(query: string): { id: string; score: number }[];
      sequenceStep(first: number, last?: number): void;
      hideSequence(): void;
      terminalShow(cwd?: string): void;
      terminalHide(): void;
      terminalClear(): void;
      terminalRun(scene: string, msPerChar?: number, msPerLine?: number): Promise<void>;
      map(name: string, options?: { all?: boolean }): void;
      mapReveal(ids: string[], gap?: number): Promise<void>;
      mapStep(step: number, ms?: number): Promise<void>;
      mapReplay(ms?: number): Promise<void>;
      mapOverview(): Promise<void>;
      mapFocus(ids: string[] | null): void;
      mapZoom(id: string): Promise<void>;
      hideMap(): void;
      locate(name: string, id: string): void;
      hideLocator(): void;
    };
  }
}

export async function openTour(page: Page, url = process.env.KT_TOUR_URL ?? 'http://127.0.0.1:8765/ide.html') {
  await page.goto(url);
  await page.waitForFunction(() => Boolean(window.ide));
}

export const focus = (page: Page, ranges: Ranges, note?: string) =>
  page.evaluate(({ ranges, note }) => window.ide.focus(ranges, note), { ranges, note });

export const flow = (page: Page, journey: string, step: string | null) =>
  page.evaluate(({ journey, step }) => window.ide.flow(journey, step), { journey, step });

export const welcome = (page: Page, title: string, sub: string) =>
  page.evaluate(({ title, sub }) => window.ide.welcome(title, sub), { title, sub });

/** The spoken cue for a folder or file name, said after `afterSec` in the line: "order-service" is also
 *  found as "order service", "refund.service.ts" as "refund service". The first time it is said after the
 *  last folder's word wins, so "open order service, then service" clicks the second folder on the second "service". */
function cueFor(cue: SceneCue, name: string, afterSec: number): { word: string; nth: number; at: number; end: number } | null {
  const stem = name.replace(/\.[a-z0-9]+$/i, '');
  const forms = [...new Set([name, stem, stem.replace(/[-_.]+/g, ' '), stem.replace(/([a-z])([A-Z])/g, '$1 $2')])];
  let best: { word: string; nth: number; at: number; end: number } | null = null;
  for (const word of forms) {
    for (let nth = 1; nth < 10; nth++) {
      const span = cue.when({ word, nth });
      if (span === null) break;
      // A name said in the line's first second comes too soon for the pointer to get there: open it at once.
      if (span.start >= afterSec && span.start >= 1.0) {
        if (!best || span.start < best.at) best = { word, nth, at: span.start, end: span.end };
        break;
      }
    }
  }
  return best;
}

/** Open each closed folder on the way to `path`, like a person would.
 *  Without a cue: every folder is clicked with the calm pointer.
 *  With a scene cue (lib/sync.ts): a folder named in the voice line is clicked as its name is spoken, with
 *  a short hop; the folders the line does not name open at once, the way VS Code shows compact folders
 *  (a Java path such as src/main/java/com/shop is one quick step, not five slow clicks). */
export async function clickThrough(page: Page, cursor: Cursor, repo: string, path: string, cue?: SceneCue) {
  const parts = path.split('/');
  const ids = [`${repo}:`, ...parts.map((_, i) => `${repo}:${parts.slice(0, i + 1).join('/')}`)];
  const names = [await page.evaluate((key) => window.TOUR.repos[key].dir, repo), ...parts];
  let lastSec = -1;
  let quiet: string[] = [];   // unnamed folders waiting to be opened together
  const openQuiet = async () => {
    if (!quiet.length) return;
    // A run of folders the line does not name (src/main/java/com/shop) opens in one step, like VS Code's
    // compact folders: one at a time, each with its own scroll and click, a deep Java path ran 1.3 s late.
    await page.evaluate((batch) => {
      for (const id of batch) {
        const row = document.querySelector<HTMLElement>(`.row[data-id="${CSS.escape(id)}"]`);
        if (row && !row.querySelector('.chev.open')) row.click();
      }
    }, quiet);
    await page.evaluate((rowId) => window.ide.scrollTreeTo(rowId), quiet.at(-1)!);
    quiet = [];
    await page.waitForTimeout(150);
  };
  await page.evaluate(() => window.ide.hideSequence());  // a diagram from the scene before would cover the explorer walk
  for (const [k, id] of ids.entries()) {
    const isFile = k === ids.length - 1;
    const said = cue ? cueFor(cue, names[k], lastSec) : null;
    if (cue && !said && !isFile) {
      quiet.push(id);
      continue;
    }
    await openQuiet();
    const row = page.locator(`.row[data-id="${id}"]`);
    if (!isFile && (await row.locator('.chev.open').count())) continue;
    await page.evaluate((rowId) => window.ide.scrollTreeTo(rowId), id);
    if (!cue) await cursor.click(row, CALM);
    else if (said) {
      lastSec = said.end;   // the next folder is a word said after this name ends
      await cue.click(row, { word: said.word, nth: said.nth }, HOP);
    } else await cue.click(row, undefined, HOP);   // the file itself, even when the line does not name it
  }
  await openQuiet();
  await page.waitForTimeout(800);
}

const PALETTE = { showMs: 200, beforeEnterMs: 300, afterMs: 500 };
const paletteMs = (query: string) => PALETTE.showMs + query.length * QUICK_OPEN_MS + PALETTE.beforeEnterMs;

/** Ctrl+P style open: types the query into the palette and presses Enter. About 1 to 1.5 s.
 *  Fails when the query matches no file, or two files equally well (add part of the path: "api/client"). */
export async function quickOpen(page: Page, query: string) {
  const ranked = await page.evaluate((q) => window.ide.rank(q), query);
  if (!ranked.length) throw new Error(`quickOpen("${query}"): no tour file matches`);
  if (ranked[1] && ranked[1].score === ranked[0].score) {
    throw new Error(`quickOpen("${query}") is ambiguous: ${ranked.filter((m) => m.score === ranked[0].score).map((m) => m.id).join(', ')}. Use more of the path.`);
  }
  await page.evaluate(() => window.ide.showPalette());
  await page.waitForTimeout(PALETTE.showMs);
  await demoType(page, '#palette-input', query, QUICK_OPEN_MS);
  await page.waitForTimeout(PALETTE.beforeEnterMs);
  await page.keyboard.press('Enter');
  await page.waitForTimeout(PALETTE.afterMs);
}

/** The same open, timed so the file appears as `word` is spoken ("one small client"). The scene is already marked. */
export async function quickOpenOn(page: Page, cue: SceneCue, query: string, word: string) {
  await cue.at(word, { lead: paletteMs(query) });
  await quickOpen(page, query);
}

/** "Follow the call": underline a token, click it, land on the target line in another file. */
export async function follow(
  page: Page,
  cursor: Cursor,
  from: { line: number; token: string },
  to: { repo: string; path: string; line: number },
) {
  await page.evaluate(({ line, token }) => window.ide.linkToken(line, token), from);
  await cursor.click(page.locator('#kt-link'), { durationMs: 900, dwellMs: 500 });
  await cursor.hide();
  await page.evaluate(async ({ repo, path, line }) => {
    await window.ide.open(repo, path);
    await window.ide.focus([[line, line]], undefined, { ms: 900 });
  }, to);
  await page.waitForTimeout(700);
}

/** One spoken point: highlight lines, show the note, wait for the voice plus a pause. */
export async function explain(page: Page, narration: Narration, scene: string, ranges: Ranges, note?: string) {
  if (patchSkips(scene)) return focus(page, ranges, note);  // outside a patch range: same picture, no voice
  narration.mark(scene);
  await focus(page, ranges, note);
  await page.waitForTimeout(narration.durationFor(scene, PAUSE_AFTER_POINT));
}

/**
 * A sequence diagram scene (storyboard kind "diagram"). Shows diagram `name` and lights the scene's
 * steps, the same `[first, last]` as its storyboard `diagram.steps`, one after another: the first at once,
 * each next one on its word when `words` gives one, else 1.2 s later. The scene is already marked.
 * `diagramOn(await sync.say('B1-02'), page, 'book', [1, 3], [null, 'asks', 'free'])` lights 1, 2, 3.
 */
export async function diagramOn(cue: SceneCue, page: Page, name: string, steps: [number, number?], words: (Cue | null)[] = []) {
  const [first, last = first] = steps;
  await page.evaluate((n) => window.ide.sequence(n), name);
  for (let step = first, i = 0; step <= last; step++, i++) {
    if (words[i]) await cue.at(words[i]!);
    else if (i > 0) await page.waitForTimeout(1_200);
    await page.evaluate((k) => window.ide.sequenceStep(k), step);
  }
  await cue.end();
}

/**
 * A map scene (storyboard kind "map"): the system map (map.js), driven on the narrator's words. Use the
 * same plan as the scene's storyboard `map`:
 * - reveal: groups of node ids, each brought in on its word (a group with no word comes in at once);
 * - overview: every node and link at once, still (the high-level design);
 * - steps: [first, last] of the map's steps, each played on its word in `words`, else right after the one
 *   before (a step takes about 1.3 s: the link draws, then the message travels);
 * - replay: the whole journey again, quickly (the recap).
 * The map stays up for the next map scene; opening a file or a title hides it.
 *   mapOn(await sync.say('B1-01'), page, 'refund', { reveal: [[['agent', 'shop'], 'shop'], [['api', 'db'], 'orders']] })
 *   mapOn(await sync.say('B1-02'), page, 'refund', { steps: [2, 3], words: ['sends', 'saves'] })
 */
export async function mapOn(
  cue: SceneCue,
  page: Page,
  name: string,
  plan: { reveal?: [string[], Cue | null][]; overview?: boolean; steps?: [number, number?]; words?: (Cue | null)[]; replay?: boolean; ms?: number } = {},
) {
  await page.evaluate((n) => window.ide.map(n), name);
  for (const [ids, word] of plan.reveal ?? []) {
    if (word) await cue.at(word);
    await page.evaluate((list) => window.ide.mapReveal(list), ids);
  }
  if (plan.overview) await page.evaluate(() => window.ide.mapOverview());
  if (plan.steps) {
    const [first, last = first] = plan.steps;
    for (let step = first, i = 0; step <= last; step++, i++) {
      const word = plan.words?.[i];
      if (word) await cue.at(word);
      await page.evaluate(({ k, ms }) => window.ide.mapStep(k, ms), { k: step, ms: plan.ms ?? 900 });
    }
  }
  if (plan.replay) await page.evaluate(() => window.ide.mapReplay());
  await cue.end();
}

/** Zooms into one node of the map on screen (on `word` when given), right before its code opens. */
export async function zoomInto(page: Page, node: string, cue?: SceneCue, word?: Cue) {
  if (cue && word) await cue.at(word);
  await page.evaluate((id) => window.ide.mapZoom(id), node);
}

/** "You are here": the map, small, in the corner of the code, with `node` lit. Call it after opening the file. */
export const locate = (page: Page, map: string, node: string) =>
  page.evaluate(({ map, node }) => window.ide.locate(map, node), { map, node });

export const hideLocator = (page: Page) => page.evaluate(() => window.ide.hideLocator());

/** `explain()` for a scene started with sync.say(): `explainOn(await sync.say('B2-02'), page, [[16, 18]], note)`. */
export async function explainOn(cue: SceneCue, page: Page, ranges: Ranges, note?: string) {
  await focus(page, ranges, note);
  await cue.end();
}

/** A narrated folder walk, so a long trip through the explorer is never silent. */
export async function walk(page: Page, cursor: Cursor, narration: Narration, scene: string, repo: string, path: string) {
  if (patchSkips(scene)) {
    await clickThrough(page, cursor, repo, path);
    return cursor.hide();
  }
  narration.mark(scene);
  await clickThrough(page, cursor, repo, path);
  await cursor.hide();
  await page.waitForTimeout(narration.durationFor(scene, PAUSE_AFTER_WALK));
}

/** The same walk, with each folder clicked on its spoken name: `walkOn(page, cursor, await sync.say('B2-01'), 'api', path)`. */
export async function walkOn(page: Page, cursor: Cursor, cue: SceneCue, repo: string, path: string) {
  await clickThrough(page, cursor, repo, path, cue);
  await cursor.hide();  // an idle pointer over the code distracts
  await cue.end(PAUSE_AFTER_WALK);
}

/**
 * A terminal scene (storyboard kind "terminal"): the panel opens, the scene's command is typed (on `word`
 * when given, else at once) and its recorded output is printed, with the storyboard's `marks` lit.
 * `terminalOn(await sync.say('B1-02'), page, 'B1-02', 'run')`. The panel stays open for the next scene;
 * `terminalHide(page)` before a scene that needs the whole editor.
 */
export async function terminalOn(cue: SceneCue, page: Page, scene: string, word?: Cue) {
  if (word) await cue.at(word, { lead: 250 });
  await page.evaluate((id) => window.ide.terminalRun(id), scene);
  await cue.end();
}

export const terminalHide = (page: Page) => page.evaluate(() => window.ide.terminalHide());

/** Empties the terminal, for a new chapter: old commands would push the new one out of view. */
export const terminalClear = (page: Page) => page.evaluate(() => window.ide.terminalClear());

/** Clears the highlight and the note, before a scene that should not show the last one. */
export const unfocus = (page: Page) => page.evaluate(() => window.ide.unfocus());
