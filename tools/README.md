# 검증 도구 목업 — CT 목업 · STATIC 목업

> 이 폴더의 도구는 **교육용 목업**입니다. 실제 슈어소프트 제품(CT · STATIC · ADS)의 공개 표면을 같은 꼴로 흉내 내며,
> 결과는 여러분 저장소의 코드에서 실제로 계산합니다. 모든 결과 머리에 `"source": "MOCK"` 이 붙습니다.

| 도구 | 에이전틱 판 (PR · 개발 단계 · Skill + CLI) | CLI 판 (CI/CD · 배포 단계) | 자세히 |
|---|---|---|---|
| CT 목업 (DVERA) | 요구사항 기반 · 구조 기반 시험 명세 → 승인 뒤 생성 · 실행 · 커버리지 — `python -m vsmmock ct find · spec · generate` | `python -m vsmmock ct …` → `out/ct.json` | `tools/dvera/README.md` |
| STATIC 목업 (STATICA) | MISRA C:2023 정적분석 · 교정 제안 | `python -m vsmmock static analyze` → `out/static.json` | `tools/statica/README.md` |
| ADS | 요구사항 문서 생성 · 추적성 확인 — 이번 실습에서는 설치하지 않습니다(도구 소개용) | `python -m vsmmock ads trace` → `out/ads.json` | `tools/ads/README.md` |

커버리지 에이전트 COVERA 는 공개 표면이 없어 목업을 만들지 않았습니다 — 분기 커버리지는 CT 목업이 맡습니다.

## 준비 (1번 저장소 루트에서 한 번)

```powershell
python -m pip install git+https://github.com/sunsook/sure-lab-tools
git clone --depth 1 https://github.com/sunsook/sure-lab-tools $env:TEMP\sure-lab-tools
New-Item -ItemType Directory -Force .claude\skills | Out-Null
Copy-Item -Recurse -Force $env:TEMP\sure-lab-tools\skills\dvera, $env:TEMP\sure-lab-tools\skills\statica .claude\skills\
python -m vsmmock ct run
```

첫 줄이 목업(CLI)을 설치하고, 둘째 ~ 넷째 줄이 CT 목업 · STATIC 목업 Skill 두 개를 `.claude/skills/` 에 넣습니다(MCP 등록은 필요 없습니다). 마지막 줄이 `[CT] run PASS …` 를 내면 준비 끝입니다(`tests/` 의 시험을 실제로 빌드 · 실행합니다). `ct check-criteria` · `static analyze` 는 실습 2-④ 에서 `docs/기준설계.md` 를 만든 뒤에 씁니다 — 그 전에는 「기준설계가 없다」는 ERROR 가 정상입니다. **gcc 는 설치하지 마세요** — 분기 커버리지는 CI(ubuntu)에서만 잽니다(CI 는 `pip install "vsmmock[ci] @ git+https://github.com/sunsook/sure-lab-tools"`).

## 목업이 지키는 약속

1. **기준 · 기대값을 지어내지 않습니다.** 요구사항이나 `docs/기준설계.md` 에 근거가 없으면 질문으로 돌려줍니다(CLI 는 `ERROR · CRITERIA_MISSING`).
2. **기준을 주면 검증하고 근거(SR 줄 · 파일:줄)와 함께 돌려줍니다.**
3. **알려진 한계**(`MOCK_LIMIT`)는 각 도구 README 「목업 한계」 표에 있습니다 — 판정은 ERROR 입니다.
4. **목업이 예상하지 못한 패턴**(`MOCK_UNHANDLED`)은 여러분 탓이 아닙니다. 그 항목은 「실습 목업의 한계」로 공지하고 통과 처리하며, 사례를 `logs/` 에 기록합니다. 이런 사례는 목업 개선에 큰 도움이 됩니다 — 기여해 주셔서 감사합니다. 모은 사례는 다음 차수 실습 전에 목업 개선에 반영합니다.

## 목업 사례 로그 올리기 (3일차 실습 종료 전)

실습 중 `[MOCK] 실습 목업의 한계 …` 공지를 본 적이 있다면 `logs/` 폴더에
`<계정>_Mock_CaseReport.log` 가 생겼을 것입니다. `<계정>` 은 `gh auth login` 한 GitHub 계정이고, gh 로 확인이 안 되면 `git config user.name`(Git 표시 이름) · 그것도 없으면 `UNKNOWN` 입니다 — 파일 이름이 예상과 달라도 `logs/` 안의 `*_Mock_CaseReport.log` 를 올리면 됩니다. 다음 차수 목업을 고치는 데 쓰니 실습 종료 전에 올려 주세요.
로그에는 목업이 멈춘 위치의 코드 앞뒤 두 줄 · 오류 메시지 첫 줄 · Git 브랜치 · 커밋 번호가 들어 있습니다. 목업은 비밀값을 따로 걸러 내지 않습니다 — 아래 프롬프트가 올리기 전에 내용을 보여 주니 반드시 확인하세요.

Claude Code 에 아래 프롬프트를 그대로 붙여 넣으세요(`<배포 저장소>` 는 강사가 알려 준 주소로 바꿉니다).

```text
logs/ 폴더의 *_Mock_CaseReport.log 파일을 실습 배포 저장소 <배포 저장소> 로 올려 줘.
1) 파일이 없으면 「올릴 사례 없음」이라고만 말하고 멈춰.
2) 올리기 전에 파일 내용을 보여 주고, 비밀번호 · 토큰 · 개인 이메일처럼 보이는 값이 있으면 그 줄을 알려 주고 내 확인을 받아.
3) gh 로 <배포 저장소> 를 fork 하고, 브랜치 case-report/<내 GitHub 계정> 에 case-reports/<내 GitHub 계정>_Mock_CaseReport.log 로 그 파일만 추가해(git add 는 그 경로만 — git add -A 금지).
4) gh pr create 로 제목 「Mock CaseReport — <내 GitHub 계정>」, 본문에 사례 건수와 도구별 건수를 적어 PR 을 열어 줘.
5) 내 저장소 원본 logs/ 는 지우지 마. 끝나면 PR 주소를 알려 줘.
```

권한 문제로 fork · PR 이 안 되면 강사에게 파일을 직접 전달해 주세요.
