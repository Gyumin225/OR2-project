"""최종 일정 내보내기: 기본 설정(설정 A)으로 한 시드를 실행하고 과제 템플릿 양식의 CSV·XLSX로 저장한다.

사용 예:
  python export_schedule.py --seed 33   # 최종 채택 해 -> best_schedule_C1.634.csv / .xlsx
  python export_schedule.py --seed 8    # 30시드 내 최선 해 (C = 1.6889)

CSV 양식은 저장소의 gyumin_improved.csv(시드 8)와 같다.
위쪽은 구장(연고지)별 일자별 대진표(원정 @ 홈), 아래쪽은 구단별 일자별 이동거리(Distance 표)이다.
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
from pathlib import Path

import gyumin_improved as gi

ROOT = Path(__file__).resolve().parent
CITIES = ("서울", "인천", "대전", "광주", "대구", "부산")  # 구단 순서(MBC, 삼미, OB, 해태, 삼성, 롯데)의 연고지


def schedule_rows(schedule, cost: float, seed: int):
    n, d = gi.N_TEAMS, gi.N_DAYS
    blank = [""] * (n + 1)
    rows = [["Schedule"] + [""] * n, [""] + list(CITIES)]
    loc = [[t] * (d + 2) for t in range(n)]  # 0일·11일은 연고지
    for r, day in enumerate(schedule):
        cells = [""] * n
        for home, away in day:
            cells[home] = f"{gi.TEAMS[away]} @ {gi.TEAMS[home]}"
            loc[home][r + 1] = home
            loc[away][r + 1] = home
        rows.append([f"Day {r + 1}"] + cells)
    rows += [blank] * 5
    rows += [["Distance"] + [""] * n, blank, [""] + list(gi.TEAMS)]
    totals = [0] * n
    for r in range(d + 1):
        label = f"Day {r + 1}" if r < d else "복귀"
        steps = [gi.DIST[loc[t][r]][loc[t][r + 1]] for t in range(n)]
        totals = [a + b for a, b in zip(totals, steps)]
        rows.append([label] + [str(v) for v in steps])
    rows.append(blank)
    rows.append([f"C = {cost:.4f} (v2), gyumin_improved, setting A, seed {seed}"] + [""] * n)
    return rows, totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=33)
    args = parser.parse_args()

    res = gi.run_ga(gi.GAConfig(seed=args.seed))  # 기본 설정(설정 A)
    schedule = gi.decode(res.best)
    assert gi.is_feasible(schedule)
    cost = float(res.best.cost)
    rows, totals = schedule_rows(schedule, cost, args.seed)

    stem = f"best_schedule_C{cost:.3f}"
    csv_path = ROOT / f"{stem}.csv"
    def write_csv() -> None:  # 저장소의 기존 CSV와 같은 줄바꿈(CRLF)
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f, lineterminator="\r\n").writerows(rows)

    write_csv()
    spec = importlib.util.spec_from_file_location("build_colab_notebook", ROOT / "build_colab_notebook.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.csv_to_xlsx(csv_path, ROOT / f"{stem}.xlsx")
    write_csv()  # csv_to_xlsx가 줄바꿈을 바꾸므로 다시 저장

    print(f"seed {args.seed}: C = {cost:.4f}, 구단별 총 이동 {dict(zip(gi.TEAMS, totals))}, 합계 {sum(totals)}")
    print(f"저장: {stem}.csv, {stem}.xlsx")


if __name__ == "__main__":
    main()
