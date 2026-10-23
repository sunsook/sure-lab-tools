# CT 목업 (DVERA) — 교육용 목업

> 이 폴더의 CT 목업(DVERA)은 **교육용 목업**입니다. 결과 머리에 항상 `"source": "MOCK"` 이 붙고, 결과는 여러분 저장소의 C 코드를 실제로 빌드 · 실행해서 계산합니다. 공통 약속(지어내지 않음 · 한계 공지)은 [`tools/README.md`](../README.md).

## 실제 제품 — CT 와 DVERA 가 하는 일

| 영역 | 실제 제품이 하는 일 | 공개 근거 |
|---|---|---|
| 정체 | CT(단위 · 통합 · 코드 기반 시험 · 커버리지 · 리포트 · 추적성 관리 도구)의 검증 작업을 코딩 에이전트로 가져오는 플러그인. 「DVERA 는 CT 의 검증 결과를 대체하지 않는다」 | [dvera-plugin](https://github.com/SuresoftTechnologies/dvera-plugin) README |
| 에이전트 도구 | MCP 도구 21개 — 프로젝트 생성 · 분석 · 함수 탐색(`ct_find_functions`) · AI 시험 생성(`ct_ai_generate_test`) · 실행(`ct_execute_test`) · 결과(`ct_get_test_results`) · 커버리지(`ct_get_coverage`) · 리포트(`ct_generate_report`) · 툴체인 · 컴파일/링크 플래그 · 환경 점검(`dvera_check_environment`) | dvera-plugin `resources/tool-annotations.json` |
| 작업 흐름 Skill | 14개 — 프로젝트 준비 · 분석 루프 · 시험 생성 · 실행 · 빌드 오류 교정 루프 · 승인된 요구사항 → AI 시험 · 회귀 재실행 · 리포트 등 | dvera-plugin `skills/` |
| 요구사항 기반 시험 | 함수 하나를 골라 요구사항을 「전제 · 입력 · 기대 결과」 스펙 표로 만들고 **사용자 승인 뒤** 생성 → 실행 → 결과 · 커버리지 | dvera-plugin `skills/ct-req-to-test` |
| 코드 분석 기반 시험 | 스펙 없이 함수 코드에서 시험 생성 | dvera-plugin `ct_ai_generate_test`(specs 생략) |
| 커버리지 | Statement · Branch · MC/DC | dvera-plugin `ct_get_coverage` · [ct-jenkins-plugin](https://github.com/SuresoftTechnologies/ct-jenkins-plugin) README |
| 리포트 | PDF · HTML · XLSX · DOCX · PPTX | dvera-plugin `ct_generate_report` |
| 회귀 | 변경 뒤 재실행 · regressed / recovered · 커버리지 이전 → 현재 | dvera-plugin `skills/ct-regression` |
| CI | CLI `csc` 로 AI 시험 생성 · 실행 · 결과(JUnit XML) 게시 · Call/Statement/Branch/MC-DC 임계값 미달 시 빌드 상태 변경 (Jenkins) | ct-jenkins-plugin |

dvera-plugin README 의 문장 — 「요구사항 기반 시험과 구조 커버리지는 서로 다른 질문에 답한다. 실행이 통과하고 커버리지가 높다고 해서 의도한 요구사항을 시험했다는 증거는 아니다.」

## 목업이 하는 일

| 얼굴 | 도구 · 명령 | 하는 일 |
|---|---|---|
| 에이전틱(PR · 개발 단계 · Skill 이 부름) | `python -m vsmmock ct find [이름 일부]` | `src/*.c` 함수 · 시그니처 · signatureHash · 파일:줄 |
| | `python -m vsmmock ct spec <함수> --specs SR-xxx …` | 요구사항 · 기준설계로 스펙 표(입력 · 기대 · 근거 줄 · `spec.id`) — 근거가 없으면 질문(`NEEDS_CRITERIA`) · 파일을 쓰지 않음. `--specs` 없음 → 분기(파일:줄 · 참/거짓)와 입력 제안 |
| | `python -m vsmmock ct generate <함수> --specs … --approved-spec <spec.id>` | **승인 뒤에만** `ct/*.json` 시험 정의 생성 · 요구사항이 바뀌어 낡은 시험은 `ct/retired/` 로 옮김(지우지 않음) · 표가 바뀌었으면 `ERROR · SPEC_STALE` |
| | MCP 를 등록한 경우 같은 함수: `ct_find_functions` · `ct_ai_generate_test` · `ct_execute_test` · `ct_get_test_results` · `ct_get_coverage` · `dvera_check_environment` | 결과는 CLI 와 같음 |
| CLI(CI/CD · 배포 단계) | `python -m vsmmock ct check-criteria` | `docs/기준설계.md` 기준 시험이 다 있는지 · 요구사항과 기준이 맞는지(시험 통과는 안 봄) — PR 가드와 게이트가 같이 씀 |
| | `python -m vsmmock ct run` | 시험 실행 → `out/ct.json` · `out/ct-junit.xml` |
| | `python -m vsmmock ct coverage` | 분기 측정값 / 목표 · 미충족 분기 → `out/ct.json` |

종료 코드: 0 문제 없음 · 1 문제 찾음(FAIL) · 2 검사 실패(ERROR). `ct find · spec · generate` 는 결과 JSON 을 화면과 `out/ct-gen.json` 에 내고, `ERROR` 일 때만 2 입니다 — `NEEDS_CRITERIA` · `NEEDS_APPROVAL` 은 다음 대화 단계라 0.

**목업이 묻는 경우** — 요구사항 문장이나 `docs/기준설계.md` 에 근거가 없는 기준 · 기대값은 만들지 않고 질문(`NEEDS_CRITERIA`)으로 돌려줍니다(`docs/기준설계.md` 가 아직 없어도 같습니다). 답은 질문의 `write_to` 위치(기준설계)에 직접 적고 다시 실행하세요 — `brake_on` 같은 bool 입력은 `true` / `false` 로 적습니다. CI 게이트 명령(`ct check-criteria` 등)은 같은 상황을 `ERROR · CRITERIA_MISSING` 으로 냅니다.

## 목업 한계

| 요청 | 목업 응답 |
|---|---|
| 정수 · bool · enum 이 아닌 입력(포인터 · 배열 · 문자열 · 구조체) · 호출 순서가 필요한 함수의 요구사항 기반 생성 | 「목업이 다루지 못한 패턴」 공지(`MOCK_UNHANDLED`) · 생성 0건 → `tests/TC-*.c` 로 직접 작성 |
| CT 실제 테스트 파일 · 스텁 · self-healing · 회귀 델타 · 리포트 | 제공하지 않음 |
| 로컬(Windows) 분기 커버리지 | `MOCK_LIMIT` · ERROR — 실습 PC 컴파일러(zig)에 gcov 런타임이 없어 측정할 수 없다. **gcc 를 설치하지 마세요** — 커버리지는 CI 에서 잰다 |
| CI 분기 커버리지 | ubuntu 의 gcc `--coverage` + 오픈소스 [gcovr](https://gcovr.com). gcov 의 분기 정의는 CT 와 다를 수 있다 |
| Statement · MC/DC | `N/A(목업 미측정)` |
| 요구사항의 비교 방향만 바뀜(「이상」→「초과」 · 수치 그대로) | `ct check-criteria` 는 기준 입력(경계 수치)이 그대로라 통과시킨다 — 대신 `ads trace` 가 바뀐 요구사항을 알리고, 게이트는 요구사항 파일 변경으로 REVIEW(사람 결정)가 된다. 시험 기대값이 새 요구사항과 맞는지는 사람이 검토한다 |

## 설치 · 등록

[`tools/README.md` 「준비」](../README.md) 대로 목업(CLI)을 설치하고 Skill(`dvera` · `statica`)을 `.claude/skills/` 에 넣습니다. MCP 등록은 필요 없습니다. 마지막 줄 `python -m vsmmock ct run` 이 `[CT] run PASS …` 를 내면 준비 끝입니다. `ct check-criteria` 는 실습 2-④ 에서 `docs/기준설계.md` 를 만든 뒤에 씁니다.

MCP 로도 쓰려면(선택): `python -m pip install "vsmmock[mcp] @ git+https://github.com/sunsook/sure-lab-tools"` 뒤 `claude mcp add dvera -- python -m vsmmock.faces.mcp_dvera`.

---
실습 중 `[MOCK] 실습 목업의 한계 …` 공지를 봤다면 → [목업 사례 로그 올리기](../README.md#목업-사례-로그-올리기-3일차-실습-종료-전)
