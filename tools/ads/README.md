# ADS — 교육용 목업

> 이 폴더의 ADS 는 **교육용 목업**입니다. 결과 머리에 항상 `"source": "MOCK"` 이 붙습니다. 공통 약속은 [`tools/README.md`](../README.md).

## 실제 제품 — ADS 가 하는 일

| 영역 | 실제 제품이 하는 일 | 근거 |
|---|---|---|
| 문서 생성 | 요구사항에서 SRS → SAD → SDD → 코드 → Test Spec → Test Case 를 단계별로 생성(ALIRA AI) | 교육자료 1차수 3일차 ADS 기능 소개 · `ads-시연-261008` |
| 추적성 | 식별자 사슬 `SR-001 → SRS_… → SAD_… → SWU_… → …_TC_…` · 단계마다 연결 100% 여부를 게이트로 확인 | 교육자료 `ads-시연-261008/trace_check.py` |

ADS 는 공개 저장소가 없어 교육자료 시연 자료를 근거로 합니다.

## 목업이 하는 일

| 얼굴 | 도구 · 명령 | 하는 일 |
|---|---|---|
| 에이전틱 | `ads_generate_docs` | `docs/요구사항.md` 와 시험 정의로 `docs/generated/SRS.md` · `TestSpec.md` 조립 — 문장을 지어내지 않고 옮겨 담기만 함 · 사슬 `SR-xxx → SRS_xxx_01 → 시험 ID` |
| | `ads_trace` | 요구사항 ↔ 시험 연결 · 시험 없는 요구사항 · 요구사항 없는 시험 · main 대비 바뀐 요구사항 · 시험 |
| CLI | `python -m vsmmock ads trace` | → `out/ads.json` |

판정: 시험 첫 줄에 `@req SR-xxx` 표시가 **없으면** FAIL(추적 누락), 표시 **꼴이 깨지면**(`@req SR-2` 등) ERROR. 시험이 없는 요구사항은 알리기만 합니다(기준 시험이 필요한 요구사항은 `ct check-criteria` 가 잡습니다).

## 목업 한계

| 요청 | 목업 응답 |
|---|---|
| SAD · SDD · 코드 단계 문서 | 제공하지 않음(SRS · Test Spec 만) |
| AI 로 문장을 새로 쓰는 문서 생성 | 하지 않음 — 요구사항 · 시험 정의를 옮겨 조립 |

## 설치 · 등록

이번 실습에서는 ADS 를 설치하지 않습니다(도구 소개용). 아래는 따로 써 볼 때의 명령입니다 — 실습 저장소 루트에서:

```powershell
python -m pip install pycparser ziglang mcp
claude mcp add ads -- python -m vsmmock.faces.mcp_ads
python -m vsmmock ads trace
```

---
실습 중 `[MOCK] 실습 목업의 한계 …` 공지를 봤다면 → [목업 사례 로그 올리기](../README.md#목업-사례-로그-올리기-3일차-실습-종료-전)
