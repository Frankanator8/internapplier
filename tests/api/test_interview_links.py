import pytest

from api.interview_links import (
    QuestionGroup,
    default_groups,
    merge_groups,
    new_group_id,
    parse_entries,
    serialize_groups,
    unlink_question,
)


class TestNewGroupId:
    def test_returns_hex_string(self):
        gid = new_group_id()
        assert isinstance(gid, str) and len(gid) == 32
        int(gid, 16)  # parses as hex


class TestParseEntries:
    def test_none_returns_empty(self):
        assert parse_entries(None) == []

    def test_standalone_entries(self):
        out = parse_entries([
            {"question": "Q1", "answer": "A1"},
            {"question": "Q2", "answer": "A2"},
        ])
        assert len(out) == 2
        assert all(g.group_id is None for g in out)

    def test_grouped_entries_combine(self):
        out = parse_entries([
            {"question": "Q1", "answer": "A1", "group_id": "g1"},
            {"question": "Q2", "answer": "", "group_id": "g1"},
        ])
        assert len(out) == 1
        assert out[0].questions == ["Q1", "Q2"]
        assert out[0].answer == "A1"
        assert out[0].group_id == "g1"

    def test_single_member_group_loses_gid(self):
        out = parse_entries([
            {"question": "Q1", "answer": "A1", "group_id": "g1"},
        ])
        assert out[0].group_id is None

    def test_first_non_empty_answer_wins(self):
        out = parse_entries([
            {"question": "Q1", "answer": "", "group_id": "g1"},
            {"question": "Q2", "answer": "later", "group_id": "g1"},
        ])
        assert out[0].answer == "later"

    def test_skips_non_dict_entries(self):
        out = parse_entries([{"question": "Q"}, "garbage", None])
        assert len(out) == 1


class TestSerializeGroups:
    def test_standalone_group_omits_gid(self):
        out = serialize_groups([QuestionGroup(None, ["Q"], "A")])
        assert out == [{"question": "Q", "answer": "A"}]

    def test_grouped_emits_gid_per_question(self):
        out = serialize_groups([QuestionGroup("g", ["Q1", "Q2"], "A")])
        assert all(e["group_id"] == "g" for e in out)
        assert [e["question"] for e in out] == ["Q1", "Q2"]

    def test_drops_empty_question_and_answer(self):
        out = serialize_groups([QuestionGroup(None, [""], "")])
        assert out == []


class TestMergeGroups:
    def test_same_index_returns_unchanged(self):
        groups = [QuestionGroup(None, ["Q"], "A")]
        assert merge_groups(groups, 0, 0) == groups

    def test_combines_and_picks_smaller_anchor(self):
        groups = [
            QuestionGroup(None, ["Q1"], "A1"),
            QuestionGroup(None, ["Q2"], "A2"),
        ]
        out = merge_groups(groups, source_idx=1, target_idx=0)
        # Anchored at 0; questions in visual order (target first since anchor=target)
        assert len(out) == 1
        assert out[0].questions == ["Q1", "Q2"]
        assert out[0].answer == "A2"  # source A2 wins auto (non-empty)
        assert out[0].group_id  # new id minted

    def test_answer_choice_source(self):
        groups = [
            QuestionGroup(None, ["Q1"], "A1"),
            QuestionGroup(None, ["Q2"], "A2"),
        ]
        out = merge_groups(groups, 0, 1, answer_choice="source")
        assert out[0].answer == "A1"

    def test_answer_choice_target(self):
        groups = [
            QuestionGroup(None, ["Q1"], "A1"),
            QuestionGroup(None, ["Q2"], "A2"),
        ]
        out = merge_groups(groups, 0, 1, answer_choice="target")
        assert out[0].answer == "A2"

    def test_reuses_existing_gid(self):
        groups = [
            QuestionGroup("existing", ["Q1"], "A1"),
            QuestionGroup(None, ["Q2"], "A2"),
        ]
        out = merge_groups(groups, 0, 1)
        assert out[0].group_id == "existing"

    def test_out_of_range_raises(self):
        with pytest.raises(IndexError):
            merge_groups([], 0, 1)


class TestUnlinkQuestion:
    def test_pops_into_new_standalone(self):
        groups = [QuestionGroup("g", ["Q1", "Q2"], "A")]
        out = unlink_question(groups, 0, 0)
        # Original loses one; new standalone appended
        assert len(out) == 2
        assert out[0].questions == ["Q2"]
        assert out[0].group_id is None  # reduced to single member
        assert out[1].questions == ["Q1"]
        assert out[1].group_id is None
        assert out[1].answer == "A"

    def test_keeps_gid_when_two_remain(self):
        groups = [QuestionGroup("g", ["Q1", "Q2", "Q3"], "A")]
        out = unlink_question(groups, 0, 1)
        assert out[0].questions == ["Q1", "Q3"]
        assert out[0].group_id == "g"

    def test_single_member_no_op(self):
        groups = [QuestionGroup(None, ["Q"], "A")]
        out = unlink_question(groups, 0, 0)
        assert out == groups

    def test_out_of_range(self):
        with pytest.raises(IndexError):
            unlink_question([], 0, 0)


class TestDefaultGroups:
    def test_each_is_standalone(self):
        groups = default_groups()
        assert all(g.group_id is None and len(g.questions) == 1 for g in groups)
        assert len(groups) > 0


class TestParseSerializeRoundTrip:
    def test_round_trip_standalone(self):
        entries = [{"question": "Q1", "answer": "A1"}]
        assert serialize_groups(parse_entries(entries)) == entries

    def test_round_trip_grouped(self):
        entries = [
            {"question": "Q1", "answer": "A1", "group_id": "g"},
            {"question": "Q2", "answer": "", "group_id": "g"},
        ]
        out = serialize_groups(parse_entries(entries))
        # Both serialized with same gid, shared answer
        assert {e["group_id"] for e in out} == {"g"}
        assert all(e["answer"] == "A1" for e in out)
