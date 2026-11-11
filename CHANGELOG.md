# Changelog

All notable changes to Spendly are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0]

Recurring expenses, an Upcoming review queue, templates, duplicate expenses, and
category ordering.

### Added

- **Recurring expenses.** Add weekly, monthly, or yearly rules with an amount,
  category, description, start date, optional end date, and next due date. Due
  rules appear in a new Upcoming card on the dashboard.
- **Review queue.** Post, skip, or edit each due occurrence from the dashboard.
  Edit one occurrence on the spot, or change the whole series in Settings.
- **Optional auto-post.** Rules post automatically only when explicitly enabled.
  Review stays the default, and each due date is recorded at most once.
- **Templates.** Save frequently used entries in Settings and add one to today's
  expenses with a single click from the dashboard.
- **Duplicate expenses.** Copy any expense from the dashboard or search results,
  dated today.
- **Category ordering.** Move categories up or down in Settings. The order is
  saved in the existing position column and used throughout the app.

### Changed

- Category deletion is blocked while a category is used by expenses, recurring
  rules, or templates. Renaming a category also updates recurring rules and
  templates.
- Settings now includes recurring rules and templates alongside periods,
  categories, budgets, currency, and appearance.

### Notes

- Existing databases upgrade automatically and are backed up before migrating
  to schema version 2. Each upgrade is recorded in `migration.log`.
- Month-end and leap-year due dates stay anchored to the rule's original date,
  so dates do not drift. Skipped dates are recorded and never posted later, and
  deleting a rule keeps expenses that were already posted.

## [1.3.2]

Fixes release notes appearing as raw Markdown in the update dialog and makes the
installer much smaller.

### Changed

- **Smaller installer.** The setup now bundles the WebView2 Evergreen Bootstrapper
  instead of the 215 MB standalone runtime, reducing the download from about
  221 MB to about 19 MB. The runtime is downloaded during setup only when it is
  missing.

### Fixed

- **Release notes formatting.** Update descriptions now render headings, lists,
  emphasis, links, code, and tables like GitHub. Links open in the default
  browser instead of replacing the app.

## [1.3.1]

Fixes the dashboard total being clipped in gradient themes.

### Fixed

- **Dashboard total clipping.** The amount shown in the hero card no longer loses
  the right edge of its last digit in themes that render the total with a
  gradient.

## [1.3.0]

Spending insights, custom categories, category budgets, and system theme support.

### Added

- **Category breakdown.** The dashboard now shows a donut chart and legend for
  spending by category, with theme-aware colors and per-category expense counts.
- **Pacing insights.** A cumulative spending chart compares actual spending with
  the ideal pace and reports safe-to-spend per day, daily burn rate, projected
  total, and days left in the period.
- **Custom categories.** Add, rename, recolor, and delete categories from
  Settings. Existing expense categories are adopted automatically, and
  categories that still have expenses cannot be deleted.
- **Category budgets.** Set an optional budget for each category. The dashboard
  and Settings show progress, budget percentage, and the amount remaining for
  the selected period.
- **System theme.** The theme picker now includes a System option that follows
  the operating system's light or dark preference, using Light SaaS and Dark
  Fintech respectively.

### Changed

- Category badges throughout the dashboard and search results now use the
  selected theme's category colors.
- Settings now combines category and budget management with the existing
  period, currency, appearance, and update controls.

### Notes

- Existing databases upgrade automatically. A new `categories` table is created
  and seeded with the default categories, and category names already present in
  expenses are added to each profile's category list.

## [1.2.1]

Fixes in-app updates failing to launch their installer or restart the app.

### Fixed

- **In-app updates on Windows.** The update helper now starts with the correct
  process flags, so Spendly closes, installs the downloaded update, and reopens
  automatically instead of stopping silently after the download.

### Notes

- Spendly 1.1.0 and 1.2.0 cannot install this release from the in-app updater
  because the updater itself is affected. Install `Spendly-1.2.1-Setup.exe`
  manually once; later updates work normally.

## [1.2.0]

A dedicated settings page, currency-aware amounts, expense editing, undo, and search.

### Added

- **Settings page.** Manage saved periods, cycle settings, currency, appearance,
  and desktop update preferences from one place.
- **Currency support.** Choose INR (default), USD, EUR, or GBP in Settings. The
  choice is remembered and applied to dashboard totals, limits, history, and
  search results.
- **Expense editing.** Update the date, category, amount, or description of any
  saved expense from the dashboard or search results.
- **Undo after delete.** Deleting an expense now shows a themed toast with an
  Undo action that restores the expense immediately.
- **Expense search.** Filter the current period's transactions as you type, or
  use the search page to find expenses by description, category, date, or
  amount across the current period or all saved data.
- **Desktop update controls in Settings.** See the installed version, toggle
  automatic update checks, and start a manual check without opening the update
  dialog first.

### Changed

- Period settings is now the general Settings page, with the existing period
  and cycle controls alongside the new preferences.
- All money values are formatted with the selected currency symbol and locale
  conventions instead of showing bare numbers.

## [1.1.0]

Desktop update notifications, one-click updates, and a lighter updater download.

### Added

- **Update notifications.** After a one-time consent prompt, the desktop app
  checks GitHub once a day for a newer release and shows a themed banner and
  dialog with the version and release notes.
- **One-click updates.** Download the update inside the app, verify its
  SHA-256 digest, install it after Spendly exits, and relaunch automatically.
