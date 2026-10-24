"use strict";
const $ = (s, root = document) => root.querySelector(s),
  $$ = (s, root = document) => [...root.querySelectorAll(s)];
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const state = {
  user: { authenticated: false },
  config: null,
  currency: "ZAR",
  category: "",
  products: new Map(),
  next: null,
  cart: [],
  page: "shop",
  checkoutKey: null,
};
try {
  state.currency = localStorage.getItem("ivanka-currency") || "ZAR";
} catch (e) {}
let pending = 0,
  toastTimer,
  watchId = null,
  mapLoaded = null;
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("#toast").hidden = true), 4500);
}
function errorText(data) {
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(errorText).join(" ");
  return Object.entries(data || {})
    .map(
      ([k, v]) =>
        (k === "detail" || k === "non_field_errors" ? "" : k + ": ") +
        errorText(v),
    )
    .join(" ");
}
async function api(path, options = {}) {
  const url =
    /^https?:/.test(path) || path.startsWith("/") ? path : "/store/api/" + path;
  if (new URL(url, location.origin).origin !== location.origin)
    throw Error("Unexpected API location.");
  const csrf = decodeURIComponent(
    document.cookie
      .split("; ")
      .find((x) => x.startsWith("csrftoken="))
      ?.split("=")
      .slice(1)
      .join("=") || "",
  );
  const headers = { "X-CSRFToken": csrf, ...options.headers };
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  pending++;
  $("#busy").hidden = false;
  try {
    const r = await fetch(url, {
      ...options,
      headers,
      credentials: "same-origin",
    });
    const raw = await r.text();
    let data = null;
    if (raw) {
      try {
        data = JSON.parse(raw);
      } catch {
        throw Error("The server returned an unreadable response.");
      }
    }
    if (!r.ok) throw Error(errorText(data) || `Request failed (${r.status}).`);
    return data;
  } finally {
    pending--;
    $("#busy").hidden = pending === 0;
  }
}
function price(n, code = state.currency) {
  try {
    return new Intl.NumberFormat("en-ZA", {
      style: "currency",
      currency: code,
      currencyDisplay: "symbol",
    }).format(Number(n));
  } catch (e) {
    return `${code} ${Number(n).toFixed(2)}`;
  }
}
function field(name, label, type = "text", value = "", extra = "") {
  return `<label class="field">${esc(label)}<input name="${esc(name)}" type="${type}" value="${esc(value)}" ${extra}></label>`;
}
function textField(name, label, value = "") {
  return `<label class="field">${esc(label)}<textarea name="${name}" required>${esc(value)}</textarea></label>`;
}
function empty(title, description, link = "") {
  return `<div class="empty"><h3>${esc(title)}</h3><p>${esc(description)}</p>${link}</div>`;
}
function showModal(title, content) {
  $("#modal-label").textContent = title;
  $("#modal-body").innerHTML = content;
  if (!$("#modal").open) $("#modal").showModal();
}
function closeModal() {
  $("#modal").close();
}
function formModal(title, content, onSubmit, submit = "Save") {
  showModal(
    title,
    `<h2>${esc(title)}</h2><form id="active-form">${content}<p class="form-error" id="form-error" role="alert"></p><button class="primary" type="submit">${esc(submit)} ↗</button></form>`,
  );
  $("#active-form").onsubmit = async (e) => {
    e.preventDefault();
    const button = $("button[type=submit]", e.target);
    button.disabled = true;
    $("#form-error").textContent = "";
    try {
      await onSubmit(new FormData(e.target), e.target);
    } catch (err) {
      if ($("#form-error")) $("#form-error").textContent = err.message;
      else toast(err.message);
    } finally {
      button.disabled = false;
    }
  };
}
function needAuth() {
  if (state.user.authenticated) return true;
  authModal();
  return false;
}
function authModal(register = false) {
  formModal(
    register ? "Create your Ivanka account" : "Welcome to Ivanka",
    `${field("username", "Username", "text", "", 'required autocomplete="username" maxlength="150"')}${register ? field("email", "Email", "email", "", 'required autocomplete="email"') : ""}${field("password", "Password", "password", "", 'required minlength="8" autocomplete="' + (register ? "new-password" : "current-password") + '"')}<p class="fine-print">${register ? "Already have an account?" : "New here?"} <button type="button" id="switch-auth" class="link-button">${register ? "Sign in" : "Create an account"}</button></p>${!register ? '<p><a class="text-link" href="/accounts/password_reset/">Forgot password?</a></p>' : ""}`,
    async (fd) => {
      await api("/api/auth/" + (register ? "register" : "login") + "/", {
        method: "POST",
        body: Object.fromEntries(fd),
      });
      state.user = await api("/api/me/");
      closeModal();
      toast("Welcome, " + state.user.name);
      await refreshCart();
      route();
    },
    register ? "Create account" : "Sign in",
  );
  $("#switch-auth").onclick = () => authModal(!register);
}
function card(p) {
  state.products.set(p.id, p);
  const v = p.variants[0],
    image = p.images[0];
  return `<article class="product-card"><div class="product-visual" role="button" tabindex="0" data-action="detail" data-id="${p.id}" aria-label="View ${esc(p.name)}">${image ? `<img src="${esc(image.image)}" alt="${esc(image.alt || p.name)}" loading="lazy">` : '<div class="empty">Image coming soon</div>'}${p.featured ? '<span class="product-tag">THE IVANKA EDIT</span>' : ""}</div><button class="save-button" data-action="save" data-id="${p.id}" aria-label="Save ${esc(p.name)}">♡</button><div class="product-meta"><span>${esc(p.brand || p.store_name)}</span><span>${p.rating ? "★ " + Number(p.rating).toFixed(1) : "NEW FIND"}</span></div><h3><a href="#" data-action="detail" data-id="${p.id}">${esc(p.name)}</a></h3><div class="product-bottom"><strong>${v ? price(v.display_price) : "Coming soon"}</strong><button class="add-button" data-action="detail" data-id="${p.id}" aria-label="Choose options for ${esc(p.name)}">+</button></div></article>`;
}
async function loadProducts(append = false) {
  const params = new URLSearchParams({
    currency: state.currency,
    search: $("#search").value,
  });
  if (state.category) params.set("category", state.category);
  if ($("#stock-filter").checked) params.set("in_stock", "1");
  if ($("#min-price").value) params.set("min_price", $("#min-price").value);
  if ($("#max-price").value) params.set("max_price", $("#max-price").value);
  const data = await api(append ? state.next : `products/?${params}`);
  const rows = data.results || data;
  state.next = data.next;
  const markup =
    rows.map(card).join("") ||
    empty(
      "A fresh start",
      "No products match these filters. Try another search.",
    );
  if (append) $("#products").insertAdjacentHTML("beforeend", markup);
  else $("#products").innerHTML = markup;
  $("#product-count").textContent =
    `${data.count ?? rows.length} considered finds`;
  $("#load-more").hidden = !state.next;
}
async function productDetail(id) {
  const p = await api(`products/${id}/?currency=${state.currency}`);
  state.products.set(p.id, p);
  showModal(
    p.brand || p.store_name,
    `<div class="split"><div><img id="detail-img" class="detail-image" src="${esc(p.images[0]?.image || "/static/store/placeholder.png")}" alt="${esc(p.name)}"><div class="actions">${p.images.map((im) => `<button class="small-button" data-action="gallery" data-src="${esc(im.image)}">${esc(im.position + 1)}</button>`).join("")}</div></div><div><p class="eyebrow">${esc(p.store_name)}</p><h2>${esc(p.name)}</h2><div class="detail-description">${esc(p.description)}</div><label class="field">Choose your option<select id="variant-select">${p.variants.map((v) => `<option value="${v.id}" ${v.stock ? "" : "disabled"}>${esc(v.label)} — ${price(v.display_price)} · ${v.stock} in stock</option>`).join("")}</select></label>${field("quantity", "Quantity", "number", "1", 'id="detail-quantity" min="1" max="99"')}<button class="primary" id="detail-add" ${p.variants.some((v) => v.stock > 0) ? "" : "disabled"}>Add to bag +</button><p class="fine-print">Delivery calculated at checkout. Prices in ${esc(state.currency)}.</p></div></div>`,
  );
  $("#detail-add").onclick = async () => {
    if (!needAuth()) return;
    try {
      const variant = Number($("#variant-select").value),
        qty = Number($("#detail-quantity").value);
      const existing = state.cart.find((x) => x.variant === variant);
      await api("cart/", {
        method: "POST",
        body: { variant, quantity: (existing?.quantity || 0) + qty },
      });
      await refreshCart();
      closeModal();
      toast("A good find, added to your bag.");
    } catch (e) {
      toast(e.message);
    }
  };
}
async function refreshCart() {
  if (!state.user.authenticated) {
    state.cart = [];
    $("#cart-count").textContent = "0";
    return;
  }
  const c = await api(`cart/?currency=${state.currency}`);
  state.cart = c.items;
  $("#cart-count").textContent = c.items.reduce((n, x) => n + x.quantity, 0);
  return c;
}
async function cartModal() {
  if (!needAuth()) return;
  const c = await refreshCart();
  showModal(
    "YOUR BAG",
    `<h2>Your good finds.</h2>${c.items.length ? c.items.map((l) => `<div class="row">${l.image ? `<img src="${esc(l.image)}" alt="${esc(l.name)}">` : ""}<div class="grow"><h3>${esc(l.name)}</h3><span class="muted">${esc(l.label)} · ${esc(l.store_name)}</span></div><input class="quantity" aria-label="Quantity for ${esc(l.name)}" type="number" value="${l.quantity}" min="0" max="99" data-cart-variant="${l.variant}"><strong>${price(Number(l.price) * l.quantity)}</strong><button class="small-button" data-action="remove" data-id="${l.variant}" aria-label="Remove ${esc(l.name)}">✕</button></div>`).join("") + `<div class="totals"><span>Subtotal</span><strong>${price(c.subtotal)}</strong></div><p class="fine-print">Shipping and eligible discounts are calculated securely at checkout. One order is created for each seller.</p><button class="primary" id="checkout-button">Continue to checkout ↗</button>` : empty("Your bag is waiting", "Discover something you’ll love.", '<button class="secondary" data-action="close">Keep exploring</button>')}`,
  );
  if ($("#checkout-button")) $("#checkout-button").onclick = checkoutModal;
  $$("[data-cart-variant]").forEach(
    (input) =>
      (input.onchange = async () => {
        try {
          await api("cart/", {
            method: "POST",
            body: {
              variant: Number(input.dataset.cartVariant),
              quantity: Number(input.value),
            },
          });
          await cartModal();
        } catch (e) {
          toast(e.message);
        }
      }),
  );
}
async function checkoutModal() {
  const a = await api("addresses/");
  const addresses = a.results || a;
  formModal(
    "Make it yours.",
    `<label class="field">Deliver to<select name="address_id" required><option value="">Choose an address</option>${addresses.map((x) => `<option value="${x.id}">${esc(x.recipient)} · ${esc(x.line1)}, ${esc(x.city)}</option>`).join("")}</select></label><button type="button" id="add-address" class="small-button">+ Add delivery address</button>${field("coupon", "Discount code (optional)")}<p class="fine-print">Order currency: ${esc(state.currency)}. Delivery is charged per seller. You can select payment on each order after reviewing its final total.</p>`,
    async (fd) => {
      state.checkoutKey ||= crypto.randomUUID();
      const body = {
        address_id: Number(fd.get("address_id")),
        coupon: fd.get("coupon"),
        currency: state.currency,
        idempotency_key: state.checkoutKey,
      };
      const result = await api("checkout/", { method: "POST", body });
      state.checkoutKey = null;
      await refreshCart();
      closeModal();
      location.hash = "orders";
      await route();
      toast(
        `${result.orders.length} order(s) created. Review totals and select payment.`,
      );
    },
    "Create orders",
  );
  $("#add-address").onclick = () => addressModal(checkoutModal);
}
function addressModal(
  after = () => {
    closeModal();
    route();
  },
) {
  formModal(
    "A place for your delivery",
    `<div class="form-grid">${field("recipient", "Recipient", "text", state.user.name || "", "required")}${field("phone", "Phone", "tel", "", "required")}${field("line1", "Street address", "text", "", "required")}${field("city", "City", "text", "", "required")}${field("province", "Province / region", "text", "", "required")}${field("postal_code", "Postal code", "text", "", "required")}${field("latitude", "Latitude (optional)", "number", "", 'step="any" min="-90" max="90"')}${field("longitude", "Longitude (optional)", "number", "", 'step="any" min="-180" max="180"')}</div><button type="button" id="address-gps" class="secondary">⌖ Use my current location</button><p class="fine-print">GPS requires your permission. Confirm the street address and postal code before saving.</p>`,
    async (fd) => {
      const data = Object.fromEntries(fd);
      if (!data.latitude) delete data.latitude;
      if (!data.longitude) delete data.longitude;
      await api("addresses/", { method: "POST", body: data });
      await after();
    },
    "Save address",
  );
  $("#address-gps").onclick = () => {
    if (!navigator.geolocation)
      return toast("Location is unavailable in this browser.");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = pos.coords.latitude.toFixed(7),
          lng = pos.coords.longitude.toFixed(7);
        $("[name=latitude]").value = lat;
        $("[name=longitude]").value = lng;
        try {
          const geo = await api(`geocode/reverse/?lat=${lat}&lng=${lng}`);
          $("[name=line1]").value = geo.formatted_address;
          toast("Location found. Check the address fields.");
        } catch (e) {
          toast("GPS saved. Enter your street address manually.");
        }
      },
      (err) => toast(err.message),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };
}
async function ordersPage(next = null) {
  const data = await api(next || "orders/");
  let rows = data.results || data;
  const markup = rows.length
    ? rows
        .map((o) => {
          const buyer = o.buyer === state.user.id;
          return `<article class="panel"><div class="order-head"><div><p class="eyebrow">${esc(o.store_name)} · ${String(o.id).slice(0, 8)}</p><h3>${price(o.total, o.currency)}</h3></div><span class="badge">${esc(o.status)} · ${esc(o.payment_status)}</span></div>${o.items.map((i) => `<div class="row"><div class="grow">${esc(i.name)} <span class="muted">× ${i.quantity}</span></div><span>${price(i.unit_price * i.quantity, o.currency)}</span>${buyer && o.status === "delivered" ? `<button class="small-button" data-action="review" data-id="${i.id}">Review</button><button class="small-button" data-action="return" data-id="${i.id}">Return</button>` : ""}</div>`).join("")}<p class="fine-print">Shipping ${price(o.shipping, o.currency)} · Discount ${price(o.discount, o.currency)} · ${esc(o.address.line1)}, ${esc(o.address.city)}</p><div class="actions">${buyer && o.payment_status !== "paid" && o.status !== "cancelled" ? `<button class="primary" data-action="pay" data-id="${o.id}" data-currency="${esc(o.currency)}">${o.payment ? "View payment" : "Choose payment"} ↗</button>` : ""}${buyer && o.status === "pending" && !o.payment ? `<button class="secondary" data-action="cancel-order" data-id="${o.id}">Cancel order</button>` : ""}${!buyer && ["confirmed", "packing"].includes(o.status) ? `<button class="primary" data-action="order-status" data-id="${o.id}" data-status="${o.status === "confirmed" ? "packing" : "shipped"}">Mark ${o.status === "confirmed" ? "packing" : "shipped"}</button>` : ""}${o.delivery_id ? `<button class="secondary" data-action="track" data-id="${o.delivery_id}">Track delivery ⌖</button>` : ""}<button class="secondary" data-action="messages" data-id="${o.id}">Messages</button></div><div class="timeline">${o.events.map((e) => `<span>${esc(e.status)}</span>`).join("")}</div></article>`;
        })
        .join("")
    : empty(
        "Your next good find is out there",
        "Orders appear here once you check out.",
      );
  if (next) $("#orders-content").insertAdjacentHTML("beforeend", markup);
  else $("#orders-content").innerHTML = markup;
  if (data.next)
    $("#orders-content").insertAdjacentHTML(
      "beforeend",
      `<button class="secondary" data-action="more-orders" data-next="${esc(data.next)}">More orders</button>`,
    );
}
function paymentModal(id, code) {
  showModal(
    "PAYMENT",
    `<h2>Choose how to pay.</h2><p class="fine-print">Currency: ${esc(code)}. Payment status updates after verification.</p><div class="actions"><button class="primary" data-action="start-pay" data-id="${id}" data-method="cash">Cash on delivery</button>${code === "ZAR" && state.config.yoco_configured ? `<button class="secondary" data-action="start-pay" data-id="${id}" data-method="yoco">Card with Yoco ↗</button>` : ""}</div><p class="fine-print">Cash stays unpaid until the assigned driver confirms collection. Online card checkout is available for ZAR when configured.</p>`,
  );
}
async function wishlistPage() {
  const rows = await api(`wishlist/?currency=${state.currency}`);
  $("#wishlist-content").innerHTML = rows.length
    ? rows.map(card).join("")
    : empty(
        "Keep your favourites close",
        "Tap the heart on a product to save it here.",
      );
}
async function messagesModal(id) {
  const rows = await api(`orders/${id}/messages/`);
  formModal(
    "Order messages",
    `<div>${
      rows
        .reverse()
        .map(
          (m) =>
            `<div class="message"><small>${esc(m.sender__username)}</small>${esc(m.content)}</div>`,
        )
        .join("") ||
      '<p class="muted">Start a conversation with your seller.</p>'
    }</div>${textField("content", "Your message")}`,
    async (fd) => {
      await api(`orders/${id}/messages/`, {
        method: "POST",
        body: { content: fd.get("content") },
      });
      await messagesModal(id);
    },
    "Send message",
  );
}
function feedbackModal(id, kind) {
  formModal(
    kind === "review" ? "How was your find?" : "Request a return",
    `${kind === "review" ? '<label class="field">Rating<select name="rating"><option value="5">5 — Excellent</option><option value="4">4 — Good</option><option value="3">3 — Okay</option><option value="2">2 — Poor</option><option value="1">1 — Disappointing</option></select></label>' : ""}${textField(kind === "review" ? "comment" : "reason", kind === "review" ? "Your review" : "Tell us what went wrong")}<p class="fine-print">${kind === "return" ? "Staff will review the request. A request does not automatically issue a refund." : "Reviews are available for delivered purchases."}</p>`,
    async (fd) => {
      await api(`feedback/${kind}/`, {
        method: "POST",
        body: { order_item: Number(id), ...Object.fromEntries(fd) },
      });
      closeModal();
      toast(
        kind === "return"
          ? "Return request submitted."
          : "Thank you for your review.",
      );
    },
    "Submit",
  );
}
async function sellerPage() {
  const store = await api("seller/");
  const root = $("#seller-content");
  if (!store) {
    root.innerHTML = empty(
      "Bring your business to Ivanka",
      "Open your seller account. Listings go live after staff approval.",
      '<button class="primary" data-action="seller-register">Create seller account ↗</button>',
    );
    return;
  }
  root.innerHTML = `<div class="panel"><div class="order-head"><h2>${esc(store.name)}</h2><span class="badge">${store.approved ? "Approved seller" : "Awaiting staff approval"}</span></div><p>${esc(store.description)}</p><div class="actions"><button class="secondary" id="edit-store">Edit store</button>${store.approved ? '<button class="primary" id="new-product">+ Add a product</button>' : ""}<a class="secondary" href="#orders">Manage orders</a><button class="secondary" data-action="wallet">Accounting</button></div></div><div id="seller-products"></div>`;
  $("#edit-store").onclick = () => sellerRegister(store);
  if (!store.approved) return;
  $("#new-product").onclick = () => productForm();
  const data = await api(`products/?mine=1&currency=${state.currency}`);
  $("#seller-products").innerHTML =
    (data.results || data)
      .map(
        (p) =>
          `<div class="panel row"><div class="grow"><h3>${esc(p.name)}</h3><span class="muted">${p.variants.length} options · ${p.active ? "Visible" : "Hidden"}</span></div><div class="actions"><button class="small-button" data-action="edit-product" data-id="${p.id}">Edit</button><button class="small-button" data-action="variant-form" data-id="${p.id}">Price / stock</button><button class="small-button" data-action="upload" data-id="${p.id}">Images</button></div></div>`,
      )
      .join("") ||
    empty("A blank canvas", "Add your first product to get started.");
}
function sellerRegister(store = {}) {
  formModal(
    "Your seller account",
    `${field("name", "Store name", "text", store.name || "", "required")}${textField("description", "About your store", store.description || "")}${field("address", "Dispatch address", "text", store.address || "", "required")}${field("shipping_fee", `Shipping fee (${state.config.catalog_currency})`, "number", store.shipping_fee || "65", 'required min="0" step="0.01"')}${field("latitude", "Dispatch latitude (optional)", "number", store.latitude || "", 'step="any"')}${field("longitude", "Dispatch longitude (optional)", "number", store.longitude || "", 'step="any"')}`,
    async (fd) => {
      const d = Object.fromEntries(fd);
      if (!d.latitude) delete d.latitude;
      if (!d.longitude) delete d.longitude;
      await api("seller/", { method: "POST", body: d });
      state.user = await api("/api/me/");
      closeModal();
      await sellerPage();
      toast("Seller details saved.");
    },
    "Save store",
  );
}
async function productForm(id) {
  const p = id
    ? await api(`products/${id}/?mine=1&currency=${state.currency}`)
    : {};
  formModal(
    id ? "Edit your product" : "Introduce a good find",
    `${field("name", "Product name", "text", p.name || "", "required")}${field("brand", "Brand", "text", p.brand || "")}<label class="field">Category<select name="category">${state.config.categories.map((c) => `<option value="${c.id}" ${c.id === p.category ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></label>${textField("description", "Description", p.description || "")}<label class="field"><span><input type="checkbox" name="active" ${p.active !== false ? "checked" : ""}> Visible in shop</span></label>`,
    async (fd) => {
      const body = Object.fromEntries(fd);
      body.active = fd.has("active");
      await api(id ? `products/${id}/` : "products/", {
        method: id ? "PATCH" : "POST",
        body,
      });
      closeModal();
      await sellerPage();
      toast("Product saved. Add pricing, stock and images next.");
    },
    "Save product",
  );
}
async function variantForm(id) {
  const p = await api(`products/${id}/?mine=1&currency=${state.currency}`);
  const content = `${p.variants.length ? '<p class="fine-print">Choose an existing option to update it, or create a new one.</p><label class="field">Option<select id="edit-variant"><option value="">New option</option>' + p.variants.map((v) => `<option value="${v.id}">${esc(v.label)}</option>`).join("") + "</select></label>" : ""}${field("sku", "Unique SKU", "text", "", "required")}${field("label", "Option (size / colour)", "text", "Standard", "required")}${field("price", `Catalog price (${state.config.catalog_currency})`, "number", "", 'required min="0" step="0.01"')}${field("stock", "Available stock", "number", "0", 'required min="0" step="1"')}${field("weight_kg", "Weight (kg)", "number", "1", 'min="0" step="0.001"')}`;
  formModal(
    "Price & inventory",
    content,
    async (fd) => {
      const body = Object.fromEntries(fd);
      if ($("#edit-variant")?.value) body.id = Number($("#edit-variant").value);
      await api(`products/${id}/variant/`, { method: "POST", body });
      closeModal();
      await sellerPage();
      toast("Inventory updated.");
    },
    "Save option",
  );
  if ($("#edit-variant"))
    $("#edit-variant").onchange = (e) => {
      const v = p.variants.find((v) => v.id === Number(e.target.value));
      for (const k of ["sku", "label", "price", "stock", "weight_kg"])
        $(`[name=${k}]`).value = v
          ? v[k]
          : { label: "Standard", stock: 0, weight_kg: 1 }[k] || "";
    };
}
function uploadForm(id) {
  formModal(
    "A consistent product gallery",
    `${field("image", "Product photo", "file", "", 'required accept="image/jpeg,image/png,image/webp"')}${field("alt", "Image description", "text", "", "required")}${field("position", "Gallery position", "number", "0", 'min="0"')}<p class="fine-print">${state.config.image_background_removal ? "Upload JPG, PNG or WebP. The background will be removed automatically." : "Upload a transparent PNG or WebP product cutout. Ordinary photographs are accepted once automatic cutouts are enabled by the operator."} Up to 10 MB / 25 megapixels. Every image is centred on the same neutral square background.</p>`,
    async (fd) => {
      await api(`products/${id}/image/`, { method: "POST", body: fd });
      closeModal();
      toast("Image processed and saved.");
      await sellerPage();
    },
    "Upload image",
  );
}
async function walletModal() {
  const data = await api("wallet/");
  showModal(
    "ACCOUNTING",
    `<h2>Your ledger.</h2><p class="fine-print">${esc(data.note)} Pending records are not withdrawable balances.</p>${data.balances.map((b) => `<div class="row"><span>${esc(b.kind.replaceAll("_", " "))}</span><strong>${price(b.amount, b.currency)}</strong></div>`).join("") || '<p class="muted">No entries yet.</p>'}`,
  );
}
async function courierPage() {
  const root = $("#courier-content");
  const c = await api("courier/");
  if (!c && !state.user.driver) {
    root.innerHTML = empty(
      "Move with Ivanka",
      "Register your courier company and connect with sellers. Staff approval is required.",
      '<button class="primary" data-action="courier-register">Create courier account ↗</button>',
    );
    return;
  }
  root.innerHTML = `<div class="panel"><div class="order-head"><h2>${esc(c?.name || "Driver workspace")}</h2><span class="badge">${c ? (c.approved ? "Approved courier" : "Awaiting approval") : "Delivery driver"}</span></div><p>Claim open jobs, manage assignments and keep deliveries connected.</p><div class="actions">${c ? '<button class="secondary" id="edit-courier">Edit company</button>' : ""}<button class="secondary" data-action="wallet">Accounting</button>${state.user.driver ? '<button class="primary" id="start-gps">⌖ Share live location</button><button class="secondary" id="stop-gps">Stop sharing</button>' : ""}<button class="secondary" data-reload>Refresh jobs</button></div><p class="fine-print">Location is shared only when you start it, while you have an active delivery and this page stays open. Stop sharing at any time.</p></div><div id="courier-jobs"></div>`;
  if (c) $("#edit-courier").onclick = () => courierRegister(c);
  if (state.user.driver) {
    $("#start-gps").onclick = startGPS;
    $("#stop-gps").onclick = stopGPS;
  }
  if (c && !c.approved) return;
  const rows = await api("courier/jobs/");
  let agents = [];
  if (c) agents = await api("courier/agents/");
  $("#courier-jobs").innerHTML = rows.length
    ? rows
        .map(
          (d) =>
            `<div class="panel"><div class="order-head"><h3>Delivery ${esc(d.order_reference)} · ${esc(d.city)}</h3><span class="badge">${esc(d.status)}</span></div><p>Shipping budget ${price(d.fee, d.currency)}</p><div class="actions">${
              d.status === "open"
                ? `<button class="primary" data-action="claim" data-id="${d.id}">Claim job</button><button class="secondary" data-action="bid" data-id="${d.id}" data-currency="${d.currency}">Place bid</button>`
                : `<button class="secondary" data-action="track" data-id="${d.id}">View delivery</button>${
                    c && d.company === c.id && d.status === "assigned"
                      ? `<select id="agent-${d.id}" aria-label="Assign a driver"><option value="">Choose driver</option>${agents
                          .filter((a) => a.available)
                          .map(
                            (a) =>
                              `<option value="${a.id}">${esc(a.user__username)} · ${esc(a.vehicle)}</option>`,
                          )
                          .join(
                            "",
                          )}</select><button class="secondary" data-action="assign" data-id="${d.id}">Assign</button>`
                      : ""
                  }${state.user.driver && ["assigned", "picked_up", "in_transit"].includes(d.status) ? `<button class="primary" data-action="delivery-status" data-id="${d.id}" data-status="${{ assigned: "picked_up", picked_up: "in_transit", in_transit: "delivered" }[d.status]}">Mark ${{ assigned: "picked up", picked_up: "in transit", in_transit: "delivered" }[d.status]}</button>` : ""}`
            }</div></div>`,
        )
        .join("")
    : empty(
        "No deliveries right now",
        "Jobs appear when sellers start packing their orders.",
      );
}
function courierRegister(c = {}) {
  formModal(
    "Your courier company",
    `${field("name", "Company name", "text", c.name || "", "required")}${field("phone", "Contact phone", "tel", c.phone || "", "required")}`,
    async (fd) => {
      await api("courier/", { method: "POST", body: Object.fromEntries(fd) });
      state.user = await api("/api/me/");
      closeModal();
      courierPage();
    },
    "Save company",
  );
}
function startGPS() {
  if (watchId !== null) return toast("Location sharing is already running.");
  if (!navigator.geolocation) return toast("GPS is unavailable.");
  let last = 0;
  watchId = navigator.geolocation.watchPosition(
    async (p) => {
      if (Date.now() - last < 15000) return;
      last = Date.now();
      try {
        await api("delivery/location/", {
          method: "POST",
          body: {
            latitude: p.coords.latitude.toFixed(7),
            longitude: p.coords.longitude.toFixed(7),
          },
        });
      } catch (e) {
        stopGPS();
        toast(e.message);
      }
    },
    (e) => {
      stopGPS();
      toast(e.message);
    },
    { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 },
  );
  toast("Live location sharing started.");
}
function stopGPS() {
  if (watchId !== null) navigator.geolocation.clearWatch(watchId);
  watchId = null;
  toast("Location sharing stopped.");
}
async function trackModal(id) {
  const d = await api(`delivery/${id}/track/`);
  showModal(
    "DELIVERY TRACKING",
    `<h2>Your delivery, connected.</h2><span class="badge">${esc(d.delivery.status)}</span><p>${esc(d.destination.line1)}, ${esc(d.destination.city)}</p><p class="muted">${d.driver ? esc(d.driver.name) + " · " + (d.driver.fresh ? "Live location available" : "Waiting for a fresh location") : "A driver has not been assigned."}</p><div class="timeline">${d.events.map((e) => `<span>${esc(e.status)}</span>`).join("")}</div><div id="tracking-map" class="map" hidden></div><div id="route-info"></div><div class="actions"><a class="primary" href="${esc(d.navigation_url)}" target="_blank" rel="noopener">Open Google Maps ↗</a><button class="secondary" data-action="track" data-id="${id}">Refresh tracking</button></div>${d.bids?.length ? "<h3>Courier bids</h3>" + d.bids.map((b) => `<div class="row"><span>${esc(b.company__name)} · ${price(b.amount, d.delivery.currency)}</span>${d.delivery.status === "open" ? `<button class="small-button" data-action="accept-bid" data-id="${id}" data-bid="${b.id}">Accept</button>` : ""}</div>`).join("") : ""}`,
  );
  if (d.driver?.fresh) {
    const key = JSON.parse($("#maps-key").textContent);
    if (key)
      try {
        if (!mapLoaded)
          mapLoaded = new Promise((resolve, reject) => {
            const s = document.createElement("script");
            s.src =
              "https://maps.googleapis.com/maps/api/js?key=" +
              encodeURIComponent(key);
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
          });
        await mapLoaded;
        if (!$("#tracking-map")) return;
        $("#tracking-map").hidden = false;
        const center = {
          lat: Number(d.driver.latitude),
          lng: Number(d.driver.longitude),
        };
        const map = new google.maps.Map($("#tracking-map"), {
          center,
          zoom: 13,
        });
        new google.maps.Marker({ position: center, map, title: "Driver" });
        if (d.destination.latitude && d.destination.longitude)
          new google.maps.Marker({
            position: {
              lat: Number(d.destination.latitude),
              lng: Number(d.destination.longitude),
            },
            map,
            title: "Destination",
          });
      } catch (e) {
        toast("Map unavailable. Open Google Maps for directions.");
      }
    try {
      const route = await api(`delivery/${id}/route/`);
      const r = route.routes?.[0];
      if (r && $("#route-info"))
        $("#route-info").textContent =
          `${(r.distanceMeters / 1000).toFixed(1)} km · estimated ${Math.ceil(parseFloat(r.duration) / 60)} min`;
    } catch (e) {}
  }
}
async function careersPage() {
  const jobs = await api("/hiring/api/jobs/");
  $("#careers-content").innerHTML = jobs.length
    ? jobs
        .map(
          (j) =>
            `<article class="panel"><p class="eyebrow">${esc(j.company_name)}</p><h2>${esc(j.title)}</h2><p>${esc(j.location)} · ${esc(j.contract_type)} · Apply by ${esc(j.apply_by)}</p><div class="detail-description">${esc(j.description)}</div><div class="actions"><button class="primary" data-action="apply-job" data-id="${j.id}">Apply for this role ↗</button></div></article>`,
        )
        .join("")
    : empty(
        "New possibilities are coming",
        "Check back for opportunities from Ivanka businesses.",
      );
}
function jobForm() {
  if (!needAuth()) return;
  formModal(
    "A new opportunity",
    `${field("title", "Job title", "text", "", "required")}${field("company_name", "Company", "text", "", "required")}${field("location", "Location", "text", "", "required")}${field("contract_type", "Contract type", "text", "Full time", "required")}${field("apply_by", "Application deadline", "date", "", "required")}${textField("description", "Role and requirements")}<p class="fine-print">Approved sellers and couriers can submit jobs. Staff review and publish them.</p>`,
    async (fd) => {
      await api("/hiring/api/jobs/", {
        method: "POST",
        body: Object.fromEntries(fd),
      });
      closeModal();
      toast("Job submitted for review.");
    },
    "Submit job",
  );
}
async function accountPage() {
  const a = await api("addresses/"),
    n = await api("notifications/"),
    apps = await api("/hiring/api/applications/");
  $("#account-content").innerHTML =
    `<div class="panel"><h2>Hello, ${esc(state.user.name)}.</h2><p>Make yourself at home.</p><div class="actions"><button class="secondary" data-action="logout">Sign out</button><button class="secondary" id="account-theme">Switch black / white theme</button>${state.user.staff ? '<a class="primary" href="/admin/">Administration ↗</a>' : ""}</div></div><div class="split"><div class="panel"><h2>Your addresses</h2>${(a.results || a).map((x) => `<div class="row"><span>${esc(x.recipient)}<br><small>${esc(x.line1)}, ${esc(x.city)}</small></span><button class="small-button" data-action="delete-address" data-id="${x.id}">Remove</button></div>`).join("") || "<p>No addresses yet.</p>"}<div class="actions"><button class="secondary" id="account-address">+ Add address</button></div></div><div class="panel"><h2>Updates for you</h2>${
      n
        .slice(0, 8)
        .map(
          (x) =>
            `<div class="row"><span>${esc(x.title)}</span>${!x.read ? `<button class="small-button" data-action="read-note" data-id="${x.id}">Read</button>` : ""}</div>`,
        )
        .join("") || "<p>You’re all caught up.</p>"
    }</div></div><div class="panel"><h2>Make your next move</h2><div class="actions"><a href="#seller" class="primary">Seller studio ↗</a><a href="#courier" class="secondary">Courier hub ↗</a><a href="#careers" class="secondary">Careers ↗</a></div><h3>Your applications</h3>${apps.map((x) => `<div class="row"><span>${esc(x.job_title)}</span><span class="badge">${esc(x.status)}</span></div>`).join("") || "<p>No applications yet.</p>"}</div>`;
  $("#account-theme").onclick = toggleTheme;
  $("#account-address").onclick = () => addressModal();
}
async function toggleTheme() {
  const theme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem("ivanka-theme", theme);
  } catch (e) {}
  if (state.user.authenticated)
    try {
      await api("/api/me/", { method: "PATCH", body: { theme } });
    } catch (e) {
      toast(e.message);
    }
}
async function route() {
  let page = location.hash.slice(1).split("?")[0] || "shop";
  if (
    ![
      "shop",
      "wishlist",
      "orders",
      "seller",
      "courier",
      "careers",
      "account",
    ].includes(page)
  )
    page = "shop";
  state.page = page;
  $$(".page").forEach((x) => (x.hidden = x.id !== page));
  $$("[data-nav]").forEach((x) =>
    x.classList.toggle("active", x.dataset.nav === page),
  );
  if (!["shop", "careers"].includes(page) && !state.user.authenticated) {
    $(`#${page}-content`).innerHTML = empty(
      "Your Ivanka starts here",
      "Sign in to continue.",
      '<button class="primary" data-action="login">Sign in ↗</button>',
    );
    return;
  }
  try {
    await {
      shop: loadProducts,
      wishlist: wishlistPage,
      orders: ordersPage,
      seller: sellerPage,
      courier: courierPage,
      careers: careersPage,
      account: accountPage,
    }[page]();
  } catch (e) {
    toast(e.message);
  }
}
document.addEventListener("click", async (e) => {
  const el = e.target.closest("[data-action]");
  if (!el) return;
  e.preventDefault();
  const id = el.dataset.id,
    action = el.dataset.action;
  try {
    switch (action) {
      case "detail":
        await productDetail(id);
        break;
      case "gallery":
        $("#detail-img").src = el.dataset.src;
        break;
      case "save":
        if (needAuth()) {
          const d = await api("wishlist/", {
            method: "POST",
            body: { product: Number(id) },
          });
          toast(
            d.saved ? "Saved to your favourites." : "Removed from saved finds.",
          );
          if (state.page === "wishlist") await wishlistPage();
        }
        break;
      case "close":
        closeModal();
        break;
      case "login":
        authModal();
        break;
      case "remove":
        await api("cart/", {
          method: "POST",
          body: { variant: Number(id), quantity: 0 },
        });
        await cartModal();
        break;
      case "pay":
        paymentModal(id, el.dataset.currency);
        break;
      case "start-pay": {
        el.disabled = true;
        const code = el.dataset.method;
        const result = await api(`orders/${id}/pay/`, {
          method: "POST",
          body: {
            payment_method: code === "cash" ? "cash" : "card",
            gateway_code: code,
          },
        });
        if (result.redirect_url) {
          const u = new URL(result.redirect_url);
          if (u.protocol !== "https:") throw Error("Invalid payment redirect.");
          location.assign(u.href);
        } else {
          closeModal();
          await ordersPage();
          toast(
            result.payment.status === "paid"
              ? "Payment confirmed."
              : "Cash on delivery selected.",
          );
        }
        break;
      }
      case "cancel-order":
        await api(`orders/${id}/cancel/`, { method: "POST", body: {} });
        await ordersPage();
        toast("Order cancelled; inventory restored.");
        break;
      case "order-status":
        await api(`orders/${id}/set-status/`, {
          method: "POST",
          body: { status: el.dataset.status },
        });
        await ordersPage();
        break;
      case "messages":
        await messagesModal(id);
        break;
      case "review":
      case "return":
        feedbackModal(id, action);
        break;
      case "seller-register":
        sellerRegister();
        break;
      case "edit-product":
        productForm(id);
        break;
      case "variant-form":
        variantForm(id);
        break;
      case "upload":
        uploadForm(id);
        break;
      case "wallet":
        walletModal();
        break;
      case "courier-register":
        courierRegister();
        break;
      case "claim":
        await api("courier/jobs/", {
          method: "POST",
          body: { delivery: Number(id), action: "claim" },
        });
        await courierPage();
        toast("Delivery claimed. Assign a driver next.");
        break;
      case "bid":
        formModal(
          "Your delivery bid",
          field(
            "amount",
            `Bid amount (${el.dataset.currency})`,
            "number",
            "",
            'required min="0.01" step="0.01"',
          ),
          async (fd) => {
            await api("courier/jobs/", {
              method: "POST",
              body: {
                action: "bid",
                delivery: Number(id),
                amount: fd.get("amount"),
              },
            });
            closeModal();
            toast("Bid submitted.");
          },
          "Submit bid",
        );
        break;
      case "assign":
        await api(`delivery/${id}/track/`, {
          method: "POST",
          body: { action: "assign", agent: Number($(`#agent-${id}`).value) },
        });
        await courierPage();
        toast("Driver assigned.");
        break;
      case "delivery-status":
        if (el.dataset.status === "delivered") {
          formModal(
            "Complete this delivery",
            '<p>Confirm that the parcel reached the recipient. For cash orders, collect the exact order total.</p><label class="field"><span><input name="cash" type="checkbox"> Cash has been collected (cash orders only)</span></label>',
            async (fd) => {
              await api(`delivery/${id}/track/`, {
                method: "POST",
                body: {
                  action: "status",
                  status: "delivered",
                  cash_collected: fd.has("cash"),
                },
              });
              closeModal();
              stopGPS();
              await courierPage();
              toast("Delivery completed.");
            },
            "Confirm delivered",
          );
        } else {
          await api(`delivery/${id}/track/`, {
            method: "POST",
            body: { action: "status", status: el.dataset.status },
          });
          await courierPage();
        }
        break;
      case "track":
        await trackModal(id);
        break;
      case "accept-bid":
        await api(`delivery/${id}/track/`, {
          method: "POST",
          body: { action: "accept_bid", bid: Number(el.dataset.bid) },
        });
        await trackModal(id);
        break;
      case "apply-job":
        if (needAuth())
          formModal(
            "Put your best foot forward",
            textField("cover_letter", "Why are you a good fit?"),
            async (fd) => {
              await api("/hiring/api/applications/", {
                method: "POST",
                body: { job: Number(id), cover_letter: fd.get("cover_letter") },
              });
              closeModal();
              toast("Application submitted.");
            },
            "Submit application",
          );
        break;
      case "logout":
        if (watchId !== null) stopGPS();
        await api("/api/auth/logout/", { method: "POST", body: {} });
        state.user = { authenticated: false };
        await refreshCart();
        await route();
        toast("Signed out.");
        break;
      case "delete-address":
        await api(`addresses/${id}/`, { method: "DELETE" });
        await accountPage();
        break;
      case "read-note":
        await api("notifications/", {
          method: "POST",
          body: { id: Number(id) },
        });
        await accountPage();
        break;
      case "more-orders": {
        const next = el.dataset.next;
        el.remove();
        await ordersPage(next);
        break;
      }
    }
  } catch (err) {
    toast(err.message);
  } finally {
    el.disabled = false;
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.matches(".product-visual"))
    e.target.click();
});
document.addEventListener("click", (e) => {
  if (e.target.closest("[data-reload]")) route();
});
$("#close-modal").onclick = closeModal;
$("#modal").addEventListener("click", (e) => {
  if (e.target === $("#modal")) {
    const r = e.target.getBoundingClientRect();
    if (
      e.clientX < r.left ||
      e.clientX > r.right ||
      e.clientY < r.top ||
      e.clientY > r.bottom
    )
      closeModal();
  }
});
$("#theme-toggle").onclick = toggleTheme;
$("#account-button").onclick = () =>
  state.user.authenticated ? (location.hash = "account") : authModal();
