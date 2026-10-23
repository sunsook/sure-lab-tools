# STATICA / STATIC — 교육용 목업

> 이 폴더의 정적분석기는 **교육용 목업**입니다. PR · 개발 단계 에이전틱 판 이름은 **STATICA**, CI/CD · 배포 단계 CLI 판 이름은 **STATIC** 입니다. 결과 머리에 항상 `"source": "MOCK"` 이 붙습니다. 공통 약속은 [`tools/README.md`](../README.md).

## 실제 제품 — STATIC 과 STATICA 가 하는 일

| 영역 | 실제 제품이 하는 일 | 공개 근거 |
|---|---|---|
| 정체 | STATIC: 코딩 규칙 위반 · 런타임 오류 · 잠재 보안 취약점 탐지 · 도메인 규칙셋 · 품질 메트릭. STATICA: 분석 준비 · 실행 · 보고 에이전트 — **소스를 고치지 않는다** | [statica-plugin](https://github.com/SuresoftTechnologies/statica-plugin) README |
| 증분 분석 | 코딩 중 응답이 끝날 때마다(Stop 훅) 바뀐 파일만 분석 · `[STATIC] N개 대상 분석 완료 · 결함 M건` | statica-plugin `hooks/` |
| 명령 | `pre-analyze`(변경분 분석) · `upload`(전체 분석) · `ruleset-show/set` · `scope` · `metric` · `report`(DOC · PDF · HTML · EXCEL, 12종) · `status` | statica-plugin `scripts/static_agent/cli.py` |
| 결과 | 결함마다 경로 · 시작 줄 · 심각도 · 규칙셋 · 규칙 · 메시지 · 규칙별 · 심각도별 집계 | statica-plugin `defects.py` |
| MISRA C:2023 | 1차수 실습 코드(VSM)에서 실측 44건 · 27개 규칙(9.1 초기화 전 사용 6건 · Dir 4.6 7건 등) | 교육자료 1차수 실측 JSON |

## 목업이 하는 일

| 얼굴 | 도구 · 명령 | 하는 일 |
|---|---|---|
| 에이전틱(STATICA) | `statica_pre_analyze` | 아래 6 규칙 위배 위치(파일:줄) · `fix_hint` · 규칙별 · 심각도별 집계 — 소스 무변경 |
| | `statica_ruleset_show` | 기준설계에서 고른 규칙 · 목업이 지원하는 규칙 |
| CLI(STATIC) | `python -m vsmmock static analyze` | → `out/static.json` · 위배 수가 기준설계 `misra_max` 를 넘으면 FAIL |

목업 규칙 6개 — 1차수 실측에 있고 Required 등급이며 구문 구조로 판정할 수 있는 것: **16.3**(case 끝 break) · **16.4**(switch default) · **10.1**(bool 을 산술에 사용) · **14.3**(항상 참인 unsigned 비교) · **21.7**(`atoi` 류) · **21.6**(표준 입출력 함수). 쓸 규칙은 `docs/기준설계.md` 의 `misra_rules` 줄로 정합니다.

## 목업 한계

| 요청 | 목업 응답 |
|---|---|
| 6 규칙 밖 규칙(9.1 등 데이터 흐름 · Dir 4.6 · 8.x …)을 `misra_rules` 에 넣음 | `MOCK_LIMIT` · ERROR — 실제 STATIC 은 검사한다 |
| `statica_ruleset_set` 으로 규칙 바꾸기 | `MOCK_LIMIT` · ERROR — 규칙은 기준설계 `misra_rules` 로 |
| 메트릭 · 리포트 12종 · 증분 분석 훅 · 서버 업로드 | 제공하지 않음 |
| 목업 파서가 읽지 못하는 코드(GNU 확장 등) | 그 파일만 「목업이 다루지 못한 패턴」 공지(`MOCK_UNHANDLED`) · 나머지 파일로 판정 |

## 설치 · 등록

실습 저장소 루트에서:

```powershell
python -m pip install pycparser ziglang mcp
claude mcp add statica -- python -m vsmmock.faces.mcp_statica
python -m vsmmock static analyze
```

`static analyze` 는 `docs/기준설계.md` 의 `misra_rules` · `misra_max` 줄을 읽습니다 — 실습 2-② 에서 기준설계를 만들기 전에는 `CRITERIA_MISSING` ERROR 가 정상입니다(목업은 검사할 규칙 · 통과선을 대신 정하지 않습니다).

---
실습 중 `[MOCK] 실습 목업의 한계 …` 공지를 봤다면 → [목업 사례 로그 올리기](../README.md#목업-사례-로그-올리기-3일차-실습-종료-전)
