"""Evidence backed inputs and expected values for generated CT definitions."""

import re
from dataclasses import dataclass
from pathlib import Path

from .criteria import read_criteria
from .requirements import boundaries, read_grades, read_requirements


@dataclass(frozen=True)
class NeedsCriteria(Exception):
    sr: str
    missing: str
    why: str
    options: list[int]
    write_to: str

    def as_dict(self) -> dict:
        return vars(self)


def _satisfies(condition: str, value: int) -> bool:
    condition = condition.replace("km/h", "").strip()
    if match := re.search(r"(\d+)\s*<\s*차속\s*<\s*(\d+)", condition):
        return int(match[1]) < value < int(match[2])
    if match := re.search(r"(\d+)\s*<\s*차속\s*≤\s*(\d+)", condition):
        return int(match[1]) < value <= int(match[2])
    if match := re.search(r"차속\s*(≥|>|≤|<)\s*(\d+)", condition):
        return {"≥": value >= int(match[2]), ">": value > int(match[2]),
                "≤": value <= int(match[2]), "<": value < int(match[2])}[match[1]]
    if match := re.fullmatch(r"차속\s*(\d+)", condition):
        return value == int(match[1])
    return False


BOOL_TYPES = ("_Bool", "bool")
INTEGER_TYPES = ("int", "int8_t", "int16_t", "int32_t", "uint8_t", "uint16_t", "uint32_t")


def _form(ctype: str) -> str:
    return "true|false" if ctype in BOOL_TYPES else "정수" if ctype in INTEGER_TYPES else "값"


def _literal(raw: str, ctype: str):
    """기준설계에 적힌 값을 매개변수 형으로 읽는다 — 읽지 못하면 None(승인 전에 다시 묻는다)."""
    if ctype in BOOL_TYPES:
        return {"true": True, "false": False}.get(raw)
    if ctype in INTEGER_TYPES:
        return int(raw) if re.fullmatch(r"-?\d+", raw) else None
    return raw


def fixed_inputs(repo: Path, function: str, parameters: list[str], sr: str,
                 boundary_input: str, types: dict[str, str] | None = None) -> dict:
    fixed = read_criteria(repo, missing_ok=True).fixed_inputs or ""
    types = types or {}
    result = {}
    match = re.fullmatch(r"(\w+)\(([^()]*)\)", fixed)
    if match and match[1] == function:
        for part in match[2].split(","):
            if "=" not in part:
                continue
            key, raw = (piece.strip() for piece in part.split("=", 1))
            if key not in parameters:
                continue
            ctype = types.get(key, "")
            value = _literal(raw, ctype)
            if value is None:
                raise NeedsCriteria(sr, f"{key} 고정 입력 값 {raw!r} 을 읽을 수 없습니다",
                                    f"{key} 은 {ctype} 입력입니다 — {_form(ctype)} 로 적어야 합니다(받은 값: {raw}).", [],
                                    f"docs/기준설계.md · fixed_inputs: {function}({key}=<{_form(ctype)}>)")
            result[key] = value
    for parameter in parameters:
        if parameter != boundary_input and parameter not in result:
            raise NeedsCriteria(sr, f"{parameter} 고정 입력", "요구사항에 입력값의 기준이 없습니다.", [],
                                f"docs/기준설계.md · fixed_inputs: {function}({parameter}=<{_form(types.get(parameter, ''))}>)")
    return result


def requirement_rows(repo: Path, sr: str, function: str, parameters: list[str],
                     boundary_input: str, enum_members: list[str],
                     types: dict[str, str] | None = None) -> list[dict]:
    criteria = read_criteria(repo, missing_ok=True)
    requirements = read_requirements(repo, criteria.requirements or "docs/요구사항.md")
    requirement = requirements.get(sr)
    if requirement is None:
        raise NeedsCriteria(sr, "요구사항", "요구사항 ID를 찾지 못했습니다.", [], "docs/요구사항.md")
    values = criteria.required_tests.get(sr)
    boundary = boundaries(requirement.text)
    numbers = {number for number, _ in boundary}
    options = sorted({candidate for number in numbers for candidate in (number - 1, number, number + 1)})
    if not values:
        raise NeedsCriteria(sr, f"기준설계에 {sr} 기준 시험이 없습니다",
                            f"기준설계 required_tests에 {sr} 항목이 없습니다.", options,
                            f"docs/기준설계.md · required_tests: {sr}[…]")
    if not numbers:
        raise NeedsCriteria(sr, f"{sr} 문장에 경계 수치가 없어 기준 입력을 정할 수 없습니다",
                            f"{sr} 요구사항 문장에 수치 경계가 없습니다.", [],
                            f"docs/요구사항.md · {sr}")
    if not numbers.intersection(values):
        raise NeedsCriteria(sr, "요구사항과 기준설계 경계 불일치", "required_tests가 현재 요구사항 경계를 포함하지 않습니다.",
                            options, "docs/기준설계.md · required_tests")
    fixed = fixed_inputs(repo, function, parameters, sr, boundary_input, types)
    rows = []
    for value in values:
        expected, basis = expected_value(repo, sr, value, enum_members)
        rows.append({"req": sr, "function": function, "inputs": {boundary_input: value, **fixed},
                     "expected": expected, "expected_source": "requirement", "basis": basis})
    return rows


def expected_value(repo: Path, sr: str, value: int,
                   enum_members: list[str] | None = None) -> tuple[str, str]:
    criteria = read_criteria(repo, missing_ok=True)
    requirements = read_requirements(repo, criteria.requirements or "docs/요구사항.md")
    grades = read_grades(repo, criteria.requirements or "docs/요구사항.md")
    grade = next((grade for grade in grades.values() if _satisfies(grade.condition, value)), None)
    if grade is None:
        raise NeedsCriteria(sr, f"speed_kph={value} 기대값", "등급 표에서 기대값을 결정할 수 없습니다.", [],
                            "docs/요구사항.md · §3")
    supporting = next((other for other in requirements.values()
                       if re.search(rf"`{grade.name}`", other.text)
                       and _matches_requirement(other.text, value)), None)
    basis = (f"{supporting.id} (docs/요구사항.md:{supporting.line})" if supporting
             else f"§3 {grade.name} (docs/요구사항.md:{grade.line})")
    matches = [member for member in (enum_members or [])
               if member == grade.name or member.endswith("_" + grade.name)]
    if len(matches) != 1:
        raise NeedsCriteria(sr, f"{grade.name} 반환 enum", "반환 enum에서 등급 멤버를 한 개로 결정할 수 없습니다.", [],
                            "include/ · 반환 enum")
    return matches[0], basis


def _matches_requirement(text: str, value: int) -> bool:
    clauses = boundaries(text)
    if not clauses:
        return False
    for number, direction in clauses:
        if not {"이상": value >= number, "초과": value > number, "미만": value < number,
                "이하": value <= number, "≥": value >= number, ">": value > number,
                "<": value < number, "≤": value <= number}[direction]:
            return False
    return True
