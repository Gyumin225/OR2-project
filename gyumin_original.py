"""
O.R.2 프로야구(1982 KBO 6개 구단) 10일 경기 일정 최적화 — 통합 최적안
====================================================================
각 설계안에서 검증된 최적 요소만 통합한 최종 GA 코드 (Python 3 표준 라이브러리 전용)

[채택 구성 및 출처]
1. 염색체 표현 및 제약 처리 (유진안 + 호연안):
   - 원형법(Circle Method) 기반 특수 인코딩 x = (sigma, pi, h) (유전자 31개)
     * sigma: 길이 6 순열 (0..5) — 자리 p에 배정된 구단
     * pi   : 길이 10 순열 (0..9) — d일차에 사용할 기본 매칭 사본 (0..4=사본 A, 5..9=사본 B)
     * h    : 길이 15 이진 비트 (0/1) — 각 쌍 n의 사본 A 홈팀 결정 (사본 B는 자동 반대)
   - 디코딩 규칙 자체가 두 하드 제약((1) 매일 모든 팀 1경기, (2) 각 쌍 홈1·원정1)을
     100% 보장하므로 페널티 계수 튜닝이나 백트래킹 수리 단계가 불필요함 (교안 29쪽 1순위)

2. 적합도 함수 (OR2_적합도함수_v2.md + 진우안):
   - 7개 공정성 지표(G1~G7) + 두 기준점 정규화(G_star, G0) + 가중치 w=(1,1,1,1,1,1,3)
   - 정규화 비용 C(x)가 음수가 될 수 있으므로 토너먼트 선택에서는 C(x)를 직접 최소화하고,
     f(x) = 1 / (1 + C(x))는 보고서·그래프용 보조 지표로만 계산 (진우안)

3. GA 연산자 및 세대 교체 (유진안 + 규민안):
   - 초기 개체군: 무작위 (sigma, pi, h) N=60개 (디코딩 일정 기준 중복 제거 + 독립 검증)
   - 선택: 토너먼트 선택 (k=3, 비복원 k개 추출 후 최소 C(x) 선택, 교안 39~41쪽)
   - 교차: pc=0.9 (4장 실험용으로 0.0, 0.5, 0.9 설정 가능)
     * sigma: 부모 A 상속 / pi: 순서 교차(OX, 교안 50쪽) / h: 1점 교차(교안 44쪽)
   - 변이: 염색체당 확률 pm=0.3, 실행 가능성 보존 4종 연산자 균등 선택 (교안 52~54쪽)
     * (a) 일자 교환 (pi swap) / (b) 구간 역전 (pi inversion)
     * (c) 홈/원정 비트 뒤집기 (h bit-flip) / (d) 구단 교환 (sigma swap)
   - 세대 교체: 엘리트 보존(e=2, 교안 57쪽) + 디코딩 일정 기준 중복 제거(조기 수렴 방지)
   - 종료 조건: 최대 세대(G_max=500, 약 29,060회 평가) 또는 정체(stall=150세대) (규민안)
   - 다양성 추적: 매 세대 디코딩 기준 서로 다른 일정 수(distinct_schedules) 기록 (규민안)

4. 검증 및 재현성 (진우안):
   - 독립 제약 검증 함수 is_feasible() 및 8가지 완료 판정 테스트 내장
   - 시드 고정 재현성, 다중 시드 탐색, 교차율/가중치 민감도 실험 모드 지원
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------------------
# 1. 문제 상수 및 거리 행렬 (과제 안내서 Table 1 / OR2_적합도함수_v2.md)
# ---------------------------------------------------------------------------
TEAMS: Tuple[str, ...] = ("MBC", "삼미", "OB", "해태", "삼성", "롯데")
N_TEAMS: int = 6
N_DAYS: int = 10

# 구단 인덱스: 0=MBC(서울), 1=삼미(인천), 2=OB(대전), 3=해태(광주), 4=삼성(대구), 5=롯데(부산)
DIST: Tuple[Tuple[int, ...], ...] = (
    (0,   35,  165, 330, 300, 400),  # MBC (서울)  -> B_t = 2,460
    (35,  0,   180, 320, 320, 420),  # 삼미 (인천) -> B_t = 2,550
    (165, 180, 0,   170, 150, 250),  # OB (대전)   -> B_t = 1,830
    (330, 320, 170, 0,   210, 270),  # 해태 (광주) -> B_t = 2,600
    (300, 320, 150, 210, 0,   100),  # 삼성 (대구) -> B_t = 2,160
    (400, 420, 250, 270, 100, 0),    # 롯데 (부산) -> B_t = 2,880
)

# 기준 거리 B_t = 2 * sum_{j != t} d_{tj}
B_T: Tuple[int, ...] = tuple(2 * sum(row) for row in DIST)

ALL_GAMES: Tuple[Tuple[int, int], ...] = tuple(
    (i, j) for i in range(N_TEAMS) for j in range(N_TEAMS) if i != j
)

# Circle Method 5개 기본 완전 매칭 (자리 5 고정, 0~4 회전)
BASE_MATCHINGS: Tuple[Tuple[Tuple[int, int], ...], ...] = (
    ((0, 5), (1, 4), (2, 3)),  # M_0
    ((1, 5), (2, 0), (3, 4)),  # M_1
    ((2, 5), (3, 1), (4, 0)),  # M_2
    ((3, 5), (4, 2), (0, 1)),  # M_3
    ((4, 5), (0, 3), (1, 2)),  # M_4
)

# 적합도 v2 기준값(G0: 무작위 1,000개 평균), 이상값(G_STAR), 가중치 프리셋
G0_DEFAULT: Tuple[float, ...] = (11611.0, 2379.0, 0.112, 1229.0, 4.44, 1.88, 3.15)
G_STAR_DEFAULT: Tuple[float, ...] = (7620.0, 1485.0, 0.005, 840.0, 1.0, 0.0, 0.0)
WEIGHT_PRESETS: Dict[str, Tuple[float, ...]] = {
    "base": (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 3.0),        # 기준
    "fairness": (1.0, 2.0, 2.0, 2.0, 2.0, 1.0, 3.0),    # 공정성 중시
    "efficiency": (2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 3.0),  # 효율 중시
}

# 타입 별칭
Game = Tuple[int, int]              # (home_team_idx, away_team_idx)
DaySchedule = Tuple[Game, ...]      # 하루 3경기
Schedule = Tuple[DaySchedule, ...]  # 10일 일정


# ---------------------------------------------------------------------------
# 2. 염색체 표현, 디코딩, 독립 제약 검증
# ---------------------------------------------------------------------------
@dataclass
class Chromosome:
    """원형법 특수 인코딩 x = (sigma, pi, h)"""
    sigma: List[int]  # 길이 6 순열 (0..5): 자리 p에 배정된 구단
    pi: List[int]     # 길이 10 순열 (0..9): d일차 매칭 사본 (0..4=A, 5..9=B)
    h: List[int]      # 길이 15 비트 (0/1): 쌍 n의 사본 A 홈 결정

    # 디코딩 및 평가 결과 캐시
    schedule: Optional[Schedule] = None
    sched_key: Optional[Tuple[Tuple[Game, ...], ...]] = None
    cost: Optional[float] = None
    fitness: Optional[float] = None
    g_vals: Optional[Tuple[float, ...]] = None

    def invalidate(self) -> None:
        self.schedule = None
        self.sched_key = None
        self.cost = None
        self.fitness = None
        self.g_vals = None

    def clone(self) -> "Chromosome":
        return Chromosome(
            sigma=list(self.sigma),
            pi=list(self.pi),
            h=list(self.h),
            schedule=self.schedule,
            sched_key=self.sched_key,
            cost=self.cost,
            fitness=self.fitness,
            g_vals=self.g_vals,
        )


def decode(chrom: Chromosome) -> Schedule:
    """(sigma, pi, h) -> 10일 경기 일정 (각 날 3경기 (home, away))"""
    if chrom.schedule is not None:
        return chrom.schedule

    sigma = chrom.sigma
    pi = chrom.pi
    h = chrom.h
    days: List[DaySchedule] = []
    keys: List[Tuple[Game, ...]] = []

    for d in range(N_DAYS):
        c = pi[d]
        k = c % 5
        is_copy_a = c < 5
        games: List[Game] = []
        for idx, (p, q) in enumerate(BASE_MATCHINGS[k]):
            n = 3 * k + idx
            home_is_p = (h[n] == 1) if is_copy_a else (h[n] == 0)
            games.append((sigma[p], sigma[q]) if home_is_p else (sigma[q], sigma[p]))
        day_t = tuple(games)
        days.append(day_t)
        keys.append(tuple(sorted(day_t)))

    chrom.schedule = tuple(days)
    chrom.sched_key = tuple(keys)
    return chrom.schedule


def schedule_key(chrom: Chromosome) -> Tuple[Tuple[Game, ...], ...]:
    """디코딩된 일정(표현형) 기준 정규화 키 (중복 제거 및 다양성 측정용)"""
    if chrom.sched_key is None:
        decode(chrom)
    assert chrom.sched_key is not None
    return chrom.sched_key


def is_feasible(schedule: Sequence[Sequence[Game]]) -> bool:
    """독립 하드 제약 검증:
    1) 정확히 10일
    2) 매일 3경기이며 6개 구단이 정확히 1번씩 등장
    3) 전체 30개 순서쌍 (홈, 원정)이 정확히 1번씩 등장
    4) 구단별 홈 5경기, 원정 5경기 (교차 검증)
    """
    if len(schedule) != N_DAYS:
        return False

    seen_games: List[Game] = []
    home_cnt = [0] * N_TEAMS
    away_cnt = [0] * N_TEAMS

    for day in schedule:
        if len(day) != 3:
            return False
        day_teams: List[int] = []
        for home, away in day:
            if not (0 <= home < N_TEAMS and 0 <= away < N_TEAMS) or home == away:
                return False
            day_teams.append(home)
            day_teams.append(away)
            home_cnt[home] += 1
            away_cnt[away] += 1
            seen_games.append((home, away))
        if sorted(day_teams) != [0, 1, 2, 3, 4, 5]:
            return False

    if sorted(seen_games) != sorted(ALL_GAMES):
        return False
    if any(c != 5 for c in home_cnt) or any(c != 5 for c in away_cnt):
        return False
    return True


# ---------------------------------------------------------------------------
# 3. 적합도 함수 v2 (G1~G7, 두 기준점 정규화, C(x) 최소화)
# ---------------------------------------------------------------------------
def compute_g_values(schedule: Schedule) -> Tuple[float, ...]:
    """일정의 7개 원시 공정성 지표 G1~G7 계산 (탐색 루프 최적화 버전)"""
    loc = [[t] * (N_DAYS + 2) for t in range(N_TEAMS)]
    home_flag = [[0] * N_DAYS for _ in range(N_TEAMS)]
    opp = [[-1] * N_DAYS for _ in range(N_TEAMS)]

    for d in range(N_DAYS):
        d1 = d + 1
        for h, a in schedule[d]:
            loc[h][d1] = h
            loc[a][d1] = h
            home_flag[h][d] = 1
            opp[h][d] = a
            opp[a][d] = h

    total_dist = 0
    max_dist = 0
    max_trip_all = 0
    max_long_all = 0
    streak_excess = 0
    rho_list = [0.0] * N_TEAMS

    for t in range(N_TEAMS):
        lt = loc[t]
        ht = home_flag[t]
        steps = [DIST[lt[r]][lt[r + 1]] for r in range(N_DAYS + 1)]
        dt = sum(steps)
        total_dist += dt
        if dt > max_dist:
            max_dist = dt
        rho_list[t] = dt / B_T[t]

        # G5: 경기일 사이 9개 구간(r = 1..9) 중 300km 이상 이동 횟수
        long_cnt = 0
        for r in range(1, N_DAYS):
            if steps[r] >= 300:
                long_cnt += 1
        if long_cnt > max_long_all:
            max_long_all = long_cnt

        # G4: 1회 원정 순회(연고지 출발 -> 연속 원정 -> 연고지 복귀) 최대 이동거리
        d = 0
        while d < N_DAYS:
            if ht[d] == 0:
                start = d
                while d < N_DAYS and ht[d] == 0:
                    d += 1
                trip = sum(steps[start:d + 1])
                if trip > max_trip_all:
                    max_trip_all = trip
            else:
                d += 1

        # G6: 3일 초과 연속 홈/원정 경기 수
        run = 1
        for d in range(1, N_DAYS):
            if ht[d] == ht[d - 1]:
                run += 1
            else:
                if run > 3:
                    streak_excess += run - 3
                run = 1
        if run > 3:
            streak_excess += run - 3

    # G7: 리피터(이틀 연속 동일 상대 대진) 수
    repeaters = 0
    for d in range(1, N_DAYS):
        d_prev = d - 1
        for t in range(N_TEAMS):
            if opp[t][d] == opp[t][d_prev]:
                repeaters += 1
    repeaters //= 2

    # G3: 지리 보정 이동 비율 rho_t 의 모표준편차
    rho_mean = sum(rho_list) / N_TEAMS
    g3 = math.sqrt(sum((r - rho_mean) ** 2 for r in rho_list) / N_TEAMS)

    return (
        float(total_dist),
        float(max_dist),
        g3,
        float(max_trip_all),
        float(max_long_all),
        float(streak_excess),
        float(repeaters),
    )


def detailed_team_stats(schedule: Schedule) -> Dict[str, object]:
    """보고서/리포트 출력용 구단별 상세 공정성 지표 계산"""
    loc = [[t] * (N_DAYS + 2) for t in range(N_TEAMS)]
    home_flag = [[0] * N_DAYS for _ in range(N_TEAMS)]

    for d in range(N_DAYS):
        for h, a in schedule[d]:
            loc[h][d + 1] = h
            loc[a][d + 1] = h
            home_flag[h][d] = 1

    dist_total = [0] * N_TEAMS
    max_trip = [0] * N_TEAMS
    long_moves = [0] * N_TEAMS
    breaks = [0] * N_TEAMS
    max_streak = [0] * N_TEAMS
    patterns: List[str] = []

    for t in range(N_TEAMS):
        steps = [DIST[loc[t][r]][loc[t][r + 1]] for r in range(N_DAYS + 1)]
        dist_total[t] = sum(steps)
        long_moves[t] = sum(1 for r in range(1, N_DAYS) if steps[r] >= 300)

        d = 0
        while d < N_DAYS:
            if home_flag[t][d] == 0:
                s = d
                while d < N_DAYS and home_flag[t][d] == 0:
                    d += 1
                trip = sum(steps[s:d + 1])
                if trip > max_trip[t]:
                    max_trip[t] = trip
            else:
                d += 1

        run = 1
        for d in range(1, N_DAYS + 1):
            if d < N_DAYS and home_flag[t][d] == home_flag[t][d - 1]:
                run += 1
                breaks[t] += 1
            else:
                if run > max_streak[t]:
                    max_streak[t] = run
                run = 1

        patterns.append("".join("H" if home_flag[t][d] == 1 else "A" for d in range(N_DAYS)))

    rho = [dist_total[t] / B_T[t] for t in range(N_TEAMS)]
    return {
        "D_t": dist_total,
        "rho_t": rho,
        "W_t": max_trip,
        "L_t": long_moves,
        "breaks": breaks,
        "max_streak": max_streak,
        "patterns": patterns,
    }


def evaluate_schedule(
    schedule: Schedule,
    weights: Sequence[float] = WEIGHT_PRESETS["base"],
    g0: Sequence[float] = G0_DEFAULT,
    g_star: Sequence[float] = G_STAR_DEFAULT,
) -> Tuple[float, float, Tuple[float, ...]]:
    """일정 x에 대해 (정규화 비용 C(x), 보조 적합도 f(x), 원시 지표 G1~G7) 반환"""
    g_vals = compute_g_values(schedule)
    cost = sum(
        weights[k] * (g_vals[k] - g_star[k]) / (g0[k] - g_star[k])
        for k in range(7)
    )
    fitness = 1.0 / (1.0 + cost) if cost > -1.0 else float("inf")
    return cost, fitness, g_vals


def evaluate_chrom(
    chrom: Chromosome,
    weights: Sequence[float] = WEIGHT_PRESETS["base"],
    g0: Sequence[float] = G0_DEFAULT,
    g_star: Sequence[float] = G_STAR_DEFAULT,
) -> float:
    """염색체 평가 후 cost 캐시 반환"""
    if chrom.cost is None:
        sched = decode(chrom)
        cost, fitness, g_vals = evaluate_schedule(sched, weights, g0, g_star)
        chrom.cost = cost
        chrom.fitness = fitness
        chrom.g_vals = g_vals
    return chrom.cost


# ---------------------------------------------------------------------------
# 4. GA 연산자 (초기화, 선택, 교차, 변이)
# ---------------------------------------------------------------------------
def random_chromosome(rng: random.Random) -> Chromosome:
    sigma = list(range(N_TEAMS))
    pi = list(range(N_DAYS))
    rng.shuffle(sigma)
    rng.shuffle(pi)
    h = [rng.randint(0, 1) for _ in range(15)]
    return Chromosome(sigma=sigma, pi=pi, h=h)


def init_population(
    pop_size: int,
    rng: random.Random,
    dedup: bool = True,
    max_attempts: int = 10000,
) -> List[Chromosome]:
    """초기 개체군 생성 (유효성 검증 + 디코딩 일정 기준 중복 제거)"""
    pop: List[Chromosome] = []
    seen = set()
    attempts = 0
    while len(pop) < pop_size:
        attempts += 1
        if attempts > max_attempts:
            raise RuntimeError("초기 개체군 중복 회피 한도 초과")
        ind = random_chromosome(rng)
        sched = decode(ind)
        assert is_feasible(sched), "특수 인코딩 디코딩 결과가 실행 불가능합니다."
        key = schedule_key(ind)
        if dedup and key in seen:
            continue
        seen.add(key)
        pop.append(ind)
    return pop


def tournament_select(pop: Sequence[Chromosome], k: int, rng: random.Random) -> Chromosome:
    """토너먼트 선택 (k개 비복원 추출, 정규화 비용 C(x) 직접 비교)"""
    contestants = rng.sample(pop, k)
    return min(contestants, key=lambda c: c.cost if c.cost is not None else float("inf"))


def order_crossover(a: Sequence[int], b: Sequence[int], rng: random.Random) -> List[int]:
    """순열 순서 교차 (OX, 교안 50쪽)"""
    n = len(a)
    i, j = sorted(rng.sample(range(n), 2))
    child: List[Optional[int]] = [None] * n
    child[i:j + 1] = a[i:j + 1]
    placed = set(a[i:j + 1])

    fill_positions = [(j + 1 + t) % n for t in range(n - (j - i + 1))]
    b_seq = [b[(j + 1 + t) % n] for t in range(n) if b[(j + 1 + t) % n] not in placed]
    for pos, val in zip(fill_positions, b_seq):
        child[pos] = val
    return [v for v in child if v is not None]


def one_point_crossover(a: Sequence[int], b: Sequence[int], rng: random.Random) -> List[int]:
    """이진 벡터 1점 교차 (교안 44쪽)"""
    cut = rng.randint(1, len(a) - 1)
    return list(a[:cut]) + list(b[cut:])


def crossover(p1: Chromosome, p2: Chromosome, pc: float, rng: random.Random) -> Chromosome:
    """부분별 교차: sigma 상속(A), pi OX, h 1점 교차 (자식 1개 생성)"""
    if rng.random() >= pc:
        return p1.clone()
    return Chromosome(
        sigma=list(p1.sigma),
        pi=order_crossover(p1.pi, p2.pi, rng),
        h=one_point_crossover(p1.h, p2.h, rng),
    )


def mutate_once(chrom: Chromosome, rng: random.Random) -> None:
    """실행 가능성 보존 4종 변이 중 하나를 균등 확률로 적용"""
    op = rng.randrange(4)
    if op == 0:
        # (a) 일자 교환 (Swap days in pi)
        i, j = rng.sample(range(N_DAYS), 2)
        chrom.pi[i], chrom.pi[j] = chrom.pi[j], chrom.pi[i]
    elif op == 1:
        # (b) 구간 역전 (Inversion in pi)
        i, j = sorted(rng.sample(range(N_DAYS), 2))
        chrom.pi[i:j + 1] = chrom.pi[i:j + 1][::-1]
    elif op == 2:
        # (c) 홈/원정 비트 뒤집기 (Flip 1 bit in h -> 사본 A, B 동시 반전)
        idx = rng.randrange(15)
        chrom.h[idx] ^= 1
    else:
        # (d) 구단 자리 교환 (Swap 2 teams in sigma)
        i, j = rng.sample(range(N_TEAMS), 2)
        chrom.sigma[i], chrom.sigma[j] = chrom.sigma[j], chrom.sigma[i]
    chrom.invalidate()


def mutate(chrom: Chromosome, pm: float, rng: random.Random) -> None:
    """염색체당 확률 pm으로 변이 적용"""
    if rng.random() < pm:
        mutate_once(chrom, rng)


# ---------------------------------------------------------------------------
# 5. 메인 GA 루프 (엘리트 보존 + 중복 제거 + 정체 종료 + 다양성 추적)
# ---------------------------------------------------------------------------
@dataclass
class GAConfig:
    pop_size: int = 60          # 개체군 크기 N
    max_gens: int = 500         # 최대 세대 (60 + 500*58 = 29,060회 ≈ 30,000회)
    stall_gens: int = 150       # 정체 종료 기준 세대 (0이면 최대 세대까지 고정 실행)
    pc: float = 0.9             # 교차 확률 (4장 실험: 0.0, 0.5, 0.9 비교)
    pm: float = 0.3             # 변이 확률 (염색체당)
    tournament_k: int = 3       # 토너먼트 크기
    elite_size: int = 2         # 엘리트 보존 수
    dedup: bool = True          # 디코딩 일정 기준 중복 제거
    max_dedup_muts: int = 50    # 중복 해소 최대 추가 변이 횟수
    seed: int = 42
    weights: Tuple[float, ...] = WEIGHT_PRESETS["base"]
    g0: Tuple[float, ...] = G0_DEFAULT
    g_star: Tuple[float, ...] = G_STAR_DEFAULT


@dataclass
class GAResult:
    best: Chromosome
    history: List[Tuple[int, float, float, int]] = field(default_factory=list)
    # history 원소: (generation, best_cost, avg_cost, distinct_schedules)
    evaluations: int = 0
    elapsed_sec: float = 0.0
    stopped_gen: int = 0


def run_ga(cfg: GAConfig) -> GAResult:
    """유전 알고리즘 실행"""
    t0 = time.perf_counter()
    rng = random.Random(cfg.seed)
    evals = 0

    pop = init_population(cfg.pop_size, rng, dedup=cfg.dedup)
    for ind in pop:
        evaluate_chrom(ind, cfg.weights, cfg.g0, cfg.g_star)
        evals += 1

    pop.sort(key=lambda c: c.cost if c.cost is not None else float("inf"))
    best = pop[0].clone()
    last_improve_gen = 0

    distinct_0 = len({schedule_key(ind) for ind in pop})
    avg_0 = sum(c.cost for c in pop if c.cost is not None) / len(pop)
    history: List[Tuple[int, float, float, int]] = [
        (0, float(best.cost), avg_0, distinct_0)
    ]

    stopped_gen = 0
    for gen in range(1, cfg.max_gens + 1):
        pop.sort(key=lambda c: c.cost if c.cost is not None else float("inf"))

        next_pop: List[Chromosome] = []
        seen_keys = set()

        # 엘리트 보존 (상위 e개)
        for i in range(cfg.elite_size):
            elite_copy = pop[i].clone()
            next_pop.append(elite_copy)
            seen_keys.add(schedule_key(elite_copy))

        # 나머지 N - e개 자식 생성
        while len(next_pop) < cfg.pop_size:
            p1 = tournament_select(pop, cfg.tournament_k, rng)
            p2 = tournament_select(pop, cfg.tournament_k, rng)
            child = crossover(p1, p2, cfg.pc, rng)
            mutate(child, cfg.pm, rng)

            if cfg.dedup:
                attempts = 0
                while schedule_key(child) in seen_keys and attempts < cfg.max_dedup_muts:
                    mutate_once(child, rng)
                    attempts += 1

            seen_keys.add(schedule_key(child))
            evaluate_chrom(child, cfg.weights, cfg.g0, cfg.g_star)
            evals += 1
            next_pop.append(child)

        pop = next_pop
        cur_best = min(pop, key=lambda c: c.cost if c.cost is not None else float("inf"))
        assert cur_best.cost is not None and best.cost is not None
        if cur_best.cost < best.cost - 1e-12:
            best = cur_best.clone()
            last_improve_gen = gen

        distinct_cnt = len({schedule_key(ind) for ind in pop})
        avg_cost = sum(c.cost for c in pop if c.cost is not None) / len(pop)
        history.append((gen, float(best.cost), avg_cost, distinct_cnt))
        stopped_gen = gen

        if cfg.stall_gens > 0 and (gen - last_improve_gen) >= cfg.stall_gens:
            break

    assert is_feasible(decode(best))
    elapsed = time.perf_counter() - t0
    return GAResult(
        best=best,
        history=history,
        evaluations=evals,
        elapsed_sec=elapsed,
        stopped_gen=stopped_gen,
    )


# ---------------------------------------------------------------------------
# 6. 기준값 측정, 교수님 예시 대조, 리포트 포맷팅
# ---------------------------------------------------------------------------
def measure_random_baseline(n_samples: int = 1000, seed: int = 0) -> Tuple[float, ...]:
    """무작위 (sigma, pi, h) 일정 n_samples개의 G1~G7 평균 측정"""
    rng = random.Random(seed)
    sums = [0.0] * 7
    for _ in range(n_samples):
        g_vals = compute_g_values(decode(random_chromosome(rng)))
        for k in range(7):
            sums[k] += g_vals[k]
    return tuple(s / n_samples for s in sums)


def professor_example_schedule() -> Schedule:
    """예시 보고서 Table 4의 10일 경기 일정 (원정 @ 홈 -> (홈, 원정))"""
    idx = {name: i for i, name in enumerate(TEAMS)}
    raw = [
        [("삼미", "MBC"), ("해태", "OB"), ("롯데", "삼성")],  # 1일차
        [("OB", "삼성"), ("해태", "삼미"), ("롯데", "MBC")],  # 2일차
        [("OB", "삼미"), ("삼성", "MBC"), ("롯데", "해태")],  # 3일차
        [("MBC", "삼미"), ("OB", "해태"), ("삼성", "롯데")],  # 4일차
        [("MBC", "삼성"), ("삼미", "OB"), ("해태", "롯데")],  # 5일차
        [("삼미", "삼성"), ("OB", "롯데"), ("해태", "MBC")],  # 6일차
        [("OB", "MBC"), ("삼성", "해태"), ("롯데", "삼미")],  # 7일차
        [("MBC", "해태"), ("삼성", "삼미"), ("롯데", "OB")],  # 8일차
        [("MBC", "롯데"), ("삼미", "해태"), ("삼성", "OB")],  # 9일차
        [("MBC", "OB"), ("삼미", "롯데"), ("해태", "삼성")],  # 10일차
    ]
    return tuple(tuple((idx[h], idx[a]) for h, a in day) for day in raw)


def _disp_width(text: str) -> int:
    """한글(전각) 2칸, 영문/숫자(반각) 1칸 기준 출력 폭 계산"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad_left(text: str, width: int) -> str:
    return text + " " * max(0, width - _disp_width(text))


