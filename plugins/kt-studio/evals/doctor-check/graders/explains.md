---
type: llm
weight: 1
---

The reply reports the doctor's result in simple English. This folder has no KT Studio settings (no .kt-studio/config.yml) and no
recorder runtime, so a good reply says the project is not ready yet and names the fixes: create the
settings with `/kt-studio:init`, and run setup (about 1 GB the first time). It must not claim the
project is ready, and it must not start the install itself, because `doctor` only checks.
