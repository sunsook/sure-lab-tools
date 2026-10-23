"""ADS shaped document and trace adapters."""

from pathlib import Path

from vsmmock.engine.requirements import read_requirements
from vsmmock.engine.testdef import read_definitions
from vsmmock.engine.trace import trace as engine_trace


def trace(repo: Path) -> dict:
    result = engine_trace(Path(repo))
    return {"source": result.source, "status": result.status, "reason": result.reason,
            "links": result.metrics.get("links", []),
            "unlinked_requirements": result.metrics.get("unlinked_requirements", []),
            "orphan_tests": result.metrics.get("orphan_tests", []),
            "changed_requirements": result.metrics.get("changed_requirements", []),
            "changed_tests": result.metrics.get("changed_tests", [])}


def generate_docs(repo: Path) -> dict:
    repo = Path(repo)
    requirements = read_requirements(repo)
    traced = engine_trace(repo)
    if traced.status == "ERROR":
        return {"source": "MOCK", "status": "ERROR", "reason": traced.reason,
                "findings": [finding.__dict__ for finding in traced.findings]}
    definitions = read_definitions(repo)
    chain = traced.metrics["links"]
    destination = repo / "docs" / "generated"
    destination.mkdir(parents=True, exist_ok=True)
    srs = ["# SRS", "", "generated_by: engine", "", "| SR | SRS | 요구사항 | 관련 구현 |",
           "|---|---|---|---|"]
    for link in chain:
        requirement = requirements[link["sr"]]
        srs.append(f"| {link['sr']} | {link['srs']} | {requirement.text} | {requirement.implementation} |")
    specs = ["# TestSpec", "", "generated_by: engine", "",
             "| 시험 ID | SR | 함수 | 입력 | 기대 | 근거 |", "|---|---|---|---|---|---|"]
    for definition in definitions:
        specs.append(f"| {definition.id} | {definition.req} | {definition.function} | "
                     f"{definition.inputs} | {definition.expected} | {definition.basis} |")
    for link in chain:
        for test_id in link["tests"]:
            if test_id.startswith("TC-"):
                specs.append(f"| {test_id} | {link['sr']} | | | | |")
    (destination / "SRS.md").write_text("\n".join(srs) + "\n", encoding="utf-8")
    (destination / "TestSpec.md").write_text("\n".join(specs) + "\n", encoding="utf-8")
    return {"source": "MOCK", "status": "PASS", "generated_by": "engine",
            "created": ["docs/generated/SRS.md", "docs/generated/TestSpec.md"], "chain": chain}
