"""CLI adapter for the shared verification engine."""

import argparse
import json
import sys
from pathlib import Path

from vsmmock.agentic import dvera, statica
from vsmmock.engine.caselog import FACE
from vsmmock.engine.criteria import check_criteria
from vsmmock.engine.coverage import measure
from vsmmock.engine.misra import analyze
from vsmmock.engine.result import Result, exit_code
from vsmmock.engine.runner import run
from vsmmock.engine.trace import trace


CONVERSATION = {("ct", "find"), ("ct", "spec"), ("ct", "generate"), ("ct", "pre-check"),
                ("static", "pre-analyze")}  # 생성 대화 명령 — 게이트 아님(ADR-013 · ADR-014 · ADR-016)


def _signature(repo: Path, function: str) -> tuple[str | None, dict | None]:
    """함수 이름 또는 signatureHash → signatureHash (입력 변환만 · 판정 없음)."""
    found = dvera.find_functions(repo)
    matches = [item for item in found["functions"] if function in (item["name"], item["signatureHash"])]
    if len(matches) == 1:
        return matches[0]["signatureHash"], None
    detail = (f"함수를 찾지 못했습니다: {function} — ct find 로 이름을 확인하세요." if not matches else
              f"같은 이름의 함수가 여럿입니다: {function} — ct find 의 signatureHash 로 다시 부르세요.")
    return None, {"source": "MOCK", "status": "ERROR", "reason": "INPUT_BROKEN", "detail": detail,
                  "notices": found["notices"]}


def _conversation(repo: Path, args: argparse.Namespace) -> int:
    """agentic(dvera · statica) 결과 dict 를 그대로 stdout(JSON) · --out 에 낸다. ERROR 만 종료 2."""
    try:
        if args.tool == "static":
            answer = statica.pre_analyze(repo)
        elif args.action == "pre-check":
            answer = dvera.pre_check(repo)
        elif args.action == "find":
            answer = dvera.find_functions(repo, args.query)
        else:
            signature, answer = _signature(repo, args.function)
            if signature:
                specs = ([part for item in args.specs for part in item.split(",") if part]
                         if args.specs else None)
                approved = getattr(args, "approved_spec", None)
                answer = dvera.ai_generate_test(repo, signature, specs, approved)
    except (OSError, ValueError) as error:
        answer = {"source": "MOCK", "status": "ERROR", "reason": "INPUT_BROKEN", "detail": str(error)}
    text = json.dumps(answer, ensure_ascii=False, indent=2)
    target = repo / args.out
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 2 if answer.get("status") == "ERROR" else 0


def main(argv: list[str] | None = None) -> int:
    token = FACE.set("cli")
    try:
        return _main(argv)
    finally:
        FACE.reset(token)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vsmmock")
    tools = parser.add_subparsers(dest="tool", required=True)
    ct = tools.add_parser("ct")
    actions = ct.add_subparsers(dest="action", required=True)
    find_command = actions.add_parser("find", help="함수 · signatureHash 찾기")
    find_command.add_argument("query", nargs="?", default="")
    find_command.add_argument("--out", default="out/ct-gen.json")
    spec_command = actions.add_parser("spec", help="시험 명세 — 질문 또는 승인할 표(파일 안 씀)")
    spec_command.add_argument("function", help="함수 이름 또는 signatureHash")
    spec_command.add_argument("--specs", nargs="+", help="요구사항 ID (없으면 구조 기반)")
    spec_command.add_argument("--out", default="out/ct-gen.json")
    generate_command = actions.add_parser("generate", help="승인한 명세로 ct/*.json 생성")
    generate_command.add_argument("function", help="함수 이름 또는 signatureHash")
    generate_command.add_argument("--specs", nargs="+", required=True)
    generate_command.add_argument("--approved-spec", required=True, help="ct spec 이 낸 spec.id")
    generate_command.add_argument("--out", default="out/ct-gen.json")
    criterion = actions.add_parser("check-criteria")
    criterion.add_argument("--out", default="out/ct.json")
    run_command = actions.add_parser("run")
    run_command.add_argument("--out", default="out/ct.json")
    coverage_command = actions.add_parser("coverage")
    coverage_command.add_argument("--out", default="out/ct.json")
    pre_check = actions.add_parser("pre-check", help="커버리지 기준 사전 점검 — 빠진 칸만 질문(파일 안 씀)")
    pre_check.add_argument("--out", default="out/ct-pre.json")
    static = tools.add_parser("static")
    static_actions = static.add_subparsers(dest="action", required=True)
    static_analyze = static_actions.add_parser("analyze")
    static_analyze.add_argument("--out", default="out/static.json")
    static_pre = static_actions.add_parser("pre-analyze", help="결함 위치 · fix_hint — 기준 줄이 없으면 질문")
    static_pre.add_argument("--out", default="out/static-pre.json")
    ads = tools.add_parser("ads")
    ads_actions = ads.add_subparsers(dest="action", required=True)
    ads_trace = ads_actions.add_parser("trace")
    ads_trace.add_argument("--out", default="out/ads.json")
    for subparsers in (actions, static_actions, ads_actions):
        for command in subparsers.choices.values():
            command.add_argument("--repo", help="검사할 저장소 경로(없으면 현재 폴더) — PR head worktree 등")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve() if args.repo else Path.cwd()
    if not repo.is_dir():
        parser.error(f"--repo 경로가 폴더가 아닙니다: {args.repo}")
    if (args.tool, args.action) in CONVERSATION:
        return _conversation(repo, args)
    try:
        if args.tool == "ads":
            result = trace(repo)
        elif args.tool == "static":
            result = analyze(repo)
        elif args.action == "check-criteria":
            result = check_criteria(repo)
        elif args.action == "coverage":
            result = measure(repo)
        else:
            result = run(repo, junit_path=repo / "out/ct-junit.xml")
    except (OSError, ValueError) as error:
        tool = ({"name": "ADS", "mimics": "ADS trace_check ID chain"} if args.tool == "ads" else
                {"name": "STATIC", "mimics": "statica-plugin v0.1.0 pre-analyze"} if args.tool == "static"
                else {"name": "DVERA", "mimics": "dvera-plugin v0.1.4 ct_get_test_results"})
        result = Result(check=f"{args.tool}.{args.action}", status="ERROR", reason="INPUT_BROKEN",
                        detail=str(error), tool=tool)
    target = repo / args.out
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(result.to_json(), encoding="utf-8")
    tag = {"static": "STATIC", "ads": "ADS"}.get(args.tool, "CT")
    if result.status == "ERROR":
        # 검사 자체 실패 — 「결함 0건」처럼 통과로 읽히는 집계 줄을 찍지 않는다
        print(f"[{tag}] {args.action} ERROR · {result.reason} — {result.detail or ''}".rstrip(" —"))
    elif args.tool == "static":
        line = (f"[STATIC] {result.metrics.get('analyzed', 0)}개 대상 분석 완료 · "
                f"결함 {result.metrics.get('defects', len(result.findings))}건")
        if result.metrics.get("mode") == "category":  # 분류 모드 — findings = Merge 막는 위배(ADR-015)
            line += f" · Merge 막는 위배 {len(result.findings)}건"
        print(line)
    elif args.tool == "ads":
        print(f"[ADS] 요구사항 {result.metrics.get('requirements', 0)} · 연결 {result.metrics.get('linked', 0)} · 누락 {result.metrics.get('missing', 0)}")
    else:
        print(f"[CT] {args.action} {result.status} · 발견 {len(result.findings)}건")
    for notice in result.notices:
        print(notice.get("message", ""))
    return exit_code(result.status)
