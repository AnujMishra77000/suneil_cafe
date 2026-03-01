const state = {
    cart_phone: "",
    cart: {
        items: [],
        total_items: 0,
        total_amount: "0.00"
    },
    history_orders: []
};

const profileBtnEl = document.getElementById("profileBtn");
const cartListEl = document.getElementById("cartList");
const itemCountEl = document.getElementById("itemCount");
const summaryItemsEl = document.getElementById("summaryItems");
const summarySubtotalEl = document.getElementById("summarySubtotal");
const summaryTotalEl = document.getElementById("summaryTotal");
const placeOrderBtnEl = document.getElementById("placeOrderBtn");
const statusMsgEl = document.getElementById("statusMsg");
const historyBtnEl = document.getElementById("historyBtn");
const historyPanelEl = document.getElementById("historyPanel");
const qtyTimers = {};
let historyLoaded = false;

function rememberContinueShoppingUrl() {
    const fallback = "/bakery/";
    const raw = document.referrer || "";
    if (!raw) {
        if (!localStorage.getItem("thathwamasi_continue_shopping_url")) {
            localStorage.setItem("thathwamasi_continue_shopping_url", fallback);
        }
        return;
    }

    try {
        const ref = new URL(raw, window.location.origin);
        if (ref.origin !== window.location.origin) {
            return;
        }
        const path = `${ref.pathname}${ref.search}`;
        if (/^\/(billing|checkout|order-success)\/?$/i.test(ref.pathname)) {
            return;
        }
        localStorage.setItem("thathwamasi_continue_shopping_url", path || fallback);
    } catch {
        // Ignore invalid referrers.
    }
}

function readProfile() {
    const checkoutPhone = localStorage.getItem("thathwamasi_checkout_phone");
    if (checkoutPhone) {
        profileBtnEl.textContent = `Using phone ${checkoutPhone}`;
    }
}

function askPhoneForHistory() {
    const phone = prompt("Enter phone number");
    if (!phone) return false;
    localStorage.setItem("thathwamasi_checkout_phone", phone.trim());
    profileBtnEl.textContent = `Using phone ${phone.trim()}`;
    historyLoaded = false;
    setupHistoryAccess(true).catch(() => {});
    return true;
}

function generateCartPhone() {
    const base = Math.floor(1000000000 + Math.random() * 9000000000);
    return `9${String(base).slice(0, 9)}`;
}

function getOrCreateCartPhone() {
    let cartPhone = localStorage.getItem("thathwamasi_cart_phone");
    if (!cartPhone) {
        cartPhone = generateCartPhone();
        localStorage.setItem("thathwamasi_cart_phone", cartPhone);
    }
    state.cart_phone = cartPhone;
    return cartPhone;
}

function resolveApiError(data, fallback = "Request failed") {
    if (!data || typeof data !== "object") return fallback;
    if (typeof data.error === "string" && data.error.trim()) return data.error;
    if (typeof data.detail === "string" && data.detail.trim()) return data.detail;

    const keys = Object.keys(data);
    for (const key of keys) {
        const value = data[key];
        if (typeof value === "string" && value.trim()) return value;
        if (Array.isArray(value) && value.length) {
            const first = value[0];
            if (typeof first === "string" && first.trim()) return first;
        }
        if (value && typeof value === "object") {
            const nested = Object.values(value)[0];
            if (typeof nested === "string" && nested.trim()) return nested;
            if (Array.isArray(nested) && nested.length && typeof nested[0] === "string") {
                return nested[0];
            }
        }
    }

    return fallback;
}

async function apiGet(url) {
    const res = await fetch(url);
    const raw = await res.text();
    let data;
    try {
        data = raw ? JSON.parse(raw) : {};
    } catch (err) {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) throw new Error(resolveApiError(data, `Request failed (${res.status})`));
    return data;
}

