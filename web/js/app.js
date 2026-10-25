/* ================= 云游 · 前端应用 ================= */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const state = {
  view: 'home', cities: [], cityId: 'guiyang', trendES: null,
  plan: null, planRunning: false, chatBusy: false, chatHistory: [],
  token: localStorage.getItem('wy_token') || '',
  user: null, photos: {}, cfg: null, overview: [],
};

const ICON = { sun: '☀️', cloud: '⛅', rain: '🌧️', snow: '❄️', storm: '⛈️', fog: '🌫️' };
const LEVEL_COLOR = { crowded: '#f87171', hot: '#fbbf24', warm: '#38bdf8', calm: '#4ade80' };
/* 无图片时的山峦剪影，比纯色块更有质感 */
const RIDGE = `<svg class="ridge" viewBox="0 0 300 120" preserveAspectRatio="none">
  <path d="M0,120 L0,78 L38,46 L76,72 L118,38 L162,70 L206,42 L252,68 L300,52 L300,120Z" fill="rgba(255,255,255,.085)"/>
  <path d="M0,120 L0,98 L46,74 L92,96 L138,68 L188,94 L236,70 L300,92 L300,120Z" fill="rgba(255,255,255,.055)"/>
</svg>`;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const cleanModelText = (s) => String(s ?? '')
  .replace(/<(tool_call|tool_response|tool_result)>[\s\S]*?<\/\1>/gi, '')
  .replace(/<\/?(?:tool_call|tool_response|tool_result|function_call)[^>]*>/gi, '')
  .replace(/^\s*[}{]\s*/, '');

const renderRich = (s) => esc(cleanModelText(s))
  .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  .replace(/`([^`]+?)`/g, '<code>$1</code>')
  .replace(/^###\s?(.+)$/gm, '<strong>$1</strong>');

/* ---------------- 基础 ---------------- */
function toast(msg, type = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  $('#toastWrap').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = '.4s'; setTimeout(() => el.remove(), 400); }, 2800);
}

async function api(path, opt = {}) {
  const headers = { ...(opt.headers || {}) };
  if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
  if (opt.body && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const res = await fetch(path, { ...opt, headers });
  if (!res.ok) {
    let msg = `请求失败(${res.status})`;
    try { const j = await res.json(); msg = j.detail || j.message || msg; } catch (e) { /* ignore */ }
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

async function streamSSE(url, body, onEvent) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
  const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!res.ok) {
    let msg = `请求失败 ${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch (e) { /* ignore */ }
    throw new Error(msg);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder('utf-8');
  let buf = '';
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, idx); buf = buf.slice(idx + 2);
      let ev = 'message', data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) ev = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trim();
      }
      if (!data) continue;
      try { onEvent(ev, JSON.parse(data)); } catch (e) { /* 半包 */ }
    }
  }
}

