// Pacing a person can follow. Measured on real takes; see references/quality.md before changing.

/** Mouse travel for every scripted click. */
export const CALM = { durationMs: 700, dwellMs: 200, afterMs: 300 };

/** Pause after each spoken point before the next thing moves. */
export const PAUSE_AFTER_POINT = { leadOutMs: 1_500 };

/** Shorter pause after a narrated navigation line. */
export const PAUSE_AFTER_WALK = { leadOutMs: 600 };

/** Typing speed for form fields, in ms per character. */
export const TYPE_MS = 75;

/** Typing speed in the code tour's quick open: a developer types a file name fast. */
export const QUICK_OPEN_MS = 55;
