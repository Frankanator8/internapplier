import sys
from PyQt6.QtWidgets import QApplication
from app.main_window import MainWindow
from app.style import GLOBAL_STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("InternApplier")
    app.setStyleSheet(GLOBAL_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
