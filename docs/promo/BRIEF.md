---
workflow: general-video
flow: automation
storyboard: no
message: "Name a feature, get a narrated KT video made from your real code and your real app."
destination: github-readme
aspect: 1920x1080
language: en
audience: developers landing on the kt-studio GitHub repo
length: 75s
angle: product-promo
---

## Intent

A product-style video for the KT Studio Claude Code plugin's README, so people get what the plugin does
at a glance. Not a long, boring explanation: "it should be a product thing", smooth from one thing to
the next. Open on the VS Code style code tour — the eye-catching core ("start from the core VS Code
thing, folder structures and explaining a file"), then the explanation design / diagram with motion
design, then the features.

## Assets

- samples/dental-clinic/.kt-studio/features/appointment-booking/runs/2026-10-14-appointment-booking/5-videos/appointment-booking-code.mp4 — code tour with folder walk, highlighted code, notes, sequence diagram, terminal; the opening and the diagram beat.
- samples/dental-clinic/.kt-studio/features/appointment-booking/runs/2026-10-14-appointment-booking/5-videos/appointment-booking-ui.mp4 — the real app clicked on the spoken words; the sync beat.
- samples/shop-checkout/.kt-studio/features/payment-confirmation/runs/2026-10-14-payment-confirmation/5-videos/payment-confirmation.mp4 — Java and TypeScript deep dive; the any-language beat.
- samples/tiny-notes/.kt-studio/features/notes-cli/runs/2026-10-14-notes-cli/5-videos/notes-cli.mp4 — Rust CLI terminal scenes; the no-UI beat.
- samples/*/.kt-studio/features/*/runs/*/4-checks/storyboard-snaps/ — the storyboard page; the review-gate beat.

## Customizations

- Background music generated with MusicGen (offline).
- Voice-over in the plugin's own offline voice (Kokoro), plus on-screen text.

## Notes

- Smooth transitions only: no fade to black ("not any dumb animation like dark eye close").
- End card with the install command `/plugin install kt-studio@kt-studio`.
- Brand: KT Studio, dark VS Code look, orange accent #ff8a46, teal #4fc3b6.
