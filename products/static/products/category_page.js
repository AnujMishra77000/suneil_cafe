const state = {
    sectionName: document.body.dataset.section,
    categoryId: Number(document.body.dataset.categoryId || 0),
    categoryName: document.body.dataset.categoryName || "Category",
    products: [],
    filteredProducts: [],
    profile: {
        name: "",
        phone: "",
        whatsapp_no: ""
    },
    cart_phone: ""
};

const PRODUCT_TTL_MS = 5 * 60 * 1000;
const OWNER_PHONE = "7700010890";
const productGridEl = document.getElementById("productGrid");
const countLabelEl = document.getElementById("countLabel");
const pageTitleEl = document.getElementById("pageTitle");
const searchInputEl = document.getElementById("searchInput");
const searchBtnEl = document.getElementById("searchBtn");
const profileBtnEl = document.getElementById("profileBtn");
const cartCountEl = document.getElementById("cartCount");

function productCacheKey(categoryId) {
    return `thathwamasi_products_${Number(categoryId)}`;
}

function readJsonCache(key, ttlMs) {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    try {
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object") return null;
        const ts = Number(parsed.ts || 0);
        if (!ts || Date.now() - ts > ttlMs) return null;
        return parsed.data;
    } catch {
        return null;
    }
}

function writeJsonCache(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify({ ts: Date.now(), data }));
    } catch {
        // Ignore quota errors.
    }
}

function normalizeList(payload) {
    if (Array.isArray(payload)) return payload;
    if (payload && Array.isArray(payload.results)) return payload.results;
    return [];
}

function toast(message, ok = true) {
    const el = document.createElement("div");
    el.className = "toast";
    el.style.background = ok ? "#1f7a3f" : "#a12f2f";
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1800);
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

async function apiGet(url) {
    const res = await fetch(url);
    const raw = await res.text();
    let data;
    try {
        data = raw ? JSON.parse(raw) : {};
    } catch {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) {
        throw new Error(data.error || data.detail || `Request failed (${res.status})`);
    }
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
    } catch {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) throw new Error(data.error || data.detail || "Request failed");
    return data;
}

function animateCardReveal(selector) {
    const nodes = document.querySelectorAll(selector);
    nodes.forEach((node, index) => {
        node.style.animationDelay = `${Math.min(index, 12) * 35}ms`;
        node.classList.add("reveal");
    });
}

function cardTemplate(product) {
    const image = product.image ? `<img src="${product.image}" alt="${product.name}" loading="lazy" decoding="async" />` : "";
    const out = product.is_available ? "" : `<div class="out">Out of Stock</div>`;
    const description = (product.description || "").trim() || "Fresh and tasty product from Thathwamasi Bakery Cafe.";

    return `
        <article class="card" data-product-id="${product.id}" data-available="${product.is_available ? "1" : "0"}">
            <div class="thumb">${image}</div>
            <div class="body">
                <div class="title-row">
                    <h3>${product.name}</h3>
                    <span class="price">Rs ${product.price}</span>
                </div>
                <div class="meta">${product.category_name}</div>
                <p class="meta">${description}</p>
                <div class="action-row">
                    <button class="cart-btn" data-action="cart">Add to Cart</button>
                    <button class="buy-btn" data-action="buy">Buy Now</button>
                </div>
                ${out}
            </div>
        </article>
    `;
}

function showOutOfStockPopup(productName = "This product") {
    alert(`${productName} is out of stock. Please contact owner: ${OWNER_PHONE}`);
}

function renderProducts(title, products) {
    if (pageTitleEl) pageTitleEl.textContent = title;
    if (countLabelEl) countLabelEl.textContent = `${products.length} items`;

    if (!productGridEl) return;
    if (!products.length) {
        productGridEl.innerHTML = `
            <div class="empty empty--coming-soon">
                <strong>Fresh & handmade goodies are coming soon.</strong>
                <span>Our ovens are doing a happy dance and this category will be loaded very soon.</span>
            </div>
        `;
        return;
    }

    productGridEl.innerHTML = products.map(cardTemplate).join("");
    animateCardReveal("#productGrid .card");
}

