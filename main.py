import logging
import pathlib
import sys
import threading
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

    for noisy in ("httpx", "httpcore", "filelock", "urllib3", "huggingface_hub"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    print(f"Logging to: {_LOG_FILE}", file=sys.stderr)


_setup_logging()

import uvicorn
from PyQt6.QtWidgets import QApplication
from api import ai_provider
from app.main_window import MainWindow
from app.theme import apply_theme, install_system_listener


def _start_api_server() -> None:
    config = uvicorn.Config(
        "api.server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_config=None,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="api-server", daemon=True)
    thread.start()


def main():
    for i in range(10):
        print("STARTING AGAIN")
    for i in range(10):
        print()
    ai_provider._seed_prompts()
    if ai_provider.get_auto_resync_prompts():
        ai_provider.resync_all_prompts()
    _start_api_server()
    app = QApplication(sys.argv)
    app.setApplicationName("I*ternship")
    apply_theme(app, ai_provider.get_theme_preference())
    install_system_listener(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
