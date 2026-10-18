// Word timings for every voice clip of one demo, so a script can act ON a spoken word and captions can
// follow the voice phrase by phrase. Run after `argo tts generate`, inside the runtime.
//
// Usage: node tools/beats.mjs <demo-name>          e.g. node tools/beats.mjs 2026-10-14-refunds-ui
// Writes demos/<demo-name>.beats.json:
//   { "<scene>": { "text", "clipMs", "speechMs": [start, end], "source", "words": [{ "text", "start", "end" }] } }
//   start/end are seconds from the start of the clip (the clip starts at the scene's voice placement).
//
// Source of the times:
//   whisper   a Whisper transcript cached next to the clip. With KT_TRANSCRIBE=1 this tool makes it
//             (offline, a one-time model download of about 150 MB) and argo pipeline reuses it.
//   estimate  from the clip itself: sentence ends take the longest pauses in the audio, commas a pause
//             near where they fall, and each phrase is shared out over its words by length (the last word
//             gets more). Against Whisper on 509 words: median 0.12 s, 90% within 0.3 s, worst 0.7 s.
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const demo = process.argv[2];
if (!demo) {
  console.error('usage: node tools/beats.mjs <demo-name>');
  process.exit(1);
}
const argo = (file) => import(pathToFileURL(path.resolve('node_modules/@argo-video/cli/dist', file)).href);
const { ClipCache } = await argo('tts/cache.js');
const { parseWavHeader } = await argo('tts/engine.js');
const { transcribeWav, DEFAULT_WHISPER_MODEL } = await argo('tts/transcribe.js');
const config = (await import(pathToFileURL(path.resolve('argo.config.mjs')).href)).default;
const manifest = JSON.parse(readFileSync(path.join(config.demosDir ?? 'demos', `${demo}.scenes.json`), 'utf8'));
const cache = new ClipCache(process.cwd());

const FRAME_S = 0.01;
const MIN_PAUSE_S = 0.12;
// The last word of a phrase is spoken slower. 1.8 halved the gap to Whisper's word times (189 → 115 ms median).
const FINAL_STRETCH = 1.8;

function readClip(file) {
  const buffer = readFileSync(file);
  const header = parseWavHeader(buffer);
  const count = Math.floor(header.dataSize / 4);
  const samples = new Float32Array(count);
  for (let i = 0; i < count; i++) samples[i] = buffer.readFloatLE(header.dataOffset + i * 4);
  return { samples, rate: header.sampleRate ?? 24_000 };
}

/** Speech runs [start, end] in seconds, from a 10 ms loudness envelope. */
function speechRuns({ samples, rate }) {
  const size = Math.round(rate * FRAME_S);
  const db = [];
  for (let i = 0; i + size <= samples.length; i += size) {
    let sum = 0;
    for (let j = i; j < i + size; j++) sum += samples[j] * samples[j];
    db.push(10 * Math.log10(sum / size + 1e-12));
  }
  const floor = Math.max(-50, Math.max(...db) - 38);
  const runs = [];
  let start = -1;
  db.forEach((value, i) => {
    if (value > floor && start < 0) start = i;
    if (value <= floor && start >= 0) {
      runs.push([start * FRAME_S, i * FRAME_S]);
      start = -1;
    }
  });
  if (start >= 0) runs.push([start * FRAME_S, db.length * FRAME_S]);
  // Short dips inside a word are not pauses.
  const merged = [];
  for (const run of runs) {
    const last = merged.at(-1);
    if (last && run[0] - last[1] < MIN_PAUSE_S) last[1] = run[1];
    else merged.push([...run]);
  }
  return merged;
}

const weight = (word) => Math.max(2, word.replace(/[^\p{L}\p{N}]/gu, '').length);

/** Whisper often puts a word inside the silence before it (the first word at 0.00 s); move it to where the sound starts. */
function onSpeech(t, runs) {
  const run = runs.find(([, end]) => end > t);
  return +(run && t < run[0] ? run[0] : t).toFixed(3);
}

