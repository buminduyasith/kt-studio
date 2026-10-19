// Builds one code tour folder: copies the VS Code style page and writes data.js with the real
// explorer tree and the highlighted tour files, read from git at each repo's ref (not the working tree).
//
// Usage: node tools/build_tour.mjs <tour.json> <out-dir>
// tour.json: { "title", "workspace",
//              "repos": { "<key>": { "path": "/abs/or/relative/to/tour.json", "label": "Backend", "ref": "origin/dev" } },
//              "files": [["<key>", "src/path/file.ts"], ...] }
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { codeToTokens } from 'shiki';

const [tourPath, outDir] = process.argv.slice(2);
if (!tourPath || !outDir) {
  console.error('usage: node tools/build_tour.mjs <tour.json> <out-dir>');
  process.exit(1);
}
const here = path.dirname(fileURLToPath(import.meta.url));  // keeps spaces and non-ASCII letters
const tour = JSON.parse(readFileSync(tourPath, 'utf8'));
const LANGS = {
  '.ts': 'ts', '.tsx': 'tsx', '.js': 'js', '.jsx': 'jsx', '.mjs': 'js', '.py': 'python', '.go': 'go', '.java': 'java',
  '.kt': 'kotlin', '.cs': 'csharp', '.rb': 'ruby', '.rs': 'rust', '.php': 'php', '.sql': 'sql', '.json': 'json',
  '.yml': 'yaml', '.yaml': 'yaml', '.md': 'markdown', '.html': 'html', '.css': 'css', '.sh': 'bash',
  '.cjs': 'js', '.kts': 'kotlin', '.scss': 'scss', '.vue': 'vue', '.svelte': 'svelte', '.swift': 'swift', '.dart': 'dart',
  '.scala': 'scala', '.c': 'c', '.h': 'c', '.cpp': 'cpp', '.hpp': 'cpp', '.xml': 'xml', '.proto': 'proto',
  '.graphql': 'graphql', '.gql': 'graphql', '.tf': 'hcl', '.toml': 'toml', '.ini': 'ini', '.gradle': 'groovy',
};
// Files known by their whole name.
const NAMES = { Dockerfile: 'docker', Makefile: 'make', Jenkinsfile: 'groovy', Gemfile: 'ruby', Rakefile: 'ruby' };
const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const git = (repoPath, ...args) => execFileSync('git', ['-C', repoPath, ...args], { encoding: 'utf8', maxBuffer: 64 << 20 });

async function highlight(source, file) {
  const lang = NAMES[path.basename(file)] ?? LANGS[path.extname(file)] ?? 'text';
  // An unknown language falls back to plain text instead of failing the whole tour.
  const { tokens } = await codeToTokens(source, { lang, theme: 'dark-plus' })
    .catch(() => codeToTokens(source, { lang: 'text', theme: 'dark-plus' }));
  return tokens.map((line) =>
    line.map((t) => `<span style="color:${t.color}${t.fontStyle & 1 ? ';font-style:italic' : ''}">${escape(t.content)}</span>`).join(''),
  );
}

// Children of one folder: sub-folders first, then files, sorted the way VS Code sorts them.
function listChildren(allPaths, folder) {
  const prefix = folder ? `${folder}/` : '';
  const folders = new Set();
  const files = new Set();
  for (const p of allPaths) {
    if (!p.startsWith(prefix)) continue;
    const rest = p.slice(prefix.length);
    const slash = rest.indexOf('/');
    if (slash === -1) files.add(rest);
    else folders.add(rest.slice(0, slash));
  }
  const sort = (a, b) => a.localeCompare(b, 'en', { sensitivity: 'base' });
  return [
    ...[...folders].sort(sort).map((name) => ({ name, type: 'folder', path: prefix + name })),
    ...[...files].sort(sort).map((name) => ({ name, type: 'file', path: prefix + name })),
  ];
}

