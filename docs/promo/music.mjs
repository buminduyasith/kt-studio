import { writeFileSync } from 'node:fs';
const { generateMusic } = await import(process.cwd() + '/node_modules/@argo-video/cli/dist/music/musicgen.js');
const t0 = Date.now();
const wav = await generateMusic({
  prompt: 'modern minimal electronic product launch music, warm analog synth pads, soft pulsing arpeggio, gentle kick, uplifting and confident, 112 bpm, no vocals',
  durationSec: 30,
});
writeFileSync(process.argv[2], wav);
console.log(`music ready in ${Math.round((Date.now() - t0) / 1000)} s`);
