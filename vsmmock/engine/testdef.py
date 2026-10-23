"""Read and validate approved C test definitions."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TestDefinition:
    id: str
    req: str
    function: str
    inputs: dict[str, Any]
    expected: str
    basis: str
    where: str


class InputBroken(ValueError):
    def __init__(self, where: str, detail: str):
        super().__init__(detail)
        self.where = where


def read_definitions(repo: Path) -> list[TestDefinition]:
    definitions = []
    for path in sorted((repo / "ct").glob("*.json")):
        where = path.relative_to(repo).as_posix()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("시험 정의가 객체가 아닙니다")
            required = ("id", "req", "function", "inputs", "expected", "expected_source",
                        "basis", "approved_spec", "generated_by")
            absent = [key for key in required if key not in data]
            if absent:
                raise ValueError(f"필수 키 없음: {', '.join(absent)}")
            if not all(isinstance(data[key], str) and data[key] for key in required if key != "inputs"):
                raise ValueError("문자열 필드가 비었거나 형식이 틀렸습니다")
            if not isinstance(data["inputs"], dict) or not data["inputs"]:
                raise ValueError("inputs가 비었거나 객체가 아닙니다")
            if not re.fullmatch(r"SR-\d{3}", data["req"]):
                raise ValueError("req 형식 오류")
            if data["expected_source"] not in ("requirement", "criteria", "code"):
                raise ValueError("expected_source 형식 오류")
            definitions.append(TestDefinition(data["id"], data["req"], data["function"],
                                              data["inputs"], data["expected"], data["basis"], where))
        except (OSError, ValueError, TypeError) as error:
            raise InputBroken(where, str(error)) from error
    return definitions
