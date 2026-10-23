"""Parse only backtick-enclosed machine-readable criteria."""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .requirements import boundaries, read_requirements
from .result import Finding, Result
from .tests_index import read_tests

ACTIONS = ("block", "fix", "report")
CHOICES = {  # 정책 키의 허용 값 — ADR-015 · ADR-016
    "misra_mandatory": ACTIONS, "misra_required": ACTIONS, "misra_advisory": ACTIONS,
    "misra_deviation": ("allow", "deny"), "coverage_exception": ("allow", "deny"),
}


@dataclass
class Criteria:
    requirements: str | None = None
    required_tests: dict[str, list[int]] = field(default_factory=dict)
    fixed_inputs: str | None = None
    misra_rules: list[str] = field(default_factory=list)
    misra_max: int | None = None
    misra_mandatory: str | None = None
    misra_required: str | None = None
    misra_advisory: str | None = None
    misra_deviation: str | None = None
    branch_target: int | None = None
    branch_scope: str | None = None
    coverage: str | None = None
    coverage_exception: str | None = None
    expected: dict[str, str] = field(default_factory=dict)


def parse_criteria(text: str) -> Criteria:
    criteria = Criteria()
    for line in text.splitlines():
        for key, raw in re.findall(r"`([a-z_]+):\s*([^`]+)`", line):
            value = raw.strip()
            if key == "required_tests":
                match = re.fullmatch(r"(SR-\d{3})\[([\d,\s]+)\]", value)
                if not match:
                    raise ValueError(f"잘못된 required_tests: {value}")
                criteria.required_tests[match[1]] = [int(item) for item in match[2].split(",")]
            elif key == "expected":
                label, expected = value.split("=", 1)
                criteria.expected[label.strip()] = expected.strip()
            elif key == "misra_rules":
                criteria.misra_rules = [part.strip() for part in value.split(",")]
            elif key in ("misra_max", "branch_target"):
                setattr(criteria, key, int(value))
            elif key in CHOICES:
                if value not in CHOICES[key]:
                    raise ValueError(f"잘못된 {key}: {value} — {' · '.join(CHOICES[key])} 중 하나로 적으세요")
                setattr(criteria, key, value)
            elif hasattr(criteria, key):
                setattr(criteria, key, value)
    return criteria


def read_criteria(repo: Path, missing_ok: bool = False) -> Criteria:
    """missing_ok — 에이전틱 생성 경로만: 파일이 없으면 빈 기준으로 읽어 질문(NEEDS_CRITERIA)으로 돌린다."""
    path = repo / "docs/기준설계.md"
    if not path.is_file():
        if missing_ok:
            return Criteria()
        raise FileNotFoundError("docs/기준설계.md 가 없습니다 — 실습 2-④ 에서 만듭니다")
    return parse_criteria(path.read_text(encoding="utf-8"))


def check_criteria(repo: Path) -> Result:
    """Compare human criteria, requirement boundaries, and test presence."""
    tool = {"name": "DVERA", "mimics": "dvera-plugin v0.1.4 ct_get_test_results"}
    try:
        criteria = read_criteria(repo)
    except FileNotFoundError as error:
        return Result(check="ct.check-criteria", status="ERROR", reason="INPUT_BROKEN",
                      detail=str(error), tool=tool)
    requirements = read_requirements(repo, criteria.requirements or "docs/요구사항.md")
    result = Result(check="ct.check-criteria", status="PASS", tool=tool)
    for sr, values in criteria.required_tests.items():
        requirement = requirements.get(sr)
        boundary = boundaries(requirement.text) if requirement else []
        numbers = {number for number, _ in boundary}
        basis = f"{sr} (docs/요구사항.md:{requirement.line}) · 기준설계 required_tests" if requirement else f"{sr} · 기준설계 required_tests"
        if not numbers or not numbers.intersection(values):
            result.findings.append(Finding(
                id=f"CT-CRITERIA-{sr}", where=f"docs/기준설계.md:{sr}",
                expected=f"요구사항의 새 경계 {', '.join(map(str, sorted(numbers))) or '확인 불가'}",
                actual=f"현재 기준 {', '.join(map(str, values))}",
                fix_hint="요구사항 경계에 맞는 기준 시험 입력을 사람이 정해야 합니다.",
                basis=basis, back_to="요구사항"))
    if result.findings:
        result.status = "ERROR"
        result.reason = "CRITERIA_MISSING"
        return result

    existing = {(item.req, item.value) for item in read_tests(repo)}
    for sr, values in criteria.required_tests.items():
        requirement = requirements[sr]
        for value in values:
            if (sr, value) not in existing:
                result.findings.append(Finding(
                    id=f"CT-{sr}-{value}", where=f"{sr}[{value}]",
                    expected=f"{sr} 입력 {value} 시험", actual="연결된 시험 없음",
                    fix_hint="이 입력의 시험을 추가하세요.",
                    basis=f"{sr} (docs/요구사항.md:{requirement.line}) · 기준설계 required_tests",
                    back_to="시험 추가"))
    if result.findings:
        result.status = "FAIL"
    return result
