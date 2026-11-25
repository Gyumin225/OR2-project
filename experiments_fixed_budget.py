"""고정 평가 예산 비교 실험 (보고서 4장 표 4-1, 4-3과 표 2-5, 3-6의 '평가 횟수 고정' 행 재현)

`gyumin_improved.py --mode ablation`은 정체 종료나 최대 세대로 멈추므로 설정마다 평가 횟수가 다르다.
보고서 4장의 비교 실험은 설정 간 공정한 비교를 위해 다음 조건으로 실행하였고, 이 스크립트가 그 조건을 그대로 따른다.

  - 시드 0–29 (30회), 정체 종료 끔(stall_gens = 0)
  - 실제 비용 계산 횟수(evaluate_schedule 호출, 캐시에서 가져온 값 제외)가 17,460회에 이르면 종료
    (17,460 = 기본 설정 N = 60으로 정체 종료 시 평균적으로 쓰는 횟수에 맞춘 값)
  - 각 실행의 결과는 그때까지 계산한 일정 중 비용이 가장 낮은 일정
  - 변경하지 않은 파라미터는 채택 설정(N = 60, pc = 0.6, pm = 0.3, k = 3, 엘리트 2, 중복 제거)과 같음

사용 예 (Python 3, 표준 라이브러리만 사용):
  python experiments_fixed_budget.py --table 4-1     # 표 4-1 (하이퍼파라미터 9개 설정)
  python experiments_fixed_budget.py --table 4-3     # 표 4-3 (가중치 프리셋 3개)
  python experiments_fixed_budget.py --table 2-5     # 표 2-5 (교차 확률 4개, 평가 횟수 고정 열)
  python experiments_fixed_budget.py --table all     # 위 세 표 모두
  python experiments_fixed_budget.py --table 3-5     # (참고) 기본 설정 시드 0–239 실행 기록 (표 3-5, 약 4분)

결과는 results/ 폴더에 시드별 CSV(fixed_budget_<표>_runs.csv)와 요약 CSV(fixed_budget_<표>_summary.csv)로 저장된다.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import gyumin_improved as gi

BUDGET = 17460
EXAMPLE_COST = 2.0131  # 과제 예시 일정의 비용 (1.5절 비용함수)


class BudgetReached(Exception):
    """실제 비용 계산 횟수가 예산에 도달함"""


def run_fixed_budget(cfg: gi.GAConfig, budget: int = BUDGET) -> Dict[str, object]:
    """run_ga를 그대로 실행하되, 실제 비용 계산이 budget회에 이르면 멈춘다."""
    original_eval = gi.evaluate_schedule
    original_select = gi.tournament_select
    state = {"n": 0, "best": (math.inf, None), "selects": 0}

    def counted_eval(schedule, *args, **kwargs):
        if state["n"] >= budget:
            raise BudgetReached
        result = original_eval(schedule, *args, **kwargs)
        state["n"] += 1
        if result[0] < state["best"][0]:
            state["best"] = (result[0], result[2])
        return result

    def counted_select(*args, **kwargs):
        state["selects"] += 1
        return original_select(*args, **kwargs)

    gi.evaluate_schedule = counted_eval
    gi.tournament_select = counted_select
    t0 = time.perf_counter()
    try:
        gi.run_ga(cfg)
    except BudgetReached:
        pass
    finally:
        gi.evaluate_schedule = original_eval
        gi.tournament_select = original_select
    cost, g_vals = state["best"]
    # 자식 1개당 토너먼트 2회 -> 진행 세대 수(마지막 미완료 세대 포함) 추정
    children_per_gen = cfg.pop_size - cfg.elite_size
    gens = math.ceil(state["selects"] / (2 * children_per_gen))
    return {
        "cost": cost,
        "g": g_vals,
        "evals": state["n"],
        "gens": gens,
        "sec": time.perf_counter() - t0,
    }


# ---------------------------------------------------------------------------
# 통계 (외부 패키지 없이 Welch t 신뢰구간)
# ---------------------------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    p = 0.5 * _betainc(df / 2.0, 0.5, x)
    return 1.0 - p if t >= 0 else p


def t_quantile(p: float, df: float) -> float:
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def welch_ci(x: Sequence[float], y: Sequence[float], alpha: float = 0.05) -> Tuple[float, float, float]:
    """평균 차이 mean(x) - mean(y)와 Welch t 신뢰구간 (하한, 상한)"""
    nx, ny = len(x), len(y)
    vx, vy = statistics.variance(x) / nx, statistics.variance(y) / ny
    se = math.sqrt(vx + vy)
    df = (vx + vy) ** 2 / (vx ** 2 / (nx - 1) + vy ** 2 / (ny - 1))
    diff = statistics.mean(x) - statistics.mean(y)
    q = t_quantile(1.0 - alpha / 2.0, df)
    return diff, diff - q * se, diff + q * se


def paired_ci(x: Sequence[float], y: Sequence[float], alpha: float = 0.05) -> Tuple[float, float, float]:
    """같은 시드끼리 짝지은 차이 x - y의 평균과 t 신뢰구간"""
    d = [a - b for a, b in zip(x, y)]
    m, s = statistics.mean(d), statistics.stdev(d)
    q = t_quantile(1.0 - alpha / 2.0, len(d) - 1)
    half = q * s / math.sqrt(len(d))
    return m, m - half, m + half


# ---------------------------------------------------------------------------
# 실험 정의
# ---------------------------------------------------------------------------
def settings_for(table: str) -> List[Tuple[str, str, Dict[str, object]]]:
    """(변경 항목, 설정 이름, GAConfig 변경값) 목록. 첫 행이 기준."""
    if table == "4-1":
        return [
            ("기준", "채택 설정", {}),
            ("개체 수 N", "30", {"pop_size": 30}),
            ("개체 수 N", "120", {"pop_size": 120}),
            ("기본 변이율 pm", "0.1", {"pm": 0.1}),
            ("기본 변이율 pm", "0.6", {"pm": 0.6}),
            ("교차율 pc", "0.0", {"pc": 0.0}),
            ("교차율 pc", "0.9", {"pc": 0.9}),
            ("토너먼트 크기 k", "2", {"tournament_k": 2}),
            ("토너먼트 크기 k", "5", {"tournament_k": 5}),
        ]
    if table == "4-3":
        return [
            ("가중치", name, {"weights": w}) for name, w in gi.WEIGHT_PRESETS.items()
        ]
    if table == "2-5":
        return [
            ("교차율 pc", "0.6 (채택)", {"pc": 0.6}),
            ("교차율 pc", "0.9", {"pc": 0.9}),
            ("교차율 pc", "0.3", {"pc": 0.3}),
            ("교차율 pc", "0 (교차 없음)", {"pc": 0.0}),
        ]
    raise ValueError(table)


def run_table(table: str, seeds: int, budget: int, out_dir: Path) -> None:
    settings = settings_for(table)
    out_dir.mkdir(parents=True, exist_ok=True)
    runs_path = out_dir / f"fixed_budget_{table}_runs.csv"
    summary_path = out_dir / f"fixed_budget_{table}_summary.csv"
    costs: Dict[str, List[float]] = {}
    rows = []
    print(f"\n=== 표 {table}: 시드 0–{seeds - 1}, 실제 비용 계산 {budget:,}회 고정, 정체 종료 끔 ===")
    for item, name, change in settings:
        key = f"{item} | {name}"
        costs[key] = []
        gens = []
        t0 = time.perf_counter()
        for s in range(seeds):
            cfg = gi.GAConfig(seed=s, max_gens=10 ** 6, stall_gens=0, **change)
            res = run_fixed_budget(cfg, budget)
            costs[key].append(res["cost"])
            gens.append(res["gens"])
            rows.append([table, item, name, s, f"{res['cost']:.6f}", res["evals"], res["gens"]]
                        + [f"{v:.6f}" for v in res["g"]])
        print(f"  {key:<24} 평균 {statistics.mean(costs[key]):.3f} ± {statistics.stdev(costs[key]):.3f}"
              f" | 최선 {min(costs[key]):.4f} | 진행 세대 약 {statistics.mean(gens):.0f}"
              f" | {time.perf_counter() - t0:.0f}s")

    with runs_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["table", "item", "setting", "seed", "best_cost", "evals", "gens_approx",
                    "G1", "G2", "G3", "G4", "G5", "G6", "G7"])
        w.writerows(rows)

    if table == "4-3":
        # 가중치가 다르면 비용 C의 크기를 서로 비교할 수 없으므로, 최선 일정의 지표 G1–G7 평균 ± 표본표준편차를 낸다.
        summary = []
        print("\n  최선 일정의 지표 평균 ± 표본표준편차")
        for item, name, _ in settings:
            g_cols = [[float(r[7 + k]) for r in rows if r[2] == name] for k in range(7)]
            cells = [f"{statistics.mean(c):.5f} ± {statistics.stdev(c):.5f}" for c in g_cols]
            summary.append([table, name] + cells)
            print(f"  {name:<11} " + " | ".join(f"G{k + 1} {cells[k]}" for k in range(7)))
        with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["table", "weights", "G1", "G2", "G3", "G4", "G5", "G6", "G7"])
            w.writerows(summary)
        print(f"  저장: {runs_path}, {summary_path}")
        return

    base_key = f"{settings[0][0]} | {settings[0][1]}"
    base = costs[base_key]
    m = len(settings) - 1  # 기준과 비교하는 설정 수 (Bonferroni 보정용)
    summary = []
    print(f"\n  기준 대비 차이 (Welch 95% CI / Bonferroni 보정 {m}개 비교 CI / 짝지은 차이 95% CI)")
    for item, name, _ in settings:
        key = f"{item} | {name}"
        c = costs[key]
        row = [table, item, name, len(c), f"{statistics.mean(c):.4f}", f"{statistics.stdev(c):.4f}",
               f"{min(c):.4f}", f"{max(c):.4f}", sum(1 for v in c if v < EXAMPLE_COST)]
        if key != base_key:
            d, lo, hi = welch_ci(c, base)
            _, blo, bhi = welch_ci(c, base, alpha=0.05 / m)
            pd, plo, phi = paired_ci(c, base)
            row += [f"{d:+.4f}", f"{lo:+.4f}", f"{hi:+.4f}", f"{blo:+.4f}", f"{bhi:+.4f}",
                    f"{plo:+.4f}", f"{phi:+.4f}"]
            print(f"  {key:<24} {d:+.3f} | ({lo:+.3f}, {hi:+.3f}) | ({blo:+.3f}, {bhi:+.3f})"
                  f" | ({plo:+.3f}, {phi:+.3f})")
        else:
            row += [""] * 7
        summary.append(row)
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["table", "item", "setting", "n", "mean", "sd", "best", "worst", "better_than_example",
                    "diff_vs_base", "welch95_lo", "welch95_hi", "bonferroni_lo", "bonferroni_hi",
                    "paired95_lo", "paired95_hi"])
        w.writerows(summary)
    print(f"  저장: {runs_path}, {summary_path}")


def run_setting_a(seeds: int, out_dir: Path) -> None:
    """기본 설정(설정 A: 정체 150세대 / 최대 500세대)을 시드 0..seeds-1로 실행 (보고서 3장 표 3-5).

    gyumin_improved.py --seeds N과 같은 실행이며, 콘솔 '총 평가'(복사된 자식 포함)와 함께
    실제 비용 계산 횟수(캐시 제외)를 시드별로 기록한다.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"setting_A_seeds_0-{seeds - 1}.csv"
    original_eval = gi.evaluate_schedule
    count = {"n": 0}

    def counted_eval(schedule, *args, **kwargs):
        count["n"] += 1
        return original_eval(schedule, *args, **kwargs)

    rows, costs, gens, evals = [], [], [], []
    gi.evaluate_schedule = counted_eval
    try:
        for s in range(seeds):
            count["n"] = 0
            res = gi.run_ga(gi.GAConfig(seed=s))
            costs.append(res.best.cost)
            gens.append(res.stopped_gen)
            evals.append(count["n"])
            best_gen = next(g for g, c, _, _ in res.history if c <= res.best.cost + 1e-12)
            rows.append([s, f"{res.best.cost:.6f}", res.stopped_gen, best_gen, count["n"], res.evaluations]
                        + [f"{v:.6f}" for v in res.best.g_vals])
    finally:
        gi.evaluate_schedule = original_eval
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["seed", "best_cost", "stopped_gen", "best_found_gen", "real_evals", "printed_evals",
                    "G1", "G2", "G3", "G4", "G5", "G6", "G7"])
        w.writerows(rows)
    best_seed = min(range(seeds), key=lambda i: costs[i])
    print(f"\n=== 설정 A, 시드 0–{seeds - 1} ===")
    print(f"  평균 {statistics.mean(costs):.3f} ± {statistics.stdev(costs):.3f} | 중앙값 {statistics.median(costs):.3f}"
          f" | 최선 {min(costs):.4f}(시드 {best_seed}) | 최악 {max(costs):.3f}"
          f" | 예시보다 좋음 {sum(1 for c in costs if c < EXAMPLE_COST)}/{seeds}")
    print(f"  평균 종료 세대 {statistics.mean(gens):.0f} (중앙값 {statistics.median(gens):.0f})"
          f" | 실제 비용 계산 평균 {statistics.mean(evals):,.0f}회")
    print(f"  저장: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="고정 평가 예산 비교 실험 (보고서 4장)")
    parser.add_argument("--table", choices=["4-1", "4-3", "2-5", "all", "3-5"], default="4-1")
    parser.add_argument("--seeds", type=int, default=None,
                        help="시드 수 (기본: 고정 예산 표는 30, --table 3-5는 240)")
    parser.add_argument("--budget", type=int, default=BUDGET)
    parser.add_argument("--out", default="results")
    args = parser.parse_args()
    if args.table == "3-5":
        run_setting_a(args.seeds or 240, Path(args.out))
        return
    tables = ["4-1", "4-3", "2-5"] if args.table == "all" else [args.table]
    for t in tables:
        run_table(t, args.seeds or 30, args.budget, Path(args.out))


if __name__ == "__main__":
    main()
