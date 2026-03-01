const continueShoppingBtnEl = document.getElementById("continueShoppingBtn");
const orderIdTextEl = document.getElementById("orderIdText");

function resolvedContinueShoppingUrl() {
    const fallback = "/bakery/";
    const stored = (localStorage.getItem("thathwamasi_continue_shopping_url") || "").trim();
    if (!stored) return fallback;

    try {
        const url = new URL(stored, window.location.origin);
        if (url.origin !== window.location.origin) return fallback;
        if (/^\/(billing|checkout|order-success)\/?$/i.test(url.pathname)) return fallback;
        return `${url.pathname}${url.search}` || fallback;
    } catch {
        return fallback;
    }
}

function hydrateOrderId() {
    const bodyOrderId = (document.body.dataset.orderId || "").trim();
    const fallbackOrderId = (localStorage.getItem("thathwamasi_last_order_id") || "").trim();
    const orderId = bodyOrderId || fallbackOrderId;
    if (!orderIdTextEl) return;
    if (!orderId) {
        orderIdTextEl.classList.add("hidden");
        return;
    }
    orderIdTextEl.textContent = `Order ID: #${orderId}`;
    orderIdTextEl.classList.remove("hidden");
}

function bootstrap() {
    if (continueShoppingBtnEl) {
        continueShoppingBtnEl.href = resolvedContinueShoppingUrl();
    }
    hydrateOrderId();
}

bootstrap();
