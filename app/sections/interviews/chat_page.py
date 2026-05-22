from __future__ import annotations

import datetime
import logging
import uuid
from typing import Callable

from PyQt6.QtCore import QObject, QThread, QTimer, Qt
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QTabWidget, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from api.interview_parsing import extract_partial_feedback, parse_grade_payload

from ..base import _icon_btn, _label, _primary_btn, _secondary_btn
from .workers import _ChatReplyWorker, _FeedbackWorker, _NotesWorker

logger = logging.getLogger(__name__)


class InterviewChatPage(QWidget):
    def __init__(
        self,
        get_profile: Callable[[], dict] | None = None,
        get_applications: Callable[[], list[dict]] | None = None,
        get_research_cache: Callable[[], dict] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._get_profile = get_profile or (lambda: {})
        self._get_applications = get_applications or (lambda: [])
        self._get_research_cache = get_research_cache or (lambda: {})

        self._threads: list[QThread] = []
        self._workers: list[QObject] = []

        self._history: list[dict] = []
        self._cards: list[dict] = []
        self._notes_md: str = ""
        self._session_id: str = uuid.uuid4().hex
        self._started_at: datetime.datetime = datetime.datetime.now()
        self._current_job: dict | None = None
        self._current_job_app_idx: int | None = None
        self._reply_in_flight: bool = False
        self._notes_buffer: str = ""

        self._stt = None
        self._stt_active: bool = False
        self._tts = None
        self._pending_auto_listen: bool = False

        self._camera = None
        self._capture_session = None
        self._video_widget = None

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        main_col = QWidget()
        main_layout = QVBoxLayout(main_col)
        main_layout.setContentsMargins(20, 18, 12, 14)
        main_layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addWidget(_label("Interview Practice", "section-title"))
        header_row.addStretch()
        header_row.addWidget(QLabel("Job:"))
        self._job_picker = QComboBox()
        self._job_picker.setMinimumWidth(220)
        self._job_picker.currentIndexChanged.connect(self._on_job_changed)
        header_row.addWidget(self._job_picker)
        self._new_chat_btn = _secondary_btn("🆕 New Chat", 110)
        self._new_chat_btn.clicked.connect(self._on_new_chat)
        header_row.addWidget(self._new_chat_btn)
        main_layout.addLayout(header_row)

        self._transcript_scroll = QScrollArea()
        self._transcript_scroll.setWidgetResizable(True)
        self._transcript_scroll.setFrameShape(QFrame.Shape.NoFrame)
        transcript_host = QWidget()
        transcript_host.setStyleSheet("background: transparent;")
        self._transcript_layout = QVBoxLayout(transcript_host)
        self._transcript_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._transcript_layout.setSpacing(10)
        self._transcript_layout.setContentsMargins(0, 0, 8, 8)
        self._transcript_scroll.setWidget(transcript_host)
        main_layout.addWidget(self._transcript_scroll, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        self._input = QTextEdit()
        self._input.setPlaceholderText("Type your answer, or click 🎤 to speak…")
        self._input.setFixedHeight(80)
        self._input.textChanged.connect(self._refresh_send_enabled)
        input_row.addWidget(self._input, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(6)
        self._mic_btn = _icon_btn("🎤")
        self._mic_btn.setToolTip("Speak your answer")
        self._mic_btn.setCheckable(True)
        self._mic_btn.clicked.connect(self._on_mic_toggled)
        self._send_btn = _primary_btn("Send", 90)
        self._send_btn.clicked.connect(self._on_send)
        self._send_btn.setEnabled(False)
        btn_col.addWidget(self._mic_btn, 0, Qt.AlignmentFlag.AlignRight)
        btn_col.addWidget(self._send_btn, 0, Qt.AlignmentFlag.AlignRight)
        input_row.addLayout(btn_col)
        main_layout.addLayout(input_row)

        outer.addWidget(main_col, 1)

        # ── Side panel ────────────────────────────────────────────
        side = QWidget()
        side.setFixedWidth(340)
        side.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(8, 18, 20, 14)
        side_layout.setSpacing(8)

        # Local-only camera preview. Frames are rendered straight to the
        # QVideoWidget by Qt's pipeline — no capture path feeds AI workers.
        self._camera_frame = self._build_camera_preview()
        side_layout.addWidget(self._camera_frame)

        side_layout.addWidget(_label("Feedback", "section-title"))

        self._side_tabs = QTabWidget()
        self._side_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._cards_scroll = QScrollArea()
        self._cards_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        cards_host = QWidget()
        cards_host.setStyleSheet("background: transparent;")
        self._cards_layout_v = QVBoxLayout(cards_host)
        self._cards_layout_v.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards_layout_v.setSpacing(10)
        self._cards_layout_v.setContentsMargins(0, 4, 4, 4)
        self._cards_empty_label = QLabel(
            "Per-answer feedback will appear here after you send a reply."
        )
        self._cards_empty_label.setWordWrap(True)
        self._cards_empty_label.setObjectName("muted")
        self._cards_empty_label.setStyleSheet("padding: 8px 4px;")
        self._cards_layout_v.addWidget(self._cards_empty_label)
        self._cards_scroll.setWidget(cards_host)
        self._side_tabs.addTab(self._cards_scroll, "Per-Answer")

        self._notes_view = QTextBrowser()
        self._notes_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._notes_view.setPlaceholderText(
            "Overall coaching notes will populate as the conversation progresses."
        )
        self._side_tabs.addTab(self._notes_view, "Overall Notes")

        side_layout.addWidget(self._side_tabs, 1)

        outer.addWidget(side)

        # Ctrl+Enter sends
        self._input.installEventFilter(self)

        self._populate_job_picker()
        # Speech setup and the opening AI turn are deferred until the page is
        # actually shown — otherwise TTS prewarm and the first interviewer reply
        # fire at app startup, while the user is on a different tab.
        self._opening_kicked: bool = False

    # ── Camera preview (local display only — never sent to AI) ───
    def _build_camera_preview(self) -> QWidget:
        container = QFrame()
        container.setObjectName("card")
        container.setStyleSheet(
            "QFrame#card { background: #111; border: 1px solid #e0e0e0;"
            " border-radius: 8px; }"
        )
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        container.setFixedHeight(190)
        self._camera_layout = v
        self._camera_placeholder: QLabel | None = None

        # Fire the macOS permission prompt early (fire-and-forget). Without
        # this, QCamera silently shows black frames the first time.
        self._kick_macos_camera_permission()

        try:
            from PyQt6.QtMultimedia import QCamera, QMediaCaptureSession, QMediaDevices
            from PyQt6.QtMultimediaWidgets import QVideoWidget
        except Exception:
            logger.info("Camera preview unavailable — QtMultimedia not present")
            self._show_camera_placeholder("Camera unavailable")
            return container

        device = QMediaDevices.defaultVideoInput()
        if device is None or device.isNull():
            self._show_camera_placeholder(self._no_device_hint())
            return container

        try:
            self._video_widget = QVideoWidget()
            self._video_widget.setStyleSheet("background: #000;")
            v.addWidget(self._video_widget)

            self._camera = QCamera(device)
            self._capture_session = QMediaCaptureSession()
            self._capture_session.setCamera(self._camera)
            self._capture_session.setVideoOutput(self._video_widget)
            # Surface camera errors (denied permission, in-use, etc.) in the UI.
            try:
                self._camera.errorOccurred.connect(self._on_camera_error)
            except Exception:
                pass
        except Exception:
            logger.exception("Camera preview setup failed")
            self._camera = None
            self._capture_session = None
            self._show_camera_placeholder("Camera setup failed")
        return container

    def _show_camera_placeholder(self, text: str):
        # Replace the video widget with a label, or update the existing one.
        if self._camera_placeholder is not None:
            self._camera_placeholder.setText(text)
            return
        if getattr(self, "_video_widget", None) is not None:
            self._camera_layout.removeWidget(self._video_widget)
            self._video_widget.deleteLater()
            self._video_widget = None
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("muted")
        label.setStyleSheet("font-size: 12px;")
        label.setWordWrap(True)
        self._camera_layout.addWidget(label)
        self._camera_placeholder = label

    def _kick_macos_camera_permission(self):
        import sys
        if sys.platform != "darwin":
            return
        try:
            from AVFoundation import AVCaptureDevice, AVMediaTypeVideo
        except Exception:
            return
        try:
            status = AVCaptureDevice.authorizationStatusForMediaType_(AVMediaTypeVideo)
        except Exception:
            return
        # 3 = Authorized; nothing to do. 1/2 = Restricted/Denied; prompt won't help.
        if status != 0:
            return
        try:
            # Fire-and-forget. The handler may never run if Info.plist lacks
            # NSCameraUsageDescription, so we don't block UI on it.
            AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                AVMediaTypeVideo, lambda _granted: None
            )
        except Exception:
            logger.exception("Camera permission request failed")

    def _no_device_hint(self) -> str:
        import sys
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

    def _on_camera_error(self, *_args):
        try:
            err = self._camera.errorString() if self._camera else ""
        except Exception:
            err = ""
        logger.warning("Camera error: %s", err or "unknown")
        self._show_camera_placeholder(err or "Camera unavailable")

    def _start_camera(self):
        if self._camera is not None:
            try:
                self._camera.start()
            except Exception:
                logger.exception("Camera start failed")

    def _stop_camera(self):
        if self._camera is not None:
            try:
                self._camera.stop()
            except Exception:
                logger.exception("Camera stop failed")

    def hideEvent(self, event):  # noqa: N802
        self._stop_camera()
        self._stop_speaking()
        super().hideEvent(event)

    # ── Speech wiring ────────────────────────────────────────────
    def _maybe_setup_speech(self):
        try:
            from api.speech import SpeechToText, TextToSpeech, is_supported
        except Exception:
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip("Speech not available.")
            return

        import sys
        if sys.platform == "darwin":
            self._tts = TextToSpeech(self)
            self._tts.finished.connect(self._on_tts_finished)
            self._tts.error.connect(lambda _msg: self._on_tts_finished())
            # Pre-warm `say` so the first real utterance plays without
            # the macOS audio-subsystem startup delay swallowing it.
            try:
                self._tts.speak(" ")
            except Exception:
                logger.exception("TTS prewarm failed")

        if not is_supported():
            self._mic_btn.setEnabled(False)
            self._mic_btn.setToolTip("Speech recognition not available on this platform.")
            return
        self._stt = SpeechToText(self)
        self._stt.partial.connect(self._on_stt_partial)
        self._stt.final.connect(self._on_stt_final)
        self._stt.error.connect(self._on_stt_error)
        self._stt.finished.connect(self._on_stt_finished)

    def _on_mic_toggled(self, checked: bool):
        if self._stt is None:
            return
        if checked:
            self._stop_speaking()
            self._stt_active = True
            self._mic_btn.setText("⏺")
            try:
                self._stt.start()
            except Exception as exc:
                logger.exception("STT start failed")
                self._on_stt_error(str(exc))
        else:
            self._stt_active = False
            self._stt.stop()
            QTimer.singleShot(50, self._on_send)

    def _speak(self, text: str) -> None:
        if self._tts is None:
            return
        try:
            self._tts.speak(text)
        except Exception:
            logger.exception("TTS speak failed")

    def _stop_speaking(self) -> None:
        if self._tts is None:
            return
        try:
            self._tts.stop()
        except Exception:
            logger.exception("TTS stop failed")

    def _on_stt_partial(self, text: str):
        if self._stt_active:
            self._input.setPlainText(text)

    def _on_stt_final(self, text: str):
        if not self._stt_active:
            # Late final emitted after we already stopped (e.g. user hit
            # Send or pressed the mic again). Ignore so we don't undo
            # the input clear.
            return
        self._input.setPlainText(text)

    def _on_stt_error(self, msg: str):
        logger.warning("STT error: %s", msg)
        self._mic_btn.setChecked(False)
        self._mic_btn.setText("🎤")
        self._stt_active = False

    def _on_stt_finished(self):
        self._mic_btn.setChecked(False)
        self._mic_btn.setText("🎤")
        self._stt_active = False

    def _auto_start_listening(self):
        if self._stt is None or self._stt_active or self._reply_in_flight:
            self._pending_auto_listen = False
            return
        if not self._mic_btn.isEnabled():
            self._pending_auto_listen = False
            return
        self._pending_auto_listen = False
        self._input.clear()
        self._mic_btn.setChecked(True)
        self._on_mic_toggled(True)

    def _on_tts_finished(self):
        if self._pending_auto_listen:
            self._auto_start_listening()

    # ── Job picker ───────────────────────────────────────────────
    def _populate_job_picker(self):
        self._job_picker.blockSignals(True)
        self._job_picker.clear()
        self._job_picker.addItem("Generic — no job", userData=None)
        apps = self._get_applications() or []
        for idx, entry in enumerate(apps):
            company = (entry.get("company") or "").strip()
            role = (entry.get("role") or "").strip()
            if not company and not role:
                continue
            label = " — ".join([s for s in (company, role) if s])
            self._job_picker.addItem(label, userData=idx)

        # Restore previously selected job so it survives re-show / apps changes.
        target_row = 0
        if self._current_job_app_idx is not None:
            found = False
            for row in range(self._job_picker.count()):
                if self._job_picker.itemData(row) == self._current_job_app_idx:
                    target_row = row
                    found = True
                    break
            if not found:
                self._current_job_app_idx = None
                self._current_job = None
        self._job_picker.setCurrentIndex(target_row)
        self._job_picker.blockSignals(False)

    def _on_job_changed(self, index: int):
        if index < 0:
            self._current_job_app_idx = None
            self._current_job = None
            return
        app_idx = self._job_picker.itemData(index)
        if app_idx is None:
            self._current_job_app_idx = None
            self._current_job = None
            return
        apps = self._get_applications() or []
        if not (0 <= app_idx < len(apps)):
            self._current_job_app_idx = None
            self._current_job = None
            return
        entry = apps[app_idx]
        from ..applier import _research_from_cache
        research = _research_from_cache(
            self._get_research_cache() or {}, entry.get("company", "")
        )
        self._current_job_app_idx = app_idx
        self._current_job = {
            "company_name": entry.get("company") or None,
            "title": entry.get("role") or None,
            "company_research": research,
            "job_description": entry.get("description") or None,
        }

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._populate_job_picker()
        self._start_camera()
        if not self._opening_kicked:
            self._opening_kicked = True
            self._maybe_setup_speech()
            QTimer.singleShot(0, self._kick_off_opening_turn)

    # ── Transcript bubbles ───────────────────────────────────────
    def _add_bubble(self, role: str, text: str) -> QLabel:
        card = QFrame()
        card.setObjectName("chat-bubble-user" if role == "user" else "chat-bubble-ai")
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 8, 12, 10)
        v.setSpacing(4)

        who = QLabel("You" if role == "user" else "Interviewer")
        who.setObjectName("muted")
        who.setStyleSheet("font-size: 11px; font-weight: 600;")
        v.addWidget(who)

        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        body.setStyleSheet("font-size: 14px;")
        v.addWidget(body)

        self._transcript_layout.addWidget(card)
        QTimer.singleShot(0, self._scroll_transcript_to_bottom)
        return body

    def _scroll_transcript_to_bottom(self):
        bar = self._transcript_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _scroll_cards_to_bottom(self):
        bar = self._cards_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ── Per-answer feedback cards ────────────────────────────────
    def _add_feedback_card(self, question: str) -> dict:
        if self._cards_empty_label is not None:
            self._cards_empty_label.setVisible(False)

        card = QFrame()
        card.setObjectName("card")
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 10)
        v.setSpacing(4)

        q_label = QLabel(question or "Opening exchange")
        q_label.setWordWrap(True)
        q_label.setObjectName("field-sublabel")
        v.addWidget(q_label)

        title = QLabel("GENERATING…")
        title.setObjectName("muted")
        title.setStyleSheet("font-size: 10px; font-weight: 700;")
        v.addWidget(title)

        body = QLabel("")
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        body.setStyleSheet("font-size: 13px;")
        body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        body.setMinimumWidth(1)
        body_sp = body.sizePolicy()
        body_sp.setHeightForWidth(True)
        body_sp.setVerticalPolicy(QSizePolicy.Policy.MinimumExpanding)
        body.setSizePolicy(body_sp)
        v.addWidget(body)

        self._cards_layout_v.addWidget(card)
        QTimer.singleShot(0, self._scroll_cards_to_bottom)
        record = {
            "question": question,
            "answer": "",
            "rubric_md": "",
            "buffer": "",
            "widget": card,
            "title": title,
            "body": body,
        }
        self._cards.append(record)
        return record

    # ── Send flow ────────────────────────────────────────────────
    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        from PyQt6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
                mods & Qt.KeyboardModifier.ControlModifier
            ):
                self._on_send()
                return True
        return super().eventFilter(obj, event)

    def _refresh_send_enabled(self):
        has_text = bool(self._input.toPlainText().strip())
        self._send_btn.setEnabled(has_text and not self._reply_in_flight)

    def _set_reply_in_flight(self, value: bool):
        self._reply_in_flight = value
        self._refresh_send_enabled()

    def _kick_off_opening_turn(self):
        # Empty history → AI greets and asks first question.
        self._spawn_chat_reply()

    def _on_send(self):
        if self._reply_in_flight:
            return
        text = self._input.toPlainText().strip()
        if not text:
            return
        if self._stt is not None and self._stt_active:
            self._stt_active = False
            self._stt.stop()
        self._stop_speaking()
        self._input.clear()

        last_question = ""
        for turn in reversed(self._history):
            if turn.get("role") == "assistant" and (turn.get("content") or "").strip():
                last_question = turn["content"]
                break

        self._add_bubble("user", text)
        self._history.append({"role": "user", "content": text})

        card = self._add_feedback_card(last_question)
        card["answer"] = text
        self._spawn_feedback_worker(last_question, text, card)

        self._spawn_chat_reply()

    def _spawn_chat_reply(self):
        profile = self._get_profile() or {}
        job = self._current_job or {}

        bubble_body = self._add_bubble("assistant", "")
        buffer = {"text": ""}

        worker = _ChatReplyWorker(
            history=list(self._history),
            profile=profile,
            company_name=job.get("company_name"),
            company_research=job.get("company_research"),
            job_description=job.get("job_description"),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        self._set_reply_in_flight(True)

        def on_chunk(delta: str):
            buffer["text"] += delta
            try:
                bubble_body.setText(buffer["text"])
            except RuntimeError:
                # Bubble was deleted (e.g. New Chat clicked mid-stream).
                return
            self._scroll_transcript_to_bottom()

        def on_finished():
            final = buffer["text"].strip()
            spoke = False
            if final:
                self._history.append({"role": "assistant", "content": final})
                if self._tts is not None and self.isVisible():
                    self._speak(final)
                    spoke = True
                self._spawn_notes_worker()
            self._set_reply_in_flight(False)
            thread.quit()
            if spoke:
                # Wait for TTS to finish before opening the mic — otherwise
                # starting STT immediately stops TTS playback.
                self._pending_auto_listen = True
            else:
                self._auto_start_listening()

        def on_error(msg: str):
            try:
                bubble_body.setText(f"(error: {msg})")
            except RuntimeError:
                pass
            self._set_reply_in_flight(False)
            thread.quit()

        worker.stream.connect(on_chunk)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self._workers.remove(worker) if worker in self._workers else None
        )
        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()

    def _spawn_feedback_worker(self, question: str, response: str, card: dict):
        profile = self._get_profile() or {}
        job = self._current_job or {}

        worker = _FeedbackWorker(
            question=question or "(opening — interviewer had not asked a question yet)",
            response=response,
            profile=profile,
            company_name=job.get("company_name"),
            company_research=job.get("company_research"),
            job_description=job.get("job_description"),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_chunk(delta: str):
            card["buffer"] += delta
            partial = extract_partial_feedback(card["buffer"])
            if partial:
                card["title"].setText("STREAMING…")
                card["body"].setText(partial)

        def on_finished():
            buf = card["buffer"]
            try:
                score, feedback = parse_grade_payload(buf)
                rendered = feedback if feedback else "Strong answer — nothing actionable."
                score_str = f"{score:g}"
                card["title"].setText(f"SCORE {score_str}/10")
                card["body"].setText(rendered)
                card["rubric_md"] = f"**Score:** {score_str}/10\n\n{rendered}"
            except (ValueError, TypeError) as exc:
                logger.error(
                    "_FeedbackWorker.on_finished — parse failed: %s; raw=%r",
                    exc, buf[:500],
                )
                err = "AI returned unexpected format — please try again."
                card["title"].setText("FEEDBACK · ERROR")
                card["body"].setText(err)
                card["rubric_md"] = err
            thread.quit()

        def on_error(msg: str):
            card["title"].setText("FEEDBACK · ERROR")
            card["body"].setText(msg)
            thread.quit()

        worker.stream.connect(on_chunk)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self._workers.remove(worker) if worker in self._workers else None
        )
        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()

    def _spawn_notes_worker(self):
        profile = self._get_profile() or {}
        job = self._current_job or {}

        self._notes_buffer = ""

        worker = _NotesWorker(
            history=list(self._history),
            prior_notes=self._notes_md,
            profile=profile,
            company_name=job.get("company_name"),
            company_research=job.get("company_research"),
            job_description=job.get("job_description"),
        )
        thread = QThread(self)
        worker.moveToThread(thread)

        def on_chunk(delta: str):
            self._notes_buffer += delta
            self._notes_view.setMarkdown(self._notes_buffer)

        def on_finished():
            self._notes_md = self._notes_buffer
            self._notes_view.setMarkdown(self._notes_md)
            thread.quit()

        def on_error(msg: str):
            self._notes_view.setMarkdown(
                self._notes_md
                + f"\n\n_(notes update failed: {msg})_"
            )
            thread.quit()

        worker.stream.connect(on_chunk)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            lambda: self._workers.remove(worker) if worker in self._workers else None
        )
        self._threads.append(thread)
        self._workers.append(worker)
        thread.start()

    # ── Session lifecycle ────────────────────────────────────────
    def _on_new_chat(self):
        self._stop_speaking()
        self.flush_active_chat()
        self._reset_state()

    def _reset_state(self):
        self._history = []
        self._cards = []
        self._notes_md = ""
        self._notes_buffer = ""
        self._session_id = uuid.uuid4().hex
        self._started_at = datetime.datetime.now()

        # Clear transcript
        while self._transcript_layout.count():
            item = self._transcript_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        # Clear feedback cards
        while self._cards_layout_v.count():
            item = self._cards_layout_v.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards_empty_label = QLabel(
            "Per-answer feedback will appear here after you send a reply."
        )
        self._cards_empty_label.setWordWrap(True)
        self._cards_empty_label.setObjectName("muted")
        self._cards_empty_label.setStyleSheet("padding: 8px 4px;")
        self._cards_layout_v.addWidget(self._cards_empty_label)

        self._notes_view.setMarkdown("")

        QTimer.singleShot(0, self._kick_off_opening_turn)

    def cleanup_threads(self) -> None:
        from .._thread_cleanup import shutdown_threads
        shutdown_threads(self._threads)
        self._workers.clear()

    def flush_active_chat(self) -> None:
        if not any(t.get("role") == "user" for t in self._history):
            return
        try:
            from api.data_store import append_interview_feedback
            job_meta = None
            if self._current_job:
                job_meta = {
                    "company": self._current_job.get("company_name"),
                    "title": self._current_job.get("title"),
                }
            session = {
                "id": self._session_id,
                "started_at": self._started_at.isoformat(timespec="seconds"),
                "ended_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "job": job_meta,
                "transcript": list(self._history),
                "cards": [
                    {
                        "question": c["question"],
                        "answer": c["answer"],
                        "rubric_md": c["rubric_md"],
                    }
                    for c in self._cards
                ],
                "notes_md": self._notes_md,
            }
            append_interview_feedback(session)
        except Exception:
            logger.exception("flush_active_chat — failed to persist session")