async function apiPost(url, payload) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const raw = await res.text();
    let data;
    try {
        data = raw ? JSON.parse(raw) : {};
    } catch (err) {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) throw new Error(resolveApiError(data, `Request failed (${res.status})`));
    return data;
}

function toAmount(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatDateTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString();
}

function recalcCart() {
    const totalItems = state.cart.items.reduce((acc, item) => acc + Number(item.quantity || 0), 0);
    const totalAmount = state.cart.items.reduce(
        (acc, item) => acc + toAmount(item.price) * Number(item.quantity || 0),
        0
    );
    state.cart.total_items = totalItems;
    state.cart.total_amount = totalAmount.toFixed(2);
    state.cart.items = state.cart.items.map((item) => ({
        ...item,
        line_total: (toAmount(item.price) * Number(item.quantity || 0)).toFixed(2),
    }));
}

function applyLocalQty(productId, quantity) {
    state.cart.items = state.cart.items.map((item) =>
        Number(item.product_id) === Number(productId)
            ? { ...item, quantity: Math.max(1, quantity) }
            : item
    );
    recalcCart();
}

function applyLocalRemove(productId) {
    state.cart.items = state.cart.items.filter((item) => Number(item.product_id) !== Number(productId));
    recalcCart();
}

function renderSummary() {
    itemCountEl.textContent = `${state.cart.total_items || 0} items`;
    summaryItemsEl.textContent = String(state.cart.total_items || 0);
    summarySubtotalEl.textContent = `Rs ${state.cart.total_amount || "0.00"}`;
    summaryTotalEl.textContent = `Rs ${state.cart.total_amount || "0.00"}`;
}

function rowTemplate(item) {
    const image = item.image ? `<img src="${item.image}" alt="${item.product_name}" loading="lazy" decoding="async" />` : "";
    return `
        <article class="item-row" data-product-id="${item.product_id}">
            <div class="thumb">${image}</div>
            <div class="item-main">
                <h4>${item.product_name}</h4>
                <p>Price: Rs ${item.price}</p>
                <div class="qty-row">
                    <button data-action="dec">-</button>
                    <input class="qty-input" type="number" min="1" max="99" value="${item.quantity}" />
                    <button data-action="inc">+</button>
                </div>
            </div>
            <div class="actions">
                <div class="item-total">Rs ${item.line_total}</div>
                <button class="update-btn" data-action="update">Update</button>
                <button class="remove-btn" data-action="remove">Remove</button>
            </div>
        </article>
    `;
}

function renderCart() {
    if (!state.cart.items || !state.cart.items.length) {
        cartListEl.innerHTML = `<div class="empty">Your cart is empty. Add products from Bakery or Snacks.</div>`;
        renderSummary();
        return;
    }
    cartListEl.innerHTML = state.cart.items.map(rowTemplate).join("");
    renderSummary();
}

function renderOrderHistory() {
    if (!historyPanelEl) return;
    if (!state.history_orders.length) {
        historyPanelEl.innerHTML = "";
        return;
    }

    historyPanelEl.innerHTML = state.history_orders.map((order) => {
        const feedback = order.feedback || null;
        const message = feedback?.message || "";
        const ratingValue = feedback?.rating ? String(feedback.rating) : "";
        const feedbackLabel = feedback ? "Update Feedback" : "Submit Feedback";
        const updatedText = feedback?.updated_at ? `Updated: ${formatDateTime(feedback.updated_at)}` : "";

        const itemsHtml = Array.isArray(order.items)
            ? order.items.map((item) => `
                <div class="history-item-line">
                    <span>${escapeHtml(item.product_name)}</span>
                    <span>${escapeHtml(item.quantity)} x Rs ${escapeHtml(item.price)}</span>
                </div>
            `).join("")
            : "";

        return `
            <article class="history-item history-card" data-order-id="${order.id}">
                <div class="history-head">
                    <strong>Order #${order.id} (${escapeHtml(order.status)})</strong>
                    <strong>Rs ${escapeHtml(order.total_price)}</strong>
                </div>
                <div class="history-items-wrap">${itemsHtml}</div>
                <form class="feedback-form" data-order-id="${order.id}">
                    <div class="feedback-row">
                        <label for="rating-${order.id}">Rating</label>
                        <select id="rating-${order.id}" name="rating">
                            <option value="">Select</option>
                            <option value="1" ${ratingValue === "1" ? "selected" : ""}>1</option>
                            <option value="2" ${ratingValue === "2" ? "selected" : ""}>2</option>
                            <option value="3" ${ratingValue === "3" ? "selected" : ""}>3</option>
                            <option value="4" ${ratingValue === "4" ? "selected" : ""}>4</option>
                            <option value="5" ${ratingValue === "5" ? "selected" : ""}>5</option>
                        </select>
                    </div>
                    <textarea name="message" rows="3" placeholder="Write your feedback for this order" required>${escapeHtml(message)}</textarea>
                    <div class="feedback-actions">
                        <button type="submit" class="feedback-submit-btn">${feedbackLabel}</button>
                        <span class="feedback-updated">${escapeHtml(updatedText)}</span>
                    </div>
                    <p class="feedback-inline-status"></p>
                </form>
            </article>
        `;
    }).join("");
}

