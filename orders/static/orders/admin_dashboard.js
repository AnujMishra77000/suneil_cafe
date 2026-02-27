const rangeEl = document.getElementById('rangeSelect');
const summaryCards = document.getElementById('summaryCards');
const ordersTable = document.getElementById('ordersTable');
const productQuery = document.getElementById('productQuery');
const searchBtn = document.getElementById('searchBtn');
const productList = document.getElementById('productList');
const alertBox = document.getElementById('alertBox');
const exportSalesCsvBtn = document.getElementById('exportSalesCsvBtn');
const exportSalesExcelBtn = document.getElementById('exportSalesExcelBtn');
const exportOrdersCsvBtn = document.getElementById('exportOrdersCsvBtn');
const exportOrdersExcelBtn = document.getElementById('exportOrdersExcelBtn');

let topChart, growthChart, categoryChart, lastOrderId = 0, audioCtx;

function ensureAudio() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
}

function beep() {
    try {
        ensureAudio();
        const o = audioCtx.createOscillator();
        const g = audioCtx.createGain();
        o.connect(g);
        g.connect(audioCtx.destination);
        o.type = 'sine';
        o.frequency.value = 880;
        g.gain.value = 0.05;
        o.start();
        setTimeout(() => o.stop(), 220);
    } catch {}
}

function pop(msg) {
    if (!alertBox) return;
    alertBox.textContent = msg;
    alertBox.style.display = 'block';
    setTimeout(() => { alertBox.style.display = 'none'; }, 2300);
}

async function api(url) {
    const r = await fetch(url, { credentials: 'include' });
    if (!r.ok) throw new Error('Request failed');
    return r.json();
}

function animateNumber(from, to, onTick, duration = 540) {
    const start = performance.now();
    const diff = to - from;
    function frame(now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        onTick(from + diff * eased);
        if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
}

function card(label, value) {
    return `<article class="card"><h3>${label}</h3><strong data-value="${value}">0</strong></article>`;
}

function renderSummary(summary) {
    const revenue = Number(summary.total_revenue || 0);
    const qty = Number(summary.total_quantity || 0);
    const products = Number(summary.total_products || 0);

    summaryCards.innerHTML = [
        card('Revenue', revenue),
        card('Quantity', qty),
        card('Products', products),
        `<article class="card"><h3>Range</h3><strong>${rangeEl.value}</strong></article>`
    ].join('');

    const vals = summaryCards.querySelectorAll('strong[data-value]');
    vals.forEach((el, idx) => {
        const target = Number(el.dataset.value || 0);
        setTimeout(() => {
            animateNumber(0, target, (n) => {
                if (idx === 0) {
                    el.textContent = `Rs ${Math.round(n)}`;
                } else {
                    el.textContent = `${Math.round(n)}`;
                }
            });
        }, idx * 70);
    });
}

function renderOrders(orders) {
    ordersTable.innerHTML = orders.map((o, i) => `
        <div class="item" style="animation-delay:${Math.min(i, 10) * 40}ms;">
            <strong>#${o.id} ${o.customer_name}</strong>
            <span class="muted">${o.phone}</span>
            <div class="muted">${o.shipping_address}</div>
            <div>Total: Rs ${o.total_price} | ${o.status}</div>
            <div class="muted">${o.items.map((x) => `${x.product_name} x${x.quantity} @ Rs ${x.price}`).join(' , ')}</div>
        </div>
    `).join('');
}

function buildOrUpdateChart(ctx, chart, labels, data, label) {
    if (chart) {
        chart.data.labels = labels;
        chart.data.datasets[0].data = data;
        chart.update();
        return chart;
    }
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label,
                data,
                borderColor: '#5a2e16',
                backgroundColor: 'rgba(90,46,22,.18)',
                fill: true,
                tension: 0.34,
                pointRadius: 2,
            }],
        },
        options: { responsive: true, maintainAspectRatio: false },
    });
}