// Sequence diagrams: from tour.json, or diagrams.json next to it (scripts/make_scenes.py writes it from the storyboard).
const diagramsFile = path.join(path.dirname(path.resolve(tourPath)), 'diagrams.json');
const diagrams = tour.diagrams ?? (existsSync(diagramsFile) ? JSON.parse(readFileSync(diagramsFile, 'utf8')) : {});
// Terminal scenes (command and recorded output per scene id), also written by make_scenes.py.
const terminalsFile = path.join(path.dirname(path.resolve(tourPath)), 'terminals.json');
const terminals = tour.terminals ?? (existsSync(terminalsFile) ? JSON.parse(readFileSync(terminalsFile, 'utf8')) : {});
// System maps (services, how they talk, a request travelling between them), also written by make_scenes.py.
const mapsFile = path.join(path.dirname(path.resolve(tourPath)), 'maps.json');
const maps = tour.maps ?? (existsSync(mapsFile) ? JSON.parse(readFileSync(mapsFile, 'utf8')) : {});
// The project's brand colour (scripts/brand.py, through make_scenes.py): the highlight, the map, the notes.
const brandFile = path.join(path.dirname(path.resolve(tourPath)), 'brand.json');
const brand = tour.brand ?? (existsSync(brandFile) ? JSON.parse(readFileSync(brandFile, 'utf8')) : {});
delete brand.logo;  // the tour shows no logo; the intro and outro cards do
const data = { title: tour.title ?? 'Code tour', workspace: tour.workspace ?? 'WORKSPACE', repos: {}, files: {}, diagrams, terminals, maps, brand };
for (const [key, entry] of Object.entries(tour.repos)) {
  // Repo paths may be relative to tour.json.
  const repo = { ...entry, path: path.resolve(path.dirname(path.resolve(tourPath)), entry.path) };
  const ref = repo.ref ?? tour.ref ?? 'HEAD';
  const tourFiles = tour.files.filter(([r]) => r === key).map(([, f]) => f);
  // KT Studio's own settings (.kt-studio/) are committed in the project but are not part of the code
  // being explained: keep them out of the file tree.
  const ours = (f) => /^\.kt-studio\//.test(f);
  const allPaths = git(repo.path, 'ls-tree', '-r', '--name-only', ref).split('\n').filter(Boolean)
    .filter((f) => !ours(f) || tourFiles.includes(f));
  const openFolders = new Set(['']);
  for (const f of tourFiles) {
    const parts = f.split('/');
    for (let i = 1; i < parts.length; i++) openFolders.add(parts.slice(0, i).join('/'));
  }
  const tree = {};
  for (const folder of openFolders) tree[folder] = listChildren(allPaths, folder);
  data.repos[key] = {
    dir: path.basename(repo.path),
    label: repo.label ?? key,
    sha: git(repo.path, 'rev-parse', '--short=8', ref).trim(),
    // ref HEAD shows the branch it points at, as VS Code does.
    // A pinned sha shows the branch it was approved from (`branch` in tour.json), as VS Code would.
    branch: repo.branch ?? (ref === 'HEAD' ? git(repo.path, 'rev-parse', '--abbrev-ref', 'HEAD').trim() : ref).replace(/^origin\//, ''),
    tree,
  };
  for (const f of tourFiles) {
    // `./` reads the path from repo.path, which may be a folder inside a bigger repo (a monorepo),
    // the same way ls-tree above lists it. A bare `${ref}:${f}` would read from the repo's top.
    const source = git(repo.path, 'show', `${ref}:./${f}`);
    data.files[`${key}:${f}`] = { repo: key, path: f, lines: await highlight(source.replace(/\n$/, ''), f) };
  }
}

mkdirSync(outDir, { recursive: true });
for (const asset of ['ide.html', 'ide.css', 'ide.js', 'map.css', 'map.js']) copyFileSync(path.join(here, '..', 'ide', asset), path.join(outDir, asset));
writeFileSync(path.join(outDir, 'data.js'), `window.TOUR = ${JSON.stringify(data)};\n`);
console.log(Object.entries(data.files).map(([k, v]) => `${k} (${v.lines.length} lines)`).join('\n'));
if (Object.keys(diagrams).length) console.log(`diagrams: ${Object.keys(diagrams).join(', ')}`);
if (Object.keys(maps).length) console.log(`maps: ${Object.keys(maps).join(', ')}`);
if (Object.keys(terminals).length) console.log(`terminal scenes: ${Object.keys(terminals).join(', ')}`);
