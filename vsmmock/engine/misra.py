"""Small AST based subset of MISRA C:2023 for the teaching mock."""

import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pycparser import c_ast, c_parser
from pycparser.c_parser import ParseError

from .cparse import FAKE_LIBC
from .criteria import ACTIONS, read_criteria
from .result import Finding, Result, add_unhandled, mock_limit

CATEGORY = {  # MISRA C:2023 분류 — 원문 문서 쪽(ADR-007) · 지원 규칙은 이 표 한 곳
    "16.3": "Required",   # 155
    "16.4": "Required",   # 156
    "10.1": "Required",   # 100
    "14.3": "Required",   # 142
    "21.7": "Required",   # 199
    "21.6": "Required",   # 199
    "12.5": "Mandatory",  # 128
    "2.7": "Advisory",    # 50
}
SUPPORTED = tuple(CATEGORY)
CATEGORIES = ("Mandatory", "Required", "Advisory")
POLICY_KEYS = {"Mandatory": "misra_mandatory", "Required": "misra_required", "Advisory": "misra_advisory"}
MANDATORY_NOTE = "Mandatory 는 예외 표시를 인정하지 않습니다 — MISRA C:2023 문서 8쪽(deviation from mandatory guidelines is not permitted)"
DEVIATION = re.compile(r"/\*\s*MISRA-DEVIATION\s+(?P<rule>\d+\.\d+)\s+사유=(?P<why>.*?)\s*승인=(?P<by>.*?)\s*\*/")
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
    "12.5": "배열 매개변수에 sizeof 를 쓰지 말고 요소 수를 따로 넘기세요 — 매개변수는 포인터라 배열 크기가 아닙니다.",
    "2.7": "쓰지 않는 매개변수를 지우거나, 인터페이스상 필요하면 (void)이름; 으로 쓰지 않음을 밝히세요.",
}


@dataclass
class MisraFinding(Finding):
    rule: str = ""
    category: str = ""


def find_deviation(lines: list[str], line: int, rule: str) -> dict | None:
    """위배 줄(line · 1부터) 또는 바로 윗줄에서 그 규칙의 예외 표시를 찾는다(ADR-015 · 목업이 정한 꼴)."""
    for number in (line, line - 1):
        if not 1 <= number <= len(lines):
            continue
        for match in DEVIATION.finditer(lines[number - 1]):
            if match["rule"] == rule:
                why, by = match["why"].strip(), match["by"].strip()
                return {"rule": rule, "why": why, "by": by, "line": number, "complete": bool(why and by)}
    return None


def _walk(node: c_ast.Node):
    yield node
    for _, child in node.children():
        yield from _walk(child)


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
        self.array_params: set[str] = set()

    def _emit(self, rule: str, node: c_ast.Node, actual: str) -> None:
        if rule not in self.enabled or not node.coord:
            return
        # Header declarations are visited with each translation unit; report source only.
        if Path(node.coord.file.replace("\\", "/")).name != self.source.name:
            return
        line = node.coord.line
        self.findings.append({
            "rule": rule, "category": CATEGORY[rule], "where": f"{self.relative}:{line}",
            "path": self.relative, "startLine": line, "actual": actual,
            "fix_hint": HINTS[rule], "basis": f"MISRA C:2023 Rule {rule} ({CATEGORY[rule]})",
        })

    def visit_FuncDef(self, node: c_ast.FuncDef) -> None:
        # 이름 있는 매개변수만 — f(void) 의 Typename · ... 은 매개변수가 아니다(cparse.function_shapes 와 같은 기준)
        args = node.decl.type.args if isinstance(node.decl.type, c_ast.FuncDecl) else None
        params = [param for param in (args.params if args else [])
                  if isinstance(param, c_ast.Decl) and param.name]
        used = {item.name for item in _walk(node.body) if isinstance(item, c_ast.ID)}
        for param in params:
            if param.name not in used:  # 같은 이름 지역변수가 가리면 「사용」으로 보는 근사(README 한계)
                self._emit("2.7", node.decl, f"매개변수 {param.name} 미사용")
        outer = self.array_params
        self.array_params = {param.name for param in params if isinstance(param.type, c_ast.ArrayDecl)}
        self.generic_visit(node)
        self.array_params = outer

    def visit_UnaryOp(self, node: c_ast.UnaryOp) -> None:
        if node.op == "sizeof" and isinstance(node.expr, c_ast.ID) and node.expr.name in self.array_params:
            self._emit("12.5", node, f"배열 매개변수 {node.expr.name} 에 sizeof")
        self.generic_visit(node)

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


