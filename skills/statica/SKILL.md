---
name: statica
description: 교육용 STATIC 목업(STATICA)으로 MISRA 규칙 위배 위치와 교정 힌트를 확인한다.
---

# STATIC 목업 (STATICA)

모든 결과는 `source: "MOCK"`인 목업 결과다. 명령은 저장소 루트에서 Bash 로 실행한다. MCP 등록 없이 동작한다.

- 소스를 분석할 때 `python -m vsmmock static analyze`를 실행하고 `out/static.json`의 `findings`(규칙 `rule` · 위치 `where` · `fix_hint` · `basis`)를 사람에게 보여 준다. 소스를 자동 수정하지 않는다.
- 검사 규칙과 허용 결함 수는 `docs/기준설계.md`의 `misra_rules` · `misra_max` 줄이다. 규칙을 바꾸려는 요청에는 사람이 그 줄을 직접 고치게 안내한다. 에이전트가 기준설계를 대신 고치지 않는다. 목업이 지원하지 않는 규칙은 `MOCK_LIMIT`이다.
- 결함을 고치는 일은 사람(또는 사람이 승인한 수정 작업)의 몫이다 — 이 스킬은 위치 · 근거 · `fix_hint` 만 전한다.
- `MOCK_LIMIT`은 `detail`을 포함해 ERROR라고 알린다. `MOCK_UNHANDLED`는 `[MOCK] 실습 목업의 한계 — <where> 은 목업이 다루지 못해 통과 처리했습니다 · 사례 기록: logs/<계정>_Mock_CaseReport.log · 목업 개선에 기여해 주셔서 감사합니다(다음 차수에 반영)`으로 공지한다.
- 결론에는 결과의 `basis` 또는 결함의 파일:줄을 인용하고, 근거가 없으면 판정을 만들지 않는다.
- MCP 서버를 따로 등록한 환경이면 `statica_pre_analyze` · `statica_ruleset_show` · `statica_ruleset_set`으로도 같은 결과를 받는다.
