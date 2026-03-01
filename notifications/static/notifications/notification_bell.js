(function () {
    const DEFAULT_POLL_MS = 8000;

    function esc(value) {
        return String(value || "")
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
    }

    function toHumanTime(raw) {
        if (!raw) return "";
        const dt = new Date(raw);
        if (Number.isNaN(dt.getTime())) return "";
        return dt.toLocaleString();
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    async function apiGet(url) {
        const resp = await fetch(url, { credentials: "same-origin" });
        const text = await resp.text();
        let data = {};
        try {
            data = text ? JSON.parse(text) : {};
        } catch (err) {
            throw new Error("Invalid server response");
        }
        if (!resp.ok) {
            throw new Error(data.detail || data.error || "Request failed");
        }
        return data;
    }

    async function apiPost(url, payload) {
        const headers = { "Content-Type": "application/json" };
        const csrfToken = getCookie("csrftoken");
        if (csrfToken) {
            headers["X-CSRFToken"] = csrfToken;
        }

        const resp = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers,
            body: JSON.stringify(payload),
        });
        const text = await resp.text();
        let data = {};
        try {
            data = text ? JSON.parse(text) : {};
        } catch (err) {
            throw new Error("Invalid server response");
        }
        if (!resp.ok) {
            throw new Error(data.detail || data.error || "Request failed");
        }
        return data;
    }

    class NotificationWidget {
        constructor(options) {
            this.options = options || {};
            this.mode = this.options.mode === "ADMIN" ? "ADMIN" : "USER";
            this.storageKey = this.options.storageKey || "thathwamasi_checkout_phone";
            this.pollMs = Number(this.options.pollMs || DEFAULT_POLL_MS);
            this.latestId = null;
            this.isOpen = false;
            this.items = [];
            this.unreadCount = 0;
            this.root = null;
            this.countEl = null;
            this.panelEl = null;
            this.listEl = null;
        }

        getIdentifier(promptIfMissing = false) {
            if (this.mode === "ADMIN") {
                return "";
            }

            let value = "";
            if (typeof this.options.resolveIdentifier === "function") {
                value = String(this.options.resolveIdentifier() || "").trim();
            }
            if (!value && this.storageKey) {
                value = String(localStorage.getItem(this.storageKey) || "").trim();
            }

            if (!value && promptIfMissing) {
                value = String(prompt("Enter phone to view notifications") || "").trim();
                if (value && this.storageKey) {
                    localStorage.setItem(this.storageKey, value);
                }
            }

            return value;
        }

        buildQueryParams(promptIfMissing = false) {
            const params = new URLSearchParams({ recipient_type: this.mode });
            const identifier = this.getIdentifier(promptIfMissing);
            if (identifier) {
                params.set("recipient_identifier", identifier);
            }
            return { params, identifier };
        }

        buildRecipientPayload(promptIfMissing = false) {
            const { identifier } = this.buildQueryParams(promptIfMissing);
            const payload = { recipient_type: this.mode };
            if (identifier) {
                payload.recipient_identifier = identifier;
            }
            return { payload, identifier };
        }

        mount() {
            if (this.root) return;

            const root = document.createElement("div");
            root.className = "thn-root";
            root.innerHTML = `
                <button type="button" class="thn-btn" title="Notifications" aria-label="Notifications">
                    🔔
                    <span class="thn-count">0</span>
                </button>
                <section class="thn-panel" aria-live="polite">
                    <header class="thn-head">
                        <h3>Notifications</h3>
                        <button type="button" class="thn-mark-all">Mark all read</button>
                    </header>
                    <div class="thn-list"></div>
                </section>
            `;

            document.body.appendChild(root);

            this.root = root;
            this.countEl = root.querySelector(".thn-count");
            this.panelEl = root.querySelector(".thn-panel");
            this.listEl = root.querySelector(".thn-list");

            root.querySelector(".thn-btn").addEventListener("click", () => this.togglePanel());
            root.querySelector(".thn-mark-all").addEventListener("click", () => this.markAllRead());

            document.addEventListener("click", (event) => {
                if (!this.root || !this.isOpen) return;
                if (!this.root.contains(event.target)) {
                    this.closePanel();
                }
            });

            this.refreshCount();
            setInterval(() => this.refreshCount(), this.pollMs);
        }

        renderCount() {
            if (!this.countEl) return;
            const count = Number(this.unreadCount || 0);
            this.countEl.textContent = count > 99 ? "99+" : String(count);
            this.countEl.style.display = count > 0 ? "inline-block" : "none";
        }

        renderProducts(items) {
            if (!Array.isArray(items) || !items.length) {
                return "";
            }
            return `
                <div class="thn-products">
                    ${items
                        .map(
                            (row) => `
                            <div class="thn-product">
                                <span class="thn-product-name">${esc(row.product_name)}</span>
                                <span class="thn-product-meta">Qty ${esc(row.quantity)} | Rs ${esc(row.price)}</span>
                            </div>
                        `
                        )
                        .join("")}
                </div>
            `;
        }

        buildActionButton(payload) {
            if (!payload || typeof payload !== "object") return "";

            if (this.mode === "USER") {
                const downloadUrl = String(payload.download_url || "").trim();
                if (!downloadUrl) return "";
                return `<a class="thn-action-btn" href="${esc(downloadUrl)}" target="_blank" rel="noopener">Download</a>`;
            }

            const fallbackBillUrl = payload.admin_bill_id
                ? `/admin-dashboard/billing/${payload.admin_bill_id}/`
                : "/admin-dashboard/billing/";
            const billUrl = String(payload.bill_url || fallbackBillUrl).trim();
            return `<a class="thn-action-btn" href="${esc(billUrl)}">Bill</a>`;
        }

        renderReceipt(item) {
            const payload = item && item.payload && typeof item.payload === "object" ? item.payload : {};
            const customerName = payload.customer_name || "N/A";
            const totalPrice = payload.total_price || "-";
            const phoneLabel = this.mode === "ADMIN" ? "Customer Phone" : "Delivery Contact";
            const phoneValue =
                this.mode === "ADMIN"
                    ? payload.customer_phone || "-"
                    : payload.owner_phone || "-";

            const productHtml = this.renderProducts(payload.items);
            const actionBtn = this.buildActionButton(payload);
            const fallbackMessage = !productHtml
                ? `<p class="thn-item-msg">${esc(item.message || "")}</p>`
                : "";

            return `
                <article class="thn-item ${item.is_read ? "" : "unread"}" data-id="${item.id}">
                    <p class="thn-item-title">${esc(item.title)}</p>
                    <p class="thn-item-time">${esc(toHumanTime(item.created_at))}</p>

                    <div class="thn-receipt">
                        <div class="thn-meta-row"><span>Customer</span><strong>${esc(customerName)}</strong></div>
                        ${productHtml}
                        <div class="thn-meta-row"><span>Total Price</span><strong>Rs ${esc(totalPrice)}</strong></div>
                        <div class="thn-meta-row"><span>${esc(phoneLabel)}</span><strong>${esc(phoneValue)}</strong></div>
                        ${fallbackMessage}
                        ${
                            actionBtn
                                ? `<div class="thn-actions">${actionBtn}</div>`
                                : ""
                        }
                    </div>
                </article>
            `;
        }

        renderList() {
            if (!this.listEl) return;

            if (this.mode === "USER" && !this.getIdentifier(false)) {
                this.listEl.innerHTML = `
                    <div class="thn-empty">
                        Add your phone number to view notifications.
                        <br />
                        <button type="button" data-thn-action="set-phone">Set Phone</button>
                    </div>
                `;
                const setBtn = this.listEl.querySelector("[data-thn-action='set-phone']");
                setBtn?.addEventListener("click", async () => {
                    this.getIdentifier(true);
                    await this.loadFeed();
                    await this.refreshCount();
                });
                return;
            }

            if (!this.items.length) {
                this.listEl.innerHTML = '<div class="thn-empty">No notifications yet.</div>';
                return;
            }

            this.listEl.innerHTML = this.items.map((item) => this.renderReceipt(item)).join("");

            this.listEl.querySelectorAll(".thn-item").forEach((node) => {
                node.addEventListener("click", (event) => {
                    if (event.target.closest(".thn-action-btn")) {
                        return;
                    }
                    const id = Number(node.dataset.id);
                    if (id) this.markRead([id]);
                });
            });
        }

        async refreshCount() {
            try {
                const { params, identifier } = this.buildQueryParams(false);
                if (this.mode === "USER" && !identifier) {
                    this.unreadCount = 0;
                    this.renderCount();
                    return;
                }

                const data = await apiGet(`/api/notifications/unread-count/?${params.toString()}`);
                this.unreadCount = Number(data.unread_count || 0);
                this.latestId = data.latest_id || this.latestId;
                this.renderCount();
            } catch (err) {
                // keep existing UI state
            }
        }

        async loadFeed() {
            try {
                const { params, identifier } = this.buildQueryParams(false);
                if (this.mode === "USER" && !identifier) {
                    this.items = [];
                    this.renderList();
                    return;
                }

                params.set("limit", "30");
                const data = await apiGet(`/api/notifications/feed/?${params.toString()}`);
                this.items = Array.isArray(data.notifications) ? data.notifications : [];
                this.unreadCount = Number(data.unread_count || 0);
                this.latestId = data.latest_id || this.latestId;
                this.renderCount();
                this.renderList();
            } catch (err) {
                this.listEl.innerHTML = `<div class="thn-empty">Unable to load notifications: ${esc(err.message)}</div>`;
            }
        }

        async markRead(ids) {
            if (!Array.isArray(ids) || !ids.length) return;

            try {
                const { payload, identifier } = this.buildRecipientPayload(false);
                if (this.mode === "USER" && !identifier) {
                    return;
                }

                payload.notification_ids = ids;
                const data = await apiPost("/api/notifications/mark-read/", payload);
                this.unreadCount = Number(data.unread_count || 0);
                this.items = this.items.map((item) =>
                    ids.includes(Number(item.id)) ? { ...item, is_read: true, status: "READ" } : item
                );
                this.renderCount();
                this.renderList();
            } catch (err) {
                // ignore mark-read failure in UI
            }
        }

        async markAllRead() {
            try {
                const { payload, identifier } = this.buildRecipientPayload(false);
                if (this.mode === "USER" && !identifier) {
                    return;
                }

                await apiPost("/api/notifications/mark-all-read/", payload);
                this.unreadCount = 0;
                this.items = this.items.map((item) => ({ ...item, is_read: true, status: "READ" }));
                this.renderCount();
                this.renderList();
            } catch (err) {
                // ignore mark-all failure in UI
            }
        }

        async togglePanel() {
            if (!this.panelEl) return;
            this.isOpen = !this.isOpen;
            if (this.isOpen) {
                this.panelEl.classList.add("open");
                await this.loadFeed();
                if (this.unreadCount > 0) {
                    await this.markAllRead();
                }
            } else {
                this.closePanel();
            }
        }

        closePanel() {
            this.isOpen = false;
            this.panelEl?.classList.remove("open");
        }
    }

    window.ThathwamasiNotifications = {
        mount(options) {
            const widget = new NotificationWidget(options || {});
            widget.mount();
            return widget;
        },
    };
})();
