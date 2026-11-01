(() => {
    let openInstance = null;
    let uid = 0;
    let ignoreFocusLoss = false;

    const normalize = text => (text || "").replace(/\s+/g, " ").trim();

    function labelTextFor(select) {
        const labels = select.labels ? Array.from(select.labels) : [];
        for (const label of labels) {
            const clone = label.cloneNode(true);
            clone.querySelectorAll("select").forEach(node => node.remove());
            const text = normalize(clone.textContent);
            if (text) return text;
        }
        return normalize(select.getAttribute("aria-label") || "");
    }

    function slug(value) {
        return String(value || "")
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");
    }

    function dotClass(select, value) {
        if (select.id === "theme-select") {
            return `dropdown-dot dropdown-dot--theme dropdown-dot--${slug(value)}`;
        }
        if (select.name === "category") {
            return `dropdown-dot dropdown-dot--cat dropdown-dot--${slug(value)}`;
        }
        return "";
    }

    function enhance(select) {
        if (select.dataset.dropdownReady === "true" || select.multiple) return;
        if (!select.options.length) return;

        select.dataset.dropdownReady = "true";

        const labelText = labelTextFor(select);
        const baseId = select.id || `spendly-select-${++uid}`;
        if (!select.id) select.id = baseId;
        const triggerId = `${baseId}-trigger`;
        const menuId = `${baseId}-menu`;

        const wrapper = document.createElement("div");
        wrapper.className = "dropdown";
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);

        select.classList.add("dropdown-native");
        select.tabIndex = -1;
        select.setAttribute("aria-hidden", "true");
        if (labelText) select.setAttribute("aria-label", labelText);

        const trigger = document.createElement("button");
        trigger.type = "button";
        trigger.className = "dropdown-trigger";
        trigger.id = triggerId;
        trigger.setAttribute("role", "combobox");
        trigger.setAttribute("aria-haspopup", "listbox");
        trigger.setAttribute("aria-expanded", "false");
        trigger.setAttribute("aria-controls", menuId);
        if (labelText) trigger.setAttribute("aria-label", labelText);
        trigger.innerHTML = `
            <span class="dropdown-value">
                <span class="dropdown-dot" hidden></span>
                <span class="dropdown-value-text"></span>
            </span>
            <span class="dropdown-chevron" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false"><path d="m6 9 6 6 6-6"></path></svg>
            </span>`;
        wrapper.appendChild(trigger);

        if (select.labels) {
            Array.from(select.labels).forEach(label => {
                if (label.control === select) label.htmlFor = triggerId;
            });
        }

        const menu = document.createElement("div");
        menu.className = "dropdown-menu";
        menu.id = menuId;
        menu.setAttribute("role", "listbox");
        menu.setAttribute("aria-label", labelText ? `${labelText} options` : "Options");
        menu.hidden = true;
        (document.querySelector("main") || document.body).appendChild(menu);

        const valueText = trigger.querySelector(".dropdown-value-text");
        const valueDot = trigger.querySelector(".dropdown-dot");
        let activeOption = null;
        let typeBuffer = "";
        let typeTimer = 0;

        const instance = {
            select,
            trigger,
            menu,
            wrapper,
            close,
        };

        function selectedOption() {
            return select.options[select.selectedIndex] || select.options[0] || null;
        }

        function syncValue() {
            const option = selectedOption();
            const text = option ? normalize(option.textContent) : "";
            valueText.textContent = text;
            trigger.title = text;
            const dot = option ? dotClass(select, option.value) : "";
            valueDot.className = dot || "dropdown-dot";
            valueDot.hidden = !dot;
        }

        function addOption(option, parent, index) {
            const item = document.createElement("div");
            item.className = "dropdown-option";
            item.id = `${menuId}-option-${index}`;
            item.setAttribute("role", "option");
            item.setAttribute("aria-selected", option.selected ? "true" : "false");
            item.dataset.index = String(index);
            if (option.disabled) item.setAttribute("aria-disabled", "true");
            item._option = option;

            const dot = dotClass(select, option.value);
            if (dot) {
                const swatch = document.createElement("span");
                swatch.className = dot;
                swatch.setAttribute("aria-hidden", "true");
                item.appendChild(swatch);
            }

            const label = document.createElement("span");
            label.className = "dropdown-option-label";
            label.textContent = normalize(option.textContent);
            item.appendChild(label);

            const check = document.createElement("span");
            check.className = "dropdown-check";
            check.setAttribute("aria-hidden", "true");
            check.innerHTML =
                '<svg viewBox="0 0 24 24" focusable="false"><path d="m5 12.5 4.5 4.5L19 7.5"></path></svg>';
            item.appendChild(check);

            parent.appendChild(item);
        }

        function buildMenu() {
            menu.textContent = "";
            let index = 0;

            Array.from(select.children).forEach(child => {
                if (child.tagName === "OPTGROUP") {
                    const group = document.createElement("div");
                    group.className = "dropdown-group";
                    group.setAttribute("role", "group");
                    if (child.label) group.setAttribute("aria-label", child.label);

                    const heading = document.createElement("div");
                    heading.className = "dropdown-group-label";
                    heading.textContent = child.label;
                    heading.setAttribute("aria-hidden", "true");
                    group.appendChild(heading);

                    Array.from(child.children).forEach(option => {
                        addOption(option, group, index);
                        index += 1;
                    });
                    menu.appendChild(group);
                } else if (child.tagName === "OPTION") {
                    addOption(child, menu, index);
                    index += 1;
                }
            });

            syncSelection();
        }

        function options() {
            return Array.from(menu.querySelectorAll('[role="option"]'));
        }

        function enabledOptions() {
            return options().filter(item => item.getAttribute("aria-disabled") !== "true");
        }

        function syncSelection() {
            options().forEach(item => {
                item.setAttribute(
                    "aria-selected",
                    item._option && item._option.selected ? "true" : "false"
                );
            });
        }

        function scrollIntoView(item) {
            const itemRect = item.getBoundingClientRect();
            const menuRect = menu.getBoundingClientRect();
            if (itemRect.top < menuRect.top + 4) {
                menu.scrollTop -= menuRect.top - itemRect.top + 6;
            } else if (itemRect.bottom > menuRect.bottom - 4) {
                menu.scrollTop += itemRect.bottom - menuRect.bottom + 6;
            }
        }

        function setActive(item, reveal = true) {
            if (!item) return;
            options().forEach(option => option.classList.toggle("is-active", option === item));
            activeOption = item;
            trigger.setAttribute("aria-activedescendant", item.id);
            if (reveal) scrollIntoView(item);
        }

        function moveActive(step) {
            const list = enabledOptions();
            if (!list.length) return;
            let index = activeOption ? list.indexOf(activeOption) : -1;
            if (index === -1) index = step > 0 ? -1 : 0;
            index = (index + step + list.length) % list.length;
            setActive(list[index]);
        }

        function typeahead(character) {
            typeBuffer += character.toLowerCase();
            window.clearTimeout(typeTimer);
            typeTimer = window.setTimeout(() => {
                typeBuffer = "";
            }, 650);

            const match = enabledOptions().find(item =>
                normalize(item.textContent).toLowerCase().startsWith(typeBuffer)
            );
            if (match) setActive(match);
        }

        function position() {
            if (menu.hidden) return;

            const gap = 7;
            const pad = 10;
            const rect = trigger.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const maxWidth = Math.max(180, Math.min(440, viewportWidth - pad * 2));
            const preferredWidth = select.id === "theme-select" ? 220 : Math.max(rect.width, 180);

            menu.style.minWidth = `${Math.min(preferredWidth, maxWidth)}px`;
            menu.style.maxWidth = `${maxWidth}px`;
            menu.style.maxHeight = "320px";

            const naturalHeight = menu.offsetHeight;
            const spaceBelow = window.innerHeight - rect.bottom - gap - pad;
            const spaceAbove = rect.top - gap - pad;
            const openUp = naturalHeight > spaceBelow && spaceAbove > spaceBelow;
            const maxHeight = Math.max(120, Math.min(320, openUp ? spaceAbove : spaceBelow));

            menu.style.maxHeight = `${maxHeight}px`;
            menu.style.top = "0px";
            menu.style.left = "0px";

            const menuWidth = menu.offsetWidth;
            const menuHeight = menu.offsetHeight;
            let left = Math.min(Math.max(pad, rect.left), viewportWidth - pad - menuWidth);
            let top = openUp ? rect.top - gap - menuHeight : rect.bottom + gap;

            top = Math.min(Math.max(pad, top), window.innerHeight - pad - menuHeight);

            menu.style.left = `${Math.round(left)}px`;
            menu.style.top = `${Math.round(top)}px`;
        }

        function open(prefer = "selected") {
            if (openInstance && openInstance !== instance) openInstance.close();

            buildMenu();
            menu.hidden = false;
            wrapper.classList.add("is-open");
            trigger.classList.add("is-open");
            trigger.setAttribute("aria-expanded", "true");
            openInstance = instance;

            position();

            const selected = selectedOption();
            const list = enabledOptions();
            let target = selected
                ? options().find(item => item._option === selected)
                : null;
            if (target && target.getAttribute("aria-disabled") === "true") target = null;
            if (prefer === "last") target = list[list.length - 1] || null;
            else if (prefer === "first") target = list[0] || null;
            if (!target) target = list[0] || null;
            setActive(target);
        }

        function close(refocus = false) {
            if (menu.hidden) return;

            menu.hidden = true;
            wrapper.classList.remove("is-open");
            trigger.classList.remove("is-open");
            trigger.setAttribute("aria-expanded", "false");
            trigger.removeAttribute("aria-activedescendant");
            activeOption = null;
            if (openInstance === instance) openInstance = null;
            if (refocus) trigger.focus({ preventScroll: true });
        }

        function choose(item) {
            if (!item || item.getAttribute("aria-disabled") === "true") return;
            const option = item._option;
            if (!option) return;

            const changed = select.selectedIndex !== option.index || select.value !== option.value;
            select.value = option.value;
            syncValue();
            syncSelection();
            close(true);

            if (changed) {
                select.dispatchEvent(new Event("change", { bubbles: true }));
            }
        }

        trigger.addEventListener("click", () => {
            if (menu.hidden) open("selected");
            else close(true);
        });

        trigger.addEventListener("keydown", event => {
            const key = event.key;
            const modifier = event.ctrlKey || event.metaKey || event.altKey;

            if (key === "ArrowDown" || key === "ArrowUp") {
                event.preventDefault();
                if (menu.hidden) open(key === "ArrowUp" ? "last" : "selected");
                else moveActive(key === "ArrowDown" ? 1 : -1);
                return;
            }

            if (key === "Home" || key === "End") {
                if (menu.hidden) return;
                event.preventDefault();
                const list = enabledOptions();
                setActive(key === "Home" ? list[0] : list[list.length - 1]);
                return;
            }

            if (key === "Enter" || key === " " || key === "Spacebar") {
                event.preventDefault();
                if (menu.hidden) open("selected");
                else choose(activeOption);
                return;
            }

            if (key === "Escape") {
                if (!menu.hidden) {
                    event.preventDefault();
                    close(true);
                }
                return;
            }

            if (key === "Tab") {
                close();
                return;
            }

            if (key.length === 1 && !modifier) {
                event.preventDefault();
                if (menu.hidden) open("selected");
                typeahead(key);
            }
        });

        menu.addEventListener("pointerdown", event => {
            const item = event.target.closest('[role="option"]');
            if (!item) return;
            if (event.pointerType === "mouse") {
                event.preventDefault();
            } else {
                ignoreFocusLoss = true;
                window.setTimeout(() => {
                    ignoreFocusLoss = false;
                }, 400);
            }
        });

        menu.addEventListener("pointerup", event => {
            if (event.pointerType !== "mouse" && !menu.hidden) {
                trigger.focus({ preventScroll: true });
            }
        });

        menu.addEventListener("pointermove", event => {
            const item = event.target.closest('[role="option"]');
            if (
                item &&
                item.getAttribute("aria-disabled") !== "true" &&
                item !== activeOption
            ) {
                setActive(item, false);
            }
        });

        menu.addEventListener("click", event => {
            const item = event.target.closest('[role="option"]');
            if (!item) {
                close(true);
                return;
            }
            choose(item);
        });

        select.addEventListener("change", () => {
            syncValue();
            if (!menu.hidden) syncSelection();
        });

        select.addEventListener("input", syncValue);
        select.addEventListener("dropdown:refresh", syncValue);

        const reposition = () => {
            if (!menu.hidden) position();
        };
        window.addEventListener("resize", reposition);
        window.addEventListener(
            "scroll",
            event => {
                if (event.target === document || event.target === document.documentElement) {
                    reposition();
                }
            },
            true
        );

        syncValue();
    }

    document.addEventListener(
        "pointerdown",
        event => {
            if (
                openInstance &&
                !openInstance.menu.contains(event.target) &&
                !openInstance.trigger.contains(event.target)
            ) {
                openInstance.close();
            }
        },
        true
    );

    document.addEventListener("focusin", event => {
        if (ignoreFocusLoss) return;
        if (
            openInstance &&
            !openInstance.menu.contains(event.target) &&
            !openInstance.trigger.contains(event.target)
        ) {
            openInstance.close();
        }
    });

    document.querySelectorAll("select:not([multiple])").forEach(enhance);
})();
