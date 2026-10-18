# Quality: pace, sync and checks

## Pace a person can follow

| Rule | Value | Where |
|---|---|---|
| Voice speed | 0.9 | `KT_SPEED`, `argo.config.mjs` |
| Pause after each point | 1.5 s of real silence, from the last spoken sound | `PAUSE_AFTER_POINT` in `lib/pacing.ts`, `s.end()` in `lib/sync.ts` |
| Mouse travel | 700 ms, dwell 200 ms, after 300 ms (`HOP`: 450 / 120 / 120) | `CALM`, `HOP` |
| Typing | 75 ms per character (quick open: 55) | `TYPE_MS`, `QUICK_OPEN_MS` |
| Code scroll | 1.2 s | `ide.js` focus |
| Note | 0.5 s after the highlight lands | `ide.js` focus |
| Scene changes | no fade, no dip to black, no speed-up | `argo.config.mjs` has no `transition` and no `speedRamp` |
| Silence between lines | under about 4 s; narrate long walks and jumps | demo scripts, `check_sync.py` warns |

Do not add `export.transition` or `export.speedRamp` back. A fade-through-black transition made every
scene start dip to black (measured brightness 51 → 16 at 12 scene starts), which viewers saw as
blinking. A 1.8x speed ramp made navigation too fast to follow.

## Voice and picture in sync

Measured on a lab app with a probe that flips a corner square at every `mark()`, and a log of every click:

| What | Measured | Meaning |
|---|---|---|
| Recorder: mark → picture | +1 to +67 ms, no drift over a take | Argo's capture and voice placement are accurate. Never shift the audio by hand |
| Voice clip lead-in | 0.34 s of silence at the start of every Kokoro clip | The voice starts just after the screen changes. Good |
| Clicks vs their words, actions straight after the mark (old pattern) | 0.2 to 2.9 s late, median 1.7 s | This is the drift viewers notice |
| Argo cursor, `durationMs: 700` | really about 1.4 s (a round trip per path step) | `lib/sync.ts` measures this and corrects it |
| Clicks vs their words with `lib/sync.ts` | +0.07 to +0.21 s on named buttons (aim +0.12 s); 41 of 41 cues on their word in the final takes of two lab apps | The fix |
| Joining parts with `finish.py` | each part's voice lands within 5 ms of where it was alone | Safe to deliver one file |
| Captions | one cue per scene, shown 0.34 s before the voice | `tools/captions.mjs` makes phrase cues timed to the voice |

The rules that keep them together:

1. **Actions wait for their words** (`lib/sync.ts`): `s.click(target, 'Send')` lands the click as
   "Send" is spoken. Word times come from `tools/beats.mjs`: by default from the clip itself (sentence
   ends matched to the longest pauses, commas to nearby ones; against Whisper on 509 words, median
   0.12 s, 90% within 0.3 s).
   For closer times, set `KT_TRANSCRIBE=1` for `beats.mjs` and the pipeline: Whisper runs offline
   (its model, about 150 MB, is downloaded by `/kt-studio:init` when `voice.word_timing` is `whisper`), and its times are laid onto the script's own words, so
   a misheard word never breaks a cue. Cue words need a language written with spaces between words.
2. **Navigation the line does not mention happens before the line.** A line about a server result
   starts after the result is on screen (`sync.say()` also waits for requests to finish).
3. **A line must have room for its actions**: about 1 s per click, 75 ms per typed character. When it
   does not, change the cue word, use `HOP`, or split the line in the storyboard.

## Checks before delivering

```bash
python3 <skill>/scripts/check_video.py <run>/5-videos/<feature>-ui.mp4 \
  --report <run>/4-checks/ui-scene-report.json --sheet <run>/4-checks/ui-sheet.png --marks <run>/4-checks/ui-timing.json
python3 <skill>/scripts/check_sync.py <run>/4-checks ui
```

- `check_video.py` must print `PASS: no blinks` (0 dark frames, 0 sudden jumps) and `PASS: picture
  keeps time with the voice`. The second compares where the picture changes (a file opens, a click
  lands) with the scene marks and click words, and fails when that delay grows through the video by
  more than 0.6 s. The recorder stamps each frame when it arrives; on a busy computer (another take,
  a build, a voice run) frames queue and the picture slid 2 to 5 s behind the voice in a test, while
  `check_sync.py` still passed. Record with nothing else running; preflight warns when the computer is busy.
- `check_sync.py` must print `PASS: voice and picture in sync`: no voice line starts more than 0.25 s
  after its mark, and every cue hits its word within 0.4 s. Read its warnings about silences.
- Look at the contact sheet: every scene shows the screen the storyboard promised, with the
  highlight and note visible, no login page, no spinner, no modal, no secret on screen.
- Argo ends a take with `Overflow: 12.0s (video padded)`. That is not an error: the last line ran past
  the last new frame (the page stopped changing), so the final frame is held while the voice finishes.
  `check_sync.py` reports the same as "the last frame is held".
- The last seconds may hold the final frame while the outro voice finishes. That is expected: the
  capture gets no new frames once the page stops changing, and Argo holds the last one.
