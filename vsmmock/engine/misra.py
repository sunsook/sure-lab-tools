"""Small AST based subset of MISRA C:2023 for the teaching mock."""

import os
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pycparser import c_ast, c_parser
from pycparser.c_parser import ParseError

from .cparse import FAKE_LIBC
from .criteria import read_criteria
from .result import Finding, Result, add_unhandled, mock_limit

SUPPORTED = ("16.3", "16.4", "10.1", "14.3", "21.7", "21.6")
TOOL = {"name": "STATIC", "mimics": "statica-plugin v0.1.0 pre-analyze"}
STDIO = {"printf", "fprintf", "sprintf", "snprintf", "scanf", "fscanf", "sscanf",
         "puts", "putchar", "getchar", "fgets", "fputs", "fputc", "fgetc", "fread",
         "fwrite", "fopen", "fclose", "fflush", "perror", "remove", "rename"}
ATOI = {"atoi", "atol", "atoll", "atof"}
HINTS = {
    "16.3": "case 끝에 break 또는 명시적인 제어 흐름 종료를 추가하세요.",
    "16.4": "switch 문에 default 분기를 추가하세요.",
    "10.1": "bool 값을 산술식에 쓰지 말고 명시적으로 정수 값으로 변환하세요.",
    "14.3": "항상 참인 unsigned 비교를 제거하거나 유효한 조건으로 바꾸세요.",
    "21.7": "변환 실패를 확인할 수 있는 strtol 계열 함수로 바꾸세요.",
    "21.6": "표준 입출력 함수 대신 대상 환경에 맞는 출력 수단을 사용하세요.",
}


@dataclass
class MisraFinding(Finding):
    rule: str = ""


def _parse(repo: Path, source: Path) -> c_ast.FileAST:
    command = [sys.executable, "-m", "ziglang", "cc", "-E", "-std=c11", "-nostdinc",
               "-I", str(FAKE_LIBC), "-I", str(repo / "include"), str(source)]
    with tempfile.TemporaryDirectory(prefix="vsmmock_cpp_") as cache:
        env = {**os.environ, "ZIG_LOCAL_CACHE_DIR": cache}  # 전역 캐시는 기본 위치(runner.py 주석 참고)
        result = subprocess.run(command, cwd=repo, capture_output=True, stdin=subprocess.DEVNULL, text=True,
                                encoding="utf-8", env=env)
    if result.returncode:
        raise ValueError(result.stderr.strip() or f"전처리 실패: {source}")
    return c_parser.CParser().parse(result.stdout, filename=str(source))


def _type_names(node: c_ast.Node) -> set[str]:
    names = set()
    if isinstance(node, c_ast.IdentifierType):
        names.update(node.names)
    for _, child in node.children():
        names.update(_type_names(child))
    return names


def _zero(node: c_ast.Node) -> bool:
    return isinstance(node, c_ast.Constant) and node.value.lower().rstrip("ul") == "0"


def _boolean_expr(node: c_ast.Node, bool_names: set[str]) -> bool:
    return (isinstance(node, c_ast.ID) and node.name in bool_names
            or isinstance(node, c_ast.BinaryOp) and node.op in
            {"<", "<=", ">", ">=", "==", "!=", "&&", "||"}
            or isinstance(node, c_ast.UnaryOp) and node.op == "!")


def _base_name(node: c_ast.Node) -> str | None:
    if isinstance(node, c_ast.ID):
        return node.name
    if isinstance(node, c_ast.ArrayRef):
        return _base_name(node.name)
    return None


class UnsupportedPattern(ValueError):
    def __init__(self, node: c_ast.Node):
        super().__init__("식 위치의 GNU 문장식은 목업 AST 검사 범위 밖입니다")
        self.coord = node.coord


