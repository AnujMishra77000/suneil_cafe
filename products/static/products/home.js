const slides = Array.from(document.querySelectorAll(".slide"));
const dotsWrap = document.getElementById("carouselDots");
const prevBtn = document.getElementById("heroPrev");
const nextBtn = document.getElementById("heroNext");
const heroCarousel = document.getElementById("heroCarousel");
const offersSwiperRoot = document.querySelector("[data-offers-swiper]");
const offersViewport = offersSwiperRoot?.querySelector("[data-offers-viewport]");
const offersTrack = offersSwiperRoot?.querySelector("[data-offers-track]");
const offersPrevBtn = offersSwiperRoot?.querySelector("[data-offers-prev]");
const offersNextBtn = offersSwiperRoot?.querySelector("[data-offers-next]");
const offersDotsWrap = offersSwiperRoot?.querySelector("[data-offers-dots]");
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
const OFFERS_AUTOPLAY_MS = 3600;
const OFFERS_SWIPE_THRESHOLD = 36;
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

function initOffersSwiper() {
    if (!offersSwiperRoot || !offersViewport || !offersTrack) return;

    const offerSlides = Array.from(offersTrack.querySelectorAll(".offer-slide"));
    if (!offerSlides.length) return;

    let offerIndex = 0;
    let offerMaxIndex = 0;
    let offerStep = 0;
    let offerAutoplayId = null;
    let offerTouchStartX = 0;
    let offerTouchDeltaX = 0;
    let offerTrackingSwipe = false;
    let hasMultipleSteps = false;

    function renderOfferDots() {
        if (!offersDotsWrap) return;
        offersDotsWrap.innerHTML = "";
        if (!hasMultipleSteps) return;
        for (let index = 0; index <= offerMaxIndex; index += 1) {
            const dot = document.createElement("button");
            dot.type = "button";
            dot.ariaLabel = `Go to offer ${index + 1}`;
            if (index === offerIndex) dot.classList.add("active");
            dot.addEventListener("click", () => goToOffer(index));
            offersDotsWrap.appendChild(dot);
        }
    }

    function computeOfferMetrics() {
        const firstSlide = offerSlides[0];
        if (!firstSlide) return;
        const slideRect = firstSlide.getBoundingClientRect();
        const trackStyles = window.getComputedStyle(offersTrack);
        const gap = Number.parseFloat(trackStyles.columnGap || trackStyles.gap || "0") || 0;
        const viewportWidth = offersViewport.getBoundingClientRect().width;

        offerStep = slideRect.width + gap;
        const visibleCount = offerStep > 0 ? Math.max(1, Math.floor((viewportWidth + gap) / offerStep)) : 1;
        offerMaxIndex = Math.max(0, offerSlides.length - visibleCount);
        hasMultipleSteps = offerMaxIndex > 0;
        offersSwiperRoot.classList.toggle("is-single", !hasMultipleSteps);

        if (offerIndex > offerMaxIndex) {
            offerIndex = offerMaxIndex;
        }
    }

    function renderOffers() {
        const translateX = offerStep > 0 ? offerIndex * offerStep : 0;
        offersTrack.style.transform = `translate3d(-${translateX}px, 0, 0)`;
        renderOfferDots();
    }

    function stopOfferAutoplay() {
        if (!offerAutoplayId) return;
        clearInterval(offerAutoplayId);
        offerAutoplayId = null;
    }

    function startOfferAutoplay() {
        stopOfferAutoplay();
        if (!hasMultipleSteps || prefersReducedMotion) return;
        offerAutoplayId = setInterval(() => {
            offerIndex = offerIndex >= offerMaxIndex ? 0 : offerIndex + 1;
            renderOffers();
        }, OFFERS_AUTOPLAY_MS);
    }

    function goToOffer(index) {
        if (!hasMultipleSteps) return;
        if (index > offerMaxIndex) {
            offerIndex = 0;
        } else if (index < 0) {
            offerIndex = offerMaxIndex;
        } else {
            offerIndex = index;
        }
        renderOffers();
        startOfferAutoplay();
    }

    function onOfferSwipeStart(point) {
        offerTouchStartX = point.clientX;
        offerTouchDeltaX = 0;
        offerTrackingSwipe = true;
        stopOfferAutoplay();
    }

    function onOfferSwipeMove(point) {
        if (!offerTrackingSwipe) return;
        offerTouchDeltaX = point.clientX - offerTouchStartX;
    }

    function onOfferSwipeEnd() {
        if (!offerTrackingSwipe) return;
        if (Math.abs(offerTouchDeltaX) >= OFFERS_SWIPE_THRESHOLD) {
            if (offerTouchDeltaX < 0) {
                goToOffer(offerIndex + 1);
            } else {
                goToOffer(offerIndex - 1);
            }
        } else {
            startOfferAutoplay();
        }
        offerTrackingSwipe = false;
        offerTouchStartX = 0;
        offerTouchDeltaX = 0;
    }

    offersPrevBtn?.addEventListener("click", () => goToOffer(offerIndex - 1));
    offersNextBtn?.addEventListener("click", () => goToOffer(offerIndex + 1));

    offersSwiperRoot.addEventListener("mouseenter", stopOfferAutoplay);
    offersSwiperRoot.addEventListener("mouseleave", startOfferAutoplay);

    offersViewport.addEventListener("touchstart", (event) => {
        if (!hasMultipleSteps || !event.touches.length) return;
        onOfferSwipeStart(event.touches[0]);
    }, { passive: true });

    offersViewport.addEventListener("touchmove", (event) => {
        if (!hasMultipleSteps || !event.touches.length) return;
        onOfferSwipeMove(event.touches[0]);
    }, { passive: true });

    offersViewport.addEventListener("touchend", onOfferSwipeEnd);
    offersViewport.addEventListener("touchcancel", () => {
        offerTrackingSwipe = false;
        startOfferAutoplay();
    });

    const reflowOffers = () => {
        computeOfferMetrics();
        renderOffers();
        startOfferAutoplay();
    };

    if ("ResizeObserver" in window) {
        const resizeObserver = new ResizeObserver(reflowOffers);
        resizeObserver.observe(offersViewport);
    } else {
        window.addEventListener("resize", reflowOffers);
    }

    document.addEventListener("visibilitychange", () => {
        if (document.hidden) {
            stopOfferAutoplay();
        } else {
            startOfferAutoplay();
        }
    });

    computeOfferMetrics();
    renderOffers();
    startOfferAutoplay();
}

initOffersSwiper();

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
