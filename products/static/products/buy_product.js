const OWNER_PHONE = "7700010890";
const MAX_QTY = 25;

const productId = Number(document.body.dataset.productId || 0);
const buyCardEl = document.getElementById("buyCard");

function normalizeQty(value) {
    const qty = Number(value || 1);
    if (!Number.isFinite(qty) || qty < 1) return 1;
    return Math.min(Math.floor(qty), MAX_QTY);
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

function renderProduct(product) {
    const image = product.image ? `<img src="${product.image}" alt="${product.name}" loading="lazy" decoding="async" />` : "";
    const description = (product.description || "").trim() || "Fresh and tasty product from Thathwamasi.";
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
            window.location.href = "/billing/";
        } catch (err) {
            alert(err.message || "Unable to proceed");
            proceedBtn.disabled = false;
            proceedBtn.textContent = "Proceed to Billing";
        }
    });
}

async function bootstrap() {
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

bootstrap();
