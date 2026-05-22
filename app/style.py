LIGHT_STYLESHEET = """
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

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    background: transparent;
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

/* ── Interview chat bubbles ─────────────────────────────────── */
QFrame#chat-bubble-user {
    background: #eef3fb;
    border: 1px solid #cfd8e3;
    border-radius: 8px;
}
QFrame#chat-bubble-ai {
    background: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
}
"""


DARK_STYLESHEET = """
/* ── App background ─────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: #1b1f23;
    font-family: -apple-system, "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #e6e6e6;
}

/* ── Toolbar ────────────────────────────────────────────────── */
QToolBar {
    background: #242a31;
    border-bottom: 1px solid #3a4148;
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
QToolBar QToolButton:hover  { background: #3380d4; }
QToolBar QToolButton:pressed { background: #004182; }

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {
    background: #242a31;
    border-top: 1px solid #3a4148;
    color: #70b5f9;
    font-weight: bold;
}

/* ── Sidebar ────────────────────────────────────────────────── */
QListWidget#sidebar {
    background: #11161b;
    color: #a8b3c0;
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
    background: #1c2530;
    color: white;
}

/* ── Scroll areas ───────────────────────────────────────────── */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: #242a31;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #4a525b;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ── Cards (QFrame used instead of QGroupBox) ───────────────── */
QFrame#card {
    background: #2d343c;
    border: 1px solid #3a4148;
    border-radius: 10px;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    background: transparent;
    color: #e6e6e6;
}

/* ── Form labels ────────────────────────────────────────────── */
QLabel#field-label {
    color: #a0a8b0;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Line edits ─────────────────────────────────────────────── */
QLineEdit {
    background: #1b1f23;
    border: 1px solid #3a4148;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: #e6e6e6;
    selection-background-color: #0a66c2;
}
QLineEdit:focus {
    border: 1.5px solid #3380d4;
    background: #242a31;
    outline: none;
}
QLineEdit:placeholder {
    color: #6b7480;
}

/* ── Plain / multiline text inputs ──────────────────────────── */
QPlainTextEdit, QTextEdit {
    background: #1b1f23;
    border: 1px solid #3a4148;
    border-radius: 6px;
    color: #e6e6e6;
    selection-background-color: #0a66c2;
}
QPlainTextEdit:focus, QTextEdit:focus {
    border: 1.5px solid #3380d4;
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
QPushButton#primary:hover  { background: #3380d4; }
QPushButton#primary:pressed { background: #004182; }

/* ── Ghost / secondary buttons ──────────────────────────────── */
QPushButton#secondary {
    background: transparent;
    color: #70b5f9;
    border: 1.5px solid #3380d4;
    border-radius: 14px;
    padding: 5px 14px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton#secondary:hover  { background: #1c2c40; }
QPushButton#secondary:pressed { background: #0f2238; }

/* ── Danger (remove) buttons ────────────────────────────────── */
QPushButton#danger {
    background: transparent;
    color: #ff7a5c;
    border: 1.5px solid #ff7a5c;
    border-radius: 14px;
    padding: 5px 14px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton#danger:hover  { background: #3a1f17; }
QPushButton#danger:pressed { background: #4a2820; }

/* ── Small icon buttons (✕ remove bullet / skill) ───────────── */
QPushButton#icon-btn {
    background: transparent;
    color: #8a929b;
    border: none;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 12px;
}
QPushButton#icon-btn:hover  { background: #3a1f17; color: #ff7a5c; }

/* ── AI analyze icon button (✦) ─────────────────────────────── */
QPushButton#ai-btn {
    background: transparent;
    color: #70b5f9;
    border: none;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 12px;
}
QPushButton#ai-btn:hover   { background: #1c2c40; color: #a8d4ff; }
QPushButton#ai-btn:pressed { background: #0f2238; }
QPushButton#ai-btn:disabled { color: #5a6068; }

/* ── Bullets list ───────────────────────────────────────────── */
QListWidget#bullets-list {
    background: #242a31;
    border: 1px solid #3a4148;
    border-radius: 6px;
    padding: 2px;
    outline: none;
    font-size: 13px;
    color: #e6e6e6;
}
QListWidget#bullets-list::item { border: none; background: transparent; }
QListWidget#bullets-list::item:selected { background: transparent; }

/* ── Skills list ────────────────────────────────────────────── */
QListWidget#skills-list {
    background: #2d343c;
    border: 1px solid #3a4148;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    color: #e6e6e6;
}
QListWidget#skills-list::item { border: none; background: transparent; }
QListWidget#skills-list::item:selected { background: #1c2c40; border-radius: 4px; }

/* ── Section page title label ───────────────────────────────── */
QLabel#section-title {
    font-size: 22px;
    font-weight: bold;
    color: #e6e6e6;
}

/* ── Bullets section label ──────────────────────────────────── */
QLabel#bullets-label {
    font-size: 13px;
    font-weight: 600;
    color: #70b5f9;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Analyze dialog ─────────────────────────────────────────── */
QFrame#analyze-quote {
    background: #1c2c40;
    border: 1px solid #2a4565;
    border-radius: 6px;
}
QLabel#analyze-quote-title {
    font-size: 10px;
    font-weight: 600;
    color: #70b5f9;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#analyze-bullet-text {
    font-size: 13px;
    color: #e6e6e6;
}
QTextBrowser#analyze-browser {
    background: #242a31;
    border: 1px solid #3a4148;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
    color: #e6e6e6;
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
    background: #242a31;
    color: #a0a8b0;
    border: 1px solid #3a4148;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 600;
    min-width: 100px;
}
QTabBar::tab:selected {
    background: #2d343c;
    color: #70b5f9;
    border-top: 3px solid #0a66c2;
    border-left: 1px solid #3a4148;
    border-right: 1px solid #3a4148;
    border-bottom: none;
}
QTabBar::tab:hover:!selected {
    background: #2a313a;
    color: #a8d4ff;
}

/* ── Combo boxes ────────────────────────────────────────────── */
QComboBox {
    background: #1b1f23;
    border: 1px solid #3a4148;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    color: #e6e6e6;
}
QComboBox:focus {
    border: 1.5px solid #3380d4;
    background: #242a31;
}
QComboBox QAbstractItemView {
    background: #242a31;
    color: #e6e6e6;
    selection-background-color: #0a66c2;
    selection-color: white;
    border: 1px solid #3a4148;
}

/* ── Tracker status combo ───────────────────────────────────── */
QComboBox#status-combo {
    background: #1b1f23;
    border: 1px solid #3a4148;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    color: #e6e6e6;
}
QComboBox#status-combo:focus {
    border: 1.5px solid #3380d4;
    background: #242a31;
}

/* ── Application Tracker table ──────────────────────────────── */
QTableWidget {
    background: #242a31;
    alternate-background-color: #2a313a;
    gridline-color: #3a4148;
    border: 1px solid #3a4148;
    border-radius: 6px;
    font-size: 13px;
    color: #e6e6e6;
    selection-background-color: #1c2c40;
    selection-color: #e6e6e6;
}
QHeaderView::section {
    background: #1b1f23;
    color: #e6e6e6;
    font-weight: 700;
    font-size: 12px;
    padding: 6px 10px;
    border: none;
    border-right: 1px solid #3a4148;
    border-bottom: 2px solid #0a66c2;
}
QTableWidget::item {
    padding: 4px 8px;
    border: none;
}
QTableWidget::item:selected {
    background: #1c2c40;
    color: #e6e6e6;
}

/* ── Applier ────────────────────────────────────────────────── */
QTextEdit#jd-input {
    background: #1b1f23;
    border: 1px solid #3a4148;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    color: #e6e6e6;
}
QTextEdit#jd-input:focus {
    border: 1.5px solid #3380d4;
}
QLabel#applier-section-header {
    font-size: 12px;
    font-weight: 700;
    color: #70b5f9;
}
QFrame#result-bullet-row {
    background: #2d343c;
    border: 1px solid #3a4148;
    border-radius: 6px;
}

/* ── Interview chat bubbles ─────────────────────────────────── */
QFrame#chat-bubble-user {
    background: #1c2c40;
    border: 1px solid #2a4565;
    border-radius: 8px;
}
QFrame#chat-bubble-ai {
    background: #2d343c;
    border: 1px solid #3a4148;
    border-radius: 8px;
}
"""


GLOBAL_STYLESHEET = LIGHT_STYLESHEET
