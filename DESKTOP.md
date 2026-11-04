# Spendly 1.0.0 — Desktop

Spendly runs as a Windows desktop app: the existing Flask app is hosted in-process and rendered by pywebview (EdgeChromium/WebView2). The web version still works with `python Spendly/app.py`.

## Run from source

```powershell
python -m pip install -r Spendly/requirements-dev.txt
python Spendly/desktop.py
```

Useful during development:

```powershell
$env:SPENDLY_DEBUG = "1"          # DevTools, console logs, right-click menu
$env:SPENDLY_DATA_DIR = "C:\tmp\spendly-data"   # throwaway data
```

## Where data lives

Installed app: `%LOCALAPPDATA%\Spendly\`

| Path | Contents |
|---|---|
| `spendly.db` | SQLite database (WAL mode) |
| `settings.json` | Flask secret key, window geometry |
| `backups\` | Startup snapshots, newest 10 kept |
| `webview\` | pywebview cookies/localStorage |
| `logs\app.log` | Rotating runtime log |
| `migration.log` | Database imports and backups |

Portable builds (a `portable.txt` marker next to `Spendly.exe`) keep everything in `data\` beside the executable instead.

On first launch Spendly looks for an existing `expense.db`/`spendly.db` next to the executable or in the working directory and copies the newest match. Anything else can be imported with the **Import database** button in the header. Files that do not have Spendly's core tables/columns are rejected before any data is replaced; extra tables and columns are allowed.

## Desktop features

- Single instance; launching again focuses the running window.
- Fixed local port `47821`, persistent WebView storage, so the selected theme survives restarts.
- Window size and position are remembered.
- Header actions in the desktop app: **Export CSV** and **Import database**. Dialogs are owned by the app window and open in the foreground.
- Every startup writes a database snapshot to `backups\`.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File build/build.ps1
```

Outputs:

- `dist/Spendly/Spendly.exe` — one-folder build
- `dist/Spendly-1.0.0-portable.zip` — portable build (data beside the exe)
- `dist/Spendly-1.0.0-Setup.exe` — offline installer, if Inno Setup 6 is installed

Individual steps can be skipped: `-SkipVenv`, `-SkipIcon`, `-SkipInstaller`.

### Installer

Install `build/installer.iss` with [Inno Setup 6](https://jrsoftware.org/isinfo.php). It installs per-user to `%LOCALAPPDATA%\Programs\Spendly`, creates Start Menu and optional desktop shortcuts, refuses to run while Spendly is open, and leaves user data in `%LOCALAPPDATA%\Spendly` on uninstall.

The setup is fully offline: it bundles Microsoft's WebView2 Evergreen Standalone Installer (`build/MicrosoftEdgeWebView2RuntimeInstallerX64.exe`, about 215 MB) and runs it silently only when the WebView2 runtime is missing. `build.ps1` downloads that file automatically if it is not present. No internet connection is needed on the target machine.

### Icon

`build/icon.ico` is the app icon (16, 20, 24, 32, 40, 48, 64 and 256 px). `build.ps1` copies it to `Spendly/assets/Spendly.ico` before packaging, and both the executable and the setup use it. `Spendly/assets/make_icon.py` is the original icon generator and is no longer part of the build.

## Release checklist

- [ ] `build.ps1` completes with no warnings that matter
- [ ] Test on a clean Windows VM without Python
- [ ] Test the installer on an offline Windows VM (WebView2 installs from the bundle)
- [ ] All 10 themes render and the chosen theme survives a restart
- [ ] Window geometry is restored
- [ ] Startup backup appears in `%LOCALAPPDATA%\Spendly\backups`
- [ ] CSV export opens correctly in Excel
- [ ] Import database creates a `before-import-*.db` backup
- [ ] Import rejects unrelated databases without changing current data
- [ ] Import and export result dialogs appear in the foreground
- [ ] Second launch focuses the first window
- [ ] Install → upgrade → uninstall keeps user data

## Notes

- The build is unsigned, so SmartScreen may show "Unknown publisher" on other machines.
- WebView2 is preinstalled on Windows 11 and current Windows 10; the bundled standalone installer covers older and offline images.
- The app never binds beyond `127.0.0.1` and requires no network access.
