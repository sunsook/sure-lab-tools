"""Compile and execute test definitions and student C tests together."""

import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .cparse import functions
from .result import Finding, Result, mock_limit
from .testdef import InputBroken, read_definitions

TOOL = {"name": "DVERA", "mimics": "dvera-plugin v0.1.4 ct_get_test_results"}


def _finding(id: str, where: str, expected: str, actual: str, basis: str) -> Finding:
    return Finding(id=id, where=where, expected=expected, actual=actual,
                   fix_hint="실제 코드의 판정과 시험 기대값을 비교하고 코드를 수정하세요.",
                   basis=basis, back_to="코드 수정")


def _enum_names(repo: Path) -> list[str]:
    names = []
    for header in sorted((repo / "include").glob("*.h")):
        content = re.sub(r"/\*.*?\*/|//[^\n]*", "", header.read_text(encoding="utf-8"), flags=re.S)
        for body in re.findall(r"\benum\b[^{}]*\{([^{}]*)\}", content, flags=re.S):
            names.extend(match.group(1) for entry in body.split(",")
                         if (match := re.match(r"\s*([A-Za-z_]\w*)", entry)))
    return names


def _literal(value: object, enums: set[str], where: str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value in enums:
        return value
    raise UnsupportedInput(where, f"포인터·배열·구조체 또는 알 수 없는 입력: {value!r}")


class UnsupportedInput(ValueError):
    def __init__(self, where: str, detail: str):
        super().__init__(detail)
        self.where = where


def _test_source(repo: Path, definitions: list, c_tests: list[Path], signatures: dict,
                 enum_names: list[str]) -> str:
    headers = [p.name for p in sorted((repo / "include").glob("*.h"))]
    lines = ["#include <stdio.h>", "#include <stdbool.h>"]
    lines += [f'#include "{name}"' for name in headers]
    lines += [f"int {name}(void);" for path in c_tests
              for name in re.findall(r"\bint\s+(tc_\w+)\s*\(\s*void\s*\)",
                                     path.read_text(encoding="utf-8"))]
    lines += ["static const char *enum_name(int value) {", "switch (value) {"]
    lines += [f'case {name}: return "{name}";' for name in enum_names]
    lines += ['default: return "<unknown enum>";', "}", "}", "int main(void) {"]
    enums = set(enum_names)
    for index, definition in enumerate(definitions):
        function = signatures.get(definition.function)
        if function is None:
            raise InputBroken(definition.where, f"대상 함수를 찾지 못했습니다: {definition.function}")
        if function.get("unsupported"):
            raise UnsupportedInput(definition.where, f"포인터·배열·구조체 인자 미지원: {definition.function}")
        params = function["params"]
        if set(definition.inputs) != set(params):
            raise InputBroken(definition.where, "입력 인자와 함수 선언이 일치하지 않습니다")
        if definition.expected not in enums:
            raise InputBroken(definition.where, f"enum 기대값을 찾지 못했습니다: {definition.expected}")
        args = ", ".join(_literal(definition.inputs[name], enums, definition.where) for name in params)
        lines.append(f'printf("D\\t{index}\\t%s\\n", enum_name((int){definition.function}({args})));')
    test_index = 0
    for path in c_tests:
        names = re.findall(r"\bint\s+(tc_\w+)\s*\(\s*void\s*\)",
                           path.read_text(encoding="utf-8"))
        if not names:
            raise InputBroken(path.relative_to(repo).as_posix(), "tc_*(void) 함수를 찾지 못했습니다")
        for name in names:
            lines.append(f'printf("T\\t{test_index}\\t%d\\n", {name}());')
            test_index += 1
    lines += ["return 0;", "}"]
    return "\n".join(lines) + "\n"


def run(repo: Path, *, junit_path: Path | None = None) -> Result:
    result = Result(check="ct.run", status="PASS", tool=TOOL)
    try:
        definitions = read_definitions(repo)
        c_tests = sorted((repo / "tests").glob("TC-*.c"))
        discovered = functions(repo)
        signatures = {}
        for item in discovered:
            match = re.search(r"\b" + re.escape(item["name"]) + r"\s*\((.*)\)", item["signature"])
            raw_params = [] if not match or match[1].strip() == "void" else match[1].split(",")
            params = [re.search(r"([A-Za-z_]\w*)\s*$", part.strip()).group(1) for part in raw_params]
            unsupported = any("*" in part or "[" in part or re.search(r"\b(struct|union)\b", part)
                              for part in raw_params)
            signatures[item["name"]] = {"where": item["where"], "params": params}
            if unsupported:
                signatures[item["name"]]["unsupported"] = True
        enum_names = _enum_names(repo)
        source = _test_source(repo, definitions, c_tests, signatures, enum_names)
    except InputBroken as error:
        result.status, result.reason, result.detail = "ERROR", "INPUT_BROKEN", str(error)
        result.findings.append(_finding("CT-INPUT", error.where, "올바른 시험 정의", str(error), error.where))
        return result
    except UnsupportedInput as error:
        return mock_limit(repo, check="ct.run", tool=TOOL, face="cli", command="ct run",
                          where=error.where, detail=str(error))
    except (OSError, ValueError) as error:
        result.status, result.reason, result.detail = "ERROR", "INPUT_BROKEN", str(error)
        result.findings.append(_finding("CT-SOURCE", "src/", "파싱 가능한 C 소스", str(error), "소스 코드"))
        return result

    with tempfile.TemporaryDirectory(prefix="vsmmock_ct_") as temporary:
        runner_file = Path(temporary) / "runner.c"
        binary = Path(temporary) / ("runner.exe" if sys.platform == "win32" else "runner")
        runner_file.write_text(source, encoding="utf-8")
        sources = [str(path) for path in sorted((repo / "src").glob("*.c")) if path.name != "main.c"]
        command = [sys.executable, "-m", "ziglang", "cc", "-std=c11", "-I", str(repo / "include"),
                   *sources, *(str(path) for path in c_tests), str(runner_file), "-o", str(binary)]
        try:
            # 전역 캐시(libc · compiler-rt)는 사용자 기본 위치를 그대로 쓴다 — 임시 폴더로 돌리면 매 실행 libc 를 다시 빌드한다(실측 39초 → 1초)
            env = {**os.environ, "ZIG_LOCAL_CACHE_DIR": temporary}
            compiled = subprocess.run(command, cwd=repo, capture_output=True, text=True,
                                      encoding="utf-8", timeout=120, env=env)
            if compiled.returncode:
                result.status, result.reason = "ERROR", "BUILD_FAILED"
                result.detail = compiled.stderr[:1000]
                return result
            executed = subprocess.run([str(binary)], cwd=repo, capture_output=True, text=True,
                                      encoding="utf-8", timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            result.status, result.reason, result.detail = "ERROR", "BUILD_FAILED", str(error)
            return result
        if executed.returncode:
            result.status, result.reason, result.detail = "ERROR", "BUILD_FAILED", executed.stderr[:1000]
            return result

    outcomes = {}
    for line in executed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] in ("D", "T") and parts[1].isdigit():
            outcomes[(parts[0], int(parts[1]))] = parts[2]
    cases = []
    case_details = []
    for index, definition in enumerate(definitions):
        actual = outcomes.get(("D", index), "<missing result>")
        passed = actual == definition.expected
        cases.append((definition.id, passed, actual))
        case_details.append({"testName": definition.id, "suiteName": "ct", "passed": passed, "actual": actual})
        if not passed:
            result.findings.append(_finding(definition.id, signatures[definition.function]["where"],
                                            definition.expected, actual, definition.basis))
    test_index = 0
    for path in c_tests:
        content = path.read_text(encoding="utf-8")
        names = re.findall(r"\bint\s+(tc_\w+)\s*\(\s*void\s*\)", content)
        function = re.search(r"\b([A-Za-z_]\w*)\s*\([^;]*\)\s*==", content)
        target = signatures.get(function[1], {}) if function else {}
        marker = re.search(r"@req\s+(SR-\d{3})", content)
        for name in names:
            case_id = path.stem if len(names) == 1 else f"{path.stem}::{name}"
            actual = outcomes.get(("T", test_index), "<missing result>")
            test_index += 1
            passed = actual == "0"
            cases.append((case_id, passed, actual))
            case_details.append({"testName": case_id, "suiteName": "tests", "passed": passed, "actual": actual})
            if not passed:
                result.findings.append(_finding(case_id, target.get("where", path.relative_to(repo).as_posix()),
                                                "PASS", "FAIL", marker[1] if marker else case_id))
    result.metrics = {"total": len(cases), "passed": sum(passed for _, passed, _ in cases),
                      "failed": sum(not passed for _, passed, _ in cases), "cases": case_details}
    result.status = "FAIL" if result.findings else "PASS"
    if junit_path is not None:
        suite = ET.Element("testsuite", tests=str(len(cases)), failures=str(result.metrics["failed"]))
        for name, passed, actual in cases:
            case = ET.SubElement(suite, "testcase", name=name)
            if not passed:
                ET.SubElement(case, "failure", message=f"actual: {actual}")
        junit_path.parent.mkdir(parents=True, exist_ok=True)
        ET.ElementTree(suite).write(junit_path, encoding="utf-8", xml_declaration=True)
    return result
