"""STATICA shaped adapter over the shared MISRA engine."""

from collections import Counter
from pathlib import Path

from vsmmock.engine.misra import SUPPORTED, analyze
from vsmmock.engine.result import mock_limit


def pre_analyze(repo: Path) -> dict:
    result = analyze(Path(repo), face="mcp")
    items = [{"path": item["path"], "startLine": item["startLine"],
              "severity": "Required", "ruleSet": "MISRA C:2023", "rule": item["rule"],
              "message": item["actual"], "fix_hint": item["fix_hint"]}
             for item in result.metrics.get("items", [])]
    by_rule = Counter(item["rule"] for item in items)
    files = sorted({item["path"] for item in items})
    return {"source": "MOCK", "ok": result.status == "PASS", "status": result.status,
            "reason": result.reason, "notices": result.notices,
            "findings": [item.__dict__ for item in result.findings],
            "analyzed": result.metrics.get("analyzed", 0),
            "defects": {"total": len(items), "files": files,
                        "topRules": [{"ruleName": rule, "ruleSet": "MISRA C:2023", "count": count}
                                     for rule, count in by_rule.most_common()],  # statica-plugin defects.py 꼴
                        "bySeverity": {"Required": len(items)}, "scope": "src/*.c", "items": items}}


def ruleset_show(repo: Path) -> dict:
    from vsmmock.engine.criteria import read_criteria

    criteria = read_criteria(Path(repo))
    if not criteria.misra_rules or criteria.misra_max is None:
        result = analyze(Path(repo), face="mcp")
        return {"source": "MOCK", "status": result.status, "reason": result.reason,
                "findings": [item.__dict__ for item in result.findings]}
    rules = criteria.misra_rules
    return {"source": "MOCK", "ruleSet": "MISRA C:2023", "rules": rules,
            "supported": list(SUPPORTED)}


def ruleset_set(repo: Path, rules: list[str]) -> dict:
    detail = f"규칙 설정 변경({', '.join(rules)})은 목업 미지원입니다. 실제 STATIC 은 검사함."
    result = mock_limit(Path(repo), check="static.ruleset-set",
                        tool={"name": "STATIC", "mimics": "statica-plugin v0.1.0 ruleset-set"},
                        face="mcp", command="ruleset-set", where="docs/기준설계.md", detail=detail)
    return {"source": result.source, "status": result.status,
            "reason": result.reason, "detail": result.detail}
