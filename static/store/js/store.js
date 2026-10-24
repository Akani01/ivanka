
(function(){
'use strict';
const API = document.body.dataset.apiRoot.replace(/config\/$/, '');
const JOBS_API = document.body.dataset.jobsApi || '';
const NEWSLETTER_API = document.body.dataset.newsletterApi || '';
const isLoggedIn = document.body.dataset.userLoggedIn === 'true';
const ADS = [
  {title:'Your brand here.', text:'Reach thousands of local shoppers across South Africa with a sponsored slot on Ivanka.', cta:'Advertise with us', href:document.body.dataset.contactUrl},
  {title:'Sell on Ivanka.', text:'Open your store in minutes. Get paid securely through Yoco.', cta:'Open a store', view:'seller'},
  {title:'Deliver & earn.', text:'Join our courier network and earn on every delivery.', cta:'Become a courier', view:'courier'}
];

/* shop state (declared up here so the search handlers can always see it) */
let shopCat = null, shopQuery = '';

/* ---------- helpers ---------- */
const $ = id => document.getElementById(id);
function csrf(){ const m = document.cookie.match(/csrftoken=([^;]+)/); if (m) return decodeURIComponent(m[1]); const i = document.querySelector('input[name=csrfmiddlewaretoken]'); return i ? i.value : ''; }
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function toast(msg, type){ const el = document.createElement('div'); el.className = 'iv-toast' + (type ? ' ' + type : ''); el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 2800); }
function fmtPrice(v, cur){ return (cur || 'ZAR') + ' ' + (Number(v) || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}); }
function uuid4(){ if (window.crypto && crypto.randomUUID) return crypto.randomUUID(); return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => { const r = Math.random()*16|0; return (c === 'x' ? r : (r&3|8)).toString(16); }); }
function listOf(d){ return Array.isArray(d) ? d : ((d && (d.results || d.jobs)) || []); }
function firstPrice(p){ const v = p.variants && p.variants[0]; return v ? (v.display_price || v.price) : 0; }
function imgOf(p){ return p.images && p.images[0] ? (p.images[0].image || p.images[0].url) : null; }

async function api(path, opts){
  opts = opts || {}; opts.headers = Object.assign({'Accept':'application/json'}, opts.headers || {});
  if (opts.method && opts.method !== 'GET'){ opts.headers['X-CSRFToken'] = csrf(); if (!(opts.body instanceof FormData) && !opts.headers['Content-Type']) opts.headers['Content-Type'] = 'application/json'; }
  opts.credentials = 'same-origin';
  const res = await fetch(API + path, opts); let data = null; try { data = await res.json(); } catch(e){}
  if (!res.ok){
    let msg = 'Error ' + res.status;
    if (data){ if (data.detail || data.error) msg = data.detail || data.error; else if (typeof data === 'object'){ const parts = []; Object.keys(data).forEach(k => { const v = data[k]; parts.push(Array.isArray(v) ? v.join(' ') : v); }); if (parts.length) msg = parts.join(' '); } }
    if (res.status === 401 || res.status === 403) msg = (data && data.detail) || 'Please sign in first.';
    throw new Error(msg);
  }
  return data;
}
const post = (path, body) => api(path, {method:'POST', body: JSON.stringify(body || {})});
function needLogin(box, icon, title, wrap){ box.innerHTML = '<div class="iv-empty" ' + (wrap ? 'style="grid-column:1/-1;"' : '') + '><i class="fas fa-' + icon + '"></i><h4>' + title + '</h4><button class="iv-btn" data-auth="login">Sign in</button></div>'; }
function loading(box, wrap){ box.innerHTML = '<div class="iv-empty" ' + (wrap ? 'style="grid-column:1/-1;"' : '') + '><i class="fas fa-spinner fa-spin"></i><h4>Loading…</h4></div>'; }
function fail(box, err, wrap){ box.innerHTML = '<div class="iv-empty" ' + (wrap ? 'style="grid-column:1/-1;"' : '') + '><i class="fas fa-triangle-exclamation"></i><h4>' + esc(err.message || err) + '</h4></div>'; }

