#!/usr/bin/env bash
# Rebuilds docs/promo/v3/assets/ for the energetic cut of the product video.
# Reuses the footage and thumbnails from ../build-assets.sh, then adds what v3 needs:
#   the whole storyboard page, the v3 voice-over, the energetic music bed and the premixed sound effects.
# Needs: ../build-assets.sh run first, ffmpeg, python3 with numpy and Pillow, and the HyperFrames skills
# (the sound effects come from the media-use skill's bundled Pixabay library).
# Usage: bash docs/promo/v3/build-assets.sh        (then: cd docs/promo/v3 && npx hyperframes render -o kt-studio-v3.mp4)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
A="$HERE/assets"
RT="$REPO/samples/dental-clinic/.kt-studio/runtime"
D="$(ls -d "$REPO"/samples/dental-clinic/.kt-studio/features/appointment-booking/runs/*-appointment-booking | head -1)"
SFX="${SFX_DIR:-$HOME/.claude/skills/media-use/audio/assets/sfx}"
mkdir -p "$A/audio/vo3" "$A/sfx"

# Footage, thumbnails: from the v2 build.
cp -R "$HERE/../assets/footage" "$HERE/../assets/images" "$A/"
cp "$A/footage/tour.mp4" "$A/footage/tour2.mp4"   # the same code-tour cut v2 uses

# The whole storyboard page: the review screenshots stitched top to bottom (1440 x 9152).
python3 - "$D/4-checks/storyboard-snaps" "$A/images/board-full.png" <<'PY'
import sys, glob
from PIL import Image
ims = [Image.open(f) for f in sorted(glob.glob(sys.argv[1] + "/snap-*.png"))]
full = Image.new("RGB", (ims[0].size[0], sum(i.size[1] for i in ims)), "white")
y = 0
for i in ims:
    full.paste(i, (0, y)); y += i.size[1]
full.save(sys.argv[2])
PY

# Voice-over: the plugin's own offline voice, a little faster for this cut.
(cd "$RT" && node --input-type=module -e '
  import { readFileSync } from "node:fs";
  const { KokoroTTS } = await import("kokoro-js");
  const tts = await KokoroTTS.from_pretrained("onnx-community/Kokoro-82M-v1.0-ONNX", { dtype: "q8" });
  for (const [id, text] of JSON.parse(readFileSync(process.argv[1], "utf8"))) {
    await (await tts.generate(text, { voice: "af_heart", speed: 1.12 })).save(`${process.argv[2]}/${id}.wav`);
  }' "$HERE/voice-over.json" "$A/audio/vo3")
# Bring every line to -16 LUFS, so the voice sits well above the music bed.
for f in "$A"/audio/vo3/*.wav; do
  ffmpeg -v error -y -i "$f" -af "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000" "$f.tmp.wav" && mv "$f.tmp.wav" "$f"
done

# Music: 30 s from MusicGen. Its loud part from the drop (13.44 s) is 8 bars at 124 bpm (15.51 s);
# four of those back to back cover the 50.15 s after Enter.
cp "$HERE/music.mjs" "$RT/.kt-music3.mjs"
(cd "$RT" && node ./.kt-music3.mjs "$A/audio/music3-30s.wav")
rm -f "$RT/.kt-music3.mjs"
ffmpeg -v error -y -i "$A/audio/music3-30s.wav" -af "atrim=13.44:28.95,asetpts=PTS-STARTPTS,afade=t=in:d=0.006,afade=t=out:st=15.504:d=0.006" "$A/audio/seg.wav"
printf "file 'seg.wav'\n%.0s" 1 2 3 4 > "$A/audio/loop.txt"
ffmpeg -v error -y -f concat -safe 0 -i "$A/audio/loop.txt" \
  -af "atrim=0:50.15,afade=t=out:st=47.4:d=2.75,aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=11" -ac 2 "$A/audio/music3.wav"
rm -f "$A/audio/seg.wav" "$A/audio/loop.txt"
# The drop depends on the generation: check where the loud part starts if you regenerate the music.

# Sound effects: key presses for every typed character, whooshes, pops and hits, premixed into one track.
for f in key-press click click-soft pop whoosh whoosh-short impact-bass-1 impact-bass-2 chime ping riser sparkle; do
  cp "$SFX/$f.mp3" "$A/sfx/"
done
python3 "$HERE/sfx_mix.py" "$HERE"
echo "assets ready in $A"
