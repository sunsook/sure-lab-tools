"""STATICA shaped adapter over the shared MISRA engine."""

from collections import Counter
from pathlib import Path

from vsmmock.engine.caselog import FACE
from vsmmock.engine.misra import CATEGORIES, SUPPORTED, analyze, criteria_questions
from vsmmock.engine.result import mock_limit


def pre_analyze(repo: Path) -> dict:
    asked = criteria_questions(Path(repo), face=FACE.get())  # 빠진 칸만 묻는다 — ADR-014 개정 · ADR-015
    if asked:
        return asked
    result = analyze(Path(repo), face=FACE.get())
    items = [{"path": item["path"], "startLine": item["startLine"],
              "severity": item["category"], "ruleSet": "MISRA C:2023", "rule": item["rule"],
              "message": item["actual"], "fix_hint": item["fix_hint"], "category": item["category"],
              "action": item.get("action"), "deviation": item.get("deviation")}
             for item in result.metrics.get("items", [])]
    by_rule = Counter(item["rule"] for item in items)
    by_severity = Counter(item["severity"] for item in items)
    files = sorted({item["path"] for item in items})
    return {"source": "MOCK", "ok": result.status == "PASS", "status": result.status,
            "reason": result.reason, "detail": result.detail, "notices": result.notices,
            "findings": [item.__dict__ for item in result.findings],
            "analyzed": result.metrics.get("analyzed", 0),
            "defects": {"total": len(items), "files": files,
                        "topRules": [{"ruleName": rule, "ruleSet": "MISRA C:2023", "count": count}
                                     for rule, count in by_rule.most_common()],  # statica-plugin defects.py 꼴
                        "bySeverity": {category: by_severity[category] for category in CATEGORIES
                                       if by_severity[category]},
                        "scope": "src/*.c", "items": items}}


def ruleset_show(repo: Path) -> dict:
    from vsmmock.engine.criteria import read_criteria

    asked = criteria_questions(Path(repo), face=FACE.get())
    if asked:
        return asked
    rules = read_criteria(Path(repo)).misra_rules
    return {"source": "MOCK", "ruleSet": "MISRA C:2023", "rules": rules,
            "supported": list(SUPPORTED)}


def ruleset_set(repo: Path, rules: list[str]) -> dict:
    detail = f"규칙 설정 변경({', '.join(rules)})은 목업 미지원입니다. 실제 STATIC 은 검사함."
    result = mock_limit(Path(repo), check="static.ruleset-set",
                        tool={"name": "STATIC", "mimics": "statica-plugin v0.1.0 ruleset-set"},
                        face=FACE.get(), command="ruleset-set", where="docs/기준설계.md", detail=detail)
    return {"source": result.source, "status": result.status,
            "reason": result.reason, "detail": result.detail}
