const state = {
    sections: [],
    categories: [],
    selectedSectionId: null,
    selectedCategoryId: null,
    products: [],
    profile: {
        name: "",
        phone: "",
        whatsapp_no: ""
    },
    buyNowInFlight: {}
};

const sectionTabsEl = document.getElementById("sectionTabs");
const categoryTabsEl = document.getElementById("categoryTabs");
const productGridEl = document.getElementById("productGrid");
const productCountEl = document.getElementById("productCount");
const productTitleEl = document.getElementById("productTitle");
const searchInputEl = document.getElementById("searchInput");
const searchBtnEl = document.getElementById("searchBtn");
const profileBtnEl = document.getElementById("profileBtn");
const relatedPanelEl = document.getElementById("relatedPanel");
const relatedListEl = document.getElementById("relatedList");
const closeRelatedEl = document.getElementById("closeRelated");

function readProfile() {
    const raw = localStorage.getItem("thathwamasi_profile");
    if (!raw) return;
    try {
        const data = JSON.parse(raw);
        if (data.name && data.phone && data.whatsapp_no) {
            state.profile = data;
            profileBtnEl.textContent = `Deliver to ${data.name}`;
        }
    } catch (error) {
        console.error(error);
    }
}

function askProfile() {
    const name = prompt("Enter your name");
    if (!name) return false;
    const phone = prompt("Enter phone number");
    if (!phone) return false;
    const whatsapp = prompt("Enter WhatsApp number");
    if (!whatsapp) return false;

    state.profile = { name: name.trim(), phone: phone.trim(), whatsapp_no: whatsapp.trim() };
    localStorage.setItem("thathwamasi_profile", JSON.stringify(state.profile));
    profileBtnEl.textContent = `Deliver to ${state.profile.name}`;
    return true;
}

function notify(message, ok = true) {
    const el = document.createElement("div");
    el.className = "status-msg";
    el.style.background = ok ? "#1f7a3f" : "#9f342d";
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 1800);
}

async function apiGet(url) {
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`Failed GET ${url}`);
    }
    return res.json();
}

async function apiPost(url, payload) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.error || "Request failed");
    }
    return data;
}

function renderSections() {
    sectionTabsEl.innerHTML = "";
    state.sections.forEach((section) => {
        const btn = document.createElement("button");
        btn.className = `tab-btn ${section.id === state.selectedSectionId ? "active" : ""}`;
        btn.textContent = section.name;
        btn.onclick = async () => {
            state.selectedSectionId = section.id;
            state.selectedCategoryId = null;
            await loadCategories(section.id);
            await loadProductsBySection(section.id);
            renderSections();
        };
        sectionTabsEl.appendChild(btn);
    });
}

function renderCategories() {
    categoryTabsEl.innerHTML = "";
    const allBtn = document.createElement("button");
    allBtn.className = `chip-btn ${!state.selectedCategoryId ? "active" : ""}`;
    allBtn.textContent = "All";
    allBtn.onclick = async () => {
        state.selectedCategoryId = null;
        await loadProductsBySection(state.selectedSectionId);
        renderCategories();
    };
    categoryTabsEl.appendChild(allBtn);

    state.categories.forEach((category) => {
        const btn = document.createElement("button");
        btn.className = `chip-btn ${category.id === state.selectedCategoryId ? "active" : ""}`;
        btn.textContent = category.name;
        btn.onclick = async () => {
            state.selectedCategoryId = category.id;
            await loadProductsByCategory(category.id);
            renderCategories();
        };
        categoryTabsEl.appendChild(btn);
    });
}

function productCardTemplate(product) {
    const unavailable = !product.is_available
        ? `<div class="unavailable">Out of stock right now</div>`
        : "";

    const image = product.image
        ? `<img src="${product.image}" alt="${product.name}" />`
        : "";

    return `
        <article class="card">
            <div class="thumb">${image}</div>
            <div class="card-body">
                <div class="name-row">
                    <h4>${product.name}</h4>
                    <div class="price">Rs ${product.price}</div>
                </div>
                <div class="meta">${product.category_name} | ${product.section_name}</div>
                <div class="btn-row">
                    <button class="secondary-btn" data-action="add-cart" data-product-id="${product.id}">Add to Cart</button>
                    <button class="primary-btn" data-action="buy-now" data-product-id="${product.id}">Buy Now</button>
                </div>
                <button class="ghost-btn" data-action="show-related" data-product-id="${product.id}">Related Products</button>
                ${unavailable}
            </div>
        </article>
    `;
}

function renderProducts(title = "All Products") {
    productTitleEl.textContent = title;
    productCountEl.textContent = `${state.products.length} items`;

    if (!state.products.length) {
        productGridEl.innerHTML = `<div class="empty-state">No products found for this selection.</div>`;
        return;
    }

    productGridEl.innerHTML = state.products.map(productCardTemplate).join("");
}

