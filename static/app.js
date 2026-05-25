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

// ── Loading helper ─────────────────────────────────────────────────────────
// Disables btn + shows loadingText while fn() runs; always restores on finish.
async function withLoading(btn, loadingText, fn) {
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = loadingText;
  try { await fn(); } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
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
  // Render free tier spins down after ~15 min of inactivity; first request
  // can take 30-60 s. Show a banner after 1.5 s so the user isn't left staring
  // at a blank page with no explanation.
  let wakeBanner = null;
  const wakeTimer = setTimeout(() => {
    wakeBanner = document.createElement('div');
    wakeBanner.id = 'wake-banner';
    wakeBanner.textContent = '⏳ Server is waking up — this takes ~30 s on first load after idle…';
    document.body.insertBefore(wakeBanner, document.body.firstChild);
  }, 1500);

  const r = await fetch('/api/auth/me');
  clearTimeout(wakeTimer);
  if (wakeBanner) wakeBanner.remove();

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
  btn.addEventListener('click', () => withLoading(btn, 'Signing in…', doLogin));
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
  btn.addEventListener('click', () => withLoading(btn, 'Creating account…', doSignup));
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

// ── Dashboard Page ─────────────────────────────────────────────────────────
let _pollInterval = null;

async function renderDashboard() {
  const app = document.getElementById('app');
  app.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'section-title';
  title.textContent = 'Dashboard';
  app.appendChild(title);

  const cards = document.createElement('div');
  cards.className = 'stat-cards';
  cards.innerHTML = `
    <div class="stat-card"><div class="label">TOTAL BILLS</div><div class="value" id="stat-bills">—</div></div>
    <div class="stat-card"><div class="label">LAST SYNCED</div><div class="value" id="stat-synced" style="font-size:18px">—</div></div>
    <div class="stat-card"><div class="label">MY CATEGORIES</div><div class="value" id="stat-cats">—</div></div>
  `;
  app.appendChild(cards);

  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';
  toolbar.innerHTML = `
    <button class="btn btn-primary" id="fetch-btn">&#x21BB; Fetch Bills</button>
    <span id="fetch-status-text" style="font-size:13px;color:#4a5568"></span>
  `;
  app.appendChild(toolbar);
  document.getElementById('fetch-btn').addEventListener('click', startFetch);

  const progressWrap = document.createElement('div');
  progressWrap.className = 'progress-wrap';
  progressWrap.id = 'progress-wrap';
  progressWrap.style.display = 'none';
  progressWrap.innerHTML = '<div class="progress-bar" id="progress-bar" style="width:0%"></div>';
  app.appendChild(progressWrap);

  loadDashboardStats();
  checkActiveFetch();
}

async function loadDashboardStats() {
  const [billsR, catsR, latestR] = await Promise.all([
    api('GET', '/bills?limit=1'),
    api('GET', '/categories'),
    api('GET', '/fetch/latest'),
  ]);
  if (!billsR) return;
  const [bills, cats, latest] = await Promise.all([billsR.json(), catsR.json(), latestR.json()]);

  const statBills = document.getElementById('stat-bills');
  if (statBills) statBills.textContent = bills.total.toLocaleString();
  const statCats = document.getElementById('stat-cats');
  if (statCats) statCats.textContent = cats.length;
  const statSynced = document.getElementById('stat-synced');
  if (statSynced && latest && latest.finished_at) {
    statSynced.textContent = new Date(latest.finished_at).toLocaleString();
  }
}

async function checkActiveFetch() {
  const r = await api('GET', '/fetch/latest');
  if (!r) return;
  const job = await r.json();
  if (job && (job.status === 'queued' || job.status === 'running')) {
    startPolling(job.id);
  }
}

async function startFetch() {
  const btn = document.getElementById('fetch-btn');
  if (btn) { btn.disabled = true; btn.textContent = '↻ Fetching…'; }
  const r = await api('POST', '/fetch');
  if (!r) {
    if (btn) { btn.disabled = false; btn.textContent = '↻ Fetch Bills'; }
    return;
  }
  const data = await r.json();
  startPolling(data.job_id);
}

function startPolling(jobId) {
  clearInterval(_pollInterval);
  const wrap = document.getElementById('progress-wrap');
  if (wrap) wrap.style.display = 'block';

  _pollInterval = setInterval(async () => {
    const r = await api('GET', `/fetch/status/${jobId}`);
    if (!r) return;
    const job = await r.json();
    const pct = job.total_bills ? Math.round((job.bills_fetched / job.total_bills) * 100) : 0;
    const bar = document.getElementById('progress-bar');
    if (bar) bar.style.width = pct + '%';
    const statusText = document.getElementById('fetch-status-text');
    if (statusText) {
      statusText.textContent = job.total_bills
        ? 'Syncing… ' + job.bills_fetched.toLocaleString() + ' / ' + job.total_bills.toLocaleString()
        : 'Starting…';
    }
    if (job.status === 'done' || job.status === 'failed') {
      clearInterval(_pollInterval);
      const btn = document.getElementById('fetch-btn');
      if (btn) { btn.disabled = false; btn.textContent = '↻ Fetch Bills'; }
      if (bar) bar.style.width = job.status === 'done' ? '100%' : bar.style.width;
      if (statusText) {
        statusText.textContent = job.status === 'done'
          ? 'Done — ' + job.bills_updated + ' bills updated'
          : 'Error: ' + (job.error_msg || 'unknown');
      }
      if (job.status === 'done') loadDashboardStats();
    }
  }, 3000);
}

// ── Browse Bills Page ──────────────────────────────────────────────────────
let _billsState = { categories: [], selectedIds: [], page: 1, total: 0 };

async function renderBills() {
  const app = document.getElementById('app');
  app.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'section-title';
  title.textContent = 'Browse Bills';
  app.appendChild(title);

  const filterLabel = document.createElement('div');
  filterLabel.style = 'font-size:12px;color:#4a5568;margin-bottom:8px';
  filterLabel.textContent = 'Filter by category:';
  app.appendChild(filterLabel);

  const pills = document.createElement('div');
  pills.className = 'pills';
  pills.id = 'category-pills';
  app.appendChild(pills);

  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';
  toolbar.innerHTML = `
    <button class="btn btn-primary" id="filter-btn">Filter Bills</button>
    <button class="btn btn-ghost" id="clear-btn">Clear</button>
    <span class="bill-count" id="bill-count"></span>
    <div style="flex:1"></div>
    <button class="btn btn-success" id="export-btn">&#x2B07; Export CSV</button>
  `;
  app.appendChild(toolbar);
  document.getElementById('filter-btn').addEventListener('click', () => loadBillsPage(1));
  document.getElementById('clear-btn').addEventListener('click', clearBillsFilter);
  document.getElementById('export-btn').addEventListener('click', exportCSV);

  const tableWrap = document.createElement('div');
  tableWrap.className = 'table-wrap';
  tableWrap.innerHTML = `
    <table>
      <thead><tr>
        <th>Bill #</th><th>Title</th><th>Chamber</th>
        <th>Committee</th><th>Last Action</th><th>Status</th>
      </tr></thead>
      <tbody id="bills-tbody"></tbody>
    </table>
  `;
  app.appendChild(tableWrap);

  const pagination = document.createElement('div');
  pagination.id = 'bills-pagination';
  pagination.style = 'margin-top:14px;display:flex;gap:8px;align-items:center';
  app.appendChild(pagination);

  const r = await api('GET', '/categories');
  if (!r) return;
  _billsState.categories = await r.json();
  _billsState.selectedIds = [];
  _billsState.page = 1;
  renderBillsPills();
  loadBillsPage(1);
}

function renderBillsPills() {
  const pills = document.getElementById('category-pills');
  if (!pills) return;
  pills.innerHTML = '';
  _billsState.categories.forEach(c => {
    const pill = document.createElement('div');
    pill.className = 'pill' + (_billsState.selectedIds.includes(c.id) ? ' selected' : '');
    pill.textContent = c.name;
    pill.addEventListener('click', () => toggleBillsPill(c.id));
    pills.appendChild(pill);
  });
}

function toggleBillsPill(id) {
  if (_billsState.selectedIds.includes(id)) {
    _billsState.selectedIds = _billsState.selectedIds.filter(x => x !== id);
  } else {
    _billsState.selectedIds.push(id);
  }
  renderBillsPills();
}

async function loadBillsPage(page) {
  _billsState.page = page;

  // Show loading feedback immediately so the button doesn't feel frozen
  const filterBtn = document.getElementById('filter-btn');
  const clearBtn  = document.getElementById('clear-btn');
  const countEl   = document.getElementById('bill-count');
  if (filterBtn) { filterBtn.disabled = true; filterBtn.textContent = 'Filtering…'; }
  if (clearBtn)  clearBtn.disabled = true;
  if (countEl)   countEl.textContent = 'Loading…';

  let r;
  if (_billsState.selectedIds.length) {
    r = await api('POST', '/bills/filter?page=' + page, { category_ids: _billsState.selectedIds });
  } else {
    r = await api('GET', '/bills?page=' + page);
  }

  // Restore buttons regardless of success/failure
  if (filterBtn) { filterBtn.disabled = false; filterBtn.textContent = 'Filter Bills'; }
  if (clearBtn)  clearBtn.disabled = false;

  if (!r) return;
  const data = await r.json();
  _billsState.total = data.total;
  renderBillsTable(data.bills);
  renderBillsPagination(data.total, page);
  if (countEl) countEl.textContent = 'Showing ' + data.bills.length + ' of ' + data.total.toLocaleString() + ' bills';
}

function renderBillsTable(bills) {
  const tbody = document.getElementById('bills-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';
  bills.forEach(b => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="bill-num">${esc(b.number)}</td>
      <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${esc(b.title)}">${esc(b.title)}</td>
      <td>${esc(b.chamber)}</td>
      <td style="color:#718096">${esc(b.committee || '—')}</td>
      <td style="color:#718096;white-space:nowrap">${esc(b.last_action_date)}</td>
      <td><span style="background:rgba(59,130,246,.12);color:#60a5fa;border-radius:4px;padding:2px 8px;font-size:11px">${esc(b.status)}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderBillsPagination(total, page) {
  const el = document.getElementById('bills-pagination');
  if (!el) return;
  el.innerHTML = '';
  const totalPages = Math.ceil(total / 50);
  if (page > 1) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-ghost';
    btn.textContent = '← Prev';
    btn.addEventListener('click', () => loadBillsPage(page - 1));
    el.appendChild(btn);
  }
  const info = document.createElement('span');
  info.style = 'font-size:13px;color:#4a5568';
  info.textContent = 'Page ' + page + ' of ' + totalPages;
  el.appendChild(info);
  if (page < totalPages) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-ghost';
    btn.textContent = 'Next →';
    btn.addEventListener('click', () => loadBillsPage(page + 1));
    el.appendChild(btn);
  }
}

function clearBillsFilter() {
  _billsState.selectedIds = [];
  renderBillsPills();
  loadBillsPage(1);
}

function exportCSV() {
  const ids = _billsState.selectedIds.join(',');
  window.location.href = '/api/bills/export?category_ids=' + ids;
}

// ── My Categories Page ─────────────────────────────────────────────────────
let _catsState = { categories: [], selectedId: null };

async function renderCategories() {
  const app = document.getElementById('app');
  app.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'section-title';
  title.textContent = 'My Categories';
  app.appendChild(title);

  const layout = document.createElement('div');
  layout.className = 'category-layout';
  layout.innerHTML = `
    <div class="category-list" id="cat-list"></div>
    <div style="flex:1" id="cat-editor">
      <p style="color:#4a5568">Select a category or create one.</p>
    </div>
  `;
  app.appendChild(layout);

  const r = await api('GET', '/categories');
  if (!r) return;
  _catsState.categories = await r.json();
  _catsState.selectedId = null;
  renderCatList();
}

function renderCatList() {
  const list = document.getElementById('cat-list');
  if (!list) return;
  list.innerHTML = '';

  _catsState.categories.forEach(c => {
    const item = document.createElement('div');
    item.className = 'category-item' + (c.id === _catsState.selectedId ? ' selected' : '');
    item.innerHTML = `
      <div class="cat-name">${esc(c.name)}</div>
      <div class="cat-count">${c.keywords.length} keyword${c.keywords.length !== 1 ? 's' : ''}</div>
    `;
    item.addEventListener('click', () => selectCat(c.id));
    list.appendChild(item);
  });

  const newBtn = document.createElement('button');
  newBtn.className = 'btn btn-ghost';
  newBtn.style = 'width:100%;margin-top:8px;font-size:13px';
  newBtn.textContent = '+ New Category';
  newBtn.addEventListener('click', () => withLoading(newBtn, 'Creating…', createCat));
  list.appendChild(newBtn);
}

function selectCat(id) {
  _catsState.selectedId = id;
  renderCatList();
  const cat = _catsState.categories.find(c => c.id === id);
  if (cat) renderCatEditor(cat);
}

function renderCatEditor(cat) {
  const editor = document.getElementById('cat-editor');
  if (!editor) return;
  editor.innerHTML = '';

  const header = document.createElement('div');
  header.style = 'display:flex;align-items:center;gap:10px;margin-bottom:16px';
  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.id = 'cat-name-input';
  nameInput.value = cat.name;
  nameInput.style = 'font-size:16px;font-weight:600;flex:1';
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn btn-danger';
  deleteBtn.textContent = 'Delete';
  deleteBtn.addEventListener('click', async () => {
    if (!confirm('Delete this category?')) return;
    await withLoading(deleteBtn, 'Deleting…', () => deleteCat(cat.id));
  });
  header.appendChild(nameInput);
  header.appendChild(deleteBtn);
  editor.appendChild(header);

  const kwLabel = document.createElement('div');
  kwLabel.style = 'font-size:11px;color:#4a5568;letter-spacing:.05em;margin-bottom:8px';
  kwLabel.textContent = 'KEYWORDS — bills containing any of these are included';
  editor.appendChild(kwLabel);

  const chips = document.createElement('div');
  chips.className = 'keyword-chips';
  chips.id = 'chip-list';
  cat.keywords.forEach(kw => {
    const chip = document.createElement('div');
    chip.className = 'chip';
    const kwText = document.createElement('span');
    kwText.textContent = kw;
    const removeBtn = document.createElement('span');
    removeBtn.className = 'chip-remove';
    removeBtn.textContent = '\xD7';
    removeBtn.addEventListener('click', () => removeKeyword(cat, kw));
    chip.appendChild(kwText);
    chip.appendChild(removeBtn);
    chips.appendChild(chip);
  });
  editor.appendChild(chips);

  const addRow = document.createElement('div');
  addRow.style = 'display:flex;gap:8px;margin-bottom:16px';
  const kwInput = document.createElement('input');
  kwInput.type = 'text';
  kwInput.id = 'kw-input';
  kwInput.placeholder = 'Add keyword, press Enter…';
  kwInput.style = 'flex:1';
  kwInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addKeyword(cat); });
  const addBtn = document.createElement('button');
  addBtn.className = 'btn btn-ghost';
  addBtn.textContent = 'Add';
  addBtn.addEventListener('click', () => addKeyword(cat));
  addRow.appendChild(kwInput);
  addRow.appendChild(addBtn);
  editor.appendChild(addRow);

  const saveRow = document.createElement('div');
  const saveBtn = document.createElement('button');
  saveBtn.className = 'btn btn-primary';
  saveBtn.textContent = 'Save Category';
  saveBtn.addEventListener('click', () => withLoading(saveBtn, 'Saving…', () => saveCat(cat)));
  const saveMsg = document.createElement('span');
  saveMsg.id = 'save-msg';
  saveMsg.style = 'font-size:13px;color:#10b981;margin-left:12px';
  saveRow.appendChild(saveBtn);
  saveRow.appendChild(saveMsg);
  editor.appendChild(saveRow);
}

