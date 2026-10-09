# app/

PyQt6 desktop UI. The main window is a tab shell; each tab is a feature in [`sections/`](sections/), built from the shared kit in [`ui/`](ui/).

| Path | Purpose |
|---|---|
| `main_window.py` | Top-level `QMainWindow` — toolbar, tabs, loading/saving the profile file, joining worker threads on close. |
| `context.py` | `AppContext` (what a tab may ask of the app: profile, applications, save, status bar) and the shared `ResearchCache`. |
| `importers.py` | LinkedIn-export and resume-PDF import flows, shared by the main window and onboarding. |
| `dialogs/` | `onboarding.py` (first-run wizard) and `import_review.py` (checkable review of imported data). |
| `ui/` | Reusable widgets and plumbing with no feature logic — see below. |
| `sections/` | One subpackage per tab. |
| `theme.py` | Light/dark/system theme switching; macOS appearance listener. |
| `style.py` | Color palettes and the global stylesheet. Widgets are styled by `objectName`, never inline CSS. |

## `ui/`

| File | Purpose |
|---|---|
| `widgets.py` | Small factories and helpers: `label`, `hint`, `button`, `BusyButton`, `field`, `page_layout`, `section_header`, `scroll_area`, `set_status`, `confirm`, … |
| `workers.py` | `Worker` / `CallWorker` / `StreamWorker` and `WorkerPool`, which owns a widget's `QThread`s. Every background job goes through a pool. |
| `sidebar_stack.py` | `SidebarStack` — the sidebar + stacked-pages container used by every multi-page tab. Pages may define `on_shown()`. |
| `latex_preview.py` | `PdfView` and `LatexPreviewPane` (debounced off-thread LaTeX compile with PDF/error display). Imports QtWebEngine. |
| `feedback_panel.py` | Dismissable panel that accumulates streamed AI feedback. |
| `application_picker.py` | "Fill from application" combo box. |
