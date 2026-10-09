"""Local-only camera preview. Frames are rendered straight to a QVideoWidget by
Qt's pipeline — no capture path feeds AI workers."""
from __future__ import annotations

import logging
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from app.ui.widgets import label

logger = logging.getLogger(__name__)


def _request_macos_permission() -> None:
    """Fire the macOS camera permission prompt early (fire-and-forget).

    Without this, QCamera silently shows black frames the first time.
    """
    if sys.platform != "darwin":
        return
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeVideo
        status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeVideo)
    except Exception:
        return
    # 0 = not determined. Authorized needs nothing; restricted/denied won't re-prompt.
    if status != 0:
        return
    try:
        # The handler may never run if Info.plist lacks NSCameraUsageDescription,
        # so nothing waits on it.
        AVCaptureDevice.requestAccessForMediaType_completionHandler_(
            AVMediaTypeVideo, lambda _granted: None
        )
    except Exception:
        logger.exception("Camera permission request failed")


def _no_device_hint() -> str:
    if sys.platform == "darwin":
        return (
            "No camera detected.\nIf you have one, allow access in\n"
            "System Settings → Privacy & Security → Camera."
        )
    if sys.platform.startswith("win"):
        return (
            "No camera detected.\nIf you have one, allow access in\n"
            "Settings → Privacy & security → Camera."
        )
    return "No camera detected."


class CameraPreview(QFrame):
    """Shows the default camera, or a hint explaining why it can't."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("camera-card")
        self.setFixedHeight(190)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._camera = None
        self._session = None
        self._video = None
        self._placeholder: QLabel | None = None

        _request_macos_permission()
        try:
            from PyQt6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
            from PyQt6.QtMultimediaWidgets import QVideoWidget
        except Exception:
            logger.info("Camera preview unavailable — QtMultimedia not present")
            self._show_placeholder("Camera unavailable")
            return

        device = QMediaDevices.defaultVideoInput()
        if device is None or device.isNull():
            self._show_placeholder(_no_device_hint())
            return
        try:
            self._video = QVideoWidget()
            self._video.setObjectName("camera-video")
            self._layout.addWidget(self._video)
            self._camera = QCamera(device)
            self._session = QMediaCaptureSession()
            self._session.setCamera(self._camera)
            self._session.setVideoOutput(self._video)
            # Surface camera errors (denied permission, in-use, etc.) in the UI.
            self._camera.errorOccurred.connect(self._on_error)
        except Exception:
            logger.exception("Camera preview setup failed")
            self._camera = None
            self._session = None
            self._show_placeholder("Camera setup failed")

    def _show_placeholder(self, text: str) -> None:
        if self._placeholder is not None:
            self._placeholder.setText(text)
            return
        if self._video is not None:
            self._layout.removeWidget(self._video)
            self._video.deleteLater()
            self._video = None
        self._placeholder = label(text, "camera-hint", wrap=True)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._placeholder)

    def _on_error(self, *_args) -> None:
        try:
            err = self._camera.errorString() if self._camera else ""
        except Exception:
            err = ""
        logger.warning("Camera error: %s", err or "unknown")
        self._show_placeholder(err or "Camera unavailable")

    def start(self) -> None:
        if self._camera is not None:
            try:
                self._camera.start()
            except Exception:
                logger.exception("Camera start failed")

    def stop(self) -> None:
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                logger.exception("Camera stop failed")
