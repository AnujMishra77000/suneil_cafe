const state = {
    profile: {
        name: "",
        phone: "",
        address: "",
        pincode: ""
    },
    cart_phone: "",
    idempotency_key: "",
    coupon: {
        code: "",
        discount_percent: 0,
        subtotal: "0.00",
        discount_amount: "0.00",
        total: "0.00"
    },
    cart: {
        items: [],
        total_items: 0,
        total_amount: "0.00"
    },
    serviceablePincodes: []
};

const formEl = document.getElementById("checkoutForm");
const nameInputEl = document.getElementById("nameInput");
const phoneInputEl = document.getElementById("phoneInput");
const addressInputEl = document.getElementById("addressInput");
const pincodeInputEl = document.getElementById("pincodeInput");
const couponInputEl = document.getElementById("couponInput");
const applyCouponBtnEl = document.getElementById("applyCouponBtn");
const clearCouponBtnEl = document.getElementById("clearCouponBtn");
const couponMsgEl = document.getElementById("couponMsg");
const submitBtnEl = document.getElementById("submitBtn");
const statusMsgEl = document.getElementById("statusMsg");
const previewItemsEl = document.getElementById("previewItems");
const totalItemsEl = document.getElementById("totalItems");
const summarySubtotalEl = document.getElementById("summarySubtotal");
const couponSummaryRowEl = document.getElementById("couponSummaryRow");
const couponSummaryLabelEl = document.getElementById("couponSummaryLabel");
const couponDiscountAmountEl = document.getElementById("couponDiscountAmount");
const totalAmountEl = document.getElementById("totalAmount");
const pincodeListEl = document.getElementById("pincodeList");
const profileBtnEl = document.getElementById("profileBtn");
const cartCountEl = document.getElementById("cartCount");

function setProfileButtonState(label = "Save Profile (Optional)", ready = false) {
    if (!profileBtnEl) return;
    profileBtnEl.setAttribute("title", label);
    profileBtnEl.setAttribute("aria-label", label);
    profileBtnEl.dataset.profileReady = ready ? "true" : "false";
}

function setStatus(message, type = "info") {
    statusMsgEl.textContent = message || "";
    statusMsgEl.classList.remove("ok", "error", "info");
    statusMsgEl.classList.add(type);
}

function setCouponMessage(message, type = "info") {
    if (!couponMsgEl) return;
    couponMsgEl.textContent = message || "";
    couponMsgEl.classList.remove("ok", "error", "info");
    if (message) {
        couponMsgEl.classList.add(type);
    }
}

function firstErrorMessage(payload) {
    if (!payload) return "Request failed";
    if (typeof payload === "string") return payload;
    if (Array.isArray(payload)) {
        for (const item of payload) {
            const nested = firstErrorMessage(item);
            if (nested) return nested;
        }
        return "Request failed";
    }
    if (typeof payload !== "object") return String(payload);

    if (typeof payload.error === "string" && payload.error.trim()) return payload.error.trim();
    if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail.trim();
    if (typeof payload.message === "string" && payload.message.trim()) return payload.message.trim();

    for (const key of Object.keys(payload)) {
        const nested = firstErrorMessage(payload[key]);
        if (nested) return nested;
    }
    return "Request failed";
}

function serviceablePincodeText() {
    if (!state.serviceablePincodes.length) return "";
    return state.serviceablePincodes.map((item) => item.code).join(", ");
}

function renderPincodeList() {
    if (!pincodeListEl) return;
    if (!state.serviceablePincodes.length) {
        pincodeListEl.textContent = "No serviceable pincode list available right now.";
        return;
    }
    pincodeListEl.textContent = `We currently serve: ${serviceablePincodeText()}`;
}

function readProfile() {
    const raw = localStorage.getItem("thathwamasi_profile");
    if (!raw) return;
    try {
        const profile = JSON.parse(raw);
        state.profile = {
            name: profile.name || "",
            phone: profile.phone || "",
            address: profile.address || "",
            pincode: profile.pincode || ""
        };
    } catch (err) {
        console.error(err);
    }

    const checkoutPhone = localStorage.getItem("thathwamasi_checkout_phone");
    if (checkoutPhone && !state.profile.phone) {
        state.profile.phone = checkoutPhone;
    }

    if (state.profile.name && state.profile.phone) {
        setProfileButtonState(`Saved profile for ${state.profile.name}`, true);
    }
}