/* ---------- AUTH MODAL ---------- */
let authReturnFocus = null;
function openAuth(mode){
  if (!$('authVeil').classList.contains('show')) authReturnFocus = document.activeElement;
  mode = mode === 'signup' ? 'signup' : 'login';
  $('authTitle').textContent = mode === 'signup' ? 'Join Ivanka' : 'Welcome back';
  document.querySelectorAll('.iv-seg button').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  $('loginForm').hidden = mode !== 'login'; $('signupForm').hidden = mode !== 'signup';
  $('googleBtn').href = '/accounts/google/login/?process=' + mode + '&next=' + encodeURIComponent(location.pathname + location.hash);
  $('authVeil').classList.add('show'); document.body.style.overflow = 'hidden';
  setTimeout(() => $(mode === 'login' ? 'lUser' : 'sUser').focus(), 60);
}
function closeAuth(){ $('authVeil').classList.remove('show'); document.body.style.overflow = ''; if(authReturnFocus && authReturnFocus.focus) authReturnFocus.focus(); }
$('authClose').onclick = closeAuth;
$('authVeil').addEventListener('click', e => { if (e.target === $('authVeil')) closeAuth(); });
document.querySelectorAll('.iv-seg button').forEach(b => b.onclick = () => openAuth(b.dataset.mode));
async function submitAuth(url, body, errBox, btn, done){
  errBox.textContent = ''; btn.disabled = true;
  try{
    const r = await fetch(url, {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),'Accept':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json().catch(() => ({}));
    if (!r.ok || d.success === false) throw new Error(d.error || d.detail || 'That did not work. Check your details and try again.');
    done(d);
  }catch(err){ errBox.textContent = err.message; } finally { btn.disabled = false; }
}
$('loginForm').addEventListener('submit', function(e){ e.preventDefault();
  submitAuth('/api/auth/login/', Object.fromEntries(new FormData(this)), $('loginErr'), this.querySelector('[type=submit]'), () => { toast('Signed in'); setTimeout(() => location.reload(), 500); }); });
$('signupForm').addEventListener('submit', function(e){ e.preventDefault();
  const d = Object.fromEntries(new FormData(this));
  if (d.password !== d.password_confirm){ $('signupErr').textContent = 'Passwords do not match.'; return; }
  submitAuth('/api/auth/signup/', d, $('signupErr'), this.querySelector('[type=submit]'), () => { toast('Account created. Sign in to continue.'); openAuth('login'); }); });

/* ---------- PROFILE POP-UP ---------- */
const menu = $('profileMenu'), pbtn = $('profileBtn');
function toggleProfile(force){ if (!menu) return; const open = force !== undefined ? force : !menu.classList.contains('show'); menu.classList.toggle('show', open); if (pbtn) pbtn.setAttribute('aria-expanded', String(open)); }
if (pbtn) pbtn.addEventListener('click', e => { e.stopPropagation(); toggleProfile(); });
$('dockMe').addEventListener('click', e => { e.stopPropagation(); if (!isLoggedIn) openAuth('login'); else toggleProfile(); });
document.addEventListener('click', e => { if (menu && menu.classList.contains('show') && (!e.target.closest('#profileWrap') || e.target.closest('#profileMenu a, #profileMenu button'))) toggleProfile(false); });
document.addEventListener('keydown', e => { if(e.key === 'Tab' && $('authVeil').classList.contains('show')){ const fields=[...$('authVeil').querySelectorAll('button,a[href],input')].filter(x=>x.offsetParent!==null&&!x.disabled); const first=fields[0],last=fields[fields.length-1]; if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();} else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();} } if (e.key === 'Escape'){ toggleProfile(false); closeAuth(); } });

/* ---------- ROUTER ---------- */
const loaders = {}; let prevView = 'home', currentRoute = 'home';
function parseRoute(){ const parts = (location.hash || '#home').slice(1).split('/'); return {name: parts[0] || 'home', arg: parts[1] || null}; }
function go(route){ location.hash = '#' + route; }
function render(){
  let {name, arg} = parseRoute(); const authMode = name === 'login' || name === 'signup' ? name : null; if (!loaders[name]) name = 'home';
  if (name !== 'product') prevView = name; currentRoute = name;
  document.querySelectorAll('.iv-view').forEach(v => v.classList.toggle('active', v.dataset.view === name));
  document.querySelectorAll('.iv-dock-btn[data-view], .iv-nav .iv-icon[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  window.scrollTo(0, 0); loaders[name](arg); if (authMode) openAuth(authMode);
}
document.addEventListener('click', function(e){
  const a = e.target.closest('[data-auth]'); if (a){ e.preventDefault(); openAuth(a.dataset.auth); return; }
  const t = e.target.closest('[data-view]'); if (!t || t.tagName === 'SECTION') return;
  if (t.tagName === 'A' && t.getAttribute('href')) return;
  e.preventDefault();
  /* tapping Shop from the nav clears any old search so you always see the full shop */
  if (t.dataset.view === 'shop' && (t.closest('.iv-dock') || t.closest('.iv-nav'))){ shopQuery = ''; shopCat = null; $('searchInput').value = ''; if (currentRoute === 'shop'){ loaders.shop(); return; } }
  go(t.dataset.view);
});
window.addEventListener('hashchange', render);
$('backBtn').addEventListener('click', () => go(prevView || 'shop'));

/* ---------- SEARCH ---------- */
function runSearch(value){
  shopQuery = (value || '').trim(); shopCat = null;
  if (currentRoute === 'shop') loaders.shop();
  else if (shopQuery) go('shop');
}
$('searchForm').addEventListener('submit', function(e){ e.preventDefault(); clearTimeout(searchTimer); runSearch($('searchInput').value); $('searchInput').blur(); });
let searchTimer = null;
$('searchInput').addEventListener('input', function(){
  const v = this.value; clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { if (v.trim() === shopQuery) return; runSearch(v); }, 350);
});

/* dock auto-hide */
(function(){ const dock = $('ivDock'); let last = window.scrollY, tick = false;
  window.addEventListener('scroll', () => { if (tick) return; tick = true; requestAnimationFrame(() => { const y = Math.max(0, window.scrollY), d = y - last;
    if (y < 48 || d < -5) dock.classList.remove('hide'); else if (d > 7 && y > 120) dock.classList.add('hide'); last = y; tick = false; }); }, {passive:true}); })();

