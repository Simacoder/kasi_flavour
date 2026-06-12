/**
 * js/menus.js – Load and render menus, flash deals, and AI recommendations
 */

let allMenuItems = [];

async function loadMenus() {
  try {
    allMenuItems = await api.getMenus();
    renderMenuGrid(allMenuItems);
  } catch (e) {
    document.getElementById("menu-grid").innerHTML =
      `<p class="loading">Could not load menus. Is the server running?</p>`;
  }
}

async function loadFlashDeals() {
  try {
    const deals = await api.getFlashDeals();
    const grid = document.getElementById("flash-grid");
    if (!deals.length) {
      grid.innerHTML = `<p style="color:var(--orange);font-size:14px;">No flash deals right now – check back soon!</p>`;
      return;
    }
    grid.innerHTML = deals.map(buildCard).join("");
    startFlashTimer();
  } catch (e) { /* silent */ }
}

async function loadRecommendations() {
  try {
    // Use user_id 1 for demo; replace with auth user id
    const recs = await api.getRecommendations(1, null, null, null);
    const grid = document.getElementById("rec-grid");
    if (!recs.length) { grid.closest("section").remove(); return; }
    grid.innerHTML = recs.map(r => buildCard({
      ...r, id: r.menu_item_id, cuisine_tags: ""
    })).join("");
  } catch (e) {
    document.getElementById("rec-grid").closest("section").remove();
  }
}

function renderMenuGrid(items) {
  const grid = document.getElementById("menu-grid");
  if (!items.length) {
    grid.innerHTML = `<p class="loading">No meals found.</p>`;
    return;
  }
  grid.innerHTML = items.map(buildCard).join("");
}

function buildCard(item) {
  const tags = item.cuisine_tags
    ? item.cuisine_tags.split(",").filter(Boolean)
        .map(t => `<span class="tag">${t.trim()}</span>`).join("")
    : "";

  const displayPrice = item.flash_price ?? item.price;
  const originalPrice = item.flash_price ? `<span class="flash-price">R${item.price.toFixed(2)}</span>` : "";

  return `
    <div class="menu-card" onclick="addToCart(${item.id}, '${item.name}', ${displayPrice})">
      <div class="menu-card-img">🍽</div>
      <div class="menu-card-body">
        <h3>${item.name}</h3>
        ${item.cook_kasi ? `<p class="kasi-tag">📍 ${item.cook_kasi}</p>` : ""}
        <div class="tags">${tags}</div>
      </div>
      <div class="menu-card-footer">
        <div>
          ${originalPrice}
          <span class="price">R${displayPrice.toFixed(2)}</span>
        </div>
        <button class="btn-add" onclick="event.stopPropagation();addToCart(${item.id},'${item.name}',${displayPrice})">
          + Add
        </button>
      </div>
    </div>`;
}

function filterMenus() {
  const query = document.getElementById("search").value.toLowerCase();
  const kasi  = document.getElementById("kasi-filter").value.toLowerCase();
  const filtered = allMenuItems.filter(item => {
    const matchQuery = !query ||
      item.name.toLowerCase().includes(query) ||
      item.cuisine_tags.toLowerCase().includes(query);
    const matchKasi = !kasi || (item.cook_kasi || "").toLowerCase().includes(kasi);
    return matchQuery && matchKasi;
  });
  renderMenuGrid(filtered);
}

// ── Flash deal countdown timer ────────────────────────────────────────────────
function startFlashTimer() {
  const timerEl = document.getElementById("flash-timer");
  if (!timerEl) return;
  let seconds = 60 * 42; // 42 min remaining demo
  const tick = () => {
    const m = Math.floor(seconds / 60).toString().padStart(2, "0");
    const s = (seconds % 60).toString().padStart(2, "0");
    timerEl.textContent = `⏱ ${m}:${s} left`;
    if (seconds > 0) { seconds--; setTimeout(tick, 1000); }
    else { timerEl.textContent = "Deal expired!"; }
  };
  tick();
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadFlashDeals();
loadRecommendations();
loadMenus();
