const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, (token) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;",
    })[token]);
}

async function apiGet(url) {
    const response = await fetch(url);
    const raw = await response.text();
    let payload = {};
    try {
        payload = raw ? JSON.parse(raw) : {};
    } catch (error) {
        throw new Error(`Server returned non-JSON response (${response.status})`);
    }
    if (!response.ok) {
        throw new Error(payload.error || payload.detail || `Request failed (${response.status})`);
    }
    return payload;
}

function initAutoSwiper(root) {
    if (!root) return;
    const track = root.querySelector("[data-swiper-track]");
    const dotsWrap = root.querySelector("[data-swiper-dots]");
    const slides = Array.from(track?.children || []);
    if (!track || !slides.length) return;

    const interval = Math.max(1800, Number(root.dataset.interval || 3200));
    let index = 0;
    let timer = null;

    function renderDots() {
        if (!dotsWrap) return;
        dotsWrap.innerHTML = "";
        slides.forEach((_, dotIndex) => {
            const dot = document.createElement("button");
            dot.type = "button";
            dot.ariaLabel = `Open slide ${dotIndex + 1}`;
            if (dotIndex === index) dot.classList.add("active");
            dot.addEventListener("click", () => {
                index = dotIndex;
                update();
                start();
            });
            dotsWrap.appendChild(dot);
        });
    }

    function update() {
        track.style.transform = `translateX(-${index * 100}%)`;
        if (!dotsWrap) return;
        dotsWrap.querySelectorAll("button").forEach((dot, dotIndex) => {
            dot.classList.toggle("active", dotIndex === index);
        });
    }

    function stop() {
        if (!timer) return;
        window.clearInterval(timer);
        timer = null;
    }

    function start() {
        stop();
        if (slides.length < 2 || prefersReducedMotion) return;
        timer = window.setInterval(() => {
            index = (index + 1) % slides.length;
            update();
        }, interval);
    }

    renderDots();
    update();
    start();

    root.addEventListener("mouseenter", stop);
    root.addEventListener("mouseleave", start);
    root.addEventListener("touchstart", stop, { passive: true });
    root.addEventListener("touchend", start, { passive: true });
}

function normalizeSectionName(section) {
    const value = String(section || "").trim().toLowerCase();
    if (value === "backery") return "bakery";
    if (value === "snack") return "snacks";
    return value || "bakery";
}

function buildCategoryCardMarkup(item, fallbackSection) {
    const id = Number(item?.id || 0);
    const name = escapeHtml(item?.name || "Category");
    const section = normalizeSectionName(item?.section || fallbackSection);
    const image = String(item?.image || "").trim();
    const href = `/${section}/category/${id}/`;
    const style = image ? ` style="background-image:url('${image}');"` : "";
    return `<a class="category-mini-card" href="${href}"${style}><span>${name}</span></a>`;
}

function buildEmptyCategoryPage(text) {
    const safeText = escapeHtml(text);
    return `
        <article class="category-page">
            <article class="category-mini-card category-mini-card--placeholder"><span>${safeText}</span></article>
            <article class="category-mini-card category-mini-card--placeholder"><span>${safeText}</span></article>
            <article class="category-mini-card category-mini-card--placeholder"><span>${safeText}</span></article>
            <article class="category-mini-card category-mini-card--placeholder"><span>${safeText}</span></article>
        </article>
    `;
}

function initCategorySwiper(swiperRoot, dotsWrap) {
    const track = swiperRoot?.querySelector(".category-pages-track");
    const pages = Array.from(track?.children || []);
    if (!track || !pages.length) return;

    const interval = Math.max(2200, Number(swiperRoot.dataset.interval || 3400));
    let index = 0;
    let timer = null;

    function renderDots() {
        if (!dotsWrap) return;
        dotsWrap.innerHTML = "";
        pages.forEach((_, dotIndex) => {
            const dot = document.createElement("button");
            dot.type = "button";
            dot.ariaLabel = `Open category frame ${dotIndex + 1}`;
            if (dotIndex === index) dot.classList.add("active");
            dot.addEventListener("click", () => {
                index = dotIndex;
                update();
                start();
            });
            dotsWrap.appendChild(dot);
        });
    }

    function update() {
        track.style.transform = `translateX(-${index * 100}%)`;
        if (!dotsWrap) return;
        dotsWrap.querySelectorAll("button").forEach((dot, dotIndex) => {
            dot.classList.toggle("active", dotIndex === index);
        });
    }

    function stop() {
        if (!timer) return;
        window.clearInterval(timer);
        timer = null;
    }

    function start() {
        stop();
        if (pages.length < 2 || prefersReducedMotion) return;
        timer = window.setInterval(() => {
            index = (index + 1) % pages.length;
            update();
        }, interval);
    }

    renderDots();
    update();
    start();

    swiperRoot.addEventListener("mouseenter", stop);
    swiperRoot.addEventListener("mouseleave", start);
    swiperRoot.addEventListener("touchstart", stop, { passive: true });
    swiperRoot.addEventListener("touchend", start, { passive: true });
}