/* Newsletter handler shared with the support pages. */
/* ---------- ADS ---------- */
let adIdx = 0, adTimer = null;
function buildAds(){
  $('adSlides').innerHTML = ADS.map((a, i) => '<div class="iv-ad-slide' + (i === 0 ? ' active' : '') + '"><h2>' + esc(a.title) + '</h2><p>' + esc(a.text) + '</p>' +
    (a.href ? '<a class="iv-ad-cta" href="' + esc(a.href) + '">' + esc(a.cta) + ' <i class="fas fa-arrow-right"></i></a>' : '<button class="iv-ad-cta" data-view="' + esc(a.view) + '">' + esc(a.cta) + ' <i class="fas fa-arrow-right"></i></button>') + '</div>').join('');
  $('adDots').innerHTML = ADS.map((_, i) => '<button aria-label="Ad ' + (i+1) + '" class="' + (i === 0 ? 'active' : '') + '" data-ad="' + i + '"></button>').join('');
  $('adDots').addEventListener('click', e => { const b = e.target.closest('[data-ad]'); if (b){ showAd(Number(b.dataset.ad)); startAds(); } }); startAds();
}
function showAd(i){ adIdx = i; document.querySelectorAll('.iv-ad-slide').forEach((s, k) => s.classList.toggle('active', k === i)); document.querySelectorAll('#adDots button').forEach((s, k) => s.classList.toggle('active', k === i)); }
function startAds(){ clearInterval(adTimer); if (ADS.length > 1) adTimer = setInterval(() => showAd((adIdx + 1) % ADS.length), 6000); }

/* ---------- CATEGORIES ---------- */
let cats = null, enabledCurrencies = [];
async function getCats(){ if (cats) return cats; try { const cfg = await api('config/'); cats = cfg.categories || []; enabledCurrencies = (cfg.currencies || []).map(c => c.code); } catch(e){ cats = []; } return cats; }
async function renderChips(boxId, current, onPick){
  const box = $(boxId), list = await getCats();
  box.innerHTML = '<button class="iv-cat' + (!current ? ' active' : '') + '" data-cat="">All</button>' + list.map(c => '<button class="iv-cat' + (String(current) === String(c.id) ? ' active' : '') + '" data-cat="' + c.id + '">' + esc(c.name) + '</button>').join('');
  box.onclick = e => { const b = e.target.closest('.iv-cat'); if (!b) return; box.querySelectorAll('.iv-cat').forEach(x => x.classList.remove('active')); b.classList.add('active'); onPick(b.dataset.cat || null); };
}

/* ---------- PRODUCT CARDS ---------- */
let wished = new Set();
function cardHTML(p){
  const img = imgOf(p), v = p.variants && (p.variants.find(x => x.stock > 0) || p.variants[0]), heart = wished.has(p.id);
  return '<div class="iv-product" role="link" tabindex="0" aria-label="View ' + esc(p.name) + '" data-id="' + p.id + '"><div class="iv-product-img">' + (img ? '<img src="' + esc(img) + '" alt="' + esc(p.name) + '" loading="lazy">' : '<i class="fas fa-image"></i>') + (p.featured ? '<span class="iv-product-badge">Featured</span>' : '') + '</div>' +
    '<div class="iv-product-body"><div class="iv-product-title">' + esc(p.name) + '</div><div class="iv-product-store">' + esc(p.store_name || '') + '</div><div class="iv-product-price">' + fmtPrice(firstPrice(p), p.currency) + '</div>' +
    '<div class="iv-product-actions"><button class="iv-btn-view" data-action="wish" data-product="' + p.id + '" aria-label="Wishlist"><i class="' + (heart ? 'fas' : 'far') + ' fa-heart"></i></button><button class="iv-btn-add" data-action="add" data-variant="' + (v ? v.id : '') + '">Add</button></div></div></div>';
}
async function addToCart(variantId, qty, btn, label){
  if (!isLoggedIn){ toast('Please sign in first', 'error'); openAuth('login'); return; }
  if (!variantId){ toast('No stock available', 'error'); return; }
  if (btn){ btn.disabled = true; btn.textContent = '…'; }
  try{
    const cart = await api('cart/'); const ex = (cart.items || []).find(x => Number(x.variant) === Number(variantId));
    await post('cart/', {variant: Number(variantId), quantity: Math.min(99, (ex ? ex.quantity : 0) + (qty || 1))});
    toast('Added to cart'); refreshBadges();
    if (btn){ btn.textContent = '✓'; setTimeout(() => { btn.innerHTML = label || 'Add'; btn.disabled = false; }, 1100); }
  }catch(err){ toast(err.message, 'error'); if (btn){ btn.innerHTML = label || 'Add'; btn.disabled = false; } }
}
async function toggleWish(productId, btn, removeCard){
  if (!isLoggedIn){ toast('Please sign in first', 'error'); openAuth('login'); return; }
  try{ const r = await post('wishlist/', {product: Number(productId)}); if (r.saved) wished.add(Number(productId)); else wished.delete(Number(productId));
    if (btn) btn.innerHTML = '<i class="' + (r.saved ? 'fas' : 'far') + ' fa-heart"></i>'; toast(r.saved ? 'Added to wishlist' : 'Removed from wishlist');
    if (removeCard && !r.saved){ const c = btn.closest('.iv-product'); if (c) c.remove(); if (!$('wishlistContent').children.length) loaders.wishlist(); }
  }catch(err){ toast(err.message, 'error'); }
}
document.addEventListener('click', function(e){
  const card = e.target.closest('.iv-product'); if (!card) return;
  const add = e.target.closest('[data-action="add"]'), wish = e.target.closest('[data-action="wish"]');
  if (add){ e.stopPropagation(); addToCart(add.dataset.variant, 1, add, 'Add'); return; }
  if (wish){ e.stopPropagation(); toggleWish(wish.dataset.product, wish, currentRoute === 'wishlist'); return; }
  go('product/' + card.dataset.id);
});
async function loadWished(){ if (!isLoggedIn) return; try { wished = new Set(listOf(await api('wishlist/')).map(p => p.id)); } catch(e){} }