function countUp(el, to, dur = 900) {
  const t0 = performance.now();
  const step = (t) => {
    const p = Math.min(1, (t - t0) / dur);
    el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ---------------- 通用弹窗 ---------------- */
function openModal(html) {
  $('#modalBody').innerHTML = html;
  $('#modal').classList.add('on');
  $('#modalMask').classList.add('on');
}
function closeModal() {
  $('#modal').classList.remove('on');
  $('#modalMask').classList.remove('on');
}
$('#modalClose')?.addEventListener('click', closeModal);
$('#modalMask')?.addEventListener('click', closeModal);
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

function copyText(text) {
  if (navigator.clipboard?.writeText) {
    return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand('copy');
  ta.remove();
  return Promise.resolve(ok);
}

/* ---------------- 认证 ---------------- */
const auth = {
  show(tab = 'login') {
    $('#authLayer').classList.remove('hidden');
    auth.switchTab(tab);
    renderAuthSlides();
  },
  hide() { $('#authLayer').classList.add('hidden'); },
  switchTab(tab) {
    $$('.auth-tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === tab));
    $('#loginForm').classList.toggle('hidden', tab !== 'login');
    $('#registerForm').classList.toggle('hidden', tab !== 'register');
    const title = tab === 'login' ? '欢迎回来' : '创建你的账号';
    $('#authTitle').textContent = title;
    $('#authSub').textContent = tab === 'login'
      ? '使用 163 邮箱登录，继续你的旅程'
      : '只需邮箱验证，30 秒完成注册';
  },
  async load() {
    if (!state.token) return;
    try {
      const { user } = await api('/api/auth/me');
      state.user = user;
    } catch (e) {
      state.token = '';
      state.user = null;
      localStorage.removeItem('wy_token');
    }
    renderUserBox();
  },
  async sendCode() {
    const local = $('#regEmail').value.trim();
    const btn = $('#sendCodeBtn');
    if (!local) return (($('#regErr').textContent = '请先填写邮箱前缀'));
    btn.disabled = true;
    btn.textContent = '发送中…';
    try {
      const r = await api('/api/auth/code', { method: 'POST', body: JSON.stringify({ email: local + '@163.com' }) });
      if (!r.ok) throw new Error(r.message || '发送失败');
      toast(r.message || '验证码已发送');
      if (r.dev_mode && r.code) {
        $('#regErr').innerHTML = '';
        $('#regCode').value = r.code;
        const box = document.createElement('div');
        box.className = 'dev-code';
        box.innerHTML = `开发模式（未配 SMTP）：验证码 <b>${esc(r.code)}</b> 已自动填入`;
        const old = $('#registerForm .dev-code');
        if (old) old.remove();
        $('#regCode').closest('.fld').appendChild(box);
      }
      let left = 60;
      const timer = setInterval(() => {
        left -= 1;
        btn.textContent = left > 0 ? `${left}s 后重发` : '获取验证码';
        if (left <= 0) { clearInterval(timer); btn.disabled = false; }
      }, 1000);
    } catch (e) {
      $('#regErr').textContent = e.message;
      btn.disabled = false;
      btn.textContent = '获取验证码';
    }
  },
  async register() {
    const email = $('#regEmail').value.trim() + '@163.com';
    const payload = {
      email, code: $('#regCode').value.trim(), password: $('#regPwd').value,
      nickname: $('#regNick').value.trim(), city_id: $('#regCity').value,
    };
    $('#regErr').textContent = '';
    setLoading($('#regBtn'), true, '创建中');
    try {
      const r = await api('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) });
      localStorage.removeItem('wy_remember');
      auth.succeed(r);
    } catch (e) {
      $('#regErr').textContent = e.message;
    } finally { setLoading($('#regBtn'), false); }
  },
  async login() {
    const email = $('#loginEmail').value.trim() + '@163.com';
    $('#loginErr').textContent = '';
    setLoading($('#loginBtn'), true, '认证中');
    try {
      const r = await api('/api/auth/login', {
        method: 'POST', body: JSON.stringify({ email, password: $('#loginPwd').value }),
      });
      // 记住我：勾选则记住邮箱与登录态，取消则只保留本次
      if ($('#rememberMe')?.checked) {
        localStorage.setItem('wy_remember', email);
        localStorage.setItem('wy_token', r.token);
      } else {
        localStorage.removeItem('wy_remember');
      }
      auth.succeed(r);
    } catch (e) {
      $('#loginErr').textContent = e.message;
    } finally { setLoading($('#loginBtn'), false); }
  },
  succeed(r) {
    state.token = r.token;
    state.user = r.user;
    localStorage.setItem('wy_token', r.token);
    localStorage.removeItem('wy_skip');
    auth.hide();
    renderUserBox();
    renderWelcome();
    renderOriginSelect();
    toast(`欢迎，${r.user.nickname || r.user.email}`);
  },
  async logout() {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch (e) { /* ignore */ }
    state.token = ''; state.user = null;
    localStorage.removeItem('wy_token');
    renderUserBox(); renderWelcome(); renderOriginSelect();
    toast('已退出登录');
  },
  async locate() {
    const btn = $('#locateBtn');
    if (!navigator.geolocation) return toast('浏览器不支持定位', 'err');
    btn.textContent = '定位中…';
    navigator.geolocation.getCurrentPosition(async (pos) => {
      try {
        const { city, distance_km } = await api(`/api/geo/nearest?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}`);
        $('#regCity').value = city.id;
        $('#cityHint').textContent = `已定位到「${city.name}」（距最近城市中心约 ${distance_km} km）`;
      } catch (e) { toast('定位解析失败', 'err'); }
      btn.textContent = '📍 定位';
    }, () => {
      btn.textContent = '📍 定位';
      toast('定位被拒绝，请手动选择城市', 'err');
    }, { timeout: 8000 });
  },
};

function renderUserBox() {
  const box = $('#userBox');
  if (!state.user) {
    box.innerHTML = `<button class="user-login" id="openAuth">登录 / 注册</button>`;
    $('#openAuth').addEventListener('click', () => auth.show('login'));
    return;
  }
  const name = state.user.nickname || state.user.email.split('@')[0];
  box.innerHTML = `
    <div class="avatar" id="avatarBtn">${esc(name.slice(0, 1).toUpperCase())}</div>
    <div class="user-menu" id="userMenu">
      <div class="um-head"><b>${esc(name)}</b><small>${esc(state.user.email)} · ${esc(state.user.city_name || '未设置城市')}</small></div>
      <div class="um-item" data-act="trips">🗂 我的行程</div>
      <div class="um-item" data-act="city">📍 切换所在城市</div>
      <div class="um-item danger" data-act="logout">⏻ 退出登录</div>
    </div>`;
  $('#avatarBtn').addEventListener('click', (e) => {
    e.stopPropagation();
    $('#userMenu').classList.toggle('on');
  });
  $$('#userMenu .um-item').forEach(it => it.addEventListener('click', async (e) => {
    e.stopPropagation();
    $('#userMenu').classList.remove('on');
    const act = it.dataset.act;
    if (act === 'logout') return auth.logout();
    if (act === 'trips') return go('trips');
    if (act === 'city') {
      const id = prompt('输入城市名（如：成都 / 贵阳 / 西安）', state.user.city_name || '');
      if (!id) return;
      const city = state.cities.find(c => c.name.includes(id.trim()) || c.id === id.trim());
      if (!city) return toast('未找到该城市', 'err');
      const r = await api('/api/auth/city', { method: 'POST', body: JSON.stringify({ city_id: city.id }) });
      state.user = r.user;
      renderUserBox(); renderWelcome();
      toast(`所在城市已切换为 ${city.name}`);
    }
  }));
}

document.addEventListener('click', () => $('#userMenu')?.classList.remove('on'));

/* ---------------- 视图路由 ---------------- */
function go(view) {
  state.view = view;
  $$('.view').forEach(v => v.classList.toggle('active', v.id === `view-${view}`));
  $$('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  window.scrollTo({ top: 0, behavior: 'smooth' });
  if (view === 'trends') loadTrends(state.cityId);
  if (view === 'explore' && !$('#cityWall').children.length) loadCities();
  if (view === 'trips') loadTrips();
  if (view === 'orders') loadOrders();
  if (state.trendES && view !== 'trends') { state.trendES.close(); state.trendES = null; }
}

document.addEventListener('click', (e) => {
  const nav = e.target.closest('[data-nav]');
  if (nav) go(nav.dataset.nav);
  const nb = e.target.closest('.nav-btn');
  if (nb) go(nb.dataset.view);
});

/* ---------------- 图片轮播 ---------------- */
function buildSlides(container, photos) {
  if (!container) return;
  container._slides = [];
  container._idx = 0;
  container.innerHTML = '';
  if (!photos || !photos.length) {
    container._slides = [];
    return;
  }
  photos.forEach((p, i) => {
    const cls = container.dataset.kind || 'cw-slide';
    const d = document.createElement('div');
    d.className = cls + (i === 0 ? ' on' : '');
    d.style.backgroundImage = `url("${p.url}")`;
    container.appendChild(d);
    container._slides.push(d);
  });
}

function nextSlide(container, dotSel) {
  const slides = container._slides || [];
  if (slides.length < 2) return;
  slides[container._idx].classList.remove('on');
  container._idx = (container._idx + 1) % slides.length;
  slides[container._idx].classList.add('on');
  const dots = container.parentElement?.querySelectorAll(dotSel);
  if (dots) dots.forEach((d, i) => d.classList.toggle('on', i === container._idx));
}

/* 全局统一节拍，避免几十个 timer */
setInterval(() => {
  $$('[data-slider]').forEach(el => {
    const kind = el.dataset.kind;
    nextSlide(el, kind === 'rc-slide' ? '.rc-dots i' : '.cw-dots i');
  });
}, 4200);

/* ---------------- 旅行格言轮播 ---------------- */
const QUOTES = [
  { cn: '要么读书，要么旅行', sub: '身体和灵魂，必须有一个在路上。',
    en: 'One must travel, or read, for one does not know what one does not see.', by: '旅行箴言' },
  { cn: '世界是一本书', sub: '不旅行的人，只读了一页。',
    en: 'The world is a book, and those who do not travel read only one page.', by: '圣奥古斯丁' },
  { cn: '人生是旷野，不是轨道', sub: '去没人抵达过的地方，才知道天地有多宽。',
    en: 'Life is a journey, not a destination.', by: '旅行的意义' },
  { cn: '见过山川，才懂人间', sub: '把日子过成诗，把远方过成日常。',
    en: 'Travel is the only thing you buy that makes you richer.', by: '云游' },
  { cn: '山河辽阔，人间值得', sub: '下一站，永远是未知的那一站。',
    en: 'To travel is to live.', by: '汉娜·奥尔森' },
];

let quoteIdx = 0;
function renderQuote(i) {
  const box = $('#quoteLines');
  const dots = $('#quoteDots');
  if (!box) return;
  const q = QUOTES[i % QUOTES.length];
  box.classList.add('fade');
  setTimeout(() => {
    box.innerHTML = `
      <div class="quote-cn">${esc(q.cn)}</div>
      <div class="quote-sub">${esc(q.sub)}</div>
      <div class="quote-en">${esc(q.en)}</div>
      <div class="quote-by">— <b>${esc(q.by)}</b></div>`;
    box.classList.remove('fade');
  }, 320);
  if (dots) $$('i', dots).forEach((d, k) => d.classList.toggle('on', k === i % QUOTES.length));
}

function initQuotes() {
  const dots = $('#quoteDots');
  if (dots) {
    dots.innerHTML = QUOTES.map((_, i) => `<i data-i="${i}" class="${i === 0 ? 'on' : ''}"></i>`).join('');
    $$('i', dots).forEach(d => d.addEventListener('click', () => {
      quoteIdx = Number(d.dataset.i);
      renderQuote(quoteIdx);
      clearInterval(window.__quoteTimer);
      window.__quoteTimer = setInterval(nextQuote, 7000);
    }));
  }
  renderQuote(0);
  clearInterval(window.__quoteTimer);
  window.__quoteTimer = setInterval(nextQuote, 7000);
}
function nextQuote() {
  quoteIdx = (quoteIdx + 1) % QUOTES.length;
  renderQuote(quoteIdx);
}

/* ---------------- 首页 ---------------- */
async function boot() {
  try {
    state.cfg = await api('/api/public-config');
    const h = await api('/api/health');
    $('#statusText').textContent = h.llm_ready ? `Agent 就绪 · ${h.model.split('/').pop()}` : '降级模式（无 Key）';
    $('#sysStatus .dot').classList.toggle('bad', !h.llm_ready);
    const mc = $('#mCities'), mp = $('#mPois');
    if (mc) countUp(mc, h.cities);
    if (mp) countUp(mp, h.pois);
  } catch (e) {
    $('#statusText').textContent = '服务未连接';
    $('#sysStatus .dot').classList.add('bad');
  }

  await loadCitiesCache();
  await auth.load();
  await loadPhotos();
  renderAuthSlides();
  initHero();
  // initQuotes();  // 旅行格言艺术字模块已下线，需要时取消注释即可恢复
  renderWelcome();
  loadSeason();
  loadRadar();
  loadCityStrip();
  renderCitySelect();
  renderOriginSelect();
  initRemember();

  if (!state.token && !localStorage.getItem('wy_skip')) {
    // 支持 /?auth=register 深链直开注册页
    const want = new URLSearchParams(location.search).get('auth') === 'register' ? 'register' : 'login';
    auth.show(want);
  }
}

async function loadCitiesCache() {
  try {
    if (!state.cities.length) state.cities = (await api('/api/cities')).items;
  } catch (e) { /* ignore */ }
}

async function loadPhotos() {
  try {
    const r = await api('/api/photos');
    state.photos = r.cities || {};
  } catch (e) { state.photos = {}; }
}

function photoPool(seed = '') {
  const all = Object.values(state.photos).flat();
  if (all.length < 3) return [];
  const start = Math.abs(hash(seed)) % all.length;
  return [all[start], all[(start + 3) % all.length], all[(start + 7) % all.length]].filter(Boolean);
}

function hash(s) {
  let h = 0;
  for (let i = 0; i < String(s).length; i++) h = (h * 31 + String(s).charCodeAt(i)) | 0;
  return h;
}

function initHero() {
  const box = $('#heroSlides');
  const pool = photoPool('hero');
  box.innerHTML = '';
  if (!pool.length) {
    box.innerHTML = '<div class="hero-noimg"></div>';
    return;
  }
  pool.forEach((p, i) => {
    const d = document.createElement('div');
    d.className = 'hero-slide' + (i === 0 ? ' on' : '');
    d.style.backgroundImage = `url("${p.url}")`;
    box.appendChild(d);
  });
  setInterval(() => nextSlide(box, null), 7000);
}

function renderAuthSlides() {
  const box = $('#authSlides');
  if (!box || box.dataset.done === '1') return;
  const pool = photoPool('auth');
  if (!pool.length) {
    $('#authLayer .auth-visual').classList.add('no-photo');
    box.style.background = 'radial-gradient(760px 560px at 26% 26%,rgba(56,189,248,.4),transparent 62%),radial-gradient(680px 520px at 72% 76%,rgba(167,139,250,.34),transparent 62%),radial-gradient(520px 420px at 50% 50%,rgba(94,234,212,.18),transparent 70%)';
    return;
  }
  $('#authLayer .auth-visual').classList.remove('no-photo');
  box.dataset.done = '1';
  pool.forEach((p, i) => {
    const d = document.createElement('div');
    d.className = 'auth-slide' + (i === 0 ? ' on' : '');
    d.style.backgroundImage = `url("${p.url}")`;
    box.appendChild(d);
  });
  $('#authCredit').textContent = `城市影像来自 Unsplash · 摄影师 ${pool[0].author}`;
  setInterval(() => nextSlide(box, null), 6500);
}

function renderWelcome() {
  const bar = $('#welcomeBar');
  if (!bar) return;
  if (!state.user) {
    bar.className = 'welcome';
    bar.innerHTML = `<span class="wp">未登录也可以看热点和城市；登录后能生成并保存行程</span>
      <span class="wgo" id="wLogin">登录 / 注册 →</span>`;
    $('#wLogin').addEventListener('click', () => auth.show('login'));
    return;
  }
  const city = state.cities.find(c => c.id === state.user.city_id);
  const row = (state.overview || []).find(r => r.city_id === state.user.city_id);
  bar.className = 'welcome';
  bar.innerHTML = `
    <span>👋 <b>${esc(state.user.nickname || state.user.email.split('@')[0])}</b>，你所在的城市是 <b>${esc(city ? city.name : (state.user.city_name || '未设置'))}</b></span>
    ${row ? `<span class="wp">此刻 <b>${esc(row.hot_name)}</b> 热度 ${Math.round(row.heat)}，${esc(row.weather?.text || '')} ${row.weather?.temp != null ? Math.round(row.weather.temp) + '℃' : ''}</span>
      <span class="wgo" id="wGoTrend">看完整榜单 →</span>` : ''}`;
  const goTrend = $('#wGoTrend');
  if (goTrend) goTrend.addEventListener('click', () => { state.cityId = state.user.city_id; go('trends'); });
}

function renderCitySelect() {
  const sel = $('#regCity');
  if (!sel || sel.options.length) return;
  sel.innerHTML = state.cities.map(c => `<option value="${esc(c.id)}"${c.id === 'guiyang' ? ' selected' : ''}>${esc(c.name)} · ${esc(c.province)}</option>`).join('');
}

/* 规划页「出发地」下拉：登录用户默认用其所在城市 */
function renderOriginSelect() {
  const sel = $('#planOrigin');
  if (!sel) return;
  const keep = sel.value;
  sel.innerHTML = '<option value="">未指定（按人均 800 估算）</option>' +
    state.cities.map(c => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('');
  if (keep) sel.value = keep;
  else if (state.user?.city_name) sel.value = state.user.city_name;
  const hint = $('#originHint');
  if (hint) {
    hint.textContent = state.user?.city_name
      ? `默认 ${state.user.city_name}（注册城市）`
      : '用于估算城际交通';
  }
}

/* 首页右侧实时看板 */
function renderHeroSide(items) {
  const list = $('#hsList');
  if (!list || !items || !items.length) return;
  list.innerHTML = items.slice(0, 4).map((it, i) => `
    <div class="hs-row" data-city="${esc(it.city_id)}" style="cursor:pointer">
      <span class="hs-idx">${i + 1}</span>
      <div style="min-width:0">
        <div class="hs-name">${esc(it.hot_name)}</div>
        <div class="hs-sub">
          <span>${esc(it.city)}</span>
          <span>${esc(it.weather?.text || '')} ${it.weather?.temp != null ? Math.round(it.weather.temp) + '℃' : ''}</span>
        </div>
        <div class="hs-bar"><i style="width:${Math.min(100, it.heat)}%"></i></div>
      </div>
      <div class="hs-hot">${Math.round(it.heat)}
        <small class="${it.delta >= 0 ? 'up' : 'down'}">${it.delta >= 0 ? '▲' : '▼'}${Math.abs(it.delta).toFixed(1)}</small>
      </div>
    </div>`).join('');
  $('#hsTime').textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  $$('#hsList .hs-row').forEach(r => r.addEventListener('click', () => {
    state.cityId = r.dataset.city;
    go('trends');
  }));
}

/* ---------------- 时令 · 节气 / 应季 / 玩法 / 风味 / 线路 / 矩阵 ---------------- */
function renderTermBar(term) {
  if (!term) return;
  $('#tbName').textContent = term.name;
  $('#tbSeason').textContent = term.season || '';
  $('#tbDate').textContent = term.date;
  $('#tbCount').textContent = `距${term.next} ${term.days_to_next} 天`;
  $('#tbPheno').textContent = term.pheno ? `「${term.pheno}」 · ${term.climate}` : term.climate;
  $('#tbAdvice').textContent = term.advice;

  // 年度进度环：已过天数占全年比例
  const arc = $('#tbArc');
  if (arc) {
    const C = 2 * Math.PI * 38;
    const start = new Date(term.year_terms[0].date).getTime();
    const end = new Date(term.year_terms[term.year_terms.length - 1].date).getTime();
    const now = new Date(term.today).getTime();
    const p = Math.max(0.02, Math.min(1, (now - start) / (end - start)));
    arc.setAttribute('stroke-dasharray', `${(C * p).toFixed(1)} ${C.toFixed(1)}`);
  }

  const today = term.today;
  $('#tbTerms').innerHTML = term.year_terms.map(t => {
    const cls = t.date === term.date ? 'on' : (t.date < today ? 'past' : (t.name === term.next ? 'next' : ''));
    return `<i class="${cls}" title="${esc(t.date)}">${esc(t.name)}</i>`;
  }).join('');
}

function renderFestivals(list) {
  const box = $('#tbFest');
  if (!box) return;
  if (!list || !list.length) { box.innerHTML = ''; return; }
  box.innerHTML = list.map(f =>
    `<span><b>${esc(f.city)}</b> · ${esc(f.name)}</span>`).join('');
}

function renderSeasonRail(rows) {
  const box = $('#seasonRail');
  if (!box) return;
  if (!rows || !rows.length) { box.innerHTML = '<div class="skel-row"></div>'; return; }
  box.innerHTML = rows.map(c => `
    <article class="sc" style="--ac:${esc(c.accent)}" data-city="${esc(c.city_id)}">
      <div class="sc-top">
        <div class="sc-city"><i></i>${esc(c.city)}</div>
        <div class="sc-prov">${esc(c.province)}</div>
      </div>
      <div class="sc-sign">${esc(c.signature || '')}</div>
      <div class="sc-tags">${(c.tags || []).slice(0, 3).map(t => `<span>${esc(t)}</span>`).join('')}</div>
      ${c.festival ? `<div class="sc-fest">🎪 ${esc(c.festival)}</div>` : ''}
    </article>`).join('');
  $$('.sc', box).forEach(el => el.addEventListener('click', () => {
    state.cityId = el.dataset.city;
    go('explore');
    openCity(el.dataset.city);
  }));
}

function renderThemes(themes) {
  const box = $('#themeWall');
  if (!box) return;
  if (!themes || !themes.length) { box.innerHTML = ''; return; }
  box.innerHTML = themes.map(t => `
    <article class="th" style="--ac:${esc(t.color)}" data-theme="${esc(t.name)}" data-key="${esc(t.id)}">
      <div class="th-ico">${esc(t.icon)}</div>
      <h3>${esc(t.name)}</h3>
      <p>${esc(t.desc)}</p>
      <div class="th-cities">${(t.cities || []).slice(0, 4).map(c =>
        `<span>${esc(c.city)}${c.top ? '' : ' · ' + esc((c.foods || [])[0] || '避暑首选')}</span>`).join('')}</div>
      <div class="th-foot">
        <span class="th-stat"><b>${t.total_cities}</b> 城 · <b>${t.total_pois}</b> 个相关景点</span>
        <span class="th-go">按这个玩法排 →</span>
      </div>
    </article>`).join('');
  $$('.th', box).forEach(el => el.addEventListener('click', () => {
    const t = themes.find(x => x.id === el.dataset.key);
    const city = (t && t.cities && t.cities[0] && t.cities[0].city) || '';
    const q = city
      ? `${city}，${el.dataset.theme}主题，2天，节奏适中`
      : `想玩${el.dataset.theme}，帮我排行程`;
    $('#heroQuery').value = q;
    $('#heroForm').dispatchEvent(new Event('submit', { cancelable: true }));
  }));
}

function renderFoods(rows) {
  const box = $('#foodGrid');
  if (!box) return;
  if (!rows || !rows.length) { box.innerHTML = ''; return; }
  box.innerHTML = rows.map(f => `
    <article class="fd" style="--ac:${esc(f.accent)}" data-city="${esc(f.city_id)}">
      <div class="fd-head">
        <span class="fd-city">${esc(f.city)}</span>
        <span class="fd-prov">${esc(f.province)}</span>
      </div>
      <div class="fd-sign">${esc(f.signature || '')}</div>
      <div class="fd-dishes">${(f.foods || []).slice(0, 4).map(x => `<span>${esc(x)}</span>`).join('')}</div>
      ${(f.markets || []).length ? `<div class="fd-mkt">老饕聚集地 · <b>${esc(f.markets[0].name)}</b></div>` : ''}
    </article>`).join('');
  $$('.fd', box).forEach(el => el.addEventListener('click', () => {
    state.cityId = el.dataset.city;
    go('explore');
    openCity(el.dataset.city);
  }));
}

function renderRoutes(rows) {
  const box = $('#routeGrid');
  if (!box) return;
  if (!rows || !rows.length) { box.innerHTML = ''; return; }
  box.innerHTML = rows.map(r => {
    const photos = state.photos[r.cover] || [];
    return `
    <article class="rt" style="--ac:${esc(r.color)}" data-route="${esc(r.name)}"
             data-city="${esc(r.cover || '')}">
      <div class="rt-media">
        <div data-slider data-kind="rc-slide" style="position:absolute;inset:0"></div>
        ${photos.length ? '' : RIDGE}
        <span class="rt-season ${r.in_season ? 'in' : ''}">${esc(r.season_hint)}</span>
      </div>
      <div class="rt-body">
        <div class="rt-theme">${esc(r.theme)}</div>
        <div class="rt-name">${esc(r.name)}</div>
        <div class="rt-tags">${(r.tags || []).map(t => `<span>${esc(t)}</span>`).join('')}</div>
        <div class="rt-steps">${(r.route || []).slice(0, 3).map(s => `<div>${esc(s)}</div>`).join('')}</div>
        <div class="rt-tip">${esc(r.tip)}</div>
        <div class="rt-foot">
          <span class="rt-meta"><b>${esc(r.days)}</b> 天 · ${esc(r.budget)} · ${esc(r.pace)}</span>
          <span class="rt-go">照这条走 →</span>
        </div>
      </div>
    </article>`;
  }).join('');
  $$('.rt', box).forEach(card => {
    const media = $('[data-slider]', card);
    buildSlides(media, state.photos[card.dataset.city] || []);
  });
  $$('.rt', box).forEach(el => el.addEventListener('click', () => {
    const name = el.dataset.route;
    const q = `按「${name}」这条经典线路安排行程`;
    $('#heroQuery').value = q;
    $('#heroForm').dispatchEvent(new Event('submit', { cancelable: true }));
  }));
}

function renderMatrix(matrix) {
  const box = $('#matrixScroll');
  if (!box || !matrix) return;
  const cm = matrix.current_month;
  const head = `<div class="mhead"><div>城市 / 月份</div>${
    Array.from({ length: 12 }, (_, i) =>
      `<div class="${i + 1 === cm ? 'cur' : ''}">${i + 1}月</div>`).join('')}</div>`;

  const rows = matrix.cities.map(c => {
    const cells = Array.from({ length: 12 }, (_, i) => {
      const m = i + 1;
      const on = c.months.includes(m);
      // 亮度按该城最佳季覆盖的月份数分档：覆盖越多说明全年越适合
      const n = c.months.length;
      const lv = on ? (n <= 3 ? 1 : n <= 5 ? 2 : n <= 8 ? 3 : 4) : 0;
      return `<div class="mcell ${on ? 'on lv' + lv : ''} ${m === cm ? 'now' : ''}"
                   data-city="${esc(c.city_id)}" data-name="${esc(c.city)}"
                   title="${esc(c.city)} · ${m}月${on ? ' 适合前往' : ''}"></div>`;
    }).join('');
    return `<div class="mrow">
      <div class="mname" title="${esc(c.city)} · ${esc(c.best_season)}">${esc(c.city)}</div>${cells}</div>`;
  }).join('');

  box.innerHTML = head + rows;
  $$('.mcell.on', box).forEach(el => el.addEventListener('click', () => {
    state.cityId = el.dataset.city;
    go('explore');
    openCity(el.dataset.city);
  }));
}

async function loadSeason() {
  try {
    const d = await api('/api/season');
    state.themeCity = {};
    (d.themes || []).forEach(t => { state.themeCity[t.id] = (t.cities[0] || {}).city || ''; });
    renderTermBar(d.term);
    renderFestivals(d.festivals);
    renderSeasonRail(d.best_cities);
    renderThemes(d.themes);
    renderFoods(d.foods);
    renderRoutes(d.routes);
    renderMatrix(d.matrix);
  } catch (e) { /* 时令模块失败不影响主流程 */ }
}

async function loadRadar() {
  const box = $('#radar');
  try {
    const { items } = await api('/api/trends/overview?limit=14');
    state.overview = items;
    renderWelcome();
    renderHeatmap(items);
    renderHeroSide(items);
    box.innerHTML = items.slice(0, 8).map((it) => {
      const photos = state.photos[it.city_id] || [];
      return `
      <article class="rc" style="--ac:${esc(it.accent)}" data-city="${esc(it.city_id)}">
        <div class="rc-media">
          <div data-slider data-kind="rc-slide" style="position:absolute;inset:0"></div>
          ${photos.length ? '' : RIDGE}
        </div>
        <div class="rc-body">
          <div class="rc-top">
            <div>
              <div class="rc-city"><i></i>${esc(it.city)}</div>
              <div class="rc-prov">${esc(it.province)} · ${esc((it.tags || [])[0] || '')}</div>
            </div>
            <div class="rc-heat">${Math.round(it.heat)}<small>热度</small></div>
          </div>
          <div class="rc-name">${esc(it.hot_name)} <span class="lvl ${esc(it.level_key)}">${esc(it.level)}</span></div>
          <div class="bar"><i style="width:${Math.min(100, it.heat)}%"></i></div>
          <div class="rc-foot">
            <span>${esc(it.weather?.text || '')} ${it.weather?.temp != null ? Math.round(it.weather.temp) + '℃' : ''}</span>
            <span class="${it.delta >= 0 ? 'up' : 'down'}">${it.delta >= 0 ? '▲' : '▼'} ${Math.abs(it.delta).toFixed(1)}</span>
          </div>
        </div>
      </article>`;
    }).join('');

    $$('.rc', box).forEach(card => {
      const media = $('[data-slider]', card);
      buildSlides(media, state.photos[card.dataset.city] || []);
      card.addEventListener('click', () => { state.cityId = card.dataset.city; go('trends'); });
    });
  } catch (e) {
    box.innerHTML = `<div class="warn-box">热点数据加载失败：${esc(e.message)}</div>`;
  }
}

/* ---------- 热度地图 ---------- */
/* 密集区域的标签手动错位，避免贵州几城叠在一起 */
const LABEL_POS = {
  guiyang: [-4, 26], qiandongnan: [26, 30], zunyi: [-26, -20], anshun: [-52, 4],
  shanghai: [26, -10], hangzhou: [-24, 16], lijiang: [-30, -4], dali: [26, 14],
  chengdu: [-28, -12], chongqing: [24, 18], guilin: [30, 6], xiamen: [12, 20],
  kunming: [30, -12], qingdao: [24, -12], changsha: [-26, 14], nanjing: [20, 20],
  suzhou: [-22, -16], harbin: [0, -20],
  guangzhou: [26, 14], shenzhen: [-20, 16], wuhan: [16, -12], tianjin: [22, -10],
  luoyang: [-24, 4], sanya: [24, 10], lhasa: [-20, -6], urumqi: [-16, -6],
  dunhuang: [-24, 10], fuzhou: [22, 12],
};

/* ---------- 真地图（省级边界 + 城市光点） ---------- */
let CHINA_MAP = null;

async function loadChinaMap() {
  if (CHINA_MAP) return CHINA_MAP;
  try {
    const r = await fetch('/static/assets/china-geo.json');
    if (!r.ok) throw new Error('地图数据缺失');
    CHINA_MAP = await r.json();
  } catch (e) {
    CHINA_MAP = null;
  }
  return CHINA_MAP;
}

function renderHeatmap(items) {
  const svg = $('#heatMap');
  if (!svg || !items || !items.length) return;
  loadChinaMap().then((geo) => {
    if (!geo) { renderGridMap(items); return; }
    drawChinaMap(svg, geo, items);
  });
}

function drawChinaMap(svg, geo, items) {
  const W = geo.width, H = geo.height;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  const px = (lon) => (lon - geo.lon_range[0]) / (geo.lon_range[1] - geo.lon_range[0]) * W;
  const py = (lat) => (geo.lat_range[1] - lat) / (geo.lat_range[1] - geo.lat_range[0]) * H;

  const byProv = {};
  for (const it of items) {
    const c = state.cities.find(x => x.id === it.city_id);
    if (!c) continue;
    const key = geo.city_province[c.id];
    if (!key) continue;
    (byProv[key] = byProv[key] || []).push(it);
  }

  const provPaths = Object.entries(geo.provinces).map(([name, d]) => {
    const list = byProv[name] || [];
    const avg = list.length ? list.reduce((s, i) => s + i.heat, 0) / list.length : 0;
    const covered = list.length > 0;
    const fill = covered
      ? `rgba(94,234,212,${(0.05 + (avg / 100) * 0.22).toFixed(3)})`
      : 'rgba(255,255,255,.022)';
    const stroke = covered ? 'rgba(94,234,212,.38)' : 'rgba(255,255,255,.08)';
    return `<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="1" stroke-linejoin="round"/>`;
  }).join('');

  const provLabels = Object.entries(geo.centers)
    .filter(([k]) => byProv[k])
    .map(([k, xy]) => `<text x="${xy[0]}" y="${xy[1]}" class="hm-prov" text-anchor="middle">${esc(k.replace(/省|市|自治区|特别行政区/g, ''))}</text>`)
    .join('');

  const nodes = items.map((it) => {
    const city = state.cities.find(c => c.id === it.city_id);
    if (!city) return '';
    const x = px(city.lon), y = py(city.lat);
    const r = 4 + (it.heat / 100) * 8;
    const color = LEVEL_COLOR[it.level_key] || '#4ade80';
    const [ldx, ldy] = LABEL_POS[it.city_id] || [0, -(r + 9)];
    return `
      <g class="hm-city" data-city="${esc(it.city_id)}" data-name="${esc(it.city)}"
         data-hot="${esc(it.hot_name)}" data-heat="${Math.round(it.heat)}" data-level="${esc(it.level)}">
        <circle cx="${x}" cy="${y}" r="${r + 7}" fill="${color}" opacity=".12">
          <animate attributeName="r" values="${r + 4};${r + 15};${r + 4}" dur="3.2s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values=".2;.02;.2" dur="3.2s" repeatCount="indefinite"/>
        </circle>
        <circle class="core" cx="${x}" cy="${y}" r="${r}" fill="${color}" opacity=".95"/>
        <circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="rgba(255,255,255,.55)" stroke-width=".8"/>
        <text x="${x + ldx}" y="${y + ldy}" class="hm-label" text-anchor="middle">${esc(it.city)}</text>
      </g>`;
  }).join('');

  svg.innerHTML = `<g class="hm-provinces">${provPaths}</g>
    <g class="hm-provlabels">${provLabels}</g>
    <g class="hm-nodes">${nodes}</g>`;

  bindMapTips(svg);
}

function bindMapTips(svg) {
  const tip = $('#hmTip');
  $$('.hm-city', svg).forEach(g => {
    g.addEventListener('mouseenter', () => {
      const box = svg.getBoundingClientRect();
      const b = g.getBoundingClientRect();
      tip.innerHTML = `<b>${esc(g.dataset.name)}</b> · ${esc(g.dataset.hot)}<br>热度 ${g.dataset.heat} · ${esc(g.dataset.level)}`;
      tip.style.left = `${b.left - box.left + b.width / 2}px`;
      tip.style.top = `${b.top - box.top}px`;
      tip.classList.add('on');
    });
    g.addEventListener('mouseleave', () => tip.classList.remove('on'));
    g.addEventListener('click', () => { state.cityId = g.dataset.city; go('trends'); });
  });
}

function renderGridMap(items) {
  const svg = $('#heatMap');
  if (!svg || !items || !items.length) return;
  const W = 900, H = 420, padX = 46, padY = 34;
  const lonMin = 76, lonMax = 128, latMin = 20, latMax = 45;
  const px = (lon) => padX + ((lon - lonMin) / (lonMax - lonMin)) * (W - padX * 2);
  const py = (lat) => padY + ((latMax - lat) / (latMax - latMin)) * (H - padY * 2);

  let grid = '';
  for (let lon = 80; lon <= 130; lon += 10) {
    grid += `<line x1="${px(lon)}" y1="${padY}" x2="${px(lon)}" y2="${H - padY}" stroke="rgba(255,255,255,.05)" stroke-dasharray="2 6"/>`;
    grid += `<text x="${px(lon)}" y="${H - padY + 14}" class="hm-label" text-anchor="middle">${lon}°E</text>`;
  }
  for (let lat = 20; lat <= 50; lat += 10) {
    grid += `<line x1="${padX}" y1="${py(lat)}" x2="${W - padX}" y2="${py(lat)}" stroke="rgba(255,255,255,.05)" stroke-dasharray="2 6"/>`;
    grid += `<text x="${padX - 10}" y="${py(lat) + 3}" class="hm-label" text-anchor="end">${lat}°N</text>`;
  }

  const nodes = items.map((it) => {
    const city = state.cities.find(c => c.id === it.city_id);
    if (!city) return '';
    const x = px(city.lon), y = py(city.lat);
    const r = 4 + (it.heat / 100) * 9;
    const color = LEVEL_COLOR[it.level_key] || '#4ade80';
    const [ldx, ldy] = LABEL_POS[it.city_id] || [0, -(r + 8)];
    return `
      <g class="hm-city" data-city="${esc(it.city_id)}" data-name="${esc(it.city)}"
         data-hot="${esc(it.hot_name)}" data-heat="${Math.round(it.heat)}" data-level="${esc(it.level)}">
        <circle cx="${x}" cy="${y}" r="${r + 7}" fill="${color}" opacity=".12">
          <animate attributeName="r" values="${r + 4};${r + 14};${r + 4}" dur="3.2s" repeatCount="indefinite"/>
          <animate attributeName="opacity" values=".18;.02;.18" dur="3.2s" repeatCount="indefinite"/>
        </circle>
        <circle class="core" cx="${x}" cy="${y}" r="${r}" fill="${color}" opacity=".92"/>
        <circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="rgba(255,255,255,.5)" stroke-width=".8"/>
        <text x="${x + ldx}" y="${y + ldy}" class="hm-label" text-anchor="middle">${esc(it.city)}</text>
      </g>`;
  }).join('');

  svg.innerHTML = `${grid}
    <text x="${W / 2}" y="22" class="hm-label" text-anchor="middle" style="font-size:11px;fill:#64748b">
      经纬网格 · 光点半径与热度正相关 · 点击查看城市实时榜单
    </text>
    ${nodes}`;

  const tip = $('#hmTip');
  $$('.hm-city', svg).forEach(g => {
    g.addEventListener('mouseenter', () => {
      const box = svg.getBoundingClientRect();
      const b = g.getBoundingClientRect();
      tip.innerHTML = `<b>${esc(g.dataset.name)}</b> · ${esc(g.dataset.hot)}<br>热度 ${g.dataset.heat} · ${esc(g.dataset.level)}`;
      tip.style.left = `${b.left - box.left + b.width / 2}px`;
      tip.style.top = `${b.top - box.top}px`;
      tip.classList.add('on');
    });
    g.addEventListener('mouseleave', () => tip.classList.remove('on'));
    g.addEventListener('click', () => { state.cityId = g.dataset.city; go('trends'); });
  });
}

/* ---------------- 城市条 ---------------- */
async function loadCityStrip() {
  try {
    if (!state.cities.length) state.cities = (await api('/api/cities')).items;
    const note = $('#hsNote');
    if (note) note.textContent = `全国 ${state.cities.length} 城 · 每 20 秒刷新`;
    $('#cityStrip').innerHTML = state.cities.map(c => `
      <button class="cs-item ${c.id === state.cityId ? 'on' : ''}" data-id="${esc(c.id)}" style="--ac:${esc(c.accent)}">
        <i></i>${esc(c.name)}
      </button>`).join('');
    $$('#cityStrip .cs-item').forEach(b => b.addEventListener('click', () => {
      state.cityId = b.dataset.id;
      $$('#cityStrip .cs-item').forEach(x => x.classList.toggle('on', x === b));
      loadTrends(state.cityId);
    }));
  } catch (e) { /* ignore */ }
}

/* ---------------- 规划页 ---------------- */
const STEP_LABEL = { intake: '解析需求', context: '采集实时数据', compose: '编排每日行程', review: '质量校验' };

function resetSteps() {
  $$('.stp').forEach(s => { s.className = 'stp'; $('small', s).textContent = '等待中'; });
}

function setStep(key, status, detail) {
  const el = $(`.stp[data-step="${key}"]`);
  if (!el) return;
  const small = $('small', el);
  if (status === 'start' || status === 'progress') { el.className = 'stp run'; small.textContent = detail || '进行中…'; }
  else if (status === 'done') { el.className = 'stp ok'; small.textContent = detail || '完成'; }
  else if (status === 'warn' || status === 'error') { el.className = 'stp warn'; small.textContent = detail || '提示'; }
}

$('#heroForm')?.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = $('#heroQuery').value.trim();
  if (!q) return toast('先说说你的计划吧', 'err');
  if (!state.token) { auth.show('login'); return toast('生成行程需要先登录', 'err'); }
  $('#planQuery').value = q;
  go('planner');
  setTimeout(runPlan, 320);
});

$('#heroChips')?.addEventListener('click', (e) => {
  const btn = e.target.closest('.chip');
  if (!btn) return;
  $('#heroQuery').value = btn.dataset.q;
  $('#heroQuery').focus();
});

$$('.qg .chips').forEach(group => {
  group.addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (group.classList.contains('multi')) return b.classList.toggle('on');
    $$('button', group).forEach(x => x.classList.toggle('on', x === b));
  });
});

$('#planBtn')?.addEventListener('click', runPlan);

function composeQuery() {
  let q = $('#planQuery').value.trim();
  const picks = $$('.qg .chips button.on').map(b => b.dataset.t).filter(Boolean);
  if (picks.length) q += (q ? '，' : '') + picks.join('，');
  return q;
}

async function runPlan() {
  if (state.planRunning) return toast('正在生成中…');
  if (!state.token) { auth.show('login'); return toast('生成行程需要先登录', 'err'); }
  const q = composeQuery();
  if (!q) return toast('请先描述你的行程需求', 'err');

  state.planRunning = true;
  $('#planBtn').disabled = true;
  $('#planBtn').textContent = 'Agent 正在工作…';
  $('#planEmpty').classList.add('hidden');
  $('#planResult').classList.add('hidden');
  $('#planLoading').classList.remove('hidden');
  resetSteps();

  let gotPlan = false;
  try {
    const origin = $('#planOrigin')?.value || '';
    await streamSSE('/api/plan', { query: q, origin }, (ev, data) => {
      if (ev === 'step') setStep(data.key, data.status, data.detail);
      else if (ev === 'plan') {
        gotPlan = true;
        state.plan = data;
        $('#planLoading').classList.add('hidden');
        renderPlan(data);
      } else if (ev === 'error') toast(data.message, 'err');
    });
  } catch (e) {
    toast('规划失败：' + e.message, 'err');
    if (e.message.includes('登录')) auth.show('login');
  } finally {
    state.planRunning = false;
    $('#planBtn').disabled = false;
    $('#planBtn').textContent = '生成行程';
    $('#planLoading').classList.add('hidden');
    if (!gotPlan) $('#planEmpty').classList.remove('hidden');
  }
}

function typeWriter(el, text, speed = 9) {
  el.textContent = '';
  let i = 0;
  const tick = () => {
    if (i >= text.length) return;
    el.textContent += text.slice(i, i + 2);
    i += 2;
    setTimeout(tick, speed);
  };
  tick();
}

function renderPlan(result) {
  const box = $('#planResult');
  const plan = result.plan || {};
  const city = result.city || {};
  if (!plan.itinerary || !plan.itinerary.length) {
    box.innerHTML = `<div class="warn-box">未能生成有效行程。${esc((result.errors || []).join('；'))}</div>`;
    box.classList.remove('hidden');
    return;
  }

  const accent = city.accent || '#5eead4';
  const budget = plan.budget || {};
  const total = Number(budget.total || 0);
  const colors = ['#5eead4', '#38bdf8', '#a78bfa', '#fbbf24', '#f472b6'];

  box.innerHTML = `
    <div class="plan-hero" style="--ac:${esc(accent)}">
      <div class="ph-top">
        <div class="ph-city">${esc(plan.city || city.name)}</div>
        <div class="ph-pill">${esc(plan.days)} 天</div>
        <div class="ph-pill">${esc(result.brief?.people || 2)} 人</div>
        <div class="ph-pill">${esc(result.brief?.budget_level || '中等')}</div>
        <div class="ph-pill">${esc(result.brief?.pace || '适中')}</div>
        ${result.ok ? '' : '<div class="ph-pill" style="color:#fcd34d;border-color:rgba(251,191,36,.35)">含提示</div>'}
      </div>
      <div class="ph-theme">${esc(plan.theme || '')}</div>
      <div class="ph-sum" id="planSummary"></div>
      <div class="ph-high">${(plan.highlights || []).map(h => `<span>${esc(h)}</span>`).join('')}</div>
    </div>
    <div class="plan-actions">
      <button class="ghost" id="savePlanBtn">☆ 收藏</button>
      <button class="ghost" id="sharePlanBtn">⇗ 分享链接</button>
      <button class="ghost" id="exportBtn">⤓ 导出长图</button>
      <button class="ghost" id="toOrderBtn">＋ 生成订单</button>
      <span style="font-size:10.5px;color:var(--dim);align-self:center;margin-left:4px">
        ${result.brief?.origin ? '出发地 ' + esc(result.brief.origin) : '未指定出发地'}
      </span>
    </div>
    <div class="daytabs" id="dayTabs">
      ${plan.itinerary.map((d, i) => `
        <button class="dtab ${i === 0 ? 'on' : ''}" data-day="${i}">
          <b>Day ${d.day || i + 1}</b>
          <small>${esc((d.date || '').slice(5))} · ${esc(d.title || '')}</small>
        </button>`).join('')}
    </div>
    <div id="dayPanel"></div>
    <div class="plan-foot">
      <div class="card-out">
        <h5>预算拆解</h5>
        <div class="budget-flex">
          <div class="donut">
            <svg width="112" height="112" viewBox="0 0 112 112">
              <circle cx="56" cy="56" r="46" fill="none" stroke="rgba(255,255,255,.07)" stroke-width="11"/>
              ${donutArcs(budget.breakdown || {}, total, colors)}
            </svg>
            <div class="donut-center"><b>¥${Math.round(total)}</b><span>预估总花费</span></div>
          </div>
          <div class="bd-list">
            ${Object.entries(budget.breakdown || {}).map(([k, v], i) => `
              <div class="bd-row"><i style="background:${colors[i % colors.length]}"></i>
                <span>${esc(k)}</span><b>¥${Math.round(v)}</b></div>`).join('')}
          </div>
        </div>
      </div>
      <div class="card-out">
        <h5>行前提示</h5>
        <ul class="tip-list">${(plan.tips || []).map(t => `<li>${esc(t)}</li>`).join('')}</ul>
        <div class="pack-tags">${(plan.packing || []).map(p => `<span>${esc(p)}</span>`).join('')}</div>
      </div>
    </div>
    ${(result.errors?.length || result.warnings?.length) ? `<div class="warn-box">
      ${result.errors?.length ? '校验：' + esc(result.errors.slice(0, 2).join('；')) : ''}
      ${result.errors?.length && result.warnings?.length ? ' ｜ ' : ''}
      ${result.warnings?.length ? '节奏提示：' + esc(result.warnings.slice(0, 2).join('；')) : ''}
    </div>` : ''}
  `;
  box.classList.remove('hidden');
  typeWriter($('#planSummary'), plan.summary || '');

  let planId = null;
  const ensureSaved = async () => {
    if (planId) return planId;
    const r = await api('/api/plans', { method: 'POST', body: JSON.stringify({ payload: result }) });
    planId = r.id;
    return planId;
  };

  $('#savePlanBtn').addEventListener('click', async () => {
    try { await ensureSaved(); toast('已收藏，可在「我的行程」查看'); }
    catch (e) { toast(e.message, 'err'); }
  });

  $('#sharePlanBtn').addEventListener('click', async () => {
    try {
      const id = await ensureSaved();
      const r = await api(`/api/plans/${id}/share`, { method: 'POST' });
      const url = location.origin + r.path;
      openModal(`<h3>分享这份行程</h3>
        <p class="mh">任何拿到链接的人都能查看（无需登录），你的邮箱不会暴露。</p>
        <div class="share-box"><input id="shareUrl" readonly value="${esc(url)}">
          <button class="primary" id="copyShare">复制</button></div>
        <div class="modal-actions"><button class="ghost" id="openShare">新窗口打开</button></div>`);
      $('#copyShare').addEventListener('click', async () => {
        const ok = await copyText(url);
        toast(ok ? '链接已复制' : '复制失败，请手动选中', ok ? '' : 'err');
      });
      $('#openShare').addEventListener('click', () => window.open(r.path, '_blank'));
    } catch (e) { toast(e.message, 'err'); }
  });

  $('#exportBtn').addEventListener('click', () => exportPlanImage(result));

  $('#toOrderBtn').addEventListener('click', async () => {
    const btn = $('#toOrderBtn');
    btn.disabled = true;
    btn.textContent = '生成中…';
    try {
      const id = await ensureSaved();
      const r = await api('/api/orders/import', {
        method: 'POST',
        body: JSON.stringify({ payload: result, plan_id: id }),
      });
      toast(`已生成 ${r.count} 条订单草稿`);
      go('orders');
    } catch (e) {
      toast(e.message, 'err');
    } finally {
      btn.disabled = false;
      btn.textContent = '＋ 生成订单';
    }
  });

  // 事件委托：点「改这一天」打开修改弹窗
  $('#dayPanel').onclick = (e) => {
    const btn = e.target.closest('.day-edit');
    if (btn) openDayEditor(result, Number(btn.dataset.day));
  };

  const tabs = $$('#dayTabs .dtab');
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.toggle('on', x === t));
    renderDay(plan.itinerary[Number(t.dataset.day)]);
  }));
  renderDay(plan.itinerary[0]);
}

