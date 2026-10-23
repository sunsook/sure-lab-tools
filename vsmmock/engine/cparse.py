"""Discover C functions from preprocessed source with pycparser."""

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pycparser import c_ast, c_generator, c_parser
from pycparser.c_parser import ParseError

from .caselog import FACE, record
from .result import unhandled_message

FAKE_LIBC = Path(__file__).with_name("fake_libc")


def _parse_source(repo: Path, source: Path):
    command = [sys.executable, "-m", "ziglang", "cc", "-E", "-std=c11", "-nostdinc",
               "-I", str(FAKE_LIBC), "-I", str(repo / "include"), str(source)]
    with tempfile.TemporaryDirectory(prefix="vsmmock_cpp_") as cache:
        env = {**os.environ, "ZIG_LOCAL_CACHE_DIR": cache}  # 전역 캐시는 기본 위치(runner.py 주석 참고)
        preprocessed = subprocess.run(command, cwd=repo, capture_output=True, stdin=subprocess.DEVNULL, text=True,
                                     encoding="utf-8", env=env)
    if preprocessed.returncode:
        raise ValueError(f"{source}: {preprocessed.stderr[:500]}")
    return c_parser.CParser().parse(preprocessed.stdout, filename=str(source))


def _safe_parse(repo: Path, source: Path, notices: list[dict] | None, command: str):
    try:
        return _parse_source(repo, source)
    except (OSError, ValueError, ParseError) as error:
        where = source.relative_to(repo).as_posix() + ":1"
        if notices is not None and any(item.get("where") == where for item in notices):
            return None
        case_id = record(repo, tool="DVERA", face=FACE.get(), command=command,
                         kind="MOCK_UNHANDLED", where=where, detail=str(error), exception=error)
        if notices is not None:
            notices.append({"kind": "MOCK_UNHANDLED", "where": where, "case_id": case_id,
                            "message": unhandled_message(where, "목업 파서가 읽지 못한 파일",
                                                         "목업이 다루지 못해 건너뛰었습니다")})
        return None


def functions(repo: Path, *, include_main: bool = False,
              notices: list[dict] | None = None) -> list[dict[str, str]]:
    generator = c_generator.CGenerator()
    found = []
    for source in sorted((repo / "src").glob("*.c")):
        if not include_main and source.name == "main.c":
            continue
        tree = _safe_parse(repo, source, notices, "ct_find_functions")
        if tree is None:
            continue
        for node in tree.ext:
            if not isinstance(node, c_ast.FuncDef):
                continue
            decl = node.decl
            signature = generator.visit(decl)
            signature = re.sub(r"\s+", " ", signature).strip()
            relative = source.relative_to(repo).as_posix()
            found.append({"name": decl.name, "signature": signature,
                          "signatureHash": hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16],
                          "sourceFile": relative, "where": f"{relative}:{decl.coord.line}"})
    return found


def function_shapes(repo: Path, source_file: str | None = None,
                    notices: list[dict] | None = None) -> dict[str, dict]:
    """Return definition coordinates, parameter types, and typedef enum members."""
    shapes = {}
    for source in sorted((repo / "src").glob("*.c")):
        if source_file and source.relative_to(repo).as_posix() != source_file:
            continue
        if source.name == "main.c":
            continue
        tree = _safe_parse(repo, source, notices, "ct_ai_generate_test")
        if tree is None:
            continue
        enums = {}
        for node in tree.ext:
            if isinstance(node, c_ast.Typedef):
                type_node = node.type
                if isinstance(type_node, c_ast.TypeDecl) and isinstance(type_node.type, c_ast.Enum):
                    values = type_node.type.values
                    enums[node.name] = [member.name for member in values.enumerators] if values else []
        for node in tree.ext:
            if not isinstance(node, c_ast.FuncDef):
                continue
            declaration = node.decl.type
            parameters = []
            for parameter in declaration.args.params if declaration.args else []:
                if isinstance(parameter, c_ast.EllipsisParam):
                    parameters.append({"name": "...", "type": "..."})
                elif not (isinstance(parameter.type, c_ast.TypeDecl)
                          and isinstance(parameter.type.type, c_ast.IdentifierType)
                          and parameter.type.type.names == ["void"]):
                    parameters.append({"name": parameter.name,
                                       "type": (" ".join(parameter.type.type.names)
                                                if isinstance(parameter.type, c_ast.TypeDecl)
                                                and isinstance(parameter.type.type, c_ast.IdentifierType)
                                                else "")})
            return_node = declaration.type
            return_type = (" ".join(return_node.type.names)
                           if isinstance(return_node, c_ast.TypeDecl)
                           and isinstance(return_node.type, c_ast.IdentifierType) else "")
            relative = source.relative_to(repo).as_posix()
            shapes[node.decl.name] = {"parameters": parameters, "return_type": return_type,
                                      "enum_members": enums.get(return_type, []),
                                      "where": f"{relative}:{node.decl.coord.line}"}
    return shapes


def find_functions(repo: Path, *, include_main: bool = False) -> list[dict[str, str]]:
    return functions(repo, include_main=include_main)


DECISIONS = (c_ast.If, c_ast.For, c_ast.TernaryOp, c_ast.Case)  # branches 의 Visitor 와 같은 판정 지점


def decision_sites(repo: Path, notices: list[dict] | None = None) -> dict[str, int]:
    """main.c 를 뺀 src/*.c 마다 함수 본문의 판정 지점 수 — ct pre-check 근거(gcov 분기 정의와 다를 수 있음)."""
    def walk(node):
        yield node
        for _, child in node.children():
            yield from walk(child)

    counts = {}
    for source in sorted((repo / "src").glob("*.c")):
        if source.name == "main.c":
            continue
        tree = _safe_parse(repo, source, notices, "ct pre-check")
        if tree is None:
            continue
        bodies = [node.body for node in tree.ext if isinstance(node, c_ast.FuncDef)
                  and Path(node.decl.coord.file.replace("\\", "/")).name == source.name]
        counts[source.relative_to(repo).as_posix()] = sum(isinstance(item, DECISIONS)
                                                          for body in bodies for item in walk(body))
    return counts


def branches(repo: Path, function: str, notices: list[dict] | None = None) -> list[dict]:
    """Return AST decision sites with both sides, using original source coordinates."""
    result = []
    for source in sorted((repo / "src").glob("*.c")):
        tree = _safe_parse(repo, source, notices, "ct_ai_generate_test")
        if tree is None:
            continue
        for node in tree.ext:
            if not isinstance(node, c_ast.FuncDef) or node.decl.name != function:
                continue
            class Visitor(c_ast.NodeVisitor):
                def _decision(self, item, kind):
                    where = f"{source.relative_to(repo).as_posix()}:{item.coord.line}"
                    for side in ("T", "F"):
                        result.append({"where": where, "side": side, "kind": kind})
                    self.generic_visit(item)

                def visit_If(self, item):
                    self._decision(item, "if")

                def visit_For(self, item):
                    self._decision(item, "for")

                def visit_TernaryOp(self, item):
                    self._decision(item, "?:")

                def visit_Case(self, item):
                    self._decision(item, "case")

            Visitor().visit(node.body)
    return result
