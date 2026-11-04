from __future__ import annotations

import csv
import ctypes
import logging
import os
import socket
import sys
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import paths
import settings

APP_TITLE = paths.WINDOW_TITLE
PORT = 47821
MUTEX_NAME = "Spendly.Desktop.SingleInstance"
MAX_BACKUPS = 10

log = logging.getLogger("spendly.desktop")
_mutex_handle = None


def _enable_high_dpi() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _window_handle(window=None) -> int | None:
    if sys.platform != "win32":
        return None

    if window is None:
        try:
            import webview

            window = webview.windows[0] if webview.windows else None
        except Exception:
            window = None
    if window is None:
        return None

    native = getattr(window, "native", None)
    handle = getattr(native, "Handle", None)
    if handle is not None:
        try:
            value = int(handle)
            if value:
                return value
        except (TypeError, ValueError):
            pass

    try:
        value = ctypes.windll.user32.FindWindowW(
            None, getattr(window, "title", None) or APP_TITLE
        )
        return int(value) if value else None
    except Exception:
        return None


def _native_dialog(title: str, text: str, flags: int, window=None) -> int | None:
    if sys.platform != "win32":
        return None

    user32 = ctypes.windll.user32
    user32.MessageBoxW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_wchar_p,
        ctypes.c_uint,
    ]
    user32.MessageBoxW.restype = ctypes.c_int

    owner = _window_handle(window)
    result = user32.MessageBoxW(
        ctypes.c_void_p(owner) if owner else None,
        text,
        title,
        flags,
    )
    return int(result)


def _message(
    title: str, text: str, error: bool = False, window=None
) -> None:
    if sys.platform == "win32":
        flags = (0x10 if error else 0x40) | 0x10000 | 0x40000
        _native_dialog(title, text, flags, window=window)
    else:
        print(f"{title}: {text}", file=sys.stderr if error else sys.stdout)


def _confirm(window, title: str, text: str) -> bool:
    if sys.platform == "win32":
        flags = 0x04 | 0x30 | 0x100 | 0x10000 | 0x40000
        result = _native_dialog(title, text, flags, window=window)
        if result is not None:
            return result == 6

    if window is None:
        return False
    return bool(window.create_confirmation_dialog(title, text))