function readStoredCoupon() {
    const stored = (localStorage.getItem("thathwamasi_checkout_coupon_code") || "").trim();
    if (stored && couponInputEl) {
        couponInputEl.value = stored;
    }
    return stored;
}

function persistCoupon() {
    if (state.coupon.code) {
        localStorage.setItem("thathwamasi_checkout_coupon_code", state.coupon.code);
    } else {
        localStorage.removeItem("thathwamasi_checkout_coupon_code");
    }
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

function writeProfile() {
    localStorage.setItem("thathwamasi_profile", JSON.stringify(state.profile));
    if (state.profile.phone) {
        localStorage.setItem("thathwamasi_checkout_phone", state.profile.phone);
    }
    if (state.profile.name && state.profile.phone) {
        setProfileButtonState(`Saved profile for ${state.profile.name}`, true);
    }
}

function newIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
        return window.crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
        const rand = Math.random() * 16 | 0;
        const value = char === "x" ? rand : (rand & 0x3 | 0x8);
        return value.toString(16);
    });
}

function loadIdempotencyKey() {
    let key = localStorage.getItem("thathwamasi_checkout_idempotency_key");
    if (!key) {
        key = newIdempotencyKey();
        localStorage.setItem("thathwamasi_checkout_idempotency_key", key);
    }
    state.idempotency_key = key;
}

function rotateIdempotencyKey() {
    const key = newIdempotencyKey();
    localStorage.setItem("thathwamasi_checkout_idempotency_key", key);
    state.idempotency_key = key;
}

function fillForm() {
    nameInputEl.value = state.profile.name;
    phoneInputEl.value = state.profile.phone;
    addressInputEl.value = state.profile.address;
    pincodeInputEl.value = state.profile.pincode;
}

async function refreshCartCount() {
    if (!cartCountEl) return;
    const cartPhone = localStorage.getItem("thathwamasi_cart_phone") || state.cart_phone || "";
    if (!cartPhone) {
        cartCountEl.textContent = "0";
        return;
    }
    try {
        const cart = await apiGet(`/api/cart/view/?phone=${encodeURIComponent(cartPhone)}`);
        const count = Number(cart.total_items || 0);
        cartCountEl.textContent = Number.isFinite(count) ? String(count) : "0";
    } catch {
        cartCountEl.textContent = "0";
    }
}

function saveProfileFromForm() {
    state.profile.name = nameInputEl.value.trim();
    state.profile.phone = phoneInputEl.value.trim();
    state.profile.address = addressInputEl.value.trim();
    state.profile.pincode = pincodeInputEl.value.trim();

    if (!state.profile.name || !state.profile.phone) {
        setStatus("Add at least name and phone before saving profile.", "info");
        return false;
    }

    writeProfile();
    setStatus("Profile saved for faster checkout.", "ok");
    return true;
}

function openProfilePage() {
    state.profile.name = nameInputEl.value.trim();
    state.profile.phone = phoneInputEl.value.trim();
    state.profile.address = addressInputEl.value.trim();
    state.profile.pincode = pincodeInputEl.value.trim();

    if (state.profile.name || state.profile.phone || state.profile.address || state.profile.pincode) {
        writeProfile();
    }

    window.location.href = "/profile/";
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
    if (!res.ok) throw new Error(firstErrorMessage(data));
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
    if (!res.ok) throw new Error(firstErrorMessage(data));
    return data;
}

async function loadServiceablePincodes() {
    try {
        const payload = await apiGet("/api/orders/serviceable-pincodes/");
        state.serviceablePincodes = payload.pincodes || [];
    } catch (err) {
        state.serviceablePincodes = [];
    }
    renderPincodeList();
}

async function loadCart() {
    const cartPhone = getOrCreateCartPhone();
    const payload = await apiGet(`/api/cart/view/?phone=${encodeURIComponent(cartPhone)}`);
    state.cart = {
        items: payload.items || [],
        total_items: payload.total_items || 0,
        total_amount: payload.total_amount || "0.00"
    };
}

