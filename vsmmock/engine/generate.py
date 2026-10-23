"""Build reviewable CT specifications and approved definitions."""

import hashlib
import json
import re
from pathlib import Path

from . import cparse
from .caselog import FACE, record
from .result import unhandled_message
from .criteria import read_criteria
from .oracle import NeedsCriteria, expected_value, requirement_rows
from .requirements import boundaries, read_requirements
from .runner import run


def _test_id(row: dict) -> str:
    first = next(iter(row["inputs"].values()))
    return f"CT-{row['req'].replace('-', '')}-{first}"


def _existing(repo: Path) -> list[tuple[Path, dict]]:
    found = []
    for path in sorted((repo / "ct").glob("*.json")):
        found.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return found


def _stale(repo: Path, specs: list[str], notices: list[dict] | None = None) -> list[str]:
    stale = []
    existing = _existing(repo)
    if not existing:
        return stale
    shapes = cparse.function_shapes(repo, notices=notices)
    for _, definition in existing:
        if definition.get("req") not in specs:
            continue
        inputs = definition.get("inputs", {})
        shape = shapes.get(definition.get("function"))
        if not shape or not shape["enum_members"]:
            continue
        candidates = [p["name"] for p in shape["parameters"]
                      if p["type"] in ("int", "int8_t", "int16_t", "int32_t", "uint8_t", "uint16_t", "uint32_t")
                      and p["name"] in inputs]
        if len(candidates) != 1:
            continue
        expected, _ = expected_value(repo, definition["req"], inputs[candidates[0]], shape["enum_members"])
        if expected != definition.get("expected"):
            stale.append(definition["id"])
    return stale


def specification(repo: Path, function: str, specs: list[str],
                  notices: list[dict] | None = None) -> dict:
    signatures = {item["name"]: item for item in cparse.functions(repo, notices=notices)}
    if function not in signatures:
        return {"source": "MOCK", "status": "ERROR", "reason": "INPUT_BROKEN", "detail": "함수를 찾지 못했습니다."}
    shape = cparse.function_shapes(repo, signatures[function]["sourceFile"], notices=notices)[function]
    names = [parameter["name"] for parameter in shape["parameters"]]
    fixed = read_criteria(repo, missing_ok=True).fixed_inputs or ""
    fixed_match = re.fullmatch(r"(\w+)\(([^()]*)\)", fixed)
    fixed_names = ({part.split("=", 1)[0].strip() for part in fixed_match[2].split(",") if "=" in part}
                   if fixed_match and fixed_match[1] == function else set())
    integers = [p["name"] for p in shape["parameters"]
                if p["type"] in ("int", "int8_t", "int16_t", "int32_t", "uint8_t", "uint16_t", "uint32_t")
                and p["name"] not in fixed_names]
    if len(integers) != 1 or not shape["enum_members"] or any(
            p["type"] in ("...", "") for p in shape["parameters"]):
        detail = "목업이 이 함수의 요구사항 기반 시험을 만들 수 없습니다."
        case_id = record(repo, tool="DVERA", face=FACE.get(), command="ct_ai_generate_test",
                         kind="MOCK_UNHANDLED", where=shape["where"], detail=detail)
        return {"source": "MOCK", "status": "MOCK_UNHANDLED", "created": [],
                "notices": [{"kind": "MOCK_UNHANDLED", "where": shape["where"],
                             "message": unhandled_message(shape["where"], "목업이 지원하지 않는 함수 형태",
                                                          "목업이 시험을 만들지 못합니다 — tests/TC-*.c 로 직접 작성하세요"),
                             "case_id": case_id}],
                "fix_hint": "목업이 이 함수는 만들 수 없습니다. 직접 tests/TC-*.c 로 작성하세요."}
    rows, questions = [], []
    for sr in specs:
        try:
            rows.extend(requirement_rows(repo, sr, function, names, integers[0], shape["enum_members"],
                                         {p["name"]: p["type"] for p in shape["parameters"]}))
        except NeedsCriteria as question:
            questions.append(question.as_dict())
    stale = _stale(repo, specs, notices=notices)
    if questions:
        answer = {"source": "MOCK", "status": "NEEDS_CRITERIA", "questions": questions, "stale": stale}
        if not (repo / "docs/기준설계.md").is_file():
            answer["detail"] = ("docs/기준설계.md 가 없습니다 — 질문의 write_to 대로 이 파일을 만들어 답을 적은 뒤 "
                                "다시 실행하세요(실습 2-④).")
        return answer
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return {"source": "MOCK", "status": "NEEDS_APPROVAL",
            "spec": {"id": f"spec-{digest}", "rows": rows, "stale": stale}}


