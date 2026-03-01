const continueShoppingBtnEl = document.getElementById("continueShoppingBtn");

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

function bootstrap() {
    if (continueShoppingBtnEl) {
        continueShoppingBtnEl.href = resolvedContinueShoppingUrl();
    }
}

bootstrap();
