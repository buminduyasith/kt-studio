# Recording UI scenes (Part A)

**Contents:** Why actions wait for words · Script pattern · Run

Tools: Argo (`@argo-video/cli`) runs a Playwright script, records 1080p with a scripted cursor, places
each voice clip at its scene mark and exports MP4 + chapters + subtitles. Kokoro makes the voice offline.

Files, written in `<run>/3-scripts/` and copied into the runtime by `scripts/stage.sh`:

- `ui.scenes.json`: made from the storyboard by `scripts/make_scenes.py <run>`: one entry per scene,
  `{ "scene": "A1-03", "text": "<spoken, pronounce map applied>", "caption": "<on-screen spelling>" }`
  (`caption` only when it differs). Optional `overlay`, added by hand and kept on regeneration:
  `{ "type": "lower-third", "text": "...", "placement": "bottom-center", "motion": "fade-in" }` or
  `headline-card` / `callout`.
- `ui.demo.ts`: the script. Scene names must match the storyboard ids. Import helpers as `../lib/...`
  (valid inside the runtime, where the staged copy runs).

## Why actions wait for words

The voice of a scene starts at its mark and runs at its own pace. Actions inside the scene run at the
script's pace: cursor travel, typing, and server waits. Measured on a lab take written the old way
(actions straight after the mark), clicks landed 0.2 to 2.9 s after the narrator said them (median 1.7 s),
while the recorder itself put every mark within 0.07 s. So the drift viewers notice comes from the
script, not the recorder. `lib/sync.ts` fixes it: each action waits for the word that describes it.
Word times come from `demos/<demo>.beats.json`, made by `tools/beats.mjs` from the voice clips.

## Script pattern

```ts
import path from 'node:path';
import { test, zoomTo, createHumanCursor } from '@argo-video/cli';
import { CALM } from '../lib/pacing';
import { createSync, HOP } from '../lib/sync';
import { cardOn, loadCards } from '../lib/cards';

const DRY = process.env.KT_DRY === '1';          // rehearsal: stop before every write
const NAME = process.env.KT_NAME ?? 'kt-video';   // unique names for things the recording creates

// The staged file is named <run-id>-ui.demo.ts; the test title must match it for `argo pipeline <run-id>-ui`.
test(path.basename(__filename, '.demo.ts'), async ({ page, narration }) => {
  test.setTimeout(30 * 60_000);                  // Argo writes its own Playwright config: allow far more than the take
  page.setDefaultTimeout(45_000);                // a missing element must fail fast, not hang
  await page.goto('/orders/1042');               // setup before recording: navigate, wait, prepare
  await narration.startRecording(page);
  const cursor = await createHumanCursor(page, { seed: 'refunds', size: 28, start: { x: 0.2, y: 0.9 } });
  const sync = createSync(page, narration, cursor);

  // "To refund this order, click Refund. A drawer opens with the amount."
  let s = await sync.say('A1-01');               // waits until no request is in flight, then the voice starts
  await s.click(page.getByRole('button', { name: 'Refund' }), 'Refund');
  await s.end();                                 // the rest of the line, then the 1.5 s pause

  // "Type the amount, twenty five euros, and pick a reason."
  s = await sync.say('A1-02');
  await s.type(page.getByLabel('Amount'), '25.00', 'twenty five');
  await s.click(page.getByLabel('Reason'), 'reason', HOP);
  await s.end();

  if (DRY) return;                               // nothing below this line runs in a rehearsal
  // "Click Confirm refund. The server checks the order first."
  s = await sync.say('A1-03');
  await s.click(page.getByRole('button', { name: 'Confirm refund' }), 'Confirm', HOP);
  await s.end();

  await page.getByText('Refund created').waitFor();   // the result is the NEXT line's subject: wait first
  s = await sync.say('A1-04');
  await s.end();
});
```

