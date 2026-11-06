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
    const systemLight = themes.includes(root.dataset.systemLight)
        ? root.dataset.systemLight
        : fallback;
    const systemDark = themes.includes(root.dataset.systemDark)
        ? root.dataset.systemDark
        : fallback;
    const media = window.matchMedia
        ? window.matchMedia("(prefers-color-scheme: light)")
        : null;

    const resolve = preference => {
        if (preference === "system") {
            return media && media.matches ? systemLight : systemDark;
        }
        return themes.includes(preference) ? preference : fallback;
    };

    const preference = () => {
        try {
            const saved = localStorage.getItem("spendly.theme");
            if (saved === "system" || themes.includes(saved)) return saved;
        } catch (error) {
        }
        return fallback;
    };

    const current = () => resolve(preference());

    function apply(value) {
        const nextPreference =
            value === "system"
                ? "system"
                : themes.includes(value)
                  ? value
                  : fallback;
        const next = resolve(nextPreference);
        root.dataset.variant = next;
        try {
            localStorage.setItem("spendly.theme", nextPreference);
        } catch (error) {
        }
        if (select) {
            select.value = nextPreference;
            select.dispatchEvent(new Event("dropdown:refresh"));
        }
        if (meta) meta.setAttribute("content", metaColors[next] || "");
        radios.forEach(radio => {
            const selected =
                radio.value === "system"
                    ? nextPreference === "system"
                    : nextPreference !== "system" && radio.value === next;
            radio.checked = selected;
            radio.closest(".theme-option")?.classList.toggle("is-selected", selected);
        });
        document.dispatchEvent(
            new CustomEvent("themechange", {
                detail: { theme: next, preference: nextPreference },
            })
        );
    }

    if (select) {
        select.value = preference();
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

    if (media) {
        const onSchemeChange = () => {
            if (preference() === "system") apply("system");
        };
        if (media.addEventListener) media.addEventListener("change", onSchemeChange);
        else if (media.addListener) media.addListener(onSchemeChange);
    }

    window.SpendlyTheme = {
        apply,
        current,
        preference,
        themes: [...themes],
        metaColors: { ...metaColors },
    };

    apply(preference());
})();