function addKeyword(cat) {
  const input = document.getElementById('kw-input');
  if (!input) return;
  const kw = input.value.trim().toLowerCase();
  if (!kw || cat.keywords.includes(kw)) { input.value = ''; return; }
  cat.keywords.push(kw);
  renderCatEditor(cat);
}

function removeKeyword(cat, kw) {
  cat.keywords = cat.keywords.filter(k => k !== kw);
  renderCatEditor(cat);
}

async function saveCat(cat) {
  const nameInput = document.getElementById('cat-name-input');
  const name = nameInput ? nameInput.value.trim() : cat.name;
  const r = await api('PUT', '/categories/' + cat.id, { name, keywords: cat.keywords });
  if (!r || !r.ok) return;
  const updated = await r.json();
  Object.assign(cat, updated);
  renderCatList();
  const msg = document.getElementById('save-msg');
  if (msg) {
    msg.textContent = 'Saved!';
    setTimeout(() => { if (msg) msg.textContent = ''; }, 2000);
  }
}

async function deleteCat(id) {
  const r = await api('DELETE', '/categories/' + id);
  if (!r || !r.ok) return;
  _catsState.categories = _catsState.categories.filter(c => c.id !== id);
  _catsState.selectedId = null;
  renderCatList();
  const editor = document.getElementById('cat-editor');
  if (editor) editor.innerHTML = '<p style="color:#4a5568">Select a category or create one.</p>';
}

async function createCat() {
  const r = await api('POST', '/categories', { name: 'New Category', keywords: [] });
  if (!r || !r.ok) return;
  const cat = await r.json();
  _catsState.categories.push(cat);
  _catsState.selectedId = cat.id;
  renderCatList();
  renderCatEditor(cat);
}