| Call | Does |
|---|---|
| `sync.say(id, { settle? })` | Waits until no fetch/XHR has been in flight for 0.4 s (at most 4 s), marks the scene, returns its cue `s`. Steady polling is recognised and ignored; ignore more with `createSync(page, narration, cursor, { ignore: /analytics/ })` |
| `s.click(target, word, move = CALM)` | Starts the cursor so the click lands about 0.1 s after `word` starts |
| `s.type(field, text, word, msPerChar = 75)` | Clicks the field on `word`, then types |
| `s.move(target, word)` | The cursor arrives on `word` (pointing at something without clicking) |
| `s.choose(select, option, word, { pickOn })` | A native `<select>`: draws a look-alike list (the real one never shows on video), glides to the option and picks it on `word`. With `pickOn`, the list opens on `word` and stays open until `pickOn`, while the voice talks about it |
| `s.confirm(button, word, okWord)` | A button that asks with the browser's `confirm()`: clicks on `word`, shows the question as a look-alike, clicks OK on `okWord` |
| `s.scroll(target, word)` | Scrolls a target into view smoothly on `word` (clicks and moves already scroll smoothly by themselves) |
| `s.has(word)` | True when the word is in this scene's line (for helpers that cue only when they can) |
| `sync.settle()` | Waits for the page's requests to finish, without starting a line |
| `s.at(word, { lead })` | Waits until `lead` ms before `word` (`{ word, nth: 2 }` for the second time it is said). For anything else |
| `s.end(pause?)` | Waits for the rest of the voice line plus the pause (ms, or `PAUSE_AFTER_POINT`; 1.5 s by default) |
| `s.left(pause?)` | How long `s.end()` would wait, in ms: the length to give `showOverlay()` |
| `sync.click(target)` / `sync.move(target)` / `sync.choose(select, option)` | The same calibrated pointer with no word, for housekeeping before a line |
| `HOP` | A short cursor move (0.45 s) for the next field or button nearby |

Rules:

- One `sync.say(id)` per storyboard scene, in storyboard order, with the same id.
- Every visible action inside a scene waits for its word. Pick the word that names the thing: the
  button label, the field, the value being typed. Spell it as in the `text` of `ui.scenes.json` (the
  spoken form, for example `'L R'` for LR-1044).
- Navigation and housekeeping the line does not talk about (closing a drawer, opening a page) happen
  **before** `say()`, with `sync.click(target)`. The voice starts on the right screen.
- Use the sync pointer for every click, not `cursor.click()`: Argo's own cursor takes about twice the
  `durationMs` it is given (see `references/quality.md`).
