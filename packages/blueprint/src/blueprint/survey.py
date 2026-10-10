"""The run survey: a template the agent fills after each run, and a check that every answer is there."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

SURVEY_FILE = Path(__file__).resolve().parent / "survey.toml"
_ROW = re.compile(r"^\|\s*(?P<id>[A-Z]\d+)\s*\|[^|]*\|\s*(?P<answer>[^|]*?)\s*\|\s*(?P<evidence>[^|]*?)\s*\|\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Question:
    """One survey question."""

    id: str
    section: str
    text: str


def load() -> tuple[list[Question], tuple[str, ...], dict[str, str]]:
    """`(questions, allowed answers, section intros)`."""
    data = tomllib.loads(SURVEY_FILE.read_text())
    questions = [Question(q["id"], s["name"], q["text"]) for s in data["section"] for q in s["questions"]]
    return questions, tuple(data["answers"]), {s["name"]: s["intro"] for s in data["section"]}


def template(repo_name: str, set_hash: str) -> str:
    """The empty survey, one table per section."""
    questions, answers, intros = load()
    out = [
        f"# Blueprint run survey: {repo_name}",
        "",
        f"Checkpoint set: `{set_hash}`. Answer every row with one of: {' · '.join(answers)}. "
        "Evidence is one line: a row id, a file, a quote. Anything worth a checkpoint goes in Lacks.",
        "",
    ]
    for section, intro in intros.items():
        out += [f"## {section}", "", intro, "", "| id | question | answer | evidence |", "|---|---|---|---|"]
        out += [f"| {q.id} | {q.text} |  |  |" for q in questions if q.section == section]
        out.append("")
    out += ["## Lacks", "", "One line each: `blueprint lacks: <what>` (also filed as a bead in the shelf).", ""]
    return "\n".join(out)


def problems(text: str) -> list[str]:
    """What is wrong with a filled survey: missing rows, answers outside the set, no evidence for a non-yes."""
    questions, answers, _ = load()
    rows = {m["id"]: (m["answer"].strip().lower(), m["evidence"].strip()) for m in _ROW.finditer(text)}
    found: list[str] = []
    for q in questions:
        if q.id not in rows:
            found.append(f"{q.id}: no row")
            continue
        answer, evidence = rows[q.id]
        if answer not in answers:
            found.append(f"{q.id}: answer {answer or '(empty)'!r} is not one of {', '.join(answers)}")
        elif answer != "yes" and not evidence:
            found.append(f"{q.id}: '{answer}' needs evidence")
    return found