/** Matches the text's phrase breaks (punctuation) to the pauses in the audio, then shares each
 *  phrase's speech time out over its words by length.
 *  The voice pauses at every sentence end, and longest there; at a comma it often does not pause at
 *  all. So sentence ends take the longest pauses first, a comma takes a pause only when one sits close to
 *  where it should fall, and every other break is placed by length between its neighbours. */
function estimate(text, runs) {
  const words = text.split(/\s+/).filter(Boolean);
  const phrases = [[]];
  const kinds = []; // kind of the break after each phrase but the last
  words.forEach((word, i) => {
    phrases.at(-1).push(word);
    const mark = /([.,;:!?])["')\]]*$/.exec(word);
    if (mark && i < words.length - 1) {
      kinds.push(/[.!?]/.test(mark[1]) ? 'sentence' : 'comma');
      phrases.push([]);
    }
  });
  // Speech time: the clip with the pauses taken out, so a pause never counts as speaking.
  const speech = runs.reduce((sum, [a, b]) => sum + (b - a), 0);
  const pauses = []; // { at: speech time where the pause falls, dur }
  let acc = 0;
  for (let i = 0; i < runs.length - 1; i++) {
    acc += runs[i][1] - runs[i][0];
    pauses.push({ at: acc, dur: runs[i + 1][0] - runs[i][1], used: false });
  }
  const share = (phrase, i) => weight(phrase[i]) * (i === phrase.length - 1 ? FINAL_STRETCH : 1);
  const sizes = phrases.map((phrase) => phrase.reduce((s, _, i) => s + share(phrase, i), 0));
  const total = sizes.reduce((a, b) => a + b, 0);
  const upTo = (k) => sizes.slice(0, k + 1).reduce((a, b) => a + b, 0); // size up to the end of phrase k
  const anchor = new Array(kinds.length).fill(null);

  // 1. Sentence ends: the longest pauses, in order, each near where its sentence should end.
  const ends = kinds.map((kind, k) => (kind === 'sentence' ? k : -1)).filter((k) => k >= 0);
  const longest = [...pauses].sort((a, b) => b.dur - a.dur).slice(0, ends.length).sort((a, b) => a.at - b.at);
  if (longest.length === ends.length) {
    ends.forEach((k, n) => {
      if (Math.abs(longest[n].at - (upTo(k) / total) * speech) < 0.3 * speech) {
        anchor[k] = longest[n].at;
        longest[n].used = true;
      }
    });
  }
  // 2. Other breaks: a free pause close to where they fall between their anchored neighbours.
  const place = (k) => {
    let a = k - 1;
    while (a >= 0 && anchor[a] === null) a--;
    let b = k + 1;
    while (b < kinds.length && anchor[b] === null) b++;
    const [t0, s0] = a >= 0 ? [anchor[a], upTo(a)] : [0, 0];
    const [t1, s1] = b < kinds.length ? [anchor[b], upTo(b)] : [speech, total];
    return { t0, t1, at: t0 + ((upTo(k) - s0) / Math.max(1e-9, s1 - s0)) * (t1 - t0) };
  };
  kinds.forEach((_, k) => {
    if (anchor[k] !== null) return;
    const { t0, t1, at } = place(k);
    const near = pauses.filter((p) => !p.used && p.at > t0 && p.at < t1 && Math.abs(p.at - at) < 0.35)
      .sort((p, q) => Math.abs(p.at - at) - Math.abs(q.at - at))[0];
    if (near) {
      anchor[k] = near.at;
      near.used = true;
    }
  });
  // 3. Breaks with no pause: by length between their anchored neighbours.
  kinds.forEach((_, k) => {
    if (anchor[k] === null) anchor[k] = place(k).at;
  });
  const bounds = [0, ...anchor, speech];
  for (let i = 1; i < bounds.length; i++) bounds[i] = Math.max(bounds[i], bounds[i - 1]);
  // Speech time back to clip time.
  const toClip = (t) => {
    let left = t;
    for (const [a, b] of runs) {
      if (left <= b - a + 1e-9) return a + left;
      left -= b - a;
    }
    return runs.at(-1)[1];
  };
  const out = [];
  phrases.forEach((phrase, k) => {
    const span = bounds[k + 1] - bounds[k];
    const sum = phrase.reduce((s, _, i) => s + share(phrase, i), 0);
    let at = bounds[k];
    for (const [i, word] of phrase.entries()) {
      const length = (share(phrase, i) / sum) * span;
      out.push({ text: word, start: +toClip(at + 0.001).toFixed(3), end: +toClip(at + length).toFixed(3) });
      at += length;
    }
  });
  return out;
}

/** Whisper may mishear a word ("and" as "in"). Keep the script's own words, so cues always match, and take
 *  the times from the Whisper words they line up with (longest common subsequence); words with no match
 *  share the time between their matched neighbours. */
function alignToScript(text, heard, runs) {
  const norm = (w) => w.toLowerCase().replace(/[^\p{L}\p{N}']/gu, '');
  const said = text.split(/\s+/).filter(Boolean);
  const a = said.map(norm);
  const b = heard.map((w) => norm(w.text));
  const L = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--) for (let j = b.length - 1; j >= 0; j--) {
    L[i][j] = a[i] && a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  }
  const match = new Array(a.length).fill(null);
  for (let i = 0, j = 0; i < a.length && j < b.length;) {
    if (a[i] && a[i] === b[j]) { match[i] = heard[j]; i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) i++; else j++;
  }
  const first = runs[0][0];
  const last = runs.at(-1)[1];
  const out = said.map((text, i) => (match[i] ? { text, start: match[i].start, end: match[i].end } : { text }));
  for (let i = 0; i < out.length;) {
    if (out[i].start !== undefined) { i++; continue; }
    let k = i;
    while (k < out.length && out[k].start === undefined) k++;
    const from = i > 0 ? out[i - 1].end : first;
    const to = k < out.length ? out[k].start : last;
    const total = out.slice(i, k).reduce((sum, w) => sum + weight(w.text), 0);
    let at = from;
    for (let n = i; n < k; n++) {
      const span = ((to - from) * weight(out[n].text)) / total;
      out[n] = { text: out[n].text, start: +at.toFixed(3), end: +(at + span).toFixed(3) };
      at += span;
    }
    i = k;
  }
  return out;
}

const beats = {};
for (const raw of manifest) {
  if (typeof raw.text !== 'string' || !raw.text.trim()) continue;
  const entry = { scene: raw.scene, text: raw.text, voice: raw.voice ?? config.tts?.defaultVoice, speed: raw.speed ?? config.tts?.defaultSpeed, lang: raw.lang };
  const clip = cache.getClipPath(demo, entry);
  if (!existsSync(clip)) {
    console.error(`${raw.scene}: no clip yet. Run: npx argo tts generate ${path.join(config.demosDir ?? 'demos', `${demo}.scenes.json`)}`);
    process.exit(1);
  }
  const audio = readClip(clip);
  const runs = speechRuns(audio);
  const base = path.basename(clip, '.wav');
  if (process.env.KT_TRANSCRIBE === '1') {
    // Whisper word times, written where argo pipeline looks for them, so both use the same words.
    const transcript = cache.getTranscriptPath(demo, entry, config.tts?.transcribe?.model ?? DEFAULT_WHISPER_MODEL);
    if (!existsSync(transcript)) writeFileSync(transcript, JSON.stringify(await transcribeWav(clip, {}), null, 2));
  }
  const whisper = readdirSync(path.dirname(clip)).find((f) => f.startsWith(`${base}.`) && f.endsWith('.transcript.json'));
  const words = whisper
    ? alignToScript(raw.text, JSON.parse(readFileSync(path.join(path.dirname(clip), whisper), 'utf8'))
      .map((w) => ({ text: w.text, start: onSpeech(w.start, runs), end: w.end })), runs)
    : estimate(raw.text, runs);
  beats[raw.scene] = {
    text: raw.text,
    clipMs: Math.round((audio.samples.length / audio.rate) * 1000),
    speechMs: [Math.round(runs[0][0] * 1000), Math.round(runs.at(-1)[1] * 1000)],
    source: whisper ? 'whisper' : 'estimate',
    words,
  };
}
const out = path.join(config.demosDir ?? 'demos', `${demo}.beats.json`);
writeFileSync(out, JSON.stringify(beats, null, 1));
console.log(`beats: ${out} (${Object.keys(beats).length} scenes)`);
