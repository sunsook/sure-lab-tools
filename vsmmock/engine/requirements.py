"""Read requirement rows and their numeric boundary clauses."""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Requirement:
    id: str
    text: str
    implementation: str
    line: int


@dataclass(frozen=True)
class Grade:
    name: str
    meaning: str
    condition: str
    line: int


def parse_requirements(text: str) -> dict[str, Requirement]:
    rows = {}
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"\|\s*(SR-\d{3})\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|", line)
        if match:
            rows[match[1]] = Requirement(match[1], match[2], match[3], number)
    return rows


def parse_grades(text: str) -> dict[str, Grade]:
    grades = {}
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r"\|\s*`?(NONE|LOW|MID|HIGH)`?\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|", line)
        if match:
            grades[match[1]] = Grade(match[1], match[2], match[3], number)
    return grades


def read_requirements(repo: Path, relative: str = "docs/요구사항.md") -> dict[str, Requirement]:
    return parse_requirements((repo / relative).read_text(encoding="utf-8"))


def read_grades(repo: Path, relative: str = "docs/요구사항.md") -> dict[str, Grade]:
    return parse_grades((repo / relative).read_text(encoding="utf-8"))


def boundaries(sentence: str) -> list[tuple[int, str]]:
    """Return numbers paired with their comparison direction, in sentence order."""
    cleaned = re.sub(r"\*|`", "", sentence)
    patterns = [
        (r"(\d+)\s*(?:km/h\s*)?(이상|초과|미만|이하)", lambda m: (int(m[1]), m[2])),
        (r"차속\s*(≥|>|≤|<)\s*(\d+)", lambda m: (int(m[2]), m[1])),
        (r"(\d+)\s*(<|≤)\s*차속", lambda m: (int(m[1]), ">" if m[2] == "<" else "≥")),
    ]
    found = []
    for pattern, convert in patterns:
        for match in re.finditer(pattern, cleaned):
            value = convert(match)
            if value not in found:
                found.append(value)
    return found


def _git(repo: Path, *args: str) -> str | None:
    run = subprocess.run(["git", *args], cwd=repo, capture_output=True,
                         text=True, encoding="utf-8")
    return run.stdout if run.returncode == 0 else None


def base_branch(repo: Path) -> str | None:
    for branch in (os.environ.get("VSMMOCK_BASE"), "origin/main", "main"):
        if branch and _git(repo, "rev-parse", "--verify", branch) is not None:
            return branch
    return None


def changed_requirements(repo: Path, relative: str = "docs/요구사항.md") -> list[str]:
    branch = base_branch(repo)
    if branch is None:
        return []
    old = _git(repo, "show", f"{branch}:{relative}")
    if old is None:
        return []
    before = parse_requirements(old)
    after = read_requirements(repo, relative)
    return sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
