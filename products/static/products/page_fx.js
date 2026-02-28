(function () {
    const root = document.documentElement;
    root.classList.add("fx-ready");

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const observed = new WeakSet();
    const prepared = new WeakSet();
    const autoSelectors = [
        { selector: "#productGrid > .card", kind: "card", stagger: 34 },
        { selector: ".product-grid > .card", kind: "card", stagger: 34 },
        { selector: "#categoryGrid > .category-card", kind: "card", stagger: 34 },
        { selector: ".category-grid > .category-card", kind: "card", stagger: 34 },
        { selector: "#cartList > .item-row", kind: "card", stagger: 26 },
        { selector: ".history-panel > .history-card", kind: "card", stagger: 26 },
        { selector: "#previewItems > .preview-item", kind: "card", stagger: 20 },
        { selector: "#ordersList > .order-card", kind: "card", stagger: 26 },
        { selector: "#relatedList > .related-item", kind: "card", stagger: 26 },
        { selector: "#buyCard > .product", kind: "card", stagger: 0 },
        { selector: "#productGrid > .empty", kind: "card", stagger: 0 },
        { selector: "#categoryGrid > .empty", kind: "card", stagger: 0 },
        { selector: "#cartList > .empty", kind: "card", stagger: 0 },
        { selector: "#ordersList > .empty-block", kind: "card", stagger: 0 },
        { selector: "#buyCard > .state", kind: "card", stagger: 0 }
    ];

    const observer = !prefersReducedMotion && "IntersectionObserver" in window
        ? new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting || entry.intersectionRatio > 0.08) {
                    reveal(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        }, {
            threshold: 0.08,
            rootMargin: "0px 0px -10% 0px"
        })
        : null;

    function reveal(node) {
        node.classList.add("is-fx-visible");
    }

    function getCollection(rootNode, selector) {
        const out = [];
        if (rootNode instanceof Element && rootNode.matches(selector)) {
            out.push(rootNode);
        }
        if (rootNode.querySelectorAll) {
            rootNode.querySelectorAll(selector).forEach((node) => out.push(node));
        }
        return out;
    }

    function prepare(node, index, kind, stagger) {
        if (!(node instanceof HTMLElement) || prepared.has(node)) {
            return;
        }
        prepared.add(node);
        node.classList.add("fx-auto");
        node.dataset.fxKind = kind || "block";
        const delay = Math.min(index * stagger, 180);
        node.style.setProperty("--fx-delay", `${delay}ms`);

        if (prefersReducedMotion) {
            reveal(node);
            return;
        }

        const rect = node.getBoundingClientRect();
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
        if (rect.top <= viewportHeight * 0.88) {
            requestAnimationFrame(() => reveal(node));
            return;
        }

        if (observer && !observed.has(node)) {
            observed.add(node);
            observer.observe(node);
        }
    }

    function scan(rootNode) {
        autoSelectors.forEach(({ selector, kind, stagger }) => {
            const matches = getCollection(rootNode, selector);
            matches.forEach((node, index) => prepare(node, index, kind, stagger));
        });
    }

    function hydrateStatic() {
        const staticNodes = document.querySelectorAll("[data-fx]");
        staticNodes.forEach((node, index) => {
            if (!(node instanceof HTMLElement)) {
                return;
            }
            node.style.setProperty("--fx-delay", `${Math.min(index * 42, 160)}ms`);
            if (prefersReducedMotion) {
                reveal(node);
                return;
            }
            const rect = node.getBoundingClientRect();
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
            if (rect.top <= viewportHeight * 0.92) {
                requestAnimationFrame(() => reveal(node));
                return;
            }
            if (observer && !observed.has(node)) {
                observed.add(node);
                observer.observe(node);
            }
        });
    }

    function init() {
        hydrateStatic();
        scan(document);

        const mutationObserver = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (!(node instanceof HTMLElement)) {
                        return;
                    }
                    scan(node);
                    if (node.hasAttribute("data-fx")) {
                        requestAnimationFrame(() => reveal(node));
                    }
                });
            });
        });

        mutationObserver.observe(document.body, {
            childList: true,
            subtree: true,
        });

        window.ThathwamasiPageFX = {
            scan,
            reveal,
        };
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }
})();
