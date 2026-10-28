(() => {
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