def _scan(repo: Path, rules: set[str], result: Result, face: str, command: str) -> tuple[list[dict], int]:
    """src/*.c 를 규칙 집합으로 검사한다 — 파싱 실패는 그 파일만 공지(MOCK_UNHANDLED)."""
    findings = []
    analyzed = 0
    for source in sorted((repo / "src").glob("*.c")):
        try:
            tree = _parse(repo, source)
            checker = Checker(source, repo, rules)
            checker.visit(tree)
            findings.extend(checker.findings)
            analyzed += 1
        except (OSError, ValueError, ParseError) as error:
            # pycparser's ParseError derives from Exception. Keep the failure local to this file.
            relative = source.relative_to(repo).as_posix()
            location = getattr(error, "coord", None)
            line = getattr(location, "line", 1) if location else 1
            add_unhandled(result, repo, tool="STATIC", face=face, command=command,
                          where=f"{relative}:{line}", detail=str(error), exception=error)
    findings.sort(key=lambda item: (item["path"], item["startLine"], item["rule"]))
    return findings, analyzed


def _policy(criteria) -> dict[str, str | None]:
    return {category: getattr(criteria, key) for category, key in POLICY_KEYS.items()}


def _category_mode(criteria) -> bool:
    """분류 키가 하나라도 있으면 분류 모드 — 없으면 misra_max 하위 호환(ADR-015 · ADR-014)."""
    return any(value is not None for value in _policy(criteria).values())


def _missing_keys(criteria) -> list[str]:
    missing = [] if criteria.misra_rules else ["misra_rules"]
    if _category_mode(criteria) or criteria.misra_max is None:  # misra_max 는 묻지 않는다 — 분류 키를 묻는다
        missing += [POLICY_KEYS[category] for category, value in _policy(criteria).items() if value is None]
        if criteria.misra_deviation is None:
            missing.append("misra_deviation")
    return missing


def _by_category(findings: list[dict]) -> dict[str, int]:
    return {category: sum(item["category"] == category for item in findings) for category in CATEGORIES}


