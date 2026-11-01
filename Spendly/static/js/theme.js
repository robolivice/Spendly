(() => {
    let config = [];
    const configNode = document.getElementById("theme-config");
    if (configNode) {
        try {
            const parsed = JSON.parse(configNode.textContent);
            if (Array.isArray(parsed)) config = parsed;
        } catch (error) {
        }
    }

    const themes = config.map(theme => theme.id).filter(Boolean);
    const metaColors = Object.fromEntries(
        config
            .filter(theme => theme.id && theme.metaColor)
            .map(theme => [theme.id, theme.metaColor])
    );
    const fallback = themes[0] || "fintech";

    const root = document.documentElement;
    const select = document.getElementById("theme-select");
    const radios = document.querySelectorAll('input[name="theme-choice"]');
    const meta = document.getElementById("theme-color");

    const current = () => {
        const value = root.dataset.variant;
        return themes.includes(value) ? value : fallback;
    };

    function apply(theme) {
        const next = themes.includes(theme) ? theme : fallback;
        root.dataset.variant = next;
        try {
            localStorage.setItem("spendly.theme", next);
        } catch (error) {
        }
        if (select) {
            select.value = next;
            select.dispatchEvent(new Event("dropdown:refresh"));
        }
        if (meta) meta.setAttribute("content", metaColors[next] || "");
        radios.forEach(radio => {
            const selected = radio.value === next;
            radio.checked = selected;
            radio.closest(".theme-option")?.classList.toggle("is-selected", selected);
        });
        document.dispatchEvent(
            new CustomEvent("themechange", { detail: { theme: next } })
        );
    }

    if (select) {
        select.value = current();
        select.addEventListener("change", () => apply(select.value));
    }

    radios.forEach(radio => {
        radio.addEventListener("change", () => {
            if (radio.checked) apply(radio.value);
        });
    });

    window.addEventListener("storage", event => {
        if (event.key === "spendly.theme" && event.newValue) apply(event.newValue);
    });

    window.SpendlyTheme = {
        apply,
        current,
        themes: [...themes],
        metaColors: { ...metaColors },
    };

    apply(current());
})();
