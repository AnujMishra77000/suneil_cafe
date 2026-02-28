const state = {
    sectionName: document.body.dataset.section,
    categories: [],
    filteredCategories: [],
    profile: {
        name: "",
        phone: "",
        whatsapp_no: ""
    },
    cart_phone: ""
};

const CATEGORY_TTL_MS = 10 * 60 * 1000;
const categoryGridEl = document.getElementById("categoryGrid");
const categoryCountEl = document.getElementById("categoryCount");
const searchInputEl = document.getElementById("searchInput");
const searchBtnEl = document.getElementById("searchBtn");
const profileBtnEl = document.getElementById("profileBtn");
const cartCountEl = document.getElementById("cartCount");

function sectionCategoryCacheKey() {
    return `thathwamasi_categories_v3_${state.sectionName.toLowerCase()}`;
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

function animateCardReveal(selector) {
    const nodes = document.querySelectorAll(selector);
    nodes.forEach((node, index) => {
        node.style.animationDelay = `${Math.min(index, 12) * 35}ms`;
        node.classList.add("reveal");
    });
}

function buildCategoryUrl(category) {
    return `/${state.sectionName.toLowerCase()}/category/${category.id}/`;
}

function renderCategoryCards() {
    if (!categoryGridEl || !categoryCountEl) return;
    const visibleCategories = state.filteredCategories.length || !searchInputEl?.value.trim()
        ? state.filteredCategories
        : [];
    categoryCountEl.textContent = `${visibleCategories.length} categories`;

    if (!visibleCategories.length) {
        categoryGridEl.innerHTML = `<div class="empty">No categories match your search.</div>`;
        return;
    }

    categoryGridEl.innerHTML = visibleCategories.map((category) => `
        <a class="category-card" href="${buildCategoryUrl(category)}" data-category-id="${category.id}">
            <h3>${category.name}</h3>
            <p>Open this category to view all related products.</p>
            <span class="category-card-cta">View products</span>
        </a>
    `).join("");
    animateCardReveal("#categoryGrid .category-card");
}

function filterCategories(query) {
    const normalized = (query || "").trim().toLowerCase();
    if (!normalized) {
        state.filteredCategories = [...state.categories];
    } else {
        state.filteredCategories = state.categories.filter((category) =>
            (category.name || "").toLowerCase().includes(normalized)
        );
    }
    renderCategoryCards();
}

async function loadCategories() {
    const cachedCategories = readJsonCache(sectionCategoryCacheKey(), CATEGORY_TTL_MS);
    if (Array.isArray(cachedCategories) && cachedCategories.length) {
        state.categories = cachedCategories;
        state.filteredCategories = [...cachedCategories];
        renderCategoryCards();
    }

    const payload = await apiGet(`/api/products/category-cards/?section=${encodeURIComponent(state.sectionName)}`);
    state.categories = normalizeList(payload);
    state.filteredCategories = [...state.categories];
    writeJsonCache(sectionCategoryCacheKey(), state.categories);
    renderCategoryCards();
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

function runSearch() {
    filterCategories(searchInputEl?.value || "");
}

async function bootstrap() {
    readProfile();
    getOrCreateCartPhone();
    try {
        await loadCategories();
        await refreshCartCount();
    } catch (err) {
        console.error(err);
        if (categoryGridEl) {
            categoryGridEl.innerHTML = `<div class="empty">Unable to load categories for this section.</div>`;
        }
        if (categoryCountEl) categoryCountEl.textContent = "0 categories";
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

bootstrap();