def _pad_right(text: str, width: int) -> str:
    return " " * max(0, width - _disp_width(text)) + text


def _pad_center(text: str, width: int) -> str:
    gap = max(0, width - _disp_width(text))
    left = gap // 2
    return " " * left + text + " " * (gap - left)


def format_report(res: GAResult) -> str:
    """최종 10일 일정, 구단별 공정성 지표, G1~G7, 제약 검증 요약 포맷팅"""
    best = res.best
    sched = decode(best)
    assert best.g_vals is not None and best.cost is not None and best.fitness is not None
    g_vals = best.g_vals
    stats = detailed_team_stats(sched)
    d_t = stats["D_t"]
    rho_t = stats["rho_t"]
    w_t = stats["W_t"]
    l_t = stats["L_t"]
    breaks = stats["breaks"]
    max_streak = stats["max_streak"]
    patterns = stats["patterns"]

    prof_cost, _, _ = evaluate_schedule(professor_example_schedule())

    lines: List[str] = []
    lines.append("=" * 82)
    lines.append(
        f"최적 일정 탐색 결과 (종료 세대: {res.stopped_gen}, 총 평가: {res.evaluations:,}회, {res.elapsed_sec:.2f}s)"
    )
    lines.append(
        f"정규화 비용 C(x) = {best.cost:.4f} (교수님 예시 {prof_cost:.4f} 대비 {best.cost - prof_cost:+.4f}) "
        f"| 보조 적합도 f(x) = {best.fitness:.4f}"
    )
    lines.append(f"독립 제약 검증 is_feasible(): {is_feasible(sched)}")
    lines.append("-" * 82)
    lines.append(
        f"G1(총이동)={g_vals[0]:.0f}km | G2(최대)={g_vals[1]:.0f}km | "
        f"G3(비율std)={g_vals[2]:.4f} | G4(최장원정)={g_vals[3]:.0f}km | "
        f"G5(>=300km)={g_vals[4]:.0f}회 | G6(3연속초과)={g_vals[5]:.0f} | G7(리피터)={g_vals[6]:.0f}"
    )
    lines.append("-" * 82)
    lines.append("[10일 경기 스케줄] (표기: 원정 @ 홈)")
    for d, day in enumerate(sched, 1):
        day_str = "   ".join(_pad_left(f"{TEAMS[a]} @ {TEAMS[h]}", 12) for h, a in day)
        lines.append(f"  {d:2d}일차: {day_str.rstrip()}")
    lines.append("-" * 82)
    lines.append("[구단별 공정성 지표]")

    headers = ["구단", "홈/원정 패턴", "총이동(km)", "D/B비율", "최장원정", ">=300km", "브레이크", "최장연속"]
    col_widths = [4, 12, 10, 7, 8, 7, 8, 8]
    header_line = "  " + " | ".join(_pad_center(h, w) for h, w in zip(headers, col_widths))
    lines.append(header_line)
    lines.append("  " + "-+-".join("-" * w for w in col_widths))

    for t in range(N_TEAMS):
        cells = [
            _pad_left(TEAMS[t], col_widths[0]),
            _pad_center(patterns[t], col_widths[1]),
            _pad_right(f"{d_t[t]:,d}", col_widths[2]),
            _pad_right(f"{rho_t[t]:.3f}", col_widths[3]),
            _pad_right(f"{w_t[t]:,d}", col_widths[4]),
            _pad_right(f"{l_t[t]}", col_widths[5]),
            _pad_right(f"{breaks[t]}", col_widths[6]),
            _pad_right(f"{max_streak[t]}", col_widths[7]),
        ]
        lines.append("  " + " | ".join(cells))

    lines.append("=" * 82)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7. 구현 완료 판정 테스트 8종 (OR2_GA_설계.md 기준)