async function loadCart() {
    const cartPhone = getOrCreateCartPhone();
    if (!cartPhone) {
        state.cart = { items: [], total_items: 0, total_amount: "0.00" };
        renderCart();
        return;
    }
    const payload = await apiGet(`/api/cart/view/?phone=${encodeURIComponent(cartPhone)}`);
    state.cart = {
        items: payload.items || [],
        total_items: payload.total_items || 0,
        total_amount: payload.total_amount || "0.00"
    };
    recalcCart();
    renderCart();
}

function getQtyFromRow(row) {
    const input = row.querySelector(".qty-input");
    const value = Number(input.value || 1);
    if (!Number.isFinite(value) || value < 1) return 1;
    return Math.min(value, 99);
}

async function updateCartItem(productId, quantity) {
    const cartPhone = getOrCreateCartPhone();
    await apiPost("/api/cart/item/update/", {
        phone: cartPhone,
        product_id: productId,
        quantity
    });
}

async function removeCartItem(productId) {
    const cartPhone = getOrCreateCartPhone();
    await apiPost("/api/cart/item/remove/", {
        phone: cartPhone,
        product_id: productId
    });
}

async function onCartAction(event) {
    const button = event.target.closest("button");
    if (!button) return;
    const row = event.target.closest("[data-product-id]");
    const productId = Number(row?.dataset.productId);
    const action = button.dataset.action;
    if (!action || !productId) return;

    if (action === "inc" || action === "dec") {
        const input = row.querySelector(".qty-input");
        const current = getQtyFromRow(row);
        const next = action === "inc" ? current + 1 : current - 1;
        const safeNext = Math.min(Math.max(next, 1), 99);
        input.value = safeNext;
        applyLocalQty(productId, safeNext);
        renderCart();

        clearTimeout(qtyTimers[productId]);
        qtyTimers[productId] = setTimeout(async () => {
            try {
                await updateCartItem(productId, safeNext);
            } catch (err) {
                statusMsgEl.textContent = err.message || "Unable to sync cart.";
                await loadCart();
            }
        }, 180);
        return;
    }

    try {
        if (action === "update") {
            const qty = getQtyFromRow(row);
            applyLocalQty(productId, qty);
            renderCart();
            await updateCartItem(productId, qty);
            statusMsgEl.textContent = "Cart updated.";
        }
        if (action === "remove") {
            applyLocalRemove(productId);
            renderCart();
            await removeCartItem(productId);
            statusMsgEl.textContent = "Item removed from cart.";
        }
    } catch (err) {
        statusMsgEl.textContent = err.message || "Action failed";
        await loadCart();
    }
}

async function proceedToCheckout() {
    if (!state.cart.items.length) {
        statusMsgEl.textContent = "Your cart is empty.";
        return;
    }
    window.location.href = "/checkout/";
}

