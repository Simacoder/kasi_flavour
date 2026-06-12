/**
 * js/cart.js – Shopping cart state and order placement
 */

let cart = JSON.parse(localStorage.getItem("kf_cart") || "[]");

function saveCart() {
  localStorage.setItem("kf_cart", JSON.stringify(cart));
  renderCart();
}

function addToCart(id, name, price) {
  const existing = cart.find(i => i.id === id);
  if (existing) {
    existing.qty++;
  } else {
    cart.push({ id, name, price, qty: 1 });
  }
  saveCart();
  // Brief visual feedback
  document.getElementById("cart-count").textContent = cart.reduce((s, i) => s + i.qty, 0);
}

function removeFromCart(id) {
  cart = cart.filter(i => i.id !== id);
  saveCart();
}

function renderCart() {
  const container = document.getElementById("cart-items");
  if (!container) return;

  document.getElementById("cart-count").textContent =
    cart.reduce((s, i) => s + i.qty, 0);

  if (!cart.length) {
    container.innerHTML = `<p style="text-align:center;padding:24px;color:#999;">Your cart is empty</p>`;
    document.getElementById("cart-total").textContent = "R0.00";
    return;
  }

  container.innerHTML = cart.map(item => `
    <div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-bottom:1px solid #eee">
      <div style="flex:1">
        <p style="font-weight:600;font-size:14px">${item.name}</p>
        <p style="font-size:13px;color:var(--orange)">R${item.price.toFixed(2)} × ${item.qty}</p>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <button onclick="changeQty(${item.id},-1)"
          style="width:28px;height:28px;border-radius:50%;border:1.5px solid var(--orange);background:none;font-size:16px;cursor:pointer;color:var(--orange)">−</button>
        <span style="font-weight:700">${item.qty}</span>
        <button onclick="changeQty(${item.id},1)"
          style="width:28px;height:28px;border-radius:50%;border:1.5px solid var(--red);background:var(--red);color:#fff;font-size:16px;cursor:pointer">+</button>
        <button onclick="removeFromCart(${item.id})"
          style="background:none;border:none;cursor:pointer;color:#999;font-size:18px;">✕</button>
      </div>
    </div>
  `).join("");

  const subtotal = cart.reduce((s, i) => s + i.price * i.qty, 0);
  document.getElementById("cart-total").textContent = `R${(subtotal + 8).toFixed(2)}`;
}

function changeQty(id, delta) {
  const item = cart.find(i => i.id === id);
  if (!item) return;
  item.qty += delta;
  if (item.qty <= 0) removeFromCart(id);
  else saveCart();
}

function openCart() {
  document.getElementById("cart-overlay").classList.remove("hidden");
  document.getElementById("cart-drawer").classList.remove("hidden");
  renderCart();
}

function closeCart() {
  document.getElementById("cart-overlay").classList.add("hidden");
  document.getElementById("cart-drawer").classList.add("hidden");
}

async function placeOrder() {
  if (!cart.length) return alert("Your cart is empty!");

  const items = cart.map(i => ({ menu_item_id: i.id, quantity: i.qty }));

  try {
    const order = await api.placeOrder(
      items,
      "cash",
      "Delivery address here",
      null, null, null
    );
    alert(`✅ Order #${order.id} placed! We'll notify your cook now.`);
    cart = [];
    saveCart();
    closeCart();
    window.location.href = `track.html?order=${order.id}`;
  } catch (e) {
    alert("Failed to place order: " + (e.detail || "Unknown error"));
  }
}

// Init
renderCart();