# ---------------------------------------------------------------------------
def run_completion_tests() -> None:
    """설계 문서의 8가지 완료 판정 테스트 실행"""
    rng = random.Random(12345)

    # Test 1: 염색체 및 카드 무결성 (초기화, OX/1점 교차, 4종 변이)
    for _ in range(100):
        p1 = random_chromosome(rng)
        p2 = random_chromosome(rng)
        c = crossover(p1, p2, 1.0, rng)
        mutate(c, 1.0, rng)
        assert sorted(c.sigma) == [0, 1, 2, 3, 4, 5]
        assert sorted(c.pi) == list(range(10))
        assert len(c.h) == 15 and all(b in (0, 1) for b in c.h)
        assert is_feasible(decode(c))

    # Test 2 & 3: 무작위 염색체 1,000개 실행 가능성 및 표현형 다양성 비율
    decoded_keys = set()
    for _ in range(1000):
        ind = random_chromosome(rng)
        sched = decode(ind)
        assert is_feasible(sched)
        decoded_keys.add(schedule_key(ind))
    unique_ratio = len(decoded_keys) / 1000.0
    assert unique_ratio > 0.99, f"다양성 비율이 지나치게 낮음: {unique_ratio}"

    # Test 4: 비용 계산 재현성 및 교수님 예시 일정 대조
    prof_sched = professor_example_schedule()
    assert is_feasible(prof_sched)
    c1, f1, g1 = evaluate_schedule(prof_sched)
    c2, f2, _ = evaluate_schedule(prof_sched)
    assert math.isclose(c1, c2, rel_tol=0.0, abs_tol=1e-12)
    assert math.isclose(f1, f2, rel_tol=0.0, abs_tol=1e-12)
    assert g1[0] == 9280.0 and g1[1] == 1585.0
    assert abs(c1 - 2.013) < 0.01, f"교수님 예시 v2 비용 불일치: {c1}"

    # Test 5 & 6 & 7: 세대 크기(60), 엘리트 단조성, 동일 시드 재현성
    res1 = run_ga(GAConfig(pop_size=60, max_gens=50, stall_gens=0, seed=42))
    res2 = run_ga(GAConfig(pop_size=60, max_gens=50, stall_gens=0, seed=42))
    assert len(res1.history) == 51
    for gen in range(1, len(res1.history)):
        assert res1.history[gen][1] <= res1.history[gen - 1][1] + 1e-12
    assert res1.best.cost == res2.best.cost
    assert decode(res1.best) == decode(res2.best)

    # Test 8: 최종 출력 생성 검증
    rep = format_report(res1)
    assert "10일 경기 스케줄" in rep and "True" in rep

    print(
        f"[완료 판정 테스트 8/8 통과] "
        f"무작위 1,000개 실행가능 100% (고유 일정 {len(decoded_keys)}/1000={unique_ratio:.3f}), "
        f"교수님 예시 C(x)={c1:.4f}"
    )


