# 프로야구 일정 최적화 (O.R.2 팀 프로젝트)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Gyumin225/OR2-project/blob/main/OR2_KBO_GA_Colab.ipynb)

1982년 KBO 원년 6개 구단의 10일 더블 라운드로빈 일정을 유전 알고리즘(GA)으로 만든다. 표현은 원형법 기반 특수 인코딩 (σ, π, h), 비용은 7개 공정성 지표를 정규화한 C(x)(작을수록 좋음)이다. 채택 설정은 개체 수 60, 교차 확률 0.6, 변이 확률 0.3, 토너먼트 크기 3, 엘리트 2, 일정 기준 중복 제거, 150세대 정체 시 종료(최대 500세대)이다.

`gyumin_improved.py`는 원본 코드(`gyumin_original.py`)에서 **교차 확률 pc만 0.9 → 0.6**으로 바꾼 것이다.

## 최종 결과: 시드 33 (C = 1.6343)

기본 설정(설정 A)으로 시드 0–239(240회)를 실행해 얻은 가장 낮은 비용의 일정이다. 시드 33 등 5개 시드가 같은 일정에 도달하였다.

| 지표 | 값 |
| --- | --- |
| 정규화 비용 C / 보조 적합도 f | 1.6343 / 0.3796 |
| G1 총 이동거리 | 9,260 km |
| G2 구단별 최대 이동거리 | 1,585 km (구단별 1,485–1,585 km) |
| G3 지리 보정 이동 비율의 표준편차 | 0.08595 |
| G4 최장 원정 순회 | 865 km |
| G5 300 km 이상 이동 최대 횟수 | 2 |
| G6 3연전 초과 / G7 리피터 | 0 / 0 |

- 일정 파일: `best_schedule_C1.634.xlsx`, `best_schedule_C1.634.csv` (대진표 + 구단별 일자별 이동거리)
- 재현: `python gyumin_improved.py --mode single --seed 33`
- 파일 다시 만들기: `python export_schedule.py --seed 33`

## 이전 결과: 시드 8 (C = 1.6889), 보존

시드 0–29 중 가장 낮은 비용의 일정이다(총 이동 8,840 km, 최대 이동 1,675 km). 이 결과 파일은 바꾸지 않고 그대로 둔다.

- 일정 파일: `gyumin_improved.xlsx`, `gyumin_improved.csv`
- 재현: `python gyumin_improved.py --mode single --seed 8`

## 다중 시드 요약 (설정 A, 표본표준편차)

| 시드 | 평균 C ± SD | 중앙값 | 최선 | 최악 | 예시(2.0131)보다 좋은 시드 |
| --- | --- | --- | --- | --- | --- |
| 0–29 | 1.941 ± 0.133 | 1.926 | 1.6889 (시드 8) | 2.312 | 23/30 |
| 0–239 | 1.986 ± 0.153 | 1.956 | 1.6343 (시드 33 등) | 2.463 | 164/240 |

원본(pc = 0.9)과 비교 (시드 0–29):

| 조건 | 원본 (pc 0.9) | 개량 (pc 0.6) |
| --- | --- | --- |
| 평가 17,460회 고정 (설정 B) | 1.988 ± 0.114 | 1.941 ± 0.118 |
| 기본 종료 조건 (설정 A) | 1.993 ± 0.118 | 1.941 ± 0.133 |

개량 쪽이 평균이 낮지만 시드 30개로 차이를 확정할 수준은 아니다.

## 실행 (Python 3, 표준 라이브러리만)

```bash
python gyumin_improved.py                          # 자체 테스트 + 시드 0–7 탐색 (기본)
python gyumin_improved.py --mode single --seed 33  # 최종 일정 재현 (C = 1.6343)
python gyumin_improved.py --mode single --seed 8   # 시드 0–29 최선 일정 재현 (C = 1.6889)
python gyumin_improved.py --seeds 30               # 시드 0–29 요약 (설정 A)
python export_schedule.py --seed 33                # 최종 일정을 xlsx/csv로 저장
```

콘솔의 '총 평가'는 교차·변이 없이 복사된 자식까지 센 값이다. 보고서의 '실제 비용 계산 횟수'는 캐시에서 가져온 값을 뺀 횟수이므로 더 작다(시드 33: 출력 16,648회, 실제 13,549회).

