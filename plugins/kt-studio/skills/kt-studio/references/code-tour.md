# Recording the code tour (Part B)

**Contents:** 1. Tour data · 2. Page API (`window.ide`) · 3. Script pattern (helpers in `lib/ide-driver.ts` and `lib/sync.ts`) · 4. Run

A web page that looks like VS Code (`ide/`), filled with the real code at each repo's ref, driven
by a script in time with the voice. It never runs or changes code. It is a snapshot: rebuild it after
the code changes.

## 1. Tour data

`<run>/3-scripts/tour.json`:

```json
{
  "title": "Order Refunds",
  "workspace": "ACME",
  "repos": {
    "web": { "path": "../../../../web", "label": "Frontend", "ref": "origin/main" },
    "api": { "path": "../../../../api", "label": "Backend", "ref": "origin/develop" }
  },
  "files": [["web", "src/refunds/use-refund.ts"], ["api", "src/refunds/refund.service.ts"]]
}
```

Each repo's `ref` is the sha from the storyboard's `meta.sources` (SKILL.md step 5); add
`"branch": "main"` (the branch it came from) so the status bar shows a branch name, not the sha twice.
Repo paths: absolute paths are simplest. A relative path is resolved from the folder of `tour.json`
(`<run>/3-scripts/`), not from the project root.
`scripts/stage.sh` builds it into `<out>/runtime/tours/<run-id>/` (real code from git, VS Code colours),
with the storyboard's diagrams from `3-scripts/diagrams.json` (written by `make_scenes.py`).

The explorer shows every folder on the way to a tour file. Of the files, only tour files show; the
rest fold into one row `+ N more files`.

## 2. Page API (`window.ide`)

| Call | Does |
|---|---|
| `open(repo, path)` | Opens a tab, reveals the file in the explorer, collapses other repos, swaps the code instantly |
| `focus(ranges, note)` | Highlights line ranges, dims the rest, scrolls (1.2 s), shows the note 0.5 s later under the lines |
| `unfocus()` | Clears highlight, note and token link |
| `flow(journey, step)` | Top-right bar: a journey label (for example `PUSH`) and the repo labels with `step` lit; `'all'` lights all |
| `welcome(title, html)` | Title screen |
| `showPalette()` | Ctrl+P style quick open |
| `linkToken(line, token)` | Underlines one token for a "follow the call" jump |
| `tip(rowId, text)` / `clearTips()` | Small label next to an explorer row (`rowId` = `repo:path`, `repo:` for the root) |
| `terminalRun(sceneId)` / `terminalShow(cwd)` / `terminalHide()` / `terminalClear()` | A VS Code style terminal panel under the editor: types the scene's command and prints its recorded output (from `3-scripts/terminals.json`, written by `make_scenes.py`), lighting its `marks`. The code above stays visible |
| `sequence(name)` / `sequenceStep(first, last)` / `hideSequence()` | The storyboard's sequence diagram over the editor; lights steps, earlier ones stay, later ones hidden. Opening a file hides it |

Browse it by hand: `http://127.0.0.1:8765/ide.html?view`. When port 8765 is busy, serve on another
(`serve.sh start <dir> 8766`) and set `KT_TOUR_URL=http://127.0.0.1:8766/ide.html` for the code take.

## 3. Script pattern (helpers in `lib/ide-driver.ts` and `lib/sync.ts`)

```ts
import path from 'node:path';
import { test, createHumanCursor } from '@argo-video/cli';
import { openTour, flow, welcome, walkOn, quickOpen, quickOpenOn, follow, explain, focus, diagramOn } from '../lib/ide-driver';
import { createSync } from '../lib/sync';

test(path.basename(__filename, '.demo.ts'), async ({ page, narration }) => {
  test.setTimeout(30 * 60_000);                                  // far more than the take, or a long tour is cut off
  page.setDefaultTimeout(30_000);
  await openTour(page);
  await welcome(page, 'Order Refunds', 'Code tour · how a refund flows through two repos');
  await flow(page, '', 'all');
  await narration.startRecording(page);
  const cursor = await createHumanCursor(page, { seed: 'refunds-code', size: 26, start: { x: 0.5, y: 0.7 } });
  await cursor.hide();                                           // shown only while a walk or a jump moves it
  const sync = createSync(page, narration, cursor);

  let s = await sync.say('B1-01');                               // intro on the welcome screen
  await s.end();

  // The big picture: the storyboard's "refund" diagram, steps lit on their words.
  await diagramOn(await sync.say('B1-02'), page, 'refund', [1, 3], [null, 'server', 'provider']);

  // "In the web app, open src, then refunds." Each folder opens as its name is spoken.
  await flow(page, 'REFUND', 'web');
  await walkOn(page, cursor, await sync.say('B2-01'), 'web', 'src/refunds/use-refund.ts');
  await explain(page, narration, 'B2-02', [[40, 52]], 'Sends the order id and the amount. <b>Never the card.</b>');

  // "Checks the order..." starts with its subject: the file opens before the line.
  await flow(page, 'REFUND', 'api');
  await quickOpen(page, 'refund.service');
  await explain(page, narration, 'B2-03', [[18, 30]], 'Checks the order belongs to this shop.');

  s = await sync.say('B2-04');                                   // the voice describes the jump while it happens
  await follow(page, cursor, { line: 61, token: 'this.payments.refund' }, { repo: 'api', path: 'src/payments/client.ts', line: 12 });
  await focus(page, [[12, 25]], 'One call to the payment provider.');
  await s.end();

  // "The result is saved by one small repository." The file opens on "repository".
  s = await sync.say('B2-05');
  await quickOpenOn(page, s, 'refund.repository', 'repository');
  await focus(page, [[20, 31]], 'One insert, inside the same transaction.');
  await s.end();
});
```

