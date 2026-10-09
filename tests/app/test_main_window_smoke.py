"""End-to-end smoke test of the desktop shell, offscreen, with the AI stubbed out."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QtWebEngine must be imported before QApplication is constructed.
from app.main_window import MainWindow  # noqa: E402
from app.ui.sidebar_stack import SidebarStack  # noqa: E402
from app.ui.workers import WorkerPool  # noqa: E402

pytestmark = pytest.mark.usefixtures("isolated_app_dir")


class _FakeProvider:
    def chat_interview_stream(self, **_kw):
        yield "Tell me about yourself."

    def grade_interview_response_stream(self, **_kw):
        yield '{"score": 7, "feedback": "Add a metric."}'

    def summarize_interview_notes_stream(self, **_kw):
        yield "- Be specific."


@pytest.fixture
def window(qapp, monkeypatch):
    from app.sections.interviews.chat import camera, speech

    monkeypatch.setattr("api.ai_provider.get_provider", lambda: _FakeProvider())
    monkeypatch.setattr(speech.SpeechController, "setup", lambda self: None)
    monkeypatch.setattr(camera, "_request_macos_permission", lambda: None)
    monkeypatch.setattr(camera.CameraPreview, "start", lambda self: None)

    from api import data_store
    data_store.save({
        "general_info": {"first_name": "Ada", "employment_status": "Student"},
        "experience": [{"company": "Acme", "title": "Intern", "bullets": ["Built X"],
                        "skills": ["python", "SQL"], "start": "", "end": "", "category": "other"}],
        "skills": ["Python", "Go"],
        "hobbies": ["Chess"],
        "applications": [{"company": "Acme", "role": "SWE Intern", "date": "2026-01-01",
                          "status": "Added", "notes": "", "description": "JD", "links": []}],
        "research_cache": {"Acme": {"url": "https://acme.test", "result": {"summary": "Rockets"}}},
    })
    data_store.invalidate()  # read back from disk, as a fresh launch would
    win = MainWindow()
    win.show()
    yield win
    for pool in win.findChildren(WorkerPool):
        pool.shutdown()
    win.close()


def _drain(qapp, pools, rounds: int = 200):
    for _ in range(rounds):
        qapp.processEvents()
        if not any(p.busy for p in pools):
            qapp.processEvents()
            return
        pools[0].thread().msleep(10)


def test_every_tab_and_subpage_builds_and_shows(qapp, window):
    tabs = window.centralWidget()
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i)
        qapp.processEvents()
        for stack in tabs.widget(i).findChildren(SidebarStack) + (
            [tabs.widget(i)] if isinstance(tabs.widget(i), SidebarStack) else []
        ):
            for row in range(stack._sidebar.count()):
                stack._sidebar.setCurrentRow(row)
                qapp.processEvents()
    _drain(qapp, window.findChildren(WorkerPool))


def test_profile_round_trips(window):
    data = window._profile.get_data()
    assert data["general_info"]["first_name"] == "Ada"
    assert data["general_info"]["employment_status"] == "Student"
    assert data["experience"][0]["company"] == "Acme"
    assert data["experience"][0]["category"] == "other"
    assert "skills" not in data["experience"][0]
    # Legacy per-entry skills fold into the Skills list on load.
    assert data["skills"] == ["Python", "Go", "SQL"]
    window._profile.load(data)
    assert window._profile.get_data() == data


def test_import_merge_appends_and_dedupes(window):
    window._profile.apply_import({"skills": ["python", "Rust"], "general_info": {"last_name": "L"}}, "append")
    data = window._profile.get_data()
    assert data["skills"] == ["Python", "Go", "SQL", "Rust"]
    assert data["general_info"]["first_name"] == "Ada"
    assert data["general_info"]["last_name"] == "L"


def test_save_persists_everything(window):
    from api import data_store

    window._save()
    saved = data_store.load()
    assert saved["research_cache"]["Acme"]["result"]["summary"] == "Rockets"
    assert saved["applications"][0]["company"] == "Acme"
    assert saved["hobbies"] == ["Chess"]


def test_chat_with_a_job_selected_grades_and_saves(qapp, window):
    """Regression: picking a job used to raise ImportError (B1)."""
    from api import data_store

    chat = window._interviews._chat_page
    window.centralWidget().setCurrentWidget(window._interviews)
    window._interviews.set_current(chat)
    qapp.processEvents()
    chat._job_picker.setCurrentIndex(1)
    job, meta = chat._job()
    assert job["company_name"] == "Acme"
    assert job["company_research"] == {"summary": "Rockets"}
    assert meta == {"company": "Acme", "title": "SWE Intern"}

    pools = window.findChildren(WorkerPool)
    _drain(qapp, pools)
    chat._input.setPlainText("I build rockets.")
    chat._on_send()
    _drain(qapp, pools)
    assert chat._cards[0].rubric_md.startswith("**Score:** 7/10")

    chat.flush_active_chat()
    sessions = data_store.load_interview_feedback()
    assert sessions[-1]["job"] == {"company": "Acme", "title": "SWE Intern"}


def test_close_joins_all_threads(qapp, window):
    window.close()
    assert not any(p.busy for p in window.findChildren(WorkerPool))


def test_onboarding_steps_through_and_saves(qapp, monkeypatch, isolated_app_dir):
    from api import ai_provider, app_settings
    from app.dialogs.onboarding import OnboardingDialog

    assert ai_provider.settings.ENV_FILE.parent == isolated_app_dir  # never the real .env
    monkeypatch.setattr("app.dialogs.onboarding.ONBOARDED_FILE", isolated_app_dir / "onboarded.ini")
    dlg = OnboardingDialog()
    dlg._writing_sample_edit.setPlainText("I write like this.")
    for _ in range(dlg._stack.count() - 1):
        dlg._go_next()
    assert dlg._next_btn.text() == "Finish"
    assert "Writing sample saved" in dlg._done_summary.text()
    assert app_settings.get_writing_sample() == "I write like this."
    dlg._go_next()
    assert (isolated_app_dir / "onboarded.ini").exists()