/* ---------- HOME / SHOP ---------- */
let homeInit = false;
loaders.home = async function(){ if (!homeInit){ homeInit = true; buildAds(); renderChips('homeCats', null, c => homeProducts(c)); } await loadWished(); homeProducts(null); };
async function homeProducts(cat){
  const box = $('homeProducts'); loading(box, true);
  try{ const list = listOf(await api('products/' + (cat ? '?category=' + encodeURIComponent(cat) : '')));
    box.innerHTML = list.length ? list.slice(0, 8).map(cardHTML).join('') : '<div class="iv-empty" style="grid-column:1/-1;"><i class="fas fa-bag-shopping"></i><h4>No products yet</h4><p>Sellers are still adding items.</p></div>';
  }catch(err){ fail(box, err, true); }
}
loaders.shop = async function(){
  renderChips('shopCats', shopCat, c => { shopCat = c; loaders.shopList(); });
  $('shopTitle').textContent = shopQuery ? 'Results for “' + shopQuery + '”' : 'All products';
  if ($('searchInput').value.trim() !== shopQuery) $('searchInput').value = shopQuery;
  await loadWished(); loaders.shopList();
};
let shopReq = 0;
loaders.shopList = async function(){
  const box = $('shopProducts'), req = ++shopReq; loading(box, true);
  try{
    const params = new URLSearchParams(); if (shopCat) params.set('category', shopCat); if (shopQuery) params.set('search', shopQuery);
    let list = listOf(await api('products/?' + params.toString()));
    /* fallback: if the server ignored/missed the search, filter the catalogue in the browser */
    if (shopQuery && !list.length){
      const p2 = new URLSearchParams(); if (shopCat) p2.set('category', shopCat);
      const all = listOf(await api('products/?' + p2.toString())), q = shopQuery.toLowerCase();
      list = all.filter(p => [p.name, p.brand, p.store_name, p.description, p.category_name].some(s => String(s || '').toLowerCase().indexOf(q) > -1));
    }
    if (req !== shopReq) return; /* a newer search has started */
    box.innerHTML = list.length ? list.map(cardHTML).join('') : '<div class="iv-empty" style="grid-column:1/-1;"><i class="fas fa-magnifying-glass"></i><h4>No products found</h4><p>Try another search or category.</p></div>';
  }catch(err){ if (req === shopReq) fail(box, err, true); }
};

/* ---------- PRODUCT ---------- */
loaders.product = async function(id){
  const box = $('productContent'); if (!id){ go('shop'); return; } loading(box);
  try{
    await loadWished(); const p = await api('products/' + encodeURIComponent(id) + '/'); const variants = p.variants || [];
    let sel = variants.find(v => v.stock > 0) || variants[0] || null, qty = 1; const imgs = (p.images || []).map(i => i.image || i.url).filter(Boolean);
    (function draw(){
      const stock = sel ? sel.stock : 0;
      box.innerHTML = '<div class="iv-detail"><div><div class="iv-gallery-main" id="gMain">' + (imgs[0] ? '<img src="' + esc(imgs[0]) + '" alt="' + esc(p.name) + '">' : '<i class="fas fa-image" style="font-size:56px;opacity:.15"></i>') + '</div>' +
        (imgs.length > 1 ? '<div class="iv-thumbs">' + imgs.map((s, i) => '<img src="' + esc(s) + '" data-i="' + i + '" class="' + (i === 0 ? 'active' : '') + '" alt="">').join('') + '</div>' : '') + '</div><div>' +
        '<div class="iv-product-store">' + esc(p.store_name || '') + (p.brand ? ' · ' + esc(p.brand) : '') + '</div><h2>' + esc(p.name) + '</h2>' +
        '<div class="price">' + fmtPrice(sel ? (sel.display_price || sel.price) : 0, p.currency) + '</div>' +
        (variants.length > 1 ? '<div class="iv-variants">' + variants.map(v => '<button class="iv-variant' + (sel && v.id === sel.id ? ' active' : '') + '" data-vid="' + v.id + '"' + (v.stock < 1 ? ' disabled' : '') + '>' + esc(v.label || ('Option ' + v.id)) + '</button>').join('') + '</div>' : '') +
        '<div class="iv-stock">' + (stock > 0 ? (stock <= 5 ? 'Only ' + stock + ' left' : 'In stock') : 'Out of stock') + '</div>' +
        '<div class="iv-actions" style="margin-bottom:12px;align-items:center"><div class="iv-qty"><button id="qMinus">−</button><span id="qVal">' + qty + '</span><button id="qPlus">+</button></div>' +
        '<button class="iv-btn" id="dAdd"' + (stock < 1 ? ' disabled' : '') + ' style="flex:1"><i class="fas fa-cart-plus"></i> Add to cart</button><button class="iv-btn ghost" id="dWish" aria-label="Wishlist"><i class="' + (wished.has(p.id) ? 'fas' : 'far') + ' fa-heart"></i></button></div>' +
        (p.description ? '<div class="desc">' + esc(p.description) + '</div>' : '') + '</div></div>';
      box.querySelectorAll('.iv-thumbs img').forEach(t => t.onclick = () => { $('gMain').innerHTML = '<img src="' + esc(imgs[Number(t.dataset.i)]) + '" alt="">'; box.querySelectorAll('.iv-thumbs img').forEach(x => x.classList.toggle('active', x === t)); });
      box.querySelectorAll('.iv-variant').forEach(b => b.onclick = () => { sel = variants.find(v => v.id === Number(b.dataset.vid)); qty = 1; draw(); });
      $('qMinus').onclick = () => { qty = Math.max(1, qty - 1); $('qVal').textContent = qty; };
      $('qPlus').onclick = () => { qty = Math.min(Math.max(1, stock), qty + 1, 99); $('qVal').textContent = qty; };
      $('dAdd').onclick = function(){ addToCart(sel && sel.id, qty, this, '<i class="fas fa-cart-plus"></i> Add to cart'); };
      $('dWish').onclick = function(){ toggleWish(p.id, this, false); };
    })();
  }catch(err){ fail(box, err); }
};

