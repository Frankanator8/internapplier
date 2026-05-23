import pytest

from api.ai_provider import prompts as p


pytestmark = pytest.mark.usefixtures("isolated_app_dir")


def test_seed_creates_prompt_files(isolated_app_dir):
    assert (isolated_app_dir / "prompts" / "analyze_bullet.txt").exists()
    assert (isolated_app_dir / "prompts" / "grade_resume.txt").exists()


def test_load_prompt_strips_whitespace():
    text = p.load_prompt("analyze_bullet.txt")
    assert text == text.strip()
    assert text  # non-empty


def test_load_schema_returns_dict():
    schema = p.load_schema("grade_interview.schema.json")
    assert isinstance(schema, dict)


def test_save_prompt_round_trip():
    p.save_prompt("analyze_bullet.txt", "custom prompt")
    assert p.load_prompt("analyze_bullet.txt") == "custom prompt"


def test_default_prompt_reads_from_source_not_user_dir():
    # save_prompt writes to user dir; default_prompt should still return source
    p.save_prompt("analyze_bullet.txt", "user override")
    assert p.default_prompt("analyze_bullet.txt") != "user override"


def test_list_prompt_files_sorted_by_group():
    files = p.list_prompt_files()
    # Plain .txt files come before .schema.json which come before .tool.json
    txt_idx = max(i for i, n in enumerate(files) if n.endswith(".txt"))
    schema_idx = min((i for i, n in enumerate(files) if n.endswith(".schema.json")),
                     default=len(files))
    assert txt_idx < schema_idx


def test_resync_all_prompts_overwrites_user_edits():
    p.save_prompt("analyze_bullet.txt", "edited")
    p.resync_all_prompts()
    assert p.load_prompt("analyze_bullet.txt") != "edited"
