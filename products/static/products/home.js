const slides = Array.from(document.querySelectorAll(".slide"));
const dotsWrap = document.getElementById("carouselDots");
const prevBtn = document.getElementById("heroPrev");
const nextBtn = document.getElementById("heroNext");
const heroCarousel = document.getElementById("heroCarousel");
const homeHistoryEl = document.getElementById("homeHistory");
const homeHistoryListEl = document.getElementById("homeHistoryList");
const homeHistoryPhoneEl = document.getElementById("homeHistoryPhone");
let current = 0;
let autoplayId = null;
let touchStartX = 0;
let touchStartY = 0;
let touchDeltaX = 0;
let trackingSwipe = false;
let mouseSwipePointerId = null;
const AUTOPLAY_MS = 4200;
const SWIPE_THRESHOLD = 42;
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function isInteractiveCarouselTarget(target) {
    return !!target?.closest?.(".carousel-nav, .dots button, .overlay-cta");
}

function goToSlide(index) {
    current = (index + slides.length) % slides.length;
    showSlide();
    startAutoplay();
}

function goToPreviousSlide() {
    goToSlide(current - 1);
}

function goToNextSlide() {
    goToSlide(current + 1);
}

function renderDots() {
    if (!dotsWrap) return;
    dotsWrap.innerHTML = "";
    slides.forEach((_, i) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.ariaLabel = `Go to slide ${i + 1}`;
        if (i === current) dot.classList.add("active");
        dot.addEventListener("click", () => goToSlide(i));
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

function stopAutoplay() {
    if (!autoplayId) return;
    clearInterval(autoplayId);
    autoplayId = null;
}

function startAutoplay() {
    stopAutoplay();
    if (slides.length < 2 || prefersReducedMotion) return;
    autoplayId = setInterval(autoPlay, AUTOPLAY_MS);
}

function wireHoverPause() {
    if (!heroCarousel) return;
    heroCarousel.addEventListener("mouseenter", stopAutoplay);
    heroCarousel.addEventListener("mouseleave", startAutoplay);
}

function resetSwipe() {
    touchStartX = 0;
    touchStartY = 0;
    touchDeltaX = 0;
    trackingSwipe = false;
}

function onSwipeStart(point) {
    touchStartX = point.clientX;
    touchStartY = point.clientY;
    touchDeltaX = 0;
    trackingSwipe = true;
    stopAutoplay();
}

function onSwipeMove(point) {
    if (!trackingSwipe) return;
    const deltaX = point.clientX - touchStartX;
    const deltaY = point.clientY - touchStartY;
    if (Math.abs(deltaY) > Math.abs(deltaX)) {
        resetSwipe();
        startAutoplay();
        return;
    }
    touchDeltaX = deltaX;
}

function onSwipeEnd() {
    if (!trackingSwipe) return;
    if (Math.abs(touchDeltaX) >= SWIPE_THRESHOLD) {
        if (touchDeltaX < 0) {
            goToNextSlide();
        } else {
            goToPreviousSlide();
        }
    } else {
        startAutoplay();
    }
    resetSwipe();
}

function wireTouchSwipe() {
    if (!heroCarousel || slides.length < 2) return;
    heroCarousel.addEventListener("touchstart", (event) => {
        if (!event.touches.length || isInteractiveCarouselTarget(event.target)) return;
        onSwipeStart(event.touches[0]);
    }, { passive: true });
    heroCarousel.addEventListener("touchmove", (event) => {
        if (!event.touches.length) return;
        onSwipeMove(event.touches[0]);
    }, { passive: true });
    heroCarousel.addEventListener("touchend", onSwipeEnd);
    heroCarousel.addEventListener("touchcancel", () => {
        resetSwipe();
        startAutoplay();
    });
}

function wireMouseSwipe() {
    if (!heroCarousel || slides.length < 2 || !window.PointerEvent) return;
    heroCarousel.addEventListener("pointerdown", (event) => {
        if (event.pointerType !== "mouse" || event.button !== 0 || isInteractiveCarouselTarget(event.target)) return;
        mouseSwipePointerId = event.pointerId;
        heroCarousel.style.cursor = "grabbing";
        try {
            heroCarousel.setPointerCapture(event.pointerId);
        } catch (error) {
            // Ignore browsers that do not support pointer capture here.
        }
        onSwipeStart(event);
    });
    heroCarousel.addEventListener("pointermove", (event) => {
        if (!trackingSwipe || mouseSwipePointerId !== event.pointerId) return;
        onSwipeMove(event);
    });
    const finishMouseSwipe = (event) => {
        if (mouseSwipePointerId !== event.pointerId) return;
        heroCarousel.style.cursor = "";
        try {
            heroCarousel.releasePointerCapture(event.pointerId);
        } catch (error) {
            // Ignore browsers that do not support pointer capture here.
        }
        mouseSwipePointerId = null;
        onSwipeEnd();
    };
    heroCarousel.addEventListener("pointerup", finishMouseSwipe);
    heroCarousel.addEventListener("pointercancel", (event) => {
        if (mouseSwipePointerId !== event.pointerId) return;
        heroCarousel.style.cursor = "";
        mouseSwipePointerId = null;
        resetSwipe();
        startAutoplay();
    });
    heroCarousel.addEventListener("dragstart", (event) => event.preventDefault());
}

function wireKeyboardNavigation() {
    if (!heroCarousel || slides.length < 2) return;
    heroCarousel.setAttribute("tabindex", "0");
    heroCarousel.addEventListener("focusin", stopAutoplay);
    heroCarousel.addEventListener("focusout", startAutoplay);
    heroCarousel.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") {
            event.preventDefault();
            goToPreviousSlide();
        } else if (event.key === "ArrowRight") {
            event.preventDefault();
            goToNextSlide();
        }
    });
}

if (slides.length) {
    prevBtn?.addEventListener("click", goToPreviousSlide);
    nextBtn?.addEventListener("click", goToNextSlide);
    showSlide();
    startAutoplay();
    wireHoverPause();
    wireTouchSwipe();
    wireMouseSwipe();
    wireKeyboardNavigation();
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
    return `${Math.min(index, 10) * 52}ms`;
}

function revealElement(element) {
    element.classList.add("is-visible");
    window.setTimeout(() => {
        if (element.classList.contains("is-visible")) {
            element.style.willChange = "auto";
        }
    }, 560);
}

function ensureRevealObserver() {
    if (prefersReducedMotion) return null;
    if (revealObserver || !("IntersectionObserver" in window)) return revealObserver;
    revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            revealElement(entry.target);
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
            revealElement(element);
            return;
        }
        element.style.willChange = "opacity, transform";
        observer.observe(element);
    });
}

function initScrollReveal() {
    registerScrollReveal(document.querySelectorAll(".scroll-reveal"));
}

setTimeout(initScrollReveal, 30);