# ---------------------------------------------------------------------------
# 8. 실험 실행기 (다중 시드 / 교차율 비교 / 가중치 민감도)
# ---------------------------------------------------------------------------
def run_multi_seed(
    seeds: int = 8,
    pc: float = 0.9,
    pm: float = 0.3,
    pop_size: int = 60,
    max_gens: int = 500,
    stall_gens: int = 150,
    dedup: bool = True,
    weights: Tuple[float, ...] = WEIGHT_PRESETS["base"],
    label: str = "기본 설정",
) -> GAResult:
    """다중 시드 실행 후 통계 및 최선 해 반환"""
    costs: List[float] = []
    distincts: List[int] = []
    best_res: Optional[GAResult] = None
    t0 = time.perf_counter()

    for s in range(seeds):
        cfg = GAConfig(
            pop_size=pop_size,
            max_gens=max_gens,
            stall_gens=stall_gens,
            pc=pc,
            pm=pm,
            tournament_k=3,
            elite_size=2,
            dedup=dedup,
            seed=s,
            weights=weights,
        )
        res = run_ga(cfg)
        assert res.best.cost is not None
        costs.append(res.best.cost)
        distincts.append(res.history[-1][3])
        if best_res is None or res.best.cost < best_res.best.cost:  # type: ignore[operator]
            best_res = res

    assert best_res is not None
    mean_c = statistics.mean(costs)
    std_c = statistics.stdev(costs) if len(costs) > 1 else 0.0
    print(
        f"[{label} | seeds={seeds}, pc={pc}, pm={pm}, N={pop_size}, G={max_gens}, stall={stall_gens}] "
        f"평균={mean_c:.3f} ± {std_c:.3f} | 최선={min(costs):.3f} | 최악={max(costs):.3f} | "
        f"고유일정={statistics.mean(distincts):.1f}/{pop_size} | 시간={time.perf_counter()-t0:.1f}s"
    )
    return best_res


