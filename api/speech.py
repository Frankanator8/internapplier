from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

_IS_MAC = sys.platform == "darwin"

try:
    if not _IS_MAC:
        raise ImportError("speech frameworks are macOS-only")
    import objc  # noqa: F401
    from AVFoundation import (
        AVAudioEngine,
        AVAudioSession,
        AVAudioSessionCategoryRecord,
    )
    from Foundation import NSLocale, NSObject
    from Speech import (
        SFSpeechAudioBufferRecognitionRequest,
        SFSpeechRecognizer,
        SFSpeechRecognizerAuthorizationStatusAuthorized,
    )

    _PYOBJC_AVAILABLE = True
except ImportError as _exc:
    logger.debug("speech: PyObjC frameworks unavailable: %s", _exc)
    _PYOBJC_AVAILABLE = False


def is_supported() -> bool:
    return _IS_MAC and _PYOBJC_AVAILABLE


class TextToSpeech(QObject):
    """Wraps the macOS `say(1)` command. Non-blocking; one utterance at a time."""

    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._proc: subprocess.Popen | None = None
        self._voices_cache: list[str] | None = None

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[int] = None,
    ) -> None:
        if not _IS_MAC:
            raise NotImplementedError("TTS is macOS-only for now")
        if not text.strip():
            return

        self.stop()

        cmd = ["say"]
        if voice:
            cmd += ["-v", voice]
        if rate is not None:
            cmd += ["-r", str(int(rate))]
        cmd += ["--", text]

        logger.info("TextToSpeech.speak — chars=%d voice=%s rate=%s",
                    len(text), voice, rate)
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError:
            self.error.emit("`say` command not found")
            return
        except OSError as exc:
            logger.exception("TextToSpeech.speak — Popen failed")
            self.error.emit(str(exc))
            return

        self.started.emit()

        def _watch(proc: subprocess.Popen):
            rc = proc.wait()
            if rc == 0:
                self.finished.emit()
            elif rc < 0:
                self.finished.emit()
            else:
                err = ""
                if proc.stderr is not None:
                    try:
                        err = proc.stderr.read().decode("utf-8", "replace").strip()
                    except OSError:
                        err = ""
                self.error.emit(err or f"say exited with code {rc}")

        import threading
        threading.Thread(target=_watch, args=(self._proc,), daemon=True).start()

    def stop(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
        except OSError:
            pass

    def available_voices(self) -> list[str]:
        if not _IS_MAC:
            return []
        if self._voices_cache is not None:
            return self._voices_cache
        if shutil.which("say") is None:
            self._voices_cache = []
            return self._voices_cache
        try:
            out = subprocess.check_output(
                ["say", "-v", "?"], stderr=subprocess.DEVNULL, timeout=5
            ).decode("utf-8", "replace")
        except (subprocess.SubprocessError, OSError):
            self._voices_cache = []
            return self._voices_cache

        voices: list[str] = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            name = line.split()[0]
            if name:
                voices.append(name)
        self._voices_cache = voices
        return voices


class SpeechToText(QObject):
    """Wraps Apple's on-device SFSpeechRecognizer + AVAudioEngine."""

    authorized = pyqtSignal(bool)
    partial = pyqtSignal(str)
    final = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._recognizer = None
        self._request = None
        self._task = None
        self._engine = None
        self._input_node = None
        self._running = False

    def start(self, locale: str = "en-US") -> None:
        if not is_supported():
            raise NotImplementedError("STT requires macOS with PyObjC speech frameworks")
        if self._running:
            logger.debug("SpeechToText.start — already running, ignoring")
            return

        logger.info("SpeechToText.start — locale=%s", locale)

        def _on_auth(status):
            ok = status == SFSpeechRecognizerAuthorizationStatusAuthorized
            self.authorized.emit(bool(ok))
            if not ok:
                self.error.emit(f"speech recognition not authorized (status={status})")
                self.finished.emit()
                return
            try:
                self._begin_capture(locale)
            except Exception as exc:
                logger.exception("SpeechToText._begin_capture failed")
                self.error.emit(str(exc))
                self.finished.emit()

        SFSpeechRecognizer.requestAuthorization_(_on_auth)

    def _begin_capture(self, locale: str) -> None:
        ns_locale = NSLocale.alloc().initWithLocaleIdentifier_(locale)
        recognizer = SFSpeechRecognizer.alloc().initWithLocale_(ns_locale)
        if recognizer is None or not recognizer.isAvailable():
            self.error.emit(f"recognizer unavailable for locale {locale}")
            self.finished.emit()
            return

        try:
            session = AVAudioSession.sharedInstance()
            session.setCategory_error_(AVAudioSessionCategoryRecord, None)
            session.setActive_error_(True, None)
        except Exception:
            pass

        request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
        request.setShouldReportPartialResults_(True)

        engine = AVAudioEngine.alloc().init()
        input_node = engine.inputNode()
        recording_format = input_node.outputFormatForBus_(0)

        def _tap(buffer, when):
            try:
                request.appendAudioPCMBuffer_(buffer)
            except Exception:
                logger.exception("SpeechToText: appendAudioPCMBuffer_ failed")

        input_node.installTapOnBus_bufferSize_format_block_(
            0, 1024, recording_format, _tap
        )

        engine.prepare()
        ok, err = engine.startAndReturnError_(None)
        if not ok:
            self.error.emit(f"audio engine failed to start: {err}")
            self.finished.emit()
            return

        def _result_cb(result, nserror):
            if result is not None:
                text = str(result.bestTranscription().formattedString())
                if result.isFinal():
                    self.final.emit(text)
                    self.stop()
                else:
                    self.partial.emit(text)
            if nserror is not None:
                msg = str(nserror.localizedDescription())
                logger.warning("SpeechToText: recognition error: %s", msg)
                self.error.emit(msg)
                self.stop()

        task = recognizer.recognitionTaskWithRequest_resultHandler_(
            request, _result_cb
        )

        self._recognizer = recognizer
        self._request = request
        self._task = task
        self._engine = engine
        self._input_node = input_node
        self._running = True

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        logger.info("SpeechToText.stop")
        try:
            if self._engine is not None:
                self._engine.stop()
            if self._input_node is not None:
                self._input_node.removeTapOnBus_(0)
            if self._request is not None:
                self._request.endAudio()
            if self._task is not None:
                self._task.cancel()
        except Exception:
            logger.exception("SpeechToText.stop — teardown error")
        finally:
            self._task = None
            self._request = None
            self._engine = None
            self._input_node = None
            self.finished.emit()
