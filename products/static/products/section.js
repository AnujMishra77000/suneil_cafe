const state = {
    sectionName: document.body.dataset.section,
    categories: [],
    selectedCategoryId: null,
    selectedCategoryName: "",
    products: [],
    productsByCategory: {},
    profile: {
        name: "",
        phone: "",
        whatsapp_no: ""
    },
    cart_phone: ""
};

const CATEGORY_TTL_MS = 10 * 60 * 1000;
const PRODUCT_TTL_MS = 5 * 60 * 1000;

function sectionCategoryCacheKey() {
    return `thathwamasi_categories_v2_${state.sectionName.toLowerCase()}`;
}

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

const categoryGridEl = document.getElementById("categoryGrid");
const categoryCountEl = document.getElementById("categoryCount");
const productGridEl = document.getElementById("productGrid");
const countLabelEl = document.getElementById("countLabel");
const pageTitleEl = document.getElementById("pageTitle");
const selectedCategoryBarEl = document.getElementById("selectedCategoryBar");
const searchInputEl = document.getElementById("searchInput");
const searchBtnEl = document.getElementById("searchBtn");
const profileBtnEl = document.getElementById("profileBtn");
const cartCountEl = document.getElementById("cartCount");
const OWNER_PHONE = "7700010890";

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
    } catch (err) {
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
    } catch (err) {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) throw new Error(data.error || data.detail || "Request failed");
    return data;
}

function renderCategoryCards() {
    if (!categoryGridEl || !categoryCountEl) return;
    categoryCountEl.textContent = "";
    if (!state.categories.length) {
        categoryGridEl.innerHTML = `<div class="empty">No categories found in this section.</div>`;
        return;
    }

    categoryGridEl.innerHTML = state.categories.map((category) => {
        const isActive = category.id === state.selectedCategoryId ? "active" : "";
        return `
            <button class="category-card ${isActive}" data-category-id="${category.id}">
                <h3>${category.name}</h3>
                <p>Tap to view products</p>
            </button>
        `;
    }).join("");
    animateCardReveal("#categoryGrid .category-card");
}