function donutArcs(breakdown, total, colors) {
  if (!total) return '';
  const C = 2 * Math.PI * 46;
  let offset = 0;
  return Object.values(breakdown).map((v, i) => {
    const len = (v / total) * C;
    const seg = `<circle cx="56" cy="56" r="46" fill="none" stroke="${colors[i % colors.length]}"
      stroke-width="11" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-offset}"
      stroke-linecap="butt" opacity=".92"/>`;
    offset += len;
    return seg;
  }).join('');
}

function renderDay(day) {
  if (!day) return;
  const w = day.weather || {};
  const items = day.items || [];
  const meals = day.meals || [];
  const timeline = [...items.map(i => ({ ...i, kind: 'spot' })), ...meals.map(m => ({ ...m, kind: 'meal' }))]
    .sort((a, b) => String(a.time || '').localeCompare(String(b.time || '')));

  $('#dayPanel').innerHTML = `
    <div class="day-panel">
      <div class="day-head">
        <h4>Day ${day.day} · ${esc(day.title || '')}</h4>
        <div class="dweather">
          <span>${ICON[w.icon] || '⛅'} <b>${esc(w.text || '')}</b></span>
          <span>${w.t_min ?? '-'}~${w.t_max ?? '-'}℃</span>
          <span>降水 <b>${w.rain_prob ?? '-'}%</b></span>
          <span>当日花费 <b>¥${Math.round(day.day_cost || 0)}</b></span>
        </div>
        <span class="day-edit" data-day="${day.day}">✎ 改这一天</span>
      </div>
      <div class="tl">
        ${timeline.map(it => it.kind === 'meal' ? `
          <div class="tl-item meal">
            <div class="ti-top">
              <span class="ti-time">${esc(it.time || '')}</span>
              <span class="ti-name">${esc(it.name || '用餐')}</span>
              <span class="ti-type">餐饮</span>
            </div>
            <div class="ti-desc">${esc(it.place || '')}</div>
            <div class="ti-meta"><span>人均 <i>¥${Math.round(it.cost || 0)}</i></span></div>
          </div>` : `
          <div class="tl-item">
            <div class="ti-top">
              <span class="ti-time">${esc(it.time || '')}</span>
              <span class="ti-name">${esc(it.name || '')}</span>
              <span class="ti-type">${esc(it.type || '景点')}</span>
            </div>
            <div class="ti-desc">${esc(it.desc || '')}</div>
            <div class="ti-meta">
              <span>游玩 <i>${it.hours || 2}h</i></span>
              <span>门票 <i>¥${it.cost || 0}</i></span>
              <span>交通 <i>${esc(it.transport || '步行/打车')}</i></span>
            </div>
            ${it.tip ? `<div class="ti-tip">${esc(it.tip)}</div>` : ''}
          </div>`).join('')}
      </div>
      ${day.stay ? `<div class="pack-tags"><span>🏨 建议住宿：${esc(day.stay)}</span></div>` : ''}
    </div>`;
}