def structure_specification(repo: Path, function: str, notices: list[dict] | None = None) -> dict:
    branches = cparse.branches(repo, function, notices=notices)
    requirements = read_requirements(repo)
    sr = next((req.id for req in requirements.values() if f"{function}()" in req.implementation), "")
    signatures = {item["name"]: item["signature"] for item in cparse.functions(repo, notices=notices)}
    signature = signatures.get(function, "")
    array_param = re.search(r"int16_t\s*\*\s*(\w+)", signature)
    count_param = re.search(r"(?:uint\d+_t|int)\s+(count)\b", signature)
    for branch in branches:
        if array_param and count_param:
            branch["inputs"] = {array_param[1]: [0] if branch["side"] == "T" else [-1], count_param[1]: 1}
        else:
            branch["inputs"] = {"side": branch["side"]}
    questions = [{"sr": sr, "missing": f"{branch['where']} {branch['side']} 기대값",
                  "why": "이 분기의 결과를 요구사항과 기준설계에서 결정할 수 없습니다.",
                  "options": [], "write_to": "docs/기준설계.md · expected"} for branch in branches]
    return {"source": "MOCK", "status": "NEEDS_CRITERIA", "branches": branches, "questions": questions}


def approve(repo: Path, spec: dict, specs: list[str]) -> dict:
    current = _existing(repo)
    first_creation = not any(item.get("generated_by") for _, item in current)
    stale_ids = set(spec["stale"])
    retired = []
    for path, item in current:
        if item.get("id") in stale_ids:
            target = repo / "ct" / "retired" / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            path.rename(target)
            retired.append(target.relative_to(repo).as_posix())
    present = {item["id"]: item for path, item in current if item.get("id") not in stale_ids}
    created = []
    for row in spec["rows"]:
        id_ = _test_id(row)
        if id_ in present and present[id_].get("expected") == row["expected"]:
            continue
        definition = {"id": id_, **row, "approved_spec": spec["id"], "generated_by": "engine"}
        path = repo / "ct" / f"{id_}.json"
        path.parent.mkdir(parents=True, exist_ok=True)  # 수강생 1번 저장소에는 ct/ 가 없다
        path.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        created.append(path.relative_to(repo).as_posix())
    if first_creation and created:
        requirements = read_requirements(repo)
        first_sr = specs[0]
        boundary = boundaries(requirements[first_sr].text)
        if boundary:
            value = boundary[-1][0]
            trap = next((row for row in spec["rows"] if row["req"] == first_sr
                         and value in row["inputs"].values()), None)
            if trap:
                path = repo / "ct" / f"{_test_id(trap)}.json"
                outcomes = run(repo).metrics.get("cases", [])
                actual = next((case["actual"] for case in outcomes
                               if case["testName"] == _test_id(trap)), None)
                members = cparse.function_shapes(repo)[trap["function"]]["enum_members"]
                if actual not in members:
                    return {"source": "MOCK", "status": "ERROR", "reason": "BUILD_FAILED",
                            "detail": "생성 시험의 실제 코드 실행값을 읽지 못했습니다.",
                            "created": created, "retired": retired}
                definition = json.loads(path.read_text(encoding="utf-8"))
                definition["expected"], definition["expected_source"] = actual, "code"
                path.write_text(json.dumps(definition, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"source": "MOCK", "status": "PASS", "created": created, "retired": retired}