function cardTemplate(product) {
    const image = product.image ? `<img src="${product.image}" alt="${product.name}" loading="lazy" decoding="async" />` : "";
    const out = product.is_available ? "" : `<div class="out">Out of Stock</div>`;
    const description = (product.description || "").trim() || "Fresh and tasty product from Thathwamasi.";

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

function renderProducts(title) {
    if (!pageTitleEl || !countLabelEl || !productGridEl) return;
    pageTitleEl.textContent = title;
    countLabelEl.textContent = `${state.products.length} items`;

    if (!state.products.length) {
        productGridEl.innerHTML = `<div class="empty">No products found for this category.</div>`;
        return;
    }
    productGridEl.innerHTML = state.products.map(cardTemplate).join("");
    animateCardReveal("#productGrid .card");
}

function animateCardReveal(selector) {
    const nodes = document.querySelectorAll(selector);
    nodes.forEach((node, index) => {
        node.style.animationDelay = `${Math.min(index, 12) * 35}ms`;
        node.classList.add("reveal");
    });
}

function renderSelectedCategoryBar() {
    if (!selectedCategoryBarEl) return;
    if (!state.selectedCategoryId) {
        selectedCategoryBarEl.classList.add("hidden");
        selectedCategoryBarEl.innerHTML = "";
        return;
    }

    selectedCategoryBarEl.classList.remove("hidden");
    selectedCategoryBarEl.innerHTML = `
        Showing: ${state.selectedCategoryName}
        <button id="clearCategoryFilter">Clear</button>
    `;
}

async function resolveSection() {
    const payload = await apiGet("/api/products/sections/");
    const sections = normalizeList(payload);
    const match = sections.find((x) => (x.name || "").toLowerCase() === state.sectionName.toLowerCase());
    return Boolean(match);
}

async function loadCategories() {
    const cachedCategories = readJsonCache(sectionCategoryCacheKey(), CATEGORY_TTL_MS);
    if (Array.isArray(cachedCategories) && cachedCategories.length) {
        state.categories = cachedCategories;
        renderCategoryCards();
    }

    // Primary source: robust section-name endpoint for category cards
    const payload = await apiGet(`/api/products/category-cards/?section=${encodeURIComponent(state.sectionName)}`);
    state.categories = normalizeList(payload);

    // Fallback for legacy responses/environments
    if (!state.categories.length) {
        const hasSection = await resolveSection();
        if (hasSection) {
            const sectionsPayload = await apiGet("/api/products/sections/");
            const sections = normalizeList(sectionsPayload);
            const matched = sections.find((x) => (x.name || "").toLowerCase() === state.sectionName.toLowerCase());
            if (matched?.id) {
                const fallbackPayload = await apiGet(`/api/products/sections/${matched.id}/categories/`);
                state.categories = normalizeList(fallbackPayload);
            }
        }
    }

    renderCategoryCards();
    writeJsonCache(sectionCategoryCacheKey(), state.categories);
    prefetchTopCategories();
}

async function loadProductsByCategory(categoryId) {
    const catKey = String(Number(categoryId));
    if (state.productsByCategory[catKey]) {
        state.products = state.productsByCategory[catKey];
    } else {
        const cachedProducts = readJsonCache(productCacheKey(categoryId), PRODUCT_TTL_MS);
        if (Array.isArray(cachedProducts)) {
            state.productsByCategory[catKey] = cachedProducts;
            state.products = cachedProducts;
        }
    }

    const cat = state.categories.find((x) => x.id === categoryId);
    state.selectedCategoryName = cat ? cat.name : "Category";
    renderProducts(cat ? `${cat.name} Products` : "Products");
    renderSelectedCategoryBar();

    if (!state.productsByCategory[catKey]) {
        const payload = await apiGet(`/api/products/categories/${categoryId}/products/`);
        const normalized = normalizeList(payload);
        state.productsByCategory[catKey] = normalized;
        state.products = normalized;
        writeJsonCache(productCacheKey(categoryId), normalized);
        renderProducts(cat ? `${cat.name} Products` : "Products");
    }
}

async function runSearch() {
    const q = searchInputEl.value.trim();
    if (!q) {
        if (!state.selectedCategoryId) {
            renderProducts("Select a category");
            return;
        }
        await loadProductsByCategory(state.selectedCategoryId);
        return;
    }

    const payload = await apiGet(`/api/products/search/?q=${encodeURIComponent(q)}`);
    const results = normalizeList(payload).filter((x) => (x.section_name || "").toLowerCase() === state.sectionName.toLowerCase());

    if (state.selectedCategoryId) {
        state.products = results.filter((x) => x.category_id === state.selectedCategoryId);
    } else {
        state.products = results;
    }
    renderProducts(`Search: ${q}`);
}

async function prefetchTopCategories() {
    const top = state.categories.slice(0, 3);
    for (const category of top) {
        const key = String(Number(category.id));
        if (!key || state.productsByCategory[key]) continue;
        const cachedProducts = readJsonCache(productCacheKey(category.id), PRODUCT_TTL_MS);
        if (Array.isArray(cachedProducts)) {
            state.productsByCategory[key] = cachedProducts;
            continue;
        }
        try {
            const payload = await apiGet(`/api/products/categories/${category.id}/products/`);
            const normalized = normalizeList(payload);
            state.productsByCategory[key] = normalized;
            writeJsonCache(productCacheKey(category.id), normalized);
        } catch {
            // Silent prefetch failure.
        }
    }
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

async function onCategoryClick(event) {
    const card = event.target.closest("[data-category-id]");
    if (!card) return;
    const categoryId = Number(card.dataset.categoryId);
    if (!categoryId) return;
    state.selectedCategoryId = categoryId;
    renderCategoryCards();
    await loadProductsByCategory(categoryId);
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

async function onClearCategoryFilter(event) {
    if (event.target.id !== "clearCategoryFilter") return;
    state.selectedCategoryId = null;
    state.selectedCategoryName = "";
    state.products = [];
    renderCategoryCards();
    renderSelectedCategoryBar();
    renderProducts("Select a category");
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
    } catch (err) {
        if (cartCountEl) cartCountEl.textContent = "0";
    }
}

async function bootstrap() {
    readProfile();
    getOrCreateCartPhone();
    renderProducts("Select a category");
    try {
        await loadCategories();
        await refreshCartCount();
    } catch (err) {
        console.error(err);
        if (categoryGridEl) {
            categoryGridEl.innerHTML = `<div class="empty">Unable to load categories for this section.</div>`;
        }
    }
}

if (searchBtnEl) searchBtnEl.addEventListener("click", runSearch);
if (searchInputEl) {
    searchInputEl.addEventListener("keydown", (event) => {
        if (event.key === "Enter") runSearch();
    });
}
if (profileBtnEl) profileBtnEl.addEventListener("click", askProfile);
if (categoryGridEl) categoryGridEl.addEventListener("click", onCategoryClick);
if (productGridEl) productGridEl.addEventListener("click", onGridClick);
if (selectedCategoryBarEl) selectedCategoryBarEl.addEventListener("click", onClearCategoryFilter);

bootstrap();
