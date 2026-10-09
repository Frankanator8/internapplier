from __future__ import annotations

import logging
import os

from PyQt6.QtWidgets import QMessageBox, QWidget

logger = logging.getLogger(__name__)


def resolve_pdf_collision(parent: QWidget, payload: dict) -> None:
    """If saving had to rename a resume to avoid a name clash, ask whether to
    overwrite the existing file instead. Updates ``payload["pdf"]`` in place."""
    if not payload.get("pdf_collision"):
        return
    written = payload.get("pdf") or ""
    desired = payload.get("pdf_desired") or ""
    if not written or not desired or written == desired:
        return
    if not os.path.exists(written) or not os.path.exists(desired):
        return

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Resume name already exists")
    box.setText(f"A resume named “{os.path.basename(desired)}” already exists.")
    box.setInformativeText(
        f"Overwrite it, or keep both (this one was saved as “{os.path.basename(written)}”)?"
    )
    overwrite_btn = box.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
    keep_btn = box.addButton("Keep both", QMessageBox.ButtonRole.AcceptRole)
    box.setDefaultButton(keep_btn)
    box.exec()
    if box.clickedButton() is not overwrite_btn:
        return
    try:
        from api.generate_resume.persist import move_persisted_resume

        move_persisted_resume(written, desired)
        payload["pdf"] = desired
        logger.info("resolve_pdf_collision — overwrote %s", desired)
    except Exception:
        logger.exception("resolve_pdf_collision — overwrite failed")
