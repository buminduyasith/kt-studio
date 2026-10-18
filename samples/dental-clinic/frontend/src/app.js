// A tiny hash router: #/login, #/schedule, #/book.
import { api } from './api.js';
import { renderLogin } from './pages/login.js';
import { renderSchedule } from './pages/schedule.js';
import { renderBooking } from './pages/booking.js';

const pages = { '/login': renderLogin, '/schedule': renderSchedule, '/book': renderBooking };
const app = document.getElementById('app');
const topbar = document.querySelector('.topbar');

async function show() {
  const [path, query] = (location.hash.slice(1) || '/schedule').split('?');
  const render = pages[path] ?? renderSchedule;
  if (path !== '/login') {
    try {
      const me = await api.me();
      topbar.querySelector('.who').textContent = me.name;
      topbar.hidden = false;
    } catch {
      return; // api.js already sent us to #/login
    }
  } else {
    topbar.hidden = true;
  }
  topbar.querySelectorAll('nav a').forEach((a) => a.classList.toggle('active', a.getAttribute('href') === `#${path}`));
  app.replaceChildren();
  await render(app, new URLSearchParams(query));
}

document.getElementById('logout').addEventListener('click', async () => {
  await api.logout();
  location.hash = '#/login';
});
window.addEventListener('hashchange', show);
show();
