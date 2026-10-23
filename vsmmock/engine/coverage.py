"""Measure the same CT cases as the runner with gcc/gcovr branch data."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .cparse import decision_sites, functions
from .criteria import Criteria, parse_criteria, read_criteria
from .requirements import _git, base_branch
from .result import Finding, Result, mock_limit
from .runner import TOOL, _enum_names, _test_source
from .testdef import InputBroken, read_definitions

UNMEASURED = "N/A(목업 미측정)"
NO_GCC = "로컬 Windows 는 zig 에 gcov 런타임이 없어 측정 불가 — CI 에서 측정"
CRITERIA = "docs/기준설계.md"
# 커버리지 입력 = 측정이 실제로 읽는 파일(ADR-017): 컴파일하는 src/*.c(main.c 제외 — 아래 measure) · -I include ·
# tests/TC-*.c · 시험 정의 ct/*.json 최상위(testdef.read_definitions — ct/retired/ 는 안 읽음) + 기준설계 커버리지 키
INPUTS = (":(glob)src/*.c", ":(exclude)src/main.c", ":(glob)include/**", ":(glob)tests/TC-*.c", ":(glob)ct/*.json")
COVERAGE_KEYS = ("branch_target", "branch_scope", "coverage", "coverage_exception")


def available() -> bool:
    return os.environ.get("VSMMOCK_FORCE_NO_GCC") != "1" and bool(shutil.which("gcc") and shutil.which("gcovr"))


def _record(criteria: Criteria) -> dict[str, str] | None:
    match = re.fullmatch(r"deferred-to-deploy\s*·\s*결정자=([^·]+)\s*·\s*사유=(.+)", criteria.coverage or "")
    return {"by": match[1].strip(), "why": match[2].strip()} if match else None


def _input_files(repo: Path) -> list[str]:
    found = {path for pattern in ("src/*.c", "tests/TC-*.c", "ct/*.json") for path in repo.glob(pattern)}
    found |= {path for path in (repo / "include").rglob("*") if path.is_file()}
    return sorted(relative for relative in (path.relative_to(repo).as_posix() for path in found)
                  if relative != "src/main.c")


def _unchanged(repo: Path) -> tuple[str, dict[str, str]]:
    """base 의 merge-base 대비 커버리지 입력이 그대로인가 — "unchanged" | "changed" | "no_base"(ADR-017).

    git 단계가 하나라도 실패하면 no_base — 「변경 없음」으로 바꾸지 않는다(호출부가 MOCK_LIMIT 으로 낸다).
    """
    branch = base_branch(repo)
    if branch is None:
        return "no_base", {"why": "기준 브랜치(VSMMOCK_BASE · origin/main · main)를 찾지 못함"}
    merged = _git(repo, "merge-base", "HEAD", branch)
    if not merged:
        return "no_base", {"why": f"기준 브랜치 {branch} 와 공통 조상을 찾지 못함"}
    sha = merged.strip()
    info = {"base": f"{branch}@{sha[:7]}"}
    diff = _git(repo, "diff", "--name-only", "-z", sha, "--", *INPUTS)
    if diff is None:
        return "no_base", {**info, "why": "기준 브랜치와 diff 실패"}
    if diff.strip("\0"):
        return "changed", info
    tree = _git(repo, "ls-tree", "-r", "-z", "--name-only", sha, "--", "src", "include", "tests", "ct", CRITERIA)
    if tree is None:
        return "no_base", {**info, "why": "기준 브랜치 파일 목록 실패"}
    tracked = set(tree.split("\0"))
    if any(path not in tracked for path in _input_files(repo)):  # git 무시 파일도 측정은 읽는다
        return "changed", info
    before = Criteria()
    if CRITERIA in tracked:
        text = _git(repo, "show", f"{sha}:{CRITERIA}")
        if text is None:
            return "no_base", {**info, "why": "기준 브랜치의 기준설계를 읽지 못함"}
        before = parse_criteria(text)
    now = read_criteria(repo, missing_ok=True)
    if any(getattr(before, key) != getattr(now, key) for key in COVERAGE_KEYS):
        return "changed", info
    return "unchanged", info


def pre_check(repo: Path, *, face: str = "cli") -> dict:
    """ct pre-check — 커버리지 기준(branch_target · branch_scope · coverage_exception) 중 빠진 칸만 묻는다(ADR-016)."""
    repo = Path(repo).resolve()
    criteria = read_criteria(repo, missing_ok=True)
    notices: list[dict] = []
    sites = decision_sites(repo, notices=notices)
    local = available()
    record = _record(criteria)
    current = {"branch_sites": sites, "local_measure": local, "deferral": record}
    summary = " · ".join(f"{path} {count}곳" for path, count in sites.items()) or "없음"
    where_measured = ("이 환경은 gcc · gcovr 로 잴 수 있습니다" if local
                      else "이 PC 는 gcc 가 없어 측정하지 못합니다")
    questions = []
    if criteria.branch_target is None:
        questions.append({"sr": "CT", "missing": "분기 커버리지 목표(%)",
                          "why": f"분기 목표는 사람이 정합니다 — 목업이 AST 로 센 판정 지점: {summary}(지점마다 참 · 거짓 "
                                 f"두 분기 · gcov 의 분기 정의와 다를 수 있음). 분기 커버리지는 CI(ubuntu · gcc · gcovr)에서 "
                                 f"잽니다 — {where_measured}.",
                          "options": [], "write_to": f"{CRITERIA} · branch_target: <정수>"})
    if not criteria.branch_scope:
        questions.append({"sr": "CT", "missing": "분기 커버리지 대상 소스",
                          "why": "분기 목표를 걸 소스를 사람이 고릅니다 — 목업이 잴 수 있는 소스는 supported 입니다"
                                 "(main.c 는 측정에서 빠짐).",
                          "options": [], "write_to": f"{CRITERIA} · branch_scope: <소스 경로>",
                          "supported": [path.relative_to(repo).as_posix() for path in sorted((repo / "src").glob("*.c"))
                                        if path.name != "main.c"]})
    if criteria.coverage_exception is None:
        found = f"있음(결정자={record['by']} · 사유={record['why']})" if record else "없음"
        questions.append({"sr": "CT", "missing": "커버리지 미달 예외 정책",
                          "why": "분기 목표 미달 때 결정자 · 사유를 남긴 미루기 기록(`coverage: deferred-to-deploy · 결정자=… · "
                                 "사유=…`)을 PR · 개발 단계에서 인정할지 정합니다 — allow 면 인정(막지 않음) · deny 면 미달 = "
                                 f"FAIL. 배포 게이트 ct coverage 는 이 값과 상관없이 목표로 판정합니다. 지금 미루기 기록: {found}.",
                          "options": [], "supported": ["allow", "deny"],
                          "write_to": f"{CRITERIA} · coverage_exception: <allow|deny>"})
    if not questions:
        return {"source": "MOCK", "status": "PASS", "current": current, "notices": notices,
                "criteria": {key: getattr(criteria, key) for key in ("branch_target", "branch_scope", "coverage_exception")},
                "next": "시험 기준(required_tests)은 `ct spec <함수> --specs SR-…` 이 SR 마다 묻습니다."}
    answer = {"source": "MOCK", "status": "NEEDS_CRITERIA", "questions": questions, "current": current,
              "notices": notices}
    if not (repo / CRITERIA).is_file():
        answer["detail"] = (f"{CRITERIA} 가 없습니다 — 질문의 write_to 대로 이 파일을 만들어 답을 적은 뒤 "
                            "다시 실행하세요(실습 2-④).")
    return answer


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
        state, info = _unchanged(repo)
        if state == "unchanged":  # 이 PR 이 바꾼 커버리지 입력이 없다 — 막지 않는다(ADR-017)
            result = Result(check="ct.coverage", status="PASS", tool=TOOL)
            result.metrics = {"statement": UNMEASURED, "mcdc": UNMEASURED, "base": info["base"]}
            result.notices.append({"kind": "COVERAGE_UNCHANGED",
                                   "where": "src/*.c(main.c 제외) · include/ · tests/TC-*.c · ct/*.json · docs/기준설계.md 커버리지 줄",
                                   "message": f"[MOCK] 커버리지 입력이 {info['base']} 와 같습니다 — 이 변경이 바꾼 커버리지 "
                                              "입력이 없어 막지 않습니다 · 측정은 CI(gcc)에서 합니다."})
            return result
        detail = NO_GCC if state == "changed" else (
            f"{NO_GCC} · 기준 브랜치와 비교하지 못해 변경 여부를 볼 수 없습니다({info['why']})")
        return mock_limit(repo, check="ct.coverage", tool=TOOL, face=face,
                          command="ct coverage" if face == "cli" else "get_coverage",
                          where="branch_scope", detail=detail)
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
            compiled = subprocess.run(command, cwd=work, capture_output=True, stdin=subprocess.DEVNULL, text=True,
                                      encoding="utf-8", timeout=120)
            if compiled.returncode:
                raise RuntimeError(f"gcc: {compiled.stderr[:1000]}")
            executed = subprocess.run([str(binary)], cwd=work, capture_output=True, stdin=subprocess.DEVNULL,
                                      text=True, encoding="utf-8", timeout=30)
            if executed.returncode:
                raise RuntimeError(f"runner: {executed.stderr[:1000]}")
            report = work / "coverage.json"
            collected = subprocess.run(["gcovr", "--root", str(work), "--json", "-o", str(report)],
                                       cwd=work, capture_output=True, stdin=subprocess.DEVNULL, text=True,
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


def review(repo: Path, *, face: str = "mcp") -> Result:
    """PR · 개발 단계(get_coverage) — 측정 + 미루기 정책(ADR-016). 배포 게이트 measure 는 정책을 보지 않는다."""
    repo = Path(repo)
    result = measure(repo, face=face)
    criteria = read_criteria(repo)
    record = _record(criteria)
    if record is None:
        return result
    if criteria.coverage_exception == "allow":
        result.metrics["deferred"] = record
        if result.status == "FAIL":
            result.status = "PASS"
            result.notices.append({"kind": "COVERAGE_DEFERRED", "where": CRITERIA,
                                   "message": "분기 목표 미달을 배포 게이트로 미뤘습니다.", **record})
        return result
    message = (f"coverage_exception: deny — 미루기 기록(결정자={record['by']})을 인정하지 않습니다(PR · 개발 단계에서도 미달 = FAIL)."
               if criteria.coverage_exception == "deny" else
               f"coverage_exception 이 기준설계에 없어 미루기 기록(결정자={record['by']})을 쓰지 않았습니다 — "
               "정책은 ct pre-check 가 묻습니다.")
    result.notices.append({"kind": "CRITERIA_NOTE", "where": CRITERIA, "message": message})
    return result