function buildOrUpdateBar(ctx, chart, labels, data, label) {
    if (chart) {
        chart.data.labels = labels;
        chart.data.datasets[0].data = data;
        chart.update();
        return chart;
    }
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ label, data, backgroundColor: '#8b5a3c', borderRadius: 6 }],
        },
        options: { responsive: true, maintainAspectRatio: false },
    });
}

async function loadAnalytics() {
    const data = await api(`/api/orders/admin/dashboard/analytics/?range=${encodeURIComponent(rangeEl.value)}`);
    renderSummary(data.summary || {});

    const gLabels = (data.growth || []).map((x) => x.day);
    const gVals = (data.growth || []).map((x) => Number(x.revenue || 0));
    growthChart = buildOrUpdateChart(document.getElementById('growthChart'), growthChart, gLabels, gVals, 'Revenue');

    const tLabels = (data.top_products || []).map((x) => x.product_name);
    const tVals = (data.top_products || []).map((x) => Number(x.total_qty || 0));
    topChart = buildOrUpdateBar(document.getElementById('topChart'), topChart, tLabels, tVals, 'Qty Sold');

    const cLabels = (data.category_sales || []).map((x) => x.category);
    const cVals = (data.category_sales || []).map((x) => Number(x.total_sales || 0));
    categoryChart = buildOrUpdateBar(document.getElementById('categoryChart'), categoryChart, cLabels, cVals, 'Category Sales');
}

async function loadOrders() {
    const data = await api('/api/orders/admin/dashboard/orders/?limit=20');
    const orders = data.orders || [];
    renderOrders(orders);
    if (orders.length) lastOrderId = Math.max(lastOrderId, Number(orders[0].id || 0));
}

async function checkNewOrder() {
    try {
        const d = await api(`/api/orders/admin/dashboard/order-alert/?last_id=${lastOrderId}`);
        if (d.has_new) {
            beep();
            pop('New order received');
            await loadOrders();
        }
        lastOrderId = Math.max(lastOrderId, Number(d.latest_id || 0));
    } catch {}
}

async function searchProducts() {
    const q = productQuery.value.trim();
    if (!q) {
        productList.innerHTML = '';
        return;
    }
    const d = await api(`/api/orders/admin/dashboard/product-search/?q=${encodeURIComponent(q)}`);
    const items = d.items || [];
    productList.innerHTML = items.map((p, i) => `
        <div class="item" style="animation-delay:${Math.min(i, 10) * 35}ms;">
            ${p.image ? `<img src="${p.image}" alt="${p.name}" style="width:56px;height:56px;object-fit:cover;border-radius:6px;float:right;">` : ''}
            <strong>${p.name}</strong>
            <span class="muted">${p.section} / ${p.category}</span>
            <div>Rs ${p.price} | Stock ${p.stock_qty}</div>
        </div>
    `).join('');
}

rangeEl.addEventListener('change', loadAnalytics);
searchBtn.addEventListener('click', searchProducts);
productQuery.addEventListener('keydown', (e) => { if (e.key === 'Enter') searchProducts(); });

exportSalesCsvBtn.addEventListener('click', () => {
    window.location.href = `/api/orders/admin/dashboard/export/sales/?range=${encodeURIComponent(rangeEl.value)}&format=csv`;
});
exportSalesExcelBtn.addEventListener('click', () => {
    window.location.href = `/api/orders/admin/dashboard/export/sales/?range=${encodeURIComponent(rangeEl.value)}&format=excel`;
});
exportOrdersCsvBtn.addEventListener('click', () => {
    window.location.href = `/api/orders/admin/dashboard/export/orders/?range=${encodeURIComponent(rangeEl.value)}&format=csv`;
});
exportOrdersExcelBtn.addEventListener('click', () => {
    window.location.href = `/api/orders/admin/dashboard/export/orders/?range=${encodeURIComponent(rangeEl.value)}&format=excel`;
});

(async function boot() {
    await loadAnalytics();
    await loadOrders();
    setInterval(checkNewOrder, 5000);
})();
