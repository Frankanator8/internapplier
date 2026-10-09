from __future__ import annotations

import importlib
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QtWebEngine must be imported before the QApplication is constructed.
importlib.import_module("PyQt6.QtWebEngineWidgets")


@pytest.fixture(scope="session")
def qapp():
    from PyQt6.QtWidgets import QApplication

    # A program name is required: QtWebEngine aborts on an empty argv.
    return QApplication.instance() or QApplication(["internapplier-tests"])