async function loadProducts() {
    const cacheKey = productCacheKey(state.categoryId);
    const cachedProducts = readJsonCache(cacheKey, PRODUCT_TTL_MS);
    if (Array.isArray(cachedProducts)) {
        state.products = cachedProducts;
        state.filteredProducts = [...cachedProducts];
        renderProducts(`${state.categoryName} Products`, state.filteredProducts);
    }

    const payload = await apiGet(`/api/products/categories/${state.categoryId}/products/`);
    const normalized = normalizeList(payload);
    state.products = normalized;
    state.filteredProducts = [...normalized];
    writeJsonCache(cacheKey, normalized);
    renderProducts(`${state.categoryName} Products`, state.filteredProducts);
}

function runSearch() {
    const query = (searchInputEl?.value || "").trim().toLowerCase();
    if (!query) {
        state.filteredProducts = [...state.products];
        renderProducts(`${state.categoryName} Products`, state.filteredProducts);
        return;
    }

    state.filteredProducts = state.products.filter((product) => {
        const haystacks = [product.name, product.description, product.category_name]
            .map((value) => (value || "").toLowerCase());
        return haystacks.some((value) => value.includes(query));
    });
    renderProducts(`Search in ${state.categoryName}: ${searchInputEl.value.trim()}`, state.filteredProducts);
}

async function addToCart(productId, qty) {
    if (!Number.isFinite(Number(productId)) || Number(productId) <= 0) {
        throw new Error("Invalid product selected");
    }
    const cartPhone = getOrCreateCartPhone();
    const previous = Number((cartCountEl && cartCountEl.textContent) || "0");
    if (cartCountEl) cartCountEl.textContent = String(Math.max(0, previous + qty));
    try {
        await apiPost("/api/cart/add/", {
            phone: cartPhone,
            product_id: productId,
            quantity: qty
        });
        toast("Added to cart");
        await refreshCartCount();
    } catch (err) {
        if (cartCountEl) cartCountEl.textContent = String(previous);
        throw err;
    }
}

function buyNow(productId) {
    window.location.href = `/buy/${productId}/`;
}

async function onGridClick(event) {
    const button = event.target.closest("button");
    const clickedCard = event.target.closest(".card");
    if (!button && clickedCard && clickedCard.dataset.available === "0") {
        const name = clickedCard.querySelector("h3")?.textContent || "This product";
        showOutOfStockPopup(name);
        return;
    }
    if (!button) return;
    const card = event.target.closest(".card");
    const productId = Number(card?.dataset.productId);
    const action = button.dataset.action;
    if (!action) return;

    const isAvailable = card ? card.dataset.available === "1" : true;
    const productName = card?.querySelector("h3")?.textContent || "This product";
    if ((action === "cart" || action === "buy") && !isAvailable) {
        showOutOfStockPopup(productName);
        return;
    }
    try {
        if (action === "cart") await addToCart(productId, 1);
        if (action === "buy") buyNow(productId);
    } catch (err) {
        toast(err.message || "Action failed", false);
    }
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

async function bootstrap() {
    readProfile();
    getOrCreateCartPhone();
    if (!state.categoryId) {
        renderProducts(`${state.categoryName} Products`, []);
        return;
    }
    try {
        await loadProducts();
        await refreshCartCount();
    } catch (err) {
        console.error(err);
        if (productGridEl) {
            productGridEl.innerHTML = `<div class="empty">Unable to load products for this category.</div>`;
        }
        if (countLabelEl) countLabelEl.textContent = "0 items";
    }
}

if (searchBtnEl) searchBtnEl.addEventListener("click", runSearch);
if (searchInputEl) {
    searchInputEl.addEventListener("input", runSearch);
    searchInputEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter") runSearch();
    });
}
if (profileBtnEl) profileBtnEl.addEventListener("click", askProfile);
if (productGridEl) productGridEl.addEventListener("click", onGridClick);

bootstrap();
