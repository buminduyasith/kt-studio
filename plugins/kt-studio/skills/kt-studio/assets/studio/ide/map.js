// System maps for the code tour: the parts of a system, how they talk, and one request travelling
// between them, shown BEFORE the code so a newcomer sees the whole picture working.
//
// TOUR.maps[name] = {
//   title?,
//   nodes: [{ id, label, sub?, kind?, col?, row? }],
//     kind: person | app | service | job | database | cache | queue | external | state (default service)
//     col, row: the place on a small grid (0-based); left to right is the direction of the main flow
//   groups?: [{ label, nodes: [ids] }]: a boundary drawn around nodes ("Acme cloud", "outside our system")
//   steps: [{ from, to, label, kind?, payload?, state? }],
//     to: one node id, or a list for a fan-out (an event that reaches several consumers at once)
//     kind: call (default) | reply | event (async, through a queue or topic) | write | read | fail
//     payload: a short text that travels on the message ("orderId 1042, 20.00")
//     state: { node, text }: the data at rest after this step ("refund PENDING" under the database)
// }
//
// Nothing moves on its own: the script calls these on the narrator's words, and every animation has a
// fixed length (Web Animations, awaited), so a take always looks the same.
//   ide.map(name, { all })        draw it; nodes stay hidden until revealed, unless all
//   ide.mapReveal(ids)            bring nodes in, one after another
//   ide.mapStep(n, ms)            play step n: its link lights, the message travels, the target reacts
//   ide.mapFocus(ids | null)      dim everything but these nodes and the links between them
//   ide.mapZoom(id)               zoom into one node and fade, right before its code opens
//   ide.mapReplay(ms)             the whole journey again, quickly, for the recap
//   ide.mapOverview()             every node and every link at once, still: the high-level design picture
//   ide.hideMap()
//   ide.locate(name, id)          a small "you are here" map in the corner of the code; ide.hideLocator()
(() => {
  const SVG = 'http://www.w3.org/2000/svg';
  const $ = (selector) => document.querySelector(selector);
  const el = (tag, attrs = {}, text) => {
    const node = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const EASE = 'cubic-bezier(.45, 0, .25, 1)';
  const TAG = { person: 'USER', app: 'APP', service: 'SERVICE', job: 'JOB', database: 'DATABASE', cache: 'CACHE',
    queue: 'QUEUE', external: 'EXTERNAL', state: '' };
  const STEP_KINDS = new Set(['call', 'reply', 'event', 'write', 'read', 'fail']);
  const cur = { name: null, map: null, geo: null, svg: null, shown: new Set(), played: 0 };

  function host() {
    let layer = $('#map');
    if (!layer) {
      layer = document.createElement('div');
      layer.id = 'map';
      $('#code-wrap').appendChild(layer);
    }
    return layer;
  }

  function getMap(name) {
    const m = (window.TOUR.maps ?? {})[name];
    if (!m) throw new Error(`No map "${name}" in the tour (maps.json)`);
    return m;
  }

  // Where each node sits, and its size. The grid comes from col/row; nodes without them go left to right.
  function layout(m, W, H, small = false) {
    const nodes = m.nodes.map((n, i) => ({ kind: 'service', col: i, row: 0, ...n }));
    const cols = Math.max(...nodes.map((n) => n.col)) + 1;
    const rows = Math.max(...nodes.map((n) => n.row)) + 1;
    const pad = small ? 10 : 46;
    const top = small ? 8 : (m.title ? 78 : 40);
    const bottom = small ? 8 : 104;  // the step strip
    const cw = (W - 2 * pad) / cols;
    const ch = (H - top - bottom) / rows;
    const geo = {};
    for (const n of nodes) {
      const w = small ? Math.min(cw - 12, 104) : Math.min(cw - 56, n.kind === 'state' ? 200 : 250);
      const h = small ? 26 : n.kind === 'state' ? 64 : n.kind === 'person' ? 96 : 92;
      geo[n.id] = { ...n, x: pad + cw * (n.col + 0.5), y: top + ch * (n.row + 0.5), w, h };
    }
    return geo;
  }

  // The point where the line from a's centre to b's centre leaves a's box.
  function edge(a, b) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const t = Math.min((a.w / 2 + 6) / Math.abs(dx || 1e-6), (a.h / 2 + 6) / Math.abs(dy || 1e-6));
    return { x: a.x + dx * t, y: a.y + dy * t };
  }

  const targets = (step) => (Array.isArray(step.to) ? step.to : [step.to]);

  // The two ends of one link of a step; calls and replies between the same pair run side by side.
  function ends(m, geo, from, to) {
    const a = geo[from];
    const b = geo[to];
    const both = m.steps.some((s) => s.from === to && targets(s).includes(from));
    let p = edge(a, b);
    let q = edge(b, a);
    if (both) {
      const len = Math.hypot(q.x - p.x, q.y - p.y) || 1;
      const side = from < to ? 1 : -1;
      const ox = (-(q.y - p.y) / len) * 12 * side;
      const oy = ((q.x - p.x) / len) * 12 * side;
      p = { x: p.x + ox, y: p.y + oy };
      q = { x: q.x + ox, y: q.y + oy };
    }
    return { p, q };
  }

  function drawNode(g, n, small) {
    const { x, y, w, h, kind } = n;
    const box = el('g', { class: `node k-${kind}`, 'data-id': n.id });
    if (kind === 'database') {
      const r = small ? 4 : 12;
      box.appendChild(el('path', { class: 'shape', d: `M ${x - w / 2} ${y - h / 2 + r} a ${w / 2} ${r} 0 0 1 ${w} 0 v ${h - 2 * r} a ${w / 2} ${r} 0 0 1 ${-w} 0 z` }));
      box.appendChild(el('path', { class: 'rim', d: `M ${x - w / 2} ${y - h / 2 + r} a ${w / 2} ${r} 0 0 0 ${w} 0` }));
    } else if (kind === 'person') {
      box.appendChild(el('rect', { class: 'shape', x: x - w / 2, y: y - h / 2, width: w, height: h, rx: h / 2 }));
    } else if (kind === 'state') {
      box.appendChild(el('rect', { class: 'shape', x: x - w / 2, y: y - h / 2, width: w, height: h, rx: h / 2 }));
    } else {
      box.appendChild(el('rect', { class: 'shape', x: x - w / 2, y: y - h / 2, width: w, height: h, rx: small ? 4 : 12 }));
      if (kind === 'queue' && !small) {
        for (let i = 1; i <= 3; i++) box.appendChild(el('line', { class: 'slot', x1: x + w / 2 - 14 * i, y1: y - h / 2 + 14, x2: x + w / 2 - 14 * i, y2: y + h / 2 - 14 }));
      }
    }
    if (small) {
      const fit = Math.max(4, Math.floor(w / 6.6));
      box.appendChild(el('text', { x, y: y + 4, 'text-anchor': 'middle', class: 'name' }, n.label.length > fit ? `${n.label.slice(0, fit - 1)}…` : n.label));
    } else {
      const tag = TAG[kind] ?? '';
      if (tag) box.appendChild(el('text', { x, y: y - h / 2 + 22, 'text-anchor': 'middle', class: 'tag' }, tag));
      box.appendChild(el('text', { x, y: y + (tag ? 10 : 8) - (n.sub ? 6 : 0), 'text-anchor': 'middle', class: 'name' }, n.label));
      if (n.sub) box.appendChild(el('text', { x, y: y + (tag ? 32 : 30), 'text-anchor': 'middle', class: 'sub' }, n.sub));
      box.appendChild(el('g', { class: 'state', 'data-for': n.id }));
    }
    g.appendChild(box);
    return box;
  }

  function map(name, { all = false } = {}) {
    if (cur.name === name && $('#map')?.classList.contains('on')) return;  // already up: keep what it shows
    const m = getMap(name);
    const layer = host();
    // Layout pixels, not screen pixels: the ?view page is zoomed to fit the window.
    const W = $('#code-wrap').clientWidth;
    const H = $('#code-wrap').clientHeight;
    const geo = layout(m, W, H);
    for (const s of m.steps) {
      for (const id of [s.from, ...targets(s)]) {
        if (!(id in geo)) throw new Error(`Map "${name}": a step names an unknown node (${id})`);
      }
    }
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}` });
    if (m.title) svg.appendChild(el('text', { x: 46, y: 46, class: 'mtitle' }, m.title.toUpperCase()));
    const groups = el('g', { class: 'groups' });
    for (const grp of m.groups ?? []) {
      const members = grp.nodes.map((id) => geo[id]).filter(Boolean);
      if (!members.length) throw new Error(`Map "${name}": group "${grp.label}" has no known nodes`);
      const x1 = Math.min(...members.map((n) => n.x - n.w / 2)) - 28;
      const x2 = Math.max(...members.map((n) => n.x + n.w / 2)) + 28;
      const y1 = Math.min(...members.map((n) => n.y - n.h / 2)) - 44;
      const y2 = Math.max(...members.map((n) => n.y + n.h / 2)) + 28;
      const g = el('g', { class: 'group' });
      g.appendChild(el('rect', { x: x1, y: y1, width: x2 - x1, height: y2 - y1, rx: 16 }));
      g.appendChild(el('text', { x: x1 + 18, y: y1 + 26, class: 'glabel' }, grp.label.toUpperCase()));
      groups.appendChild(g);
    }
    svg.appendChild(groups);
    const links = el('g', { class: 'links' });
    const nodes = el('g', { class: 'nodes' });
    const packets = el('g', { class: 'packets' });
    svg.append(links, nodes, packets);
    m.steps.forEach((s, i) => {
      const kind = STEP_KINDS.has(s.kind) ? s.kind : 'call';
      const g = el('g', { class: `link s-${kind}`, 'data-step': i + 1 });
      targets(s).forEach((to, j) => {
        const { p, q } = ends(m, geo, s.from, to);
        const len = Math.hypot(q.x - p.x, q.y - p.y);
        g.appendChild(el('line', { class: 'wire', x1: p.x, y1: p.y, x2: q.x, y2: q.y, style: `--len: ${len}` }));
        const ang = Math.atan2(q.y - p.y, q.x - p.x);
        const hx = q.x - Math.cos(ang) * 14;
        const hy = q.y - Math.sin(ang) * 14;
        const nx = Math.sin(ang) * 7;
        const ny = -Math.cos(ang) * 7;
        g.appendChild(el('polygon', { class: 'head', points: `${q.x},${q.y} ${hx + nx},${hy + ny} ${hx - nx},${hy - ny}` }));
        if (j > 0) return;  // one label per step
        const mx = (p.x + q.x) / 2;
        const my = (p.y + q.y) / 2;
        const above = Math.abs(q.y - p.y) < Math.abs(q.x - p.x);
        g.appendChild(el('text', { x: mx + (above ? 0 : 14), y: my + (above ? -16 : 5), 'text-anchor': above ? 'middle' : 'start', class: 'label' }, s.label));
      });
      links.appendChild(g);
    });
    for (const n of Object.values(geo)) {
      const node = drawNode(nodes, n, false);
      if (!all) node.classList.add('hidden');
    }
    // The steps along the bottom: where we are in the story, numbered, the same order as the voice.
    const strip = el('g', { class: 'strip' });
    const sw = (W - 92) / Math.max(1, m.steps.length);
    m.steps.forEach((s, i) => {
      const g = el('g', { class: 'chip', 'data-step': i + 1 });
      const x = 46 + sw * i;
      g.appendChild(el('circle', { cx: x + 16, cy: H - 52, r: 15 }));
      g.appendChild(el('text', { x: x + 16, y: H - 47, 'text-anchor': 'middle', class: 'num' }, String(i + 1)));
      g.appendChild(el('text', { x: x + 40, y: H - 46, class: 'what' }, s.label.length > Math.floor(sw / 11) ? `${s.label.slice(0, Math.floor(sw / 11) - 1)}…` : s.label));
      strip.appendChild(g);
    });
    svg.appendChild(strip);
    layer.replaceChildren(svg);
    layer.classList.add('on');
    Object.assign(cur, { name, map: m, geo, svg, shown: new Set(all ? Object.keys(geo) : []), played: 0 });
  }

  async function mapReveal(ids, gap = 260) {
    const list = Array.isArray(ids) ? ids : [ids];
    for (const id of list) {
      const node = cur.svg?.querySelector(`.node[data-id="${CSS.escape(id)}"]`);
      if (!node) throw new Error(`Map "${cur.name}" has no node "${id}"`);
      if (!cur.shown.has(id)) {
        cur.shown.add(id);
        node.classList.remove('hidden');
        const g = cur.geo[id];
        await node.animate([
          { opacity: 0, transform: 'scale(.86)', transformOrigin: `${g.x}px ${g.y}px` },
          { opacity: 1, transform: 'scale(1)', transformOrigin: `${g.x}px ${g.y}px` },
        ], { duration: 420, easing: EASE, fill: 'forwards' }).finished;
        if (gap) await new Promise((r) => setTimeout(r, gap));
      }
    }
  }

  async function mapStep(n, ms = 900) {
    const m = cur.map;
    if (!m) throw new Error('mapStep before map()');
    const step = m.steps[n - 1];
    if (!step) throw new Error(`Map "${cur.name}" has no step ${n}`);
    const ends2 = [step.from, ...targets(step)];
    await mapReveal(ends2.filter((id) => !cur.shown.has(id)), 0);
    cur.svg.querySelectorAll('.link').forEach((g) => {
      const k = Number(g.dataset.step);
      g.classList.toggle('done', k < n);
      g.classList.toggle('now', k === n);
      g.classList.toggle('later', k > n);
      g.classList.remove('all');
    });
    cur.svg.querySelectorAll('.chip').forEach((g) => {
      const k = Number(g.dataset.step);
      g.classList.toggle('done', k < n);
      g.classList.toggle('now', k === n);
    });
    // The path in use is at full strength; the rest steps back.
    cur.svg.querySelectorAll('.node').forEach((g) => {
      g.classList.toggle('active', ends2.includes(g.dataset.id));
      g.classList.toggle('rest', !ends2.includes(g.dataset.id));
    });
    const link = cur.svg.querySelector(`.link[data-step="${n}"]`);
    link.classList.add('travel');  // the label waits: the message carries it while it moves
    await Promise.all([...link.querySelectorAll('.wire')].map((wire) => wire.animate(
      [{ strokeDashoffset: `${wire.style.getPropertyValue('--len')}px` }, { strokeDashoffset: '0px' }],
      { duration: 400, easing: 'ease-out', fill: 'forwards' }).finished));

    // The message travels: a chip with the payload (or the label) slides from one end to the other.
    // A fan-out sends one copy to each target, 120 ms apart.
    const kind = STEP_KINDS.has(step.kind) ? step.kind : 'call';
    const text = step.payload ?? step.label;
    const w = Math.min(420, 22 + text.length * 10.5);
    await Promise.all(targets(step).map(async (to, i) => {
      const { p, q } = ends(m, cur.geo, step.from, to);
      const packet = el('g', { class: `packet s-${kind}` });
      packet.appendChild(el('rect', { x: -w / 2, y: -17, width: w, height: 34, rx: 17 }));
      packet.appendChild(el('text', { x: 0, y: 6, 'text-anchor': 'middle' }, text));
      cur.svg.querySelector('.packets').appendChild(packet);
      const stop = kind === 'fail' ? 0.62 : 1;
      const end = { x: p.x + (q.x - p.x) * stop, y: p.y + (q.y - p.y) * stop };
      await packet.animate([
        { transform: `translate(${p.x}px, ${p.y}px) scale(.6)`, opacity: 0 },
        { transform: `translate(${p.x + (end.x - p.x) * 0.12}px, ${p.y + (end.y - p.y) * 0.12}px) scale(1)`, opacity: 1, offset: 0.15 },
        { transform: `translate(${end.x}px, ${end.y}px) scale(1)`, opacity: 1 },
      ], { duration: ms, delay: i * 120, easing: EASE, fill: 'forwards' }).finished;
      if (kind === 'fail') {
        packet.classList.add('broken');
        packet.appendChild(el('text', { x: 0, y: -30, 'text-anchor': 'middle', class: 'cross' }, '✕'));
        await new Promise((r) => setTimeout(r, 400));
        return;
      }
      // The target reacts (only after the message lands), then the message is absorbed.
      const g = cur.geo[to];
      cur.svg.querySelector(`.node[data-id="${CSS.escape(to)}"] .shape`)?.animate([
        { transform: 'scale(1)', transformOrigin: `${g.x}px ${g.y}px` },
        { transform: 'scale(1.05)', transformOrigin: `${g.x}px ${g.y}px` },
        { transform: 'scale(1)', transformOrigin: `${g.x}px ${g.y}px` },
      ], { duration: 360, easing: 'ease-out' });
      await packet.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 280, fill: 'forwards' }).finished;
      packet.remove();
    }));
    if (kind !== 'fail' || step.payload) link.classList.remove('travel');
    if (step.state) setState(step.state.node ?? targets(step)[0], step.state.text);
    cur.played = n;
  }

  // The high-level design: every part and every connection, still, so the viewer can take it in.
  async function mapOverview() {
    await mapReveal(Object.keys(cur.geo).filter((id) => !cur.shown.has(id)), 80);
    cur.svg.querySelectorAll('.link').forEach((g) => {
      g.classList.remove('later', 'now', 'travel', 'dim');
      g.classList.add('done', 'all');
    });
    cur.svg.querySelectorAll('.node').forEach((g) => g.classList.remove('rest', 'active', 'dim'));
    cur.svg.querySelectorAll('.chip').forEach((g) => g.classList.remove('now', 'done'));
  }

  // The recap: every step again, quickly, with nothing new.
  async function mapReplay(ms = 420) {
    cur.svg?.querySelectorAll('.packet').forEach((p) => p.remove());
    for (let n = 1; n <= cur.map.steps.length; n++) await mapStep(n, ms);
    cur.svg.querySelectorAll('.node').forEach((g) => g.classList.remove('rest'));
  }

  function setState(id, text) {
    const g = cur.geo[id];
    const slot = cur.svg.querySelector(`.state[data-for="${CSS.escape(id)}"]`);
    if (!g || !slot) return;
    const w = Math.min(g.w + 40, 26 + text.length * 10);
    slot.replaceChildren(
      el('rect', { x: g.x - w / 2, y: g.y + g.h / 2 + 12, width: w, height: 30, rx: 8 }),
      el('text', { x: g.x, y: g.y + g.h / 2 + 33, 'text-anchor': 'middle' }, text),
    );
    slot.animate([{ opacity: 0, transform: 'translateY(-6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 320, easing: EASE });
  }

  function mapFocus(ids) {
    const keep = ids ? new Set(ids) : null;
    cur.svg?.querySelectorAll('.node').forEach((g) => {
      g.classList.remove('rest');
      g.classList.toggle('dim', Boolean(keep) && !keep.has(g.dataset.id));
    });
    cur.svg?.querySelectorAll('.link').forEach((g) => {
      const s = cur.map.steps[Number(g.dataset.step) - 1];
      g.classList.toggle('dim', Boolean(keep) && !(keep.has(s.from) && targets(s).some((id) => keep.has(id))));
    });
  }

  async function mapZoom(id) {
    const g = cur.geo?.[id];
    if (!g) throw new Error(`Map "${cur.name}" has no node "${id}"`);
    mapFocus([id]);
    await cur.svg.animate([
      { transform: 'scale(1)', transformOrigin: `${g.x}px ${g.y}px`, opacity: 1 },
      { transform: 'scale(2.6)', transformOrigin: `${g.x}px ${g.y}px`, opacity: 0 },
    ], { duration: 900, easing: 'cubic-bezier(.55, 0, .7, .2)', fill: 'forwards' }).finished;
    hideMap();
  }

  function hideMap() {
    $('#map')?.classList.remove('on');
    cur.name = null;
  }

  // "You are here": the map, small, in the corner of the code, with the node whose code is on screen lit.
  function locate(name, id) {
    const m = getMap(name);
    let box = $('#locator');
    if (!box) {
      box = document.createElement('div');
      box.id = 'locator';
      $('#code-wrap').appendChild(box);
    }
    const W = 400;
    const H = Math.max(110, 52 * (Math.max(...m.nodes.map((n) => n.row ?? 0)) + 1) + 16);
    const geo = layout(m, W, H, true);
    const svg = el('svg', { viewBox: `0 0 ${W} ${H}` });
    const seen = new Set();
    for (const s of m.steps) {
      for (const to of targets(s)) {
        const key = [s.from, to].sort().join('|');
        if (seen.has(key)) continue;
        seen.add(key);
        const a = geo[s.from];
        const b = geo[to];
        svg.appendChild(el('line', { class: 'wire', x1: a.x, y1: a.y, x2: b.x, y2: b.y }));
      }
    }
    for (const n of Object.values(geo)) {
      const node = drawNode(svg, n, true);
      if (n.id === id) node.classList.add('here');
    }
    const here = document.createElement('div');
    here.className = 'here';
    here.textContent = (m.nodes.find((n) => n.id === id) ?? { label: id }).label;  // the full name, never cut short
    box.replaceChildren(here, svg);
    box.classList.add('on');
  }

  function hideLocator() {
    $('#locator')?.classList.remove('on');
  }

  // A new file, a title or a sequence diagram takes the stage: the map steps aside.
  const ide = window.ide;
  const wrap = (fn, first) => async (...args) => { first(); return fn(...args); };
  ide.open = wrap(ide.open, hideMap);
  ide.welcome = wrap(ide.welcome, () => { hideMap(); hideLocator(); });
  ide.sequence = wrap(ide.sequence, hideMap);
  Object.assign(ide, { map, mapReveal, mapStep, mapReplay, mapOverview, mapFocus, mapZoom, hideMap, locate, hideLocator });
})();
