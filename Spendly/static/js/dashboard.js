(() => {
    const profileTitle = document.getElementById("profile-title");
    const renameForm = document.getElementById("rename-form");
    const renameInput = document.getElementById("rename-input");

    if (profileTitle && renameForm && renameInput) {
        profileTitle.onclick = () => {
            profileTitle.hidden = true;
            renameForm.hidden = false;
            renameInput.focus();
            renameInput.select();
        };

        renameInput.oninput = () => {
            renameInput.setCustomValidity(
                renameInput.value.trim() ? "" : "Profile name cannot be empty."
            );
        };

        renameInput.onkeydown = e => {
            if (e.key === "Escape") {
                renameInput.value = profileTitle.textContent.trim();
                renameForm.hidden = true;
                profileTitle.hidden = false;
            }
        };

        renameInput.onblur = () => {
            if (!renameForm.hidden) {
                renameForm.hidden = true;
                profileTitle.hidden = false;
            }
        };

        renameForm.onsubmit = () => {
            renameInput.value = renameInput.value.trim();
        };
    }

    const fill = document.querySelector(".fill");
    if (fill) {
        fill.style.width = fill.dataset.width + "%";
    }

    document.querySelectorAll("select.auto-submit").forEach(select => {
        select.onchange = () => select.form.submit();
    });

    const pageDate = document.querySelector("input[name='date'][max]");
    if (pageDate) {
        setInterval(() => {
            const now = new Date();
            const pad = n => String(n).padStart(2, "0");
            const current = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
            if (current !== pageDate.max) location.reload();
        }, 60000);
    }

    const txnSearch = document.getElementById("txn-search");
    const txnRows = Array.from(document.querySelectorAll("[data-expense-row]"));
    if (txnSearch && txnRows.length) {
        const txnCount = document.getElementById("txn-count");
        const txnNoResults = document.getElementById("txn-no-results");
        const txnTableWrap = document.getElementById("txn-table-wrap");
        const total = txnRows.length;
        const label = value =>
            `${value} ${total === 1 ? txnCount?.dataset.singular || "expense" : txnCount?.dataset.plural || "expenses"}`;

        const applyFilter = () => {
            const query = txnSearch.value.trim().toLowerCase();
            let visible = 0;
            txnRows.forEach(row => {
                const match = !query || (row.dataset.search || "").includes(query);
                row.hidden = !match;
                if (match) visible += 1;
            });
            if (txnCount) {
                txnCount.textContent = query ? `${visible} of ${label(total)}` : label(total);
            }
            if (txnNoResults) txnNoResults.hidden = visible !== 0;
            if (txnTableWrap) txnTableWrap.hidden = visible === 0;
        };

        txnSearch.addEventListener("input", applyFilter);
    }

    const editDialog = document.getElementById("expense-dialog");
    const editForm = document.getElementById("expense-form");
    if (editDialog && editForm) {
        const editDate = document.getElementById("expense-dialog-date");
        const editCategory = document.getElementById("expense-dialog-category");
        const editAmount = document.getElementById("expense-dialog-amount");
        const editDescription = document.getElementById("expense-dialog-description");
        const editNext = document.getElementById("expense-dialog-next");
        const editClose = document.getElementById("expense-dialog-close");
        const editCancel = document.getElementById("expense-dialog-cancel");

        const closeEdit = () => {
            if (editDialog.open) editDialog.close();
        };

        document.querySelectorAll("[data-edit-expense]").forEach(button => {
            button.addEventListener("click", () => {
                const params = new URLSearchParams(window.location.search);
                params.delete("undo");
                const query = params.toString();
                editForm.action = button.dataset.action || "";
                if (editNext) {
                    editNext.value = `${window.location.pathname}${query ? `?${query}` : ""}`;
                }
                if (editDate) editDate.value = button.dataset.date || "";
                if (editCategory) editCategory.value = button.dataset.category || "Other";
                if (editAmount) editAmount.value = button.dataset.amount || "";
                if (editDescription) editDescription.value = button.dataset.description || "";
                if (typeof editDialog.showModal === "function") editDialog.showModal();
                if (editAmount) editAmount.focus();
                if (editAmount) editAmount.select();
            });
        });

        if (editClose) editClose.addEventListener("click", closeEdit);
        if (editCancel) editCancel.addEventListener("click", closeEdit);
        editDialog.addEventListener("click", event => {
            if (event.target === editDialog) closeEdit();
        });
        editForm.addEventListener("submit", () => {
            if (editDescription) editDescription.value = editDescription.value.trim();
        });
    }

    const toast = document.querySelector(".toast-undo");
    if (toast) {
        const dismiss = () => {
            toast.classList.add("toast-out");
            window.setTimeout(() => toast.remove(), 180);
        };
        const close = toast.querySelector("[data-toast-close]");
        if (close) close.addEventListener("click", dismiss);
        window.setTimeout(dismiss, 9000);
    }

    const calendar = document.getElementById("calendar");
    if (!calendar) return;

    const calTitle = document.getElementById("cal-title");
    const calGrid = document.getElementById("cal-grid");
    let calInput = null;
    let calView = new Date();

    const pad = n => String(n).padStart(2, "0");
    const toISO = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    const fromISO = s => {
        const [y, m, d] = s.split("-").map(Number);
        return new Date(y, m - 1, d);
    };

    function openCalendar(input) {
        calInput = input;
        const selected = input.value ? fromISO(input.value) : new Date();
        calView = new Date(selected.getFullYear(), selected.getMonth(), 1);
        drawCalendar();
        calendar.showModal();
    }

    function drawCalendar() {
        const year = calView.getFullYear();
        const month = calView.getMonth();
        const first = new Date(year, month, 1).getDay();
        const start = new Date(year, month, 1 - first);
        const today = toISO(new Date());
        const selected = calInput.value;
        const cells = [];

        calTitle.textContent = calView.toLocaleString(undefined, { month: "long", year: "numeric" });

        for (let i = 0; i < 42; i++) {
            const day = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
            const iso = toISO(day);
            let cls = "cal-day";
            if (day.getMonth() !== month) cls += " other";
            if (iso === today) cls += " today";
            if (iso === selected) cls += " selected";
            cells.push(`<button type="button" class="${cls}" data-date="${iso}">${day.getDate()}</button>`);
        }
        calGrid.innerHTML = cells.join("");
    }

    document.querySelectorAll(".date-picker").forEach(input => {
        input.onclick = e => {
            e.preventDefault();
            openCalendar(input);
        };
        input.onkeydown = e => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                openCalendar(input);
            }
        };
    });

    document.getElementById("cal-prev").onclick = () => {
        calView = new Date(calView.getFullYear(), calView.getMonth() - 1, 1);
        drawCalendar();
    };
    document.getElementById("cal-next").onclick = () => {
        calView = new Date(calView.getFullYear(), calView.getMonth() + 1, 1);
        drawCalendar();
    };
    document.getElementById("cal-today").onclick = () => {
        calInput.value = toISO(new Date());
        calendar.close();
    };
    document.getElementById("cal-cancel").onclick = () => calendar.close();
    calGrid.onclick = e => {
        const day = e.target.closest("button[data-date]");
        if (!day) return;
        calInput.value = day.dataset.date;
        calendar.close();
    };
})();