def _source_text(repo: Path, relative: str, result: Result, face: str, command: str) -> str | None:
    try:
        return (repo / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:  # 표시를 못 읽은 파일은 공지 — 「표시 없음」으로 삼키지 않는다
        add_unhandled(result, repo, tool="STATIC", face=face, command=command,
                      where=f"{relative}:1", detail=f"예외 표시를 읽지 못함: {error}", exception=error)
        return None


def _policy_question(category: str, findings: list[dict], chosen: list[str]) -> dict:
    items = [item for item in findings if item["category"] == category]
    if items:
        per_rule = " · ".join(f"{rule} {count}건" for rule, count in sorted(Counter(i["rule"] for i in items).items()))
        evidence = f"({per_rule} · 첫 위치 {' · '.join(item['where'] for item in items[:3])})"
    else:
        evidence = "" if any(CATEGORY[rule] == category for rule in chosen) else f"(고른 규칙에 {category} 규칙 없음)"
    why = (f"{category} 위배를 어떻게 처리할지 사람이 정합니다 — 지금 {category} 위배 {len(items)}건{evidence}. "
           "block = 하나라도 있으면 Merge 불가 · fix = 고치거나 사유 · 승인이 있는 예외 표시가 있어야 통과 · report = 목록에만.")
    if category == "Mandatory":
        why += f" {MANDATORY_NOTE}."
    return {"sr": "STATIC", "missing": f"{category} 위배 처리", "why": why, "options": [],
            "supported": list(ACTIONS), "write_to": f"docs/기준설계.md · {POLICY_KEYS[category]}: <block|fix|report>"}


def criteria_questions(repo: Path, *, face: str = "mcp") -> dict | None:
    """에이전틱 STATICA — 기준설계의 빠진 칸만 묻는다(ADR-014 개정 · ADR-015). 다 있으면 None.

    묻는 키: misra_rules · misra_mandatory · misra_required · misra_advisory · misra_deviation (misra_max 는 묻지 않음).
    options 는 비운다(규칙 · 정책을 지어내지 않음). 고를 수 있는 값은 supported, 지금 코드 위배는 current 근거로만.
    """
    repo = Path(repo).resolve()
    criteria = read_criteria(repo, missing_ok=True)
    missing = _missing_keys(criteria)
    if not missing:
        return None
    rules_missing = "misra_rules" in missing
    chosen = list(SUPPORTED) if rules_missing else [rule for rule in criteria.misra_rules if rule in SUPPORTED]
    result = Result(check="static.pre-analyze", status="NEEDS_CRITERIA", tool=TOOL)
    findings, analyzed = _scan(repo, set(chosen), result, face, "static pre-analyze")
    by_rule = dict(sorted(Counter(item["rule"] for item in findings).items()))
    summary = " · ".join(f"{rule} {count}건" for rule, count in by_rule.items()) or "없음"
    questions = []
    if rules_missing:
        questions.append({"sr": "STATIC", "missing": "검사할 MISRA C:2023 규칙",
                          "why": f"검사할 규칙은 사람이 고릅니다 — 목업이 검사할 수 있는 규칙은 supported 의 "
                                 f"{len(SUPPORTED)}개(분류별)입니다(지금 코드 규칙별 위배: {summary}).",
                          "options": [],
                          "supported": {category: [rule for rule in SUPPORTED if CATEGORY[rule] == category]
                                        for category in CATEGORIES},
                          "write_to": "docs/기준설계.md · misra_rules: <규칙,…>"})
    questions += [_policy_question(category, findings, chosen)
                  for category in CATEGORIES if POLICY_KEYS[category] in missing]
    if "misra_deviation" in missing:
        texts = [_source_text(repo, source.relative_to(repo).as_posix(), result, face, "static pre-analyze")
                 for source in sorted((repo / "src").glob("*.c"))]
        markers = sum(len(DEVIATION.findall(text)) for text in texts if text is not None)
        questions.append({"sr": "STATIC", "missing": "예외 · 억제 표시 인정 여부",
                          "why": "위배 줄(또는 바로 윗줄)의 예외 표시 `/* MISRA-DEVIATION <규칙> 사유=… 승인=… */`"
                                 "(목업이 정한 꼴)를 인정할지 정합니다 — allow 면 사유 · 승인이 다 있는 표시를 fix 분류에서만 "
                                 f"인정(Mandatory 는 인정 안 함) · deny 면 표시를 무시합니다. 지금 표시 {markers}건.",
                          "options": [], "supported": ["allow", "deny"],
                          "write_to": "docs/기준설계.md · misra_deviation: <allow|deny>"})
    answer = {"source": "MOCK", "status": "NEEDS_CRITERIA", "questions": questions,
              "current": {"rules": chosen, "defects": len(findings), "by_rule": by_rule,
                          "by_category": _by_category(findings), "items": findings},
              "analyzed": analyzed, "notices": result.notices}
    if not (repo / "docs/기준설계.md").is_file():
        answer["detail"] = ("docs/기준설계.md 가 없습니다 — 질문의 write_to 대로 이 파일을 만들어 답을 적은 뒤 "
                            "다시 실행하세요(실습 2-④).")
    return answer


def _deviation_verdict(marker: dict, category: str, action: str, deviation_policy: str) -> tuple[bool, str]:
    if deviation_policy != "allow":
        return False, f"misra_deviation: {deviation_policy} — 표시를 인정하지 않음"
    if category == "Mandatory":
        return False, MANDATORY_NOTE
    if action != "fix":
        return False, f"예외 표시는 fix 분류에만 씀(지금 {POLICY_KEYS[category]}: {action})"
    if not marker["complete"]:
        return False, "사유 · 승인이 둘 다 있어야 인정"
    return True, f"인정 — 사유={marker['why']} · 승인={marker['by']}"


def _judge(repo: Path, criteria, findings: list[dict], result: Result, face: str) -> None:
    """분류 모드 판정 — 항목마다 처리 · 예외 표시 · blocking, findings 는 Merge 를 막는 위배만(ADR-015)."""
    policy = _policy(criteria)
    texts: dict[str, list[str] | None] = {}
    ignored = 0
    for item in findings:
        action = policy[item["category"]]
        if item["path"] not in texts:
            text = _source_text(repo, item["path"], result, face, "static analyze")
            texts[item["path"]] = None if text is None else [line.rstrip("\r") for line in text.split("\n")]
        lines = texts[item["path"]]
        marker = find_deviation(lines, item["startLine"], item["rule"]) if lines is not None else None
        deviation = None
        if marker:
            accepted, note = _deviation_verdict(marker, item["category"], action, criteria.misra_deviation)
            deviation = {"rule": marker["rule"], "why": marker["why"], "by": marker["by"],
                         "where": f"{item['path']}:{marker['line']}", "complete": marker["complete"],
                         "accepted": accepted, "note": note}
            ignored += criteria.misra_deviation == "deny"
        accepted = bool(deviation and deviation["accepted"])
        item.update(action=action, deviation=deviation,
                    blocking=action == "block" or (action == "fix" and not accepted))
    blocking = [item for item in findings if item["blocking"]]
    for index, item in enumerate(blocking, 1):
        key = POLICY_KEYS[item["category"]]
        result.findings.append(MisraFinding(id=f"STATIC-{index:03d}", where=item["where"],
                                            expected=f"MISRA {item['rule']} 준수", actual=item["actual"],
                                            fix_hint=item["fix_hint"], basis=f"{item['basis']} · 기준설계 {key}: {item['action']}",
                                            back_to="코드 수정", rule=item["rule"], category=item["category"]))
    notes = []
    if criteria.misra_max is not None:
        notes.append("misra_max 는 분류 키(misra_mandatory · misra_required · misra_advisory)가 있어 쓰지 않습니다.")
    if policy["Mandatory"] == "report":
        notes.append("misra_mandatory: report — Mandatory 위배를 Merge 에서 막지 않습니다. Mandatory 를 지키지 않으면 "
                     "MISRA 준수라 할 수 없습니다(MISRA C:2023 문서 8쪽).")
    if ignored:
        notes.append(f"misra_deviation: deny — 예외 표시 {ignored}건을 인정하지 않았습니다(위치는 metrics.items).")
    result.notices += [{"kind": "CRITERIA_NOTE", "where": "docs/기준설계.md", "message": note} for note in notes]
    result.metrics.update(mode="category", blocking=len(blocking),
                          policy={**{POLICY_KEYS[c]: v for c, v in policy.items()},
                                  "misra_deviation": criteria.misra_deviation})
    if blocking:
        result.status = "FAIL"


def analyze(repo: Path, *, face: str = "cli") -> Result:
    """Analyze src/*.c; unsupported rules are errors and parse failures are notices."""
    repo = Path(repo).resolve()
    criteria = read_criteria(repo)
    missing = _missing_keys(criteria)
    if missing:
        result = Result(check="static.analyze", status="ERROR", reason="CRITERIA_MISSING", tool=TOOL)
        result.findings.append(Finding(id="STATIC-CRITERIA", where="docs/기준설계.md",
            expected=" · ".join(f"{key}: …" for key in missing), actual="기준 없음",
            fix_hint="기준설계에 검사 규칙 · 분류별 처리 · 예외 정책을 정하세요 — 질문은 static pre-analyze 가 합니다.",
            basis="docs/기준설계.md", back_to="요구사항"))
        return result
    unsupported = sorted(set(criteria.misra_rules) - set(SUPPORTED))
    if unsupported:
        rules = ", ".join(unsupported)
        return mock_limit(repo, check="static.analyze", tool=TOOL, face=face,
                          command="static analyze", where="docs/기준설계.md",
                          detail=f"MISRA {rules} 규칙은 목업 미지원입니다. 실제 STATIC 은 검사함.")
    result = Result(check="static.analyze", status="PASS", tool=TOOL)
    findings, analyzed = _scan(repo, set(criteria.misra_rules), result, face, "static analyze")
    result.metrics = {"analyzed": analyzed, "defects": len(findings),
                      "by_rule": dict(sorted(Counter(item["rule"] for item in findings).items())),
                      "by_category": _by_category(findings), "items": findings}
    if _category_mode(criteria):
        _judge(repo, criteria, findings, result, face)
        return result
    # 하위 호환 — 분류 키가 없고 misra_max 가 있을 때만: 총건수 상한(ADR-014)
    for index, item in enumerate(findings, 1):
        result.findings.append(MisraFinding(id=f"STATIC-{index:03d}", where=item["where"],
                                       expected=f"MISRA {item['rule']} 준수", actual=item["actual"],
                                       fix_hint=item["fix_hint"], basis=item["basis"], back_to="코드 수정",
                                       rule=item["rule"], category=item["category"]))
    result.metrics["mode"] = "max"
    if len(findings) > criteria.misra_max:
        result.status = "FAIL"
    return result
