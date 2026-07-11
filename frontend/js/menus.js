/**
 * js/menus.js  –  Kasi Flavour Menu Engine
 * ==========================================
 * Responsibilities:
 *   1. Load & display all meals (public, no auth needed)
 *   2. Load flash deals with countdown timer
 *   3. Load AI recommendations (logged-in users only)
 *   4. Filter by search text + kasi dropdown
 *   5. Gate add-to-cart behind login modal
 *   6. Render meal images from uploaded URLs
 *
 * Upload fix: image src uses full server URL (http://localhost:8000 + /uploads/meals/...)
 * No JOIN bug: GET /api/menus/ has no Cook join unless kasi filter is active
 */

const SERVER = "http://localhost:8000";   // backend base URL
let allMenuItems = [];                     // cached for client-side filtering

// ── Food emoji fallbacks (rotated by item.id) ─────────────────────────────────
const FOOD_EMOJIS = [
  "🍲","🥘","🍛","🥩","🍖","🌽","🥗","🍜","🍱","🥙",
  "🫕","🍚","🥓","🌶","🫔","🧆","🥚","🍳","🥣","🫙"
];

function _emoji(itemId) {
  return FOOD_EMOJIS[(itemId || 0) % FOOD_EMOJIS.length];
}


// ══════════════════════════════════════════════════════════════════════════════
//  LOAD FUNCTIONS
// ══════════════════════════════════════════════════════════════════════════════

async function loadMenus() {
  const grid = document.getElementById("menu-grid");
  if (grid) grid.innerHTML = `<p class="loading">Loading meals…</p>`;

  try {
    // Trailing slash avoids FastAPI 307 redirect on POST
    const res = await fetch(`${SERVER}/api/menus/`);

    if (!res.ok) {
      throw new Error(`Server responded ${res.status} — is uvicorn running?`);
    }

    allMenuItems = await res.json();

    if (!allMenuItems.length) {
      _showEmptyState(grid);
      return;
    }

    renderMenuGrid(allMenuItems);

  } catch (err) {
    _showError(grid, err.message);
  }
}


async function loadFlashDeals() {
  const sec  = document.getElementById("flash-section");
  const grid = document.getElementById("flash-grid");

  try {
    const res   = await fetch(`${SERVER}/api/menus/?flash=true`);
    const deals = res.ok ? await res.json() : [];

    if (!deals.length) {
      if (sec) sec.style.display = "none";
      return;
    }

    if (grid) grid.innerHTML = deals.map(buildCard).join("");
    startFlashTimer();

  } catch {
    if (sec) sec.style.display = "none";
  }
}


async function loadRecommendations() {
  const token  = localStorage.getItem("kf_token");
  const userId = parseInt(localStorage.getItem("kf_user_id") || "0");
  if (!token || !userId) return;    // guests don't get recommendations

  try {
    const res = await fetch(`${SERVER}/api/recommend/`, {
      method:  "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": "Bearer " + token,
      },
      body: JSON.stringify({ user_id: userId, budget: null, lat: null, lng: null }),
    });

    if (!res.ok) return;
    const recs = await res.json();
    if (!recs.length) return;

    // Inject recommendation section above the main menu section
    const menusSection = document.getElementById("menus");
    if (!menusSection) return;

    const sec = document.createElement("section");
    sec.className = "section";
    sec.id = "rec-section";
    sec.innerHTML = `
      <h2>⭐ Recommended for you</h2>
      <div class="menu-grid" id="rec-grid">
        ${recs.map(r => buildCard({
          id:           r.menu_item_id,
          name:         r.name,
          price:        r.price,
          cook_kasi:    r.cook_kasi,
          cuisine_tags: "",
          image_url:    null,
          available:    true,
          is_flash_deal: false,
          flash_price:   null,
          description:  `Score: ${(r.score * 100).toFixed(0)}% match`,
        })).join("")}
      </div>`;
    menusSection.parentNode.insertBefore(sec, menusSection);

  } catch { /* silent — recommendations are a bonus, not critical */ }
}


// ══════════════════════════════════════════════════════════════════════════════
//  RENDER
// ══════════════════════════════════════════════════════════════════════════════

function renderMenuGrid(items) {
  const grid = document.getElementById("menu-grid");
  if (!grid) return;

  if (!items.length) {
    grid.innerHTML = `
      <div style="grid-column:1/-1;text-align:center;padding:32px;color:#aaa">
        <p>No meals match your search.</p>
      </div>`;
    return;
  }

  grid.innerHTML = items.map(buildCard).join("");
}


