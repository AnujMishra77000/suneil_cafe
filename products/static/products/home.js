const slides = Array.from(document.querySelectorAll(".slide"));
const dotsWrap = document.getElementById("carouselDots");
const prevBtn = document.getElementById("heroPrev");
const nextBtn = document.getElementById("heroNext");
const homeHistoryEl = document.getElementById("homeHistory");
const homeHistoryListEl = document.getElementById("homeHistoryList");
const homeHistoryPhoneEl = document.getElementById("homeHistoryPhone");
let current = 0;
let autoplayId = null;
const AUTOPLAY_MS = 4200;

function renderDots() {
    if (!dotsWrap) return;
    dotsWrap.innerHTML = "";
    slides.forEach((_, i) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.ariaLabel = `Go to slide ${i + 1}`;
        if (i === current) dot.classList.add("active");
        dot.addEventListener("click", () => {
            current = i;
            showSlide();
            startAutoplay();
        });
        dotsWrap.appendChild(dot);
    });
}

function showSlide() {
    slides.forEach((slide, i) => slide.classList.toggle("active", i === current));
    renderDots();
}

function autoPlay() {
    current = (current + 1) % slides.length;
    showSlide();
}

function startAutoplay() {
    if (autoplayId) clearInterval(autoplayId);
    autoplayId = setInterval(autoPlay, AUTOPLAY_MS);
}

function wireHoverPause() {
    const hero = document.getElementById("heroCarousel");
    if (!hero) return;
    hero.addEventListener("mouseenter", () => autoplayId && clearInterval(autoplayId));
    hero.addEventListener("mouseleave", startAutoplay);
}

if (slides.length) {
    prevBtn?.addEventListener("click", () => {
        current = (current - 1 + slides.length) % slides.length;
        showSlide();
        startAutoplay();
    });
    nextBtn?.addEventListener("click", () => {
        current = (current + 1) % slides.length;
        showSlide();
        startAutoplay();
    });
    showSlide();
    startAutoplay();
    wireHoverPause();
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
    if (!res.ok) throw new Error(data.error || data.detail || `Request failed (${res.status})`);
    return data;
}

function renderHomeHistory(phone, orders) {
    if (!orders.length) {
        homeHistoryEl.classList.add("hidden");
        return;
    }

    homeHistoryPhoneEl.textContent = `Phone: ${phone}`;
    homeHistoryListEl.innerHTML = orders.slice(0, 6).map((order) => `
        <article class="history-order scroll-reveal">
            <h4>Order #${order.id}</h4>
            <p>Status: ${order.status}</p>
            <p>Total: Rs ${order.total_price}</p>
        </article>
    `).join("");
    homeHistoryEl.classList.remove("hidden");
    registerScrollReveal(homeHistoryEl);
    registerScrollReveal(homeHistoryListEl.querySelectorAll(".history-order"));
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
    } catch (err) {
        homeHistoryEl.classList.add("hidden");
    }
}

loadHomeHistory();

let revealObserver = null;
let revealIndex = 0;

function revealDelay(index) {
    return `${Math.min(index, 10) * 70}ms`;
}

function ensureRevealObserver() {
    if (revealObserver || !("IntersectionObserver" in window)) return revealObserver;
    revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("is-visible");
            revealObserver.unobserve(entry.target);
        });
    }, { threshold: 0.14, rootMargin: "0px 0px -8% 0px" });
    return revealObserver;
}

function registerScrollReveal(nodes) {
    const elements = nodes instanceof Element ? [nodes] : Array.from(nodes || []);
    if (!elements.length) return;

    const observer = ensureRevealObserver();
    elements.forEach((element) => {
        if (!element || !element.classList || !element.classList.contains("scroll-reveal")) return;
        if (element.dataset.revealBound === "1") return;
        element.dataset.revealBound = "1";
        element.style.setProperty("--reveal-delay", revealDelay(revealIndex));
        revealIndex += 1;

        if (!observer) {
            element.classList.add("is-visible");
            return;
        }
        observer.observe(element);
    });
}

function initScrollReveal() {
    registerScrollReveal(document.querySelectorAll(".scroll-reveal"));
}

setTimeout(initScrollReveal, 30);
