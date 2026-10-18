#!/usr/bin/env bash
# Rebuilds docs/promo/assets/ for the product video from the sample runs:
#   the footage clips, the thumbnails, the voice-over (Kokoro, offline) and the music bed (MusicGen, offline).
# Needs the three sample videos first (run /kt-studio in samples/dental-clinic, samples/shop-checkout and
# samples/tiny-notes; see samples/README.md), ffmpeg, and the dental-clinic recorder runtime.
# Usage: bash docs/promo/build-assets.sh        (then: cd docs/promo && npx hyperframes render -o kt-studio.mp4)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
A="$HERE/assets"
RT="$REPO/samples/dental-clinic/.kt-studio/runtime"
D="$(ls -d "$REPO"/samples/dental-clinic/.kt-studio/features/appointment-booking/runs/*-appointment-booking | head -1)"
S="$(ls -d "$REPO"/samples/shop-checkout/.kt-studio/features/payment-confirmation/runs/*-payment-confirmation | head -1)"
T="$(ls -d "$REPO"/samples/tiny-notes/.kt-studio/features/notes-cli/runs/*-notes-cli | head -1)"
mkdir -p "$A/footage" "$A/images" "$A/audio/vo"

# Footage: video only, 1080p; long stretches pre-sped so each scene plays at normal rate.
cut() { # source start length speed name
  ffmpeg -v error -y -ss "$2" -t "$3" -i "$1" -an -vf "setpts=PTS/$4,fps=30,scale=1920:1080,format=yuv420p" \
    -c:v libx264 -preset medium -crf 18 -g 15 -movflags +faststart "$A/footage/$5.mp4"
}
cut "$D/5-videos/appointment-booking-code.mp4" 36.2 16 1.5 tour
cut "$D/5-videos/appointment-booking-code.mp4" 12.6 23 2.6 diagram
cut "$D/5-videos/appointment-booking-ui.mp4" 45.9 9.0 1 ui
cut "$D/5-videos/appointment-booking-ui.mp4" 52.4 9.0 1 schedule
cut "$S/5-videos/payment-confirmation-code.mp4" 112.0 9.5 1.2 java
cut "$T/5-videos/notes-cli-code.mp4" 8.6 36 4 rust

# Thumbnails and the storyboard page.
ffmpeg -v error -y -ss 5 -i "$A/footage/tour.mp4" -frames:v 1 -vf scale=640:-1 -q:v 3 "$A/images/thumb-code.jpg"
ffmpeg -v error -y -ss 7.5 -i "$A/footage/ui.mp4" -frames:v 1 -vf scale=640:-1 -q:v 3 "$A/images/thumb-ui.jpg"
SNAP="$D/4-checks/storyboard-snaps/snap-01.png"
ffmpeg -v error -y -i "$SNAP" -vf "crop=1440:900:0:0" "$A/images/board.png"
ffmpeg -v error -y -i "$SNAP" -vf "crop=1440:810:0:0,scale=640:-1" -q:v 3 "$A/images/thumb-board.jpg"

# Voice-over in the plugin's own offline voice.
(cd "$RT" && node --input-type=module -e '
  import { readFileSync } from "node:fs";
  const { KokoroTTS } = await import("kokoro-js");
  const tts = await KokoroTTS.from_pretrained("onnx-community/Kokoro-82M-v1.0-ONNX", { dtype: "q8" });
  for (const [id, text] of JSON.parse(readFileSync(process.argv[1], "utf8"))) {
    await (await tts.generate(text, { voice: "af_heart", speed: 1.0 })).save(`${process.argv[2]}/${id}.wav`);
  }' "$HERE/voice-over.json" "$A/audio/vo")

# Music: 30 s from MusicGen (downloads about 1.8 GB once), looped to 67.5 s with crossfades.
cp "$HERE/music.mjs" "$RT/.kt-music.mjs"
(cd "$RT" && node ./.kt-music.mjs "$A/audio/music-30s.wav")
rm -f "$RT/.kt-music.mjs"
M="$A/audio/music-30s.wav"
ffmpeg -v error -y -i "$M" -i "$M" -i "$M" -filter_complex \
  "[0][1]acrossfade=d=2:c1=tri:c2=tri[a];[a][2]acrossfade=d=2:c1=tri:c2=tri,atrim=0:67.5,afade=t=in:st=0:d=1.2,afade=t=out:st=65:d=2.5,aresample=48000,loudnorm=I=-18:TP=-2:LRA=11" \
  -ac 2 "$A/audio/music.wav"
echo "assets ready in $A"