/* ---------------- 单日重排 ---------------- */
function openDayEditor(result, dayNo) {
  const day = result.plan.itinerary[dayNo - 1];
  if (!day) return;
  const current = (day.items || []).map(i => i.name).join(' · ') || '（空）';
  openModal(`
    <h3>修改 Day ${dayNo}</h3>
    <p class="mh">${esc(day.title || '')}<br>当前安排：${esc(current)}</p>
    <label class="fld"><span>想怎么改？</span>
      <textarea id="reviseText" rows="3" placeholder="例如：换一个室内景点，晚上加个夜市"
        style="width:100%;background:rgba(255,255,255,.045);border:1px solid var(--line);border-radius:11px;
        padding:11px 13px;color:var(--txt);font-family:inherit;font-size:13px;outline:0;resize:vertical"></textarea>
    </label>
    <p class="mh" style="margin:0 0 6px">只会重排这一天，其他天保持不变，约 20-40 秒。</p>
    <div class="modal-actions">
      <button class="primary" id="reviseGo">让 AI 重排这一天</button>
    </div>`);

  $('#reviseGo').addEventListener('click', async () => {
    const instruction = $('#reviseText').value.trim();
    const btn = $('#reviseGo');
    btn.disabled = true;
    btn.textContent = '重排中…';
    try {
      const r = await api('/api/plan/revise', {
        method: 'POST',
        body: JSON.stringify({ plan: result.plan, day: dayNo, instruction }),
      });
      result.plan = r.plan;
      closeModal();
      renderPlan(result);
      const tab = $(`#dayTabs .dtab[data-day="${dayNo - 1}"]`);
      if (tab) tab.click();
      toast(`Day ${dayNo} 已重排`);
    } catch (e) {
      toast(e.message, 'err');
      btn.disabled = false;
      btn.textContent = '让 AI 重排这一天';
    }
  });
}