- **Portable updates.** Portable builds download and unpack the portable zip
  while keeping the `data\` folder intact.
- **Lite update installer.** Existing installs download a separate
  `Spendly-<version>-Update.exe` without the bundled WebView2 runtime,
  reducing the update from about 221 MB to about 16 MB.
- **Release tooling.** `build/release.ps1` builds all artifacts, tags the
  release, publishes it to GitHub, and verifies the uploaded asset names.

### Changed

- Update checks are opt-in on first launch, and the setting can be changed
  later from the update dialog.

### Security

- Update checks send only the app version and the request IP address to GitHub.
- Downloaded updates are verified against the SHA-256 digest published by
  GitHub before the installer or portable package is used.

## [1.0.0] - 2026-11-05

The first stable release of Spendly: a local-first expense tracker for the web
and Windows, shipped with ten complete interface themes.

**Downloads:** [Windows installer](https://github.com/robolivice/spendly/releases/download/v1.0.0/Spendly-1.0.0-Setup.exe) &middot; [Portable build](https://github.com/robolivice/spendly/releases/download/v1.0.0/Spendly-1.0.0-portable.zip)

**Note:** The Windows binaries are unsigned, so SmartScreen may show an unknown publisher warning on other machines.

### Added

- **Multiple budget profiles.** Create, rename, switch between, and delete
  profiles without sharing data between them.
- **Flexible monthly cycles.** Set up a first period with any start and end
  date, then let Spendly generate future periods from the cycle end day.
  Month-end dates are handled correctly, including shorter months.
- **Custom ranges and saved periods.** Browse any date range, save it as a
  period, update an existing period, or adjust its dates. Overlapping ranges
  are validated before they are saved.
- **Budget limits and pacing.** Set an optional limit per period, inherit the
  latest limit into new periods, and see spent, remaining, percentage used,
  and On track / Near limit / Over limit status.
- **Expense tracking.** Record a date, category, amount, and optional
  description. Categories include Food, Transport, Shopping, Bills, and Other.
  Sort the transaction table by date, category, amount, or description, and
  delete mistakes from the same view.
- **Spending history.** Review saved periods by year, compare spending against
  limits, and see summary counts for saved periods, total spent, and periods
  that finished over or near their limit.
- **Ten complete themes.** Dark Fintech, Budget Cockpit, Light SaaS, Neon
  Glass, Paper Ledger, Neo Brutal, Midnight Gold, Arctic Aurora, Ember, and
  Desert Clay. Each theme changes layout, typography, color, and component
  styling rather than only the accent color.
- **Theme gallery.** Search and filter themes by name, style, mode, and shell,
  preview desktop and mobile screenshots, and apply a theme from the gallery.
  The selected theme is remembered across sessions.
- **Responsive web app.** The Flask interface adapts to desktop and mobile
  viewports, with the same data and features in both.
- **Windows desktop app.** The Flask app runs inside a native pywebview window
  using Microsoft Edge WebView2, with a single-instance lock, remembered window
  size and position, and persistent WebView storage.
- **CSV export.** Export all recorded expenses to a CSV file from the desktop
  header.
- **Safe database import.** Choose an existing Spendly database from the
  desktop header. Imports are validated before the live database is replaced,
  a `before-import-*.db` backup is created first, and the previous database is
  restored if the copy fails.
- **Database validation.** Imports accept Spendly databases with extra tables
  and columns for forward compatibility. Unrelated SQLite schemas, missing core
  tables or columns, non-SQLite files, and corrupt databases are rejected
  without changing current data.
- **Foreground dialogs.** Import confirmation, import rejection, import
  success, and export results are shown in native dialogs owned by the app
  window and kept above it.
- **Startup backups.** Every desktop launch writes a database snapshot to
  `backups\`, keeping the newest 10.
- **First-run migration.** On first launch, Spendly looks for an existing
  `expense.db` or `spendly.db` next to the executable or in the working
  directory and copies the newest match into its data directory.
- **Offline Windows installer.** Inno Setup installs Spendly per user to
  `%LOCALAPPDATA%\Programs\Spendly`, creates Start Menu and optional desktop
  shortcuts, and bundles the WebView2 Evergreen Standalone Installer so no
  internet connection is required on the target machine.
- **Portable build.** Run Spendly from a folder or removable drive with the
  database, backups, settings, and logs stored in `data\` beside the executable.
- **Build tooling.** PyInstaller packaging, portable archive creation, icon
  application, and Inno Setup compilation are available through
  `build/build.ps1`.
- **Logging and diagnostics.** Rotating application logs, migration history,
  and a documented data folder make support and troubleshooting straightforward.

### Security

- Spendly binds only to `127.0.0.1` and makes no outbound network requests.
- No accounts, cloud services, analytics, or telemetry are used. All data
  remains in the local SQLite database and its backups.
- Database imports validate the source read-only and require Spendly's core
  `profiles` and `expenses` tables before any data is replaced.
- The app keeps startup and pre-import backups, and restores the pre-import
  database if an import fails.

[1.4.0]: https://github.com/robolivice/spendly/compare/v1.3.2...v1.4.0
[1.3.2]: https://github.com/robolivice/spendly/compare/v1.3.1...v1.3.2
[1.3.1]: https://github.com/robolivice/spendly/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/robolivice/spendly/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/robolivice/spendly/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/robolivice/spendly/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/robolivice/spendly/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/robolivice/spendly/releases/tag/v1.0.0
