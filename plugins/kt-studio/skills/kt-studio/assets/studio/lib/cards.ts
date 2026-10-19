// The intro and the outro: a full screen card laid over whatever is on screen (the app's first screen
// in Part A, the code tour in Part B), so the video opens and closes the same way in both parts. The
// card's parts come in one after another with the voice, then the intro fades away to show the screen
// behind it; the outro stays to the end.
//
// The data comes from the storyboard (`intro`, `outro`) through make_scenes.py (3-scripts/cards.json),
// staged next to the demo as demos/<run-id>-cards.json:
//   const cards = loadCards(__filename);
//   await cardOn(await sync.say('A1-01'), page, 'intro', cards);
//   await cardOn(await sync.say('B4-03'), page, 'outro', cards, ['remember', 'tests', 'questions']);
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import type { Page } from '@playwright/test';
import type { Cue, SceneCue } from './sync';

export type Intro = {
  title: string; tagline?: string; learn?: string[]; builtBy?: string[]; audience?: string;
  code?: string; length?: string; agenda?: string[];
};
export type Outro = {
  title?: string; remember?: string[]; next?: { label: string; detail?: string }[]; ask?: string; builtBy?: string[];
};
export type Cards = { intro?: Intro; outro?: Outro };

/** The cards staged for this demo: `loadCards(__filename)` in a demo script. */
export function loadCards(demoFile: string): Cards {
  const id = path.basename(demoFile).replace(/-(ui|code)(-patch)?\.demo\.ts$/, '');
  const file = path.join(path.dirname(demoFile), `${id}-cards.json`);
  return existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : {};
}

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const names = (list?: string[]) => (list ?? []).filter((n) => n && n !== 'none');

const STYLE = `
:host { all: initial; }
.wrap { position: fixed; inset: 0; background: radial-gradient(circle at 18% 12%, #23262d 0%, #17181b 55%, #111214 100%);
  font-family: -apple-system, "SF Pro Display", "Segoe UI", Arial, sans-serif; color: #e8e8e8; overflow: hidden; }
.stage { position: absolute; left: 50%; top: 50%; width: 1920px; height: 1080px; transform-origin: center; }
[data-b] { opacity: 0; }
.eyebrow { position: absolute; left: 150px; top: 120px; font: 700 22px/1 inherit; letter-spacing: 4px; color: #ffc400; }
.title { position: absolute; left: 150px; top: 170px; width: 1620px; font-weight: 750; line-height: 1.04; color: #fff; }
.title::before { content: ''; position: absolute; left: -40px; top: 12px; bottom: 12px; width: 8px; border-radius: 4px; background: #ffc400; }
.tagline { position: absolute; left: 150px; top: 330px; width: 1250px; font-size: 34px; line-height: 1.35; color: #b8bcc4; }
.col { position: absolute; top: 500px; }
.col.left { left: 150px; width: 900px; } .col.right { left: 1150px; width: 620px; }
.head { font: 700 20px/1 inherit; letter-spacing: 3px; color: #8a8f99; margin-bottom: 26px; }
ol { list-style: none; margin: 0; padding: 0; counter-reset: n; }
li { counter-increment: n; position: relative; padding-left: 64px; margin-bottom: 24px; font-size: 32px; line-height: 1.3; }
li::before { content: counter(n); position: absolute; left: 0; top: -2px; width: 42px; height: 42px; border-radius: 50%;
  background: #2d3038; color: #ffc400; font: 700 22px/42px inherit; text-align: center; }
.agenda li { font-size: 25px; margin-bottom: 14px; padding-left: 50px; color: #cfd2d8; }
.agenda li::before { width: 32px; height: 32px; font-size: 17px; line-height: 32px; top: 0; }
.length { margin-top: 18px; font-size: 22px; color: #8a8f99; }
.foot { position: absolute; left: 150px; right: 150px; bottom: 96px; display: flex; gap: 56px; align-items: baseline;
  border-top: 1px solid #30333b; padding-top: 30px; font-size: 24px; color: #9aa0aa; }
.foot b { color: #e8e8e8; font-weight: 600; }
.mono { font-family: Menlo, "SF Mono", Consolas, monospace; font-size: 21px; color: #9aa0aa; }
.next li { font-size: 28px; }
.next .detail { display: block; margin-top: 6px; font-family: Menlo, "SF Mono", Consolas, monospace; font-size: 21px; color: #9fd3c7; }
.remember li { font-size: 36px; margin-bottom: 30px; }
.ask { font-size: 30px; color: #e8e8e8; } .ask span { color: #ffc400; font-weight: 700; }
`;

