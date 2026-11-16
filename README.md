# 규민 개량본 (평균 1위)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Gyumin225/OR2-project/blob/main/OR2_KBO_GA_Colab.ipynb)

규민 원본 코드에서 **교차 확률 pc만 0.9 → 0.6**으로 바꾼 것이다(규민 2장 설계 문서의 값). 표현 (σ, π, h), 적합도 v2, 나머지 파라미터는 원본과 같다.

## 결과 (시드 0–29, 공통 평가기 기준)

| 설정 | 코드 | 평균 C ± SD | 최선 | 예시(2.013)보다 좋은 시드 |
| --- | --- | --- | --- | --- |
| 동일 예산 17,460회 | 규민 원본 | 1.988 ± 0.112 | 1.824 | 20/30 |
| 동일 예산 17,460회 | **규민 개량** | **1.941 ± 0.116** | **1.689** | **23/30** |
| 코드 설계대로 | 규민 원본 | 1.993 ± 0.116 | 1.824 | 20/30 |
| 코드 설계대로 | **규민 개량** | **1.941 ± 0.131** | **1.689** | **23/30** |

- 원본과의 차이: −0.047(동일 예산, p = 0.13), −0.052(설계대로, p = 0.082). 좋아지는 경향이지만 시드 30개로 확정할 수준은 아니다.
- 최선 일정(C = 1.689): 총 이동 8,840km, 최대 이동 1,675km, 300km 이상 이동 최대 2회, 3연전 초과 0, 리피터 0

## 파일

| 파일 | 내용 |
| --- | --- |
| `OR2_KBO_GA_Colab.ipynb` | **Google Colab 연동 실행 노트북** (GitHub 자동 동기화, 파라미터 폼 UI, 구장별 대진표·이동거리표, 수렴 곡선 시각화 포함) |
| `gyumin_improved.py` | 개량본 코드 |
| `gyumin_original.py` | 원본 코드 (받은 txt를 확장자만 바꿈) |
| `diff_original_vs_improved.txt` | 두 코드의 차이. pc 기본값 외에, 시험했지만 채택하지 않은 옵션(`restart_frac`, `mut_weights`)이 기본값 꺼짐 상태로 들어 있다 |
| `변경내역.md` | 무엇을 왜 바꿨는지, 교안 근거, 시험한 다른 후보와 수치 |
| `gyumin_improved.xlsx`, `gyumin_original.xlsx` | 각 코드의 최선 일정 (교수님 템플릿 양식) |
| `gyumin_improved.csv`, `gyumin_original.csv` | 각 코드의 최선 일정 CSV (교수님 템플릿 양식) |
| `build_colab_notebook.py` | `OR2_KBO_GA_Colab.ipynb` 및 `.xlsx` 파일을 생성하는 표준 라이브러리 전용 빌드 스크립트 |
| `raw/` | 시드별 결과 json 120개 (원본·개량 × 설정 A·B × 시드 30개). 최종 일정, G1–G7, 평가 횟수, 시간, 수렴 기록 |

## Google Colab 연동 실행 방법

1. **배지 클릭 한 번으로 열기**: 상단의 **Open in Colab** 배지를 클릭하면 [`OR2_KBO_GA_Colab.ipynb`](https://colab.research.google.com/github/Gyumin225/OR2-project/blob/main/OR2_KBO_GA_Colab.ipynb)가 Google Colab에서 바로 열립니다. [모두 실행]을 누르고 [경고: 이 노트북은 Google에서 작성하지 않았습니다
이 노트는 GitHub에서 로드됩니다. 노트가 Google에 저장된 데이터에 액세스하거나 다른 세션의 데이터 및 사용자 인증 정보를 읽을 권한을 요청할 수 있습니다. 노트를 실행하기 전에 소스 코드를 검토하세요.] 가 나오면 [무시하고 계속하기]를 누르면 됩니다.

2. **코랩에서 GitHub 저장소 직접 불러오기**: Google Colab 접속 → `파일(File)` → `노트 열기(Open notebook)` → `GitHub` 탭 선택 → `Gyumin225/OR2-project` 입력 후 `OR2_KBO_GA_Colab.ipynb` 선택.
3. **코랩 셀에서 GitHub 코드 클론 후 바로 실행하기**:

```python
!git clone https://github.com/Gyumin225/OR2-project.git
%cd OR2-project
!python gyumin_improved.py --mode single --seed 8
```

> Colab 노트북 내 1번 셀(`GitHub 저장소 연동 및 소스 파일 동기화`)은 위 저장소를 자동으로 `git clone`하며, 클론이 불가능한 환경에서는 노트북에 내장된 코드로 자동 복원하여 단독 실행됩니다.

## 실행 (Python 3, 표준 라이브러리만)

```bash
python gyumin_improved.py                          # 자체 테스트 + 시드 8개 탐색 (기본)
python gyumin_improved.py --mode single --seed 8   # 시드 8 한 번 → C = 1.6889 (최선 일정)
```
