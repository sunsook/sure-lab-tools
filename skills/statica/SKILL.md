---
name: statica
description: 교육용 STATIC 목업(STATICA)으로 MISRA 규칙 위배 위치와 교정 힌트를 확인한다.
---

# STATIC 목업 (STATICA)

모든 결과는 `source: "MOCK"`인 목업 결과다. 명령은 저장소 루트에서 Bash 로 실행한다. MCP 등록 없이 동작한다.

- 소스를 분석할 때 `python -m vsmmock static pre-analyze`를 실행한다(결과 JSON 은 stdout · `out/static-pre.json`). 소스를 자동 수정하지 않는다.
- `NEEDS_CRITERIA`이면 `questions`의 `missing` · `why` · `supported` · `write_to`를 그대로 사람에게 묻는다 — 검사 규칙(`misra_rules`) · 분류별 처리(`misra_mandatory` · `misra_required` · `misra_advisory` = `block` · `fix` · `report`) · 예외 인정(`misra_deviation` = `allow` · `deny`) 중 빠진 칸만 나온다. `current`(지금 코드의 위배 건수 · 규칙별 · 분류별 집계)는 근거로 보여 주되, 값은 사람이 고른다 — 에이전트가 값을 정하거나 추천하지 않는다. 사람이 고른 답을 `docs/기준설계.md`에 `write_to` 형식(백틱 안 `키: 값`)으로 적게 하고 다시 실행한다.
- 기준이 있으면 `defects.items`를 **분류(`category`) → 규칙(`rule`) → 위치(`path:startLine`)** 로 묶어 `fix_hint`와 함께 보여 준다 — 같은 규칙의 위배를 흩어 놓지 않는다. 판정은 `python -m vsmmock static analyze`(결과 `out/static.json` · 종료 코드 0 PASS · 1 FAIL · 2 ERROR)다. 분류별 처리가 적혀 있으면 `block`은 하나라도 있으면 FAIL, `fix`는 고치거나 인정된 예외 표시가 있어야 통과, `report`는 목록에만 — `findings`는 Merge를 막는 위배만이고, 보고만 · 인정된 예외는 `metrics.items`(pre-analyze 는 `defects.items`의 `action` · `deviation`)에 있다. 분류 키가 하나도 없을 때만 옛 방식(위배 수가 `misra_max`를 넘으면 FAIL)이다.
- 규칙이나 처리 · 예외 정책을 바꾸려는 요청에는 사람이 `docs/기준설계.md`의 해당 줄을 직접 고치게 안내한다. 예외 표시 `/* MISRA-DEVIATION <규칙> 사유=… 승인=… */`(목업이 정한 꼴 · 위배 줄 끝 또는 바로 윗줄)도 사람이 단다 — 에이전트가 표시를 대신 달거나 사유 · 승인을 채우지 않는다. Mandatory 위배는 표시를 달아도 인정되지 않는다. 에이전트가 기준설계를 대신 고치지 않는다. 목업이 지원하지 않는 규칙은 `MOCK_LIMIT`이다.
- `notices`의 `CRITERIA_NOTE`(쓰지 않은 기준 · Mandatory 를 report 로 둠 · deny 로 무시한 표시)는 `message`를 그대로 전한다.
- 결함을 고치는 일은 사람(또는 사람이 승인한 수정 작업)의 몫이다 — 이 스킬은 위치 · 근거 · `fix_hint` 만 전한다.
- `MOCK_LIMIT`은 `detail`을 포함해 ERROR라고 알린다. `MOCK_UNHANDLED`는 `[MOCK] 실습 목업의 한계 — <where> 은 목업이 다루지 못해 통과 처리했습니다 · 사례 기록: logs/<계정>_Mock_CaseReport.log · 목업 개선에 기여해 주셔서 감사합니다(다음 차수에 반영)`으로 공지한다.
- 결론에는 결과의 `basis` 또는 결함의 파일:줄을 인용하고, 근거가 없으면 판정을 만들지 않는다.
- 다른 폴더(예: PR head 를 꺼낸 worktree)를 검사할 때는 `--repo <경로>`를 붙인다 — 결과 파일은 그 폴더의 `out/`에 생긴다.
- MCP 서버를 따로 등록한 환경이면 `statica_pre_analyze` · `statica_ruleset_show` · `statica_ruleset_set`으로도 같은 결과를 받는다.
