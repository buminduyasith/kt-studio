// New appointment: pick patient, treatment and dentist, then a free time, then book.
// The free times come from the server (GET /api/slots), so the rules live in one place: backend/clinic.
import { api } from '../api.js';
import { html } from './html.js';

export async function renderBooking(app) {
  const opts = await api.options();
  const tomorrow = addDays(opts.today, 1);
  app.append(html`
    <h1>New appointment</h1>
    <div class="banner bad" hidden></div>
    <form class="card" novalidate>
      <div class="grid">
        <div class="field"><label for="patient">Patient</label>
          <select id="patient"><option value="">Choose a patient</option></select></div>
        <div class="field"><label for="treatment">Treatment</label>
          <select id="treatment"></select></div>
        <div class="field"><label for="dentist">Dentist</label>
          <select id="dentist"></select></div>
        <div class="field"><label for="date">Date</label>
          <input id="date" type="date" min="${opts.today}" value="${tomorrow}"></div>
      </div>
      <div class="field"><label>Free times</label>
        <div class="slots" role="group" aria-label="Free times"></div></div>
      <div class="field"><label for="note">Note for the dentist</label>
        <input id="note" maxlength="200" placeholder="Optional"></div>
      <button class="primary" type="submit" disabled>Book appointment</button>
    </form>`);

  const form = app.querySelector('form');
  const banner = app.querySelector('.banner');
  const slotsBox = app.querySelector('.slots');
  const submit = form.querySelector('button[type=submit]');
  let picked = null;

  fill(form.patient, opts.patients.map((p) => [p.id, p.name]));
  fill(form.treatment, opts.treatments.map((t) => [t.id, `${t.label} · ${t.minutes} min`]));
  fill(form.dentist, opts.dentists.map((d) => [d.id, `${d.name} · ${d.room}`]));

  async function loadSlots() {
    picked = null;
    submit.disabled = true;
    slotsBox.replaceChildren(html`<span class="muted">Loading…</span>`);
    const { slots } = await api.slots(form.dentist.value, form.date.value, form.treatment.value);
    slotsBox.replaceChildren();
    if (!slots.length) slotsBox.append(html`<span class="muted">No free times on this day. Try another day or dentist.</span>`);
    for (const time of slots) {
      const b = html`<button type="button">${time}</button>`.firstElementChild;
      b.addEventListener('click', () => {
        slotsBox.querySelectorAll('button').forEach((x) => x.classList.toggle('picked', x === b));
        picked = time;
        submit.disabled = !form.patient.value;
      });
      slotsBox.append(b);
    }
  }

  form.patient.addEventListener('change', () => { submit.disabled = !(picked && form.patient.value); });
  for (const field of [form.treatment, form.dentist, form.date]) field.addEventListener('change', loadSlots);
  await loadSlots();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    banner.hidden = true;
    submit.disabled = true;
    try {
      const appt = await api.book({
        patientId: form.patient.value, dentistId: form.dentist.value, treatment: form.treatment.value,
        date: form.date.value, time: picked, note: form.note.value,
      });
      location.hash = `#/schedule?date=${form.date.value}&booked=${appt.id}`;
    } catch (err) {
      // slot_taken: someone else booked it a moment ago. Show the message and refresh the times.
      banner.textContent = err.message;
      banner.hidden = false;
      if (err.code === 'slot_taken') await loadSlots();
      else submit.disabled = false;
    }
  });
}

function fill(select, pairs) {
  for (const [value, text] of pairs) select.append(new Option(text, value));
}

function addDays(isoDate, n) {
  const d = new Date(`${isoDate}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}
