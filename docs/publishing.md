# Publishing KT Studio as a Claude Code plugin

A guide for shipping this plugin, and for building plugins in general. Each step has the exact
commands.

## 1. Skill or plugin: what changed

A **skill** is one folder with a `SKILL.md`. People install it by copying the folder into
`~/.claude/skills/`. There are no versions, no updates and no catalog.

A **plugin** is a package that can hold skills, commands, agents, hooks and MCP servers. People
install it from a **marketplace** (a git repo with a `marketplace.json`). Claude Code copies it into
its plugin cache, knows its version, and can update it.

KT Studio is a plugin with four skills (`make`, `init`, `update`, `doctor`). The repo is both the
plugin's marketplace and its home, so people need only one repo to install it. The plugin itself sits
in its own folder, `plugins/kt-studio/`: Claude Code copies only that folder into each user's plugin
cache, so the samples and the promo video sources never reach their computers.

## 2. The layout and what each file does

```
kt-studio/
├── .claude-plugin/
│   └── marketplace.json    the catalog: lists this one plugin, with "source": "./plugins/kt-studio"
├── plugins/kt-studio/      the plugin: the only folder users get
│   ├── .claude-plugin/plugin.json   name, version, description, author, links
│   ├── skills/
│   │   ├── kt-studio/      /kt-studio:make (name: make): SKILL.md, references, scripts, recorder files, examples
│   │   ├── init/           /kt-studio:init, a short skill that points at kt-studio/references/init.md
│   │   ├── update/         /kt-studio:update, points at kt-studio/references/update.md
│   │   └── doctor/         /kt-studio:doctor, runs kt-studio/scripts/doctor.sh
│   ├── evals/              automated checks (claude plugin eval)
│   └── LICENSE
├── samples/                test projects (not shipped)
├── docs/                   diagrams, the promo video sources and this guide (not shipped)
├── README.md               what people see on GitHub
└── LICENSE
```

Rules that matter:

- Only `plugin.json` goes inside the plugin's `.claude-plugin/`; `marketplace.json` sits in the repo's.
  Keep `version` only in `plugin.json`, and raise it on every release.
- Plugin skills are always invoked with the plugin name first: `/kt-studio:<skill>`. The main skill's
  folder is `skills/kt-studio/`, but its `name: make` makes it `/kt-studio:make`, so no command reads
  `/kt-studio:kt-studio`. `init`, `update` and `doctor` have `disable-model-invocation: true`: they run
  only when typed (asking in words goes through `make`, which handles all four).
- In `SKILL.md`, `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` are replaced
  with real folders when the skill loads. That is how the skills find `scripts/` wherever the plugin is
  installed, and where `setup.sh` installs the recorder. These variables are not set inside Bash
  commands, so write them in the Markdown, not in a script.
- Each skill's `allowed-tools` lets it run the plugin's own scripts (`bash <skill>/scripts/...`,
  `python3 <skill>/scripts/...`) without a permission prompt, for that turn only. Nothing else is
  pre-approved.
- Keep descriptions under 1,024 characters, in the third person, use case first; keep `SKILL.md` under
  500 lines and put details in `references/` (one level deep, a contents line on long files).
- Keep everything the plugin needs inside the plugin folder. At install, Claude Code copies only this
  folder, so a path like `../shared` breaks.
- No `package.json` at the plugin root. If one is there with a lockfile, Claude Code installs its Node
  packages into the plugin cache on every version, with a 60-second limit. KT Studio's packages live in
  `skills/kt-studio/assets/studio/`. `setup.sh` installs them once, with the voice model, into the
  plugin's data folder (`${CLAUDE_PLUGIN_DATA}`, `~/.claude/plugins/data/kt-studio-kt-studio/`), which
  Claude Code keeps across updates and deletes on uninstall; each project's `.kt-studio/runtime/`
  links to it. Only when the doctor asks for it, never in a hook.
