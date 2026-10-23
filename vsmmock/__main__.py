import sys

from .faces.cli import main


if __name__ == "__main__":
    # Windows 파이프(cp949)로 읽는 에이전트도 한글을 그대로 받게 — 출력은 늘 UTF-8
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