/* ---------------- 导出长图 ---------------- */
function hexA(hex, alpha) {
  const h = (hex || '#5eead4').replace('#', '');
  const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

function wrapText(ctx, text, x, y, maxW, lineH, maxLines = 3) {
  const chars = String(text || '').split('');
  let line = '', lines = 0;
  for (const ch of chars) {
    const test = line + ch;
    if (ctx.measureText(test).width > maxW && line) {
      ctx.fillText(line, x, y + lines * lineH);
      lines += 1;
      line = ch;
      if (lines >= maxLines - 1) break;
    } else {
      line = test;
    }
  }
  if (lines < maxLines) ctx.fillText(line, x, y + lines * lineH);
  return y + lines * lineH;
}

async function exportPlanImage(result) {
  const plan = result.plan || {};
  if (!plan.itinerary) return toast('没有可导出的行程', 'err');
  toast('正在生成图片…');

  const W = 760, PAD = 46;
  const days = plan.itinerary;
  const summaryLines = Math.min(3, Math.ceil((plan.summary || '').length / 26));
  let H = 210 + summaryLines * 27 + 40;
  for (const d of days) {
    H += 68 + (d.items || []).length * 76 + (d.meals || []).length * 34 + 26;
  }
  H += 150;

  const cv = document.createElement('canvas');
  const s = 2;
  cv.width = W * s;
  cv.height = H * s;
  const ctx = cv.getContext('2d');
  ctx.scale(s, s);
  ctx.textBaseline = 'top';

  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, '#0c1322');
  bg.addColorStop(1, '#070a11');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  const acc = result.city?.accent || '#5eead4';
  const hg = ctx.createLinearGradient(0, 0, W, 240);
  hg.addColorStop(0, hexA(acc, 0.3));
  hg.addColorStop(1, 'rgba(7,10,17,0)');
  ctx.fillStyle = hg;
  ctx.fillRect(0, 0, W, 240);

  let y = 52;
  ctx.fillStyle = '#ffffff';
  ctx.font = '800 40px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  ctx.fillText(plan.city || '旅行', PAD, y);
  const cityW = ctx.measureText(plan.city || '旅行').width;

  ctx.font = '600 15px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  ctx.fillStyle = hexA(acc, 0.95);
  ctx.fillText(`${plan.days || days.length} 天 · ${result.brief?.people || 2} 人 · ${result.brief?.budget_level || '中等'}`,
    PAD + cityW + 16, y + 18);

  ctx.fillStyle = 'rgba(255,255,255,.55)';
  ctx.font = '500 14px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  ctx.fillText(plan.theme || '', PAD, y + 58);

  y += 92;
  ctx.fillStyle = 'rgba(255,255,255,.44)';
  ctx.font = '400 13.5px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  wrapText(ctx, plan.summary || '', PAD, y, W - PAD * 2, 23, 3);
  y += summaryLines * 23 + 34;

  for (const d of days) {
    ctx.fillStyle = hexA(acc, 0.14);
    ctx.fillRect(PAD - 12, y - 10, W - (PAD - 12) * 2, 40);
    ctx.fillStyle = hexA(acc, 1);
    ctx.font = '700 13px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
    ctx.fillText(`DAY ${d.day}`, PAD, y);
    ctx.fillStyle = '#ffffff';
    ctx.font = '650 14px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
    ctx.fillText(d.title || '', PAD + 58, y);
    ctx.fillStyle = 'rgba(255,255,255,.35)';
    ctx.font = '400 12px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
    const w = d.weather || {};
    ctx.fillText(`${d.date || ''}  ${w.text || ''} ${w.t_min ?? ''}~${w.t_max ?? ''}℃`, W - PAD - 150, y + 1);
    y += 48;

    for (const it of (d.items || [])) {
      ctx.fillStyle = hexA(acc, 0.9);
      ctx.font = '600 12px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
      ctx.fillText(it.time || '', PAD, y);
      ctx.fillStyle = '#ffffff';
      ctx.font = '650 15px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
      ctx.fillText(it.name || '', PAD + 54, y - 2);
      const nmW = ctx.measureText(it.name || '').width;
      ctx.fillStyle = 'rgba(255,255,255,.32)';
      ctx.font = '400 11px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
      ctx.fillText(`${it.type || ''} · ${it.hours || 2}h · ${it.cost > 0 ? '¥' + it.cost : '免费'}`,
        PAD + 54 + nmW + 12, y + 2);
      ctx.fillStyle = 'rgba(255,255,255,.42)';
      ctx.font = '400 12px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
      wrapText(ctx, it.desc || '', PAD + 54, y + 24, W - PAD * 2 - 54, 19, 2);
      y += 76;
    }

    for (const m of (d.meals || [])) {
      ctx.fillStyle = 'rgba(251,191,36,.8)';
      ctx.font = '400 11.5px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
      ctx.fillText(m.time || '', PAD, y);
      ctx.fillStyle = 'rgba(255,255,255,.5)';
      ctx.fillText(`${m.name || ''}${m.place ? ' · ' + m.place : ''}`, PAD + 54, y);
      y += 34;
    }
    y += 20;
  }

  // 预算
  y += 6;
  ctx.fillStyle = 'rgba(255,255,255,.06)';
  ctx.fillRect(PAD, y, W - PAD * 2, 84);
  ctx.fillStyle = 'rgba(255,255,255,.55)';
  ctx.font = '500 12px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  ctx.fillText('预估总花费', PAD + 18, y + 18);
  ctx.fillStyle = hexA(acc, 1);
  ctx.font = '800 30px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  ctx.fillText(`¥${Math.round(plan.budget?.total || 0)}`, PAD + 18, y + 36);
  const bd = plan.budget?.breakdown || {};
  ctx.fillStyle = 'rgba(255,255,255,.4)';
  ctx.font = '400 11px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  ctx.fillText(Object.entries(bd).map(([k, v]) => `${k} ${Math.round(v)}`).join('   '),
    PAD + 18 + 150, y + 44);

  // 页脚
  y += 108;
  ctx.fillStyle = 'rgba(255,255,255,.22)';
  ctx.font = '400 11px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
  ctx.fillText('云游 · 文旅智能助手  |  数据来源：Open-Meteo 实况 + 本地景点知识库 + 五因子热度模型',
    PAD, y);
  ctx.fillText(`生成于 ${new Date().toLocaleString('zh-CN', { hour12: false })}`, PAD, y + 18);

  cv.toBlob((blob) => {
    const url = URL.createObjectURL(blob);
    const fname = `${plan.city || '行程'}_${plan.days || days.length}天_${new Date().toISOString().slice(0, 10)}.png`;
    openModal(`<h3>长图已生成</h3>
      <p class="mh">${W} × ${Math.round(H)} px · 可直接发到群里或保存到相册。</p>
      <img src="${url}" style="width:100%;border-radius:12px;border:1px solid var(--line);display:block">
      <div class="modal-actions">
        <button class="primary" id="dlImg">保存图片</button>
        <button class="ghost" id="closeImg">关闭</button>
      </div>`);
    $('#dlImg').addEventListener('click', () => {
      const a = document.createElement('a');
      a.href = url;
      a.download = fname;
      a.click();
      toast('已保存到下载目录');
    });
    $('#closeImg').addEventListener('click', () => { closeModal(); setTimeout(() => URL.revokeObjectURL(url), 2000); });
  }, 'image/png');
}

