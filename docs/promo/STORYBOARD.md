---
message: "Name a feature, get a narrated KT video made from your real code and your real app."
audience: developers landing on the kt-studio GitHub repo
mode: autonomous
duration: 67.5s
---

This video tells developers that a named feature becomes a narrated KT video made from their real
code and their real app. It follows the order a user meets the plugin: type the command, review the
storyboard, then watch the code tour and the diagram. Structure: monolithic `index.html`, eight scene
divs on one persistent dark stage (shared background, wordmark, progress line), one paused timeline.
Primary transition: push slide (0.5 s, power3.inOut). Accents: a zoom-through from the storyboard into
the code tour, and a blur crossfade into the end card. No dip to black anywhere.

## Frame 1
status: animated
src: index.html#s1
blueprint: prompt-type-submit-generate (Hook)
beat: 0.0–9.6 s · VO "Type slash K T Studio, and name a feature. It reads your code, and makes the knowledge transfer video for you."
`/kt-studio appointment-booking` types into a Claude Code prompt pill. "Name a feature." stamps, the
prompt submits, and the status steps light (reading the code · writing a storyboard · recording). Three
output cards build below it (storyboard.html, booking-ui.mp4, booking-code.mp4) next to the facts:
offline voice, subtitles, chapters.

## Frame 2
status: animated
src: index.html#s2
blueprint: agent-progress-theater (Key_Feature, dark variant)
beat: 9.6–18.6 s · VO "First, a storyboard. You review every scene and every line. Nothing is filmed until you approve."
"Storyboard first." The real storyboard page floats up in a window, the pipeline cards check in turn
(Research, Storyboard), and the gate card holds on "You approve" and then flips teal. Record and Check
wait behind it.

## Frame 3
status: animated
src: index.html#s3
blueprint: zoom-out-workspace-reveal (variant A: continuous nesting pull)
beat: 18.6–28.8 s · VO "Then the code tour. It walks your repo like a teammate would, opens the real file, and explains one idea at a time."
A zoom-through from the storyboard lands tight on the VS Code explorer. One decelerating zoom-out shows
it is a window on the stage. The side label changes with the voice: walks your repo → opens the real
file → one idea at a time.

## Frame 4
status: animated
src: index.html#s4
blueprint: video-text-pivot (Key_Feature)
beat: 28.8–36.0 s · VO "Sequence diagrams show the big picture, from the button to the database."
The sequence diagram lights up step by step in a window. "The big picture." stamps, and a pill closes
the scene: button → server → database.

## Frame 5
status: animated
src: index.html#s5
blueprint: cursor-ui-demo (Key_Feature)
beat: 36.0–44.8 s · VO "Then it records your real app. Every click lands on the word that names it, and every take is checked."
The real app take plays (11:00 picked, Book appointment clicked). Under it a word track marks the spoken
words, and the click lands on "Book". PASS chips stamp at the end.

## Frame 6
status: animated
src: index.html#s6
blueprint: grid-card-assemble (Benefits)
beat: 44.8–52.6 s · VO "Any language, any stack. No screens? It runs real commands in a terminal."
Three windows assemble (a Java service walk, a Rust CLI in a terminal, a JavaScript + Python app), and
language chips step in under them.

## Frame 7
status: animated
src: index.html#s7
blueprint: comparison-split (Key_Feature)
beat: 52.6–60.2 s · VO "Something changed? Record just that scene. It splices in without a seam."
A strip of 22 scene blocks. B3-02 lifts out and a new block drops in. A full re-take takes 4:24 and a
patch takes 0:56. The join readout: frame difference 0.0, −91 dB.

## Frame 8
status: animated
src: index.html#s8
blueprint: logo-assemble-lockup (CTA)
beat: 60.2–67.5 s · VO "KT Studio. Skip the handover meeting. Hand over a video."
"KT Studio" assembles with the tagline "Skip the meeting. Hand over a video.", the install command types
into a pill, and one line of facts sits below it. The card holds to the end.
