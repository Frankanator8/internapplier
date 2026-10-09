"""Import Anki decks (.apkg) and tab-separated note exports (.txt)."""
from __future__ import annotations

import csv
import html
import io
import json
import logging
import os
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from .leetcode_store import DEFAULT_DECK

logger = logging.getLogger(__name__)

_SQLITE_MAGIC = b"SQLite format 3"
_IMG_SRC_RE = re.compile(r"""src\s*=\s*(['"])(.*?)\1""", re.IGNORECASE)

_SEPARATORS = {
    "tab": "\t",
    "comma": ",",
    "semicolon": ";",
    "colon": ":",
    "pipe": "|",
}

_LEGACY_HINT = (
    "This file uses Anki's newer package format, which could not be read. "
    "Re-export from Anki with 'Support older Anki versions' (legacy support) "
    "checked, then import that .apkg."
)


class AnkiImportError(Exception):
    """Raised when an Anki file cannot be parsed."""


def import_anki_file(
    path: str | Path,
    media_dir: Path,
    default_deck: str = "Imported",
) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise AnkiImportError(f"File not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".apkg", ".colpkg"}:
        return import_apkg(path, media_dir, default_deck)
    if suffix in {".txt", ".tsv", ".csv"}:
        return import_txt(path, default_deck)
    raise AnkiImportError(
        f"Unsupported file type '{suffix}'. Use an Anki .apkg deck or a .txt export."
    )


def import_txt(path: str | Path, default_deck: str = "Imported") -> list[dict]:
    path = Path(path)
    raw = path.read_text(encoding="utf-8-sig")
    lines = raw.splitlines()
    separator = "\t" if path.suffix.lower() != ".csv" else ","
    is_html = True
    deck_col: int | None = None
    tags_col: int | None = None
    body_start = 0
    for i, line in enumerate(lines):
        if not line.startswith("#"):
            body_start = i
            break
        key, _, value = line[1:].partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "separator":
            separator = _SEPARATORS.get(value.lower(), value)
        elif key == "html":
            is_html = value.lower() in {"true", "1", "yes"}
        elif key == "deck column":
            deck_col = _parse_column(value)
        elif key == "tags column":
            tags_col = _parse_column(value)
    else:
        body_start = len(lines)

    body = "\n".join(lines[body_start:])
    reader = csv.reader(
        io.StringIO(body),
        delimiter=separator,
        quotechar='"',
        doublequote=True,
    )
    cards: list[dict] = []
    for row in reader:
        if not row or all(not (cell or "").strip() for cell in row):
            continue
        deck = default_deck
        tags: list[str] = []
        content: list[str] = []
        for i, cell in enumerate(row):
            if deck_col is not None and i == deck_col:
                deck = (cell or "").strip() or default_deck
            elif tags_col is not None and i == tags_col:
                tags = [t for t in (cell or "").split() if t]
            else:
                content.append(cell or "")
        if not content:
            continue
        front, back = content[0], content[1] if len(content) > 1 else content[0]
        if not is_html:
            front = html.escape(front).replace("\n", "<br>")
            back = html.escape(back).replace("\n", "<br>")
        if not front.strip() and not back.strip():
            continue
        cards.append({
            "deck": deck.strip() or default_deck,
            "front": front,
            "back": back,
            "tags": tags,
        })
    return cards


def import_apkg(
    path: str | Path,
    media_dir: Path,
    default_deck: str = "Imported",
) -> list[dict]:
    path = Path(path)
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise AnkiImportError("Not a valid Anki .apkg file (it is not a zip archive).") from exc

    with zf:
        db_bytes = _extract_collection(zf)
        name_map = _extract_media(zf, media_dir)
        return _notes_from_sqlite(db_bytes, default_deck, name_map)


def _parse_column(value: str) -> int | None:
    try:
        idx = int(value.strip()) - 1
    except ValueError as exc:
        raise AnkiImportError(f"Invalid column index in Anki export header: {value}") from exc
    return idx if idx >= 0 else None


def _extract_collection(zf: zipfile.ZipFile) -> bytes:
    names = set(zf.namelist())
    if "collection.anki21" in names:
        return zf.read("collection.anki21")
    if "collection.anki2" in names:
        return zf.read("collection.anki2")
    if "collection.anki21b" in names:
        return _decompress_zstd(zf.read("collection.anki21b"))
    raise AnkiImportError(_LEGACY_HINT)


def _decompress_zstd(raw: bytes) -> bytes:
    if raw.startswith(_SQLITE_MAGIC):
        return raw
    try:
        import zstandard
    except ImportError as exc:
        raise AnkiImportError(
            "This deck uses Anki's newer compressed format. "
            "Install the zstandard package, or re-export from Anki with "
            "'Support older Anki versions' checked."
        ) from exc
    try:
        dctx = zstandard.ZstdDecompressor()
        with dctx.stream_reader(io.BytesIO(raw)) as reader:
            return reader.read()
    except Exception as exc:
        raise AnkiImportError(_LEGACY_HINT) from exc


def _extract_media(zf: zipfile.ZipFile, media_dir: Path) -> dict[str, str]:
    """Copy packaged media into ``media_dir``.

    Returns a map of original Anki filenames → filenames on disk.
    """
    names = set(zf.namelist())
    if "media" not in names:
        return {}
    try:
        mapping = json.loads(zf.read("media").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("anki_import: could not parse media manifest; skipping media")
        return {}
    if not isinstance(mapping, dict):
        return {}

    zip_to_name: dict[str, str] = {}
    for key, value in mapping.items():
        if _looks_like_index(key) and isinstance(value, str):
            zip_to_name[str(key)] = value
        elif _looks_like_index(value) and isinstance(key, str):
            zip_to_name[str(value)] = key

    media_dir.mkdir(parents=True, exist_ok=True)
    name_map: dict[str, str] = {}
    for zip_name, orig_name in zip_to_name.items():
        if zip_name not in names:
            continue
        safe_name = Path(orig_name).name or f"media-{zip_name}"
        dest_name = safe_name
        dest = media_dir / dest_name
        if dest.exists():
            dest_name = f"{uuid4().hex[:8]}_{safe_name}"
            dest = media_dir / dest_name
        dest.write_bytes(zf.read(zip_name))
        name_map[orig_name] = dest_name
        if orig_name != safe_name:
            name_map[safe_name] = dest_name
    return name_map


def _looks_like_index(value) -> bool:
    return isinstance(value, (int, str)) and str(value).isdigit()


def _notes_from_sqlite(
    db_bytes: bytes,
    default_deck: str,
    name_map: dict[str, str],
) -> list[dict]:
    if not db_bytes.startswith(_SQLITE_MAGIC):
        raise AnkiImportError(_LEGACY_HINT)

    fd, tmp_path = tempfile.mkstemp(suffix=".anki2")
    os.close(fd)
    try:
        Path(tmp_path).write_bytes(db_bytes)
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "notes" not in tables:
                raise AnkiImportError(_LEGACY_HINT)
            deck_names = _load_deck_names(conn, tables, default_deck)
            nid_to_did = _load_note_decks(conn, tables)
            cards: list[dict] = []
            seen: set[int] = set()
            for row in conn.execute("SELECT id, flds, tags FROM notes"):
                nid = row["id"]
                if nid in seen:
                    continue
                seen.add(nid)
                fields = (row["flds"] or "").split("\x1f")
                if not fields:
                    continue
                front = fields[0]
                back = fields[1] if len(fields) > 1 else fields[0]
                if not front.strip() and not back.strip():
                    continue
                front = _rewrite_media(front, name_map)
                back = _rewrite_media(back, name_map)
                did = nid_to_did.get(nid)
                deck = deck_names.get(did, default_deck) if did is not None else default_deck
                tags = [t for t in (row["tags"] or "").split() if t]
                cards.append({
                    "deck": deck or default_deck,
                    "front": front,
                    "back": back,
                    "tags": tags,
                })
            return cards
        finally:
            conn.close()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _load_deck_names(conn: sqlite3.Connection, tables: set[str], default_deck: str) -> dict:
    names: dict = {}
    if "col" not in tables:
        return names
    try:
        row = conn.execute("SELECT decks FROM col").fetchone()
    except sqlite3.Error:
        return names
    if not row:
        return names
    try:
        decks = json.loads(row[0] or "{}")
    except (TypeError, json.JSONDecodeError):
        return names
    if not isinstance(decks, dict):
        return names
    for did, info in decks.items():
        if not isinstance(info, dict):
            continue
        name = (info.get("name") or "").strip()
        if not name or name == "Default":
            name = default_deck or DEFAULT_DECK
        try:
            names[int(did)] = name
        except (TypeError, ValueError):
            names[did] = name
    return names


def _load_note_decks(conn: sqlite3.Connection, tables: set[str]) -> dict[int, int]:
    mapping: dict[int, int] = {}
    if "cards" not in tables:
        return mapping
    try:
        rows = conn.execute("SELECT nid, did FROM cards ORDER BY id").fetchall()
    except sqlite3.Error:
        return mapping
    for nid, did in rows:
        if nid not in mapping:
            mapping[int(nid)] = int(did)
    return mapping


def _rewrite_media(text: str, name_map: dict[str, str]) -> str:
    if not name_map:
        return text

    def repl(match: re.Match) -> str:
        quote, src = match.group(1), match.group(2)
        filename = Path(src).name
        new_name = name_map.get(src) or name_map.get(filename) or filename
        return f"src={quote}{new_name}{quote}"

    return _IMG_SRC_RE.sub(repl, text)
