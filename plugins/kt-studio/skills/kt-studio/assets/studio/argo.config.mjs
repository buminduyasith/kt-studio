import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { defineConfig } from '@argo-video/cli';

// The project's voice from its settings (.kt-studio/config.yml, the nearest one above this runtime), so `argo tts generate`,
// tools/beats.mjs and the takes all use the same voice even when KT_VOICE and KT_SPEED are not set.
function projectVoice() {
  let dir = process.cwd();
  for (let i = 0; i < 5; i++, dir = path.dirname(dir)) {
    const file = path.join(dir, '.kt-studio', 'config.yml');
    if (!existsSync(file)) continue;
    const block = (readFileSync(file, 'utf8').match(/^voice:\s*\n((?:[ \t]+.*\n?|\s*\n)*)/m) ?? [])[1] ?? '';
    return {
      name: (block.match(/^\s+name:\s*([a-z_]+)/m) ?? [])[1],
      speed: (block.match(/^\s+speed:\s*([\d.]+)/m) ?? [])[1],
    };
  }
  return {};
}
const voice = projectVoice();

// Everything that differs per project or run comes in as environment variables set by the agent or
// take.sh: KT_BASE_URL (the run's app), KT_STATE (the run's login, only when the app needs one),
// KT_VOICE, KT_SPEED, and optionally KT_TRANSCRIBE=1.
const state = process.env.KT_STATE;

export default defineConfig({
  baseURL: process.env.KT_BASE_URL ?? 'http://localhost:3000',
  demosDir: 'demos',
  outputDir: 'videos',
  tts: {
    defaultVoice: process.env.KT_VOICE ?? voice.name ?? 'af_heart',
    defaultSpeed: Number(process.env.KT_SPEED ?? voice.speed ?? 0.9),
    // KT_TRANSCRIBE=1: Whisper word times (tools/beats.mjs makes them; the subtitles and cues use them).
    ...(process.env.KT_TRANSCRIBE === '1' ? { transcribe: true } : {}),
  },
  video: {
    width: 1920,
    height: 1080,
    fps: 30,
    browser: 'chromium',
    captureMode: 'jpeg-stitch',
    deviceScaleFactor: 1,
    cursorHighlight: { mode: 'click' },
    ...(state ? { contextOptions: { storageState: path.resolve(state) } } : {}),
  },
  // No export.transition and no export.speedRamp: both made scene changes blink and rush.
  export: {
    preset: 'slow',
    crf: 16,
    sharpen: true,
    audio: { loudnorm: true },
  },
  overlays: {
    autoBackground: true,
  },
});
