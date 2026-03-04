(function () {
    const root = document.querySelector("[data-customer-menu]");
    if (!root) return;

    const toggle = root.querySelector("[data-menu-toggle]");
    const panel = root.querySelector("[data-menu-panel]");

    function normalizePath(path) {
        const value = String(path || "").trim();
        if (!value || value === "/") return "/";
        return value.endsWith("/") ? value : value + "/";
    }

    function markActiveLinks() {
        const current = normalizePath(window.location.pathname);
        const links = root.querySelectorAll("a[href]");
        links.forEach((link) => {
            const href = normalizePath(link.getAttribute("href"));
            if (href === current) {
                link.classList.add("active");
            } else {
                link.classList.remove("active");
            }
        });
    }

    function positionPanel() {
        if (!toggle || !panel) return;
        const toggleRect = toggle.getBoundingClientRect();
        const panelWidth = Math.min(panel.offsetWidth || 212, window.innerWidth - 12);
        const right = Math.max(8, Math.round(window.innerWidth - toggleRect.right));
        const desiredLeft = window.innerWidth - right - panelWidth;
        const left = Math.max(8, Math.min(desiredLeft, window.innerWidth - panelWidth - 8));
        const topBase = Math.max(8, Math.round(toggleRect.bottom + 6));
        panel.style.left = `${left}px`;
        panel.style.right = 'auto';
        panel.style.top = `${topBase}px`;
        panel.style.maxHeight = `${Math.max(180, window.innerHeight - topBase - 10)}px`;
    }

    function closeMenu() {
        if (!toggle || !panel) return;
        root.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
    }

    function openMenu() {
        if (!toggle || !panel) return;
        root.classList.add("open");
        toggle.setAttribute("aria-expanded", "true");
        window.requestAnimationFrame(() => positionPanel());
    }

    if (toggle && panel) {
        toggle.addEventListener("click", function (event) {
            event.stopPropagation();
            if (root.classList.contains("open")) {
                closeMenu();
            } else {
                openMenu();
            }
        });

        panel.addEventListener("click", function (event) {
            const target = event.target.closest("a, button");
            if (!target) return;
            if (target.matches("a") || target.dataset.menuClose === "true") {
                closeMenu();
            }
        });

        document.addEventListener("click", function (event) {
            if (!root.contains(event.target)) {
                closeMenu();
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeMenu();
            }
        });

        window.addEventListener("resize", function () {
            if (root.classList.contains("open")) {
                positionPanel();
            }
        });

        window.addEventListener("scroll", function () {
            if (root.classList.contains("open")) {
                positionPanel();
            }
        }, { passive: true });
    }

    markActiveLinks();
})();