- Never let a line talk about a server result it has not got yet. Wait for the result before the
  `say()` of the scene that describes it. The line that triggers the wait can cover it ("The server
  checks the order first"). Wait for something that stays (the new row, the status), never a toast:
  a toast can come and go while the line and its pause play.
- Budget: a click needs about 1 s of voice (travel and dwell), `s.choose()` about 1.7 s before its pick
  word, typing 75 ms per character. Leave 0.5 s more than that: a rehearsal that just fits can miss in
  the real take, when the computer is busier. When two
  cue words are closer than that, the second action is late. Use `HOP`, type faster, or cue a later word.
  `check_sync.py` fails every cue that misses its word by more than 0.4 s; run it on a rehearsal too
  (`check_sync.py <rt>/.argo/<run-id>-ui`), before the real take.
- `showOverlay(page, scene, ms)` only for scenes that have an `overlay` in the scenes file. Use
  `s.left()` for `ms`, after `say()`. It waits for its whole duration: in a scene that also has
  actions, start it without waiting (`void showOverlay(page, 'A1-05', s.left())`), then do the actions.
  `make_scenes.py` turns a UI scene's storyboard `note` into a lower-third overlay.
- The `intro` scene (the first of the video) and the `outro` scene (the last) are full screen cards
  laid over whatever is on screen (`lib/cards.ts`, data from the storyboard through `3-scripts/cards.json`).
  Go to the app's first screen before `narration.startRecording`, then:
  `const cards = loadCards(__filename);` and `await cardOn(await sync.say('A1-01'), page, 'intro', cards);`.
  The intro fades into the screen behind it at the end of its line. For the outro (when Part A is the
  last part): `await cardOn(await sync.say('A3-05'), page, 'outro', cards);`; it stays. The card's blocks
  come in one by one; pass words to time them: `cardOn(s, page, 'intro', cards, ['learn', 'chapters'])`.
- A `title` scene in Part A (a chapter opener) is a card over the app's first
  screen: `make_scenes.py` gives it a `headline-card` overlay, and the script shows it with
  `s = await sync.say('A1-01'); await showOverlay(page, 'A1-01', s.left());` (`s.left()` is how long the
  scene still runs, from the word timings; `narration.durationFor()` is a fixed 5 s in a rehearsal).
  Diagrams and code belong in Part B.
- Use `getByRole` / `getByLabel` / `getByText` locators. Find them during the screenshot pass. For a
  `<select>` inside its `<label>`, use the id or an exact name: the label's name includes the options.
- Native dialogs (`alert`, `confirm`, `prompt`, "leave this page?") never show on video. `createSync()`
  answers them; for a `confirm()` the viewer should see, use `s.confirm(button, 'Check', 'confirm')`.
  Do not add your own `page.on('dialog')` handler next to it.
- A word said twice in one line: cue `{ word: 'Book', nth: 2 }` or a longer phrase.
- A full page load (a link to another page, `page.goto`) shows a blank page for a moment: do it
  before the line, then wait for an element of the new page; `sync.say()` also waits for its
  requests. Moving between apps (the shop, then the admin site) reloads everything: when both needed a
  login, merge their sessions (`login.sh merge <out> <run-id> shop admin`; `take.sh` then uses
  `.auth/kt-<run-id>.json`), keep each app's scenes together, and cut the loading between them with `finish.py --cut` (see `SKILL.md` step 9).
- Code editors (Monaco): use `lib/monaco.ts` (`installMonacoHelpers(page)`, then `window.__kt.prepare()`,
  `typeIn(text, msPerLine)`, `highlight(ranges, class)`, and `explainLines(page, narration, id, ranges)`).
  Never type code with the keyboard on camera. `prepare()` empties the editor: in an app that autosaves,
  that is a write, so list it for gate 2.
- Rehearsals write nothing: with `KT_DRY=1`, `createSync()` blocks requests that could change data
  (a GraphQL query still passes; allow more with `{ allowInRehearsal: /search/ }`) and the cue log lists them.
- Zoom: `zoomTo(page, selectorOrLocator, { narration, scale: 1.45, duration, fadeIn: 700, fadeOut: 700, holdMs })`.
  The zoom is applied after export. Overlays near the frame edges can be cropped by a zoom.
- Things the recording creates need new names each take (`KT_NAME`), because names are usually unique.

## Run

```bash
python3 <skill>/scripts/make_scenes.py <run>         # voice files from the approved storyboard
bash <skill>/scripts/stage.sh <out> <run>
cd <out>/runtime
export KT_BASE_URL=<app url> KT_VOICE=<voice> KT_SPEED=<speed>   # + KT_STATE=.auth/kt-<key>.json (or the project's own session file) when it logged in
npx argo tts generate demos/<run-id>-ui.scenes.json
node tools/beats.mjs <run-id>-ui                     # word times for the cues and the captions
KT_DRY=1 npx argo record <run-id>-ui                 # rehearsal, writes nothing
KT_NAME=<unique> npx argo pipeline <run-id>-ui       # real take (gate 2 first)
bash <skill>/scripts/collect.sh <out> <run>          # videos, captions and sync logs into the run
```

Run `beats.mjs` again whenever a voice line changes; the recorder stops with "beats are out of date"
otherwise. `argo record` alone uses 5 s per scene; real timing comes only from `argo pipeline`.
Runtime output: `videos/<run-id>-ui.mp4`, `.srt`, `.vtt`, `.argo/<run-id>-ui/scene-report.json`, `cues.jsonl`.
`collect.sh` rebuilds the captions phrase by phrase (`tools/captions.mjs`), copies the video to
`<run>/5-videos/<feature>-ui.*` and the reports to `<run>/4-checks/ui-*`.
