---
name: ads
description: 교육용 ADS 목업으로 요구사항과 시험 ID의 추적 관계를 확인하고 문서를 만든다.
---

# ADS

`repo`에는 저장소 루트를 준다. 모든 반환은 `source: "MOCK"`인 목업 결과다.

- 요구사항과 시험의 연결, 고아 시험, 변경된 요구사항을 확인할 때 `ads_trace`를 호출한다. 생성된 SRS와 Test Spec이 필요할 때 `ads_generate_docs`를 호출하고 `created`를 보고한다.
- 추적 누락(`@req` 없음)은 어느 시험 파일 몇 번째 줄인지 그대로 전하고, 어느 SR 에 연결할지는 사람이 정하게 한다. 에이전트가 `@req` 를 추측해 붙이지 않는다.
- 시험 생성 요청은 이 스킬의 일이 아니다 — DVERA(`/dvera`)를 쓰라고 안내한다.
- `MOCK_LIMIT`은 ERROR와 `detail`을 알린다. `MOCK_UNHANDLED`는 `[MOCK] 실습 목업의 한계 — <where> 은 목업이 다루지 못해 통과 처리했습니다 · 사례 기록: logs/<계정>_Mock_CaseReport.log · 목업 개선에 기여해 주셔서 감사합니다(다음 차수에 반영)`으로 공지한다.
- 결론에는 반환된 `basis`나 SR·SRS·시험 ID 및 파일:줄 근거를 인용한다.