/* ---------- CART ---------- */
loaders.cart = async function(){
  const box = $('cartContent'); if (!isLoggedIn) return needLogin(box, 'cart-shopping', 'Sign in to see your cart'); loading(box);
  try{
    const data = await api('cart/'), items = data.items || [];
    if (!items.length){ box.innerHTML = '<div class="iv-empty"><i class="fas fa-cart-shopping"></i><h4>Your cart is empty</h4><p>Browse the shop and add something.</p><button class="iv-btn" data-view="shop">Browse shop</button></div>'; return; }
    box.innerHTML = '<div class="iv-cart-list">' + items.map(it => '<div class="iv-cart-item" data-variant="' + it.variant + '" data-qty="' + it.quantity + '"><div class="iv-cart-item-img">' + (it.image ? '<img src="' + esc(it.image) + '" alt="">' : '<i class="fas fa-image" style="opacity:.2"></i>') + '</div>' +
      '<div class="iv-cart-item-info"><h4>' + esc(it.name) + '</h4><p>' + esc(it.label || '') + (it.label ? ' · ' : '') + esc(it.store_name || '') + '</p><div class="iv-cart-item-price">' + fmtPrice(it.price, data.currency) + '</div></div>' +
      '<div class="iv-cart-item-controls"><div class="iv-qty"><button data-d="-1">−</button><span>' + it.quantity + '</span><button data-d="1">+</button></div><button class="iv-link-btn" data-d="remove">Remove</button></div></div>').join('') + '</div>' +
      '<div class="iv-cart-summary"><div class="iv-cart-row"><span>Subtotal</span><span>' + fmtPrice(data.subtotal, data.currency) + '</span></div><div class="iv-cart-row total"><span>Total</span><strong>' + fmtPrice(data.subtotal, data.currency) + '</strong></div></div><button class="iv-btn block" id="goCheckout">Continue to checkout <i class="fas fa-arrow-right"></i></button>';
    box.querySelectorAll('.iv-cart-item').forEach(row => { const vid = Number(row.dataset.variant), cur = Number(row.dataset.qty);
      row.querySelectorAll('[data-d]').forEach(b => b.onclick = async () => { const d = b.dataset.d; const next = d === 'remove' ? 0 : Math.max(0, Math.min(99, cur + Number(d)));
        try{ await post('cart/', {variant: vid, quantity: next}); loaders.cart(); refreshBadges(); }catch(err){ toast(err.message, 'error'); } }); });
    $('goCheckout').onclick = () => go('checkout');
  }catch(err){ fail(box, err); }
};

