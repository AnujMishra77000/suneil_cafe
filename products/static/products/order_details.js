const state = {
    phone: "",
    orders: [],
    activeOrderId: null,
};

let isLoadingOrders = false;

const phoneInputEl = document.getElementById("orderPhoneInput");
const loadBtnEl = document.getElementById("loadOrdersBtn");
const pageStatusEl = document.getElementById("pageStatus");
const ordersListEl = document.getElementById("ordersList");
const feedbackModalEl = document.getElementById("feedbackModal");
const feedbackFormEl = document.getElementById("feedbackForm");
const feedbackTitleEl = document.getElementById("feedbackTitle");
const feedbackRatingEl = document.getElementById("feedbackRating");
const feedbackMessageEl = document.getElementById("feedbackMessage");
const feedbackStatusEl = document.getElementById("feedbackStatus");
const feedbackCancelBtnEl = document.getElementById("feedbackCancelBtn");

function readSavedPhone() {
    return (
        localStorage.getItem("thathwamasi_checkout_phone") ||
        localStorage.getItem("thathwamasi_cart_phone") ||
        ""
    ).trim();
}

function savePhone(phone) {
    const clean = String(phone || "").trim();
    state.phone = clean;
    if (clean) {
        localStorage.setItem("thathwamasi_checkout_phone", clean);
    }
}

function setPageStatus(message, type = "error") {
    pageStatusEl.textContent = message || "";
    pageStatusEl.classList.remove("ok");
    if (type === "ok") {
        pageStatusEl.classList.add("ok");
    }
}

function setFeedbackStatus(message, type = "error") {
    feedbackStatusEl.textContent = message || "";
    feedbackStatusEl.classList.remove("ok");
    if (type === "ok") {
        feedbackStatusEl.classList.add("ok");
    }
}

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatDateTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleString();
}

function ratingToStars(rating) {
    const n = Number(rating || 0);
    if (!Number.isFinite(n) || n < 1) return "☆☆☆☆☆";
    const safe = Math.min(5, Math.max(1, Math.round(n)));
    return `${"★".repeat(safe)}${"☆".repeat(5 - safe)}`;
}

function resolveApiError(data, fallback = "Request failed") {
    if (!data || typeof data !== "object") return fallback;
    if (typeof data.error === "string" && data.error.trim()) return data.error;
    if (typeof data.detail === "string" && data.detail.trim()) return data.detail;

    for (const key of Object.keys(data)) {
        const value = data[key];
        if (typeof value === "string" && value.trim()) return value;
        if (Array.isArray(value) && value.length && typeof value[0] === "string") return value[0];
        if (value && typeof value === "object") {
            const nested = Object.values(value)[0];
            if (typeof nested === "string" && nested.trim()) return nested;
            if (Array.isArray(nested) && nested.length && typeof nested[0] === "string") return nested[0];
        }
    }

    return fallback;
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
    if (!res.ok) throw new Error(resolveApiError(data, `Request failed (${res.status})`));
    return data;
}

async function apiPost(url, payload) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    const raw = await res.text();
    let data;
    try {
        data = raw ? JSON.parse(raw) : {};
    } catch (err) {
        throw new Error(`Server returned non-JSON response (${res.status}).`);
    }
    if (!res.ok) throw new Error(resolveApiError(data, `Request failed (${res.status})`));
    return data;
}

function buildItemsRows(items) {
    const safeItems = Array.isArray(items) ? items : [];
    if (!safeItems.length) {
        return '<div class="items-row"><span>No product items found.</span></div>';
    }

    const lines = safeItems
        .map(
            (item) => `
            <div class="items-row">
                <span>${escapeHtml(item.product_name)}</span>
                <span>${escapeHtml(item.quantity)}</span>
                <span>Rs ${escapeHtml(item.price)}</span>
            </div>
        `
        )
        .join("");

    return `
        <div class="items-row head">
            <span>Product</span>
            <span>Qty</span>
            <span>Price</span>
        </div>
        ${lines}
    `;
}

function renderOrders() {
    if (!state.orders.length) {
        ordersListEl.innerHTML = '<div class="empty-block">No orders found for this number.</div>';
        return;
    }

    ordersListEl.innerHTML = state.orders
        .map((order) => {
            const feedback = order.feedback || null;
            const feedbackStars = ratingToStars(feedback?.rating);
            const feedbackText = feedback?.message || "No feedback submitted yet.";
            const feedbackDate = feedback?.updated_at ? formatDateTime(feedback.updated_at) : "";
            const feedbackAction = feedback ? "Edit Feedback" : "Give Feedback";

            return `
                <article class="order-card" data-order-id="${order.id}">
                    <div class="order-head">
                        <div>
                            <div class="order-id">Order #${order.id}</div>
                            <div class="order-meta">${escapeHtml(order.status)} | ${escapeHtml(
                formatDateTime(order.created_at)
            )}</div>
                        </div>
                        <div class="order-id">Rs ${escapeHtml(order.total_price)}</div>
                    </div>

                    <div class="items-table">
                        ${buildItemsRows(order.items)}
                    </div>

                    <div class="order-feedback">
                        <div class="feedback-stars">${feedbackStars}</div>
                        <p class="feedback-text">${escapeHtml(feedbackText)}</p>
                        <div class="feedback-date">${escapeHtml(feedbackDate)}</div>
                    </div>

                    <div class="order-actions">
                        <a href="/order-details/?feedback=${order.id}" class="feedback-open-btn" data-open-feedback="${order.id}">${feedbackAction}</a>
                    </div>
                </article>
            `;
        })
        .join("");
}

