// A VS Code look-alike driven by a script: the demo calls window.ide.* while the narration plays.
(() => {
  const TOUR = window.TOUR;
  const $ = (selector) => document.querySelector(selector);
  // File icon (colour class, label) and the language name in the status bar, by extension.
  const KINDS = {
    ts: ['ts', 'TS'], tsx: ['tsx', 'TSX'], js: ['js', 'JS'], mjs: ['js', 'JS'], cjs: ['js', 'JS'], jsx: ['tsx', 'JSX'],
    py: ['py', 'PY'], json: ['json', '{}'], md: ['md', 'M↓'], css: ['css', '#'], scss: ['css', '#'], html: ['html', '<>'],
    yml: ['yml', 'YML'], yaml: ['yml', 'YML'], go: ['go', 'GO'], java: ['java', 'J'], kt: ['kt', 'KT'], kts: ['kt', 'KT'],
    cs: ['cs', 'C#'], rb: ['rb', 'RB'], rs: ['rs', 'RS'], php: ['php', 'PHP'], sql: ['sql', 'SQL'], sh: ['sh', '$'],
    vue: ['vue', 'V'], svelte: ['svelte', 'S'], swift: ['swift', 'SW'], dart: ['dart', 'D'], scala: ['java', 'SC'],
    c: ['c', 'C'], h: ['c', 'H'], cpp: ['c', 'C++'], hpp: ['c', 'H++'], xml: ['html', '<>'], proto: ['other', 'PB'],
    graphql: ['graphql', 'GQ'], tf: ['tf', 'TF'],
  };
  const LANGUAGES = {
    ts: 'TypeScript', tsx: 'TypeScript JSX', js: 'JavaScript', mjs: 'JavaScript', cjs: 'JavaScript', jsx: 'JavaScript JSX',
    py: 'Python', json: 'JSON', md: 'Markdown', css: 'CSS', scss: 'SCSS', html: 'HTML', yml: 'YAML', yaml: 'YAML', go: 'Go',
    java: 'Java', kt: 'Kotlin', kts: 'Kotlin', cs: 'C#', rb: 'Ruby', rs: 'Rust', php: 'PHP', sql: 'SQL', sh: 'Shell Script',
    vue: 'Vue', svelte: 'Svelte', swift: 'Swift', dart: 'Dart', scala: 'Scala', c: 'C', h: 'C', cpp: 'C++', hpp: 'C++',
    xml: 'XML', proto: 'Protocol Buffers', graphql: 'GraphQL', tf: 'Terraform',
  };
  const state = { open: new Set(), seen: new Set(), selected: null, tabs: [], active: null, tips: new Map() };

  const rowId = (repo, path) => `${repo}:${path}`;
  const extOf = (name) => (name.match(/\.([a-z]+)$/) ?? [, ''])[1];
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

  function animateScroll(element, to, ms = 700) {
    const from = element.scrollTop;
    const start = performance.now();
    return new Promise((resolve) => {
      const step = (now) => {
        const k = Math.min(1, (now - start) / ms);
        element.scrollTop = from + (to - from) * ease(k);
        if (k < 1) requestAnimationFrame(step);
        else resolve();
      };
      requestAnimationFrame(step);
    });
  }

  // ── explorer ────────────────────────────────────────────────────────

  function renderTree() {
    const tree = $('#tree');
    const scroll = tree.scrollTop;
    tree.innerHTML = '';
    for (const [key, repo] of Object.entries(TOUR.repos)) {
      tree.appendChild(makeRow(key, '', repo.dir, 'folder', 0));
      if (state.open.has(rowId(key, ''))) appendChildren(tree, key, '', 1);
    }
    tree.scrollTop = scroll;
  }

  // Folders always show; of the files, only the ones the tour opens. The rest fold into one row so a
  // folder with 150 files does not bury the one that matters.
  function appendChildren(container, key, folder, depth) {
    let hidden = 0;
    for (const child of TOUR.repos[key].tree[folder] ?? []) {
      if (child.type === 'file' && !TOUR.files[rowId(key, child.path)]) {
        hidden += 1;
        continue;
      }
      container.appendChild(makeRow(key, child.path, child.name, child.type, depth));
      if (child.type === 'folder' && state.open.has(rowId(key, child.path))) appendChildren(container, key, child.path, depth + 1);
    }
    if (hidden) {
      const more = document.createElement('div');
      more.className = 'row more';
      more.style.paddingLeft = `${8 + depth * 18 + 22}px`;
      more.textContent = `+ ${hidden} more file${hidden === 1 ? '' : 's'}`;
      container.appendChild(more);
    }
  }

  function collapseOthers(key) {
    for (const id of [...state.open]) if (!id.startsWith(`${key}:`)) state.open.delete(id);
  }

  function makeRow(key, path, name, type, depth) {
    const id = rowId(key, path);
    const row = document.createElement('div');
    const isOpen = state.open.has(id);
    row.className = `row${depth === 0 ? ' root' : ''}${state.selected === id ? ' sel' : ''}`;
    row.dataset.id = id;
    row.style.paddingLeft = `${8 + depth * 18}px`;
    if (!state.seen.has(id)) {
      state.seen.add(id);
      if (depth > 0) row.animate([{ opacity: 0, transform: 'translateX(-6px)' }, { opacity: 1 }], { duration: 260, easing: 'ease-out' });
    }
    if (type === 'folder') {
      row.innerHTML = `<svg class="chev${isOpen ? ' open' : ''}" viewBox="0 0 16 16"><path d="m6 4 4 4-4 4"/></svg>`
        + (depth === 0 ? '' : `<span class="ficon folder${isOpen ? ' open' : ''}"></span>`);
    } else {
      const [kind, label] = KINDS[extOf(name)] ?? ['other', ''];
      row.innerHTML = `<span class="spacer"></span><span class="ficon ${kind}">${label}</span>`;
    }
    row.insertAdjacentHTML('beforeend', `<span class="name">${name}</span>`);
    if (state.tips.has(id)) row.insertAdjacentHTML('beforeend', `<span class="tip">${state.tips.get(id)}</span>`);
    row.addEventListener('click', () => onRowClick(key, path, type));
    return row;
  }

  function onRowClick(key, path, type) {
    const id = rowId(key, path);
    state.selected = id;
    if (type === 'folder' && TOUR.repos[key].tree[path]) {
      if (state.open.has(id)) state.open.delete(id);
      else {
        if (path === '') collapseOthers(key);
        state.open.add(id);
      }
    }
    renderTree();
    if (type === 'file' && TOUR.files[id]) open(key, path);
  }

  function scrollTreeTo(id) {
    const row = document.querySelector(`.row[data-id="${CSS.escape(id)}"]`);
    if (!row) return Promise.resolve();
    const tree = $('#tree');
    const visible = row.offsetTop > tree.scrollTop + 30 && row.offsetTop < tree.scrollTop + tree.clientHeight - 60;
    if (visible) return Promise.resolve();
    const target = Math.max(0, row.offsetTop - tree.clientHeight * 0.4);
    return animateScroll(tree, target, 900);
  }

  // ── editor ──────────────────────────────────────────────────────────

  function renderTabs() {
    $('#tabs').innerHTML = state.tabs.map((id) => {
      const file = TOUR.files[id];
      const name = file.path.split('/').pop();
      const [kind, label] = KINDS[extOf(name)] ?? ['other', ''];
      return `<div class="tab${id === state.active ? ' on' : ''}"><span class="ficon ${kind}">${label}</span>${name}`
        + `<span class="repo">${TOUR.repos[file.repo].label}</span><span class="x">×</span></div>`;
    }).join('');
  }

  async function open(key, path) {
    const id = rowId(key, path);
    const file = TOUR.files[id];
    const repo = TOUR.repos[key];
    const parts = path.split('/');
    collapseOthers(key);
    state.open.add(rowId(key, ''));
    for (let i = 1; i < parts.length; i++) state.open.add(rowId(key, parts.slice(0, i).join('/')));
    state.selected = id;
    renderTree();
    if (!state.tabs.includes(id)) state.tabs.push(id);
    state.active = id;
    $('#terminal').classList.remove('tall');   // a file is on screen now: the terminal makes room for it
    renderTabs();

    const name = parts.at(-1);
    $('#title').textContent = `${name} - ${repo.dir} - ${TOUR.workspace} (Workspace)`;
    $('#crumbs').innerHTML = [repo.dir, ...parts].map((part, i, all) =>
      `<span class="${i === all.length - 1 ? 'last' : ''}">${part}</span>`).join('<span class="sep">›</span>');
    $('#st-branch').textContent = `⎇ ${repo.branch ?? 'main'}`;
    $('#st-sha').textContent = repo.sha;
    $('#st-lang').textContent = LANGUAGES[extOf(name)] ?? 'Plain Text';
    $('#st-pos').textContent = 'Ln 1, Col 1';
    $('#welcome').style.opacity = '0';
    hideSequence();

    // Swap in place, like a real tab switch: any fade here reads as a blink on video.
    const code = $('#code');
    code.classList.remove('focusing');
    code.innerHTML = file.lines.map((html, i) =>
      `<div class="ln" data-n="${i + 1}"><span class="no">${i + 1}</span><span class="src">${html || ' '}</span></div>`).join('');
    code.scrollTop = 0;
    code.classList.add('ready');
    await scrollTreeTo(id);
  }

  function lineEl(n) {
    return document.querySelector(`#code .ln[data-n="${n}"]`);
  }

  async function focus(ranges, note, options = {}) {
    unfocus();
    const code = $('#code');
    for (const [from, to] of ranges) {
      for (let n = from; n <= to; n++) lineEl(n)?.classList.add('hl');
    }
    code.classList.add('focusing');
    const [first] = ranges[0];
    $('#st-pos').textContent = `Ln ${first}, Col 1`;
    // Far-apart ranges would push the note off screen, so it then sits under the first one.
    const last = ranges.at(-1)[1] - first < 25 ? ranges.at(-1)[1] : ranges[0][1];
    // The highlighted lines and their note must be fully visible. A terminal left open by the scene before
    // takes half the height: when they do not fit above it, close it first (the code is this scene's subject).
    const need = () => lineEl(last).offsetTop + lineEl(last).offsetHeight - lineEl(first).offsetTop + (note ? 120 : 0) + 30;
    if ($('#terminal').classList.contains('on') && need() > code.clientHeight) {
      terminalHide();
      await new Promise((resolve) => setTimeout(resolve, 500));   // the panel's height transition
    }
    // Normally a little context above the first line; less when space is tight, so the end stays in view.
    const offset = options.offset ?? Math.max(24, Math.min(150, code.clientHeight - need()));
    const top = lineEl(first).offsetTop - offset;
    await animateScroll(code, Math.max(0, top), options.ms ?? 1200);
    if (note) {
      // Let the eye land on the code before the explanation appears.
      await new Promise((resolve) => setTimeout(resolve, 500));
      const file = TOUR.files[state.active];
      const where = `${file.path.split('/').pop()}:${ranges[0][0]}`;
      lineEl(last).insertAdjacentHTML('afterend',
        `<div class="note"><div class="avatar">KT</div><div><div class="who">KT guide · ${where}</div><div class="what">${note}</div></div></div>`);
    }
  }

  // A Ctrl+hover look on one token, for "follow the call" jumps. Monospace, so columns map to pixels.
  function linkToken(n, token) {
    document.getElementById('kt-link')?.remove();
    const line = lineEl(n);
    const src = line.querySelector('.src');
    // Columns as drawn: a tab reaches the next multiple of the tab size (ide.css sets 4).
    const before = src.textContent.slice(0, src.textContent.indexOf(token));
    let col = 0;
    for (const ch of before) col = ch === '\t' ? col + 4 - (col % 4) : col + 1;
    const probe = document.createElement('span');
    probe.textContent = 'x'.repeat(40);
    src.appendChild(probe);
    const charWidth = probe.getBoundingClientRect().width / 40;
    probe.remove();
    const link = document.createElement('div');
    link.id = 'kt-link';
    Object.assign(link.style, {
      left: `${src.offsetLeft + col * charWidth}px`,
      top: `${line.offsetTop}px`,
      width: `${token.length * charWidth}px`,
    });
    $('#code').appendChild(link);
  }

  function tip(id, text) {
    state.tips.set(id, text);
    renderTree();
  }

  function clearTips() {
    state.tips.clear();
    renderTree();
  }

  function unfocus() {
    document.getElementById('kt-link')?.remove();
    $('#code').classList.remove('focusing');
    document.querySelectorAll('#code .ln.hl').forEach((el) => el.classList.remove('hl'));
    document.querySelectorAll('#code .note').forEach((el) => el.remove());
  }

  // ── chrome ──────────────────────────────────────────────────────────

  function flow(journey, step) {
    const keys = Object.keys(TOUR.repos);
    const at = step === 'all' ? keys.length : keys.indexOf(step);
    $('#flow').innerHTML = (journey ? `<span class="journey">${journey}</span>` : '')
      + keys.map((key, i) => {
        const cls = step === 'all' || i === at ? 'now' : i < at ? 'done' : '';
        return `<span class="pill ${cls}">${TOUR.repos[key].label}</span>`;
      }).join('<span class="arrow">›</span>');
  }

  function welcome(title, sub) {
    $('#welcome-title').textContent = title;
    $('#welcome-sub').innerHTML = sub;
    // A closing title over an open file: fade the code out so the title stands on the empty editor.
    unfocus();
    hideSequence();
    $('#code').classList.remove('ready');
    $('#welcome').style.opacity = '1';
  }

  // ── sequence diagram ────────────────────────────────────────────────
  // TOUR.diagrams[name] = { title?, actors: ['User' | { name, sub }], steps: [{ from, to, label, reply? }] }
  // Steps start hidden; sequenceStep(first, last) lights a range, earlier steps stay as "done".

  const SVG = 'http://www.w3.org/2000/svg';
  const el = (tag, attrs = {}, text) => {
    const node = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function sequence(name) {
    // Already up (the scene before used it too): keep it, with its lit steps.
    if (state.diagram === name && $('#seq').classList.contains('on')) return;
    state.diagram = name;
    const d = (TOUR.diagrams ?? {})[name];
    if (!d) throw new Error(`No diagram "${name}" in the tour (diagrams.json)`);
    const box = $('#code-wrap').getBoundingClientRect();
    const W = box.width;
    const H = box.height;
    const actors = d.actors.map((a) => (typeof a === 'string' ? { name: a } : a));
    const pad = 40;
    const col = (W - 2 * pad) / actors.length;
    const x = Object.fromEntries(actors.map((a, i) => [a.name, pad + col * (i + 0.5)]));
    const top = d.title ? 64 : 36;
    const boxH = actors.some((a) => a.sub) ? 76 : 60;
    const boxW = Math.min(250, col - 36);
    const first = top + boxH + 58;
    const row = Math.min(86, (H - first - 50) / Math.max(1, d.steps.length));

    const svg = el('svg', { viewBox: `0 0 ${W} ${H}` });
    if (d.title) svg.appendChild(el('text', { x: pad, y: 38, class: 'dtitle' }, d.title.toUpperCase()));
    for (const a of actors) {
      svg.appendChild(el('line', { class: 'life', x1: x[a.name], y1: top + boxH, x2: x[a.name], y2: H - 24 }));
      const g = el('g', { class: 'actor' });
      g.appendChild(el('rect', { x: x[a.name] - boxW / 2, y: top, width: boxW, height: boxH, rx: 10 }));
      g.appendChild(el('text', { x: x[a.name], y: top + (a.sub ? 32 : 38), 'text-anchor': 'middle', class: 'name' }, a.name));
      if (a.sub) g.appendChild(el('text', { x: x[a.name], y: top + 58, 'text-anchor': 'middle', class: 'sub' }, a.sub));
      svg.appendChild(g);
    }
    d.steps.forEach((step, i) => {
      if (!(step.from in x) || !(step.to in x)) throw new Error(`Diagram "${name}" step ${i + 1}: unknown actor`);
      const y = first + row * i;
      const x1 = x[step.from];
      const x2 = x[step.to];
      const g = el('g', { class: `msg${step.reply ? ' reply' : ''}`, 'data-step': i + 1 });
      if (x1 === x2) {
        // A call to itself: a small loop on the right of the lifeline.
        const path = `M ${x1} ${y - 12} h 70 v 30 h -64`;
        g.appendChild(el('path', { class: 'wire', d: path, style: '--len: 164' }));
        g.appendChild(el('polygon', { class: 'head', points: `${x1 + 4},${y + 18} ${x1 + 16},${y + 11} ${x1 + 16},${y + 25}` }));
        g.appendChild(el('text', { x: x1 + 84, y: y + 8, class: 'label' }, step.label));
      } else {
        const dir = Math.sign(x2 - x1);
        const end = x2 - dir * 4;
        g.appendChild(el('line', { class: 'wire', x1, y1: y, x2: end - dir * 10, y2: y, style: `--len: ${Math.abs(end - x1)}` }));
        g.appendChild(el('polygon', { class: 'head', points: `${end},${y} ${end - dir * 16},${y - 8} ${end - dir * 16},${y + 8}` }));
        g.appendChild(el('text', { x: (x1 + x2) / 2, y: y - 14, 'text-anchor': 'middle', class: 'label' }, step.label));
      }
      const badge = el('g', { class: 'badge' });
      badge.appendChild(el('circle', { cx: x1, cy: y, r: 14 }));
      badge.appendChild(el('text', { x: x1, y: y + 5, 'text-anchor': 'middle' }, String(i + 1)));
      g.appendChild(badge);
      svg.appendChild(g);
    });
    const layer = $('#seq');
    layer.replaceChildren(svg);
    layer.classList.add('on');
  }

  function sequenceStep(first, last = first) {
    document.querySelectorAll('#seq .msg').forEach((g) => {
      const n = Number(g.dataset.step);
      g.classList.toggle('done', n < first);
      g.classList.toggle('now', n >= first && n <= last);
    });
  }

  function hideSequence() {
    $('#seq').classList.remove('on');
    state.diagram = null;
  }

  // ── terminal ────────────────────────────────────────────────────────
  // Scenes of kind "terminal" show a real command and the output it really printed when the agent ran
  // it before recording (TOUR.terminals, from the storyboard). Nothing runs here.

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const escHtml = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  function terminalLine(cwd) {
    const body = $('#term-body');
    body.querySelector('.caret')?.remove();
    const line = document.createElement('div');
    line.innerHTML = `<span class="prompt">dev@laptop <b>${escHtml(cwd || '~')}</b> $ </span><span class="cmd"></span><span class="caret"></span>`;
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
    return line;
  }

  function terminalShow(cwd) {
    $('#terminal').classList.add('on');
    $('#terminal').classList.toggle('tall', !state.active);
    $('#term-cwd').textContent = cwd || '';
    if (!$('#term-body').lastElementChild?.querySelector('.caret')) terminalLine(cwd);
  }

  function terminalHide() {
    $('#terminal').classList.remove('on');
  }

  function terminalClear() {
    $('#term-body').innerHTML = '';
  }

  // Types the scene's command, then prints its output line by line, marking the parts the voice talks about.
  async function terminalRun(id, msPerChar = 40, msPerLine = 35) {
    const t = (TOUR.terminals || {})[id];
    if (!t) throw new Error(`no terminal data for scene ${id}`);
    terminalShow(t.cwd);
    const line = $('#term-body').lastElementChild;
    const cmd = line.querySelector('.cmd');
    for (const ch of t.cmd) {
      cmd.textContent += ch;
      await sleep(msPerChar);
    }
    await sleep(350);
    line.querySelector('.caret')?.remove();
    const body = $('#term-body');
    let html;
    for (const text of (t.output || '').replace(/\n$/, '').split('\n')) {
      html = escHtml(text);
      for (const mark of t.marks || []) html = html.split(escHtml(mark)).join(`<span class="mark">${escHtml(mark)}</span>`);
      const out = document.createElement('div');
      out.innerHTML = html || '&nbsp;';
      body.appendChild(out);
      await animateScroll(body, body.scrollHeight - body.clientHeight, 120);
      await sleep(msPerLine);
    }
    terminalLine(t.cwd);
    await animateScroll(body, body.scrollHeight - body.clientHeight, 200);
  }

  // Files ranked for a query: the exact name, then names that start with it, contain it, then paths that
  // contain it ("payments/client" picks one client among several).
  function paletteRank(query) {
    const q = query.toLowerCase().replace(/\s+/g, '');
    const ranked = [];
    for (const id of Object.keys(TOUR.files)) {
      const full = id.toLowerCase();
      const base = full.split('/').pop();
      const stem = base.replace(/\.[^.]+$/, '');
      const score = base === q || stem === q ? 4 : base.startsWith(q) ? 3 : base.includes(q) ? 2 : full.includes(q) ? 1 : 0;
      if (score) ranked.push({ id, score });
    }
    return ranked.sort((a, b) => b.score - a.score || a.id.length - b.id.length);
  }

  function paletteMatches(query) {
    return paletteRank(query).map((m) => m.id);
  }

  function renderPalette() {
    const matches = paletteMatches($('#palette-input').value);
    $('#palette-list').innerHTML = matches.slice(0, 6).map((id, i) => {
      const file = TOUR.files[id];
      const name = file.path.split('/').pop();
      const [kind, label] = KINDS[extOf(name)] ?? ['other', ''];
      return `<div class="item${i === 0 ? ' on' : ''}"><span class="ficon ${kind}">${label}</span>${name}`
        + `<span class="dir">${TOUR.repos[file.repo].dir}/${file.path.split('/').slice(0, -1).join('/')}</span></div>`;
    }).join('');
  }

  function showPalette() {
    $('#palette').hidden = false;
    $('#palette-input').value = '';
    renderPalette();
    $('#palette-input').focus();
  }

  $('#palette-input').addEventListener('input', renderPalette);
  $('#palette-input').addEventListener('keydown', (event) => {
    if (event.key !== 'Enter') return;
    const [first] = paletteMatches(event.target.value);
    $('#palette').hidden = true;
    if (first) open(...first.split(/:(.*)/s).slice(0, 2));
  });

  // The project's brand colour, when it has one: the highlight bar, the notes, the map's active path.
  if (TOUR.brand?.accent) {
    const root = document.documentElement.style;
    root.setProperty('--focus-bar', TOUR.brand.accent);
    root.setProperty('--focus', `color-mix(in srgb, ${TOUR.brand.accent} 12%, transparent)`);
    if (TOUR.brand.accentSoft) root.setProperty('--accent-soft', TOUR.brand.accentSoft);
  }
  $('#ws-name').textContent = `${TOUR.workspace} (WORKSPACE)`;
  renderTree();
  flow('', null);
  window.ide = { open, focus, unfocus, flow, welcome, showPalette, scrollTreeTo, linkToken, tip, clearTips, sequence, sequenceStep, hideSequence, rank: paletteRank,
    terminalShow, terminalHide, terminalClear, terminalRun };

  // ?view: scale the 1920x1080 stage to the window so a person can browse it outside a recording.
  if (new URLSearchParams(location.search).has('view')) {
    const fit = () => { document.documentElement.style.zoom = Math.min(innerWidth / 1920, innerHeight / 1080); };
    addEventListener('resize', fit);
    fit();
    flow('', 'all');
    welcome(TOUR.title ?? 'Code tour', 'Click a repo folder to explore · click a tour file to open it');
  }
})();
