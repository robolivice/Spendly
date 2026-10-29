(() => {
    const themes = ["fintech", "cockpit", "saas", "glass"];
    const metaColors = {
        fintech: "#0a0c12",
        cockpit: "#0a0f1c",
        saas: "#f6f8fd",
        glass: "#07070f",
    };
    const root = document.documentElement;
    const select = document.getElementById("theme-select");
    const radios = document.querySelectorAll('input[name="theme-choice"]');
    const meta = document.getElementById("theme-color");

    const current = () => {
        const value = root.dataset.variant;
        return themes.includes(value) ? value : "fintech";
    };

    function apply(theme) {
        const next = themes.includes(theme) ? theme : "fintech";
        root.dataset.variant = next;
        try {
            localStorage.setItem("spendly.theme", next);
        } catch (error) {
            /* private mode or storage disabled */
        }
        if (select) select.value = next;
        if (meta) meta.setAttribute("content", metaColors[next]);
        radios.forEach(radio => {
            const selected = radio.value === next;
            radio.checked = selected;
            radio.closest(".theme-option")?.classList.toggle("is-selected", selected);
        });
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

    apply(current());
})();