/* ---------- CHECKOUT ---------- */
loaders.checkout = async function(){
  const box = $('checkoutContent'); if (!isLoggedIn) return needLogin(box, 'user', 'Sign in to checkout'); loading(box);
  try{
    await getCats(); const cart = await api('cart/'), items = cart.items || [];
    if (!items.length){ box.innerHTML = '<div class="iv-empty"><i class="fas fa-cart-shopping"></i><h4>Your cart is empty</h4><button class="iv-btn" data-view="shop">Browse shop</button></div>'; return; }
    let addrs = []; try { addrs = listOf(await api('addresses/')); } catch(e){}
    box.innerHTML = '<div class="iv-cart-summary">' + items.map(it => '<div class="iv-cart-row"><span>' + esc(it.name) + ' × ' + it.quantity + '</span><span>' + fmtPrice(Number(it.price) * it.quantity, cart.currency) + '</span></div>').join('') + '<div class="iv-cart-row total"><span>Total</span><strong>' + fmtPrice(cart.subtotal, cart.currency) + '</strong></div></div>' +
      '<div class="iv-form-grid"><div class="iv-form-field full"><label>Delivery address</label><select id="coAddress"><option value="">— select an address —</option>' + addrs.map(a => '<option value="' + a.id + '">' + esc([a.recipient || a.name, a.line1 || a.address, a.city].filter(Boolean).join(' · ') || ('Address ' + a.id)) + '</option>').join('') + '</select></div>' +
      '<div class="iv-form-field"><label>Coupon code</label><input id="coCoupon" placeholder="Optional"></div><div class="iv-form-field"><label>Currency</label><select id="coCurrency">' + (enabledCurrencies.length ? enabledCurrencies : ['ZAR']).map(c => '<option>' + esc(c) + '</option>').join('') + '</select></div>' +
      '<div class="iv-form-field full"><label>Payment method</label><select id="coPay"><option value="card">Card (secure checkout with Yoco)</option><option value="cash">Cash on delivery</option></select></div></div>' +
      '<details class="iv-details"><summary>+ Add a new address</summary><div class="iv-form-grid"><div class="iv-form-field"><label>Recipient</label><input id="adRecipient"></div><div class="iv-form-field"><label>Phone</label><input id="adPhone" type="tel"></div><div class="iv-form-field full"><label>Street address</label><input id="adLine1"></div><div class="iv-form-field"><label for="adCity">City</label><input id="adCity" autocomplete="address-level2"></div><div class="iv-form-field"><label for="adProvince">Province / region</label><input id="adProvince" autocomplete="address-level1"></div><div class="iv-form-field"><label for="adPostal">Postal code</label><input id="adPostal" autocomplete="postal-code"></div></div><button class="iv-btn ghost block" id="saveAddr">Save address</button></details>' +
      '<button class="iv-btn block" id="placeOrder">Place order</button>';
    $('saveAddr').onclick = async function(){
      const body = {recipient:$('adRecipient').value.trim(), phone:$('adPhone').value.trim(), line1:$('adLine1').value.trim(), city:$('adCity').value.trim(), province:$('adProvince').value.trim(), postal_code:$('adPostal').value.trim()};
      if (!body.recipient || !body.phone || !body.line1 || !body.city || !body.province || !body.postal_code){ toast('Complete all delivery address fields', 'error'); return; }
      this.disabled = true; try{ await post('addresses/', body); toast('Address saved'); loaders.checkout(); }catch(err){ toast(err.message, 'error'); this.disabled = false; } };
    $('placeOrder').onclick = async function(){
      const addr = $('coAddress').value; if (!addr){ toast('Choose a delivery address', 'error'); return; }
      const btn = this; btn.disabled = true; btn.innerHTML = '<span class="iv-spin"></span> Placing…';
      try{
        const res = await post('checkout/', {address_id: Number(addr), idempotency_key: uuid4(), currency: $('coCurrency').value, coupon: $('coCoupon').value.trim()});
        toast('Order placed!'); refreshBadges();
        const method = $('coPay').value, gateway = method === 'cash' ? 'cash' : 'yoco', created = (res && res.orders) || [];
        for (let i = 0; i < created.length; i++){
          try{ const pay = await post('orders/' + created[i].id + '/pay/', {payment_method: method, gateway_code: gateway}); if (method === 'card' && pay && pay.redirect_url){ location.href = pay.redirect_url; return; } }catch(e){ toast(e.message, 'error'); }
        }
        go('orders');
      }catch(err){ toast(err.message, 'error'); btn.disabled = false; btn.innerHTML = 'Place order'; }
    };
  }catch(err){ fail(box, err); }
};

