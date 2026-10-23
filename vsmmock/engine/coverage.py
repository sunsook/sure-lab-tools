"""Measure the same CT cases as the runner with gcc/gcovr branch data."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .cparse import functions
from .criteria import read_criteria
from .result import Finding, Result, mock_limit
from .runner import TOOL, _enum_names, _test_source
from .testdef import InputBroken, read_definitions

UNMEASURED = "N/A(목업 미측정)"
NO_GCC = "로컬 Windows 는 zig 에 gcov 런타임이 없어 측정 불가 — CI 에서 측정"


def available() -> bool:
    return os.environ.get("VSMMOCK_FORCE_NO_GCC") != "1" and bool(shutil.which("gcc") and shutil.which("gcovr"))


def deferral(repo: Path) -> dict[str, str] | None:
    value = read_criteria(repo).coverage or ""
    match = re.fullmatch(r"deferred-to-deploy\s*·\s*결정자=([^·]+)\s*·\s*사유=(.+)", value)
    return {"by": match[1].strip(), "why": match[2].strip()} if match else None


def _signatures(repo: Path) -> dict:
    signatures = {}
    for item in functions(repo):
        match = re.search(r"\b" + re.escape(item["name"]) + r"\s*\((.*)\)", item["signature"])
        raw = [] if not match or match[1].strip() == "void" else match[1].split(",")
        params = [re.search(r"([A-Za-z_]\w*)\s*$", part.strip()).group(1) for part in raw]
        signatures[item["name"]] = {"where": item["where"], "params": params,
                                     "unsupported": any("*" in part or "[" in part or
                                                        re.search(r"\b(struct|union)\b", part) for part in raw)}
    return signatures


def measure(repo: Path, *, face: str = "cli") -> Result:
    repo = Path(repo)
    criteria = read_criteria(repo)
    missing = [key for key, absent in (("branch_target", criteria.branch_target is None),
                                         ("branch_scope", not criteria.branch_scope)) if absent]
    if missing:
        result = Result(check="ct.coverage", status="ERROR", reason="CRITERIA_MISSING", tool=TOOL)
        result.findings.append(Finding(id="CT-COVERAGE-CRITERIA", where="docs/기준설계.md",
            expected=" · ".join(f"{key}: …" for key in missing), actual="기준 없음",
            fix_hint="분기 목표와 대상 소스를 기준설계에 정하세요.", basis="docs/기준설계.md",
            back_to="요구사항"))
        return result
    if not available():
        return mock_limit(repo, check="ct.coverage", tool=TOOL, face=face,
                          command="ct coverage" if face == "cli" else "get_coverage",
                          where="branch_scope", detail=NO_GCC)
    result = Result(check="ct.coverage", status="PASS", tool=TOOL)
    result.metrics = {"statement": UNMEASURED, "mcdc": UNMEASURED}
    try:
        scope = Path(criteria.branch_scope)
        if scope.is_absolute() or ".." in scope.parts or not (repo / scope).is_file():
            raise ValueError("branch_scope 소스 경로가 올바르지 않습니다")
        definitions = read_definitions(repo)
        c_tests = sorted((repo / "tests").glob("TC-*.c"))
        source = _test_source(repo, definitions, c_tests, _signatures(repo), _enum_names(repo))
        with tempfile.TemporaryDirectory(prefix="vsmmock_coverage_") as directory:
            work = Path(directory)
            (work / "src").mkdir()
            (work / "tests").mkdir()
            for path in (repo / "src").glob("*.c"):
                shutil.copyfile(path, work / "src" / path.name)
            for path in c_tests:
                shutil.copyfile(path, work / "tests" / path.name)
            runner = work / "runner.c"
            runner.write_text(source, encoding="utf-8")
            binary = work / "runner"
            sources = [str(path) for path in sorted((work / "src").glob("*.c")) if path.name != "main.c"]
            command = ["gcc", "--coverage", "-std=c11", "-I", str(repo / "include"),
                       *sources, *(str(work / "tests" / path.name) for path in c_tests),
                       str(runner), "-o", str(binary)]
            compiled = subprocess.run(command, cwd=work, capture_output=True, text=True,
                                      encoding="utf-8", timeout=120)
            if compiled.returncode:
                raise RuntimeError(f"gcc: {compiled.stderr[:1000]}")
            executed = subprocess.run([str(binary)], cwd=work, capture_output=True,
                                      text=True, encoding="utf-8", timeout=30)
            if executed.returncode:
                raise RuntimeError(f"runner: {executed.stderr[:1000]}")
            report = work / "coverage.json"
            collected = subprocess.run(["gcovr", "--root", str(work), "--json", "-o", str(report)],
                                       cwd=work, capture_output=True, text=True,
                                       encoding="utf-8", timeout=120)
            if collected.returncode:
                raise RuntimeError(f"gcovr: {collected.stderr[:1000]}")
            data = json.loads(report.read_text(encoding="utf-8"))
        scoped = [item for item in data.get("files", [])
                  if Path(item["file"]).as_posix().endswith(scope.as_posix())]
        if len(scoped) != 1:
            raise ValueError(f"branch_scope gcovr 결과가 하나가 아닙니다: {scope}")
        branches = [(line["line_number"], branch)
                    for line in scoped[0].get("lines", []) for branch in line.get("branches", [])]
        if not branches:
            raise ValueError(f"branch_scope 분기 데이터가 없습니다: {scope}")
        covered = sum(branch.get("count", 0) > 0 for _, branch in branches)
        total = len(branches)
        percent = round(100 * covered / total, 2)
        result.metrics.update(branch_percent=percent, branch_covered=covered,
                              branch_total=total, branch_target=criteria.branch_target)
        for line, branch in branches:
            if branch.get("count", 0) > 0:
                continue
            side = "T" if branch.get("branchno", 0) % 2 == 0 else "F"
            where = f"{scope.as_posix()}:{line}"
            result.findings.append(Finding(id=f"CT-BRANCH-{line}-{branch.get('branchno', 0)}",
                                           where=where, expected="분기 실행", actual=f"미실행 ({side})",
                                           fix_hint="해당 분기를 실행하는 시험을 추가하세요.",
                                           basis="docs/기준설계.md branch_scope · branch_target",
                                           back_to="시험 추가"))
        if percent < criteria.branch_target:
            result.status = "FAIL"
        return result
    except (OSError, ValueError, InputBroken, RuntimeError, subprocess.TimeoutExpired) as error:
        result.status, result.reason, result.detail = "ERROR", "BUILD_FAILED", str(error)
        return result