function findOrder(orderId) {
    const id = Number(orderId);
    if (!id) return null;
    return state.orders.find((order) => Number(order.id) === id) || null;
}

function clearFeedbackQuery() {
    const url = new URL(window.location.href);
    url.searchParams.delete("feedback");
    window.history.replaceState({}, "", `${url.pathname}${url.search}`);
}

function openFeedbackModal(orderId, updateQuery = true) {
    const order = findOrder(orderId);
    if (!order) {
        setPageStatus("Order not found for feedback window.");
        return;
    }

    state.activeOrderId = Number(order.id);
    const feedback = order.feedback || null;

    feedbackTitleEl.textContent = `Feedback for Order #${order.id}`;
    feedbackRatingEl.value = feedback?.rating ? String(feedback.rating) : "";
    feedbackMessageEl.value = feedback?.message || "";
    setFeedbackStatus("");

    feedbackModalEl.classList.remove("hidden");
    if (updateQuery) {
        const url = new URL(window.location.href);
        url.searchParams.set("feedback", String(order.id));
        window.history.replaceState({}, "", `${url.pathname}${url.search}`);
    }
}

function closeFeedbackModal(clearQuery = true) {
    feedbackModalEl.classList.add("hidden");
    state.activeOrderId = null;
    if (clearQuery) {
        clearFeedbackQuery();
    }
}

async function loadOrders() {
    if (isLoadingOrders) return;

    const phone = (phoneInputEl.value || "").trim();
    if (!phone) {
        setPageStatus("Please enter your phone number.");
        return;
    }

    isLoadingOrders = true;
    if (loadBtnEl) {
        loadBtnEl.disabled = true;
        loadBtnEl.textContent = "Loading...";
    }

    savePhone(phone);
    setPageStatus("Loading orders...", "ok");

    try {
        const payload = await apiGet("/api/orders/history-by-phone/?phone=" + encodeURIComponent(phone));
        state.orders = Array.isArray(payload.orders) ? payload.orders : [];
        renderOrders();

        if (!state.orders.length) {
            setPageStatus("No orders found for this number.");
            return;
        }

        setPageStatus("Loaded " + state.orders.length + " orders.", "ok");

        const params = new URLSearchParams(window.location.search);
        const feedbackOrderId = params.get("feedback");
        if (feedbackOrderId) {
            openFeedbackModal(feedbackOrderId, false);
        }
    } catch (err) {
        state.orders = [];
        renderOrders();
        setPageStatus(err.message || "Unable to load orders.");
    } finally {
        isLoadingOrders = false;
        if (loadBtnEl) {
            loadBtnEl.disabled = false;
            loadBtnEl.textContent = "Load Orders";
        }
    }
}

async function submitFeedback(event) {
    event.preventDefault();
    if (!state.activeOrderId) {
        setFeedbackStatus("Order not selected.");
        return;
    }

    const message = (feedbackMessageEl.value || "").trim();
    const ratingValue = (feedbackRatingEl.value || "").trim();

    if (message.length < 3) {
        setFeedbackStatus("Please enter at least 3 characters.");
        return;
    }

    const phone = (state.phone || phoneInputEl.value || "").trim();
    if (!phone) {
        setFeedbackStatus("Please set your phone number first.");
        return;
    }

    const submitBtn = feedbackFormEl.querySelector(".feedback-submit-btn");
    if (submitBtn) submitBtn.disabled = true;
    setFeedbackStatus("Saving feedback...", "ok");

    try {
        const payload = {
            order_id: state.activeOrderId,
            phone,
            message,
            rating: ratingValue ? Number(ratingValue) : null,
        };
        const res = await apiPost("/api/orders/feedback/", payload);
        const updatedFeedback = res.feedback || {};

        state.orders = state.orders.map((order) => {
            if (Number(order.id) !== Number(state.activeOrderId)) return order;
            return {
                ...order,
                feedback: {
                    ...(order.feedback || {}),
                    ...updatedFeedback,
                },
            };
        });

        renderOrders();
        setPageStatus("Feedback submitted successfully.", "ok");
        closeFeedbackModal();
    } catch (err) {
        setFeedbackStatus(err.message || "Unable to submit feedback.");
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}

function onOrdersListClick(event) {
    const trigger = event.target.closest("[data-open-feedback]");
    if (!trigger) return;

    event.preventDefault();
    const orderId = trigger.getAttribute("data-open-feedback");
    openFeedbackModal(orderId, true);
}

function bootstrap() {
    const savedPhone = readSavedPhone();
    if (savedPhone) {
        savePhone(savedPhone);
        phoneInputEl.value = savedPhone;
        loadOrders().catch(() => {});
    } else {
        renderOrders();
        setPageStatus("Enter phone number to load your order history.");
    }
}

loadBtnEl.addEventListener("click", function () {
    loadOrders().catch(() => {});
});

phoneInputEl.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
        event.preventDefault();
        loadOrders().catch(() => {});
    }
});

ordersListEl.addEventListener("click", onOrdersListClick);
feedbackFormEl.addEventListener("submit", submitFeedback);

feedbackCancelBtnEl.addEventListener("click", function () {
    closeFeedbackModal();
});

feedbackModalEl.addEventListener("click", function (event) {
    if (event.target === feedbackModalEl) {
        closeFeedbackModal();
    }
});

document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !feedbackModalEl.classList.contains("hidden")) {
        closeFeedbackModal();
    }
});

bootstrap();
