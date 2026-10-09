from __future__ import annotations

from string import Template

# Semantic color tokens. Every distinct color role used by the Qt stylesheet
# lives here exactly twice — once for light, once for dark.
PALETTE: dict[str, dict[str, str]] = {
    "light": {
        # Base
        "bg":                       "#F4F5F8",
        "text":                     "#1A1C1E",
        "text_muted":               "#5C6370",
        "text_faint":               "#8A9099",
        "text_disabled":            "#B0B5BD",
        # Accent
        "accent":                   "#0D9488",
        "accent_hover":             "#0F766E",
        "accent_pressed":           "#115E59",
        "accent_soft_bg":           "#E6F7F4",
        "accent_soft_pressed_bg":   "#CDEEE8",
        "on_accent":                "#FFFFFF",
        # Status
        "status_ok":                "#0F766E",
        "status_error":             "#C2410C",
        # Danger
        "danger":                   "#C2410C",
        "danger_soft_bg":           "#FFF1EB",
        "danger_soft_pressed_bg":   "#FDE4D8",
        # Surfaces
        "surface_bar":              "#FFFFFF",
        "surface_card":             "#FFFFFF",
        "surface_input":            "#F8F9FB",
        "surface_input_focus":      "#FFFFFF",
        "surface_list_subtle":      "#F8F9FB",
        "surface_alt":              "#F4F5F8",
        "surface_code":             "#1A1C1E",
        "text_code":                "#E8EAED",
        "border_code":              "#2A2E33",
        "surface_camera":           "#111111",
        "surface_video":            "#000000",
        # Borders
        "border":                   "#E2E4EA",
        "border_input":             "#D5D8E0",
        "border_bar":               "#E2E4EA",
        # Scrollbar
        "scrollbar_track":          "#EEF0F4",
        "scrollbar_handle":         "#C5C9D1",
        # Sidebar
        "sidebar_bg":               "#F8F9FB",
        "sidebar_text":             "#3D4450",
        "sidebar_hover_bg":         "#ECEEF2",
        # Tabs
        "tab_text":                 "#5C6370",
        "tab_hover_bg":             "#E6F7F4",
        "tab_hover_text":           "#0F766E",
        # Icon button hover
        "icon_btn_color":           "#8A9099",
        # Placeholder
        "placeholder":              "#B0B5BD",
        # Quote
        "quote_bg":                 "#E6F7F4",
        "quote_border":             "#B7E4DC",
        # Header (table)
        "header_bg":                "#F8F9FB",
        # Chat bubbles
        "bubble_user_bg":           "#E6F7F4",
        "bubble_user_border":       "#B7E4DC",
        "bubble_ai_bg":             "#FFFFFF",
        "bubble_ai_border":         "#E2E4EA",
        # Heatmap
        "heatmap_0":                "#E8EEF0",
        "heatmap_1":                "#B8E4DC",
        "heatmap_2":                "#5EC4B6",
        "heatmap_3":                "#1AA392",
        "heatmap_4":                "#0D9488",
    },
    "dark": {
        # Base
        "bg":                       "#12151A",
        "text":                     "#E8EAED",
        "text_muted":               "#A8B0BA",
        "text_faint":               "#8A929B",
        "text_disabled":            "#5A6068",
        # Accent
        "accent":                   "#2DD4BF",
        "accent_hover":             "#5EEAD4",
        "accent_pressed":           "#14B8A6",
        "accent_soft_bg":           "#14332F",
        "accent_soft_pressed_bg":   "#0F2825",
        "on_accent":                "#042F2E",
        # Status
        "status_ok":                "#2DD4BF",
        "status_error":             "#FB923C",
        # Danger
        "danger":                   "#FB923C",
        "danger_soft_bg":           "#3A2417",
        "danger_soft_pressed_bg":   "#4A2E1C",
        # Surfaces
        "surface_bar":              "#1C2128",
        "surface_card":             "#1C2128",
        "surface_input":            "#161A20",
        "surface_input_focus":      "#1C2128",
        "surface_list_subtle":      "#161A20",
        "surface_alt":              "#161A20",
        "surface_code":             "#0E1114",
        "text_code":                "#E8EAED",
        "border_code":              "#2A313A",
        "surface_camera":           "#0A0A0A",
        "surface_video":            "#000000",
        # Borders
        "border":                   "#2A313A",
        "border_input":             "#2A313A",
        "border_bar":               "#2A313A",
        # Scrollbar
        "scrollbar_track":          "#161A20",
        "scrollbar_handle":         "#3A424C",
        # Sidebar
        "sidebar_bg":               "#161A20",
        "sidebar_text":             "#A8B0BA",
        "sidebar_hover_bg":         "#1E252C",
        # Tabs
        "tab_text":                 "#A8B0BA",
        "tab_hover_bg":             "#14332F",
        "tab_hover_text":           "#5EEAD4",
        # Icon button hover
        "icon_btn_color":           "#8A929B",
        # Placeholder
        "placeholder":              "#6B7480",
        # Quote
        "quote_bg":                 "#14332F",
        "quote_border":             "#1E4A44",
        # Header (table)
        "header_bg":                "#161A20",
        # Chat bubbles
        "bubble_user_bg":           "#14332F",
        "bubble_user_border":       "#1E4A44",
        "bubble_ai_bg":             "#1C2128",
        "bubble_ai_border":         "#2A313A",
        # Heatmap
        "heatmap_0":                "#2E3842",
        "heatmap_1":                "#164E48",
        "heatmap_2":                "#0F766E",
        "heatmap_3":                "#14B8A6",
        "heatmap_4":                "#2DD4BF",
    },
}