def _setup_logging() -> None:
    handler = RotatingFileHandler(
        paths.log_dir() / "app.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    if os.environ.get("SPENDLY_DEBUG"):
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(stream)


def _acquire_single_instance() -> bool:
    global _mutex_handle
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _mutex_handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.get_last_error() != 183


def _focus_existing_window() -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    handle = user32.FindWindowW(None, APP_TITLE)
    if handle:
        user32.ShowWindow(handle, 9)
        user32.SetForegroundWindow(handle)


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _first_path(result) -> str | None:
    if not result:
        return None
    if isinstance(result, (list, tuple)):
        return str(result[0]) if result else None
    return str(result)


def backup_database() -> Path:
    import db

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = paths.backup_dir() / f"spendly-{stamp}.db"
    db.backup_to(destination)

    existing = sorted(
        paths.backup_dir().glob("spendly-*.db"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for stale in existing[MAX_BACKUPS:]:
        try:
            stale.unlink()
        except OSError:
            log.warning("Could not remove old backup %s", stale)

    return destination


def _current_window():
    import webview

    return webview.windows[0] if webview.windows else None


def write_csv(destination: Path) -> Path:
    import db

    destination = Path(destination)
    if destination.suffix.lower() != ".csv":
        destination = destination.with_suffix(".csv")

    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["profile", "date", "category", "amount", "description"])
        for row in db.export_rows():
            writer.writerow(
                [
                    row["profile"],
                    row["date"],
                    row["category"],
                    row["amount"],
                    row["description"] or "",
                ]
            )
    return destination


def export_csv(window=None) -> None:
    import webview

    window = window or _current_window()
    if window is None:
        return

    filename = f"spendly-export-{date.today().isoformat()}.csv"
    selected = _first_path(
        window.create_file_dialog(
            dialog_type=webview.FileDialog.SAVE,
            directory=str(Path.home()),
            save_filename=filename,
            file_types=("CSV files (*.csv)",),
        )
    )
    if not selected:
        return

    try:
        target = write_csv(Path(selected))
        log.info("Exported CSV to %s", target)
        _message(APP_TITLE, f"Exported {target.name}.", window=window)
    except OSError as error:
        log.exception("CSV export failed")
        _message(
            APP_TITLE,
            f"Could not export CSV:\n\n{error}",
            error=True,
            window=window,
        )


def import_database(window=None) -> None:
    import webview

    import migration

    window = window or _current_window()
    if window is None:
        return

    selected = _first_path(
        window.create_file_dialog(
            dialog_type=webview.FileDialog.OPEN,
            directory=str(Path.home()),
            file_types=("SQLite database (*.db)",),
        )
    )
    if not selected:
        return

    source = Path(selected)
    try:
        migration.validate_database(source)
    except migration.InvalidDatabase as error:
        log.warning("Database import rejected for %s: %s", source, error)
        _message(APP_TITLE, str(error), error=True, window=window)
        return

    confirmed = _confirm(
        window,
        "Import database",
        "This replaces the current Spendly data with the selected database.\n\n"
        "A backup of the current data is saved first. Continue?",
    )
    if not confirmed:
        return

    ok, message = migration.replace_database(source)
    if ok:
        log.info(message)
        window.evaluate_js("window.location.assign('/')")
    _message(APP_TITLE, message, error=not ok, window=window)


class DesktopApi:

    def export_csv(self) -> bool:
        export_csv(_current_window())
        return True

    def import_database(self) -> bool:
        import_database(_current_window())
        return True


def main() -> int:
    if "--version" in sys.argv:
        print(APP_TITLE)
        return 0

    _enable_high_dpi()
    _setup_logging()

    def _log_unhandled(exc_type, exc_value, traceback):
        log.critical("Unhandled exception", exc_info=(exc_type, exc_value, traceback))

    sys.excepthook = _log_unhandled
    log.info("Starting %s", APP_TITLE)

    try:
        if not _acquire_single_instance():
            log.info("Another instance is already running; focusing it")
            _focus_existing_window()
            return 0

        import migration

        migrated = migration.migrate_if_needed()
        if migrated is not None:
            log.info("Imported existing database from %s", migrated)

        os.environ["SPENDLY_DESKTOP"] = "1"
        import app as app_module

        try:
            snapshot = backup_database()
            log.info("Startup backup: %s", snapshot)
        except Exception:
            log.exception("Startup backup failed")

        if not _port_available(PORT):
            message = (
                f"Port {PORT} is already in use.\n\n"
                "Close the other application using it, or restart Spendly."
            )
            log.error(message)
            _message(APP_TITLE, message, error=True)
            return 1

        import webview

        state = settings.window_state()
        window = webview.create_window(
            APP_TITLE,
            app_module.app,
            width=state["width"],
            height=state["height"],
            x=state["x"],
            y=state["y"],
            min_size=(920, 620),
            background_color="#0a0c12",
            text_select=False,
            js_api=DesktopApi(),
        )

        def _on_closing(*_args):
            try:
                settings.set(
                    "window",
                    {
                        "width": window.width,
                        "height": window.height,
                        "x": window.x,
                        "y": window.y,
                    },
                )
            except Exception:
                log.exception("Could not save window geometry")

        window.events.closing += _on_closing

        webview.start(
            http_server=True,
            http_port=PORT,
            private_mode=False,
            storage_path=str(paths.webview_dir()),
            icon=str(paths.resource_path("assets", "Spendly.ico")),
            debug=bool(os.environ.get("SPENDLY_DEBUG")),
        )
        log.info("Spendly closed")
        return 0
    except Exception as error:
        log.exception("Fatal startup error")
        _message(
            APP_TITLE,
            f"Spendly could not start.\n\n{error}\n\n"
            f"See {paths.log_dir() / 'app.log'} for details.",
            error=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
