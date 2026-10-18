# The KT Studio product video

The calmer cut of the product video (67 s, 1920x1080) is built with
[HyperFrames](https://github.com/heygen-com/hyperframes) from footage KT Studio recorded of the sample
projects in [`samples/`](../../samples/): the code tour, the sequence diagram and the real app from
`dental-clinic`, the Java walk from `shop-checkout`, and the Rust terminal scenes from `tiny-notes`.
The voice-over is the plugin's own offline voice (Kokoro), the music is generated offline (MusicGen).

| File | What it is |
|---|---|
| `index.html` | The composition: eight scenes on one stage, one GSAP timeline |
| `STORYBOARD.md` | The plan: each scene's beat, voice line and motion blueprint |
| `BRIEF.md` | The brief the video was made from |
| `voice-over.json` | The eight voice-over lines |
| `music.mjs` | The MusicGen prompt for the music bed |
| `build-assets.sh` | Cuts the footage from the sample runs and makes the voice and the music |

To rebuild it: record the three samples (`samples/README.md`), then

```bash
bash docs/promo/build-assets.sh
cd docs/promo && npx hyperframes check && npx hyperframes render -o kt-studio-calm.mp4 --quality high --video-frame-format png
```

`assets/` is not committed (about 30 MB of footage and audio).

The energetic 53 s cut is in [`v3/`](v3/). The rendered videos are not kept in the repo, so that
installing the plugin stays small: build them with the commands above.