/* ---------- ORDERS ---------- */
loaders.orders = async function(){
  const box = $('ordersContent'); if (!isLoggedIn) return needLogin(box, 'receipt', 'Sign in to see orders'); loading(box);
  try{
    const orders = listOf(await api('orders/'));
    if (!orders.length){ box.innerHTML = '<div class="iv-empty"><i class="fas fa-receipt"></i><h4>No orders yet</h4><p>Your orders will appear here after checkout.</p><button class="iv-btn" data-view="shop">Start shopping</button></div>'; return; }
    box.innerHTML = orders.map(o => {
      const lines = (o.items || []).map(i => esc(i.name || i.product_name || 'Item') + ' × ' + esc(i.quantity)).join('<br>');
      const st = String(o.status || '').toLowerCase(), ps = String(o.payment_status || '').toLowerCase();
      const paid = ['paid','succeeded','settled','refunded'].indexOf(ps) > -1, closed = st === 'cancelled' || st === 'delivered';
      const events = (o.events || []).map(ev => esc(ev.status) + (ev.note ? ' — ' + esc(ev.note) : '')).join('<br>');
      return '<div class="iv-order" data-id="' + esc(o.id) + '"><div class="iv-order-head"><h4>Order ' + esc(String(o.id).slice(0, 8)) + '</h4><span class="iv-pill ' + esc(st) + '">' + esc(o.status) + '</span></div>' +
        '<div class="iv-order-meta">' + esc(o.store_name || '') + ' · ' + (o.created_at ? new Date(o.created_at).toLocaleDateString() : '') + (o.payment_status ? ' · Payment: ' + esc(o.payment_status) : '') + '</div>' +
        '<div class="iv-order-total">' + esc(o.currency_symbol || o.currency || '') + ' ' + Number(o.display_total || o.total || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</div>' +
        (lines ? '<div class="iv-order-lines">' + lines + '</div>' : '') + (events ? '<div class="iv-order-lines">' + events + '</div>' : '') +
        '<div class="iv-order-btns">' + (!closed && !paid ? '<button class="iv-btn" data-o="pay">Pay now</button>' : '') + (!closed ? '<button class="iv-btn danger" data-o="cancel">Cancel</button>' : '') + '</div></div>';
    }).join('');
    box.querySelectorAll('.iv-order').forEach(card => { const id = card.dataset.id, pay = card.querySelector('[data-o="pay"]'), cancel = card.querySelector('[data-o="cancel"]');
      if (pay) pay.onclick = async function(){ this.disabled = true; try{ const r = await post('orders/' + id + '/pay/', {payment_method:'card', gateway_code:'yoco'}); if (r.redirect_url) location.href = r.redirect_url; else { toast('Payment started'); loaders.orders(); } }catch(err){ toast(err.message, 'error'); this.disabled = false; } };
      if (cancel) cancel.onclick = async function(){ if (!confirm('Cancel this order?')) return; this.disabled = true; try{ await post('orders/' + id + '/cancel/', {}); toast('Order cancelled'); loaders.orders(); }catch(err){ toast(err.message, 'error'); this.disabled = false; } }; });
  }catch(err){ fail(box, err); }
};

/* ---------- WISHLIST / WALLET / SELLER / NOTIFS / COURIER ---------- */
loaders.wishlist = async function(){
  const box = $('wishlistContent'); if (!isLoggedIn) return needLogin(box, 'heart', 'Sign in to see your wishlist', true); loading(box, true);
  try{ const list = listOf(await api('wishlist/')); wished = new Set(list.map(p => p.id));
    box.innerHTML = list.length ? list.map(cardHTML).join('') : '<div class="iv-empty" style="grid-column:1/-1;"><i class="fas fa-heart"></i><h4>No saved products</h4><p>Tap the heart on a product to save it.</p></div>';
  }catch(err){ fail(box, err, true); }
};
loaders.wallet = async function(){
  const box = $('walletContent'); if (!isLoggedIn) return needLogin(box, 'wallet', 'Sign in to see your wallet'); loading(box);
  try{ const d = await api('wallet/'), b = d.balances || [], e = d.entries || [];
    box.innerHTML = '<div class="iv-cart-summary"><h4>Balances</h4>' + (b.length ? b.map(x => '<div class="iv-cart-row"><span>' + esc(x.currency) + ' · ' + esc(x.kind) + '</span><span>' + fmtPrice(x.amount, x.currency) + '</span></div>').join('') : '<p style="font-size:12px;color:var(--ink-faint);margin:0">No balances yet.</p>') + '</div>' +
      '<div class="iv-cart-summary"><h4>Recent entries</h4>' + (e.length ? e.map(x => '<div class="iv-cart-row"><span>' + esc(x.kind) + ' · ' + esc(String(x.order_id).slice(0, 8)) + '</span><span>' + fmtPrice(x.amount, x.currency) + '</span></div>').join('') : '<p style="font-size:12px;color:var(--ink-faint);margin:0">No entries yet.</p>') + '</div><p style="font-size:11px;color:var(--ink-faint);padding:4px">' + esc(d.note || '') + '</p>';
  }catch(err){ fail(box, err); }
};
loaders.seller = async function(){
  const box = $('sellerContent'); if (!isLoggedIn) return needLogin(box, 'store', 'Sign in to sell on Ivanka'); loading(box);
  try{
    const s = await api('seller/');
    if (!s){
      box.innerHTML = '<div class="iv-empty"><i class="fas fa-store"></i><h4>You don\'t have a store yet</h4><p>Create your seller profile to start listing products.</p></div><div class="iv-form-grid" style="margin-top:16px"><div class="iv-form-field full"><label>Store name</label><input id="sName"></div><div class="iv-form-field full"><label>Address</label><input id="sAddr"></div><div class="iv-form-field full"><label>Description</label><textarea id="sDesc" rows="3"></textarea></div></div><button class="iv-btn block" id="mkStore">Create my store</button>';
      $('mkStore').onclick = async function(){ const name = $('sName').value.trim(), address = $('sAddr').value.trim(), description = $('sDesc').value.trim(); if (!name || !address){ toast('Name and address required', 'error'); return; }
        this.disabled = true; try{ await post('seller/', {name, address, description}); toast('Store created! Awaiting approval.'); loaders.seller(); }catch(err){ toast(err.message, 'error'); this.disabled = false; } };
      return;
    }
    box.innerHTML = '<div class="iv-cart-summary"><div class="iv-cart-row"><span>Store</span><strong>' + esc(s.name) + '</strong></div><div class="iv-cart-row"><span>Status</span><span>' + (s.approved ? '✓ Approved' : 'Pending approval') + '</span></div>' +
      (s.commission_percent != null ? '<div class="iv-cart-row"><span>Commission</span><span>' + esc(s.commission_percent) + '%</span></div>' : '') + (s.shipping_fee != null ? '<div class="iv-cart-row"><span>Shipping fee</span><span>' + fmtPrice(s.shipping_fee, 'ZAR') + '</span></div>' : '') + '</div>' +
      '<div class="iv-sh"><h2 style="font-size:18px">My products</h2></div><div class="iv-products" id="myProducts"></div>';
    const mp = $('myProducts'); loading(mp, true);
    try{ const mine = listOf(await api('products/?mine=1')); mp.innerHTML = mine.length ? mine.map(cardHTML).join('') : '<div class="iv-empty" style="grid-column:1/-1;"><i class="fas fa-box-open"></i><h4>No products yet</h4><p>Product creation is available through the API; add items from your seller tools.</p></div>'; }catch(e){ fail(mp, e, true); }
  }catch(err){ fail(box, err); }
};
loaders.notifications = async function(){
  const box = $('notifContent'); if (!isLoggedIn) return needLogin(box, 'bell', 'Sign in to see updates'); loading(box);
  try{ const list = listOf(await api('notifications/'));
    if (!list.length){ box.innerHTML = '<div class="iv-empty"><i class="fas fa-bell"></i><h4>No updates</h4><p>Order updates will show up here.</p></div>'; return; }
    box.innerHTML = list.map(n => '<div class="iv-notif ' + (n.read ? '' : 'unread') + '" data-id="' + n.id + '"><div class="iv-notif-icon"><i class="fas fa-bell"></i></div><div class="iv-notif-body"><h4>' + esc(n.title) + '</h4><small>' + new Date(n.created_at).toLocaleString() + '</small></div></div>').join('');
    box.querySelectorAll('.iv-notif.unread').forEach(el => el.onclick = async () => { try{ await post('notifications/', {id: Number(el.dataset.id)}); el.classList.remove('unread'); refreshBadges(); }catch(e){} });
  }catch(err){ fail(box, err); }
};
loaders.courier = async function(){
  const box = $('courierContent'); if (!isLoggedIn) return needLogin(box, 'truck-fast', 'Sign in to see courier jobs'); loading(box);
  try{ const jobs = listOf(await api('courier/jobs/'));
    if (!jobs.length){ box.innerHTML = '<div class="iv-empty"><i class="fas fa-truck-fast"></i><h4>No courier jobs available</h4><p>Check back soon.</p></div>'; return; }
    box.innerHTML = jobs.map(j => '<div class="iv-order"><div class="iv-order-head"><h4>Delivery ' + esc(j.order_reference || j.id) + '</h4><span class="iv-pill">' + esc(j.status || 'open') + '</span></div><div class="iv-order-meta">' + esc(j.city || '') + '</div>' +
      (j.display_fee != null ? '<div class="iv-order-total">' + esc(j.currency_symbol || j.currency || '') + ' ' + Number(j.display_fee).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2}) + '</div>' : '') + '</div>').join('');
  }catch(err){ box.innerHTML = '<div class="iv-empty"><i class="fas fa-truck-fast"></i><h4>Courier jobs</h4><p>' + esc(err.message) + '</p></div>'; }
};