_STYLESHEET_TEMPLATE = Template("""
/* ── App background ─────────────────────────────────────────── */
QMainWindow, QWidget {
    background-color: $bg;
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", "Segoe UI", sans-serif;
    font-size: 13px;
    color: $text;
}

QDialog {
    background-color: $bg;
}

QMenu {
    background: $surface_bar;
    color: $text;
    border: 1px solid $border;
    padding: 4px;
}
QMenu::item {
    padding: 6px 16px;
    border-radius: 6px;
}
QMenu::item:selected {
    background: $accent_soft_bg;
    color: $accent;
}

QCheckBox, QRadioButton {
    color: $text;
    spacing: 8px;
    background: transparent;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px;
    height: 16px;
}

QSpinBox, QDoubleSpinBox, QAbstractSpinBox {
    background: $surface_input;
    border: 1px solid $border_input;
    border-radius: 8px;
    padding: 4px 8px;
    color: $text;
    selection-background-color: $accent;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1.5px solid $accent;
    background: $surface_input_focus;
}

QPushButton {
    background: $surface_card;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
}
QPushButton:hover { background: $accent_soft_bg; }
QPushButton:pressed { background: $accent_soft_pressed_bg; }
QPushButton:disabled { color: $text_disabled; }

/* ── Toolbar ────────────────────────────────────────────────── */
QToolBar {
    background: $surface_bar;
    border: none;
    border-bottom: 1px solid $border_bar;
    padding: 8px 12px;
    spacing: 8px;
}
QToolBar QWidget {
    background: transparent;
    border: none;
}
QToolBar QToolButton {
    background: transparent;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
    font-size: 13px;
}
QToolBar QToolButton:hover {
    background: $accent_soft_bg;
    color: $accent;
    border-color: $accent;
}
QToolBar QToolButton:pressed { background: $accent_soft_pressed_bg; }
QToolBar QToolButton#primary {
    background: $accent;
    color: $on_accent;
    border: none;
}
QToolBar QToolButton#primary:hover {
    background: $accent_hover;
    color: $on_accent;
    border: none;
}
QToolBar QToolButton#primary:pressed {
    background: $accent_pressed;
    color: $on_accent;
}

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {
    background: $surface_bar;
    border-top: 1px solid $border_bar;
    color: $text_muted;
    font-weight: 500;
}
QStatusBar QLabel {
    color: $text_muted;
    background: transparent;
}

/* ── Sidebar ────────────────────────────────────────────────── */
QListWidget#sidebar {
    background: $sidebar_bg;
    color: $sidebar_text;
    font-size: 13px;
    font-weight: 500;
    border: none;
    border-right: 1px solid $border_bar;
    outline: none;
    padding: 8px 0;
}
QListWidget#sidebar QScrollBar:horizontal {
    height: 0px;
}
QListWidget#sidebar::item {
    padding: 10px 14px;
    margin: 2px 8px;
    border-radius: 8px;
    border: none;
}
QListWidget#sidebar::item:selected {
    background: $accent_soft_bg;
    color: $accent;
    font-weight: 600;
}
QListWidget#sidebar::item:hover:!selected {
    background: $sidebar_hover_bg;
    color: $text;
}

/* ── Scroll areas ───────────────────────────────────────────── */
QScrollArea {
    border: none;
    background: transparent;
}
QWidget#scroll-inner {
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
    border-radius: 12px;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    background: transparent;
    color: $text;
}

/* ── Form labels ────────────────────────────────────────────── */
QLabel#field-label {
    color: $text_muted;
    font-size: 12px;
    font-weight: 500;
}

/* ── Section page title label ───────────────────────────────── */
QLabel#section-title {
    font-size: 22px;
    font-weight: 700;
    color: $text;
}

/* ── Card / page sub-title ──────────────────────────────────── */
QLabel#card-title {
    font-size: 16px;
    font-weight: 700;
    color: $text;
}

/* ── App brand label in toolbar ─────────────────────────────── */
QLabel#app-brand {
    font-size: 15px;
    font-weight: 700;
    color: $text;
    padding: 0 8px;
}

/* ── Card group heading (grouped forms, import review) ──────── */
QLabel#card-heading {
    font-size: 15px;
    font-weight: 700;
    color: $text;
}

/* ── Sub-heading inside a settings card ─────────────────────── */
QLabel#settings-subheading {
    font-size: 14px;
    font-weight: bold;
    margin-top: 12px;
}

/* ── Group subtitle (experience section headers) ────────────── */
QLabel#group-subtitle {
    font-size: 14px;
    font-weight: 600;
    color: $text;
}

/* ── Section header (smaller, "applier" style) ──────────────── */
QLabel#applier-section-header {
    font-size: 12px;
    font-weight: 700;
    color: $text_muted;
}

/* ── Hint / helper text below inputs ────────────────────────── */
QLabel#hint {
    font-size: 12px;
    color: $text_muted;
}

/* ── Muted secondary text (chat author, empty states, etc.) ─── */
QLabel#muted {
    color: $text_faint;
}
QLabel#empty-note {
    color: $text_faint;
    padding: 8px 4px;
}
QLabel#camera-hint {
    color: $text_faint;
    font-size: 12px;
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

/* ── Field sub-label ────────────────────────────────────────── */
QLabel#field-sublabel {
    font-size: 12px;
    color: $text_muted;
    font-weight: 500;
}

/* ── Bullets section label ──────────────────────────────────── */
QLabel#bullets-label {
    font-size: 13px;
    font-weight: 600;
    color: $text;
}

/* ── Linked-to-job badge ────────────────────────────────────── */
QLabel#linked-badge {
    color: $text_faint;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 8px;
    border: 1px solid $border;
    border-radius: 8px;
    background: $surface_card;
}

/* ── Line edits ─────────────────────────────────────────────── */
QLineEdit {
    background: $surface_input;
    border: 1px solid $border_input;
    border-radius: 8px;
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
    border-radius: 8px;
    color: $text;
    selection-background-color: $accent;
}
QPlainTextEdit:focus, QTextEdit:focus {
    border: 1.5px solid $accent;
}

QPlainTextEdit#code-stream {
    background: $surface_code;
    color: $text_code;
    border: 1px solid $border_code;
    border-radius: 8px;
    padding: 8px;
}

/* ── Primary buttons ────────────────────────────────────────── */
QPushButton#primary {
    background: $accent;
    color: $on_accent;
    border: none;
    border-radius: 8px;
    padding: 7px 18px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primary:hover  { background: $accent_hover; color: $on_accent; }
QPushButton#primary:pressed { background: $accent_pressed; color: $on_accent; }

/* ── Ghost / secondary buttons ──────────────────────────────── */
QPushButton#secondary {
    background: transparent;
    color: $accent;
    border: 1px solid $accent;
    border-radius: 8px;
    padding: 5px 14px;
    font-weight: 600;
    font-size: 12px;
}
QPushButton#secondary:hover  { background: $accent_soft_bg; }
QPushButton#secondary:pressed { background: $accent_soft_pressed_bg; }

/* ── Danger (remove) buttons ────────────────────────────────── */
QPushButton#danger {
    background: transparent;
    color: $danger;
    border: 1px solid $danger;
    border-radius: 8px;
    padding: 5px 14px;
    font-weight: 600;
    font-size: 12px;
}
QPushButton#danger:hover  { background: $danger_soft_bg; }
QPushButton#danger:pressed { background: $danger_soft_pressed_bg; }

/* ── Small icon buttons (✕ remove bullet / skill) ───────────── */
QPushButton#icon-btn {
    background: transparent;
    color: $icon_btn_color;
    border: none;
    border-radius: 6px;
    padding: 2px 4px;
    font-size: 12px;
}
QPushButton#icon-btn:hover  { background: $danger_soft_bg; color: $danger; }

/* ── AI analyze icon button (✦) ─────────────────────────────── */
QPushButton#ai-btn {
    background: transparent;
    color: $accent;
    border: none;
    border-radius: 6px;
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
    border-radius: 8px;
    padding: 2px;
    outline: none;
    font-size: 13px;
    color: $text;
}
QListWidget#bullets-list::item { border: none; background: transparent; }
QListWidget#bullets-list::item:selected { background: transparent; }

/* ── Coursework row ─────────────────────────────────────────── */
QFrame#course-row {
    background: transparent;
    border: none;
    border-top: 1px solid $border;
    border-radius: 0;
}

/* ── Skills list ────────────────────────────────────────────── */
QListWidget#skills-list {
    background: $surface_card;
    border: 1px solid $border;
    border-radius: 12px;
    padding: 4px;
    outline: none;
    color: $text;
}
QListWidget#skills-list::item { border: none; background: transparent; }
QListWidget#skills-list::item:selected { background: $accent_soft_bg; border-radius: 6px; }

/* ── Library / company cache lists ──────────────────────────── */
QListWidget#library-list, QListWidget#company-cache-list {
    background: $surface_card;
    border: 1px solid $border;
    border-radius: 12px;
    padding: 6px;
    outline: none;
    color: $text;
    font-size: 13px;
}
QListWidget#library-list::item, QListWidget#company-cache-list::item {
    padding: 8px 10px;
    border-radius: 8px;
}
QListWidget#library-list::item:selected,
QListWidget#company-cache-list::item:selected {
    background: $accent_soft_bg;
    color: $accent;
}
QListWidget#library-list::item:hover:!selected,
QListWidget#company-cache-list::item:hover:!selected {
    background: $sidebar_hover_bg;
}

/* ── Analyze dialog ─────────────────────────────────────────── */
QFrame#analyze-quote {
    background: $quote_bg;
    border: 1px solid $quote_border;
    border-radius: 8px;
}
QLabel#analyze-quote-title {
    font-size: 10px;
    font-weight: 600;
    color: $text_muted;
    letter-spacing: 0.5px;
}
QLabel#analyze-bullet-text {
    font-size: 13px;
    color: $text;
}

/* ── Tab widget ─────────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    border-top: 1px solid $border_bar;
    background: transparent;
    top: -1px;
}
QTabWidget::tab-bar {
    alignment: left;
}
QTabBar {
    background: $surface_bar;
    qproperty-drawBase: 0;
}
QTabBar::tab {
    background: transparent;
    color: $tab_text;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 18px;
    font-size: 13px;
    font-weight: 600;
    min-width: 80px;
}
QTabBar::tab:selected {
    background: transparent;
    color: $accent;
    border-bottom: 2px solid $accent;
}
QTabBar::tab:hover:!selected {
    background: $tab_hover_bg;
    color: $tab_hover_text;
}

/* ── Combo boxes ────────────────────────────────────────────── */
QComboBox {
    background: $surface_input;
    border: 1px solid $border_input;
    border-radius: 8px;
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
    selection-background-color: $accent_soft_bg;
    selection-color: $accent;
    border: 1px solid $border;
}

/* ── Application Tracker table ──────────────────────────────── */
QTableWidget {
    background: $surface_card;
    alternate-background-color: $surface_alt;
    gridline-color: $border_input;
    border: 1px solid $border_input;
    border-radius: 8px;
    font-size: 13px;
    color: $text;
    selection-background-color: $accent_soft_bg;
    selection-color: $text;
}
QHeaderView::section {
    background: $header_bg;
    color: $text;
    font-weight: 600;
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
QFrame#result-bullet-row {
    background: $surface_card;
    border: 1px solid $border;
    border-radius: 8px;
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
    border-radius: 8px;
}
QFrame#capability-chip QLabel {
    color: $accent;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}

/* ── Interview chat bubbles ─────────────────────────────────── */
QFrame#chat-bubble-user {
    background: $bubble_user_bg;
    border: 1px solid $bubble_user_border;
    border-radius: 12px;
}
QFrame#chat-bubble-ai {
    background: $bubble_ai_bg;
    border: 1px solid $bubble_ai_border;
    border-radius: 12px;
}
QLabel#chat-who {
    color: $text_faint;
    font-size: 11px;
    font-weight: 600;
}
QLabel#chat-body {
    font-size: 14px;
}
QLabel#feedback-status {
    color: $text_faint;
    font-size: 10px;
    font-weight: 700;
}

/* ── Interview question cards ───────────────────────────────── */
QLineEdit#question-edit, QLineEdit#question-edit:focus {
    font-size: 15px;
    font-weight: 600;
    border: none;
    background: transparent;
    padding: 2px 0;
}
QTextEdit#answer-edit {
    font-size: 15px;
}

/* ── Camera preview ─────────────────────────────────────────── */
QFrame#camera-card {
    background: $surface_camera;
    border: 1px solid $border;
    border-radius: 12px;
}
QVideoWidget#camera-video {
    background: $surface_video;
}

/* ── Resume builder ─────────────────────────────────────────── */
QTreeWidget#builder-palette {
    background: $surface_card;
    color: $text;
    border: 1px solid $border;
    border-radius: 12px;
    padding: 6px 4px;
    outline: none;
    font-size: 13px;
}
QTreeWidget#builder-palette::item {
    padding: 4px 8px;
    border-radius: 6px;
}
QTreeWidget#builder-palette::item:selected {
    background: $accent_soft_bg;
    color: $accent;
}
QTreeWidget#builder-palette::item:hover:!selected {
    background: $sidebar_hover_bg;
}
QFrame#builder-section {
    background: $surface_alt;
    border: 1px dashed $border;
    border-radius: 10px;
}
QFrame#builder-drop-indicator {
    background: $accent;
    border: none;
    border-radius: 1px;
}
QLabel#builder-handle {
    color: $text_faint;
    font-size: 14px;
    font-weight: 700;
}
""")


def palette_for(mode: str) -> dict[str, str]:
    """Colors for "light" or "dark" (anything else falls back to light)."""
    return PALETTE.get(mode, PALETTE["light"])


def build_stylesheet(mode: str) -> str:
    return _STYLESHEET_TEMPLATE.substitute(palette_for(mode))
