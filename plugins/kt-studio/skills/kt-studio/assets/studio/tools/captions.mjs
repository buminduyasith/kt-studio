// Subtitles that follow the voice phrase by phrase, instead of one block per scene that appears before
// the voice and stays after it. Run after `argo pipeline`, inside the runtime. Rewrites the .srt and .vtt.
//
// Usage: node tools/captions.mjs <demo-name>
// Reads demos/<demo>.scenes.json (text, and caption when the spelling on screen differs from the spoken
// text), demos/<demo>.beats.json (tools/beats.mjs) and .argo/<demo>/scene-report.json (where each voice
// line landed in the final video).
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const demo = process.argv[2];
if (!demo) {
  console.error('usage: node tools/captions.mjs <demo-name>');
  process.exit(1);
}
const MAX_CHARS = 84;      // two lines of 42
const LINE = 42;
const MIN_SHOW_S = 0.9;

const scenes = JSON.parse(readFileSync(path.join('demos', `${demo}.scenes.json`), 'utf8'));
const beats = JSON.parse(readFileSync(path.join('demos', `${demo}.beats.json`), 'utf8'));
const report = JSON.parse(readFileSync(path.join('.argo', demo, 'scene-report.json'), 'utf8'));
const placed = Object.fromEntries(report.scenes.map((s) => [s.scene, s.startMs / 1000]));

const phrasesOf = (words) => {
  const out = [[]];
  words.forEach((w, i) => {
    out.at(-1).push(w);
    if (/[.,;:!?]["')\]]*$/.test(typeof w === 'string' ? w : w.text) && i < words.length - 1) out.push([]);
  });
  return out;
};
const endsSentence = (text) => /[.!?]["')\]]*$/.test(text);

/** Phrases of the on-screen text with times taken from the matching spoken phrases. */
function timedPhrases(entry) {
  const b = beats[entry.scene];
  const at = placed[entry.scene];
  if (!b || at === undefined) return [];
  const spoken = phrasesOf(b.words);
  const shown = phrasesOf((entry.caption ?? entry.text).split(/\s+/).filter(Boolean));
  if (spoken.length === shown.length) {
    return shown.map((words, i) => ({ text: words.join(' '), start: at + spoken[i][0].start, end: at + spoken[i].at(-1).end }));
  }
  // Different phrase breaks (an unusual pronounce entry): one cue per scene over the whole voice line.
  return [{ text: (entry.caption ?? entry.text), start: at + b.words[0].start, end: at + b.words.at(-1).end }];
}

/** Splits text that is too long for two lines at word boundaries, sharing the time by length. */
function fit(phrase) {
  if (phrase.text.length <= MAX_CHARS) return [phrase];
  const words = phrase.text.split(' ');
  const chunks = [[]];
  for (const w of words) {
    if ([...chunks.at(-1), w].join(' ').length > MAX_CHARS) chunks.push([]);
    chunks.at(-1).push(w);
  }
  const total = phrase.text.length;
  let t = phrase.start;
  return chunks.map((c) => {
    const text = c.join(' ');
    const span = ((text.length + 1) / total) * (phrase.end - phrase.start);
    const piece = { text, start: t, end: t + span };
    t += span;
    return piece;
  });
}

const cues = [];
for (const entry of scenes) {
  if (typeof entry.text !== 'string' || !entry.text.trim()) continue;
  let cue = null;
  for (const phrase of timedPhrases(entry).flatMap(fit)) {
    // Join phrases into one cue while it still fits on two lines and does not cross a sentence end.
    if (cue && !endsSentence(cue.text) && `${cue.text} ${phrase.text}`.length <= MAX_CHARS) {
      cue.text += ` ${phrase.text}`;
      cue.end = phrase.end;
    } else {
      cue = { ...phrase };
      cues.push(cue);
    }
  }
}
cues.sort((a, b) => a.start - b.start);
cues.forEach((cue, i) => {
  const next = cues[i + 1]?.start ?? Infinity;
  cue.start = Math.max(0, cue.start - 0.05);
  cue.end = Math.min(Math.max(cue.end + 0.25, cue.start + MIN_SHOW_S), next - 0.04);
});

const lines = (text) => {
  if (text.length <= LINE) return text;
  const mid = text.length / 2;
  let best = -1;
  for (let i = text.indexOf(' '); i !== -1; i = text.indexOf(' ', i + 1)) if (best < 0 || Math.abs(i - mid) < Math.abs(best - mid)) best = i;
  return best < 0 ? text : `${text.slice(0, best)}\n${text.slice(best + 1)}`;
};
const stamp = (s, sep) => {
  const ms = Math.round(s * 1000);
  const p = (n, w = 2) => String(n).padStart(w, '0');
  return `${p(Math.floor(ms / 3_600_000))}:${p(Math.floor(ms / 60_000) % 60)}:${p(Math.floor(ms / 1000) % 60)}${sep}${p(ms % 1000, 3)}`;
};
const srt = cues.map((c, i) => `${i + 1}\n${stamp(c.start, ',')} --> ${stamp(c.end, ',')}\n${lines(c.text)}\n`).join('\n');
const vtt = `WEBVTT\n\n${cues.map((c) => `${stamp(c.start, '.')} --> ${stamp(c.end, '.')}\n${lines(c.text)}`).join('\n\n')}\n`;
writeFileSync(path.join('videos', `${demo}.srt`), srt);
writeFileSync(path.join('videos', `${demo}.vtt`), vtt);
console.log(`captions: ${cues.length} cues for ${scenes.length} scenes -> videos/${demo}.srt, .vtt`);
