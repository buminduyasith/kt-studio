# Product video, energetic cut (v3)

The energetic cut of the product video (53 s, 1920x1080) is built with
[HyperFrames](https://hyperframes.heygen.com). The calmer 67 s cut lives one folder up, in `docs/promo/`.

The order follows how a user meets the plugin:

1. `/kt-studio appointment-booking` types key by key (with key sounds), Enter lands and the music drops.
2. The real storyboard scrolls by: the overview, every Part A screen, every Part B code card, then the
   review box is ticked and stamped APPROVED.
3. The code tour in the VS Code style editor.
4. The real app take, with each click landing on its word.
5. The sequence diagram.
6. Any language, any stack. 7. Re-record one scene. 8. The end card and the install command.

| File | What it is |
| --- | --- |
| `index.html` | The composition: eight scenes on one stage, one GSAP timeline |
| `voice-over.json` | The eight voice-over lines (Kokoro `af_heart`, speed 1.12) |
| `sfx_mix.py` | Premixes every sound effect into `assets/audio/sfx.wav`; its times match `index.html` |
| `music.mjs` | The MusicGen prompt for the energetic bed |
| `build-assets.sh` | Rebuilds `assets/` from the sample runs (run `../build-assets.sh` first) |

```bash
bash docs/promo/build-assets.sh && bash docs/promo/v3/build-assets.sh
cd docs/promo/v3 && npm run check && npx --yes hyperframes@0.8.158 render -o kt-studio-v3.mp4 --quality high
```

Sound effects are from the HyperFrames media-use skill's bundled library (Pixabay Content License).
