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
        const headerRect = document.querySelector(".topbar")?.getBoundingClientRect();
        const panelWidth = Math.min(panel.offsetWidth || 220, window.innerWidth - 16);
        const left = Math.max(8, Math.min(toggleRect.left, window.innerWidth - panelWidth - 8));
        const topBase = Math.max(toggleRect.bottom + 10, (headerRect?.bottom || toggleRect.bottom) + 8);
        panel.style.left = `${left}px`;
        panel.style.top = `${topBase}px`;
        panel.style.maxHeight = `${Math.max(180, window.innerHeight - topBase - 12)}px`;
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
        window.requestAnimationFrame(positionPanel);
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