class Checker(c_ast.NodeVisitor):
    def __init__(self, source: Path, repo: Path, enabled: set[str]):
        self.relative = source.relative_to(repo).as_posix()
        self.source = source
        self.enabled = enabled
        self.findings: list[dict] = []
        self.bool_names: set[str] = set()
        self.unsigned_names: set[str] = set()

    def _emit(self, rule: str, node: c_ast.Node, actual: str) -> None:
        if rule not in self.enabled or not node.coord:
            return
        # Header declarations are visited with each translation unit; report source only.
        if Path(node.coord.file.replace("\\", "/")).name != self.source.name:
            return
        line = node.coord.line
        self.findings.append({
            "rule": rule, "where": f"{self.relative}:{line}",
            "path": self.relative, "startLine": line, "actual": actual,
            "fix_hint": HINTS[rule], "basis": f"MISRA C:2023 Rule {rule} (Required)",
        })

    def visit_Decl(self, node: c_ast.Decl) -> None:
        names = _type_names(node.type)
        if node.name:
            if "bool" in names or "_Bool" in names:
                self.bool_names.add(node.name)
            if any(name.startswith("uint") or name == "unsigned" for name in names):
                self.unsigned_names.add(node.name)
        self.generic_visit(node)

    def visit_Switch(self, node: c_ast.Switch) -> None:
        clauses = node.stmt.block_items or [] if isinstance(node.stmt, c_ast.Compound) else []
        if not any(isinstance(item, c_ast.Default) for item in clauses):
            self._emit("16.4", node, "default 분기 없음")
        for item in clauses:
            if isinstance(item, c_ast.Case) and item.stmts:
                last = item.stmts[-1]
                if not isinstance(last, (c_ast.Break, c_ast.Return, c_ast.Goto, c_ast.Continue)):
                    self._emit("16.3", item, "case 끝에 break 없음")
        self.generic_visit(node)

    def visit_BinaryOp(self, node: c_ast.BinaryOp) -> None:
        if node.op in {"+", "-", "*", "/", "%", "<<", ">>", "&", "|", "^"}:
            if _boolean_expr(node.left, self.bool_names) or _boolean_expr(node.right, self.bool_names):
                self._emit("10.1", node, "bool 값을 산술식에 사용")
        if node.op in {">=", ">"} and _zero(node.right) and _base_name(node.left) in self.unsigned_names:
            if node.op == ">=":
                self._emit("14.3", node, "unsigned 값은 항상 0 이상")
        self.generic_visit(node)

    def visit_Assignment(self, node: c_ast.Assignment) -> None:
        if node.op != "=" and (_boolean_expr(node.rvalue, self.bool_names)
                               or _boolean_expr(node.lvalue, self.bool_names)):
            self._emit("10.1", node, "bool 값을 복합 대입에 사용")
        self.generic_visit(node)

    def visit_Return(self, node: c_ast.Return) -> None:
        if isinstance(node.expr, c_ast.Compound):
            raise UnsupportedPattern(node.expr)
        self.generic_visit(node)

    def visit_FuncCall(self, node: c_ast.FuncCall) -> None:
        if isinstance(node.name, c_ast.ID):
            if node.name.name in ATOI:
                self._emit("21.7", node, f"{node.name.name} 호출")
            if node.name.name in STDIO:
                self._emit("21.6", node, f"{node.name.name} 호출")
        self.generic_visit(node)


def analyze(repo: Path, *, face: str = "cli") -> Result:
    """Analyze src/*.c; unsupported rules are errors and parse failures are notices."""
    repo = Path(repo).resolve()
    criteria = read_criteria(repo)
    missing = [key for key, absent in (("misra_rules", not criteria.misra_rules),
                                         ("misra_max", criteria.misra_max is None)) if absent]
    if missing:
        result = Result(check="static.analyze", status="ERROR", reason="CRITERIA_MISSING", tool=TOOL)
        result.findings.append(Finding(id="STATIC-CRITERIA", where="docs/기준설계.md",
            expected=" · ".join(f"{key}: …" for key in missing), actual="기준 없음",
            fix_hint="기준설계에 검사 규칙과 허용 결함 수를 정하세요.",
            basis="docs/기준설계.md", back_to="요구사항"))
        return result
    unsupported = sorted(set(criteria.misra_rules) - set(SUPPORTED))
    if unsupported:
        rules = ", ".join(unsupported)
        return mock_limit(repo, check="static.analyze", tool=TOOL, face=face,
                          command="static analyze", where="docs/기준설계.md",
                          detail=f"MISRA {rules} 규칙은 목업 미지원입니다. 실제 STATIC 은 검사함.")
    result = Result(check="static.analyze", status="PASS", tool=TOOL)
    findings = []
    analyzed = 0
    sources = sorted((repo / "src").glob("*.c"))
    for source in sources:
        try:
            tree = _parse(repo, source)
            checker = Checker(source, repo, set(criteria.misra_rules))
            checker.visit(tree)
            findings.extend(checker.findings)
            analyzed += 1
        except (OSError, ValueError, ParseError) as error:
            # pycparser's ParseError derives from Exception. Keep the failure local to this file.
            relative = source.relative_to(repo).as_posix()
            location = getattr(error, "coord", None)
            line = getattr(location, "line", 1) if location else 1
            add_unhandled(result, repo, tool="STATIC", face=face, command="static analyze",
                          where=f"{relative}:{line}", detail=str(error), exception=error)
    findings.sort(key=lambda item: (item["path"], item["startLine"], item["rule"]))
    for index, item in enumerate(findings, 1):
        result.findings.append(MisraFinding(id=f"STATIC-{index:03d}", where=item["where"],
                                       expected=f"MISRA {item['rule']} 준수", actual=item["actual"],
                                       fix_hint=item["fix_hint"], basis=item["basis"], back_to="코드 수정",
                                       rule=item["rule"]))
    result.metrics = {"analyzed": analyzed, "defects": len(findings),
                      "by_rule": dict(sorted(Counter(item["rule"] for item in findings).items())),
                      "items": findings}
    if len(findings) > criteria.misra_max:
        result.status = "FAIL"
    return result
