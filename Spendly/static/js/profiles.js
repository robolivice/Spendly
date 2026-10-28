(() => {
    const dialog = document.getElementById("delete-dialog");
    if (!dialog) return;

    const confirmBtn = document.getElementById("delete-confirm");
    let deleteUrl = "";

    document.querySelectorAll("[data-url]").forEach(btn => {
        btn.onclick = () => {
            deleteUrl = btn.dataset.url;
            document.getElementById("delete-message").textContent =
                `Delete "${btn.dataset.name}"? This cannot be undone.`;
            dialog.showModal();
        };
    });

    document.getElementById("delete-cancel").onclick = () => dialog.close();

    confirmBtn.onclick = async () => {
        confirmBtn.disabled = true;
        await fetch(deleteUrl, { method: "DELETE" });
        location.reload();
    };
})();
