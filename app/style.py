GLOBAL_STYLESHEET = """
/* ── App background ─────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #f3f2ef;
    font-family: -apple-system, "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #1d1d1d;
}

/* ── Toolbar ────────────────────────────────────────────────── */
QToolBar {
    background: #ffffff;
    border-bottom: 1px solid #dce6f0;
    padding: 6px 12px;
    spacing: 8px;
}
QToolBar QToolButton {
    background: #0a66c2;
    color: white;
    border: none;
    border-radius: 16px;
    padding: 6px 20px;
    font-weight: bold;
    font-size: 13px;
}
QToolBar QToolButton:hover  { background: #004182; }
QToolBar QToolButton:pressed { background: #003272; }

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {
    background: #ffffff;
    border-top: 1px solid #dce6f0;
    color: #0a66c2;
    font-weight: bold;
}

/* ── Sidebar ────────────────────────────────────────────────── */
QListWidget#sidebar {
    background: #004182;
    color: #cfe0f5;
    font-size: 14px;
    font-weight: 500;
    border: none;
    outline: none;
}
QListWidget#sidebar::item {
    padding: 14px 20px;
    border-left: 4px solid transparent;
}
QListWidget#sidebar::item:selected {
    background: #0a66c2;
    color: white;
    border-left: 4px solid #70b5f9;
    font-weight: bold;
}
QListWidget#sidebar::item:hover:!selected {
    background: #0052a3;
    color: white;
}

/* ── Scroll areas ───────────────────────────────────────────── */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #e8e8e8;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #b0b0b0;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ── Cards (QFrame used instead of QGroupBox) ───────────────── */
QFrame#card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
}

/* ── Form labels ────────────────────────────────────────────── */
QLabel#field-label {
    color: #555555;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Line edits ─────────────────────────────────────────────── */
QLineEdit {
    background: #f9f9f9;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #1d1d1d;
    selection-background-color: #0a66c2;
}
QLineEdit:focus {
    border: 1.5px solid #0a66c2;
    background: white;
    outline: none;
}
QLineEdit:placeholder {
    color: #aaaaaa;
}

/* ── Primary buttons ────────────────────────────────────────── */
QPushButton#primary {
    background: #0a66c2;
    color: white;
    border: none;
    border-radius: 16px;
    padding: 7px 18px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#primary:hover  { background: #004182; }
QPushButton#primary:pressed { background: #003272; }

/* ── Ghost / secondary buttons ──────────────────────────────── */
QPushButton#secondary {
    background: transparent;
    color: #0a66c2;
    border: 1.5px solid #0a66c2;
    border-radius: 14px;
    padding: 5px 14px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton#secondary:hover  { background: #e8f0fb; }
QPushButton#secondary:pressed { background: #d0e3f7; }

/* ── Danger (remove) buttons ────────────────────────────────── */
QPushButton#danger {
    background: transparent;
    color: #cc3300;
    border: 1.5px solid #cc3300;
    border-radius: 14px;
    padding: 5px 14px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton#danger:hover  { background: #fde8e0; }
QPushButton#danger:pressed { background: #fad0c4; }

/* ── Small icon buttons (✕ remove bullet / skill) ───────────── */
QPushButton#icon-btn {
    background: transparent;
    color: #999999;
    border: none;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 12px;
}
QPushButton#icon-btn:hover  { background: #fde8e0; color: #cc3300; }

/* ── AI analyze icon button (✦) ─────────────────────────────── */
QPushButton#ai-btn {
    background: transparent;
    color: #0a66c2;
    border: none;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 12px;
}
QPushButton#ai-btn:hover   { background: #e8f0fb; color: #004182; }
QPushButton#ai-btn:pressed { background: #d0e3f7; }
QPushButton#ai-btn:disabled { color: #aaaaaa; }

/* ── Bullets list ───────────────────────────────────────────── */
QListWidget#bullets-list {
    background: #fafafa;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 2px;
    outline: none;
    font-size: 13px;
}
QListWidget#bullets-list::item { border: none; background: transparent; }
QListWidget#bullets-list::item:selected { background: transparent; }

/* ── Skills list ────────────────────────────────────────────── */
QListWidget#skills-list {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}
QListWidget#skills-list::item { border: none; background: transparent; }
QListWidget#skills-list::item:selected { background: #e8f0fb; border-radius: 4px; }

/* ── Section page title label ───────────────────────────────── */
QLabel#section-title {
    font-size: 22px;
    font-weight: bold;
    color: #1d1d1d;
}

/* ── Bullets section label ──────────────────────────────────── */
QLabel#bullets-label {
    font-size: 13px;
    font-weight: 600;
    color: #0a66c2;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Analyze dialog ─────────────────────────────────────────── */
QFrame#analyze-quote {
    background: #f0f4ff;
    border: 1px solid #c0d4f0;
    border-radius: 6px;
}
QLabel#analyze-quote-title {
    font-size: 10px;
    font-weight: 600;
    color: #0a66c2;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#analyze-bullet-text {
    font-size: 13px;
    color: #1d1d1d;
}
QLabel#analyze-result-title {
    font-size: 11px;
    font-weight: 600;
    color: #555555;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QTextBrowser#analyze-browser {
    background: #fafafa;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
    color: #1d1d1d;
}

/* ── Tab widget ─────────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    background: transparent;
}
QTabWidget::tab-bar {
    alignment: left;
}
QTabBar::tab {
    background: #e8f0f8;
    color: #555555;
    border: 1px solid #dce6f0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 600;
    min-width: 100px;
}
QTabBar::tab:selected {
    background: white;
    color: #0a66c2;
    border-top: 3px solid #0a66c2;
    border-left: 1px solid #dce6f0;
    border-right: 1px solid #dce6f0;
    border-bottom: none;
}
QTabBar::tab:hover:!selected {
    background: #d4e4f5;
    color: #004182;
}

/* ── Tracker status combo ───────────────────────────────────── */
QComboBox#status-combo {
    background: #f9f9f9;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
}
QComboBox#status-combo:focus {
    border: 1.5px solid #0a66c2;
    background: white;
}

/* ── Application Tracker table ──────────────────────────────── */
QTableWidget {
    background: white;
    alternate-background-color: #f7f9fc;
    gridline-color: #d0d7de;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    font-size: 13px;
    selection-background-color: #e8f0fb;
    selection-color: #1d1d1d;
}
QHeaderView::section {
    background: #e8f0f8;
    color: #1d1d1d;
    font-weight: 700;
    font-size: 12px;
    padding: 6px 10px;
    border: none;
    border-right: 1px solid #d0d7de;
    border-bottom: 2px solid #0a66c2;
}
QTableWidget::item {
    padding: 4px 8px;
    border: none;
}
QTableWidget::item:selected {
    background: #e8f0fb;
    color: #1d1d1d;
}

/* ── Applier ────────────────────────────────────────────────── */
QTextEdit#jd-input {
    background: white;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    color: #1d1d1d;
}
QTextEdit#jd-input:focus {
    border: 1.5px solid #0a66c2;
}
QLabel#applier-section-header {
    font-size: 12px;
    font-weight: 700;
    color: #0a66c2;
}
QFrame#result-bullet-row {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
}
"""
