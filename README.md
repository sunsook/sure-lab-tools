# sure-lab-tools — 검증 도구 목업 (실습 배포판)

> 교육용 배포판 — 개인 용도로 쓰고 재배포는 문의 바랍니다.

슈어소프트 검증 도구의 공개 표면을 같은 꼴로 흉내 낸 **교육용 목업**이다. 결과는 여러분 저장소의 코드에서 실제로 계산하고, 모든 결과 머리에 `"source": "MOCK"` 이 붙는다. 실습에서는 CT(DVERA) · STATIC 목업을 쓴다.

| 쓰는 저장소 | 설치하는 때 | 쓰는 면 |
|---|---|---|
| 예제코드저장소(lab1-code) | 2-4-준비-1 | Skill + CLI |
| CICD저장소(lab3-cicd) | 3-3 | CLI(workflow 안) |

## 설치

```powershell
python -m pip install git+https://github.com/sunsook/sure-lab-tools
```

Skill 은 이 저장소의 `skills/<도구>/` 폴더를 대상 저장소 `.claude/skills/<도구>/` 로 복사한다.

확인(대상 저장소 루트에서): `python -m vsmmock ct run` 이 `[CT] run PASS …` 를 낸다.

## 들어 있는 것

| 경로 | 무엇 |
|---|---|
| `vsmmock/` | 목업 엔진 · CLI(`python -m vsmmock …`) |
| `skills/` | Claude Code Skill |
| `tools/` | 도구별 설명 · 목업 한계(`tools/README.md` 부터) |
| `pyproject.toml` | 설치 정의 |

## 출처

`sun_Tool_Mockup` 커밋 `dbb3a13` 의 `vsmmock/` · `tools/` · `skills/` · `pyproject.toml` 을 그대로 옮겼다.
