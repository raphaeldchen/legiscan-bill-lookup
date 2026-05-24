// ── Escape helper: sanitize API/user data before inserting into innerHTML ──
function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s ?? '');
  return d.innerHTML;
}

// ── State ──────────────────────────────────────────────────────────────────
let currentUser = null;

// ── API helpers ────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body) {
    opts.body = JSON.stringify(body);
    opts.headers['Content-Type'] = 'application/json';
  }
  const r = await fetch('/api' + path, opts);
  if (r.status === 401 && path !== '/auth/me') { navigate('/login'); return null; }
  return r;
}

// ── Navigation ─────────────────────────────────────────────────────────────
function navigate(path) {
  history.pushState({}, '', path);
  render();
}

window.addEventListener('popstate', render);

function render() {
  const path = window.location.pathname;
  const publicPaths = ['/login', '/signup'];
  if (!currentUser && !publicPaths.includes(path)) { renderLogin(); return; }
  if (currentUser) updateNav(path);
  if (path === '/' || path === '') renderDashboard();
  else if (path === '/bills') renderBills();
  else if (path === '/categories') renderCategories();
  else if (path === '/login') renderLogin();
  else if (path === '/signup') renderSignup();
  else document.getElementById('app').textContent = 'Page not found.';
}

function updateNav(activePath) {
  const nav = document.getElementById('nav');
  nav.innerHTML = '';

  const links = [
    ['/', 'Dashboard'],
    ['/bills', 'Browse Bills'],
    ['/categories', 'My Categories'],
  ];
  links.forEach(([href, label]) => {
    const a = document.createElement('a');
    a.href = href;
    a.textContent = label;
    if (activePath === href) a.classList.add('active');
    a.addEventListener('click', (e) => { e.preventDefault(); navigate(href); });
    nav.appendChild(a);
  });

  const spacer = document.createElement('div');
  spacer.className = 'spacer';
  nav.appendChild(spacer);

  const info = document.createElement('span');
  info.className = 'user-info';
  info.textContent = currentUser.email;
  nav.appendChild(info);

  const logoutBtn = document.createElement('button');
  logoutBtn.className = 'logout-btn';
  logoutBtn.textContent = 'Logout';
  logoutBtn.addEventListener('click', logout);
  nav.appendChild(logoutBtn);
}

async function logout() {
  await api('POST', '/auth/logout');
  currentUser = null;
  document.getElementById('nav').innerHTML = '';
  navigate('/login');
}

// ── Bootstrap ──────────────────────────────────────────────────────────────
async function init() {
  const r = await fetch('/api/auth/me');
  if (r.ok) currentUser = await r.json();
  render();
}

init();

// ── Login Page ─────────────────────────────────────────────────────────────
function renderLogin() {
  document.getElementById('nav').innerHTML = '';
  const app = document.getElementById('app');
  app.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'form-card';
  card.innerHTML = '<h2>Sign in</h2>';

  card.appendChild(makeInput('login-email', 'Email', 'email'));
  card.appendChild(makeInput('login-password', 'Password', 'password'));

  const btn = document.createElement('button');
  btn.className = 'btn btn-primary';
  btn.style.width = '100%';
  btn.textContent = 'Sign in';
  btn.addEventListener('click', doLogin);
  card.appendChild(btn);

  const err = document.createElement('div');
  err.id = 'login-error';
  err.className = 'error-msg';
  card.appendChild(err);

  const footer = document.createElement('div');
  footer.className = 'form-footer';
  footer.innerHTML = "No account? ";
  const link = document.createElement('a');
  link.href = '/signup';
  link.textContent = 'Sign up';
  link.addEventListener('click', (e) => { e.preventDefault(); navigate('/signup'); });
  footer.appendChild(link);
  card.appendChild(footer);

  app.appendChild(card);
}

async function doLogin() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const r = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (r.ok) {
    currentUser = await r.json();
    navigate('/');
  } else {
    const data = await r.json();
    document.getElementById('login-error').textContent = data.detail || 'Login failed';
  }
}

// ── Signup Page ────────────────────────────────────────────────────────────
function renderSignup() {
  document.getElementById('nav').innerHTML = '';
  const app = document.getElementById('app');
  app.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'form-card';
  card.innerHTML = '<h2>Create account</h2>';

  card.appendChild(makeInput('signup-email', 'Email', 'email'));
  card.appendChild(makeInput('signup-password', 'Password', 'password'));

  const btn = document.createElement('button');
  btn.className = 'btn btn-primary';
  btn.style.width = '100%';
  btn.textContent = 'Create account';
  btn.addEventListener('click', doSignup);
  card.appendChild(btn);

  const err = document.createElement('div');
  err.id = 'signup-error';
  err.className = 'error-msg';
  card.appendChild(err);

  const footer = document.createElement('div');
  footer.className = 'form-footer';
  footer.innerHTML = 'Already have an account? ';
  const link = document.createElement('a');
  link.href = '/login';
  link.textContent = 'Sign in';
  link.addEventListener('click', (e) => { e.preventDefault(); navigate('/login'); });
  footer.appendChild(link);
  card.appendChild(footer);

  app.appendChild(card);
}

async function doSignup() {
  const email = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;
  const r = await fetch('/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (r.ok) {
    currentUser = await r.json();
    navigate('/');
  } else {
    const data = await r.json();
    document.getElementById('signup-error').textContent = data.detail || 'Signup failed';
  }
}

// ── Shared form helpers ────────────────────────────────────────────────────
function makeInput(id, labelText, type) {
  const group = document.createElement('div');
  group.className = 'form-group';
  const label = document.createElement('label');
  label.textContent = labelText;
  const input = document.createElement('input');
  input.type = type;
  input.id = id;
  group.appendChild(label);
  group.appendChild(input);
  return group;
}
