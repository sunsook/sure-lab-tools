---
name: ads
description: 자사 검증 도구 ADS 가 무엇을 하는 도구인지 설명한다(요구사항 문서 생성 · 추적성). 이번 실습에서는 ADS 를 실행하지 않는다.
---

# ADS — 도구 설명 전용

이번 실습에서 ADS 는 **설명만** 한다. 사람이 ADS 를 물으면 아래 내용으로 설명하고, 목업 명령을 실행하지 않는다.

- **무엇을 하는 도구인가** — 요구사항에서 SRS → SAD → SDD → 코드 → Test Spec → Test Case 를 단계별로 만들고(ALIRA AI), 단계 사이 식별자 사슬(`SR-001 → SRS_… → SAD_… → SWU_… → …_TC_…`)이 끊김 없이 이어졌는지 게이트로 확인한다(문서 생성 · 추적성).
- **실제 제품과의 관계** — ADS 는 공개 저장소가 없어 교육자료 시연 자료(1차수 3일차 ADS 기능 소개 · `ads-시연-261008`)를 근거로 한다. 실습 도구 묶음의 ADS 목업은 그 흐름 중 SRS · Test Spec 조립과 ID 사슬 확인만 흉내 낸 것이다 — SAD · SDD · 코드 단계 문서는 없다. 자세한 표: https://github.com/sunsook/sure-lab-tools/blob/main/tools/ads/README.md
- **실습에서는 부르지 않는다** — `ads_generate_docs` · `ads_trace` · `python -m vsmmock ads trace` 를 실행하지 않는다. 사람이 실행을 원하면 이번 실습 범위 밖이라고 알리고 위 README 를 안내한다.
- **시험 생성은 CT 목업** — 시험을 만들거나 요구사항 기반 시험을 설계하는 요청은 CT 목업(`/dvera`)으로, 정적분석은 STATIC 목업(`/statica`)으로 안내한다.
- 이 스킬에 적힌 것과 위 README 에 있는 것만 설명한다. 근거에 없는 기능 · 수치는 말하지 않는다.
