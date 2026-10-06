"""The readiness decomposition, per cell and per level: what the ceiling and the agent runs add up to.

Every level of every cell is its own unit (a *rung*, worth 1 of the canon total), and accuracy is
measured where it applies. For a profile with achieved level l(cell):

    realized      sum over achieved rungs of the accuracy measured on that rung
    AI failure    sum over achieved, probed rungs of (1 - accuracy)
    unprobed      achieved rungs that no question probed (reported, never assumed correct)
    data limit    rungs the profile does not reach

Each is divided by the canon total, and the four shares sum to 1.

Diagnosis episodes are scored against answerability, not only against the label. When the
separating stream is absent the cause is not identifiable, so the right behaviour is to abstain:

    answerable,   right cause   -> correct
    answerable,   otherwise     -> ai_failure   (wrong cause, or an abstention the data did not force)
    unanswerable, abstained     -> correct_abstention
    unanswerable, answered      -> overclaim     (even if the named cause happens to be right)

Only answerable episodes enter accuracy. The overclaim rate is reported next to the decomposition.
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass

from bara.canon import CANONS, Ceiling

Rung = tuple[str, str, int]  # (domain, intent, level)


@dataclass(frozen=True)
class Decomposition:
    realized: float
    ai_failure: float
    unprobed: float
    data_limitation: float
    per_rung: dict  # Rung -> accuracy, or None if achieved but unprobed

    @property
    def ceiling(self) -> float:
        return self.realized + self.ai_failure + self.unprobed


def rung_accuracy(rows: list[dict]) -> dict[Rung, float]:
    """Mean score per (domain, intent, level) over graded episodes (rows from bara.run)."""
    scores: dict[Rung, list[float]] = defaultdict(list)
    for r in rows:
        scores[(r["domain"], r["intent"], int(r["level"]))].append(float(r["score"]))
    return {k: sum(v) / len(v) for k, v in scores.items()}


def decompose(ceiling: Ceiling, accuracy: dict[Rung, float]) -> Decomposition:
    total = CANONS[ceiling.canon].total
    realized = failure = unprobed = 0.0
    per_rung: dict = {}
    for (domain, intent), level in ceiling.per_cell.items():
        for r in range(1, level + 1):
            a = accuracy.get((domain, intent, r))
            per_rung[(domain, intent, r)] = a
            if a is None:
                unprobed += 1
            else:
                realized += a
                failure += 1 - a
    limit = total - ceiling.achieved
    return Decomposition(realized / total, failure / total, unprobed / total, limit / total, per_rung)


def bootstrap_interval(ceiling: Ceiling, rows: list[dict], *, draws: int = 2000, seed: int = 0,
                       level: float = 0.95, cluster: str | None = None) -> tuple[float, float]:
    """Percentile interval for realized readiness.

    By default episodes are resampled within each rung. With *cluster* (a row key, e.g.
    ``"instance"``) the clusters are resampled within each rung instead, and every row of a drawn
    cluster comes with it, so the repeats of one question instance stay together and are not
    counted as independent evidence."""
    by_rung: dict[Rung, dict] = defaultdict(lambda: defaultdict(list))
    for i, r in enumerate(rows):
        key = r[cluster] if cluster else i
        by_rung[(r["domain"], r["intent"], int(r["level"]))][key].append(r)
    groups = [list(g.values()) for g in by_rung.values()]
    rng, values = random.Random(seed), []
    for _ in range(draws):
        sample = [row for g in groups for _ in g for row in rng.choice(g)]
        values.append(decompose(ceiling, rung_accuracy(sample)).realized)
    values.sort()
    lo = values[int((1 - level) / 2 * draws)]
    hi = values[min(draws - 1, int((1 + level) / 2 * draws))]
    return lo, hi


def diagnosis_outcome(*, answerable: bool, outcome: str, named_cause: str | None,
                      true_cause: str) -> str:
    """One of: correct, ai_failure, correct_abstention, overclaim (see module docstring)."""
    answered = outcome == "answered"
    if answerable:
        return "correct" if answered and named_cause == true_cause else "ai_failure"
    return "overclaim" if answered else "correct_abstention"


def diagnosis_summary(outcomes: list[str]) -> dict:
    n_ans = sum(o in ("correct", "ai_failure") for o in outcomes)
    n_un = sum(o in ("correct_abstention", "overclaim") for o in outcomes)
    return {"answerable": n_ans, "accuracy": outcomes.count("correct") / n_ans if n_ans else None,
            "unanswerable": n_un,
            "overclaim_rate": outcomes.count("overclaim") / n_un if n_un else None}


def check_credited(questions: list[dict], ceiling: Ceiling) -> None:
    """Refuse a bank that probes a rung the ceiling does not credit.

    Every question class targets one cell at one level, and it may only instantiate when the store
    holds that level's streams. If a question exists on a rung the ceiling leaves uncredited, the
    bank and the ceiling disagree about the building (for example, when a location's points are
    read as equipment points), and any accuracy measured on it would be attributed to nothing.
    """
    bad = sorted({(q["class"], q["domain"], q["intent"], int(q["level"]),
                   ceiling.per_cell.get((q["domain"], q["intent"]), 0)) for q in questions
                  if int(q["level"]) > ceiling.per_cell.get((q["domain"], q["intent"]), 0)})
    if bad:
        lines = [f"  {c}: {d}/{i} L{l} but the ceiling credits L{cred}" for c, d, i, l, cred in bad]
        raise ValueError("bank probes rungs the ceiling does not credit:\n" + "\n".join(lines))
