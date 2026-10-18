# Updating a delivered video

A video is delivered, then something changes: a reviewer wants one line said differently, a rule
changed in the code, a scene is missing, a step should go. Record only what changed and splice it into
the delivered video. The viewer must not see where: no fade to black, no jump in the screen, no change in
the voice's loudness.

Use it for: a changed or added scene, a removed scene, a scene whose code moved. Make a new video (a
new run) for a different feature. Record the whole part again when the change touches most of it
(`patch.py plan` says so above 60% of the scenes) or the app's look changed everywhere (a redesign).

## How a patch stays invisible

| What | How |
|---|---|
| Same screen on both sides of a join | The patch take replays every scene before the range fast (no voice, a quick pointer, the same clicks and files in the same order), so it reaches the state the delivered video had there. It records the range at normal pace |
| A join the eye never sees | Joins fall at the end of a scene: after its 1.5 s pause, before the next scene moves anything, in silence. `patch.py splice` compares the frames on both sides: a plain cut when they match, a 0.25 s dissolve when they differ a little, a failure when they differ a lot |
| Back into the old video | The range ends with one unchanged **bridge** scene, recorded again, so the second join also lands on a screen the old video already shows |
| The same voice | Unchanged lines reuse the delivered take's voice clips. The new stretch's loudness is matched to the delivered video |
| Everything else | Chapters, captions, scene marks, word timings and the cue log are rebuilt on the new time line, so the checks and the next update work as before |

## Steps

1. **Find the run.** The feature's newest run with videos, in `<out>/features/<feature-slug>/runs/`
   (`run.json` lists `versions`). Read the feature's `feature.yml` and the run's
   `run.json` `choices`: they hold the audience, what to show, the depth and the chosen flows, so ask
   none of it again (`references/questions.md`). `5-videos/storyboard.delivered.json`
   is the storyboard the videos follow. A video made before patching existed has none: name the changed
   scenes with `--changed` in step 3.
2. **Change the storyboard (gate 1).** Edit `storyboard.json` for what the user asked: change a line,
   add a scene (a new id; ids of other scenes stay), remove one. For "refresh it" or "the code changed",
   run `patch.py plan` first: it lists the code scenes whose cited lines read differently at the repo's
   current ref. Research those again (`references/research.md`) and update them; a new `meta.sources`
   sha and the tour's pinned sha follow. Build: changed scenes are marked **Changed in this update**.
   Review as usual (`references/review-loop.md`) and get an approval of the changes.
3. **Plan.**
   ```bash
   python3 <skill>/scripts/patch.py plan <run>
   ```
   It prints, per part, the changed scenes, the range to record (`first` to `last`, ending with the
   bridge), the recording time against a full take, and the next commands. Part A: when a changed scene
   writes or its actions changed, the range runs to the end of its chapter, because later screens may
   show the new data. `--until <scene>` records further when you know more depends on it.
4. **Scripts.** Change `3-scripts/<part>.demo.ts` for the changed scenes only (`references/ui-recording.md`,
   `references/code-tour.md`); every scene keeps its `sync.say(id)` in storyboard order. Then
   `make_scenes.py <run>`, and stage the patch take:
   ```bash
   bash <skill>/scripts/stage.sh <out> <run> --patch <ui|code> <first> <last>
   ```
5. **Voice, rehearsal, take.** A `ui` patch uses the apps saved in `run.json` `apps` (no question,
   unless one no longer answers); logins are never kept between runs, so when `login.sh probe <out> <key> <url>` says a
   page needs one, the person logs in again (the window, or the project's own way: `references/config.md`). Then as in
   `SKILL.md` steps 6 and 7, with the demo `<run-id>-<part>-patch`:
   `npx argo tts generate demos/<run-id>-<part>-patch.scenes.json` (only the changed lines are voiced),
   `node tools/beats.mjs <run-id>-<part>-patch`, a rehearsal (`KT_DRY=1 npx argo record ...`), then
   `check_sync.py <rt>/.argo/<run-id>-<part>-patch`. Gate 2: the fast part replays every write before the
   range for real, so list those writes too. "Before each take" applies. Then `npx argo pipeline
   <run-id>-<part>-patch` in the background. Do not run `collect.sh` for a patch take.
6. **Splice.**
   ```bash
   python3 <skill>/scripts/patch.py splice <run> <ui|code>
   ```
   It keeps the previous version in `5-videos/versions/v<N>/`, writes the new part video in its place,
   and prints how each join was made. A failed join means the patch take did not reach the delivered
   state: look at the fast part (a step the script skips when it runs fast, data that differs), or
   record a longer range (`plan --until`).
7. **Check.** `check_video.py` with `--marks` on the new part video (no blinks, and the picture keeps
   time with the voice across the joins), `check_sync.py` on the patch take's own log, and the contact
   sheet against the storyboard. Then `finish.py <run>` again when the parts are delivered as one file.
8. **Deliver.** A short table: what changed, which scenes were recorded, the old and new length, where
   the previous version is. Set `run.json` steps as in a normal run.

## Commands the user can give

| They say | Do |
|---|---|
| `/kt-studio:update <feature> "<change>"` | This file, for that change |
| `/kt-studio:update <feature>` | Refresh: `patch.py plan` lists code scenes that moved; propose the storyboard changes |
| `/kt-studio:make <feature> "<instructions>"` for a feature that already has videos | Ask: update the delivered video, or make a new one |
| "Say the fee in B4-05", "drop A1-08", "add a scene about the outbox after B3-09" | An update with that change |

## Limits

- One range per part. Two far-apart changes record everything between them; `plan` says when a full
  take is about as fast.
- A patch take is still real time for the range, and the fast part takes about 2 to 3 s per scene.
- After a code change, unchanged scenes keep showing the old sha in the status bar. When that matters,
  record the whole part again.
