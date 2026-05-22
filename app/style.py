from __future__ import annotations

from string import Template

# Semantic color tokens. Every distinct color role used by the Qt stylesheet
# lives here exactly twice — once for light, once for dark.
PALETTE: dict[str, dict[str, str]] = {
    "light": {
        # Base
        "bg":                       "#f3f2ef",
        "text":                     "#1d1d1d",
        "text_muted":               "#555555",
        "text_subtle":              "#666666",
        "text_faint":               "#888888",
        "text_disabled":            "#aaaaaa",
        # Accent / link
        "accent":                   "#0a66c2",
        "accent_hover":             "#004182",
        "accent_pressed":           "#003272",
        "accent_soft_bg":           "#e8f0fb",
        "accent_soft_pressed_bg":   "#d0e3f7",
        "link":                     "#0a66c2",
        # Status
        "status_ok":                "#057642",
        "status_error":             "#cc3300",
        # Danger
        "danger":                   "#cc3300",
        "danger_soft_bg":           "#fde8e0",
        "danger_soft_pressed_bg":   "#fad0c4",
        # Surfaces
        "surface_bar":              "#ffffff",
        "surface_card":             "#ffffff",
        "surface_input":            "#f9f9f9",
        "surface_input_focus":      "#ffffff",
        "surface_list_subtle":      "#fafafa",
        "surface_alt":              "#f7f9fc",
        # Borders
        "border":                   "#e0e0e0",
        "border_input":             "#d0d7de",
        "border_bar":               "#dce6f0",
        # Scrollbar
        "scrollbar_track":          "#e8e8e8",
        "scrollbar_handle":         "#b0b0b0",
        # Sidebar
        "sidebar_bg":               "#004182",
        "sidebar_text":             "#cfe0f5",
        "sidebar_hover_bg":         "#0052a3",
        "sidebar_selected_border":  "#70b5f9",
        # Tabs
        "tab_bg":                   "#e8f0f8",
        "tab_text":                 "#555555",
        "tab_hover_bg":             "#d4e4f5",
        "tab_hover_text":           "#004182",
        # Icon button hover
        "icon_btn_color":           "#999999",
        # Placeholder
        "placeholder":              "#aaaaaa",
        # Quote
        "quote_bg":                 "#f0f4ff",
        "quote_border":             "#c0d4f0",
        # Header (table)
        "header_bg":                "#e8f0f8",
        # Chat bubbles
        "bubble_user_bg":           "#eef3fb",
        "bubble_user_border":       "#cfd8e3",
        "bubble_ai_bg":             "#ffffff",
        "bubble_ai_border":         "#e0e0e0",
        # Chip
        "chip_bg":                  "#eef3fb",
        "chip_border":              "#cfd8e3",
        "chip_text":                "#1d1d1d",
    },
    "dark": {
        # Base
        "bg":                       "#1b1f23",
        "text":                     "#e6e6e6",
        "text_muted":               "#a0a8b0",
        "text_subtle":              "#a8b3c0",
        "text_faint":               "#8a929b",
        "text_disabled":            "#5a6068",
        # Accent / link
        "accent":                   "#0a66c2",
        "accent_hover":             "#3380d4",
        "accent_pressed":           "#004182",
        "accent_soft_bg":           "#1c2c40",
        "accent_soft_pressed_bg":   "#0f2238",
        "link":                     "#70b5f9",
        # Status
        "status_ok":                "#3fb27f",
        "status_error":             "#ff7a5c",
        # Danger
        "danger":                   "#ff7a5c",
        "danger_soft_bg":           "#3a1f17",
        "danger_soft_pressed_bg":   "#4a2820",
        # Surfaces
        "surface_bar":              "#242a31",
        "surface_card":             "#2d343c",
        "surface_input":            "#1b1f23",
        "surface_input_focus":      "#242a31",
        "surface_list_subtle":      "#242a31",
        "surface_alt":              "#2a313a",
        # Borders
        "border":                   "#3a4148",
        "border_input":             "#3a4148",
        "border_bar":               "#3a4148",
        # Scrollbar
        "scrollbar_track":          "#242a31",
        "scrollbar_handle":         "#4a525b",
        # Sidebar
        "sidebar_bg":               "#11161b",
        "sidebar_text":             "#a8b3c0",
        "sidebar_hover_bg":         "#1c2530",
        "sidebar_selected_border":  "#70b5f9",
        # Tabs
        "tab_bg":                   "#242a31",
        "tab_text":                 "#a0a8b0",
        "tab_hover_bg":             "#2a313a",
        "tab_hover_text":           "#a8d4ff",
        # Icon button hover
        "icon_btn_color":           "#8a929b",
        # Placeholder
        "placeholder":              "#6b7480",
        # Quote
        "quote_bg":                 "#1c2c40",
        "quote_border":             "#2a4565",
        # Header (table)
        "header_bg":                "#1b1f23",
        # Chat bubbles
        "bubble_user_bg":           "#1c2c40",
        "bubble_user_border":       "#2a4565",
        "bubble_ai_bg":             "#2d343c",
        "bubble_ai_border":         "#3a4148",
        # Chip
        "chip_bg":                  "#1d2a3a",
        "chip_border":              "#274a6b",
        "chip_text":                "#cfe0f5",
    },
}


