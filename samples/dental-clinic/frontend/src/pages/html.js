// html`...` turns a template string into DOM nodes. Values are escaped.
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

export function html(strings, ...values) {
  const t = document.createElement('template');
  t.innerHTML = strings.reduce((out, s, i) => out + s + (i < values.length ? (values[i]?.raw ?? esc(values[i])) : ''), '');
  return t.content;
}

export const raw = (s) => ({ raw: s });
