"""DVERA shaped adapter for CT discovery, generation, and execution."""

from pathlib import Path

from vsmmock.engine.cparse import functions
from vsmmock.engine.coverage import UNMEASURED, available, deferral, measure
from vsmmock.engine.generate import approve, specification, structure_specification
from vsmmock.engine.runner import run


def find_functions(repo: Path, query: str = "") -> dict:
    notices = []
    found = functions(Path(repo), notices=notices)
    return {"source": "MOCK", "functions": [item for item in found if query in item["name"]],
            "notices": notices}


def ai_generate_test(repo: Path, signatureHash: str, specs: list[str] | None = None,
                     approved_spec: str | None = None) -> dict:
    repo = Path(repo)
    notices = []
    target = next((item for item in functions(repo, notices=notices) if item["signatureHash"] == signatureHash), None)
    if target is None:
        return {"source": "MOCK", "status": "ERROR", "reason": "INPUT_BROKEN",
                "detail": "함수 서명 해시를 찾지 못했습니다.", "notices": notices}
    if specs is None:
        result = structure_specification(repo, target["name"], notices=notices)
        return {**result, "notices": [*notices, *result.get("notices", [])]}
    planned = specification(repo, target["name"], specs, notices=notices)
    if approved_spec is None:
        return {**planned, "notices": [*notices, *planned.get("notices", [])]}
    if planned["status"] != "NEEDS_APPROVAL" or approved_spec != planned["spec"]["id"]:
        return {"source": "MOCK", "status": "ERROR", "reason": "SPEC_STALE",
                "detail": "승인한 명세와 현재 요구사항·기준이 다릅니다.", "notices": notices}
    result = approve(repo, planned["spec"], specs)
    return {**result, "notices": [*notices, *result.get("notices", [])]}


def _results(repo: Path) -> dict:
    result = run(Path(repo))
    cases = result.metrics.get("cases", [])
    tests = [{"testName": case["testName"], "suiteName": case["suiteName"],
              "status": "Success" if case["passed"] else "Failure"} for case in cases]
    return {"source": "MOCK", "status": result.status, "reason": result.reason,
            "total": len(tests), "passed": sum(t["status"] == "Success" for t in tests),
            "failed": sum(t["status"] == "Failure" for t in tests), "tests": tests}


def execute_test(repo: Path) -> dict:
    result = _results(repo)
    return {**result, "testRunSuccess": result["status"] != "ERROR"}


def get_test_results(repo: Path) -> dict:
    return _results(repo)


def check_environment(repo: Path) -> dict:
    import ziglang
    return {"source": "MOCK", "compiler": "gcc" if available() else "ziglang cc",
            "coverage_tool": "gcovr" if available() else "gcovr (CI)",
            "ok": bool(ziglang.__file__)}


def get_coverage(repo: Path) -> dict:
    repo = Path(repo)
    result = measure(repo, face="mcp")
    deferred = deferral(repo)
    metrics = result.metrics
    answer = {"source": "MOCK", "status": result.status, "statement": UNMEASURED,
              "findings": [item.__dict__ for item in result.findings],
              "branch": (f"{metrics['branch_covered']}/{metrics['branch_total']}"
                         if "branch_total" in metrics else None),
              "mcdc": UNMEASURED,
              "uncovered": [{"where": item.where,
                             "side": "T" if "(T)" in item.actual else "F"}
                            for item in result.findings],
              "notices": result.notices}
    if result.reason:
        answer["reason"] = result.reason
    if result.detail:
        answer["detail"] = result.detail
    if deferred:
        answer["deferred"] = deferred
        if result.status == "FAIL":
            answer["status"] = "PASS"
            answer["notices"] = [*result.notices, {"kind": "COVERAGE_DEFERRED",
                "message": "분기 목표 미달을 배포 게이트로 미뤘습니다.", **deferred}]
    return answer