function buildCard(item) {
  const loggedIn  = !!localStorage.getItem("kf_token");
  const price     = item.flash_price ?? item.price ?? 0;
  const safeN     = (item.name || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");
  const emoji     = _emoji(item.id);

  // ── Image ─────────────────────────────────────────────────────────────────
  // UPLOAD FIX: prefix server origin so image URL is always absolute
  const imgHtml = item.image_url
    ? `<img
         src="${SERVER}${item.image_url}"
         alt="${safeN}"
         style="width:100%;height:160px;object-fit:cover;display:block"
         onerror="this.outerHTML='<div class=\\'menu-card-img\\'>${emoji}</div>'"/>`
    : `<div class="menu-card-img">${emoji}</div>`;

  // ── Tags ─────────────────────────────────────────────────────────────────
  const tags = (item.cuisine_tags || "")
    .split(",")
    .filter(Boolean)
    .map(t => `<span class="tag">${t.trim()}</span>`)
    .join("");

  // ── Price display ─────────────────────────────────────────────────────────
  const oldPrice = item.flash_price
    ? `<span style="font-size:11px;text-decoration:line-through;color:#aaa;margin-right:3px">
         R${(item.price || 0).toFixed(2)}
       </span>`
    : "";

  // ── Action button — gated for guests ──────────────────────────────────────
  const action = loggedIn
    ? `<button
         class="btn-add"
         onclick="event.stopPropagation(); addToCart(${item.id}, '${safeN}', ${price})">
         + Add
       </button>`
    : `<button
         class="btn-add"
         style="background: var(--orange)"
         onclick="event.stopPropagation(); openModal('login')">
         🔒 Login to order
       </button>`;

  // ── Hover gate overlay for guests ─────────────────────────────────────────
  const overlay = !loggedIn
    ? `<div
         onclick="openModal('login')"
         style="position:absolute;inset:0;border-radius:12px;cursor:pointer;
                background:rgba(62,39,35,0);transition:background .2s"
         onmouseover="this.style.background='rgba(62,39,35,.5)';
                      this.querySelector('span').style.opacity='1'"
         onmouseout="this.style.background='rgba(62,39,35,0)';
                     this.querySelector('span').style.opacity='0'">
         <span style="position:absolute;bottom:56px;left:50%;transform:translateX(-50%);
                      background:var(--red);color:#fff;border-radius:8px;padding:7px 16px;
                      font-size:13px;font-weight:700;opacity:0;transition:opacity .2s;
                      white-space:nowrap;pointer-events:none">
           🔒 Login to order
         </span>
       </div>`
    : "";

  return `
    <div class="menu-card" style="position:relative">
      ${imgHtml}
      ${overlay}
      <div class="menu-card-body">
        <h3>${item.name || "Meal"}</h3>
        ${item.cook_kasi
          ? `<p class="kasi-tag">📍 ${item.cook_kasi}</p>`
          : ""}
        ${item.description
          ? `<p style="font-size:12px;color:#888;margin-bottom:5px;line-height:1.4">
               ${item.description}
             </p>`
          : ""}
        <div class="tags">${tags}</div>
      </div>
      <div class="menu-card-footer">
        <div>${oldPrice}<span class="price">R${price.toFixed(2)}</span></div>
        ${action}
      </div>
    </div>`;
}


// ══════════════════════════════════════════════════════════════════════════════
//  FILTER
// ══════════════════════════════════════════════════════════════════════════════

function filterMenus() {
  const q    = (document.getElementById("search")?.value    || "").toLowerCase().trim();
  const kasi = (document.getElementById("kasi-filter")?.value || "").toLowerCase().trim();

  const filtered = allMenuItems.filter(item => {
    const matchQ = !q
      || (item.name         || "").toLowerCase().includes(q)
      || (item.cuisine_tags || "").toLowerCase().includes(q)
      || (item.description  || "").toLowerCase().includes(q);

    const matchKasi = !kasi
      || (item.cook_kasi || "").toLowerCase().includes(kasi);

    return matchQ && matchKasi;
  });

  renderMenuGrid(filtered);
}


// ══════════════════════════════════════════════════════════════════════════════
//  FLASH DEAL COUNTDOWN
// ══════════════════════════════════════════════════════════════════════════════

function startFlashTimer() {
  const el = document.getElementById("flash-timer");
  if (!el) return;

  let secs = 60 * 42;   // 42 minutes remaining (demo value)

  (function tick() {
    const m = String(Math.floor(secs / 60)).padStart(2, "0");
    const s = String(secs % 60).padStart(2, "0");
    el.textContent = `⏱ ${m}:${s} left`;
    if (secs-- > 0) {
      setTimeout(tick, 1000);
    } else {
      el.textContent = "Expired";
      el.style.background = "#aaa";
    }
  })();
}


// ══════════════════════════════════════════════════════════════════════════════
//  EMPTY STATE / ERROR STATE
// ══════════════════════════════════════════════════════════════════════════════

function _showEmptyState(grid) {
  if (!grid) return;
  grid.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:52px 20px;color:#aaa">
      <div style="font-size:58px;margin-bottom:14px">🍽</div>
      <p style="font-size:16px;font-weight:600;color:#555">No meals available yet</p>
      <p style="font-size:13px;margin-top:8px">
        Are you a cook?
        <a href="seller.html" style="color:var(--red);font-weight:600">
          Add your first meal →
        </a>
      </p>
      <p style="font-size:12px;margin-top:10px;color:#bbb">
        Just added a meal? Check
        <a href="${SERVER}/api/menus/debug" target="_blank"
           style="color:var(--red)">
          /api/menus/debug
        </a>
        to verify it saved.
      </p>
    </div>`;
}

function _showError(grid, message) {
  if (!grid) return;
  grid.innerHTML = `
    <div style="grid-column:1/-1;text-align:center;padding:52px 20px">
      <div style="font-size:52px;margin-bottom:12px">⚠️</div>
      <p style="font-size:15px;font-weight:600;color:var(--red)">
        Cannot connect to server
      </p>
      <p style="font-size:13px;color:#888;margin-top:6px">${message}</p>
      <p style="font-size:12px;color:#bbb;margin-top:10px">
        Make sure uvicorn is running:<br>
        <code style="background:#f5f5f5;padding:3px 10px;border-radius:5px">
          uvicorn main:app --reload --port 8000
        </code>
      </p>
      <button
        onclick="loadMenus()"
        style="margin-top:16px;padding:10px 24px;background:var(--red);color:#fff;
               border:none;border-radius:8px;font-size:14px;font-weight:700;cursor:pointer">
        ↺ Retry
      </button>
    </div>`;
}


// ══════════════════════════════════════════════════════════════════════════════
//  INITIALISE
// ══════════════════════════════════════════════════════════════════════════════

loadFlashDeals();
loadMenus().then(loadRecommendations);