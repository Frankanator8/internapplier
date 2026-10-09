import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from api.anki_import import AnkiImportError, import_anki_file, import_apkg, import_txt


def _write_collection(path: Path, *, deck_name: str = "Blind 75") -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE col (
            id integer primary key, crt integer, mod integer, scm integer,
            ver integer, dty integer, usn integer, ls integer,
            conf text, models text, decks text, dconf text, tags text
        );
        CREATE TABLE notes (
            id integer primary key, guid text, mid integer, mod integer,
            usn integer, tags text, flds text, sfld text, csum integer,
            flags integer, data text
        );
        CREATE TABLE cards (
            id integer primary key, nid integer, did integer, ord integer,
            mod integer, usn integer, type integer, queue integer, due integer,
            ivl integer, factor integer, reps integer, lapses integer,
            left integer, odue integer, odid integer, flags integer, data text
        );
        """
    )
    decks = json.dumps({
        "1": {"id": 1, "name": "Default"},
        "123": {"id": 123, "name": deck_name},
    })
    conn.execute(
        "INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags) "
        "VALUES (1, 0, 0, 0, 11, 0, 0, 0, '{}', '{}', ?, '{}', '{}')",
        (decks,),
    )
    conn.execute(
        "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) "
        "VALUES (1, 'g1', 1, 0, 0, ' array ', ?, 'Two Sum', 0, 0, '')",
        ("Two Sum\x1fUse a <img src=\"diagram.png\"> hashmap",),
    )
    conn.execute(
        "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) "
        "VALUES (2, 'g2', 1, 0, 0, '', ?, 'Empty', 0, 0, '')",
        ("  \x1f  ",),
    )
    conn.execute(
        "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, "
        "reps, lapses, left, odue, odid, flags, data) "
        "VALUES (1, 1, 123, 0, 0, 0, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')"
    )
    # Second card of the same note should not duplicate the import.
    conn.execute(
        "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, "
        "reps, lapses, left, odue, odid, flags, data) "
        "VALUES (2, 1, 123, 1, 0, 0, 0, 0, 0, 0, 2500, 0, 0, 0, 0, 0, 0, '')"
    )
    conn.commit()
    conn.close()


def _make_apkg(tmp_path: Path) -> Path:
    db_path = tmp_path / "collection.anki2"
    _write_collection(db_path)
    db_bytes = db_path.read_bytes()
    apkg = tmp_path / "deck.apkg"
    with zipfile.ZipFile(apkg, "w") as zf:
        zf.writestr("collection.anki2", db_bytes)
        zf.writestr("media", json.dumps({"0": "diagram.png"}))
        zf.writestr("0", b"PNGDATA")
    return apkg


class TestTxtImport:
    def test_tab_export_with_headers(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_text(
            "#separator:tab\n"
            "#html:true\n"
            "#deck column:3\n"
            "#tags column:4\n"
            "Two Sum\tHash map\tBlind 75\tarray hash\n"
            "Valid Parentheses\tStack\tStacks\tstack\n",
            encoding="utf-8",
        )
        cards = import_txt(path, default_deck="Fallback")
        assert len(cards) == 2
        assert cards[0]["front"] == "Two Sum"
        assert cards[0]["back"] == "Hash map"
        assert cards[0]["deck"] == "Blind 75"
        assert cards[0]["tags"] == ["array", "hash"]
        assert cards[1]["deck"] == "Stacks"

    def test_quoted_multiline_fields(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_text(
            '"Question\nline 2"\t"Answer\nline 2"\n',
            encoding="utf-8",
        )
        cards = import_txt(path)
        assert len(cards) == 1
        assert "line 2" in cards[0]["front"]
        assert "Answer" in cards[0]["back"]

    def test_plain_text_is_escaped(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_text("#html:false\n<a>\tb\n", encoding="utf-8")
        cards = import_txt(path)
        assert cards[0]["front"] == "&lt;a&gt;"

    def test_csv_uses_comma(self, tmp_path):
        path = tmp_path / "notes.csv"
        path.write_text("Front,Back\n", encoding="utf-8")
        cards = import_txt(path)
        assert cards[0]["front"] == "Front"
        assert cards[0]["back"] == "Back"


class TestApkgImport:
    def test_imports_notes_media_and_deck(self, tmp_path):
        apkg = _make_apkg(tmp_path)
        media_dir = tmp_path / "media"
        cards = import_apkg(apkg, media_dir, default_deck="Imported")
        assert len(cards) == 1
        assert cards[0]["deck"] == "Blind 75"
        assert cards[0]["front"] == "Two Sum"
        assert cards[0]["tags"] == ["array"]
        assert 'src="diagram.png"' in cards[0]["back"]
        assert (media_dir / "diagram.png").read_bytes() == b"PNGDATA"

    def test_anki21b_sqlite_passthrough(self, tmp_path):
        db_path = tmp_path / "collection.anki2"
        _write_collection(db_path)
        apkg = tmp_path / "deck.apkg"
        with zipfile.ZipFile(apkg, "w") as zf:
            zf.writestr("collection.anki21b", db_path.read_bytes())
            zf.writestr("media", "{}")
        cards = import_apkg(apkg, tmp_path / "media")
        assert len(cards) == 1
        assert cards[0]["front"] == "Two Sum"

    def test_zstd_collection_anki21b(self, tmp_path, monkeypatch):
        db_path = tmp_path / "collection.anki2"
        _write_collection(db_path)
        db_bytes = db_path.read_bytes()

        class _Reader:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return db_bytes

        class _Zstd:
            class ZstdDecompressor:
                def stream_reader(self, _bio):
                    return _Reader()

        monkeypatch.setitem(__import__("sys").modules, "zstandard", _Zstd)
        apkg = tmp_path / "deck.apkg"
        with zipfile.ZipFile(apkg, "w") as zf:
            zf.writestr("collection.anki21b", b"not-sqlite" + db_bytes[:8])
            zf.writestr("media", "{}")
        cards = import_apkg(apkg, tmp_path / "media")
        assert len(cards) == 1
        assert cards[0]["front"] == "Two Sum"

    def test_zstd_missing_package_message(self, tmp_path, monkeypatch):
        monkeypatch.setitem(__import__("sys").modules, "zstandard", None)
        apkg = tmp_path / "deck.apkg"
        with zipfile.ZipFile(apkg, "w") as zf:
            zf.writestr("collection.anki21b", b"not-a-sqlite-database")
        with pytest.raises(AnkiImportError, match="zstandard"):
            import_apkg(apkg, tmp_path / "media")

    def test_missing_collection_raises_legacy_hint(self, tmp_path):
        apkg = tmp_path / "empty.apkg"
        with zipfile.ZipFile(apkg, "w") as zf:
            zf.writestr("readme.txt", "no db")
        with pytest.raises(AnkiImportError, match="legacy"):
            import_apkg(apkg, tmp_path / "media")

    def test_dispatch_txt_and_store_round_trip(self, tmp_path, isolated_app_dir):
        from api import leetcode_store

        path = tmp_path / "notes.txt"
        path.write_text("Climbing Stairs\tDP\n", encoding="utf-8")
        imported = import_anki_file(path, leetcode_store.media_dir(), default_deck="DP")
        created = leetcode_store.add_cards(imported)
        assert len(created) == 1
        assert created[0]["deck"] == "DP"
        assert leetcode_store.due_cards("DP")[0]["front"] == "Climbing Stairs"

    def test_dispatch_rejects_unknown_type(self, tmp_path):
        path = tmp_path / "notes.json"
        path.write_text("{}", encoding="utf-8")
        with pytest.raises(AnkiImportError, match="Unsupported"):
            import_anki_file(path, tmp_path / "media")
