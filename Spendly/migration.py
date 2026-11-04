from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import db
import paths

log = logging.getLogger("spendly.migration")

SOURCE_NAMES = ("expense.db", "spendly.db")

REQUIRED_TABLES = ("profiles", "expenses")
REQUIRED_COLUMNS = {
    "profiles": ("id", "name"),
    "expenses": ("id", "profile_id", "date", "category", "amount"),
    "limits": ("id", "profile_id", "start_date", "end_date", "amount"),
    "periods": ("id", "profile_id", "start_date", "end_date", "limit_amount"),
    "cycles": ("profile_id", "end_day"),
}


class InvalidDatabase(ValueError):
    pass


def _readonly_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)


def _candidate_paths() -> list[Path]:
    roots = [paths.exe_dir()]
    try:
        roots.append(Path.cwd())
    except OSError:
        pass

    candidates: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        for name in SOURCE_NAMES:
            for candidate in (root / name, root / "Spendly" / name):
                key = str(candidate.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    candidates.append(candidate)
    return candidates


def _is_sqlite(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        conn = _readonly_connection(path)
        try:
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
        finally:
            conn.close()
        return True
    except (OSError, sqlite3.Error):
        return False


def validate_database(path: Path) -> None:
    path = Path(path)
    if not path.is_file():
        raise InvalidDatabase("That file does not exist.")
    if path.stat().st_size == 0:
        raise InvalidDatabase("That file is empty.")
    if not _is_sqlite(path):
        raise InvalidDatabase(
            "That file is not a readable SQLite database.\n\n"
            "Choose a Spendly database file."
        )

    try:
        conn = _readonly_connection(path)
        try:
            tables = {
                str(row[0]).lower(): str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if not tables:
                raise InvalidDatabase(
                    "This file is not a Spendly database.\n\n"
                    "It does not contain any tables."
                )

            missing_tables = [name for name in REQUIRED_TABLES if name not in tables]
            if missing_tables:
                names = ", ".join(f'"{name}"' for name in missing_tables)
                raise InvalidDatabase(
                    "This file is not a Spendly database.\n\n"
                    f"It is missing the required {names} table"
                    f"{'s' if len(missing_tables) > 1 else ''}."
                )

            for table, required in REQUIRED_COLUMNS.items():
                actual = tables.get(table)
                if actual is None:
                    continue
                columns = {
                    str(row[1]).lower()
                    for row in conn.execute(f'PRAGMA table_info("{actual}")')
                }
                missing = [name for name in required if name not in columns]
                if missing:
                    names = ", ".join(f'"{name}"' for name in missing)
                    raise InvalidDatabase(
                        "This file is not a Spendly database.\n\n"
                        f'The "{actual}" table is missing required '
                        f"column{'s' if len(missing) > 1 else ''}: {names}."
                    )

            check = conn.execute("PRAGMA quick_check").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise InvalidDatabase(
                    "This database appears to be damaged and cannot be imported."
                )
        finally:
            conn.close()
    except InvalidDatabase:
        raise
    except (OSError, sqlite3.Error):
        raise InvalidDatabase(
            "That file is not a readable SQLite database.\n\n"
            "Choose a Spendly database file."
        ) from None


def _copy_database(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    src = _readonly_connection(source)
    dst = sqlite3.connect(str(target))
    try:
        src.backup(dst)
        dst.commit()
    finally:
        dst.close()
        src.close()


def _record(message: str) -> None:
    log.info(message)
    try:
        with (paths.data_dir() / "migration.log").open("a", encoding="utf-8") as handle:
            stamp = datetime.now().isoformat(timespec="seconds")
            handle.write(f"{stamp} {message}\n")
    except OSError:
        log.exception("Could not write migration log")


def migrate_if_needed() -> Path | None:
    target = Path(db.DB)
    if target.exists() and target.stat().st_size > 0:
        return None

    sources = [path for path in _candidate_paths() if _is_sqlite(path)]
    if not sources:
        return None

    source = max(sources, key=lambda path: path.stat().st_mtime)
    _copy_database(source, target)
    db.setup()
    _record(f"Imported existing database {source} -> {target}")
    return source


def replace_database(source: Path) -> tuple[bool, str]:
    source = Path(source)
    try:
        validate_database(source)
    except InvalidDatabase as error:
        _record(f"Rejected database {source}: {error}")
        return False, str(error)

    target = Path(db.DB)
    backup = None
    if target.exists() and target.stat().st_size > 0:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = paths.backup_dir() / f"before-import-{stamp}.db"
        try:
            db.backup_to(backup)
        except (OSError, sqlite3.Error) as error:
            log.exception("Could not back up the current database")
            return False, f"Could not back up the current database:\n\n{error}"
        _record(f"Backed up current database to {backup}")

    try:
        _copy_database(source, target)
        db.setup()
    except (OSError, sqlite3.Error) as error:
        log.exception("Database import failed")
        if backup is not None:
            try:
                _copy_database(backup, target)
                db.setup()
                _record(f"Restored previous database after failed import from {source}")
            except (OSError, sqlite3.Error):
                log.exception("Could not restore the previous database")
        return False, f"Could not import {source.name}:\n\n{error}"

    _record(f"Imported database {source} -> {target}")
    return True, f"Imported {source.name}."