_STYLESHEET_TEMPLATE = Template("""
/* ── App background ─────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: $bg;
    font-family: -apple-system, "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: $text;
}

/* ── Toolbar ────────────────────────────────────────────────── */
QToolBar {
    background: $surface_bar;
    border-bottom: 1px solid $border_bar;
    padding: 6px 12px;
    spacing: 8px;
}
QToolBar QToolButton {
    background: $accent;
    color: white;
    border: none;
    border-radius: 16px;
    padding: 6px 20px;
    font-weight: bold;
    font-size: 13px;
}
QToolBar QToolButton:hover  { background: $accent_hover; }
QToolBar QToolButton:pressed { background: $accent_pressed; }

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {
    background: $surface_bar;
    border-top: 1px solid $border_bar;
    color: $link;
    font-weight: bold;
}

/* ── Sidebar ────────────────────────────────────────────────── */
QListWidget#sidebar {
    background: $sidebar_bg;
    color: $sidebar_text;
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
    background: $accent;
    color: white;
    border-left: 4px solid $sidebar_selected_border;
    font-weight: bold;
}
QListWidget#sidebar::item:hover:!selected {
    background: $sidebar_hover_bg;
    color: white;
}

/* ── Scroll areas ───────────────────────────────────────────── */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollBar:vertical {
    background: $scrollbar_track;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: $scrollbar_handle;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ── Cards ──────────────────────────────────────────────────── */
QFrame#card {
    background: $surface_card;
    border: 1px solid $border;
    border-radius: 10px;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    background: transparent;
    color: $text;
}

/* ── Form labels ────────────────────────────────────────────── */
QLabel#field-label {
    color: $text_muted;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Section page title label ───────────────────────────────── */
QLabel#section-title {
    font-size: 22px;
    font-weight: bold;
    color: $text;
}

/* ── Card / page sub-title (was inline #0a66c2 16px) ────────── */
QLabel#card-title {
    font-size: 16px;
    font-weight: bold;
    color: $link;
}

/* ── App brand label in toolbar ─────────────────────────────── */
QLabel#app-brand {
    font-size: 15px;
    font-weight: bold;
    color: $link;
}

/* ── Group subtitle (experience section headers) ────────────── */
QLabel#group-subtitle {
    font-size: 14px;
    font-weight: 600;
    color: $link;
}

/* ── Section header (smaller, "applier" style) ──────────────── */
QLabel#applier-section-header {
    font-size: 12px;
    font-weight: 700;
    color: $link;
}

/* ── Hint / helper text below inputs ────────────────────────── */
QLabel#hint {
    font-size: 12px;
    color: $text_subtle;
}

/* ── Muted secondary text (chat author, empty states, etc.) ─── */
QLabel#muted {
    color: $text_faint;
}

/* ── Status messages (neutral / ok / error) ─────────────────── */
QLabel#status-neutral {
    font-size: 12px;
    color: $text_muted;
}
QLabel#status-ok {
    font-size: 12px;
    color: $status_ok;
}
QLabel#status-error {
    font-size: 12px;
    color: $status_error;
}

/* ── Field sub-label (smaller uppercase label) ──────────────── */
QLabel#field-sublabel {
    font-size: 11px;
    color: $text_muted;
    font-weight: 600;
}

/* ── Bullets section label ──────────────────────────────────── */
QLabel#bullets-label {
    font-size: 13px;
    font-weight: 600;
    color: $link;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* ── Line edits ─────────────────────────────────────────────── */
QLineEdit {
    background: $surface_input;
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    color: $text;
    selection-background-color: $accent;
}
QLineEdit:focus {
    border: 1.5px solid $accent;
    background: $surface_input_focus;
    outline: none;
}
QLineEdit:placeholder {
    color: $placeholder;
}

/* ── Plain / multiline text inputs ──────────────────────────── */
QPlainTextEdit, QTextEdit {
    background: $surface_input;
    border: 1px solid $border_input;
    border-radius: 6px;
    color: $text;
    selection-background-color: $accent;
}
QPlainTextEdit:focus, QTextEdit:focus {
    border: 1.5px solid $accent;
}

/* ── Primary buttons ────────────────────────────────────────── */
QPushButton#primary {
    background: $accent;
    color: white;
    border: none;
    border-radius: 16px;
    padding: 7px 18px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#primary:hover  { background: $accent_hover; }
QPushButton#primary:pressed { background: $accent_pressed; }

/* ── Ghost / secondary buttons ──────────────────────────────── */
QPushButton#secondary {
    background: transparent;
    color: $link;
    border: 1.5px solid $accent;
    border-radius: 14px;
    padding: 5px 14px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton#secondary:hover  { background: $accent_soft_bg; }
QPushButton#secondary:pressed { background: $accent_soft_pressed_bg; }

/* ── Danger (remove) buttons ────────────────────────────────── */
QPushButton#danger {
    background: transparent;
    color: $danger;
    border: 1.5px solid $danger;
    border-radius: 14px;
    padding: 5px 14px;
    font-weight: bold;
    font-size: 12px;
}
QPushButton#danger:hover  { background: $danger_soft_bg; }
QPushButton#danger:pressed { background: $danger_soft_pressed_bg; }

/* ── Small icon buttons (✕ remove bullet / skill) ───────────── */
QPushButton#icon-btn {
    background: transparent;
    color: $icon_btn_color;
    border: none;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 12px;
}
QPushButton#icon-btn:hover  { background: $danger_soft_bg; color: $danger; }

/* ── AI analyze icon button (✦) ─────────────────────────────── */
QPushButton#ai-btn {
    background: transparent;
    color: $link;
    border: none;
    border-radius: 4px;
    padding: 2px 4px;
    font-size: 12px;
}
QPushButton#ai-btn:hover   { background: $accent_soft_bg; color: $accent_hover; }
QPushButton#ai-btn:pressed { background: $accent_soft_pressed_bg; }
QPushButton#ai-btn:disabled { color: $text_disabled; }

/* ── Bullets list ───────────────────────────────────────────── */
QListWidget#bullets-list {
    background: $surface_list_subtle;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 2px;
    outline: none;
    font-size: 13px;
    color: $text;
}
QListWidget#bullets-list::item { border: none; background: transparent; }
QListWidget#bullets-list::item:selected { background: transparent; }

/* ── Skills list ────────────────────────────────────────────── */
QListWidget#skills-list {
    background: $surface_card;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    color: $text;
}
QListWidget#skills-list::item { border: none; background: transparent; }
QListWidget#skills-list::item:selected { background: $accent_soft_bg; border-radius: 4px; }

/* ── Analyze dialog ─────────────────────────────────────────── */
QFrame#analyze-quote {
    background: $quote_bg;
    border: 1px solid $quote_border;
    border-radius: 6px;
}
QLabel#analyze-quote-title {
    font-size: 10px;
    font-weight: 600;
    color: $link;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
QLabel#analyze-bullet-text {
    font-size: 13px;
    color: $text;
}
QTextBrowser#analyze-browser {
    background: $surface_list_subtle;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 8px;
    font-size: 13px;
    color: $text;
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
    background: $tab_bg;
    color: $tab_text;
    border: 1px solid $border_bar;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 24px;
    font-size: 13px;
    font-weight: 600;
    min-width: 100px;
}
QTabBar::tab:selected {
    background: $surface_card;
    color: $link;
    border-top: 3px solid $accent;
    border-left: 1px solid $border_bar;
    border-right: 1px solid $border_bar;
    border-bottom: none;
}
QTabBar::tab:hover:!selected {
    background: $tab_hover_bg;
    color: $tab_hover_text;
}

/* ── Combo boxes ────────────────────────────────────────────── */
QComboBox {
    background: $surface_input;
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    color: $text;
}
QComboBox:focus {
    border: 1.5px solid $accent;
    background: $surface_input_focus;
}
QComboBox QAbstractItemView {
    background: $surface_bar;
    color: $text;
    selection-background-color: $accent;
    selection-color: white;
    border: 1px solid $border;
}

/* ── Tracker status combo ───────────────────────────────────── */
QComboBox#status-combo {
    background: $surface_input;
    border: 1px solid $border_input;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 13px;
    color: $text;
}
QComboBox#status-combo:focus {
    border: 1.5px solid $accent;
    background: $surface_input_focus;
}

/* ── Application Tracker table ──────────────────────────────── */
QTableWidget {
    background: $surface_card;
    alternate-background-color: $surface_alt;
    gridline-color: $border_input;
    border: 1px solid $border_input;
    border-radius: 6px;
    font-size: 13px;
    color: $text;
    selection-background-color: $accent_soft_bg;
    selection-color: $text;
}
QHeaderView::section {
    background: $header_bg;
    color: $text;
    font-weight: 700;
    font-size: 12px;
    padding: 6px 10px;
    border: none;
    border-right: 1px solid $border_input;
    border-bottom: 2px solid $accent;
}
QTableWidget::item {
    padding: 4px 8px;
    border: none;
}
QTableWidget::item:selected {
    background: $accent_soft_bg;
    color: $text;
}

/* ── Applier ────────────────────────────────────────────────── */
QTextEdit#jd-input {
    background: $surface_card;
    border: 1px solid $border_input;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    color: $text;
}
QTextEdit#jd-input:focus {
    border: 1.5px solid $accent;
}
QFrame#result-bullet-row {
    background: $surface_card;
    border: 1px solid $border;
    border-radius: 6px;
}

/* ── Horizontal separator line ──────────────────────────────── */
QFrame#hline {
    color: $border;
    background: $border;
    border: none;
    max-height: 1px;
}

/* ── Capability chip (AI model section) ─────────────────────── */
QFrame#capability-chip {
    background: $accent_soft_bg;
    border: none;
    border-radius: 10px;
}
QFrame#capability-chip QLabel {
    color: $link;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}

/* ── Chip (skill badge / quick-fill) ────────────────────────── */
QFrame#chip {
    background: $chip_bg;
    border: 1px solid $chip_border;
    border-radius: 12px;
}
QFrame#chip QLabel {
    color: $chip_text;
    font-size: 12px;
}

/* ── Interview chat bubbles ─────────────────────────────────── */
QFrame#chat-bubble-user {
    background: $bubble_user_bg;
    border: 1px solid $bubble_user_border;
    border-radius: 8px;
}
QFrame#chat-bubble-ai {
    background: $bubble_ai_bg;
    border: 1px solid $bubble_ai_border;
    border-radius: 8px;
}
""")


def build_stylesheet(mode: str) -> str:
    palette = PALETTE.get(mode, PALETTE["light"])
    return _STYLESHEET_TEMPLATE.substitute(palette)