- Call scripts through their interpreter (`bash script.sh`, `python3 script.py`), so they work even
  if the executable bit is lost.

## 3. Why the setup check runs inside the skill, not as a hook

A plugin can run a `SessionStart` hook, but it runs in **every** session of **every** project while
the plugin is enabled, and Claude waits for it. Checking 1 GB of tools there would slow everyone down.

So the check lives in the skill:

- `scripts/doctor.sh` checks the tools, the settings and the recorder in under a second, changes
  nothing, and prints `doctor: ready` or a numbered list of fixes.
- Every run starts with it (step 0). `/kt-studio:init` runs it in full with a live test, and
  `/kt-studio:doctor` runs it on demand.
- `setup.sh` writes a fingerprint of the studio files into the runtime. After a plugin update the
  fingerprint differs, the doctor says `[setup]`, and the skill refreshes the runtime itself.

## 4. Test it locally

Check the manifests and the skill:

```bash
claude plugin validate . --strict
```

```bash
claude plugin validate skills --strict
```

Load the plugin from this folder, without installing it, in a session opened in a test project:

```bash
claude --plugin-dir /path/to/kt-studio/plugins/kt-studio
```

Then try `/kt-studio:doctor` and `/kt-studio:init`. After you edit a file, run `/reload-plugins` in
that session.

If you also have the skill as a plain folder in `~/.claude/skills/kt-studio`, remove it: otherwise
two copies load.

To test the real install path (copy into the cache, version handling), add this folder as a local
marketplace:

```bash
claude plugin marketplace add /path/to/kt-studio
```

```bash
claude plugin install kt-studio@kt-studio
```

## 5. Automatic checks on every pull request

`.github/workflows/validate.yml` runs on every pull request and every push to `main`, with no secrets:

| Check | What it catches |
|---|---|
| `claude plugin validate --strict` (marketplace and plugin) | Files Claude Code cannot load |
| JSON parse | A broken `plugin.json`, `marketplace.json` or recorder `package.json` |
| `shellcheck -S warning` | Shell script bugs |
| `py_compile` on Python 3.9 | Python the oldest supported version cannot run |
| `python3 -m unittest discover -s tests` | The rules that matter: the `.kt-studio` folder and its `.gitignore`, the Services, Addresses and Logging in tables, `apps.py` login decisions, `choices.py` questions and answers, clean-up deleting only KT Studio's own login files, "only init downloads", skill frontmatter (names, description length, `allowed-tools`), the version kept only in `plugin.json` |

Run the same locally before you push: `python3 -m unittest discover -s tests -v`. The tests live in
`tests/`, outside the plugin folder, so they never ship to users. Add a test whenever you fix a bug a
script could make again.

## 6. Run the evals

The `evals/` folder holds two cases: `/kt-studio:doctor` must run the doctor and explain the fixes
without installing anything, and "make a KT video for refunds" must start the skill. Each run is a
real Claude session, so it costs a little (about $0.15 per case).

```bash
claude plugin eval plugins/kt-studio --runs 1 --no-publish --allow-tools Bash --ablation none
```

Run it from a clean clone of the repo, not your working folder: the evals copy the plugin folder,
and recordings in `samples/*/.kt-studio/` are gigabytes and contain hard links the harness refuses.
On Linux the evals need `bubblewrap` and `socat` for their sandbox (`apt install bubblewrap socat`).

Add a case whenever you fix a bug the skill could make again. `claude plugin eval init` interviews
you and writes a case.

## 7. Publish on GitHub

Do this once. The repo name must match the links in `plugin.json`, `marketplace.json` and the
README (`buminduyasith/kt-studio`).

```bash
cd /path/to/kt-studio && git init -b main
```

```bash
git add . && git commit -m "KT Studio 0.1.0 as a Claude Code plugin"
```

```bash
gh repo create buminduyasith/kt-studio --public --source . --push
```

```bash
git tag v0.1.0 && git push origin v0.1.0
```