async function submitOrderFeedback(formEl) {
    const phone = (localStorage.getItem("thathwamasi_checkout_phone") || "").trim();
    if (!phone) {
        throw new Error("Please save your phone number first.");
    }

    const orderId = Number(formEl.dataset.orderId);
    const messageEl = formEl.querySelector("textarea[name='message']");
    const ratingEl = formEl.querySelector("select[name='rating']");
    const message = (messageEl?.value || "").trim();
    const ratingValue = (ratingEl?.value || "").trim();

    if (!orderId) {
        throw new Error("Invalid order selected for feedback.");
    }
    if (message.length < 3) {
        throw new Error("Please enter at least 3 characters in feedback.");
    }

    const payload = {
        order_id: orderId,
        phone,
        message,
        rating: ratingValue ? Number(ratingValue) : null,
    };

    return apiPost("/api/orders/feedback/", payload);
}

async function onHistorySubmit(event) {
    const formEl = event.target.closest(".feedback-form");
    if (!formEl) return;
    event.preventDefault();

    const statusEl = formEl.querySelector(".feedback-inline-status");
    const buttonEl = formEl.querySelector(".feedback-submit-btn");
    if (statusEl) statusEl.textContent = "";
    if (buttonEl) buttonEl.disabled = true;

    try {
        await submitOrderFeedback(formEl);
        if (statusEl) {
            statusEl.textContent = "Feedback saved.";
            statusEl.classList.add("ok");
        }
        statusMsgEl.textContent = "Feedback saved successfully.";
        await setupHistoryAccess(true);
        if (historyPanelEl) historyPanelEl.classList.remove("hidden");
    } catch (err) {
        if (statusEl) {
            statusEl.textContent = err.message || "Unable to save feedback.";
            statusEl.classList.remove("ok");
        }
        statusMsgEl.textContent = err.message || "Unable to save feedback.";
    } finally {
        if (buttonEl) buttonEl.disabled = false;
    }
}

async function bootstrap() {
    readProfile();
    rememberContinueShoppingUrl();
    await loadCart();
    await setupHistoryAccess();
}

profileBtnEl.addEventListener("click", askPhoneForHistory);
cartListEl.addEventListener("click", onCartAction);
placeOrderBtnEl.addEventListener("click", proceedToCheckout);

if (historyBtnEl && historyPanelEl) {
    historyBtnEl.addEventListener("click", async () => {
        if (!historyLoaded) {
            await setupHistoryAccess(true);
        }
        historyPanelEl.classList.toggle("hidden");
    });
    historyPanelEl.addEventListener("submit", onHistorySubmit);
}

bootstrap();

async function setupHistoryAccess(forceRender = false) {
    if (!historyBtnEl || !historyPanelEl) return;

    const phone = (localStorage.getItem("thathwamasi_checkout_phone") || "").trim();
    if (!phone) {
        historyBtnEl.classList.add("hidden");
        historyPanelEl.classList.add("hidden");
        state.history_orders = [];
        return;
    }

    try {
        const payload = await apiGet(`/api/orders/history-by-phone/?phone=${encodeURIComponent(phone)}`);
        const orders = Array.isArray(payload.orders) ? payload.orders : [];
        const filtered = orders.filter((order) => {
            const status = String(order.status || "").toLowerCase();
            return status.includes("placed") || status.includes("confirm");
        }).slice(0, 8);

        if (!filtered.length) {
            historyBtnEl.classList.add("hidden");
            historyPanelEl.classList.add("hidden");
            state.history_orders = [];
            return;
        }

        state.history_orders = filtered;
        historyBtnEl.classList.remove("hidden");
        if (forceRender || !historyLoaded) {
            renderOrderHistory();
        }
        historyLoaded = true;
    } catch (err) {
        historyBtnEl.classList.add("hidden");
        historyPanelEl.classList.add("hidden");
        state.history_orders = [];
    }
}