async function loadSections() {
    state.sections = await apiGet("/api/products/sections/");
    if (!state.sections.length) {
        renderProducts("Products");
        return;
    }
    state.selectedSectionId = state.sections[0].id;
}

async function loadCategories(sectionId) {
    state.categories = await apiGet(`/api/products/sections/${sectionId}/categories/`);
    renderCategories();
}

async function loadProductsBySection(sectionId) {
    state.products = await apiGet(`/api/products/sections/${sectionId}/products/`);
    const section = state.sections.find((x) => x.id === sectionId);
    renderProducts(section ? `${section.name} Picks` : "Products");
}

async function loadProductsByCategory(categoryId) {
    state.products = await apiGet(`/api/products/categories/${categoryId}/products/`);
    const category = state.categories.find((x) => x.id === categoryId);
    renderProducts(category ? `${category.name} Products` : "Products");
}

async function runSearch() {
    const q = searchInputEl.value.trim();
    if (!q) {
        if (state.selectedCategoryId) {
            await loadProductsByCategory(state.selectedCategoryId);
        } else {
            await loadProductsBySection(state.selectedSectionId);
        }
        return;
    }

    state.products = await apiGet(`/api/products/search/?q=${encodeURIComponent(q)}`);
    renderProducts(`Search: ${q}`);
}

async function showRelated(productId) {
    const products = await apiGet(`/api/products/${productId}/related/`);
    if (!products.length) {
        relatedListEl.innerHTML = `<div class="empty-state">No related products available.</div>`;
    } else {
        relatedListEl.innerHTML = products.map((product) => `
            <div class="related-item">
                <div>
                    <strong>${product.name}</strong><br/>
                    <small>${product.category_name} | Rs ${product.price}</small>
                </div>
                <button class="secondary-btn" data-action="add-cart" data-product-id="${product.id}">Add</button>
            </div>
        `).join("");
    }
    relatedPanelEl.classList.remove("hidden");
}

async function addToCart(productId) {
    if (!state.profile.phone) {
        const ok = askProfile();
        if (!ok) return;
    }

    await apiPost("/api/cart/add/", {
        phone: state.profile.phone,
        product_id: productId,
        quantity: 1
    });
    notify("Product added to cart");
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

function buyNowKeyStorage(productId) {
    return `thathwamasi_buy_now_idempo_${productId}`;
}

function getOrCreateBuyNowKey(productId) {
    const storageKey = buyNowKeyStorage(productId);
    let key = sessionStorage.getItem(storageKey);
    if (!key) {
        key = newIdempotencyKey();
        sessionStorage.setItem(storageKey, key);
    }
    return key;
}

function clearBuyNowKey(productId) {
    sessionStorage.removeItem(buyNowKeyStorage(productId));
}

async function buyNow(productId) {
    if (!state.profile.phone || !state.profile.name || !state.profile.whatsapp_no) {
        const ok = askProfile();
        if (!ok) return;
    }

    const lockKey = String(productId);
    if (state.buyNowInFlight[lockKey]) return;
    state.buyNowInFlight[lockKey] = true;

    try {
        const idempotencyKey = getOrCreateBuyNowKey(productId);
        const result = await apiPost("/api/orders/place-order/", {
            customer_name: state.profile.name,
            phone: state.profile.phone,
            whatsapp_no: state.profile.whatsapp_no,
            items: [{ product_id: productId, quantity: 1 }],
            idempotency_key: idempotencyKey
        });

        clearBuyNowKey(productId);
        notify(`Order placed. ID ${result.order_id}`);
        if (state.selectedCategoryId) {
            await loadProductsByCategory(state.selectedCategoryId);
        } else {
            await loadProductsBySection(state.selectedSectionId);
        }
    } finally {
        delete state.buyNowInFlight[lockKey];
    }
}

async function handleCardAction(event) {
    const target = event.target.closest("button");
    if (!target) return;
    const action = target.dataset.action;
    const productId = Number(target.dataset.productId);
    if (!action || !productId) return;

    try {
        if (action === "add-cart") await addToCart(productId);
        if (action === "buy-now") await buyNow(productId);
        if (action === "show-related") await showRelated(productId);
    } catch (error) {
        notify(error.message || "Action failed", false);
    }
}

async function bootstrap() {
    readProfile();
    try {
        await loadSections();
        renderSections();
        await loadCategories(state.selectedSectionId);
        await loadProductsBySection(state.selectedSectionId);
    } catch (error) {
        productGridEl.innerHTML = `<div class="empty-state">Unable to load storefront data.</div>`;
    }
}

searchBtnEl.addEventListener("click", runSearch);
searchInputEl.addEventListener("keydown", (event) => {
    if (event.key === "Enter") runSearch();
});
profileBtnEl.addEventListener("click", askProfile);
productGridEl.addEventListener("click", handleCardAction);
relatedListEl.addEventListener("click", handleCardAction);
closeRelatedEl.addEventListener("click", () => relatedPanelEl.classList.add("hidden"));

bootstrap();
