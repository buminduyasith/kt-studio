# KT Studio folder

Made by the KT Studio plugin. Do not delete `config.yml` or `instructions.md`: they are this project's
settings, and git keeps them (see `.gitignore`), with `learned.yml` and each feature's `feature.yml`.
Everything else here stays on your computer.

```
.kt-studio/
├── config.yml                your settings: repos and branches, docs, voice (commit it)
├── instructions.md           your rules, your services and where each one runs (commit it)
├── learned.yml               the answers people picked, so later videos ask less (commit it)
├── runtime/                  the recorder and the offline voice, shared by every run (safe to delete; setup rebuilds it)
│   └── .auth/                logins of the current run, deleted when it ends. Private: never share or commit
└── features/
    └── <feature>/            one folder per feature
        ├── feature.yml       this feature's answers: who the videos are for, what they show, how deep (commit it)
        └── runs/
            └── <date>-<feature>/   one folder per video
                ├── run.json        the request, the answers, the apps it shows, the storyboard link, the status of each step
                ├── 1-research/     brief.md: what the feature does, flows, code facts with file:line
                ├── 2-storyboard/   storyboard.json, storyboard.html, shots/ (real screenshots)
                ├── 3-scripts/      the recording scripts
                ├── 4-checks/       contact sheets, scene reports, word timings
                └── 5-videos/       the finished videos with subtitles: hand these over
```
