---
name: statica
description: 교육용 STATIC 목업으로 MISRA 규칙을 확인하고 결함 위치와 교정 힌트를 검토한다.
---

# STATICA / STATIC

`repo`에는 저장소 루트를 준다. 모든 반환은 `source: "MOCK"`인 목업 결과다.

- 규칙을 확인할 때 `statica_ruleset_show`, 소스를 분석할 때 `statica_pre_analyze`를 호출한다. `defects.items`의 규칙, 파일, 줄, `fix_hint`를 사람에게 보여 준다. 소스를 자동 수정하지 않는다.
- 규칙을 바꾸려는 요청에는 목업에서 `statica_ruleset_set` 이 `MOCK_LIMIT` 임을 알리고, 사람이 `docs/기준설계.md` 의 `misra_rules` · `misra_max` 줄을 직접 고치게 안내한다. 에이전트가 기준설계를 대신 고치지 않는다.
- 결함을 고치는 일은 사람(또는 사람이 승인한 수정 작업)의 몫이다 — 이 스킬은 위치 · 근거 · `fix_hint` 만 전한다.
- `MOCK_LIMIT`은 `detail`을 포함해 ERROR라고 알린다. `MOCK_UNHANDLED`는 `[MOCK] 실습 목업의 한계 — <where> 은 목업이 다루지 못해 통과 처리했습니다 · 사례 기록: logs/<계정>_Mock_CaseReport.log · 목업 개선에 기여해 주셔서 감사합니다(다음 차수에 반영)`으로 공지한다.
- 결론에는 결과의 `basis` 또는 결함의 파일:줄을 인용하고, 근거가 없으면 판정을 만들지 않는다.
