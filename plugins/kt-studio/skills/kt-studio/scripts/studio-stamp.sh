# shellcheck shell=bash
# Sourced by setup.sh and doctor.sh. Prints a fingerprint of the skill's studio files, so the doctor
# can tell when a runtime was set up by an older version of the skill (after a plugin update).
studio_stamp() {
  (cd "$1/assets/studio" && find . -type f ! -name '.DS_Store' | LC_ALL=C sort | while IFS= read -r f; do cksum "$f"; done) \
    | cksum | cut -d' ' -f1
}

# A fingerprint of the recorder's pinned packages (package.json and its lockfile): the name of the
# shared copy of node_modules they install.
deps_stamp() {
  cat "$1/assets/studio/package.json" "$1/assets/studio/package-lock.json" 2>/dev/null | cksum | cut -d' ' -f1
}

# The plugin's data folder, ~/.claude/plugins/data/<plugin>-<marketplace>: Claude Code keeps it across
# plugin updates and deletes it when the plugin is uninstalled. The recorder's packages and the voice
# model are installed there once and shared by every project. Empty when the skill does not run from
# the plugin cache (a development copy): then each project installs its own.
plugin_data_dir() {
  [ -n "${KT_SHARED_DIR:-}" ] && { printf '%s' "$KT_SHARED_DIR"; return; }
  local root plugin mkt cache
  root="$(cd "$1/../.." 2>/dev/null && pwd)" || return 0
  plugin="$(basename "$(dirname "$root")")"
  mkt="$(basename "$(dirname "$(dirname "$root")")")"
  cache="$(dirname "$(dirname "$(dirname "$root")")")"
  [ "$(basename "$cache")" = cache ] && [ "$(basename "$(dirname "$cache")")" = plugins ] || return 0
  printf '%s' "$(dirname "$cache")/data/$plugin-$mkt"
}
