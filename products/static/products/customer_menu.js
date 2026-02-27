(function () {
    const root = document.querySelector("[data-customer-menu]");
    if (!root) return;

    const toggle = root.querySelector("[data-menu-toggle]");
    const panel = root.querySelector("[data-menu-panel]");
    if (!toggle || !panel) return;

    function normalizePath(path) {
        const value = String(path || "").trim();
        if (!value || value === "/") return "/";
        return value.endsWith("/") ? value : value + "/";
    }

    function markActiveLink() {
        const current = normalizePath(window.location.pathname);
        const links = panel.querySelectorAll("a[href]");
        links.forEach((link) => {
            const href = normalizePath(link.getAttribute("href"));
            if (href === current) {
                link.classList.add("active");
            } else {
                link.classList.remove("active");
            }
        });
    }

    function closeMenu() {
        root.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
    }

    function openMenu() {
        root.classList.add("open");
        toggle.setAttribute("aria-expanded", "true");
    }

    toggle.addEventListener("click", function (event) {
        event.stopPropagation();
        if (root.classList.contains("open")) {
            closeMenu();
        } else {
            openMenu();
        }
    });

    panel.addEventListener("click", function (event) {
        const target = event.target.closest("a");
        if (!target) return;
        closeMenu();
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

    markActiveLink();
})();
