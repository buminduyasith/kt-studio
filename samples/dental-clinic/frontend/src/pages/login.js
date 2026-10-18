import { api } from '../api.js';
import { html } from './html.js';

export function renderLogin(app) {
  app.append(html`
    <div class="login card">
      <h1>Front desk login</h1>
      <div class="banner bad" hidden></div>
      <form>
        <div class="field"><label for="email">Email</label><input id="email" type="email" autocomplete="username" required></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" autocomplete="current-password" required></div>
        <button class="primary" type="submit">Log in</button>
      </form>
    </div>`);
  const form = app.querySelector('form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await api.login(form.email.value, form.password.value);
      location.hash = '#/schedule';
    } catch (err) {
      const banner = app.querySelector('.banner');
      banner.textContent = err.message;
      banner.hidden = false;
    }
  });
}
