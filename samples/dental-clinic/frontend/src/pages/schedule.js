// The day's schedule: every appointment, with Check in and Cancel.
import { api } from '../api.js';
import { html, raw } from './html.js';

const money = (cents) => `Rs. ${(cents / 100).toFixed(2)}`;

export async function renderSchedule(app, params) {
  const opts = await api.options();
  const day = params.get('date') || opts.today;
  const booked = params.get('booked');
  app.append(html`
    <h1>Schedule</h1>
    <div class="banner ok" hidden></div>
    <div class="banner bad" hidden></div>
    <div class="day-picker"><label for="day">Day</label><input id="day" type="date" value="${day}"></div>
    <table>
      <thead><tr><th>Time</th><th>Patient</th><th>Dentist</th><th>Treatment</th><th>Status</th><th></th></tr></thead>
      <tbody></tbody>
    </table>`);
  const ok = app.querySelector('.banner.ok');
  const bad = app.querySelector('.banner.bad');
  const body = app.querySelector('tbody');
  app.querySelector('#day').addEventListener('change', (e) => { location.hash = `#/schedule?date=${e.target.value}`; });

  async function load() {
    const { appointments } = await api.schedule(day);
    body.replaceChildren();
    if (!appointments.length) body.append(html`<tr><td colspan="6" class="muted">No appointments on this day.</td></tr>`);
    for (const a of appointments) {
      const row = html`<tr data-id="${a.id}">
        <td>${a.starts_at.slice(11, 16)}–${a.ends_at.slice(11, 16)}</td>
        <td>${a.patient}</td><td>${a.dentist}</td><td>${a.treatment_label}</td>
        <td><span class="status ${a.status}">${a.status.replace('_', ' ')}</span>${a.fee_cents ? raw(` <span class="muted">fee ${money(a.fee_cents)}</span>`) : ''}</td>
        <td class="row-actions"></td></tr>`.firstElementChild;
      const actions = row.querySelector('.row-actions');
      if (a.status === 'BOOKED') {
        actions.append(button('Check in', () => act(() => api.checkIn(a.id), `${a.patient} is checked in.`)));
        actions.append(button('Cancel', () => {
          // The 24 hour rule is the server's; the warning here only explains it before the click.
          const hours = (new Date(a.starts_at) - new Date()) / 36e5;
          const warn = hours < 24 ? '\nThis is less than 24 hours ahead: a late fee of Rs. 25.00 applies.' : '';
          if (confirm(`Cancel ${a.patient}'s visit at ${a.starts_at.slice(11, 16)}?${warn}`)) {
            act(() => api.cancel(a.id), `${a.patient}'s visit is cancelled.`);
          }
        }));
      }
      if (String(a.id) === booked) row.style.background = 'var(--brand-soft)';
      body.append(row);
    }
  }

  async function act(fn, message) {
    ok.hidden = bad.hidden = true;
    try {
      await fn();
      ok.textContent = message;
      ok.hidden = false;
    } catch (err) {
      bad.textContent = err.message;
      bad.hidden = false;
    }
    await load();
  }

  if (booked) {
    ok.textContent = 'Appointment booked. The patient gets a text message now and a reminder the day before.';
    ok.hidden = false;
  }
  await load();
}

function button(label, onClick) {
  const b = html`<button type="button">${label}</button>`.firstElementChild;
  b.addEventListener('click', onClick);
  return b;
}