/* ---------------- 热点页 ---------------- */
function loadTrends(cityId) {
  if (state.trendES) { state.trendES.close(); state.trendES = null; }
  $$('#cityStrip .cs-item').forEach(x => x.classList.toggle('on', x.dataset.id === cityId));
  $('#trendList').innerHTML = '<div class="skel-row"></div><div class="skel-row"></div><div class="skel-row"></div>';
  $('#liveText').textContent = '连接中…';

  const es = new EventSource(`/api/trends/${cityId}/stream?times=120`);
  state.trendES = es;
  es.addEventListener('snapshot', (e) => renderTrends(JSON.parse(e.data), true));
  es.addEventListener('update', (e) => renderTrends(JSON.parse(e.data), false));
  es.onerror = () => { $('#liveText').textContent = '连接中断，重连中…'; };
}

function renderTrends(data, first) {
  const w = data.weather || {};
  const cur = w.current || {};
  const day0 = (w.daily || [])[0] || {};

  $('#weatherCard').innerHTML = `
    <div class="wc-top">
      <div>
        <div class="wc-temp">${cur.temp != null ? Math.round(cur.temp) : '—'}<span>℃</span></div>
        <div class="wc-text">${esc(cur.text || '')} · ${esc(data.city.name)} · ${esc(data.calendar.label)}</div>
      </div>
      <div class="wc-icon">${ICON[cur.icon] || '⛅'}</div>
    </div>
    <div class="wc-meta">
      <div>湿度<b>${cur.humidity ?? '—'}%</b></div>
      <div>风速<b>${cur.wind ?? '—'} km/h</b></div>
      <div>降水<b>${day0.rain_prob ?? '—'}%</b></div>
      <div>体感<b>${day0.t_min ?? '—'}~${day0.t_max ?? '—'}℃</b></div>
    </div>
    <div class="forecast">
      ${(w.daily || []).slice(0, 7).map(d => `
        <div class="fc"><small>${esc((d.date || '').slice(5))}</small>
          <i>${ICON[d.icon] || '⛅'}</i>
          <b>${Math.round(d.t_max)}°</b><small>${Math.round(d.t_min)}°</small></div>`).join('')}
    </div>
    <div class="wc-src">${esc(w.source_label || '')}</div>`;

  const b = data.briefing || {};
  $('#briefCard').innerHTML = `
    <h5><i></i>AI 实时播报</h5>
    <div class="brief-head">${esc(b.headline || '正在生成…')}</div>
    <div class="brief-sum">${esc(b.summary || '')}</div>
    ${b.tips ? `<div class="brief-tip">${esc(b.tips)}</div>` : ''}`;

  $('#trendList').innerHTML = data.items.map(it => `
    <div class="tr" data-name="${esc(it.name)}">
      <div class="tr-rank">${it.rank}</div>
      <div class="tr-main">
        <b>${esc(it.name)} <span class="lvl ${esc(it.level_key)}">${esc(it.level)}</span></b>
        <div class="bar"><i style="width:${Math.min(100, it.heat_now)}%;background:linear-gradient(90deg,${esc(data.city.accent)},rgba(255,255,255,.8))"></i></div>
        <small>${esc(it.type)} · ${esc(it.crowd_text)} · 建议游玩 ${it.hours}h</small>
        <div class="tr-detail">
          <b>错峰建议：</b>${esc(it.advice)}<br>
          <b>热度成因：</b>${esc(it.reason)}<br>
          <b>最佳时段：</b>${esc(it.best)} ｜ <b>门票：</b>${it.ticket > 0 ? '¥' + it.ticket : '免费'} ｜ <b>评分：</b>${it.rating}
        </div>
      </div>
      <div class="tr-hot">
        <b>${it.heat_now.toFixed(0)}</b>
        <small class="${it.delta > 0.3 ? 'up' : it.delta < -0.3 ? 'down' : 'flat'}">
          ${it.delta > 0.3 ? '▲' : it.delta < -0.3 ? '▼' : '—'} ${Math.abs(it.delta).toFixed(1)}
        </small>
      </div>
      <div class="tr-spark">${sparkline(it.trend, data.city.accent)}</div>
    </div>`).join('');

  $$('#trendList .tr').forEach(r => r.addEventListener('click', () => r.classList.toggle('open')));
  $('#modelNote').textContent = '＊ ' + data.model_note;
  $('#liveText').textContent = `实时更新中 · ${new Date().toLocaleTimeString('zh-CN', { hour12: false })}`;

  if (first) {
    $$('#trendList .tr-hot b').forEach((el, i) => {
      const v = data.items[i]?.heat_now || 0;
      el.textContent = '0';
      setTimeout(() => countUp(el, v, 700), i * 40);
    });
  }
}

