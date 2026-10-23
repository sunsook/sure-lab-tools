# STATIC 목업 (STATICA / STATIC) — 교육용 목업

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
| 에이전틱(STATICA · Skill 이 부름) | `python -m vsmmock static pre-analyze` | 아래 8 규칙 위배 위치(파일:줄) · `rule` · 분류 · `fix_hint` · 규칙별 · 분류(심각도)별 집계 — 소스 무변경 · 기준설계에 빠진 칸이 있으면 질문(`NEEDS_CRITERIA`) · 결과 `out/static-pre.json` |
| | MCP 를 등록한 경우: `statica_pre_analyze` · `statica_ruleset_show` | 같은 결과 · 기준설계에서 고른 규칙 · 목업이 지원하는 규칙 |
| CLI(STATIC) | `python -m vsmmock static analyze` | → `out/static.json` · 분류별 처리 정책으로 판정(아래 표) — `findings` 는 Merge 를 막는 위배만 · 모든 위배는 `metrics.items` |

목업 규칙 8개 — 구문 구조로 판정할 수 있는 것. 분류는 MISRA C:2023 원문 그대로입니다.

| 분류 | 규칙 |
|---|---|
| Mandatory | **12.5**(배열 매개변수에 `sizeof`) |
| Required | **16.3**(case 끝 break) · **16.4**(switch default) · **10.1**(bool 을 산술에 사용) · **14.3**(항상 참인 unsigned 비교) · **21.7**(`atoi` 류) · **21.6**(표준 입출력 함수) — 1차수 실측에 있는 규칙 |
| Advisory | **2.7**(쓰지 않는 매개변수) |

쓸 규칙은 `docs/기준설계.md` 의 `misra_rules` 줄로, 분류마다 어떻게 처리할지는 아래 키로 정합니다.

| 키 | 값 | 판정 |
|---|---|---|
| `misra_mandatory` · `misra_required` · `misra_advisory` | `block` · `fix` · `report` | `block` = 그 분류 위배가 하나라도 있으면 FAIL(Merge 불가) · `fix` = 고치거나 인정된 예외 표시가 있어야 통과 · `report` = 목록에만(판정 영향 없음) |
| `misra_deviation` | `allow` · `deny` | `allow` 면 예외 표시를 `fix` 분류에서 인정 · `deny` 면 표시를 무시 |

**예외 표시**(목업이 정한 꼴 — 실제 STATIC 의 억제 문법이 아닙니다): 위배 줄 끝이나 바로 윗줄에 `/* MISRA-DEVIATION <규칙> 사유=<왜 못 고치나> 승인=<누가 승인했나> */`. 규칙 번호가 그 위배와 같고 사유 · 승인이 둘 다 있어야 인정합니다. **Mandatory 위배는 표시를 달아도 인정하지 않습니다**(MISRA C:2023 — 「deviation from mandatory guidelines is not permitted」). `misra_mandatory: report` 로 두면 막지는 않지만 「MISRA 준수라 할 수 없음」 공지가 붙습니다.

**목업이 묻는 경우** — 위 키 중 빠진 칸이 있으면 `static pre-analyze` 가 그 칸만 질문으로 돌려줍니다(실습 2-④ⓐ 에서 CT 목업 질문과 함께 답합니다 · 이미 적은 칸은 다시 묻지 않습니다). 질문의 `supported` 는 고를 수 있는 값(규칙은 분류별로 묶음)이고, `current` 는 지금 코드의 위배 건수 · 규칙별 · 분류별 집계입니다 — 값은 이 근거를 보고 여러분이 고릅니다(목업은 값을 정하거나 추천하지 않습니다). 분류 키가 하나도 없고 옛 `misra_max`(허용 결함 수)만 있으면 예전처럼 총건수로 판정합니다 — 이 방식은 기존 위배 하나를 없애며 새 위배 하나를 넣으면 통과하는 맹점이 있습니다. 분류별 처리(`fix`)는 그 경우도 새 위배를 잡습니다.

## 목업 한계

| 요청 | 목업 응답 |
|---|---|
| 8 규칙 밖 규칙(9.1 등 데이터 흐름 · 15.5 · 15.1 · Dir 4.6 · 8.x …)을 `misra_rules` 에 넣음 | `MOCK_LIMIT` · ERROR — 실제 STATIC 은 검사한다 |
| 2.7 · 12.5 의 세부 정의 | 2.7 은 이름 있는 매개변수를 함수 본문에서 한 번도 쓰지 않으면 함수 정의 줄에 1건(같은 이름 지역변수가 매개변수를 가리면 「사용」으로 보는 근사) · 12.5 는 배열로 선언한 매개변수에 쓴 `sizeof` 식마다 1건 — 실제 STATIC 과 건수 정의가 다를 수 있다 |
| `statica_ruleset_set` 으로 규칙 바꾸기 | `MOCK_LIMIT` · ERROR — 규칙은 기준설계 `misra_rules` 로 |
| 메트릭 · 리포트 12종 · 증분 분석 훅 · 서버 업로드 | 제공하지 않음 |
| 목업 파서가 읽지 못하는 코드(GNU 확장 등) | 그 파일만 「목업이 다루지 못한 패턴」 공지(`MOCK_UNHANDLED`) · 나머지 파일로 판정 |

## 설치 · 등록

[`tools/README.md` 「준비」](../README.md) 대로 목업(CLI)을 설치하고 Skill(`statica`)을 `.claude/skills/` 에 넣습니다. MCP 등록은 필요 없습니다 — Skill 이 `python -m vsmmock static pre-analyze` · `static analyze` 를 부릅니다.

MCP 로도 쓰려면(선택): `python -m pip install "vsmmock[mcp] @ git+https://github.com/sunsook/sure-lab-tools"` 뒤 `claude mcp add statica -- python -m vsmmock.faces.mcp_statica`.

`static analyze`(게이트)는 `docs/기준설계.md` 의 `misra_rules` · 분류별 처리 · `misra_deviation` 줄을 읽습니다 — 실습 2-④ⓐ 에서 그 줄을 적기 전에는 `CRITERIA_MISSING` ERROR(파일이 아예 없으면 `INPUT_BROKEN` · 값 꼴이 틀려도 `INPUT_BROKEN`)가 정상입니다(목업은 검사할 규칙 · 처리 정책을 대신 정하지 않습니다). 질문은 `static pre-analyze` 가 합니다. 다른 폴더(PR head worktree 등)를 검사하려면 `--repo <경로>` 를 붙입니다.

---
실습 중 `[MOCK] 실습 목업의 한계 …` 공지를 봤다면 → [목업 사례 로그 올리기](../README.md#목업-사례-로그-올리기-3일차-실습-종료-전)
