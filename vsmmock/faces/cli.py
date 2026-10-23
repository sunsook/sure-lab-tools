"""CLI adapter for the shared verification engine."""

import argparse
import sys
from pathlib import Path

from vsmmock.engine.criteria import check_criteria
from vsmmock.engine.coverage import measure
from vsmmock.engine.misra import analyze
from vsmmock.engine.result import Result, exit_code
from vsmmock.engine.runner import run
from vsmmock.engine.trace import trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vsmmock")
    tools = parser.add_subparsers(dest="tool", required=True)
    ct = tools.add_parser("ct")
    actions = ct.add_subparsers(dest="action", required=True)
    criterion = actions.add_parser("check-criteria")
    criterion.add_argument("--out", default="out/ct.json")
    run_command = actions.add_parser("run")
    run_command.add_argument("--out", default="out/ct.json")
    coverage_command = actions.add_parser("coverage")
    coverage_command.add_argument("--out", default="out/ct.json")
    static = tools.add_parser("static")
    static_actions = static.add_subparsers(dest="action", required=True)
    static_analyze = static_actions.add_parser("analyze")
    static_analyze.add_argument("--out", default="out/static.json")
    ads = tools.add_parser("ads")
    ads_actions = ads.add_subparsers(dest="action", required=True)
    ads_trace = ads_actions.add_parser("trace")
    ads_trace.add_argument("--out", default="out/ads.json")
    args = parser.parse_args(argv)
    repo = Path.cwd()
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
        print(f"[STATIC] {result.metrics.get('analyzed', 0)}개 대상 분석 완료 · 결함 {len(result.findings)}건")
    elif args.tool == "ads":
        print(f"[ADS] 요구사항 {result.metrics.get('requirements', 0)} · 연결 {result.metrics.get('linked', 0)} · 누락 {result.metrics.get('missing', 0)}")
    else:
        print(f"[CT] {args.action} {result.status} · 발견 {len(result.findings)}건")
    for notice in result.notices:
        print(notice.get("message", ""))
    return exit_code(result.status)
