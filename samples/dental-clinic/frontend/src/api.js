// Every call to the backend goes through here. Errors come back as { error, message }.
async function call(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'same-origin',
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== '/login') {
    location.hash = '#/login';
  }
  if (!res.ok) throw Object.assign(new Error(data.message || 'Something went wrong.'), { code: data.error });
  return data;
}

export const api = {
  login: (email, password) => call('POST', '/login', { email, password }),
  logout: () => call('POST', '/logout'),
  me: () => call('GET', '/me'),
  options: () => call('GET', '/options'),
  slots: (dentist, date, treatment) =>
    call('GET', `/slots?dentist=${dentist}&date=${date}&treatment=${encodeURIComponent(treatment)}`),
  schedule: (date) => call('GET', `/appointments?date=${date}`),
  book: (appointment) => call('POST', '/appointments', appointment),
  cancel: (id) => call('POST', `/appointments/${id}/cancel`),
  checkIn: (id) => call('POST', `/appointments/${id}/check-in`),
};
