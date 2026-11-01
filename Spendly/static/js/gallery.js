(() => {
    const grid = document.getElementById("gallery-grid");
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll(".gallery-card"));
    const modeButtons = Array.from(document.querySelectorAll("[data-mode-filter]"));
    const shellSelect = document.getElementById("gallery-shell");
    const searchInput = document.getElementById("theme-search");
    const count = document.getElementById("gallery-count");
    const activeName = document.getElementById("gallery-active-name");
    const empty = document.getElementById("gallery-empty");
    const resetButtons = Array.from(document.querySelectorAll("[data-reset-filters]"));
    const announcer = document.getElementById("gallery-announcer");
    const root = document.documentElement;

    const dialog = document.getElementById("theme-preview");
    const previewTitle = document.getElementById("theme-preview-title");
    const previewDescription = document.getElementById("theme-preview-description");
    const previewImage = document.getElementById("theme-preview-image");
    const previewStage = document.getElementById("theme-preview-stage");
    const previewOpen = document.getElementById("theme-preview-open");
    const previewApply = document.getElementById("theme-preview-apply");
    const previewClose = dialog?.querySelector(".gallery-dialog-close");
    const deviceButtons = dialog
        ? Array.from(dialog.querySelectorAll(".gallery-device-toggle [data-device]"))
        : [];

    let activeMode = "all";
    let activeShell = "all";
    let previewCard = null;

    const currentTheme = () =>
        window.SpendlyTheme
            ? window.SpendlyTheme.current()
            : root.dataset.variant || "";

    const normalise = value =>
        (value || "").toLowerCase().replace(/\s+/g, " ").trim();

    function announce(message) {
        if (!announcer) return;
        announcer.textContent = "";
        window.setTimeout(() => {
            announcer.textContent = message;
        }, 30);
    }

    function updateActive(themeId) {
        let name = "";

        cards.forEach(card => {
            const isActive = card.dataset.themeId === themeId;
            const flag = card.querySelector("[data-current-flag]");
            const button = card.querySelector("[data-apply-theme]");
            const label = button?.querySelector("[data-apply-label]");

            card.classList.toggle("is-current", isActive);
            if (flag) flag.hidden = !isActive;
            if (button) button.setAttribute("aria-pressed", isActive ? "true" : "false");
            if (label) label.textContent = isActive ? "Applied" : "Use theme";
            if (isActive) name = card.dataset.name || "";
        });

        if (activeName) activeName.textContent = name || "—";
        if (previewCard && previewApply) {
            previewApply.textContent =
                previewCard.dataset.themeId === themeId
                    ? "Current theme"
                    : "Use this theme";
        }
    }

    function matches(card) {
        if (activeMode !== "all" && card.dataset.mode !== activeMode) return false;
        if (activeShell !== "all" && card.dataset.shell !== activeShell) return false;

        const query = normalise(searchInput?.value);
        if (!query) return true;
        const haystack = card.dataset.search || "";
        return query.split(" ").every(term => haystack.includes(term));
    }

    function applyFilters() {
        let visible = 0;

        cards.forEach(card => {
            const show = matches(card);
            card.hidden = !show;
            if (show) visible += 1;
        });

        if (count) {
            count.textContent =
                visible === cards.length
                    ? `Showing all ${cards.length} themes`
                    : `Showing ${visible} of ${cards.length} themes`;
        }
        if (empty) empty.hidden = visible !== 0;
        grid.hidden = visible === 0;
    }

    function setMode(mode) {
        activeMode = mode;
        modeButtons.forEach(button => {
            const selected = button.dataset.modeFilter === mode;
            button.classList.toggle("is-active", selected);
            button.setAttribute("aria-pressed", selected ? "true" : "false");
        });
    }

    function resetFilters() {
        setMode("all");
        activeShell = "all";
        if (shellSelect) shellSelect.value = "all";
        if (searchInput) searchInput.value = "";
        applyFilters();
        announce("Theme filters cleared.");
    }

    function applyTheme(themeId, themeName) {
        if (window.SpendlyTheme) {
            window.SpendlyTheme.apply(themeId);
        } else {
            root.dataset.variant = themeId;
            try {
                localStorage.setItem("spendly.theme", themeId);
            } catch (error) {
            }
        }
        updateActive(themeId);
        announce(`${themeName} applied.`);
    }

    function setDevice(device) {
        if (!previewCard) return;

        const mobile = device === "mobile";
        const source = mobile
            ? previewCard.dataset.mobileSrc
            : previewCard.dataset.desktopSrc;

        deviceButtons.forEach(button => {
            const selected = button.dataset.device === device;
            button.classList.toggle("is-active", selected);
            button.setAttribute("aria-pressed", selected ? "true" : "false");
        });

        if (previewStage) previewStage.dataset.device = device;
        if (previewImage) {
            previewImage.src = source;
            previewImage.alt = `${previewCard.dataset.name} ${
                mobile ? "mobile" : "desktop"
            } dashboard preview`;
        }
        if (previewOpen) previewOpen.href = source;
    }

    function openPreview(card) {
        if (!dialog || !card) return;

        previewCard = card;
        if (previewTitle) previewTitle.textContent = card.dataset.name || "Theme preview";
        if (previewDescription) {
            previewDescription.textContent = card.dataset.tagline || "";
        }
        const compact = window.matchMedia("(max-width: 640px)").matches;
        setDevice(compact ? "mobile" : "desktop");
        if (previewApply) {
            previewApply.textContent =
                card.dataset.themeId === currentTheme()
                    ? "Current theme"
                    : "Use this theme";
        }

        if (typeof dialog.showModal === "function") {
            if (!dialog.open) dialog.showModal();
        } else {
            dialog.setAttribute("open", "");
        }
        previewClose?.focus();
    }

    modeButtons.forEach(button => {
        button.addEventListener("click", () => {
            setMode(button.dataset.modeFilter || "all");
            applyFilters();
        });
    });

    shellSelect?.addEventListener("change", () => {
        activeShell = shellSelect.value;
        applyFilters();
    });

    searchInput?.addEventListener("input", applyFilters);

    resetButtons.forEach(button => {
        button.addEventListener("click", resetFilters);
    });

    grid.addEventListener("click", event => {
        const applyButton = event.target.closest("[data-apply-theme]");
        if (applyButton) {
            const card = applyButton.closest(".gallery-card");
            applyTheme(applyButton.dataset.applyTheme, card?.dataset.name || "Theme");
            return;
        }

        const previewLink = event.target.closest("[data-preview-theme]");
        if (previewLink) {
            event.preventDefault();
            openPreview(previewLink.closest(".gallery-card"));
        }
    });

    deviceButtons.forEach(button => {
        button.addEventListener("click", () => {
            setDevice(button.dataset.device === "mobile" ? "mobile" : "desktop");
        });
    });

    previewClose?.addEventListener("click", () => dialog?.close());

    dialog?.addEventListener("click", event => {
        if (event.target === dialog) dialog.close();
    });

    dialog?.addEventListener("close", () => {
        previewCard = null;
        previewImage?.removeAttribute("src");
    });

    previewApply?.addEventListener("click", () => {
        if (!previewCard) return;
        applyTheme(
            previewCard.dataset.themeId,
            previewCard.dataset.name || "Theme"
        );
    });

    document.addEventListener("themechange", event => {
        const theme = event.detail?.theme;
        if (theme) updateActive(theme);
    });

    updateActive(currentTheme());
    applyFilters();
})();
