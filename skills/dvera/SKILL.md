---
name: dvera
description: 교육용 CT 목업(DVERA)으로 요구사항 기반 CT 시험을 설계하고, 사람 승인 뒤 생성 · 실행하고 기준 대조와 커버리지를 확인한다.
---

# CT 목업 (DVERA)

이 스킬의 도구는 `source: "MOCK"`인 교육용 목업이다. 명령은 저장소 루트에서 Bash 로 실행하고 결과 JSON(stdout · `out/ct-gen.json`)을 그대로 읽는다. MCP 등록 없이 동작한다.

- 대상 함수를 찾을 때 `python -m vsmmock ct find <이름 일부>`를 실행한다 — `functions[]`의 `name` · `signatureHash` · `where`.
- 요구사항 기반 시험 명세는 `python -m vsmmock ct spec <함수 이름> --specs SR-...`(여러 개면 공백으로 이어 쓴다), 구조 기반은 `--specs` 없이 실행한다. 이 단계는 파일을 쓰지 않는다.
- `NEEDS_CRITERIA`이면 `questions`의 `sr` · `missing` · `why` · `options` · `write_to`를 그대로 사람에게 묻는다. 사람이 고른 답을 `docs/기준설계.md`에 `write_to` 형식(백틱 안 `키: 값`)으로 적게 하고 `ct spec`을 다시 실행한다. `detail`이 파일이 없다고 하면 사람의 답으로 그 파일을 만든다. 답이나 기대값을 대신 정하지 않는다 — `options`가 비어 있으면 후보를 지어내지 말고 사람에게 값을 받는다.
- `NEEDS_APPROVAL`이면 `spec.rows`의 입력, 기대, `basis`, 기존 시험의 `spec.stale`을 사람에게 표로 그대로 보여 주고 멈춘다. 명시적 승인 전에는 생성하지 않는다. 승인 후 `python -m vsmmock ct generate <함수 이름> --specs <같은 SR> --approved-spec <spec.id>`를 실행한다. `SPEC_STALE`이면 `ct spec`을 다시 실행해 새 표로 다시 검토받는다.
- 생성된 시험 정의(`ct/*.json`)를 요약할 때 필드(`expected` · `expected_source` · `basis`)를 그대로 보여 주고, 어느 시험이 요구사항과 어긋나는지 에이전트가 먼저 판정하거나 짚지 않는다 — 생성 시험의 기대값을 요구사항과 대조하는 것은 사람의 검토 몫이다.
- 생성 시험은 `ct/*.json`(시험 정의)이다 — `tests/TC-*.c`와 함께 `ct run`이 빌드 · 실행한다. 시험을 셀 때 `tests/*.c`만 보지 말고, 기준 시험이 다 있는지는 파일을 세지 말고 `python -m vsmmock ct check-criteria`로 본다.
- `ct find` · `ct spec` · `ct generate`의 종료 코드는 `ERROR`만 2다. `NEEDS_CRITERIA` · `NEEDS_APPROVAL`은 실패가 아니라 다음 대화 단계다.
- 「지금 기준설계로 충분한지」 묻는 요청에는 `python -m vsmmock ct pre-check`(결과 stdout · `out/ct-pre.json`)를 실행한다 — 커버리지 목표(`branch_target`) · 대상 소스(`branch_scope`) · 커버리지 미달 예외(`coverage_exception`) 중 빠진 칸만 `NEEDS_CRITERIA`로 묻는다. 질문을 그대로 묻고 사람이 고른 답을 `write_to` 형식으로 적게 한 뒤 다시 실행한다. `PASS`면 커버리지 기준은 찼다 — 시험 기준은 `next` 대로 `ct spec`이 SR 마다 묻는다.
- 기준 대조는 `python -m vsmmock ct check-criteria`, 실행은 `python -m vsmmock ct run`, 분기 커버리지는 `python -m vsmmock ct coverage`를 쓴다(결과 `out/ct.json` · 종료 코드 0 문제 없음 · 1 FAIL · 2 ERROR).
- 커버리지 `MOCK_LIMIT`은 「이 자리(gcc 없는 PC)에서 못 잰 것」이다 — 통과도 실패도 아니다. 리뷰 · 보고에는 「미검증 — CI 에서 잰다」로 적고 판정 근거로 쓰지 않는다. `COVERAGE_UNCHANGED`는 커버리지 입력이 main 과 같아 막지 않았다는 뜻이다(측정은 CI). 미루기 기록은 기준설계 `coverage_exception: allow`일 때만 인정되며, 인정하지 않았으면 `CRITERIA_NOTE`의 `message`를 그대로 전한다.
- 다른 폴더(예: PR head 를 꺼낸 worktree)를 검사할 때는 `--repo <경로>`를 붙인다 — 결과 파일은 그 폴더의 `out/`에 생긴다.
- `MOCK_LIMIT`은 ERROR로 전하고 `detail`과 가능한 실제 도구를 설명한다. `MOCK_UNHANDLED`는 `[MOCK] 실습 목업의 한계 — <where> 은 목업이 다루지 못해 통과 처리했습니다 · 사례 기록: logs/<계정>_Mock_CaseReport.log · 목업 개선에 기여해 주셔서 감사합니다(다음 차수에 반영)`으로 공지한다. 다른 항목의 판정은 그대로 둔다.
- 결론에는 반환 결과의 `basis`와 파일:줄을 인용한다. 근거가 없으면 단정하지 않는다.
- MCP 서버를 따로 등록한 환경이면 같은 함수가 `ct_find_functions` · `ct_ai_generate_test`(`approved_spec`) 이름으로도 있다 — 결과는 같다.
