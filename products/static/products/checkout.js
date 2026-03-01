const state = {
    profile: {
        name: "",
        phone: "",
        address: "",
        pincode: ""
    },
    cart_phone: "",
    idempotency_key: "",
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
const submitBtnEl = document.getElementById("submitBtn");
const statusMsgEl = document.getElementById("statusMsg");
const previewItemsEl = document.getElementById("previewItems");
const totalItemsEl = document.getElementById("totalItems");
const totalAmountEl = document.getElementById("totalAmount");
const pincodeListEl = document.getElementById("pincodeList");

function setStatus(message, type = "info") {
    statusMsgEl.textContent = message || "";
    statusMsgEl.classList.remove("ok", "error", "info");
    statusMsgEl.classList.add(type);
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

function lineTotal(item) {
    const numeric = Number(item.line_total);
    if (Number.isFinite(numeric)) {
        return numeric.toFixed(2);
    }
    const qty = Number(item.quantity || 0);
    const price = Number(item.price || 0);
    return (qty * price).toFixed(2);
}

function renderPreview() {
    if (!state.cart.items.length) {
        previewItemsEl.innerHTML = `<div class="preview-empty">Cart is empty right now.</div>`;
    } else {
        previewItemsEl.innerHTML = state.cart.items.map((item) => `
            <article class="preview-item">
                <div class="preview-copy">
                    <strong class="preview-name">${escapeHtml(item.product_name)}</strong>
                    <span class="preview-meta">Quantity: ${escapeHtml(item.quantity)} item${Number(item.quantity) === 1 ? "" : "s"}</span>
                </div>
                <strong class="preview-price">Rs ${lineTotal(item)}</strong>
            </article>
        `).join("");
    }
    totalItemsEl.textContent = String(state.cart.total_items || 0);
    totalAmountEl.textContent = `Rs ${state.cart.total_amount || "0.00"}`;
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
            idempotency_key: state.idempotency_key
        });
        setStatus(`Order placed successfully. Order ID: ${result.order_id}`, "ok");
        localStorage.setItem("thathwamasi_checkout_phone", state.profile.phone);
        if (state.cart_phone !== state.profile.phone) {
            localStorage.setItem("thathwamasi_cart_phone", state.profile.phone);
        }
        rotateIdempotencyKey();
        localStorage.setItem("thathwamasi_last_order_id", String(result.order_id || ""));
        setTimeout(() => {
            const orderId = encodeURIComponent(result.order_id || "");
            window.location.href = `/order-success/?order_id=${orderId}`;
        }, 320);
    } catch (err) {
        const message = err.message || "Order failed";
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
    readProfile();
    getOrCreateCartPhone();
    loadIdempotencyKey();
    fillForm();
    await loadServiceablePincodes();
    try {
        await loadCart();
    } catch (err) {
        setStatus(err.message || "Unable to load cart.", "error");
    }
    renderPreview();
    if (state.profile.phone) {
        await lookupByPhone();
    }
}

formEl.addEventListener("submit", submitOrder);
phoneInputEl.addEventListener("blur", lookupByPhone);
bootstrap();
