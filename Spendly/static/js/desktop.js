(() => {
    const buttons = document.querySelectorAll("[data-desktop-action]");
    if (!buttons.length) return;

    const bridge = () => (window.pywebview && window.pywebview.api) || null;

    function enable() {
        buttons.forEach(button => {
            button.disabled = false;
        });
    }

    if (bridge()) {
        enable();
    } else {
        window.addEventListener("pywebviewready", enable, { once: true });
        let attempts = 0;
        const poll = setInterval(() => {
            if (bridge() || ++attempts >= 100) {
                clearInterval(poll);
                if (bridge()) enable();
            }
        }, 100);
    }

    buttons.forEach(button => {
        button.addEventListener("click", async () => {
            const api = bridge();
            const action = button.dataset.desktopAction;
            if (!api || typeof api[action] !== "function") return;

            button.disabled = true;
            try {
                await api[action]();
            } catch (error) {
            } finally {
                button.disabled = false;
            }
        });
    });
})();
