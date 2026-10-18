---
name: init
description: "Sets KT Studio up in this project, or checks and repairs the setup: checks the computer, writes the project's .kt-studio/ folder (config.yml with repos, docs and voice; instructions.md with the project's rules, its services and where each one runs in each environment) and installs the recorder."
argument-hint: "[anything to know first, e.g. 'we have dev and qa']"
disable-model-invocation: true
allowed-tools: Bash(bash ${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/scripts/*) Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/scripts/*)
---

# KT Studio: set up this project

**Request:** $ARGUMENTS

Follow `${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/references/init.md` from its first step. In that file,
`<skill>` means `${CLAUDE_PLUGIN_ROOT}/skills/kt-studio` and `<data>` means `${CLAUDE_PLUGIN_DATA}`, and the names `<root>`, `<config>`,
`<instructions>` and `<out>` are explained in `${CLAUDE_PLUGIN_ROOT}/skills/kt-studio/SKILL.md`
("Names used below"). The rules that always apply in that SKILL.md apply here too: simple English, never
log in for the person, never ask for or write down a password.

When it is done, tell the person the next command: `/kt-studio:make <feature> [instructions]`.