function introHtml(c: Intro): string {
  const size = c.title.length > 34 ? 72 : 92;
  const who = names(c.builtBy);
  const blocks = [
    `<div class="eyebrow" data-b>KNOWLEDGE TRANSFER${c.audience ? ` · ${esc(c.audience.toUpperCase())}` : ''}</div>
     <div class="title" data-b style="font-size:${size}px">${esc(c.title)}</div>`,
    c.tagline ? `<div class="tagline" data-b>${esc(c.tagline)}</div>` : '',
    c.learn?.length ? `<div class="col left" data-b><div class="head">YOU WILL LEARN</div><ol>${c.learn.map((l) => `<li>${esc(l)}</li>`).join('')}</ol></div>` : '',
    // Seven chapters fit above the footer; more become "and N more".
    c.agenda?.length ? `<div class="col right agenda" data-b><div class="head">IN THIS VIDEO</div><ol>${c.agenda.slice(0, 7).map((a) => `<li>${esc(a)}</li>`).join('')}</ol>${c.agenda.length > 7 ? `<div class="length">and ${c.agenda.length - 7} more</div>` : ''}${c.length ? `<div class="length">${esc(c.length)}</div>` : ''}</div>` : '',
    who.length || c.code ? `<div class="foot" data-b>${who.length ? `<div>Built by <b>${esc(who.join(', '))}</b></div>` : ''}${c.code ? `<div class="mono">${esc(c.code)}</div>` : ''}</div>` : '',
  ];
  return blocks.filter(Boolean).join('');
}

function outroHtml(c: Outro): string {
  const who = names(c.builtBy);
  const blocks = [
    `<div class="eyebrow" data-b>WRAP-UP</div><div class="title" data-b style="font-size:80px">${esc(c.title ?? 'Three things to remember')}</div>`,
    c.remember?.length ? `<div class="col left remember" data-b style="top:330px"><ol>${c.remember.map((r) => `<li>${esc(r)}</li>`).join('')}</ol></div>` : '',
    c.next?.length ? `<div class="col right next" data-b style="top:330px"><div class="head">NEXT STEPS</div><ol>${c.next.map((n) => `<li>${esc(n.label)}${n.detail ? `<span class="detail">${esc(n.detail)}</span>` : ''}</li>`).join('')}</ol></div>` : '',
    c.ask || who.length ? `<div class="foot" data-b>${c.ask && c.ask !== 'none' ? `<div class="ask">Questions? <span>${esc(c.ask)}</span></div>` : ''}${who.length ? `<div>Built by <b>${esc(who.join(', '))}</b></div>` : ''}</div>` : '',
  ];
  return blocks.filter(Boolean).join('');
}

/** The card's HTML, also used by tests and by a look at it in a browser. */
export function cardHtml(kind: 'intro' | 'outro', cards: Cards): string {
  const data = cards[kind];
  if (!data) throw new Error(`No ${kind} in the cards (the storyboard's "${kind}", written by make_scenes.py)`);
  return kind === 'intro' ? introHtml(data as Intro) : outroHtml(data as Outro);
}

/**
 * An intro or outro scene. The card's blocks come in one by one: the eyebrow and title at once, then each
 * next block on its word in `words` (one per block after the title: tagline, learn, agenda, footer for the
 * intro; remember, next steps, footer for the outro), else spread over the first part of the line.
 * The intro fades away at the end of its line, showing the screen behind it; the outro stays.
 */
export async function cardOn(cue: SceneCue, page: Page, kind: 'intro' | 'outro', cards: Cards, words: (Cue | null)[] = []) {
  const html = cardHtml(kind, cards);
  const count = await page.evaluate(({ html, style }) => {
    document.getElementById('kt-card')?.remove();
    const host = document.createElement('div');
    host.id = 'kt-card';
    host.style.cssText = 'position:fixed;inset:0;z-index:2147483646;';
    const root = host.attachShadow({ mode: 'open' });
    root.innerHTML = `<style>${style}</style><div class="wrap"><div class="stage">${html}</div></div>`;
    const stage = root.querySelector('.stage') as HTMLElement;
    const fit = () => { stage.style.transform = `translate(-50%, -50%) scale(${Math.min(innerWidth / 1920, innerHeight / 1080)})`; };
    fit();
    document.documentElement.appendChild(host);
    return root.querySelectorAll('[data-b]').length;
  }, { html, style: STYLE });

  const reveal = (i: number) => page.evaluate(async (n) => {
    const el = document.getElementById('kt-card')?.shadowRoot?.querySelectorAll('[data-b]')[n] as HTMLElement | undefined;
    if (!el) return;
    await el.animate([{ opacity: 0, transform: 'translateY(18px)' }, { opacity: 1, transform: 'translateY(0)' }],
      { duration: 480, easing: 'cubic-bezier(0, 0, .2, 1)', fill: 'forwards' }).finished;
  }, i);

  await Promise.all([reveal(0), reveal(1)]);  // the eyebrow and the title together
  const rest = count - 2;
  const gap = Math.max(500, Math.min(1400, (cue.left() * 0.55) / Math.max(1, rest)));
  for (let i = 0; i < rest; i++) {
    const word = words[i];
    if (word) await cue.at(word);
    else await page.waitForTimeout(gap);
    await reveal(i + 2);
  }
  await cue.end();
  if (kind === 'intro') {
    await page.evaluate(async () => {
      const host = document.getElementById('kt-card');
      if (!host) return;
      await host.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 600, easing: 'ease-in', fill: 'forwards' }).finished;
      host.remove();
    });
  }
}