function extractPincodeFromAddress(address) {
    const match = String(address || "").match(/\b(\d{6})\b/);
    return match ? match[1] : "";
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function toAmount(value) {
    const numeric = Number(value || 0);
    return Number.isFinite(numeric) ? numeric : 0;
}

function lineTotal(item) {
    const numeric = Number(item.line_total);
    if (Number.isFinite(numeric)) {
        return numeric.toFixed(2);
    }
    const qty = Number(item.quantity || 0);
    const price = Number(item.price || 0);
    return (qty * price).toFixed(2);
}

function resetCouponState({ clearInput = false } = {}) {
    state.coupon.code = "";
    state.coupon.discount_percent = 0;
    state.coupon.discount_amount = "0.00";
    state.coupon.subtotal = "0.00";
    state.coupon.total = String(state.cart.total_amount || "0.00");
    persistCoupon();
    if (clearInput && couponInputEl) {
        couponInputEl.value = "";
    }
}

function recalcCouponSummary() {
    const subtotal = toAmount(state.cart.total_amount);
    let discountAmount = 0;
    if (state.coupon.code && state.coupon.discount_percent > 0) {
        discountAmount = subtotal * (state.coupon.discount_percent / 100);
    }
    const total = Math.max(subtotal - discountAmount, 0);
    state.coupon.subtotal = subtotal.toFixed(2);
    state.coupon.discount_amount = discountAmount.toFixed(2);
    state.coupon.total = total.toFixed(2);
}

function renderCouponSummary() {
    recalcCouponSummary();
    summarySubtotalEl.textContent = `Rs ${state.coupon.subtotal}`;
    const hasCoupon = Boolean(state.coupon.code && state.coupon.discount_percent > 0);
    couponSummaryRowEl.hidden = !hasCoupon;
    if (hasCoupon) {
        couponSummaryLabelEl.textContent = `${state.coupon.code} (-${state.coupon.discount_percent}%)`;
        couponDiscountAmountEl.textContent = `-Rs ${state.coupon.discount_amount}`;
    }
    totalAmountEl.textContent = `Rs ${state.coupon.total}`;
}

function renderPreview() {
    if (!state.cart.items.length) {
        previewItemsEl.innerHTML = `<div class="preview-empty">Cart is empty right now.</div>`;
    } else {
        previewItemsEl.innerHTML = state.cart.items.map((item) => {
            const quantity = Number(item.quantity) || 0;
            const price = Number(item.price || 0).toFixed(2);
            return `
                <article class="preview-item">
                    <div class="preview-copy">
                        <strong class="preview-name">${escapeHtml(item.product_name)}</strong>
                        <span class="preview-meta">Unit Price: Rs ${escapeHtml(price)}</span>
                    </div>
                    <div class="preview-qty-wrap">
                        <span class="preview-qty">Qty ${escapeHtml(quantity)}</span>
                    </div>
                    <div class="preview-amounts">
                        <span class="preview-amount-label">Line Total</span>
                        <strong class="preview-price">Rs ${lineTotal(item)}</strong>
                    </div>
                </article>
            `;
        }).join("");
    }
    totalItemsEl.textContent = String(state.cart.total_items || 0);
    renderCouponSummary();
}

async function lookupByPhone() {
    const phone = phoneInputEl.value.trim();
    if (!phone || phone.length < 10) return;

    try {
        const payload = await apiGet(`/api/orders/history-by-phone/?phone=${encodeURIComponent(phone)}`);
        if (!payload.exists) {
            return;
        }

        const customer = payload.customer || {};

        if (!nameInputEl.value.trim() && customer.name) {
            nameInputEl.value = customer.name;
        }
        if (!addressInputEl.value.trim() && customer.address) {
            addressInputEl.value = customer.address;
            setStatus("Previous address loaded. Confirm or edit before placing order.", "info");
        }
        if (!pincodeInputEl.value.trim() && customer.address) {
            const detected = extractPincodeFromAddress(customer.address);
            if (detected) {
                pincodeInputEl.value = detected;
            }
        }
    } catch (err) {
        setStatus(err.message || "Unable to fetch previous details.", "error");
    }
}

async function applyCoupon() {
    const code = (couponInputEl.value || "").trim();
    if (!code) {
        resetCouponState();
        renderCouponSummary();
        setCouponMessage("Enter a coupon code.", "error");
        return;
    }

    applyCouponBtnEl.disabled = true;
    applyCouponBtnEl.textContent = "Applying...";
    clearCouponBtnEl.disabled = true;

    try {
        const payload = await apiPost("/api/orders/coupons/validate/", { coupon_code: code });
        state.coupon.code = payload.coupon_code || code.toUpperCase();
        state.coupon.discount_percent = Number(payload.discount_percent || 0);
        persistCoupon();
        renderCouponSummary();
        setCouponMessage(`${state.coupon.code} applied for ${state.coupon.discount_percent}% off.`, "ok");
    } catch (err) {
        resetCouponState();
        renderCouponSummary();
        setCouponMessage(err.message || "Unable to apply coupon.", "error");
    } finally {
        applyCouponBtnEl.disabled = false;
        applyCouponBtnEl.textContent = "Apply";
        clearCouponBtnEl.disabled = false;
    }
}

function clearCoupon() {
    resetCouponState({ clearInput: true });
    renderCouponSummary();
    setCouponMessage("Coupon removed.", "info");
}

async function restoreCoupon() {
    const stored = readStoredCoupon();
    if (!stored) {
        resetCouponState();
        renderCouponSummary();
        return;
    }
    await applyCoupon();
}

async function submitOrder(event) {
    event.preventDefault();

    state.profile.name = nameInputEl.value.trim();
    state.profile.phone = phoneInputEl.value.trim();
    state.profile.address = addressInputEl.value.trim();
    state.profile.pincode = pincodeInputEl.value.trim();
    writeProfile();

    if (!state.profile.name || !state.profile.phone || !state.profile.address || !state.profile.pincode) {
        setStatus("Please fill all details.", "error");
        return;
    }
    if (!/^\d{6}$/.test(state.profile.pincode)) {
        const served = serviceablePincodeText();
        const extra = served ? ` We serve only these pincodes: ${served}.` : "";
        setStatus(`Please enter a valid 6-digit pincode.${extra}`, "error");
        return;
    }
    if (!state.cart.items.length) {
        setStatus("Cart is empty.", "error");
        return;
    }

    submitBtnEl.disabled = true;
    submitBtnEl.textContent = "Placing...";
    setStatus("", "info");

    try {
        const result = await apiPost("/api/cart/place/", {
            phone: state.profile.phone,
            customer_name: state.profile.name,
            whatsapp_no: state.profile.phone,
            address: state.profile.address,
            pincode: state.profile.pincode,
            cart_phone: state.cart_phone,
            coupon_code: state.coupon.code,
            idempotency_key: state.idempotency_key
        });
        setStatus(`Order placed successfully. Order ID: ${result.order_id}`, "ok");
        localStorage.setItem("thathwamasi_checkout_phone", state.profile.phone);
        if (state.cart_phone !== state.profile.phone) {
            localStorage.setItem("thathwamasi_cart_phone", state.profile.phone);
        }
        localStorage.removeItem("thathwamasi_checkout_coupon_code");
        rotateIdempotencyKey();
        localStorage.setItem("thathwamasi_last_order_id", String(result.order_id || ""));
        setTimeout(() => {
            const orderId = encodeURIComponent(result.order_id || "");
            window.location.href = `/order-success/?order_id=${orderId}`;
        }, 320);
    } catch (err) {
        const message = err.message || "Order failed";
        if (/coupon/i.test(message)) {
            setCouponMessage(message, "error");
        }
        if (/pincode|deliver|serviceable/i.test(message)) {
            const served = serviceablePincodeText();
            const extra = served ? ` We serve only these pincodes: ${served}.` : "";
            setStatus(`${message}${extra}`, "error");
        } else {
            setStatus(message, "error");
        }
    } finally {
        submitBtnEl.disabled = false;
        submitBtnEl.textContent = "Place Order";
    }
}

async function bootstrap() {
    setProfileButtonState();
    readProfile();
    loadIdempotencyKey();
    fillForm();
    await Promise.all([loadServiceablePincodes(), loadCart(), refreshCartCount()]);
    renderPreview();
    await restoreCoupon();
}

formEl.addEventListener("submit", submitOrder);
if (profileBtnEl) {
    profileBtnEl.addEventListener("click", openProfilePage);
}
phoneInputEl.addEventListener("blur", lookupByPhone);
applyCouponBtnEl.addEventListener("click", applyCoupon);
clearCouponBtnEl.addEventListener("click", clearCoupon);
if (couponInputEl) {
    couponInputEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            applyCoupon();
        }
    });
}

bootstrap().catch((err) => {
    setStatus(err.message || "Unable to load checkout.", "error");
});
