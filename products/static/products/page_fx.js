(function () {
    const root = document.documentElement;
    root.classList.add("fx-ready");

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const observed = new WeakSet();
    const prepared = new WeakSet();
    const autoSelectors = [
        { selector: "#productGrid > .card", kind: "card", stagger: 32 },
        { selector: ".product-grid > .card", kind: "card", stagger: 32 },
        { selector: "#categoryGrid > .category-card", kind: "card", stagger: 30 },
        { selector: ".category-grid > .category-card", kind: "card", stagger: 30 },
        { selector: "#cartList > .item-row", kind: "card", stagger: 24 },
        { selector: ".history-panel > .history-card", kind: "card", stagger: 24 },
        { selector: "#previewItems > .preview-item", kind: "card", stagger: 18 },
        { selector: "#ordersList > .order-card", kind: "card", stagger: 24 },
        { selector: "#relatedList > .related-item", kind: "card", stagger: 22 },
        { selector: "#buyCard > .product", kind: "panel", stagger: 0 },
        { selector: "#productGrid > .empty", kind: "panel", stagger: 0 },
        { selector: "#categoryGrid > .empty", kind: "panel", stagger: 0 },
        { selector: "#cartList > .empty", kind: "panel", stagger: 0 },
        { selector: "#ordersList > .empty-block", kind: "panel", stagger: 0 },
        { selector: "#buyCard > .state", kind: "panel", stagger: 0 }
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
            rootMargin: "0px 0px -8% 0px"
        })
        : null;

    function resolveKind(node, fallbackKind) {
        const explicit = (node.getAttribute("data-fx") || "").trim();
        if (explicit && explicit !== "true") {
            return explicit;
        }
        return fallbackKind || node.dataset.fxKind || "block";
    }

    function releaseWillChange(node) {
        window.setTimeout(() => {
            if (node && node.classList && node.classList.contains("is-fx-visible")) {
                node.style.willChange = "auto";
            }
        }, 520);
    }

    function reveal(node) {
        node.classList.add("is-fx-visible");
        releaseWillChange(node);
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
        node.dataset.fxKind = resolveKind(node, kind);
        node.style.willChange = "opacity, transform";
        const delay = Math.min(index * stagger, 180);
        node.style.setProperty("--fx-delay", `${delay}ms`);

        if (prefersReducedMotion) {
            reveal(node);
            return;
        }

        const rect = node.getBoundingClientRect();
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
        if (rect.top <= viewportHeight * 0.9) {
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
            node.dataset.fxKind = resolveKind(node, node.dataset.fxKind || "panel");
            node.style.willChange = "opacity, transform";
            node.style.setProperty("--fx-delay", `${Math.min(index * 36, 150)}ms`);
            if (prefersReducedMotion) {
                reveal(node);
                return;
            }
            const rect = node.getBoundingClientRect();
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
            if (rect.top <= viewportHeight * 0.93) {
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
                        node.dataset.fxKind = resolveKind(node, node.dataset.fxKind || "panel");
                        node.style.willChange = "opacity, transform";
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