def main() -> None:
    parser = argparse.ArgumentParser(description="O.R.2 프로야구 10일 일정 GA (통합 최적안)")
    parser.add_argument("--mode", choices=["demo", "single", "ablation"], default="demo")
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pc", type=float, default=0.9)
    parser.add_argument("--pm", type=float, default=0.3)
    parser.add_argument("--pop-size", type=int, default=60)
    parser.add_argument("--max-gens", type=int, default=500)
    parser.add_argument("--stall", type=int, default=150)
    parser.add_argument("--weight", choices=list(WEIGHT_PRESETS.keys()), default="base")
    args, _ = parser.parse_known_args()

    run_completion_tests()

    if args.mode == "single":
        res = run_ga(
            GAConfig(
                pop_size=args.pop_size,
                max_gens=args.max_gens,
                stall_gens=args.stall,
                pc=args.pc,
                pm=args.pm,
                seed=args.seed,
                weights=WEIGHT_PRESETS[args.weight],
            )
        )
        print(format_report(res))
    elif args.mode == "ablation":
        print("\n--- 교차 확률 비교 (4장 보고용: pc = 0.0, 0.5, 0.9) ---")
        for pc in (0.0, 0.5, 0.9):
            run_multi_seed(
                seeds=args.seeds,
                pc=pc,
                pm=args.pm,
                pop_size=args.pop_size,
                max_gens=args.max_gens,
                stall_gens=0,
                label=f"pc={pc}",
            )
        print("\n--- 가중치 민감도 비교 (base / fairness / efficiency) ---")
        for name, w in WEIGHT_PRESETS.items():
            best_w = run_multi_seed(
                seeds=args.seeds,
                pc=args.pc,
                pm=args.pm,
                pop_size=args.pop_size,
                max_gens=args.max_gens,
                stall_gens=args.stall,
                weights=w,
                label=f"weight={name}",
            )
            assert best_w.best.g_vals is not None
            print(f"  -> {name} 최선 G1~G7: {[round(x, 4) for x in best_w.best.g_vals]}")
    else:
        print("\n--- 통합 최적안 다중 시드 탐색 ---")
        best_res = run_multi_seed(
            seeds=args.seeds,
            pc=args.pc,
            pm=args.pm,
            pop_size=args.pop_size,
            max_gens=args.max_gens,
            stall_gens=args.stall,
            weights=WEIGHT_PRESETS[args.weight],
            label="채택안(유진+규민+진우 통합)",
        )
        print(format_report(best_res))


if __name__ == "__main__":
    main()
