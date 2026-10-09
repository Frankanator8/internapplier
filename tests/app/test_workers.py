from __future__ import annotations

import threading

import pytest
from PyQt6.QtCore import QObject

from app.ui.workers import CallWorker, StreamWorker, WorkerPool


def _wait(qapp, pool: WorkerPool, rounds: int = 300) -> None:
    for _ in range(rounds):
        qapp.processEvents()
        if not pool.busy:
            qapp.processEvents()
            return
        pool.thread().msleep(5)
    raise AssertionError("worker never finished")


@pytest.fixture
def pool():
    owner = QObject()  # the pool is a child; keep its owner alive for the test
    yield WorkerPool(owner)
    owner.deleteLater()


def test_pool_runs_worker_and_prunes_thread(qapp, pool):
    results = []
    pool.start(CallWorker(lambda a, b: a + b, 2, 3), finished=results.append)
    assert pool.busy
    _wait(qapp, pool)
    assert results == [5]
    assert not pool.busy


def test_stream_worker_emits_chunks_then_joined_text(qapp, pool):
    chunks, done = [], []
    pool.start(StreamWorker(lambda: iter(["a", "b"])), chunk=chunks.append, finished=done.append)
    _wait(qapp, pool)
    assert chunks == ["a", "b"]
    assert done == ["ab"]


def test_worker_errors_are_reported_not_raised(qapp, pool):
    errors = []

    def boom():
        raise RuntimeError("kaboom")

    pool.start(CallWorker(boom), error=errors.append)
    _wait(qapp, pool)
    assert len(errors) == 1 and "kaboom" in errors[0]


def test_shutdown_joins_running_threads(qapp, pool):
    release = threading.Event()
    pool.start(CallWorker(release.wait, 2))
    release.set()
    pool.shutdown()
    assert not pool.busy


@pytest.mark.usefixtures("isolated_app_dir")
def test_prep_all_follows_entries_not_row_indexes(qapp, monkeypatch):
    """Regression (B3): deleting a row mid-batch must not mark the wrong one."""
    from PyQt6.QtWidgets import QStatusBar

    from app.context import AppContext, ResearchCache
    from app.sections.applications import prep_runner
    from app.sections.applications.tracker_page import TrackerPage

    gate = threading.Event()
    monkeypatch.setattr(
        prep_runner, "GenerateResumeWorker",
        lambda *_a, **_kw: CallWorker(lambda: gate.wait(2) and {}),
    )
    ctx = AppContext(
        get_profile=dict, get_applications=list, set_application_interviews=lambda *_: None,
        research=ResearchCache(), save=lambda: None, status_bar=QStatusBar(),
    )
    tracker = TrackerPage(ctx)
    for company in ("First", "Second", "Third"):
        tracker.add_entry({"company": company, "status": "Added", "description": "JD"})

    tracker._on_prep_all_clicked()   # "First" is now generating
    tracker._delete([0])             # …and gets deleted mid-flight
    gate.set()
    pool = tracker._prep._pool
    for _ in range(3):
        _wait(qapp, pool)

    assert [(e["company"], e["status"]) for e in tracker.get_data()] == [
        ("Second", "Materials Prepped"),
        ("Third", "Materials Prepped"),
    ]
