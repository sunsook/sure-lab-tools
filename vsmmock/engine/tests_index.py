"""Index test inputs against their requirement's implementation signature."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .cparse import function_shapes
from .requirements import read_requirements


@dataclass(frozen=True)
class TestInput:
    req: str
    value: int
    id: str
    where: str


def read_tests(repo: Path) -> list[TestInput]:
    found = []
    requirements = read_requirements(repo)
    shapes = function_shapes(repo)
    def target(req: str):
        requirement = requirements.get(req)
        if not requirement:
            return None
        for name in re.findall(r"\b([A-Za-z_]\w*)\s*\(\s*\)", requirement.implementation):
            shape = shapes.get(name)
            if shape:
                numeric = [(index, param["name"]) for index, param in enumerate(shape["parameters"])
                           if re.fullmatch(r"(?:u?int(?:8|16|32|64)?_t|int|unsigned(?: int)?)", param["type"])]
                if len(numeric) == 1:
                    return name, numeric[0][0], numeric[0][1]
        return None
    for path in sorted((repo / "ct").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        req = data.get("req")
        inputs = data.get("inputs", {})
        selected = target(req) if req else None
        if selected and inputs:
            value = inputs.get(selected[2])
            if isinstance(value, int) and not isinstance(value, bool):
                found.append(TestInput(req, value, data.get("id", path.stem), path.relative_to(repo).as_posix()))
    for path in sorted((repo / "tests").glob("TC-*.c")):
        lines = path.read_text(encoding="utf-8").splitlines()
        marker = re.search(r"@req\s+(SR-\d{3})\b", lines[0]) if lines else None
        if not marker:
            continue
        selected = target(marker[1])
        if not selected:
            continue
        source = "\n".join(lines)
        for call in re.finditer(r"\b" + re.escape(selected[0]) + r"\s*\(([^()]*)\)", source):
            arguments = [arg.strip() for arg in call[1].split(",")]
            if len(arguments) <= selected[1]:
                continue
            number = re.fullmatch(r"(\d+)[uUlL]*", arguments[selected[1]])
            if number:
                found.append(TestInput(marker[1], int(number[1]), path.stem,
                                       path.relative_to(repo).as_posix()))
    return found
