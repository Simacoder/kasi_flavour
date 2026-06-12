/**
 * js/api.js – Centralised API client for Kasi Flavour
 * All fetch calls go through here so the base URL is one place.
 */

const API_BASE = "http://localhost:8000/api";

const api = {

  // ── Auth ───────────────────────────────────────────────────────────────────
  async register(name, phone, password, role = "customer") {
    return _post("/auth/register", { name, phone, password, role });
  },

  async login(phone, password) {
    const data = await _post("/auth/login", { phone, password });
    if (data.access_token) localStorage.setItem("kf_token", data.access_token);
    return data;
  },

  logout() {
    localStorage.removeItem("kf_token");
    window.location.href = "login.html";
  },

  // ── Menus ──────────────────────────────────────────────────────────────────
  async getMenus(kasi = "", tag = "", flash = false) {
    const params = new URLSearchParams();
    if (kasi)  params.set("kasi", kasi);
    if (tag)   params.set("tag",  tag);
    if (flash) params.set("flash", "true");
    return _get(`/menus?${params}`);
  },

  async getFlashDeals() {
    return _get("/menus?flash=true");
  },

  // ── Orders ─────────────────────────────────────────────────────────────────
  async placeOrder(items, paymentMethod, deliveryAddress, lat, lng, notes) {
    return _post("/orders", {
      items,
      payment_method:   paymentMethod,
      delivery_address: deliveryAddress,
      delivery_lat:     lat,
      delivery_lng:     lng,
      notes,
    });
  },

  async getOrder(orderId) {
    return _get(`/orders/${orderId}`);
  },

  async getMyOrders() {
    return _get("/orders");
  },

  // ── Recommendations ────────────────────────────────────────────────────────
  async getRecommendations(userId, budget, lat, lng) {
    return _post("/recommend", { user_id: userId, budget, lat, lng });
  },

  // ── Tracking ───────────────────────────────────────────────────────────────
  openTrackingSocket(orderId, onLocation) {
    const ws = new WebSocket(`ws://localhost:8000/api/track/order/${orderId}`);
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      onLocation(data.lat, data.lng);
    };
    ws.onerror = (e) => console.error("Tracking WS error", e);
    return ws;
  },

  openDriverSocket(driverId) {
    const ws = new WebSocket(`ws://localhost:8000/api/track/driver/${driverId}`);
    return {
      sendLocation(orderId, lat, lng) {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ order_id: orderId, lat, lng }));
        }
      },
      close() { ws.close(); }
    };
  },
};

// ── Private helpers ───────────────────────────────────────────────────────────
async function _get(path) {
  const res = await fetch(API_BASE + path, { headers: _headers() });
  if (!res.ok) throw await res.json();
  return res.json();
}

async function _post(path, body) {
  const res = await fetch(API_BASE + path, {
    method:  "POST",
    headers: { "Content-Type": "application/json", ..._headers() },
    body:    JSON.stringify(body),
  });
  if (!res.ok) throw await res.json();
  return res.json();
}

function _headers() {
  const token = localStorage.getItem("kf_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

window.api = api;
