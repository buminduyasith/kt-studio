---
name: update
description: "Changes a KT video that KT Studio already delivered, by recording only the changed scenes and splicing them in: a reworded line, an added or removed scene, or code that changed since the video. Usage: /kt-studio:update, then the feature and what to change."
argument-hint: "<feature> [what to change, e.g. 'in scene B3-02 say ten working days']"
disable-model-invocation: true
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/scripts/*) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/scripts/*)
---

# KT Studio: change a delivered video

**Request:** $ARGUMENTS

The first word is the feature; the rest says what to change (nothing: find the scenes the code has made
out of date). Follow `${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/references/update.md`. In that file,
`<skill>` means `${CLAUDE_PLUGIN_ROOT}/skills/kt-studio` and `<data>` means `${CLAUDE_PLUGIN_DATA}`, and the steps it borrows (preflight, gate 2,
checks, clean-up) are in `${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/SKILL.md`, whose rules that always apply
hold here too; like every command but `/kt-studio:init`, it never downloads anything (`SKILL.md` step 1).
No delivered video for that feature yet: say so, and offer `/kt-studio:make <feature>`.
