/**
 * service-worker.js – Kasi Flavour Offline Mode
 * ===============================================
 * Strategy:
 *  - App shell (HTML/CSS/JS) → Cache First
 *  - API calls               → Network First, fallback to cache
 *  - Images                  → Stale While Revalidate
 */

const CACHE_NAME    = "kasi-flavour-v1";
const OFFLINE_PAGE  = "/pages/offline.html";

const APP_SHELL = [
  "/",
  "/pages/index.html",
  "/pages/orders.html",
  "/pages/track.html",
  "/css/main.css",
  "/js/api.js",
  "/js/cart.js",
  "/js/menus.js",
  OFFLINE_PAGE,
];

// ── Install: cache app shell ──────────────────────────────────────────────────
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

// ── Activate: delete old caches ───────────────────────────────────────────────
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch: routing strategy ───────────────────────────────────────────────────
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // Skip non-GET and cross-origin WebSocket
  if (e.request.method !== "GET") return;
  if (url.protocol === "ws:" || url.protocol === "wss:") return;

  // API calls → Network First
  if (url.pathname.startsWith("/api/")) {
    e.respondWith(networkFirst(e.request));
    return;
  }

  // Images → Stale While Revalidate
  if (/\.(png|jpg|jpeg|webp|svg|gif)$/.test(url.pathname)) {
    e.respondWith(staleWhileRevalidate(e.request));
    return;
  }

  // App shell → Cache First
  e.respondWith(cacheFirst(e.request));
});

// ── Strategies ────────────────────────────────────────────────────────────────
async function cacheFirst(req) {
  const cached = await caches.match(req);
  if (cached) return cached;
  try {
    const response = await fetch(req);
    const cache = await caches.open(CACHE_NAME);
    cache.put(req, response.clone());
    return response;
  } catch {
    return caches.match(OFFLINE_PAGE);
  }
}

async function networkFirst(req) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(req);
    cache.put(req, response.clone());
    return response;
  } catch {
    const cached = await cache.match(req);
    if (cached) return cached;
    // Return empty JSON so the UI can handle it gracefully
    return new Response(JSON.stringify({ offline: true, items: [] }), {
      headers: { "Content-Type": "application/json" },
    });
  }
}

async function staleWhileRevalidate(req) {
  const cache  = await caches.open(CACHE_NAME);
  const cached = await cache.match(req);
  const fetchPromise = fetch(req).then((response) => {
    cache.put(req, response.clone());
    return response;
  }).catch(() => cached);
  return cached || fetchPromise;
}

// ── Background Sync: queue orders placed offline ──────────────────────────────
self.addEventListener("sync", (e) => {
  if (e.tag === "sync-orders") {
    e.waitUntil(syncPendingOrders());
  }
});

async function syncPendingOrders() {
  const db = await openIDB();
  const pending = await getAllFromIDB(db, "pending_orders");
  for (const order of pending) {
    try {
      await fetch("/api/orders", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(order.data),
      });
      await deleteFromIDB(db, "pending_orders", order.id);
    } catch { /* will retry next sync */ }
  }
}

// ── Minimal IndexedDB helpers for offline order queue ─────────────────────────
function openIDB() {
  return new Promise((res, rej) => {
    const req = indexedDB.open("kasi-offline", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("pending_orders", { autoIncrement: true, keyPath: "id" });
    req.onsuccess = () => res(req.result);
    req.onerror   = () => rej(req.error);
  });
}
function getAllFromIDB(db, store) {
  return new Promise((res) => {
    const tx = db.transaction(store, "readonly");
    const req = tx.objectStore(store).getAll();
    req.onsuccess = () => res(req.result);
  });
}
function deleteFromIDB(db, store, id) {
  return new Promise((res) => {
    const tx = db.transaction(store, "readwrite");
    tx.objectStore(store).delete(id);
    tx.oncomplete = res;
  });
}
