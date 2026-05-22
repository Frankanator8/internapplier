"""Pure-data helpers for linking interview questions that share an answer.

On-disk shape (in interview_template.json and applications[i].interview_questions):
    [{"question": str, "answer": str, "group_id": str | omitted}, ...]

Entries sharing a `group_id` form a linked group displayed as one card with
multiple question fields and a single shared answer. Entries without a
`group_id` (or whose group has only one member) are standalone.

This module has no UI dependencies and is safe to import anywhere.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


_DEFAULT_QUESTIONS: list[str] = [
    "Tell me about yourself",
    "Greatest strength / a time you took initiative / ownership",
    "Tell me about a time you faced a challenge and pushed through",
    "Tell me about a time you worked well on a team",
    "Walk me through a past project",
    "How did you teach someone something?",
    "Tell me about a conflict you handled",
    "What are your goals for the future?",
    "What gives you motivation?",
    "Tell me about a time you made a mistake",
    "Leadership — tell me about a time you led",
    "Tell me about a time you learned something new (tech)",
    "How would you address a bug in prod?",
    "Why this company / role?",
    "Greatest weakness",
    "Tell me about a time you received tough feedback",
    "A time you disagreed with a manager or teammate",
    "Why should we hire you?",
]


@dataclass
class QuestionGroup:
    group_id: str | None
    questions: list[str] = field(default_factory=list)
    answer: str = ""


def new_group_id() -> str:
    return uuid.uuid4().hex


def parse_entries(entries: list[dict] | None) -> list[QuestionGroup]:
    """Bucket flat on-disk entries into groups, preserving first-appearance order.

    Entries without a `group_id` are each their own (standalone) group. For
    grouped entries the first non-empty `answer` wins as the shared answer.
    Groups that end up with only one member have `group_id` set to None.
    """
    groups: list[QuestionGroup] = []
    by_gid: dict[str, QuestionGroup] = {}

    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        q = entry.get("question", "") or ""
        a = entry.get("answer", "") or ""
        gid = entry.get("group_id") or None

        if gid and gid in by_gid:
            g = by_gid[gid]
            g.questions.append(q)
            if not g.answer and a:
                g.answer = a
            continue

        group = QuestionGroup(group_id=gid, questions=[q], answer=a)
        groups.append(group)
        if gid:
            by_gid[gid] = group

    for g in groups:
        if g.group_id is not None and len(g.questions) < 2:
            g.group_id = None

    return groups


def serialize_groups(groups: list[QuestionGroup]) -> list[dict]:
    """Flatten groups back to the on-disk list.

    - Single-member groups omit `group_id`.
    - Entries where both question and answer are empty are dropped.
    """
    out: list[dict] = []
    for g in groups:
        effective_gid = g.group_id if len(g.questions) >= 2 else None
        for q in g.questions:
            q = q or ""
            a = g.answer or ""
            if not q.strip() and not a.strip():
                continue
            entry: dict = {"question": q, "answer": a}
            if effective_gid:
                entry["group_id"] = effective_gid
            out.append(entry)
    return out


def merge_groups(
    groups: list[QuestionGroup],
    source_idx: int,
    target_idx: int,
    answer_choice: str = "auto",
) -> list[QuestionGroup]:
    """Combine two groups into one anchored at min(source_idx, target_idx).

    `answer_choice`:
      - "source" — keep `groups[source_idx].answer`
      - "target" — keep `groups[target_idx].answer`
      - "auto"   — prefer source if non-empty, else target

    Group id rule: reuse an existing id (source preferred, then target);
    otherwise mint a new one.
    """
    if source_idx == target_idx:
        return list(groups)
    if not (0 <= source_idx < len(groups) and 0 <= target_idx < len(groups)):
        raise IndexError("source_idx or target_idx out of range")

    src = groups[source_idx]
    tgt = groups[target_idx]

    if answer_choice == "source":
        merged_answer = src.answer
    elif answer_choice == "target":
        merged_answer = tgt.answer
    else:
        merged_answer = src.answer if src.answer.strip() else tgt.answer

    gid = src.group_id or tgt.group_id or new_group_id()

    anchor_idx = min(source_idx, target_idx)
    other_idx = max(source_idx, target_idx)

    # Questions appear in original visual order (anchor's first, then other's).
    if anchor_idx == source_idx:
        merged_questions = list(src.questions) + list(tgt.questions)
    else:
        merged_questions = list(tgt.questions) + list(src.questions)

    merged = QuestionGroup(
        group_id=gid,
        questions=merged_questions,
        answer=merged_answer,
    )

    out = list(groups)
    out[anchor_idx] = merged
    del out[other_idx]
    return out


def unlink_question(
    groups: list[QuestionGroup],
    group_idx: int,
    question_idx: int,
) -> list[QuestionGroup]:
    """Pop a question out of a multi-member group into its own standalone group.

    The popped question becomes a new standalone `QuestionGroup` appended to
    the end, carrying the original group's answer (so the user can keep
    iterating without losing the text). If the source group is reduced to one
    member, its `group_id` is cleared.
    """
    if not (0 <= group_idx < len(groups)):
        raise IndexError("group_idx out of range")
    g = groups[group_idx]
    if not (0 <= question_idx < len(g.questions)):
        raise IndexError("question_idx out of range")
    if len(g.questions) < 2:
        # Nothing to unlink from a standalone group.
        return list(groups)

    popped_q = g.questions[question_idx]
    remaining = list(g.questions)
    del remaining[question_idx]

    updated_source = QuestionGroup(
        group_id=g.group_id if len(remaining) >= 2 else None,
        questions=remaining,
        answer=g.answer,
    )
    popped = QuestionGroup(
        group_id=None,
        questions=[popped_q],
        answer=g.answer,
    )

    out = list(groups)
    out[group_idx] = updated_source
    out.append(popped)
    return out


def default_groups() -> list[QuestionGroup]:
    """Initial set of standalone groups used when no template exists yet."""
    return [QuestionGroup(group_id=None, questions=[q], answer="") for q in _DEFAULT_QUESTIONS]