## 보고서 4장 비교 실험 재현 (설정 B: 평가 17,460회 고정)

`gyumin_improved.py --mode ablation`은 교차 확률 비교를 최대 500세대까지, 가중치 비교를 정체 종료 조건으로 실행하므로 설정마다 평가 횟수가 다르다. 따라서 보고서 표 4-1·4-3의 조건과 같지 않다. 보고서 4장 실험은 `experiments_fixed_budget.py`로 재현한다.

- 시드 0–29, 정체 종료 끔
- 실제 비용 계산(캐시 제외)이 17,460회에 이르면 종료하고, 그때까지 계산한 일정 중 최선 비용을 기록
- 바꾸지 않은 파라미터는 채택 설정과 같음

```bash
python experiments_fixed_budget.py --table 4-1   # 표 4-1: N, pm, pc, k 9개 설정 (약 4분)
python experiments_fixed_budget.py --table 4-3   # 표 4-3: 가중치 프리셋 base / fairness / efficiency
python experiments_fixed_budget.py --table 2-5   # 표 2-5: 교차 확률 0.9 / 0.6 / 0.3 / 0 (평가 횟수 고정 열)
python experiments_fixed_budget.py --table 3-5   # 표 3-5: 설정 A 시드 0–239 기록 (약 4분)
```

결과는 `results/`에 시드별 CSV(`*_runs.csv`)와 요약 CSV(`*_summary.csv`)로 저장된다. 표 4-1 요약에는 Welch 95% 신뢰구간, Bonferroni 보정(8개 비교) 신뢰구간, 같은 시드끼리 짝지은 차이의 신뢰구간이 함께 들어 있다.

## 파일

| 파일 | 내용 |
| --- | --- |
| `gyumin_improved.py` | 최종 GA 코드 (pc = 0.6) |
| `gyumin_original.py` | 원본 코드 (pc = 0.9) |
| `experiments_fixed_budget.py` | 보고서 4장 고정 예산 실험(표 4-1, 4-3, 2-5)과 표 3-5 실행 기록 재현 스크립트 |
| `export_schedule.py` | 한 시드의 최선 일정을 템플릿 양식 xlsx/csv로 저장 |
| `best_schedule_C1.634.xlsx`, `.csv` | **최종 일정 (시드 33)** |
| `gyumin_improved.xlsx`, `.csv` | 이전 최선 일정 (시드 8), 보존 |
| `gyumin_original.xlsx`, `.csv` | 원본 코드의 최선 일정 |
| `results/` | 고정 예산 실험과 시드 0–239 실행의 시드별 결과 CSV |
| `raw/` | 원본·개량 × 설정 A·B × 시드 0–29의 시드별 결과 json 120개 |
| `OR2_KBO_GA_Colab.ipynb` | Google Colab 실행 노트북 |
| `build_colab_notebook.py` | Colab 노트북과 xlsx 생성 스크립트 |
| `diff_original_vs_improved.txt` | 원본과 개량 코드의 차이 |
| `변경내역.md` | 무엇을 왜 바꿨는지, 시험한 다른 후보와 수치 |

## Google Colab 실행

1. 위의 **Open in Colab** 배지를 누르면 노트북이 열린다. [모두 실행]을 누르고 "이 노트북은 Google에서 작성하지 않았습니다" 경고가 나오면 [무시하고 계속하기]를 누른다.
2. 노트북의 기본 설정은 **시드 0–239(240개) 다중 시드 실행**(`MODE = multi_seed`, `SEEDS = 240`)이며, 실행에는 몇 분 정도 걸리고 최선 결과로 **시드 33 일정(C = 1.6343)**을 출력한다. 시드 8 일정(C = 1.6889)만 빠르게 다시 보려면 3번 셀의 `MODE`를 `best_repro`로 바꾼다.
3. 또는 Colab에서 `파일` → `노트 열기` → `GitHub` 탭 → `Gyumin225/OR2-project` → `OR2_KBO_GA_Colab.ipynb`를 연다.
4. 셀에서 직접 실행할 수도 있다.

```python
!git clone https://github.com/Gyumin225/OR2-project.git
%cd OR2-project
!python gyumin_improved.py --mode single --seed 33
```