/* ---------- JOBS ---------- */
async function jobsApi(path, opts){
  const res = await fetch(JOBS_API.replace(/\/?$/, '/') + path, Object.assign({credentials:'same-origin', headers:{Accept:'application/json'}}, opts || {}));
  const data = await res.json().catch(() => ({}));
  if(!res.ok) throw new Error(data.detail || data.error || 'Unable to load jobs.');
  return data;
}

loaders.jobs = async function(){
  const box = $('jobsContent'); if (!JOBS_API){ box.innerHTML = '<div class="iv-empty"><i class="fas fa-briefcase"></i><h4>Careers &amp; opportunities</h4><p>Contact our team about current opportunities.</p><a class="iv-btn" href="' + esc(document.body.dataset.careersUrl) + '">Visit careers</a></div>'; return; } loading(box);
  try{ const jobs = listOf(await jobsApi(''));
    if (!jobs.length){ box.innerHTML = '<div class="iv-empty"><i class="fas fa-briefcase"></i><h4>No jobs posted yet</h4><p>New openings show up here as soon as employers publish them.</p></div>'; return; }
    box.innerHTML = jobs.map(j => { const sum = String(j.position_summary || j.description || '').slice(0, 150);
      return '<div class="iv-order" data-id="' + esc(j.id) + '"><div class="iv-order-head"><h4>' + esc(j.title || 'Untitled role') + '</h4><span class="iv-pill">' + esc(j.employment_type || 'Full-time') + '</span></div>' +
        '<div class="iv-order-meta">' + esc(j.company_name || 'Employer') + ' · ' + esc(j.location || 'South Africa') + ' · ' + esc(j.salary || 'Salary negotiable') + '</div>' + (sum ? '<div class="iv-order-lines">' + esc(sum) + (sum.length >= 150 ? '…' : '') + '</div>' : '') +
        '<div class="iv-order-btns"><a class="iv-btn ghost" href="/jobs/' + encodeURIComponent(j.id) + '/">View job</a><button class="iv-btn" data-apply>Apply</button></div></div>'; }).join('');
    box.querySelectorAll('[data-apply]').forEach(b => b.onclick = async function(){ if (!isLoggedIn){ openAuth('login'); return; }
      const id = b.closest('.iv-order').dataset.id; b.disabled = true; try{ await jobsApi(encodeURIComponent(id) + '/apply/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:'{}'}); b.textContent = 'Applied'; toast('Application sent'); }catch(err){ toast(err.message, 'error'); b.disabled = false; } });
  }catch(err){ fail(box, err); }
};

/* ---------- BADGES / BOOT ---------- */
async function refreshBadges(){
  if (!isLoggedIn) return;
  try{ const cart = await api('cart/'); const n = (cart.items || []).reduce((s, i) => s + i.quantity, 0); document.querySelectorAll('#cartBadge, #cartBadgeMobile').forEach(b => { b.textContent = n; b.classList.toggle('show', n > 0); }); }catch(e){}
  try{ const u = listOf(await api('notifications/')).filter(n => !n.read).length; const b = $('notifBadge'); if (b){ b.textContent = u; b.classList.toggle('show', u > 0); } }catch(e){}
}
function boot(){ const q = new URLSearchParams(location.search).get('q'); if(q){shopQuery=q.trim();$('searchInput').value=shopQuery;history.replaceState(null,'',location.pathname+'#shop');} render(); refreshBadges(); setInterval(refreshBadges, 60000); }
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
document.addEventListener('keydown', e => { const card = e.target.closest('.iv-product[role="link"]'); if(card && e.target === card && e.key === 'Enter'){ e.preventDefault(); go('product/' + card.dataset.id); } });
window.ivShow = go;
})();
