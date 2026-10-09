from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QtWebEngine must be imported before QApplication is constructed, and the
# applier package pulls it in via the library/preview pages.
from app.sections.applier.builder import (  # noqa: E402
    AUTOSCROLL_MARGIN, BuilderCanvas, BuilderScroll,
)


def _flush(qapp):
    for _ in range(4):
        qapp.processEvents()
        qapp.sendPostedEvents()


def _canvas_in_scroll(qapp, sections: int = 6):
    from PyQt6.QtWidgets import QVBoxLayout, QWidget

    canvas = BuilderCanvas()
    scroll = BuilderScroll(canvas)
    host = QWidget()
    QVBoxLayout(host).addWidget(scroll)
    host.resize(500, 400)
    host.show()
    _flush(qapp)
    for i in range(sections):
        canvas.insert_section(
            i,
            f"Section {i}",
            items=[{"kind": "experience", "data": {"title": "T", "bullets": ["a", "b"]}}],
        )
    _flush(qapp)
    return canvas, scroll, host


def test_empty_canvas_fills_the_viewport(qapp):
    """An empty canvas must still cover the viewport so drops land on it."""
    canvas, scroll, _host = _canvas_in_scroll(qapp, sections=0)
    assert canvas.height() == scroll.viewport().height()
    assert scroll.verticalScrollBar().maximum() == 0


def test_tall_canvas_scrolls_instead_of_clipping(qapp):
    """Regression: an explicit minimumHeight used to pin the canvas to the
    viewport, so a long resume was clipped with no scrollbar."""
    canvas, scroll, _host = _canvas_in_scroll(qapp)
    bar = scroll.verticalScrollBar()
    assert canvas.height() > scroll.viewport().height()
    assert bar.maximum() > 0
    assert canvas.height() - scroll.viewport().height() == bar.maximum()

    bar.setValue(bar.maximum())
    _flush(qapp)
    assert canvas.pos().y() == -bar.maximum()


def test_drop_index_and_indicator_track_scroll_position(qapp):
    from PyQt6.QtCore import QPoint

    canvas, scroll, _host = _canvas_in_scroll(qapp)
    bar = scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    _flush(qapp)

    last = canvas._section_widgets()[-1]
    card = last.item_widgets()[0]
    y = card.mapTo(canvas, QPoint(0, 0)).y() + card.height() // 2 + 1
    assert canvas._item_drop_index(y) == (5, 1)

    canvas._show_indicator(canvas._indicator_y_item(5, 1))
    indicator_y = canvas._indicator.geometry().y()
    assert 0 <= indicator_y - bar.value() <= scroll.viewport().height()


def test_drag_autoscroll_runs_at_the_edges_and_stops(qapp):
    canvas, scroll, _host = _canvas_in_scroll(qapp)
    bar = scroll.verticalScrollBar()
    viewport_h = scroll.viewport().height()

    bar.setValue(0)
    canvas._autoscroll.update(viewport_h - 5)
    assert canvas._autoscroll.timer.isActive()
    assert canvas._autoscroll.delta > 0
    canvas._autoscroll.tick()
    assert bar.value() > 0

    canvas._autoscroll.update(bar.value() + 5)
    assert canvas._autoscroll.delta < 0

    canvas._autoscroll.update(bar.value() + viewport_h // 2)
    assert not canvas._autoscroll.timer.isActive()

    # At the end of the range there is nowhere left to go.
    bar.setValue(bar.maximum())
    canvas._autoscroll.update(bar.value() + viewport_h - 5)
    canvas._autoscroll.tick()
    assert not canvas._autoscroll.timer.isActive()


def test_drag_autoscroll_idle_when_nothing_overflows(qapp):
    canvas, scroll, _host = _canvas_in_scroll(qapp, sections=0)
    canvas._autoscroll.update(scroll.viewport().height() - AUTOSCROLL_MARGIN // 2)
    assert not canvas._autoscroll.timer.isActive()
