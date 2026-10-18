---
name: doctor
description: "Checks that KT Studio is ready in this project (tools on this computer, the .kt-studio/ settings, the recorder, disk space) and explains how to fix each problem."
disable-model-invocation: true
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/scripts/*) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/scripts/*)
---

# KT Studio: check everything

Run `bash ${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/scripts/doctor.sh <root> --data ${CLAUDE_PLUGIN_DATA}` (`<root>`: the project
folder, the one that holds `.kt-studio/`; the current folder when unsure). Explain each `FAIL` and `TIP`
line and its fix in simple English, one line each, with the exact command for anything the person must
install. `[init]` lines are fixed by `/kt-studio:init`, the only
command that downloads (up to 1 GB the first time on a computer): tell the person to run it. A
`[setup]` line is a refresh that downloads nothing and takes seconds: offer to run the exact command it
shows (it always has `--no-download`). This check never downloads and changes nothing without a yes.
