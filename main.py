import logging
import pathlib
import sys
from dotenv import load_dotenv

load_dotenv()

_LOG_DIR = pathlib.Path.home() / "Library" / "Application Support" / "InternApplier"
_LOG_FILE = _LOG_DIR / "app.log"


def _setup_logging() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    print(f"Logging to: {_LOG_FILE}", file=sys.stderr)


_setup_logging()

from PyQt6.QtWidgets import QApplication
from app import ai_provider
from app.main_window import MainWindow
from app.style import GLOBAL_STYLESHEET


def main():
    for i in range(10):
        print("STARTING AGAIN")
    for i in range(10):
        print()
    ai_provider._seed_prompts()
    if ai_provider.get_auto_resync_prompts():
        ai_provider.resync_all_prompts()
    app = QApplication(sys.argv)
    app.setApplicationName("InternApplier")
    app.setStyleSheet(GLOBAL_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
