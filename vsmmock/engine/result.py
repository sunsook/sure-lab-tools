"""Common verification results shared by CLI and agent adapters."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import caselog


@dataclass
class Finding:
    id: str
    where: str
    expected: str
    actual: str
    fix_hint: str
    basis: str
    back_to: str


@dataclass
class Result:
    check: str
    status: str
    source: str = "MOCK"
    reason: str | None = None
    detail: str | None = None
    tool: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    notices: list[dict[str, str]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def exit_code(status: str) -> int:
    return {"PASS": 0, "FAIL": 1, "ERROR": 2}[status]


def unhandled_message(where: str, what: str = "",
                      outcome: str = "목업이 다루지 못해 통과 처리했습니다") -> str:
    """MOCK_UNHANDLED 공지 문장 — UI_GUIDE 꼴. 무엇을 건너뛰었는지 위치를 반드시 담는다."""
    what = what.replace("\n", " ").strip()
    if len(what) > 60:
        what = what[:60] + "…"
    target = f"{where} ({what})" if what else where
    return (f"[MOCK] 실습 목업의 한계 — {target} 은 {outcome} · "
            "사례 기록: logs/*_Mock_CaseReport.log · 목업 개선에 기여해 주셔서 감사합니다(다음 차수에 반영)")


def add_unhandled(result: Result, repo: Path, *, tool: str, face: str,
                  command: str, where: str, detail: str,
                  exception: BaseException | None = None) -> None:
    case_id = caselog.record(repo, tool=tool, face=face, command=command,
                             kind="MOCK_UNHANDLED", where=where,
                             detail=detail, exception=exception)
    result.notices.append({
        "kind": "MOCK_UNHANDLED", "where": where, "case_id": case_id,
        "message": unhandled_message(where, detail),
    })


def mock_limit(repo: Path, *, check: str, tool: dict[str, str], face: str,
               command: str, where: str, detail: str) -> Result:
    caselog.record(repo, tool=tool["name"], face=face, command=command,
                   kind="MOCK_LIMIT", where=where, detail=detail)
    return Result(check=check, status="ERROR", reason="MOCK_LIMIT",
                  detail=detail, tool=tool)