A private repo works too, but then only people with access to it can install the plugin.

## 8. Install it like a user would

In any Claude Code session:

```
/plugin marketplace add buminduyasith/kt-studio
/plugin install kt-studio@kt-studio
```

Then open a project and run `/kt-studio:init`.

## 9. Ship an update

How versions work for users:

- `/plugin marketplace add buminduyasith/kt-studio` reads the **default branch** (`main`). So `main`
  is always the newest release: work on other branches and merge into `main` only when you release.
- Claude Code compares the `version` in `plugins/kt-studio/.claude-plugin/plugin.json` with the one a user has. Users
  get an update **only when this string changes**. A commit that doesn't change it (a README fix, for
  example) reaches new installs but never existing ones. Set the version in `plugin.json` only, not
  in `marketplace.json` too.
- Auto-update is **off** by default for community marketplaces like this one. Users turn it on in
  `/plugin` → Marketplaces → kt-studio → Enable auto-update; the README tells them how.
- Users can stay on one version by adding the marketplace at a tag:
  `/plugin marketplace add buminduyasith/kt-studio#v0.1.0`. That is why every release gets a tag.
- Keep large files (videos, recordings) off `main`. Installing clones the repo, and the plugin source
  is `./`, so everything on `main` is copied into every user's plugin cache.

Version numbers: `0.x.y` while in beta. Raise `y` for fixes, `x` for new features or anything that
changes the settings files or the commands. `1.0.0` is the first stable release.

Steps:

1. Change the files on a branch and test them (sections 4 and 5, plus one real video).
2. Raise `version` in `plugins/kt-studio/.claude-plugin/plugin.json`, for example `0.1.0` to `0.2.0`.
3. Open a pull request and merge it into `main`.
4. Tag the merge commit on `main` and push the tag:

```bash
git checkout main && git pull && git tag -a v0.2.0 -m "KT Studio 0.2.0" && git push origin v0.2.0
```

5. On GitHub, create a release from the tag (Releases → Draft a new release). Write what changed and
   what users must do after updating (usually nothing; say so), and tick **Set as a pre-release** while the version starts with `0.`.

Users with auto-update on get it within about ten minutes of their next session. Others run:

```bash
claude plugin marketplace update kt-studio
```

```bash
claude plugin update kt-studio@kt-studio
```

then `/reload-plugins`. The old version stays in the cache for 14 days, so a running session is not
broken mid-run. After the update, `/kt-studio:doctor` refreshes each project's recorder by itself.

## 10. Share it more widely

- **Your team:** add the marketplace to a project's `.claude/settings.json` with
  `claude plugin marketplace add buminduyasith/kt-studio --scope project`. Everyone who opens that
  project is offered the plugin.
- **The community catalog:** once the repo is public and stable, you can submit it to Anthropic's
  community marketplace. See the Claude Code docs on plugin marketplaces for the current process.

## 11. Checklist before every release

- [ ] `claude plugin validate . --strict` passes.
- [ ] `/kt-studio:doctor` and `/kt-studio:init` work in a fresh project (with `--plugin-dir`).
- [ ] The evals pass.
- [ ] One real video recorded end to end on a test app (the projects in `samples/`), with
      `check_sync.py` and `check_video.py` passing.
- [ ] `version` raised in `plugin.json`, and the release notes written.
- [ ] No large files on `main`: a fresh install stays around 2 MB.
- [ ] No secrets, personal data or company-specific names in the repo.

## Reference

- Plugins: https://code.claude.com/docs/en/plugins/create.md
- `plugin.json` fields: https://code.claude.com/docs/en/plugins/manifest-reference.md
- Marketplaces: https://code.claude.com/docs/en/plugins/marketplace-reference.md
- Skills (frontmatter, `${CLAUDE_SKILL_DIR}`, arguments): https://code.claude.com/docs/en/skills.md
- Evals: https://code.claude.com/docs/en/plugin-evals.md
