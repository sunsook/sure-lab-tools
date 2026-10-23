---
name: dvera
description: 교육용 DVERA 목업으로 CT 시험을 설계, 승인 후 생성, 실행하고 커버리지를 확인한다.
---

# DVERA CT

이 스킬의 도구는 `source: "MOCK"`인 교육용 목업이다. 저장소 루트를 `repo`로 전달한다.

- 대상 함수를 찾을 때 `ct_find_functions`를 호출하고 반환된 `signatureHash`를 쓴다.
- 요구사항 기반 시험은 `ct_ai_generate_test(repo, signatureHash, specs=["SR-..."])`, 구조 기반 시험은 `specs` 없이 호출한다.
- `NEEDS_APPROVAL`이면 `spec.rows`의 전제, 입력, 기대, `basis`, 기존 시험의 `stale`을 사람에게 표로 그대로 보여 준다. 생성된 시험 정의를 요약할 때 필드(`expected` · `expected_source` · `basis`)를 그대로 보여 주고, 어느 시험이 요구사항과 어긋나는지 에이전트가 먼저 판정하거나 짚지 않는다 — 생성 시험의 기대값을 요구사항과 대조하는 것은 사람의 검토 몫이다(실습 3-③ 「생성시험검토」). 명시적 승인 전에는 `approved_spec`을 전달하거나 시험 정의를 생성하지 않는다. 승인 후 현재 응답의 `spec.id`를 `approved_spec`으로 전달한다. `SPEC_STALE`이면 새 표로 다시 검토받는다.
- `NEEDS_CRITERIA`의 `questions`를 그대로 사람에게 묻는다. 사람이 답을 `docs/기준설계.md`에 `write_to` 형식으로 적게 하고 재실행한다. 답이나 기대값을 대신 정하지 않는다.
- 실행은 `ct_execute_test`, 결과 조회는 `ct_get_test_results`, 분기 커버리지는 `ct_get_coverage`, 환경 점검은 `dvera_check_environment`를 쓴다. Windows 커버리지 `MOCK_LIMIT`은 측정값으로 간주하지 않는다.
- `MOCK_LIMIT`은 ERROR로 전하고 `detail`과 가능한 실제 도구를 설명한다. `MOCK_UNHANDLED`는 `[MOCK] 실습 목업의 한계 — <where> 은 목업이 다루지 못해 통과 처리했습니다 · 사례 기록: logs/<계정>_Mock_CaseReport.log · 목업 개선에 기여해 주셔서 감사합니다(다음 차수에 반영)`으로 공지한다. 다른 항목의 판정은 그대로 둔다.
- 결론에는 반환 결과의 `basis`와 파일:줄을 인용한다. 근거가 없으면 단정하지 않는다.
