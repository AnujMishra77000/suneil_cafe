const OWNER_PHONE = "7700010890";
const MAX_QTY = 25;

const state = {
    profile: {
        name: "",
        phone: "",
        whatsapp_no: ""
    },
    cart_phone: ""
};

const productId = Number(document.body.dataset.productId || 0);
const buyCardEl = document.getElementById("buyCard");
const profileBtnEl = document.getElementById("profileBtn");
const cartCountEl = document.getElementById("cartCount");

function normalizeQty(value) {
    const qty = Number(value || 1);
    if (!Number.isFinite(qty) || qty < 1) return 1;
    return Math.min(Math.floor(qty), MAX_QTY);
}

function generateCartPhone() {
    const base = Math.floor(1000000000 + Math.random() * 9000000000);
    return `9${String(base).slice(0, 9)}`;
}

function readProfile() {
    const raw = localStorage.getItem("thathwamasi_profile");
    if (!raw) return;
    try {
        const profile = JSON.parse(raw);
        if (profile.name && profile.phone && profile.whatsapp_no) {
            state.profile = profile;
            if (profileBtnEl) profileBtnEl.textContent = `Deliver to ${profile.name}`;
        }
    } catch (e) {
        console.error(e);
    }
}

function askProfile() {
    const name = prompt("Enter your name");
    if (!name) return false;
    const phone = prompt("Enter phone number");
    if (!phone) return false;
    const whatsapp = prompt("Enter WhatsApp number");
    if (!whatsapp) return false;

    state.profile = {
        name: name.trim(),
        phone: phone.trim(),
        whatsapp_no: whatsapp.trim()
    };
    localStorage.setItem("thathwamasi_profile", JSON.stringify(state.profile));
    if (profileBtnEl) profileBtnEl.textContent = `Deliver to ${state.profile.name}`;
    return true;
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

async function apiGet(url) {
    const res = await fetch(url);
    const raw = await res.text();
    let data;
    try {
        data = raw ? JSON.parse(raw) : {};
    } catch {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) throw new Error(data.error || data.detail || `Request failed (${res.status})`);
    return data;
}

async function apiPost(url, payload) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const raw = await res.text();
    let data;
    try {
        data = raw ? JSON.parse(raw) : {};
    } catch {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) throw new Error(data.error || data.detail || `Request failed (${res.status})`);
    return data;
}

async function refreshCartCount() {
    const cartPhone = getOrCreateCartPhone();
    if (!cartPhone) {
        if (cartCountEl) cartCountEl.textContent = "0";
        return;
    }
    try {
        const cart = await apiGet(`/api/cart/view/?phone=${encodeURIComponent(cartPhone)}`);
        const count = Number(cart.total_items || 0);
        if (cartCountEl) cartCountEl.textContent = Number.isFinite(count) ? String(count) : "0";
    } catch {
        if (cartCountEl) cartCountEl.textContent = "0";
    }
}

function renderProduct(product) {
    const image = product.image ? `<img src="${product.image}" alt="${product.name}" loading="lazy" decoding="async" />` : "";
    const description = (product.description || "").trim() || "Fresh and tasty product from Thathwamasi Bakery Cafe.";
    const out = product.is_available ? "" : `<div class="out">Out of Stock</div>`;

    buyCardEl.innerHTML = `
        <div class="product" data-available="${product.is_available ? "1" : "0"}">
            <div>${image}</div>
            <div>
                <h1>${product.name}</h1>
                <div class="meta">${product.category_name || ""}</div>
                <div class="price">Rs ${product.price}</div>
                <p>${description}</p>
                <div class="qty-row">
                    <button id="qtyDec" type="button">-</button>
                    <input id="qtyInput" class="qty-input" type="number" min="1" max="${MAX_QTY}" value="1" />
                    <button id="qtyInc" type="button">+</button>
                </div>
                <button id="proceedBtn" class="proceed-btn" type="button">Proceed to Billing</button>
                ${out}
            </div>
        </div>
    `;

    const qtyInput = document.getElementById("qtyInput");
    const qtyDec = document.getElementById("qtyDec");
    const qtyInc = document.getElementById("qtyInc");
    const proceedBtn = document.getElementById("proceedBtn");

    qtyDec.addEventListener("click", () => {
        qtyInput.value = String(Math.max(1, normalizeQty(qtyInput.value) - 1));
    });

    qtyInc.addEventListener("click", () => {
        qtyInput.value = String(Math.min(MAX_QTY, normalizeQty(qtyInput.value) + 1));
    });

    qtyInput.addEventListener("change", () => {
        qtyInput.value = String(normalizeQty(qtyInput.value));
    });

    proceedBtn.addEventListener("click", async () => {
        if (product.is_available !== true) {
            alert(`${product.name} is out of stock. Please contact owner: ${OWNER_PHONE}`);
            return;
        }

        const qty = normalizeQty(qtyInput.value);
        proceedBtn.disabled = true;
        proceedBtn.textContent = "Please wait...";
        try {
            await apiPost("/api/cart/add/", {
                phone: getOrCreateCartPhone(),
                product_id: product.id,
                quantity: qty,
            });
            await refreshCartCount();
            window.location.href = "/billing/";
        } catch (err) {
            alert(err.message || "Unable to proceed");
            proceedBtn.disabled = false;
            proceedBtn.textContent = "Proceed to Billing";
        }
    });
}

async function bootstrap() {
    readProfile();
    getOrCreateCartPhone();
    await refreshCartCount();

    if (!productId) {
        buyCardEl.innerHTML = '<div class="state">Invalid product.</div>';
        return;
    }

    try {
        const product = await apiGet(`/api/products/${productId}/`);
        renderProduct(product);
    } catch (err) {
        buyCardEl.innerHTML = `<div class="state">${err.message || "Unable to load product."}</div>`;
    }
}

if (profileBtnEl) profileBtnEl.addEventListener("click", askProfile);

bootstrap();
