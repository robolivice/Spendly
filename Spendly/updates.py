from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import paths
import settings

API_URL = "https://api.github.com/repos/robolivice/spendly/releases/latest"
RELEASES_URL = "https://github.com/robolivice/spendly/releases/latest"
CHECK_INTERVAL = timedelta(hours=24)
SNOOZE_INTERVAL = timedelta(days=7)
CACHE_AGE = timedelta(days=30)
USER_AGENT = f"Spendly/{paths.APP_VERSION}"


class UpdateError(Exception):
    pass


class UpdateCancelled(Exception):
    pass


def parse_version(value):
    if not isinstance(value, str):
        return None
    match = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", value.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def version_string(value):
    parsed = parse_version(value)
    if parsed is None:
        return None
    return ".".join(str(part) for part in parsed)


def is_newer(candidate, current):
    left = parse_version(candidate)
    right = parse_version(current)
    return bool(left and right and left > right)


def digest_for(asset):
    if not isinstance(asset, dict):
        return None
    value = asset.get("digest")
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if value.startswith("sha256:"):
        value = value[7:]
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        return None
    return value


def select_asset(assets, version, portable):
    if not isinstance(assets, list):
        return None
    normalized = version_string(version)
    if not normalized:
        return None
    if portable:
        names = [f"Spendly-{normalized}-portable.zip"]
    else:
        names = [
            f"Spendly-{normalized}-Update.exe",
            f"Spendly-{normalized}-Setup.exe",
        ]
    by_name = {
        item.get("name"): item
        for item in assets
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for name in names:
        asset = by_name.get(name)
        if asset is not None:
            return asset
    return None


def updates_supported():
    if os.environ.get("SPENDLY_DISABLE_UPDATE_CHECK"):
        return False
    return paths.is_frozen() or os.environ.get("SPENDLY_UPDATE_TEST") == "1"


def updates_dir():
    path = paths.data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_latest():
    url = os.environ.get("SPENDLY_UPDATE_URL") or API_URL
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise UpdateError(f"GitHub returned HTTP {error.code}.") from error
    except URLError as error:
        raise UpdateError("Could not reach GitHub.") from error
    except (OSError, ValueError) as error:
        raise UpdateError("GitHub returned an invalid response.") from error

    if not isinstance(payload, dict):
        raise UpdateError("GitHub returned an invalid response.")
    if payload.get("draft") or payload.get("prerelease"):
        raise UpdateError("The latest release is not a stable release.")

    version = version_string(payload.get("tag_name"))
    if not version:
        raise UpdateError("The latest release tag is not a version.")

    assets = []
    for item in payload.get("assets") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        url = item.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        size = item.get("size")
        assets.append(
            {
                "name": name,
                "url": url,
                "size": int(size) if isinstance(size, (int, float)) else 0,
                "digest": item.get("digest")
                if isinstance(item.get("digest"), str)
                else None,
            }
        )

    notes = payload.get("body")
    if not isinstance(notes, str):
        notes = ""
    published = payload.get("published_at")
    if not isinstance(published, str):
        published = ""
    release_url = payload.get("html_url")
    if not isinstance(release_url, str) or not release_url:
        release_url = RELEASES_URL
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        name = f"Spendly {version}"
    tag = payload.get("tag_name")
    if not isinstance(tag, str) or not tag:
        tag = f"v{version}"

    return {
        "version": version,
        "tag": tag,
        "name": name,
        "notes": notes,
        "published_at": published,
        "release_url": release_url,
        "assets": assets,
    }


def _now():
    return datetime.now(timezone.utc)


def _parse_time(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def _helper_script(
    mode,
    asset_path,
    expected_hash,
    exe_path,
    app_dir,
    log_path,
    error_path,
    staging_dir,
    target_pid,
):
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"$log = {_ps_quote(log_path)}",
        f"$errorTarget = {_ps_quote(error_path)}",
        "function Write-UpdateLog([string]$Message) {",
        "    $folder = Split-Path -Parent $log",
        "    if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder -Force | Out-Null }",
        "    Add-Content -LiteralPath $log -Value ((Get-Date).ToString('s') + ' ' + $Message)",
        "}",
        "function Write-UpdateError([string]$Message) {",
        "    $folder = Split-Path -Parent $errorTarget",
        "    if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder -Force | Out-Null }",
        "    Set-Content -LiteralPath $errorTarget -Value $Message -Encoding UTF8",
        "}",
        "try {",
        f"    $targetPid = {int(target_pid)}",
        "    $process = Get-Process -Id $targetPid -ErrorAction SilentlyContinue",
        "    if ($process) { $process.WaitForExit() }",
        "    Start-Sleep -Milliseconds 500",
        "    if (Test-Path $errorTarget) { Remove-Item -LiteralPath $errorTarget -Force }",
        f"    $hash = (Get-FileHash -LiteralPath {_ps_quote(asset_path)} -Algorithm SHA256).Hash.ToLowerInvariant()",
        f"    if ($hash -ne {_ps_quote(expected_hash)}) {{ throw 'The downloaded file failed verification.' }}",
    ]

    if mode == "installer":
        lines += [
            f"    $installer = {_ps_quote(asset_path)}",
            "    $arguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS'",
            "    $result = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru",
            "    if ($result.ExitCode -ne 0 -and $result.ExitCode -ne 3010) { throw \"The installer exited with code $($result.ExitCode).\" }",
            "    Write-UpdateLog 'Update installed.'",
            f"    Start-Process -FilePath {_ps_quote(exe_path)} -WorkingDirectory {_ps_quote(app_dir)}",
        ]
    else:
        lines += [
            f"    $staging = {_ps_quote(staging_dir)}",
            "    if (Test-Path $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }",
            f"    Expand-Archive -LiteralPath {_ps_quote(asset_path)} -DestinationPath $staging -Force",
            "    $newExe = Join-Path $staging 'Spendly.exe'",
            "    $newInternal = Join-Path $staging '_internal'",
            "    if (-not (Test-Path $newExe)) { throw 'The update package is missing Spendly.exe.' }",
            "    if (-not (Test-Path $newInternal)) { throw 'The update package is missing _internal.' }",
            f"    $exe = {_ps_quote(exe_path)}",
            f"    $internal = {_ps_quote(Path(app_dir) / '_internal')}",
            "    $oldExe = $exe + '.old'",
            "    $oldInternal = $internal + '.old'",
            "    if (Test-Path $oldExe) { Remove-Item -LiteralPath $oldExe -Force }",
            "    if (Test-Path $oldInternal) { Remove-Item -LiteralPath $oldInternal -Recurse -Force }",
            "    Copy-Item -LiteralPath $exe -Destination $oldExe -Force",
            "    if (Test-Path $internal) { Move-Item -LiteralPath $internal -Destination $oldInternal -Force }",
            "    try {",
            "        Copy-Item -LiteralPath $newExe -Destination $exe -Force",
            "        Copy-Item -LiteralPath $newInternal -Destination $internal -Recurse -Force",
            "        if (Test-Path $oldInternal) { Remove-Item -LiteralPath $oldInternal -Recurse -Force }",
            "        if (Test-Path $oldExe) { Remove-Item -LiteralPath $oldExe -Force }",
            "        if (Test-Path $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }",
            "    } catch {",
            "        if (Test-Path $internal) { Remove-Item -LiteralPath $internal -Recurse -Force }",
            "        if (Test-Path $oldInternal) { Move-Item -LiteralPath $oldInternal -Destination $internal -Force }",
            "        if (Test-Path $oldExe) { Copy-Item -LiteralPath $oldExe -Destination $exe -Force }",
            "        throw",
            "    }",
            "    Write-UpdateLog 'Portable update applied.'",
            f"    Start-Process -FilePath {_ps_quote(exe_path)} -WorkingDirectory {_ps_quote(app_dir)}",
        ]

    lines += [
        "    Write-UpdateLog 'Update completed.'",
        "} catch {",
        "    $message = $_.Exception.Message",
        "    Write-UpdateLog ('Update failed: ' + $message)",
        "    Write-UpdateError $message",
        f"    if (Test-Path {_ps_quote(exe_path)}) {{ Start-Process -FilePath {_ps_quote(exe_path)} -WorkingDirectory {_ps_quote(app_dir)} }}",
        "    exit 1",
        "}",
    ]
    return "\n".join(lines) + "\n"


class UpdateManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._checking = False
        self._manual = False
        self._download = None
        self._download_job = None
        self._cancel = threading.Event()
        self._install_error = None
        self._started = False

    def start(self):
        if not updates_supported():
            return
        with self._lock:
            if self._started:
                return
            self._started = True
        self._clean_cache()
        self._read_install_error()
        self._drop_stale_release()
        self._restore_download()
        state = self._state()
        if state.get("consent") is True:
            self.check(manual=False)
        threading.Thread(
            target=self._schedule_worker,
            name="spendly-update-schedule",
            daemon=True,
        ).start()

    def _schedule_worker(self):
        while True:
            time.sleep(3600)
            try:
                self.check(manual=False)
            except Exception:
                pass

    def _state(self):
        value = settings.get("updates")
        if not isinstance(value, dict):
            value = {}
        return dict(value)

    def _write_state(self, state):
        settings.set("updates", state)

    def _read_install_error(self):
        target = paths.data_dir() / "update-error.txt"
        if not target.is_file():
            return
        try:
            message = target.read_text(encoding="utf-8-sig").strip()
        except OSError:
            message = ""
        try:
            target.unlink()
        except OSError:
            pass
        if message:
            self._install_error = message

    def _clean_cache(self):
        directory = updates_dir()
        now = _now()
        try:
            items = list(directory.iterdir())
        except OSError:
            return
        for item in items:
            try:
                if item.is_dir() and item.name.startswith("staging-"):
                    modified = datetime.fromtimestamp(
                        item.stat().st_mtime, timezone.utc
                    )
                    if now - modified > CACHE_AGE:
                        shutil.rmtree(item, ignore_errors=True)
                    continue
                if not item.is_file():
                    continue
                if item.name.endswith(".part"):
                    item.unlink()
                    continue
                modified = datetime.fromtimestamp(item.stat().st_mtime, timezone.utc)
                if now - modified > CACHE_AGE:
                    item.unlink()
            except OSError:
                continue

    def _drop_stale_release(self):
        with self._lock:
            state = self._state()
            release = state.get("cached_release")
            if not isinstance(release, dict):
                return
            if is_newer(release.get("version"), paths.APP_VERSION):
                return
            state["cached_release"] = None
            state["last_check"] = None
            state["last_error"] = None
            self._write_state(state)

    def _restore_download(self):
        state = self._state()
        release = state.get("cached_release")
        if not isinstance(release, dict) or not is_newer(
            release.get("version"), paths.APP_VERSION
        ):
            return
        asset = select_asset(
            release.get("assets") or [],
            release.get("version"),
            paths.is_portable(),
        )
        if not asset:
            return
        target = updates_dir() / asset["name"]
        try:
            if not target.is_file():
                return
            size = int(asset.get("size") or 0)
            if size and target.stat().st_size != size:
                return
            downloaded = target.stat().st_size
        except OSError:
            return
        with self._lock:
            self._download = {
                "state": "ready",
                "percent": 100,
                "downloaded": downloaded,
                "total": size or downloaded,
                "error": None,
                "asset_name": asset["name"],
                "target": str(target),
            }

    def _due(self, state):
        last = _parse_time(state.get("last_check"))
        if last is None:
            return True
        return _now() - last >= CHECK_INTERVAL

    def check(self, manual=False):
        if not updates_supported():
            return self.status()
        state = self._state()
        if not manual:
            if state.get("consent") is not True:
                return self.status()
            if not self._due(state):
                return self.status()
        with self._lock:
            if self._checking:
                return self.status()
            self._checking = True
            self._manual = bool(manual)
            self._install_error = None
        threading.Thread(
            target=self._check_worker,
            name="spendly-update-check",
            daemon=True,
        ).start()
        return self.status()

    def _check_worker(self):
        error = None
        release = None
        try:
            release = fetch_latest()
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__

        with self._lock:
            state = self._state()
            state["last_check"] = _now().isoformat()
            state["last_error"] = error
            if error is None:
                if release and is_newer(release.get("version"), paths.APP_VERSION):
                    state["cached_release"] = release
                else:
                    state["cached_release"] = None
            self._write_state(state)
            self._checking = False

    def status(self):
        with self._lock:
            state = self._state()
            checking = self._checking
            manual = self._manual
            install_error = self._install_error
            raw_download = dict(self._download) if self._download else None
            checking_error = state.get("last_error")
            cached = state.get("cached_release")
            consent = state.get("consent")
            last_check = state.get("last_check")
            skipped_version = state.get("skipped_version")
            postponed_until = _parse_time(state.get("postponed_until"))

        available = isinstance(cached, dict) and is_newer(
            cached.get("version"), paths.APP_VERSION
        )
        update = None
        asset = None
        skipped = False
        postponed = False
        if available:
            asset = select_asset(
                cached.get("assets") or [],
                cached.get("version"),
                paths.is_portable(),
            )
            update = {
                "version": cached.get("version"),
                "tag": cached.get("tag") or "",
                "name": cached.get("name") or "",
                "notes": (cached.get("notes") or "")[:8000],
                "published_at": cached.get("published_at") or "",
                "release_url": cached.get("release_url") or RELEASES_URL,
                "asset_name": asset.get("name") if asset else None,
                "asset_size": int(asset.get("size") or 0) if asset else 0,
                "has_digest": bool(digest_for(asset)) if asset else False,
            }
            skipped = skipped_version == update["version"]
            postponed = postponed_until is not None and _now() < postponed_until

        download = None
        if available and isinstance(raw_download, dict):
            download = {
                "state": raw_download.get("state") or "idle",
                "percent": int(raw_download.get("percent") or 0),
                "downloaded": int(raw_download.get("downloaded") or 0),
                "total": int(raw_download.get("total") or 0),
                "error": raw_download.get("error"),
            }

        if download and download["state"] == "installing":
            phase = "installing"
        elif download and download["state"] == "downloading":
            phase = "downloading"
        elif checking:
            phase = "checking"
        elif download and download["state"] == "ready":
            phase = "ready"
        elif install_error:
            phase = "install_error"
        elif download and download["state"] == "error":
            phase = "download_error"
        elif available:
            phase = "available"
        elif checking_error:
            phase = "error"
        elif last_check:
            phase = "up_to_date"
        else:
            phase = "idle"

        return {
            "supported": updates_supported(),
            "version": paths.APP_VERSION,
            "portable": paths.is_portable(),
            "phase": phase,
            "checking": checking,
            "manual": manual,
            "consent": consent,
            "consent_required": updates_supported() and consent is None,
            "auto_check": consent is True,
            "available": available,
            "skipped": skipped,
            "postponed": postponed,
            "update": update,
            "download": download,
            "error": checking_error,
            "install_error": install_error,
            "last_check": last_check,
        }

    def set_consent(self, allowed):
        with self._lock:
            state = self._state()
            state["consent"] = bool(allowed)
            state["last_error"] = None
            self._write_state(state)
        if allowed:
            self.check(manual=True)
        return self.status()

    def postpone(self):
        with self._lock:
            state = self._state()
            state["postponed_until"] = (_now() + SNOOZE_INTERVAL).isoformat()
            self._write_state(state)
            self._manual = False
        return self.status()

    def skip(self, version):
        normalized = version_string(version)
        with self._lock:
            if normalized:
                state = self._state()
                state["skipped_version"] = normalized
                self._write_state(state)
            self._manual = False
        return self.status()

    def start_download(self):
        with self._lock:
            if self._download and self._download.get("state") in (
                "downloading",
                "installing",
            ):
                return self.status()
            state = self._state()
            release = state.get("cached_release")
            if not isinstance(release, dict) or not is_newer(
                release.get("version"), paths.APP_VERSION
            ):
                return self._download_failure("No update is available.")
            asset = select_asset(
                release.get("assets") or [],
                release.get("version"),
                paths.is_portable(),
            )
            if asset is None:
                return self._download_failure(
                    "This release does not include a matching download."
                )
            expected = digest_for(asset)
            if not expected:
                return self._download_failure(
                    "This release does not publish a SHA-256 digest."
                )
            total = int(asset.get("size") or 0)
            target = updates_dir() / asset["name"]
            if target.is_file() and (not total or target.stat().st_size == total):
                self._download = {
                    "state": "ready",
                    "percent": 100,
                    "downloaded": target.stat().st_size,
                    "total": total or target.stat().st_size,
                    "error": None,
                    "asset_name": asset["name"],
                    "target": str(target),
                }
                return self.status()
            free = shutil.disk_usage(str(updates_dir())).free
            if total and free < total + 16 * 1024 * 1024:
                return self._download_failure(
                    "There is not enough free disk space for this update."
                )
            self._cancel.clear()
            self._download = {
                "state": "downloading",
                "percent": 0,
                "downloaded": 0,
                "total": total,
                "error": None,
                "asset_name": asset["name"],
                "target": str(target),
            }
            self._download_job = {
                "asset": asset,
                "digest": expected,
                "target": target,
            }
        threading.Thread(
            target=self._download_worker,
            name="spendly-update-download",
            daemon=True,
        ).start()
        return self.status()

    def _download_failure(self, message):
        with self._lock:
            self._download = {
                "state": "error",
                "percent": 0,
                "downloaded": 0,
                "total": 0,
                "error": message,
                "asset_name": None,
                "target": None,
            }
        return self.status()

    def _download_worker(self):
        with self._lock:
            job = dict(self._download_job) if self._download_job else None
        if not job:
            return
        asset = job["asset"]
        target = Path(job["target"])
        part = target.with_name(target.name + ".part")
        expected = job["digest"]
        downloaded = 0
        total = int(asset.get("size") or 0)
        digest = hashlib.sha256()
        try:
            request = Request(
                asset["url"],
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/octet-stream",
                },
            )
            with urlopen(request, timeout=30) as response:
                length = response.headers.get("Content-Length")
                if length and length.isdigit():
                    total = max(total, int(length))
                with part.open("wb") as handle:
                    while True:
                        if self._cancel.is_set():
                            raise UpdateCancelled()
                        chunk = response.read(128 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
                        downloaded += len(chunk)
                        percent = int(downloaded * 100 / total) if total else 0
                        with self._lock:
                            self._download = {
                                "state": "downloading",
                                "percent": min(percent, 99),
                                "downloaded": downloaded,
                                "total": total,
                                "error": None,
                                "asset_name": asset["name"],
                                "target": str(target),
                            }
            if self._cancel.is_set():
                raise UpdateCancelled()
            if digest.hexdigest().lower() != expected:
                raise UpdateError(
                    "The downloaded update failed SHA-256 verification."
                )
            os.replace(part, target)
            with self._lock:
                self._download = {
                    "state": "ready",
                    "percent": 100,
                    "downloaded": downloaded,
                    "total": total or downloaded,
                    "error": None,
                    "asset_name": asset["name"],
                    "target": str(target),
                }
        except UpdateCancelled:
            try:
                part.unlink()
            except OSError:
                pass
            with self._lock:
                self._download = {
                    "state": "idle",
                    "percent": 0,
                    "downloaded": 0,
                    "total": total,
                    "error": None,
                    "asset_name": asset["name"],
                    "target": str(target),
                }
        except Exception as exc:
            try:
                part.unlink()
            except OSError:
                pass
            with self._lock:
                self._download = {
                    "state": "error",
                    "percent": 0,
                    "downloaded": downloaded,
                    "total": total,
                    "error": str(exc) or exc.__class__.__name__,
                    "asset_name": asset["name"],
                    "target": str(target),
                }

    def cancel_download(self):
        self._cancel.set()
        return self.status()

    def install(self):
        with self._lock:
            download = dict(self._download) if self._download else None
            state = self._state()
            release = state.get("cached_release")
        if not download or download.get("state") != "ready":
            return self._install_failure("The update has not been downloaded yet.")
        if not paths.is_frozen():
            return self._install_failure(
                "Updates can only be installed from the packaged app."
            )
        if sys.platform != "win32":
            return self._install_failure("Updates can only be installed on Windows.")
        target = Path(download.get("target") or "")
        if not target.is_file():
            return self._install_failure("The downloaded update file is missing.")
        asset_name = download.get("asset_name")
        asset = None
        if isinstance(release, dict):
            for item in release.get("assets") or []:
                if isinstance(item, dict) and item.get("name") == asset_name:
                    asset = item
                    break
        expected = digest_for(asset)
        if not expected:
            return self._install_failure(
                "This release does not publish a SHA-256 digest."
            )
        try:
            if sha256_file(target).lower() != expected:
                return self._install_failure(
                    "The downloaded update failed verification."
                )
        except OSError as exc:
            return self._install_failure(
                f"Could not read the downloaded update: {exc}"
            )

        exe_path = Path(sys.executable).resolve()
        app_dir = exe_path.parent
        mode = "portable" if paths.is_portable() else "installer"
        staging = updates_dir() / f"staging-{release.get('version')}"
        script = _helper_script(
            mode,
            target,
            expected,
            exe_path,
            app_dir,
            paths.log_dir() / "update.log",
            paths.data_dir() / "update-error.txt",
            staging,
            os.getpid(),
        )
        script_path = Path(tempfile.gettempdir()) / f"spendly-update-{os.getpid()}.ps1"
        try:
            script_path.write_text(script, encoding="utf-8-sig")
        except OSError as exc:
            return self._install_failure(
                f"Could not prepare the update helper: {exc}"
            )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-WindowStyle",
                    "Hidden",
                    "-File",
                    str(script_path),
                ],
                close_fds=True,
                creationflags=creationflags,
            )
        except OSError as exc:
            return self._install_failure(
                f"Could not start the update helper: {exc}"
            )
        with self._lock:
            self._download["state"] = "installing"
            self._install_error = None
        return True, "Spendly will close and restart to install the update."

    def _install_failure(self, message):
        with self._lock:
            self._install_error = message
        return False, message

    def clear_error(self):
        with self._lock:
            self._install_error = None
        return self.status()

    def release_url(self, value=None):
        if isinstance(value, str) and value.startswith(
            "https://github.com/robolivice/spendly/"
        ):
            return value
        return RELEASES_URL


manager = UpdateManager()
