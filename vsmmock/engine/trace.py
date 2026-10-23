"""Requirement to test traceability and main branch change inventory."""

import json
import re
import subprocess
from pathlib import Path

from .requirements import base_branch, parse_requirements, read_requirements
from .result import Finding, Result
from .testdef import InputBroken, read_definitions

TOOL = {"name": "ADS", "mimics": "ADS trace_check ID chain"}
MARKER = re.compile(r"@req\s+(SR-\d{3})\b")


def _finding(where: str, actual: str, back_to: str = "시험 연결") -> Finding:
    return Finding(id=f"ADS-{where}", where=where, expected="기존 요구사항 SR-xxx 연결",
                   actual=actual, fix_hint="시험의 요구사항 ID를 확인하고 연결하세요.",
                   basis="docs/요구사항.md · 시험 정의 req 또는 TC 첫 줄 @req", back_to=back_to)


def _tc_tests(repo: Path) -> tuple[list[dict], list[Finding], list[Finding]]:
    tests, broken, gaps = [], [], []
    for path in sorted((repo / "tests").glob("TC-*.c")):
        where = path.relative_to(repo).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        first = lines[0] if lines else ""
        marker = MARKER.search(first)
        if marker:
            tests.append({"id": path.stem, "req": marker[1], "where": f"{where}:1", "kind": "tc"})
        elif "@req" in first:
            broken.append(_finding(f"{where}:1", first.strip(), "시험 연결"))
        else:
            gaps.append(_finding(f"{where}:1", "@req 표시 없음"))
    return tests, broken, gaps


def _changed_tests(repo: Path) -> list[str]:
    branch = base_branch(repo)
    if branch is None:
        return []
    run = subprocess.run(["git", "ls-tree", "-r", "--name-only", branch, "--", "ct", "tests"],
                         cwd=repo, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8")
    if run.returncode != 0:
        raise ValueError(run.stderr.strip())
    old_paths = set(run.stdout.splitlines())
    now_paths = {p.relative_to(repo).as_posix() for folder, pattern in (("ct", "*.json"), ("tests", "TC-*.c"))
                 for p in (repo / folder).glob(pattern)}
    changes = set()
    for relative in sorted(old_paths | now_paths):
        if not (relative.startswith("ct/") and relative.endswith(".json") or
                relative.startswith("tests/TC-") and relative.endswith(".c")):
            continue
        old = subprocess.run(["git", "show", f"{branch}:{relative}"], cwd=repo,
                             capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8")
        old_text = old.stdout if old.returncode == 0 else None
        path = repo / relative
        new_text = path.read_text(encoding="utf-8") if path.exists() else None
        if old_text != new_text:
            if relative.startswith("ct/"):
                source = new_text if new_text is not None else old_text
                try:
                    identifier = json.loads(source)["id"]
                except (ValueError, KeyError, TypeError):
                    identifier = path.stem
            else:
                identifier = path.stem
            changes.add(identifier)
    return sorted(changes)


def _changed_requirements(repo: Path, requirements: dict) -> list[str]:
    branch = base_branch(repo)
    if branch is None:
        return []
    run = subprocess.run(["git", "show", f"{branch}:docs/요구사항.md"], cwd=repo,
                         capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8")
    if run.returncode != 0:
        return []
    before = parse_requirements(run.stdout)
    return sorted(sr for sr in before.keys() | requirements.keys()
                  if (before[sr].text if sr in before else None) !=
                     (requirements[sr].text if sr in requirements else None))


def trace(repo: Path) -> Result:
    """Check both directions of SR links; report unlinked SRs without failing."""
    repo = Path(repo)
    result = Result(check="ads.trace", status="PASS", tool=TOOL)
    requirements = read_requirements(repo)
    tc, broken, gaps = _tc_tests(repo)
    try:
        definitions = read_definitions(repo)
    except InputBroken as error:
        result.status, result.reason = "ERROR", "INPUT_BROKEN"
        result.findings.append(_finding(error.where, str(error)))
        return result
    tests = [{"id": d.id, "req": d.req, "where": d.where, "kind": "ct"} for d in definitions] + tc
    links = []
    for sr in sorted(requirements):
        linked = sorted(t["id"] for t in tests if t["req"] == sr)
        links.append({"sr": sr, "srs": f"SRS_{sr[3:]}_01", "tests": linked})
    orphans = sorted({t["id"] for t in tests if t["req"] not in requirements} |
                     {Path(finding.where.split(":", 1)[0]).stem for finding in gaps})
    for test in tests:
        if test["req"] not in requirements:
            gaps.append(_finding(test["where"], f"요구사항에 없는 {test['req']}"))
    result.metrics = {
        "requirements": len(requirements), "linked": sum(bool(link["tests"]) for link in links),
        "missing": len(gaps), "links": links,
        "unlinked_requirements": [link["sr"] for link in links if not link["tests"]],
        "orphan_tests": orphans, "changed_requirements": _changed_requirements(repo, requirements),
        "changed_tests": _changed_tests(repo),
    }
    if broken:
        result.status, result.reason, result.findings = "ERROR", "INPUT_BROKEN", broken
    elif gaps:
        result.status, result.findings = "FAIL", gaps
    return result
