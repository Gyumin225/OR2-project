"""
OR2-project Google Colab 노트북 및 Excel(.xlsx) 파일 생성 스크립트
- Python 3 표준 라이브러리만 사용 (외부 패키지 불필요)
- 생성 파일:
  1) gyumin_improved.xlsx, gyumin_original.xlsx (UTF-8 BOM CSV 보정 포함)
  2) OR2_KBO_GA_Colab.ipynb (GitHub Gyumin225/OR2-project 연동용 Colab 노트북)
"""

from __future__ import annotations

import csv
import json
import sys
import zipfile
from pathlib import Path
from typing import List
from xml.sax.saxutils import escape

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
GITHUB_USER = "Gyumin225"
GITHUB_REPO = "OR2-project"
GITHUB_URL = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
NOTEBOOK_NAME = "OR2_KBO_GA_Colab.ipynb"


# ---------------------------------------------------------------------------
# 1. 표준 라이브러리 전용 경량 XLSX 생성기
# ---------------------------------------------------------------------------
def _col_letter(col_idx: int) -> str:
    """1-based column index -> Excel column letters (1 -> A, 27 -> AA)"""
    letters: List[str] = []
    while col_idx > 0:
        col_idx, rem = divmod(col_idx - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def csv_to_xlsx(csv_path: Path, xlsx_path: Path, sheet_name: str = "Schedule") -> None:
    """UTF-8 CSV 파일을 표준 OpenXML(.xlsx) 파일로 변환"""
    raw_text = csv_path.read_text(encoding="utf-8-sig")
    csv_path.write_text(raw_text, encoding="utf-8-sig")  # utf-8-sig 정규화

    rows = list(csv.reader(raw_text.splitlines()))
    sheet_rows: List[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells_xml: List[str] = []
        for c_idx, val in enumerate(row, start=1):
            if val == "":
                continue
            ref = f"{_col_letter(c_idx)}{r_idx}"
            try:
                num_val = float(val)
                if num_val.is_integer() and "." not in val:
                    cells_xml.append(f'<c r="{ref}"><v>{int(num_val)}</v></c>')
                else:
                    cells_xml.append(f'<c r="{ref}"><v>{num_val}</v></c>')
            except ValueError:
                escaped = escape(val)
                cells_xml.append(
                    f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escaped}</t></is></c>'
                )
        if cells_xml:
            sheet_rows.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')
        else:
            sheet_rows.append(f'<row r="{r_idx}"/>')

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        "</worksheet>"
    )

    with zipfile.ZipFile(xlsx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/worksheets/sheet1.xml", worksheet)


# ---------------------------------------------------------------------------
# 2. Colab 노트북 생성기
# ---------------------------------------------------------------------------
def _to_source(text: str) -> List[str]:
    lines = text.strip("\n").split("\n")
    return [line + "\n" for line in lines[:-1]] + [lines[-1]]


def build_notebook() -> Path:
    improved_src = (ROOT / "gyumin_improved.py").read_text(encoding="utf-8")
    original_src = (ROOT / "gyumin_original.py").read_text(encoding="utf-8")

    cells = []

    def md(text: str) -> None:
        cells.append({"cell_type": "markdown", "metadata": {}, "source": _to_source(text)})

    def code(text: str) -> None:
        cells.append(
            {
                "cell_type": "code",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": _to_source(text),
            }
        )

    # Cell 1: Markdown Overview + Open in Colab Badge
    md(
        f"""
# ⚾ O.R.2 프로야구(1982 KBO 6개 구단) 10일 경기 일정 최적화 — 규민 개량본 & 원본 (Colab 연동)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/{GITHUB_USER}/{GITHUB_REPO}/blob/main/{NOTEBOOK_NAME})

이 노트북은 GitHub 저장소 [`{GITHUB_USER}/{GITHUB_REPO}`]({GITHUB_URL})와 연동되어 있으며, **Google Colab에서 바로 실행**할 수 있도록 구성되었습니다.

### 📊 핵심 비교 요약 (시드 0–29, 공통 평가기 기준)
| 설정 | 코드 | 평균 C ± SD | 최선 C(x) | 예시(2.013)보다 좋은 시드 |
| --- | --- | --- | --- | --- |
| 동일 예산 17,460회 | 규민 원본 (`pc=0.9`) | 1.988 ± 0.112 | 1.824 (`seed=3`) | 20/30 |
| 동일 예산 17,460회 | **규민 개량 (`pc=0.6`)** | **1.941 ± 0.116** | **1.689 (`seed=8`)** | **23/30** |
| 코드 설계대로 | 규민 원본 (`pc=0.9`) | 1.993 ± 0.116 | 1.824 (`seed=3`) | 20/30 |
| 코드 설계대로 | **규민 개량 (`pc=0.6`)** | **1.941 ± 0.131** | **1.689 (`seed=8`)** | **23/30** |

### 🚀 사용 방법
1. **Cell 2**를 실행해 GitHub 저장소에서 최신 코드를 동기화(또는 내장 폴백 로드)합니다.
2. **Cell 3**을 실행해 8종 완료 판정 테스트 통과 여부를 확인합니다.
3. **Cell 4**에서 버전·실행 모드·시드 등을 선택해 GA 최적화를 실행합니다.
4. **Cell 5~6**에서 교수님 템플릿 양식(구장별 대진표 & 이동거리표)과 수렴 곡선을 확인합니다.
"""
    )

    # Cell 2: GitHub Sync + Embedded Fallback
    cell2_code = f"""
#@title 🔗 1. GitHub 저장소 연동 및 소스 파일 동기화 {{ display-mode: "form" }}
import os
import subprocess
from pathlib import Path

REPO_URL = "{GITHUB_URL}.git"
REPO_NAME = "{GITHUB_REPO}"

_FALLBACK_IMPROVED = {json.dumps(improved_src, ensure_ascii=False)}
_FALLBACK_ORIGINAL = {json.dumps(original_src, ensure_ascii=False)}

def sync_project_files():
    cwd = Path.cwd()
    # 이미 저장소 루트 안에 있는 경우
    if (cwd / "gyumin_improved.py").exists() and (cwd / "gyumin_original.py").exists():
        print(f"✅ 로컬 저장소 파일 확인 완료: {{cwd}}")
        return cwd

    # 하위 폴더로 이미 클론되어 있는 경우
    sub = cwd / REPO_NAME
    if (sub / "gyumin_improved.py").exists() and (sub / "gyumin_original.py").exists():
        os.chdir(sub)
        print(f"✅ 기존 클론 폴더로 이동 완료: {{Path.cwd()}}")
        return Path.cwd()

    # GitHub에서 clone 시도
    print(f"🔄 GitHub 저장소 클론 시도: {{REPO_URL}}")
    proc = subprocess.run(["git", "clone", "--depth", "1", REPO_URL], capture_output=True, text=True)
    if proc.returncode == 0 and (sub / "gyumin_improved.py").exists():
        os.chdir(sub)
        print(f"✅ GitHub 클론 성공! 작업 디렉터리: {{Path.cwd()}}")
        return Path.cwd()

    # 오프라인 / 미푸시 상태일 때는 노트북 내장 소스로 자동 복원
    print("⚠️ GitHub 클론을 건너뛰고 노트북 내장 코드로 로컬 파일을 생성합니다.")
    (cwd / "gyumin_improved.py").write_text(_FALLBACK_IMPROVED, encoding="utf-8")
    (cwd / "gyumin_original.py").write_text(_FALLBACK_ORIGINAL, encoding="utf-8")
    print(f"✅ 내장 소스 파일 생성 완료: {{cwd}}")
    return cwd

WORK_DIR = sync_project_files()
print("📁 파일 목록:", sorted(p.name for p in WORK_DIR.iterdir() if p.suffix in (".py", ".csv", ".xlsx", ".md", ".ipynb")))
"""
    code(cell2_code)

    # Cell 3: Load Modules & Run 8 Completion Tests
    cell3_code = """
#@title 🧪 2. GA 모듈 로드 및 8종 완료 판정 테스트 실행 { display-mode: "form" }
import importlib
import sys
from pathlib import Path

if str(Path.cwd()) not in sys.path:
    sys.path.insert(0, str(Path.cwd()))

if not (Path("gyumin_improved.py").exists() and Path("gyumin_original.py").exists()):
    if "sync_project_files" in globals():
        sync_project_files()
    else:
        raise FileNotFoundError("먼저 1번 셀(GitHub 저장소 연동 및 파일 동기화)을 실행해 주세요.")

import gyumin_improved
import gyumin_original

importlib.reload(gyumin_improved)
importlib.reload(gyumin_original)

print("▶ [규민 개량본 gyumin_improved.py] 완료 판정 테스트:")
gyumin_improved.run_completion_tests()

print("▶ [규민 원본 gyumin_original.py] 완료 판정 테스트:")
gyumin_original.run_completion_tests()
"""
    code(cell3_code)

    # Cell 4: Interactive Colab Form Runner
    cell4_code = """
#@title ⚙️ 3. GA 탐색 실행 (파라미터 조정 가능) { display-mode: "form" }
VERSION = "gyumin_improved (pc=0.6)" #@param ["gyumin_improved (pc=0.6)", "gyumin_original (pc=0.9)"]
MODE = "best_repro (최선 해 재현)" #@param ["best_repro (최선 해 재현)", "single (단일 시드)", "multi_seed (다중 시드)", "ablation (교차율·가중치 비교)"]
SEED = 8 #@param {type:"integer"}
SEEDS = 8 #@param {type:"integer"}
POP_SIZE = 60 #@param {type:"integer"}
MAX_GENS = 500 #@param {type:"integer"}
STALL_GENS = 150 #@param {type:"integer"}
WEIGHT_PRESET = "base" #@param ["base", "fairness", "efficiency"]

is_improved = VERSION.startswith("gyumin_improved")
active_mod = gyumin_improved if is_improved else gyumin_original
default_pc = 0.6 if is_improved else 0.9
weights = active_mod.WEIGHT_PRESETS[WEIGHT_PRESET]

if MODE.startswith("best_repro"):
    repro_seed = 8 if is_improved else 3
    print(f"🎯 [{VERSION}] 최선 일정 재현 실행 (seed={repro_seed}, pc={default_pc})")
    best_res = active_mod.run_ga(
        active_mod.GAConfig(
            pop_size=60,
            max_gens=500,
            stall_gens=150,
            pc=default_pc,
            pm=0.3,
            seed=repro_seed,
            weights=weights,
        )
    )
    print(active_mod.format_report(best_res))

elif MODE.startswith("single"):
    print(f"🔍 [{VERSION}] 단일 시드 탐색 (seed={SEED}, pc={default_pc}, weight={WEIGHT_PRESET})")
    best_res = active_mod.run_ga(
        active_mod.GAConfig(
            pop_size=POP_SIZE,
            max_gens=MAX_GENS,
            stall_gens=STALL_GENS,
            pc=default_pc,
            pm=0.3,
            seed=SEED,
            weights=weights,
        )
    )
    print(active_mod.format_report(best_res))

elif MODE.startswith("multi_seed"):
    print(f"📊 [{VERSION}] 다중 시드 탐색 (seeds=0..{SEEDS - 1}, pc={default_pc}, weight={WEIGHT_PRESET})")
    best_res = active_mod.run_multi_seed(
        seeds=SEEDS,
        pc=default_pc,
        pm=0.3,
        pop_size=POP_SIZE,
        max_gens=MAX_GENS,
        stall_gens=STALL_GENS,
        weights=weights,
        label=VERSION,
    )
    print(active_mod.format_report(best_res))

else:
    print(f"🔬 [{VERSION}] 교차 확률 및 가중치 민감도 실험 (seeds=0..{SEEDS - 1})")
    print("\\n--- 교차 확률 비교 (pc = 0.0, 0.5, 0.9) ---")
    for pc_val in (0.0, 0.5, 0.9):
        active_mod.run_multi_seed(
            seeds=SEEDS,
            pc=pc_val,
            pm=0.3,
            pop_size=POP_SIZE,
            max_gens=MAX_GENS,
            stall_gens=0,
            label=f"pc={pc_val}",
        )
    print("\\n--- 가중치 민감도 비교 (base / fairness / efficiency, 동일 base 가중치 재평가 포함) ---")
    base_weights = active_mod.WEIGHT_PRESETS["base"]
    best_res = None
    best_base_cost = float("inf")
    best_w_name = ""
    for w_name, w_vec in active_mod.WEIGHT_PRESETS.items():
        res_w = active_mod.run_multi_seed(
            seeds=SEEDS,
            pc=default_pc,
            pm=0.3,
            pop_size=POP_SIZE,
            max_gens=MAX_GENS,
            stall_gens=STALL_GENS,
            weights=w_vec,
            label=f"weight={w_name}",
        )
        base_cost, _, _ = active_mod.evaluate_schedule(
            active_mod.decode(res_w.best), weights=base_weights
        )
        if base_cost < best_base_cost:
            best_base_cost = base_cost
            best_res = res_w
            best_w_name = w_name
        print(
            f"  -> {w_name} 최선: 자체 비용 C_{w_name}={res_w.best.cost:.4f} | "
            f"base 기준 재평가 C_base={base_cost:.4f} | "
            f"G1~G7={[round(x, 4) for x in res_w.best.g_vals]}"
        )
    print(f"\\n🏆 [동일 기준(base 가중치) 재평가 최종안 선정: weight={best_w_name}, C_base={best_base_cost:.4f}]")
    if best_w_name != "base":
        best_res_base = active_mod.GAResult(
            best=best_res.best.clone(),
            history=best_res.history,
            evaluations=best_res.evaluations,
            elapsed_sec=best_res.elapsed_sec,
            stopped_gen=best_res.stopped_gen,
        )
        c_b, f_b, g_b = active_mod.evaluate_schedule(
            active_mod.decode(best_res_base.best), weights=base_weights
        )
        best_res_base.best.cost = c_b
        best_res_base.best.fitness = f_b
        best_res_base.best.g_vals = g_b
        best_res = best_res_base
    print(active_mod.format_report(best_res))
"""
    code(cell4_code)

    # Cell 5: Professor Template Table (Stadium Schedule & Daily Distance) + CSV Export
    cell5_code = """
#@title 📋 4. 교수님 템플릿 양식(구장별 대진표 & 일별 이동거리표) 출력 및 CSV 저장 { display-mode: "form" }
import csv
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from IPython.display import display
except ImportError:
    display = print

if "best_res" not in globals() or best_res is None:
    raise RuntimeError("먼저 3번 셀(GA 탐색 실행)을 실행해 주세요.")

CITIES = ("서울", "인천", "대전", "광주", "대구", "부산")
TEAMS = active_mod.TEAMS
DIST = active_mod.DIST
N_TEAMS = active_mod.N_TEAMS
N_DAYS = active_mod.N_DAYS

sched = active_mod.decode(best_res.best)

# 1) 구장별 대진표 (Schedule)
sched_rows = []
for d_idx, day in enumerate(sched, start=1):
    row = {"Day": f"Day {d_idx}"}
    for city in CITIES:
        row[city] = ""
    for home, away in day:
        row[CITIES[home]] = f"{TEAMS[away]} @ {TEAMS[home]}"
    sched_rows.append(row)

# 2) 구단별 일별 이동거리표 (Distance)
loc = [[t] * (N_DAYS + 2) for t in range(N_TEAMS)]
for d_idx, day in enumerate(sched):
    for home, away in day:
        loc[home][d_idx + 1] = home
        loc[away][d_idx + 1] = home

dist_rows = []
for r in range(N_DAYS + 1):
    label = f"Day {r + 1}" if r < N_DAYS else "복귀"
    row = {"Day": label}
    for t in range(N_TEAMS):
        row[TEAMS[t]] = DIST[loc[t][r]][loc[t][r + 1]]
    dist_rows.append(row)

if pd is not None:
    df_sched = pd.DataFrame(sched_rows).set_index("Day")
    df_dist = pd.DataFrame(dist_rows).set_index("Day")
    print(f"🏟️ [10일 경기 일정 - 구장별 표기] (C = {best_res.best.cost:.4f})")
    display(df_sched)
    print("\\n🚌 [구단별 일일 및 복귀 이동거리 (km)]")
    display(df_dist)
else:
    print("Schedule:", sched_rows)
    print("Distance:", dist_rows)

# 교수님 템플릿 CSV 형식으로 저장
out_csv = Path("schedule_result.csv")
with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["Schedule", "", "", "", "", "", ""])
    writer.writerow(["", *CITIES])
    for r in sched_rows:
        writer.writerow([r["Day"], *(r[c] for c in CITIES)])
    for _ in range(5):
        writer.writerow(["", "", "", "", "", "", ""])
    writer.writerow(["Distance", "", "", "", "", "", ""])
    writer.writerow(["", "", "", "", "", "", ""])
    writer.writerow(["", *TEAMS])
    for r in dist_rows:
        writer.writerow([r["Day"], *(r[t] for t in TEAMS)])
    writer.writerow(["", "", "", "", "", "", ""])
    writer.writerow([f"C = {best_res.best.cost:.4f} (v2), {VERSION}", "", "", "", "", "", ""])

print(f"💾 CSV 저장 완료: {out_csv.resolve()}")
"""
    code(cell5_code)

    # Cell 6: Convergence & Diversity Plot
    cell6_code = """
#@title 📈 5. 세대별 수렴 곡선 및 개체군 다양성 시각화 { display-mode: "form" }
import matplotlib.pyplot as plt
from matplotlib import font_manager

if "best_res" not in globals() or best_res is None:
    raise RuntimeError("먼저 3번 셀(GA 탐색 실행)을 실행해 주세요.")

# 한글 폰트 탐색 (미설치 환경에서는 깨짐 방지를 위해 영문 라벨 사용)
_KOR_FONT_CANDIDATES = ("NanumGothic", "Malgun Gothic", "AppleGothic", "Noto Sans CJK KR")
_available_fonts = {f.name for f in font_manager.fontManager.ttflist}
_selected_kor_font = next((name for name in _KOR_FONT_CANDIDATES if name in _available_fonts), None)
if _selected_kor_font:
    plt.rcParams["font.family"] = _selected_kor_font
plt.rcParams["axes.unicode_minus"] = False

gens = [h[0] for h in best_res.history]
best_costs = [h[1] for h in best_res.history]
avg_costs = [h[2] for h in best_res.history]
distincts = [h[3] for h in best_res.history]

prof_cost, _, _ = active_mod.evaluate_schedule(active_mod.professor_example_schedule())

fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), dpi=120)

# Subplot 1: Cost Convergence
ax1 = axes[0]
ax1.plot(gens, best_costs, label=f"Best C(x) = {best_costs[-1]:.4f}", color="#1f77b4", linewidth=2.2)
ax1.plot(gens, avg_costs, label="Population Avg C(x)", color="#ff7f0e", alpha=0.75, linewidth=1.4)
ax1.axhline(prof_cost, color="#d62728", linestyle="--", linewidth=1.3, label=f"Professor Example ({prof_cost:.3f})")
ax1.set_xlabel("Generation" if not _selected_kor_font else "세대 (Generation)")
ax1.set_ylabel("Normalized Cost C(x)" if not _selected_kor_font else "정규화 비용 C(x)")
ax1.set_title(
    f"Convergence Curve ({VERSION})" if not _selected_kor_font else f"GA 수렴 곡선 ({VERSION})"
)
ax1.grid(True, alpha=0.3)
ax1.legend()

# Subplot 2: Phenotype Diversity
ax2 = axes[1]
ax2.plot(gens, distincts, color="#2ca02c", linewidth=1.8, label="Distinct Schedules")
ax2.set_ylim(0, max(distincts) * 1.12 if distincts else 65)
ax2.set_xlabel("Generation" if not _selected_kor_font else "세대 (Generation)")
ax2.set_ylabel("Distinct Schedules" if not _selected_kor_font else "고유 일정 수")
ax2.set_title(
    "Population Phenotype Diversity" if not _selected_kor_font else "개체군 표현형 다양성 (고유 일정 수)"
)
ax2.grid(True, alpha=0.3)
ax2.legend()

plt.tight_layout()
plt.show()
"""
    code(cell6_code)

    notebook = {
        "cells": cells,
        "metadata": {
            "colab": {
                "name": NOTEBOOK_NAME,
                "provenance": [],
                "toc_visible": True,
            },
            "kernelspec": {
                "display_name": "Python 3",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }

    nb_path = ROOT / NOTEBOOK_NAME
    nb_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return nb_path


def main() -> None:
    csv_to_xlsx(ROOT / "gyumin_improved.csv", ROOT / "gyumin_improved.xlsx")
    csv_to_xlsx(ROOT / "gyumin_original.csv", ROOT / "gyumin_original.xlsx")
    nb_path = build_notebook()
    print(f"✅ XLSX 변환 완료: gyumin_improved.xlsx, gyumin_original.xlsx")
    print(f"✅ Colab 노트북 생성 완료: {nb_path}")


if __name__ == "__main__":
    main()
