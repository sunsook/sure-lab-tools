"""Append-only records of mock limitations and unhandled patterns."""

import json
import os
import subprocess
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from vsmmock import __version__

# 엔진을 부른 입구 — MCP 서버면 기본값 mcp · CLI 는 main 에서 cli 로 바꾼다
FACE: ContextVar[str] = ContextVar("vsmmock_face", default="mcp")


def _run(repo: Path, *command: str) -> str | None:
    try:
        completed = subprocess.run(command, cwd=repo, capture_output=True, stdin=subprocess.DEVNULL,
                                   text=True, encoding="utf-8", timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def account(repo: Path) -> str:
    actor = os.environ.get("GITHUB_ACTOR")
    if actor:
        return actor
    name = _run(repo, "gh", "api", "user", "--jq", ".login")
    if name:
        return name
    name = _run(repo, "git", "config", "user.name")
    if name:
        return name
    print("[MOCK] 사례 로그 계정을 알 수 없습니다: UNKNOWN", file=sys.stderr)
    return "UNKNOWN"


def _snippet(repo: Path, where: str) -> str:
    path_text, _, line_text = where.rpartition(":")
    if not line_text.isdigit():
        path_text = where
        line_text = "1"
    path = (repo / path_text).resolve()
    try:
        path.relative_to(repo.resolve())
        lines = path.read_text(encoding="utf-8").splitlines()
        line = int(line_text)
        return "\n".join(lines[max(0, line - 3):line + 2])
    except (OSError, ValueError):
        return ""


def record(repo: Path, *, tool: str, face: str, command: str, kind: str,
           where: str, detail: str, exception: BaseException | None = None) -> str:
    """Append one case; logging problems never alter a verification decision."""
    case_id = uuid4().hex
    try:
        who = account(repo)
        entry = {
            "case_id": case_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "account": who,
            "tool": tool,
            "face": face,
            "command": command,
            "kind": kind,
            "where": where,
            "detail": detail,
            "exception": ({"type": type(exception).__name__,
                           "message": str(exception).splitlines()[0] if str(exception) else ""}
                          if exception else None),
            "snippet": _snippet(repo, where),
            "git": {"branch": _run(repo, "git", "branch", "--show-current") or "",
                    "sha": _run(repo, "git", "rev-parse", "HEAD") or "",
                    "dirty": bool(_run(repo, "git", "status", "--porcelain"))},
            "mock_version": __version__,
        }
        path = repo / "logs" / f"{who}_Mock_CaseReport.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except (OSError, ValueError) as error:
        print(f"[MOCK] 사례 로그 기록 실패: {error}", file=sys.stderr)
    return case_id