function sparkline(points, color = '#5eead4') {
  if (!points || points.length < 2) return '';
  const w = 96, h = 34, max = 100, min = 0;
  const step = w / (points.length - 1);
  const path = points.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)},${(h - ((v - min) / (max - min)) * h).toFixed(1)}`).join(' ');
  const area = `${path} L${w},${h} L0,${h} Z`;
  const id = 'sp' + Math.random().toString(36).slice(2, 7);
  return `<svg width="100%" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="${color}" stop-opacity=".35"/>
      <stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <path d="${area}" fill="url(#${id})"/>
    <path d="${path}" fill="none" stroke="${color}" stroke-width="1.6" stroke-linejoin="round" opacity=".9"/>
  </svg>`;
}

/* ---------------- 城市探索 ---------------- */
async function loadCities() {
  const wall = $('#cityWall');
  try {
    if (!state.cities.length) state.cities = (await api('/api/cities')).items;
    if (!Object.keys(state.photos).length) await loadPhotos();
    wall.innerHTML = state.cities.map(c => {
      const photos = state.photos[c.id] || [];
      return `
      <article class="cw" style="--ac:${esc(c.accent)}" data-id="${esc(c.id)}">
        <div class="cw-media">
          <div data-slider data-kind="cw-slide" style="position:absolute;inset:0"></div>
          ${photos.length ? '' : RIDGE}
          ${photos.length ? `<span class="cw-photo-credit">📷 ${esc(photos[0].author)}</span>` : ''}
          <span class="cw-badge">${esc(c.tier)}</span>
          <span class="cw-name-overlay">${esc(c.name)}</span>
          ${photos.length > 1 ? `<div class="cw-dots">${photos.map((_, i) => `<i class="${i === 0 ? 'on' : ''}"></i>`).join('')}</div>` : ''}
        </div>
        <div class="cw-body">
          <div class="cw-prov">${esc(c.province)} · 最佳 ${esc(c.best_season)}</div>
          <div class="cw-intro">${esc(c.intro)}</div>
          <div class="cw-tags">${c.tags.map(t => `<span>${esc(t)}</span>`).join('')}</div>
          <div class="cw-foot"><span>景点 <b>${c.poi_count}</b> 个</span><span>招牌 <b>${esc(c.signature.split(' · ')[0])}</b></span></div>
        </div>
      </article>`;
    }).join('');

    $$('.cw').forEach(card => {
      const media = $('[data-slider]', card);
      buildSlides(media, state.photos[card.dataset.id] || []);
      card.addEventListener('click', () => openCity(card.dataset.id));
    });
  } catch (e) {
    wall.innerHTML = `<div class="warn-box">城市数据加载失败：${esc(e.message)}</div>`;
  }
}

async function openCity(id) {
  const drawer = $('#drawer'), mask = $('#drawerMask');
  mask.classList.add('on'); drawer.classList.add('on');
  $('#drawerBody').innerHTML = '<div class="skel-row"></div>';
  try {
    const { city, items } = await api(`/api/cities/${id}/pois`);
    const trend = await api(`/api/trends/${id}`).catch(() => null);
    const heatMap = {};
    (trend?.items || []).forEach(i => { heatMap[i.name] = i; });
    const photos = state.photos[id] || [];
    // 已有实景照片的景点（用于标记「有图 / 待补」）
    let withPhoto = new Set();
    try {
      const pm = await api(`/api/cities/${id}/poi-photos`);
      withPhoto = new Set(pm.with_photo || []);
    } catch (e) { /* ignore */ }

    $('#drawerBody').innerHTML = `
      ${photos.length ? `<div style="height:170px;border-radius:14px;margin-bottom:18px;background:url('${photos[0].url}') center/cover"></div>` : ''}
      <div class="dr-city">${esc(city.name)}</div>
      <div class="dr-sub">${esc(city.province)} · ${esc(city.tier)} · 最佳旅行季 ${esc(city.best_season)}</div>
      <p class="dr-intro">${esc(city.intro)}</p>
      <div class="dr-meta">
        <div><small>招牌景点</small><b>${esc(city.signature)}</b></div>
        <div><small>当地美食</small><b>${esc(city.foods.join(' / '))}</b></div>
        <div><small>景点数量</small><b>${items.length} 个</b></div>
        <div><small>当前最高热度</small><b>${trend ? Math.round(trend.items[0].heat_now) + ' · ' + trend.items[0].level : '—'}</b></div>
      </div>
      <h5 style="font-size:13px;margin-bottom:6px;color:var(--teal)">景点清单（按热度排序）</h5>
      ${items.sort((a, b) => (heatMap[b.name]?.heat_now || b.heat) - (heatMap[a.name]?.heat_now || a.heat)).map(p => {
        const h = heatMap[p.name];
        const hasPhoto = withPhoto.has(p.name);
        return `<div class="poi-row ${hasPhoto ? 'has-photo' : ''}" data-poi="${esc(p.name)}"
             title="${hasPhoto ? '点击查看实景照片' : '该景点实景照片待补充'}">
          <div><div class="pn">${esc(p.name)} <span class="poi-view">${hasPhoto ? '▣ 看实景' : '▢ 图片待补'}</span></div>
            <div class="pd">${esc(p.desc)}<br>
              <span style="color:var(--dim)">${esc(p.type)} · 建议 ${p.hours}h · 最佳 ${esc(p.best)}${h ? ' · 实时热度 ' + Math.round(h.heat_now) : ''}</span></div></div>
          <div class="pr"><b>${p.rating}</b><small>${p.ticket > 0 ? '¥' + p.ticket : '免费'}</small></div>
        </div>`;
      }).join('')}
      <div class="dr-actions">
        <button class="primary" onclick="window.__planCity('${esc(city.name)}')">为这座城市规划行程</button>
        <button class="ghost" onclick="document.getElementById('drawerClose').click()">关闭</button>
      </div>`;
  } catch (e) {
    $('#drawerBody').innerHTML = `<div class="warn-box">加载失败：${esc(e.message)}</div>`;
  }

  // 景点行 → 预览实景照片
  $$('.poi-row', $('#drawerBody')).forEach(row => {
    row.addEventListener('click', () => openPoiGallery(id, row.dataset.poi));
  });
}

/* ---------------- 景点图片灯箱 ---------------- */
let galleryState = { items: [], idx: 0 };

async function openPoiGallery(cityId, poiName) {
  const layer = $('#lightbox');
  if (!layer) return;
  galleryState = { items: [], idx: 0 };
  layer.classList.add('on');
  layer.innerHTML = `
    <div class="lb-card">
      <button class="lb-close" id="lbClose" aria-label="关闭">✕</button>
      <div class="lb-stage" id="lbStage">
        <div class="lb-loading"><span class="spinner"></span><p>正在获取实景照片…</p></div>
      </div>
      <div class="lb-bar">
        <div class="lb-info">
          <b id="lbTitle">${esc(poiName)}</b>
          <span id="lbSub"></span>
        </div>
        <div class="lb-nav">
          <button id="lbPrev" aria-label="上一张">‹</button>
          <span id="lbIdx"></span>
          <button id="lbNext" aria-label="下一张">›</button>
        </div>
      </div>
    </div>`;

  $('#lbClose')?.addEventListener('click', closeGallery);
  $('#lbPrev')?.addEventListener('click', (e) => { e.stopPropagation(); stepGallery(-1); });
  $('#lbNext')?.addEventListener('click', (e) => { e.stopPropagation(); stepGallery(1); });
  layer.onclick = (e) => { if (e.target === layer) closeGallery(); };

  try {
    const r = await api(`/api/pois/${cityId}/photos?name=${encodeURIComponent(poiName)}`);
    if (!r.items || !r.items.length) {
      const why = r.rate_limited
        ? `图片接口限流中，约 ${r.retry_in_min || 55} 分钟后可再试`
        : (r.hint || '该景点在 Unsplash 上暂无实拍作品');
      $('#lbStage').innerHTML = `<div class="lb-empty">
        <div class="lb-empty-ico">▢</div>
        <p>「${esc(poiName)}」暂无实景照片</p>
        <small>${esc(why)}</small>
      </div>`;
      $('#lbSub').textContent = '';
      return;
    }
    galleryState.items = r.items;
    paintGallery();
  } catch (e) {
    $('#lbStage').innerHTML = `<div class="lb-empty"><p>照片加载失败：${esc(e.message)}</p></div>`;
  }
}

function paintGallery() {
  const { items, idx } = galleryState;
  if (!items.length) return;
  const it = items[idx];
  $('#lbStage').innerHTML = `
    <img src="${esc(it.url)}" alt="${esc(it.desc || '')}" loading="eager">
    ${items.length > 1 ? `<div class="lb-dots">${items.map((_, i) =>
      `<i class="${i === idx ? 'on' : ''}" data-i="${i}"></i>`).join('')}</div>` : ''}`;
  $('#lbTitle').textContent = it.desc || '实景照片';
  $('#lbSub').innerHTML = `📷 ${esc(it.author)} · ${esc(it.query || '')}`
    + (it.link ? ` · <a href="${esc(it.link)}" target="_blank" rel="noopener">原图</a>` : '');
  $('#lbIdx').textContent = `${idx + 1} / ${items.length}`;
  $$('#lbStage .lb-dots i').forEach(d => d.addEventListener('click', () => {
    galleryState.idx = Number(d.dataset.i); paintGallery();
  }));
}

function stepGallery(delta) {
  if (!galleryState.items.length) return;
  const n = galleryState.items.length;
  galleryState.idx = (galleryState.idx + delta + n) % n;
  paintGallery();
}

function closeGallery() {
  const layer = $('#lightbox');
  if (layer) { layer.classList.remove('on'); layer.innerHTML = ''; }
}

document.addEventListener('keydown', (e) => {
  const layer = $('#lightbox');
  if (!layer || !layer.classList.contains('on')) return;
  if (e.key === 'Escape') closeGallery();
  else if (e.key === 'ArrowLeft') stepGallery(-1);
  else if (e.key === 'ArrowRight') stepGallery(1);
});

window.__planCity = (name) => {
  $('#drawerClose').click();
  if (!state.token) { auth.show('login'); toast('生成行程需要先登录', 'err'); return; }
  $('#planQuery').value = `去${name}玩3天，节奏适中，把当地特色都安排上`;
  go('planner');
};

$('#drawerClose')?.addEventListener('click', () => {
  $('#drawer').classList.remove('on');
  $('#drawerMask').classList.remove('on');
});
$('#drawerMask')?.addEventListener('click', () => $('#drawerClose').click());

$('#exploreSearch')?.addEventListener('keydown', async (e) => {
  if (e.key !== 'Enter') return;
  const q = e.target.value.trim();
  if (!q) return loadCities();
  try {
    const { items } = await api('/api/search?q=' + encodeURIComponent(q));
    $('#cityWall').innerHTML = items.length ? items.map(p => `
      <article class="cw" style="--ac:#5eead4" data-city="${esc(p.city_id)}">
        <div class="cw-body">
          <div class="cw-prov">${esc(p.city)} · 评分 ${p.rating} · 基础热度 ${p.heat}</div>
          <div class="cw-name" style="font-size:19px;margin-bottom:8px">${esc(p.name)}</div>
          <div class="cw-intro">${esc(p.desc)}</div>
          <div class="cw-tags">${p.tags.map(t => `<span>${esc(t)}</span>`).join('')}</div>
          <div class="cw-foot"><span>建议 ${p.hours}h</span><span>门票 <b>${p.ticket > 0 ? '¥' + p.ticket : '免费'}</b></span></div>
        </div>
      </article>`).join('')
      : '<div class="empty-tip">没找到相关景点，换个关键词试试（如「梯田」「夜景」「溶洞」）</div>';
    $$('.cw[data-city]').forEach(c => c.addEventListener('click', () => openCity(c.dataset.city)));
  } catch (err) { toast('搜索失败', 'err'); }
});

/* ---------------- 我的行程 ---------------- */
async function loadTrips() {
  const grid = $('#tripsGrid');
  if (!state.token) {
    grid.innerHTML = `<div class="empty-tip">登录后可查看收藏的行程</div>`;
    return;
  }
  grid.innerHTML = '<div class="skel-row"></div><div class="skel-row"></div>';
  try {
    const { items } = await api('/api/plans');
    if (!items.length) {
      grid.innerHTML = `<div class="empty-tip">还没有收藏的行程，去「AI 规划」生成一个吧</div>`;
      return;
    }
    grid.innerHTML = items.map(p => `
      <article class="trip-card" data-id="${esc(p.id)}">
        <div class="tc-top">
          <div class="tc-city">${esc(p.city || '未命名')}</div>
          <span class="tc-days">${p.days} 天</span>
        </div>
        <div class="tc-title">${esc(p.title || '')}</div>
        <div class="tc-sum">${esc(p.summary || '')}</div>
        <div class="tc-foot">
          <span>${esc((p.created_at || '').replace('T', ' ').slice(0, 16))}${p.is_public ? '<span class="tc-shared">已分享</span>' : ''}</span>
          <span>
            <span class="tc-del" data-share="${esc(p.id)}">${p.is_public ? '链接' : '分享'}</span>
            <span class="tc-del" data-del="${esc(p.id)}">删除</span>
          </span>
        </div>
      </article>`).join('');

    $$('.trip-card').forEach(card => card.addEventListener('click', async (e) => {
      if (e.target.closest('[data-del]') || e.target.closest('[data-share]')) return;
      try {
        const row = await api(`/api/plans/${card.dataset.id}`);
        go('planner');
        $('#planEmpty').classList.add('hidden');
        renderPlan(row.payload);
        toast('已载入收藏的行程');
      } catch (err) { toast(err.message, 'err'); }
    }));

    $$('[data-share]').forEach(el => el.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        const r = await api(`/api/plans/${el.dataset.share}/share`, { method: 'POST' });
        const url = location.origin + r.path;
        openModal(`<h3>分享链接</h3>
          <p class="mh">任何拿到链接的人都能查看，无需登录。</p>
          <div class="share-box"><input readonly value="${esc(url)}" id="shareUrl2">
            <button class="primary" id="copyShare2">复制</button></div>
          <div class="modal-actions">
            <button class="ghost" id="unshareBtn">取消分享</button>
            <button class="ghost" id="openShare2">打开</button>
          </div>`);
        $('#copyShare2').addEventListener('click', async () => {
          const ok = await copyText(url);
          toast(ok ? '链接已复制' : '复制失败，请手动选中', ok ? '' : 'err');
        });
        $('#openShare2').addEventListener('click', () => window.open(r.path, '_blank'));
        $('#unshareBtn').addEventListener('click', async () => {
          await api(`/api/plans/${el.dataset.share}/share`, { method: 'DELETE' });
          closeModal();
          loadTrips();
          toast('已取消分享，原链接失效');
        });
        loadTrips();
      } catch (err) { toast(err.message, 'err'); }
    }));
    $$('[data-del]').forEach(el => el.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm('确定删除这份行程？')) return;
      try {
        await api(`/api/plans/${el.dataset.del}`, { method: 'DELETE' });
        loadTrips();
        toast('已删除');
      } catch (err) { toast(err.message, 'err'); }
    }));
  } catch (e) {
    grid.innerHTML = `<div class="warn-box">加载失败：${esc(e.message)}</div>`;
  }
}

/* ---------------- 我的订单 ---------------- */
let orderType = '';
const ORDER_ICON = { train: '🚄', ticket: '🎫', hotel: '🏨' };

async function loadOrders() {
  const list = $('#orderList');
  if (!state.token) {
    list.innerHTML = `<div class="empty-tip">登录后可管理订单</div>`;
    return;
  }
  list.innerHTML = '<div class="skel-row"></div><div class="skel-row"></div>';
  try {
    const { items, summary } = await api('/api/orders' + (orderType ? '?type=' + orderType : ''));
    $('#osMonth').textContent = '¥' + Math.round(summary.month_amount);
    $('#osPending').textContent = summary.pending;
    $('#osDone').textContent = summary.used;
    $('#osTotal').textContent = summary.total;

    if (!items.length) {
      list.innerHTML = `<div class="empty-tip">还没有订单。可以手动新增，也可以在行程卡上点「生成订单」自动导入。</div>`;
      return;
    }
    list.innerHTML = items.map(o => `
      <div class="order-card" data-id="${esc(o.id)}">
        <div class="oc-icon ${esc(o.type)}">${ORDER_ICON[o.type] || '📦'}</div>
        <div style="min-width:0">
          <div class="oc-title">${esc(o.title)}</div>
          <div class="oc-meta">
            <span class="oc-status st-${esc(o.status)}">${esc(o.status_label)}</span>
            ${o.travel_date ? `<span>📅 ${esc(o.travel_date)}</span>` : ''}
            ${o.city ? `<span>📍 ${esc(o.city)}</span>` : ''}
            ${o.quantity > 1 ? `<span>×${o.quantity}</span>` : ''}
            ${o.detail ? `<span>${esc(o.detail)}</span>` : ''}
          </div>
          <div class="oc-actions">
            ${o.status === 'pending' ? `<span class="oc-act buy" data-url="${esc(o.buy_url || '')}">去购买</span>` : ''}
            ${o.status === 'pending' ? '<span class="oc-act" data-act="paid">标记已付</span>' : ''}
            ${o.status === 'paid' ? '<span class="oc-act" data-act="used">标记已用</span>' : ''}
            <span class="oc-act danger" data-act="del">删除</span>
          </div>
        </div>
        <div class="oc-right">
          <div class="oc-amt">¥${Math.round(o.amount)}</div>
        </div>
      </div>`).join('');

    $$('.order-card').forEach(card => {
      const id = card.dataset.id;
      $$('.oc-act', card).forEach(btn => btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const act = btn.dataset.act;
        if (btn.dataset.url) {
          window.open(btn.dataset.url, '_blank', 'noopener');
          return;
        }
        try {
          if (act === 'del') {
            if (!confirm('确定删除这条订单？')) return;
            await api(`/api/orders/${id}`, { method: 'DELETE' });
          } else {
            await api(`/api/orders/${id}`, { method: 'PATCH', body: JSON.stringify({ status: act }) });
          }
          loadOrders();
        } catch (err) { toast(err.message, 'err'); }
      }));
    });
  } catch (e) {
    list.innerHTML = `<div class="warn-box">加载失败：${esc(e.message)}</div>`;
  }
}

$('#orderTabs')?.addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (!b) return;
  orderType = b.dataset.type;
  $$('#orderTabs button').forEach(x => x.classList.toggle('on', x === b));
  loadOrders();
});

function openOrderEditor() {
  let type = 'ticket';
  openModal(`
    <h3>新增订单</h3>
    <p class="mh">手动记录一张车票、一个景区门票或一晚住宿。</p>
    <div class="order-tabs" id="modalOrderTabs" style="margin-bottom:14px">
      <button data-t="train">🚄 车票</button>
      <button class="on" data-t="ticket">🎫 门票</button>
      <button data-t="hotel">🏨 酒店</button>
    </div>
    <label class="fld"><span>标题</span><input id="odTitle" placeholder="如：黄果树瀑布门票"></label>
    <label class="fld"><span>城市</span><input id="odCity" placeholder="如：安顺"></label>
    <label class="fld"><span>日期</span><input id="odDate" type="date"></label>
    <div style="display:flex;gap:10px">
      <label class="fld" style="flex:1"><span>金额（元）</span><input id="odAmount" type="number" min="0" step="1" placeholder="0"></label>
      <label class="fld" style="flex:1"><span>数量</span><input id="odQty" type="number" min="1" value="1"></label>
    </div>
    <label class="fld"><span>备注</span><input id="odDetail" placeholder="车次/座位、票种、房型等"></label>
    <p class="auth-err" id="odErr"></p>
    <div class="modal-actions"><button class="primary" id="odSave">保存</button></div>`);

  $('#modalOrderTabs').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    type = b.dataset.t;
    $$('#modalOrderTabs button').forEach(x => x.classList.toggle('on', x === b));
  });

  $('#odSave').addEventListener('click', async () => {
    const title = $('#odTitle').value.trim();
    if (!title) return ($('#odErr').textContent = '请填写标题');
    try {
      await api('/api/orders', {
        method: 'POST',
        body: JSON.stringify({
          type, title, city: $('#odCity').value.trim(),
          travel_date: $('#odDate').value,
          amount: Number($('#odAmount').value || 0),
          quantity: Number($('#odQty').value || 1),
          detail: $('#odDetail').value.trim(),
        }),
      });
      closeModal();
      toast('订单已添加');
      go('orders');
      loadOrders();
    } catch (e) { $('#odErr').textContent = e.message; }
  });
}

$('#addOrderBtn')?.addEventListener('click', () => {
  if (!state.token) { auth.show('login'); return toast('请先登录', 'err'); }
  openOrderEditor();
});

/* ---------------- 对话面板 ---------------- */
const TOOL_LABEL = {
  tool_train_query: '城际交通',
  tool_hotel_recommend: '住宿建议',
  tool_poi_detail: '景点查询',
  tool_weather: '气象',
  tool_attractions: '景点库',
  tool_hot_ranking: '热度榜',
  tool_budget: '预算',
  tool_city_list: '城市库',
};

/* 把车票/住宿工具的结果渲染成结构化卡片（其余工具不渲染卡片） */
function renderToolCard(name, result) {
  if (!result || typeof result !== 'object') return null;

  if (name === 'tool_train_query') {
    if (!result.ok) return null;
    const opts = (result.options || []).map(o => `
      <div class="tc-opt">
        <div class="tc-mode"><b>${esc(o.mode)}</b>${o.mode === result.recommended
          ? '<span class="tc-rec">推荐</span>' : ''}</div>
        <div class="tc-meta"><span>${esc(o.duration)}</span><span class="tc-price">${esc(o.price)}</span></div>
        <div class="tc-note">${esc(o.note || '')}</div>
      </div>`).join('');
    const L = result.links || {};
    return `<div class="toolcard">
      <div class="tc-head">
        <span class="tc-ico">🚄</span>
        <div><b>${esc(result.origin)} → ${esc(result.dest)}</b>
        <small>${esc(result.travel_date)} · 直线 ${result.distance_km} km</small></div>
      </div>
      <div class="tc-opts">${opts}</div>
      <div class="tc-links">
        <a href="${esc(L['12306_query'] || L['12306'] || '#')}" target="_blank" rel="noopener">查 12306 实时余票</a>
        <a href="${esc(L.ctrip || '#')}" target="_blank" rel="noopener">携程</a>
        <a href="${esc(L.qunar || '#')}" target="_blank" rel="noopener">去哪儿</a>
      </div>
      <p class="tc-note-all">${esc(result.data_note || '')}</p>
    </div>`;
  }

  if (name === 'tool_hotel_recommend') {
    if (!result.ok) return null;
    const areas = (result.areas || []).map((a, i) => `
      <div class="tc-area${i === 0 ? ' first' : ''}">
        <div class="tc-area-top"><b>${esc(a.area)}</b>
          ${i === 0 ? '<span class="tc-rec">首选</span>' : ''}</div>
        <div class="tc-desc">${esc(a.desc)}</div>
        <div class="tc-near">📍 ${esc(a.anchor_type || '')}${a.nearby && a.nearby.length
          ? ' · ' + esc(a.nearby.join(' / ')) : ''}</div>
      </div>`).join('');
    const L = result.links || {};
    return `<div class="toolcard">
      <div class="tc-head">
        <span class="tc-ico">🏨</span>
        <div><b>${esc(result.city)}${result.near_poi ? ' · ' + esc(result.near_poi) + ' 附近' : ' 住宿建议'}</b>
        <small>${esc(result.price_band)} · 需 ${result.rooms_needed} 间 × ${result.nights} 晚</small></div>
      </div>
      <div class="tc-areas">${areas}</div>
      <div class="tc-links">
        <a href="${esc(L.ctrip || '#')}" target="_blank" rel="noopener">携程查房价</a>
        <a href="${esc(L.tongcheng || '#')}" target="_blank" rel="noopener">同程</a>
      </div>
      <p class="tc-note-all">${esc(result.data_note || '')}</p>
    </div>`;
  }

  return null;
}
$('#chatFab')?.addEventListener('click', () => {
  $('#chatPanel').classList.toggle('on');
  $('#chatInput').focus();
});
$('#chatClose')?.addEventListener('click', () => $('#chatPanel').classList.remove('on'));

function addMsg(text, who) {
  const el = document.createElement('div');
  el.className = 'msg ' + who;
  el.textContent = text;
  $('#chatBody').appendChild(el);
  $('#chatBody').scrollTop = 1e6;
  return el;
}

$('#chatForm')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (state.chatBusy) return;
  const input = $('#chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addMsg(text, 'me');
  state.chatHistory.push({ role: 'user', content: text });

  state.chatBusy = true;
  const bot = addMsg('', 'bot');
  bot.textContent = '';
  const toolsBox = document.createElement('div');
  toolsBox.className = 'tools';
  const txt = document.createElement('div');
  txt.className = 'txt';
  bot.appendChild(toolsBox);
  bot.appendChild(txt);

  let buffer = '', toolTag = null;
  try {
    await streamSSE('/api/chat', { messages: state.chatHistory }, (ev, data) => {
      if (ev === 'token') {
        buffer += data.text;
        txt.innerHTML = renderRich(buffer);
        $('#chatBody').scrollTop = 1e6;
      } else if (ev === 'tool') {
        if (data.status === 'start') {
          toolTag = document.createElement('div');
          toolTag.className = 'tool';
          toolTag.textContent = `调用工具 · ${TOOL_LABEL[data.name] || data.name || 'tool'}`;
          toolsBox.appendChild(toolTag);
        } else if (toolTag) {
          toolTag.textContent = `${toolTag.textContent} ✓`;
          toolTag.classList.add('done');
          const card = renderToolCard(data.name, data.result);
          if (card) {
            // appendChild 只接受节点，传 HTML 字符串会变成纯文本节点，
            // 必须用 insertAdjacentHTML 才能正确渲染卡片
            bot.insertAdjacentHTML('beforeend', card);
            $('#chatBody').scrollTop = 1e6;
          } else if (data.result && data.result.ok !== undefined) {
            // 兜底：工具返回了结构化数据但没匹配到卡片模板，也要让用户看到内容
            const fb = document.createElement('div');
            fb.className = 'toolcard toolcard-raw';
            fb.textContent = JSON.stringify(data.result).slice(0, 300);
            bot.appendChild(fb);
          }
        }
      } else if (ev === 'error') {
        txt.textContent = '出错了：' + data.message;
      }
    });
    if (buffer) state.chatHistory.push({ role: 'assistant', content: buffer });
  } catch (err) {
    txt.textContent = '请求失败：' + err.message;
  } finally {
    state.chatBusy = false;
  }
});

/* ---------------- 登录页交互 ---------------- */
/* 按钮加载态：文案切换 + 箭头旋转 */
function setLoading(btn, on, label) {
  if (!btn) return;
  const lbl = btn.querySelector('.btn-label');
  if (!btn.dataset.idle && lbl) btn.dataset.idle = lbl.textContent;
  btn.classList.toggle('loading', on);
  btn.disabled = on;
  if (lbl) lbl.textContent = on ? (label || '处理中…') : btn.dataset.idle;
}

/* 密码显示 / 隐藏 */
function bindPwdEye(eyeSel, inputSel) {
  const eye = $(eyeSel), input = $(inputSel);
  if (!eye || !input) return;
  eye.addEventListener('click', () => {
    const show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    eye.classList.toggle('on', show);
    eye.textContent = show ? '◉' : '◎';
    eye.title = show ? '隐藏密码' : '显示密码';
    input.focus();
  });
}

/* 记住我：预填上次登录的邮箱前缀 */
function initRemember() {
  const saved = localStorage.getItem('wy_remember');
  const box = $('#rememberMe');
  if (!saved) return;
  if (box) box.checked = true;
  const input = $('#loginEmail');
  if (input && !input.value) input.value = saved.split('@')[0];
}

bindPwdEye('#loginEye', '#loginPwd');
bindPwdEye('#regEye', '#regPwd');

/* 页签切换用事件委托，绑在容器上，元素被替换也不失效 */
$('#authTabs')?.addEventListener('click', (e) => {
  const b = e.target.closest('button');
  if (b && b.dataset.tab) auth.switchTab(b.dataset.tab);
});
$('#loginForm')?.addEventListener('submit', (e) => { e.preventDefault(); auth.login(); });
$('#registerForm')?.addEventListener('submit', (e) => { e.preventDefault(); auth.register(); });
$('#sendCodeBtn')?.addEventListener('click', () => auth.sendCode());
$('#locateBtn')?.addEventListener('click', () => auth.locate());
$('#authSkip')?.addEventListener('click', () => {
  localStorage.setItem('wy_skip', '1');
  auth.hide();
});

/* 第三方入口（暂未开放，给出明确说明而不是静默无响应） */
$$('.ap-btn').forEach(b => b.addEventListener('click', () => {
  toast(`${b.dataset.provider} 登录入口尚未开放，请使用 163 邮箱登录`, 'err');
}));

$('#forgotBtn')?.addEventListener('click', () => {
  openModal(`
    <h3>重置密码</h3>
    <p class="mh">用注册邮箱接收验证码，验证后设置新密码。</p>
    <label class="fld"><span>邮箱</span>
      <div class="mail-input"><input id="rstEmail" type="text" placeholder="yourname"><em>@163.com</em></div>
    </label>
    <label class="fld"><span>验证码</span>
      <div class="code-input">
        <input id="rstCode" type="text" maxlength="6" placeholder="6 位数字">
        <button type="button" id="rstSend">获取验证码</button>
      </div>
    </label>
    <label class="fld"><span>新密码</span>
      <input id="rstPwd" type="password" placeholder="至少 8 位，含字母和数字">
    </label>
    <p class="auth-err" id="rstErr"></p>
    <div class="modal-actions"><button class="primary" id="rstGo">重置密码</button></div>`);

  $('#rstSend').addEventListener('click', async () => {
    const local = $('#rstEmail').value.trim();
    if (!local) return ($('#rstErr').textContent = '请先填写邮箱前缀');
    const btn = $('#rstSend');
    btn.disabled = true;
    btn.textContent = '发送中…';
    try {
      const r = await api('/api/auth/reset-code', {
        method: 'POST', body: JSON.stringify({ email: local + '@163.com' }),
      });
      if (!r.ok) throw new Error(r.message || '发送失败');
      toast(r.message || '验证码已发送');
      if (r.dev_mode && r.code) {
        $('#rstCode').value = r.code;
        $('#rstErr').textContent = `开发模式：验证码 ${r.code} 已自动填入`;
      }
      let left = 60;
      const t = setInterval(() => {
        left -= 1;
        btn.textContent = left > 0 ? `${left}s 后重发` : '获取验证码';
        if (left <= 0) { clearInterval(t); btn.disabled = false; }
      }, 1000);
    } catch (e) {
      $('#rstErr').textContent = e.message;
      btn.disabled = false;
      btn.textContent = '获取验证码';
    }
  });

  $('#rstGo').addEventListener('click', async () => {
    $('#rstErr').textContent = '';
    try {
      await api('/api/auth/reset', {
        method: 'POST',
        body: JSON.stringify({
          email: $('#rstEmail').value.trim() + '@163.com',
          code: $('#rstCode').value.trim(),
          password: $('#rstPwd').value,
        }),
      });
      closeModal();
      toast('密码已重置，请用新密码登录');
    } catch (e) { $('#rstErr').textContent = e.message; }
  });
});

/* ---------------- 启动 ---------------- */
boot();
setInterval(() => { if (state.view === 'home') loadRadar(); }, 120000);