| Helper | Does |
|---|---|
| `explain(page, narration, id, ranges, note)` | Marks the scene, highlights and scrolls at once, shows the note, waits for the voice and the pause |
| `explainOn(s, page, ranges, note)` | The same for a scene started with `sync.say()` (exact 1.5 s pause after the voice) |
| `walk(page, cursor, narration, id, repo, path)` | A narrated folder walk without word cues (marks the scene itself) |
| `quickOpen(page, query)` | Palette, types the name (55 ms per character), Enter. About 1 to 1.5 s, silent: use it before a line |
| `quickOpenOn(page, s, query, word)` | The same, timed so the file appears as `word` is spoken |
| `walkOn(page, cursor, s, repo, path)` | Opens each folder on the way; a folder named in the line is clicked on its name |
| `follow(page, cursor, from, to)` | Underlines a call, clicks it, lands on the target line in another file |
| `terminalOn(s, page, sceneId, word?)` | A `terminal` scene: types the command (on `word` when given) and prints the output, then waits for the voice. `terminalHide(page)` closes the panel |
| `terminalClear(page)` / `unfocus(page)` | Empty the terminal (at a new chapter, so old commands do not crowd the new one) / clear the highlight and note |
| `diagramOn(s, page, name, [first, last], words?)` | A `diagram` scene: shows the diagram and lights its steps `first` to `last` (the storyboard's `diagram.steps`) one by one, each on its word when given |

A `title` scene in Part B (the opening, a chapter opener, the recap) is the welcome screen:
`await welcome(page, 'Three things to remember', '1. ...<br>2. ...'); s = await sync.say('B3-01'); await s.end();`
(`welcome()` fades the code out first).

Rules:

- A line that starts with its subject ("Checks the order...") gets its file opened **before** the
  line: `quickOpen` then `explain`. A line that names the file a second or more in ("...one small
  client") opens it on that word: `quickOpenOn`. Word spelling as in the spoken `text`.
- Long folder walks use `walkOn()` with a voice line that names the folders that matter ("in the order
  service, open orders, then service"). Named folders are clicked on their words (a dashed name like
  `order-service` matches "order service"; a name said twice is matched in order); the folders the line
  does not name open at once, like VS Code's compact folders. So name two or three folders, not eight.
  Jumps start their voice line first.
- Keep the gap between two lines under about 4 s: the 1.5 s pause plus navigation. Two quick opens in
  a row, or a slow walk, make the tour feel stuck. `check_sync.py` warns about longer silences.
- One highlight and one note per scene. Two ranges more than 25 lines apart do not fit on one screen:
  split them into two scenes or keep one range.
- Notes say the idea in one line, with `<b>` and `<code>` only.
- Terminal scenes: the voice says what is run and what to look at in the answer ("The answer is a 409:
  the member owes too much"); put those words in `marks`. Open the file that explains the answer in the
  next scene: the terminal stays open under it, so the output and its code are on screen together.
  Close it (`terminalHide`) before a scene that needs the whole editor.
- Hide the cursor right after creating it. Walks and jumps show it while they move and hide it after;
  an idle pointer resting on the code pulls the eye away from the highlight.

## 4. Run

```bash
python3 <skill>/scripts/make_scenes.py <run>
bash <skill>/scripts/stage.sh <out> <run>
bash <skill>/scripts/serve.sh start <out>/runtime/tours/<run-id>
cd <out>/runtime && npx argo tts generate demos/<run-id>-code.scenes.json && node tools/beats.mjs <run-id>-code && npx argo pipeline <run-id>-code
bash <skill>/scripts/serve.sh stop <out>/runtime/tours/<run-id>
bash <skill>/scripts/collect.sh <out> <run>
```