function chunkItems(items, size) {
    const chunks = [];
    for (let i = 0; i < items.length; i += size) {
        chunks.push(items.slice(i, i + size));
    }
    return chunks;
}

async function loadCategoryFrames(section, pagesId, dotsId, emptyText) {
    const pagesEl = document.getElementById(pagesId);
    const dotsEl = document.getElementById(dotsId);
    const root = pagesEl?.closest("[data-category-swiper]");
    if (!pagesEl || !root) return;

    try {
        const payload = await apiGet(`/api/products/category-cards/?section=${encodeURIComponent(section)}`);
        const cards = Array.isArray(payload) ? payload : [];
        if (!cards.length) {
            pagesEl.innerHTML = buildEmptyCategoryPage(emptyText);
            initCategorySwiper(root, dotsEl);
            return;
        }

        const groups = chunkItems(cards, 4);
        pagesEl.innerHTML = groups.map((group) => {
            const filled = [...group];
            while (filled.length < 4) {
                filled.push({ id: 0, name: "More coming soon", section, image: "" });
            }
            return `
                <article class="category-page">
                    ${filled.map((item) => item.id ? buildCategoryCardMarkup(item, section) : '<article class="category-mini-card category-mini-card--placeholder"><span>More coming soon</span></article>').join("")}
                </article>
            `;
        }).join("");
    } catch (error) {
        pagesEl.innerHTML = buildEmptyCategoryPage(emptyText);
    }

    initCategorySwiper(root, dotsEl);
}

function renderHomeHistory(phone, orders) {
    const homeHistoryEl = document.getElementById("homeHistory");
    const homeHistoryListEl = document.getElementById("homeHistoryList");
    const homeHistoryPhoneEl = document.getElementById("homeHistoryPhone");
    if (!homeHistoryEl || !homeHistoryListEl || !homeHistoryPhoneEl) return;

    if (!orders.length) {
        homeHistoryEl.classList.add("hidden");
        return;
    }

    homeHistoryPhoneEl.textContent = `Phone: ${phone}`;
    homeHistoryListEl.innerHTML = orders.slice(0, 6).map((order) => `
        <article class="history-order">
            <h4>Order #${escapeHtml(order.id)}</h4>
            <p>Status: ${escapeHtml(order.status)}</p>
            <p>Total: Rs ${escapeHtml(order.total_price)}</p>
        </article>
    `).join("");
    homeHistoryEl.classList.remove("hidden");
}

async function loadHomeHistory() {
    const phone = (localStorage.getItem("thathwamasi_checkout_phone") || "").trim();
    if (!phone) return;

    try {
        const payload = await apiGet(`/api/orders/history-by-phone/?phone=${encodeURIComponent(phone)}`);
        const orders = Array.isArray(payload.orders) ? payload.orders : [];
        const filtered = orders.filter((order) => {
            const status = String(order.status || "").toLowerCase();
            return status.includes("placed") || status.includes("confirm");
        });
        renderHomeHistory(phone, filtered);
    } catch (error) {
        // Ignore history loading failure on homepage.
    }
}

function initScrollReveal() {
    const elements = Array.from(document.querySelectorAll(".scroll-reveal"));
    if (!elements.length) return;
    if (prefersReducedMotion || !("IntersectionObserver" in window)) {
        elements.forEach((el) => el.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
        });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });

    elements.forEach((element, index) => {
        element.style.setProperty("--reveal-delay", `${Math.min(index, 10) * 55}ms`);
        observer.observe(element);
    });
}

function initHomePage() {
    document.querySelectorAll("[data-auto-swiper]").forEach(initAutoSwiper);
    loadCategoryFrames("bakery", "bakeryCategoryPages", "bakeryCategoryDots", "Fresh bakery categories coming soon");
    loadCategoryFrames("snacks", "snacksCategoryPages", "snacksCategoryDots", "Fresh snacks are coming soon");
    loadHomeHistory();
    initScrollReveal();
}

initHomePage();