$("#cart-button").onclick = () => cartModal().catch((e) => toast(e.message));
$("#post-job").onclick = jobForm;
$("#search-form").onsubmit = (e) => {
  e.preventDefault();
  location.hash = "shop";
  loadProducts().catch((e) => toast(e.message));
  $("#collection").scrollIntoView();
};
$("#apply-filter").onclick = () =>
  loadProducts().catch((e) => toast(e.message));
$("#load-more").onclick = () =>
  loadProducts(true).catch((e) => toast(e.message));
$("#explore").onclick = () => $("#collection").scrollIntoView();
$("#about-button").onclick = () =>
  showModal(
    "ABOUT IVANKA",
    '<h2>Good things, connected.</h2><p>Ivanka brings independent sellers, shoppers, couriers and careers into one place.</p><p>For an existing purchase, open your order and use Messages to contact the seller. Returns can be requested after delivery.</p><p class="fine-print">Before launch, the operator must add their legal business details, support contacts, privacy notice, delivery and returns terms. This development build contains illustrative demo products and exchange rates.</p>',
  );
$("#currency").onchange = async (e) => {
  state.currency = e.target.value;
  try {
    localStorage.setItem("ivanka-currency", state.currency);
  } catch (err) {}
  state.checkoutKey = null;
  try {
    await refreshCart();
    if ($("#modal").open) closeModal();
    await route();
    toast("Prices shown in " + state.currency);
  } catch (err) {
    toast(err.message);
  }
};
window.addEventListener("hashchange", route);
window.addEventListener("pagehide", () => {
  if (watchId !== null) navigator.geolocation.clearWatch(watchId);
});
(async () => {
  try {
    state.config = await api("config/");
    if (!state.config.currencies.some((c) => c.code === state.currency))
      state.currency = state.config.catalog_currency;
    $("#currency").innerHTML = state.config.currencies
      .map(
        (c) =>
          `<option value="${esc(c.code)}" ${c.code === state.currency ? "selected" : ""}>${esc(c.code)}</option>`,
      )
      .join("");
    $("#categories").innerHTML =
      '<button class="chip active" data-category="">All finds</button>' +
      state.config.categories
        .map(
          (c) =>
            `<button class="chip" data-category="${c.id}">${esc(c.name)}</button>`,
        )
        .join("");
    $$("[data-category]").forEach(
      (b) =>
        (b.onclick = () => {
          state.category = b.dataset.category;
          $$("[data-category]").forEach((x) =>
            x.classList.toggle("active", x === b),
          );
          loadProducts().catch((e) => toast(e.message));
        }),
    );
    state.user = await api("/api/me/");
    let localTheme = null;
    try {
      localTheme = localStorage.getItem("ivanka-theme");
    } catch (e) {}
    if (state.user.authenticated && !localTheme)
      document.documentElement.dataset.theme = state.user.theme;
    await refreshCart();
    await route();
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js").catch(() => {});
  } catch (e) {
    $("#products").innerHTML = empty("We couldn’t load the store", e.message);
    toast(e.message);
  }
})();
