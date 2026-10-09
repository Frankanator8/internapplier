from __future__ import annotations

import logging
import sys

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class SpeechController(QObject):
    """Text-to-speech for interviewer turns and speech-to-text for answers.

    ``transcript`` carries recognized text only while listening, so a late
    result after ``stop_listening`` can't overwrite what the user did next.
    ``listening_stopped`` fires when recognition ends on its own or fails.
    """

    transcript = pyqtSignal(str)
    listening_stopped = pyqtSignal()
    speaking_finished = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._tts = None
        self._stt = None
        self.listening = False
        self.unavailable_reason = ""

    @property
    def can_listen(self) -> bool:
        return self._stt is not None

    @property
    def can_speak(self) -> bool:
        return self._tts is not None

    def setup(self) -> None:
        """Create the engines. Deferred because TTS pre-warms the audio stack."""
        try:
            from api.speech import SpeechToText, TextToSpeech, is_supported
        except Exception:
            self.unavailable_reason = "Speech not available."
            return

        if sys.platform == "darwin":
            self._tts = TextToSpeech(self)
            self._tts.finished.connect(self.speaking_finished.emit)
            self._tts.error.connect(lambda _msg: self.speaking_finished.emit())
            # Pre-warm `say` so the first real utterance plays without the
            # macOS audio-subsystem startup delay swallowing it.
            self.speak(" ")

        if not is_supported():
            self.unavailable_reason = "Speech recognition not available on this platform."
            return
        self._stt = SpeechToText(self)
        self._stt.partial.connect(self._on_text)
        self._stt.final.connect(self._on_text)
        self._stt.error.connect(self._on_stt_error)
        self._stt.finished.connect(self._on_stt_finished)

    # ── Listening ───────────────────────────────────────────────
    def start_listening(self) -> None:
        if self._stt is None:
            return
        self.stop_speaking()
        self.listening = True
        try:
            self._stt.start()
        except Exception as exc:
            logger.exception("STT start failed")
            self._on_stt_error(str(exc))

    def stop_listening(self) -> None:
        if self._stt is not None and self.listening:
            self.listening = False
            self._stt.stop()

    def _on_text(self, text: str) -> None:
        if self.listening:
            self.transcript.emit(text)

    def _on_stt_error(self, msg: str) -> None:
        logger.warning("STT error: %s", msg)
        self._on_stt_finished()

    def _on_stt_finished(self) -> None:
        self.listening = False
        self.listening_stopped.emit()

    # ── Speaking ────────────────────────────────────────────────
    def speak(self, text: str) -> None:
        if self._tts is None:
            return
        try:
            self._tts.speak(text)
        except Exception:
            logger.exception("TTS speak failed")

    def stop_speaking(self) -> None:
        if self._tts is None:
            return
        try:
            self._tts.stop()
        except Exception:
            logger.exception("TTS stop failed")
