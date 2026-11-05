(() => {
    const elements = {
        button: document.getElementById("update-button"),
        dot: document.getElementById("update-dot"),
        banner: document.getElementById("update-banner"),
        bannerTitle: document.getElementById("update-banner-title"),
        bannerText: document.getElementById("update-banner-text"),
        bannerOpen: document.getElementById("update-banner-open"),
        bannerLater: document.getElementById("update-banner-later"),
        consent: document.getElementById("update-consent"),
        consentYes: document.getElementById("update-consent-yes"),
        consentNo: document.getElementById("update-consent-no"),
        dialog: document.getElementById("update-dialog"),
        close: document.getElementById("update-close"),
        title: document.getElementById("update-dialog-title"),
        meta: document.getElementById("update-meta"),
        stateText: document.getElementById("update-state"),
        notes: document.getElementById("update-notes"),
        progress: document.getElementById("update-progress"),
        progressFill: document.getElementById("update-progress-fill"),
        progressText: document.getElementById("update-progress-text"),
        autoWrap: document.getElementById("update-auto-wrap"),
        autoCheck: document.getElementById("update-auto-check"),
        releaseLink: document.getElementById("update-release-link"),
        check: document.getElementById("update-check"),
        skip: document.getElementById("update-skip"),
        later: document.getElementById("update-later"),
        cancel: document.getElementById("update-cancel"),
        install: document.getElementById("update-install"),
        settingsAuto: document.getElementById("settings-auto-update"),
        settingsCheck: document.getElementById("settings-check-update"),
        settingsStatus: document.getElementById("settings-update-status"),
    };

    if (!elements.button || !elements.dialog) return;

    const state = {
        bridge: null,
        status: null,
        consentShown: false,
        consentOpen: false,
        dialogOpen: false,
        bannerDismissed: false,
        errorShown: false,
        busy: false,
    };

    const bridge = () => (window.pywebview && window.pywebview.api) || null;

    function setText(element, value) {
        if (element) element.textContent = value || "";
    }

    function setVisible(element, value) {
        if (element) element.hidden = !value;
    }

    function formatSize(bytes) {
        let value = Number(bytes) || 0;
        if (!value) return "";
        const units = ["B", "KB", "MB", "GB"];
        let index = 0;
        while (value >= 1024 && index < units.length - 1) {
            value /= 1024;
            index += 1;
        }
        return `${value.toFixed(index ? 1 : 0)} ${units[index]}`;
    }

    function formatDate(value) {
        if (!value) return "";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "";
        return date.toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
        });
    }

    function renderBanner(data) {
        const update = data.update;
        const blocked = Boolean(update && !data.manual && (data.skipped || data.postponed));
        const visible = Boolean(
            update &&
            data.available &&
            !blocked &&
            !state.bannerDismissed &&
            data.phase !== "installing"
        );
        setVisible(elements.banner, visible);
        elements.button.classList.toggle("has-update", visible);
        setVisible(elements.dot, visible);
        const label = visible
            ? `Spendly ${update.version} is available`
            : "Check for updates";
        elements.button.title = label;
        elements.button.setAttribute("aria-label", label);
        if (!visible) return;
        setText(elements.bannerTitle, `Spendly ${update.version} is available`);
        setText(elements.bannerText, "See what changed and install it from here.");
    }

    function renderDialog(data) {
        const update = data.update;
        const download = data.download || {};
        const phase = data.phase || "idle";
        const supported = data.supported !== false;
        const hasUpdate = Boolean(update && data.available);
        const downloading = phase === "downloading";
        const ready = phase === "ready";
        const installing = phase === "installing";
        const failed =
            phase === "error" ||
            phase === "download_error" ||
            phase === "install_error" ||
            Boolean(data.install_error);

        setText(
            elements.title,
            hasUpdate ? `Spendly ${update.version} is available` : "Spendly updates"
        );

        const meta = [];
        if (hasUpdate) {
            if (update.published_at) {
                meta.push(`Released ${formatDate(update.published_at)}`);
            }
            if (update.asset_size) meta.push(formatSize(update.asset_size));
        } else {
            meta.push(`You are running Spendly ${data.version}`);
            if (data.portable) meta.push("Portable build");
        }
        setText(elements.meta, meta.join(" · "));

        let message = "";
        if (!supported) {
            message = "Update checks are available in the installed Windows app.";
        } else if (phase === "checking") {
            message = "Checking GitHub for updates...";
        } else if (downloading) {
            message = `Downloading Spendly ${update ? update.version : ""}...`;
        } else if (installing) {
            message = "Restarting Spendly to install the update...";
        } else if (phase === "install_error" || data.install_error) {
            message = data.install_error || "The last update could not be installed.";
        } else if (ready) {
            message = "Download complete. Spendly will close and restart to install it.";
        } else if (phase === "download_error") {
            message = download.error || "The update download failed.";
        } else if (phase === "error") {
            message = data.error || "Could not check for updates.";
        } else if (hasUpdate) {
            if (data.skipped) {
                message = "You skipped this version. You can still install it now.";
            } else if (data.postponed) {
                message = "You postponed this update. You can install it now.";
            } else {
                message = "A new version is ready. Your data stays where it is.";
            }
        } else if (phase === "up_to_date") {
            message = "You're up to date.";
        } else {
            message = data.auto_check
                ? "Check for updates now."
                : "Automatic checks are off. You can still check manually.";
        }

        const canDownload = Boolean(update && update.asset_name && update.has_digest);
        if (hasUpdate && !downloading && !installing && !ready && !canDownload) {
            message = "This release does not include a verified download. Open the release page to install it manually.";
        }

        elements.stateText.classList.toggle("error", failed);
        setText(elements.stateText, message);

        const notes = hasUpdate ? (update.notes || "").trim() : "";
        setText(elements.notes, notes);
        setVisible(elements.notes, Boolean(notes));

        setVisible(elements.autoWrap, supported);
        if (elements.autoCheck) {
            elements.autoCheck.checked = data.consent === true;
            elements.autoCheck.disabled = !supported;
        }
        if (elements.settingsAuto) {
            elements.settingsAuto.checked = data.consent === true;
            elements.settingsAuto.disabled = !supported;
        }
        if (elements.settingsCheck) {
            elements.settingsCheck.disabled = !supported || !state.bridge;
        }
        if (elements.settingsStatus) {
            if (!supported) {
                setText(elements.settingsStatus, "Update checks are available in the installed Windows app.");
            } else if (data.auto_check) {
                setText(elements.settingsStatus, "Automatic checks are on.");
            } else if (data.consent === false) {
                setText(elements.settingsStatus, "Automatic checks are off. You can still check manually.");
            } else {
                setText(elements.settingsStatus, "Choose whether Spendly checks GitHub for updates.");
            }
        }

        const releaseUrl = hasUpdate ? update.release_url : "";
        if (elements.releaseLink) {
            elements.releaseLink.dataset.url = releaseUrl || "";
            elements.releaseLink.hidden = !releaseUrl;
        }

        setVisible(elements.check, supported && !downloading && !installing && !ready);
        if (elements.check) {
            elements.check.textContent = data.last_check ? "Check again" : "Check now";
        }

        setVisible(
            elements.install,
            supported && hasUpdate && !downloading && !installing
        );
        if (elements.install) {
            elements.install.textContent = ready ? "Restart & update" : "Download and install";
            elements.install.disabled = !(ready || canDownload);
        }

        setVisible(
            elements.skip,
            hasUpdate && !downloading && !installing && !ready && !data.skipped
        );
        setVisible(
            elements.later,
            hasUpdate && !downloading && !installing && !ready
        );
        setVisible(elements.cancel, downloading);
        setVisible(elements.progress, downloading || ready);

        if (elements.progressFill) {
            const percent = Math.max(0, Math.min(100, Number(download.percent) || 0));
            elements.progressFill.style.width = `${percent}%`;
        }
        if (downloading) {
            const received = formatSize(download.downloaded);
            const total = formatSize(download.total);
            const percent = Math.round(Number(download.percent) || 0);
            setText(
                elements.progressText,
                total ? `${received} of ${total} (${percent}%)` : `${percent}%`
            );
        } else if (ready) {
            setText(elements.progressText, "Downloaded and verified.");
        } else {
            setText(elements.progressText, "");
        }
    }

    function render(data) {
        state.status = data;
        renderBanner(data);
        if (
            data.consent_required &&
            !state.consentShown &&
            !state.dialogOpen &&
            !state.consentOpen
        ) {
            state.consentShown = true;
            openConsent();
        }
        if (
            data.install_error &&
            !state.errorShown &&
            !state.consentOpen &&
            !state.dialogOpen
        ) {
            state.errorShown = true;
            openDialog();
        }
        if (state.dialogOpen) renderDialog(data);
    }

    function openDialog() {
        if (!elements.dialog || elements.dialog.open) return;
        if (elements.consent && elements.consent.open) return;
        state.dialogOpen = true;
        elements.dialog.showModal();
        if (state.status) renderDialog(state.status);
    }

    function closeDialog() {
        if (elements.dialog && elements.dialog.open) elements.dialog.close();
        state.dialogOpen = false;
    }

    function openConsent() {
        if (!elements.consent || elements.consent.open) return;
        state.consentOpen = true;
        elements.consent.showModal();
    }

    function closeConsent() {
        if (elements.consent && elements.consent.open) elements.consent.close();
        state.consentOpen = false;
    }

    async function refresh() {
        if (state.busy || !state.bridge) return;
        state.busy = true;
        try {
            const data = await state.bridge.update_status();
            if (data && typeof data === "object") render(data);
        } catch (error) {
        } finally {
            state.busy = false;
        }
    }

    function startBridge() {
        if (state.bridge) return true;
        const api = bridge();
        if (!api) return false;
        state.bridge = api;
        elements.button.disabled = false;
        if (elements.settingsAuto) elements.settingsAuto.disabled = false;
        if (elements.settingsCheck) elements.settingsCheck.disabled = false;
        refresh();
        return true;
    }

    elements.button.addEventListener("click", async () => {
        if (!state.bridge) return;
        openDialog();
        try {
            const data = await state.bridge.check_for_updates(true);
            if (data && typeof data === "object") render(data);
        } catch (error) {
        }
        await refresh();
    });

    if (elements.bannerOpen) {
        elements.bannerOpen.addEventListener("click", () => {
            openDialog();
            if (state.status) renderDialog(state.status);
        });
    }

    if (elements.bannerLater) {
        elements.bannerLater.addEventListener("click", async () => {
            if (!state.bridge) return;
            state.bannerDismissed = true;
            setVisible(elements.banner, false);
            try {
                const data = await state.bridge.postpone_update();
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            await refresh();
        });
    }

    if (elements.consentYes) {
        elements.consentYes.addEventListener("click", async () => {
            closeConsent();
            if (!state.bridge) return;
            try {
                const data = await state.bridge.set_update_consent(true);
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            await refresh();
        });
    }

    if (elements.consentNo) {
        elements.consentNo.addEventListener("click", async () => {
            closeConsent();
            if (!state.bridge) return;
            try {
                const data = await state.bridge.set_update_consent(false);
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            await refresh();
        });
    }

    if (elements.close) {
        elements.close.addEventListener("click", closeDialog);
    }

    elements.dialog.addEventListener("close", () => {
        state.dialogOpen = false;
        if (state.status && state.status.install_error && state.bridge) {
            state.bridge.clear_update_error().catch(() => {});
            state.status.install_error = null;
        }
    });

    if (elements.consent) {
        elements.consent.addEventListener("close", () => {
            state.consentOpen = false;
        });
        elements.consent.addEventListener("cancel", (event) => {
            event.preventDefault();
        });
    }

    if (elements.check) {
        elements.check.addEventListener("click", async () => {
            if (!state.bridge) return;
            try {
                const data = await state.bridge.check_for_updates(true);
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            await refresh();
        });
    }

    if (elements.install) {
        elements.install.addEventListener("click", async () => {
            if (!state.bridge) return;
            let started = false;
            elements.install.disabled = true;
            try {
                if (state.status && state.status.phase === "ready") {
                    const result = await state.bridge.install_update();
                    if (result && result.ok) {
                        started = true;
                        state.status.phase = "installing";
                        setText(elements.stateText, result.message || "Restarting Spendly...");
                        setVisible(elements.progress, false);
                        setVisible(elements.install, false);
                        setText(elements.title, "Restarting Spendly");
                    } else {
                        elements.stateText.classList.add("error");
                        setText(
                            elements.stateText,
                            (result && result.message) || "The update could not be started."
                        );
                    }
                } else {
                    const data = await state.bridge.download_update();
                    if (data && typeof data === "object") render(data);
                }
            } catch (error) {
                elements.stateText.classList.add("error");
                setText(elements.stateText, "The update could not be started.");
            } finally {
                if (!started) {
                    elements.install.disabled = false;
                    await refresh();
                }
            }
        });
    }

    if (elements.cancel) {
        elements.cancel.addEventListener("click", async () => {
            if (!state.bridge) return;
            try {
                const data = await state.bridge.cancel_update_download();
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            await refresh();
        });
    }

    if (elements.skip) {
        elements.skip.addEventListener("click", async () => {
            if (!state.bridge) return;
            const version = state.status && state.status.update
                ? state.status.update.version
                : "";
            if (version) {
                try {
                    const data = await state.bridge.skip_update(version);
                    if (data && typeof data === "object") render(data);
                } catch (error) {
                }
            }
            closeDialog();
            await refresh();
        });
    }

    if (elements.later) {
        elements.later.addEventListener("click", async () => {
            if (!state.bridge) return;
            try {
                const data = await state.bridge.postpone_update();
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            closeDialog();
            await refresh();
        });
    }

    if (elements.autoCheck) {
        elements.autoCheck.addEventListener("change", async () => {
            if (!state.bridge) return;
            try {
                const data = await state.bridge.set_update_consent(elements.autoCheck.checked);
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            await refresh();
        });
    }

    if (elements.settingsAuto) {
        elements.settingsAuto.addEventListener("change", async () => {
            if (!state.bridge) return;
            try {
                const data = await state.bridge.set_update_consent(elements.settingsAuto.checked);
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            await refresh();
        });
    }

    if (elements.settingsCheck) {
        elements.settingsCheck.addEventListener("click", async () => {
            if (!state.bridge) return;
            openDialog();
            try {
                const data = await state.bridge.check_for_updates(true);
                if (data && typeof data === "object") render(data);
            } catch (error) {
            }
            await refresh();
        });
    }

    if (elements.releaseLink) {
        elements.releaseLink.addEventListener("click", async (event) => {
            event.preventDefault();
            if (!state.bridge) return;
            try {
                await state.bridge.open_release_page(elements.releaseLink.dataset.url || "");
            } catch (error) {
            }
        });
    }

    if (!startBridge()) {
        window.addEventListener("pywebviewready", startBridge, { once: true });
        let attempts = 0;
        const timer = setInterval(() => {
            if (startBridge() || ++attempts >= 100) clearInterval(timer);
        }, 100);
    }

    setInterval(refresh, 1500);
})();
