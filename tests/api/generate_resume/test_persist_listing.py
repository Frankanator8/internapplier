from __future__ import annotations


def test_list_generated_resumes_newest_first(monkeypatch, tmp_path):
    import os

    from api.generate_resume import persist

    monkeypatch.setattr(persist, "get_resume_output_dir", lambda: tmp_path)
    old = tmp_path / "Acme_SWE-Intern.pdf"
    new = tmp_path / "Globex_resume.pdf"
    old.write_bytes(b"%PDF")
    new.write_bytes(b"%PDF")
    os.utime(old, (1, 1))
    assert persist.list_generated_resumes() == [(new, "Globex"), (old, "Acme Swe Intern")]
