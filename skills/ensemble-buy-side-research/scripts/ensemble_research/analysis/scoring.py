from __future__ import annotations

import pandas as pd

from ..models import LayerScore, ScoreCard, ValueChain


QUALITY_SCORE = {"low": 1, "medium": 3, "high": 5, "unknown": 2}
RISK_SCORE = {"low": 1, "medium": 3, "high": 5, "unknown": 3}


def _problem_quality(layer_name: str, problem_solved: str) -> int:
    text = f"{layer_name} {problem_solved}".lower()
    score = 10
    if any(term in text for term in ["cost", "scarce", "latency", "bottleneck", "risk", "power", "utilization"]):
        score += 6
    if any(term in text for term in ["recurring", "service", "software", "cloud", "maintenance"]):
        score += 3
    if "source needed" not in text:
        score += 2
    return min(score, 25)


def _financial_bonus(financials: pd.DataFrame | None) -> tuple[int, list[str]]:
    if financials is None or financials.empty:
        return 0, []
    notes: list[str] = []
    bonus = 0
    for column in ("gross_margin", "operating_margin"):
        if column in financials:
            series = pd.to_numeric(financials[column], errors="coerce").dropna()
            if not series.empty:
                avg = float(series.mean())
                notes.append(f"Average {column}: {avg:.1%}")
                if avg > 0.5:
                    bonus += 3
                elif avg > 0.25:
                    bonus += 1
    return min(bonus, 5), notes


def score_value_chain(value_chain: ValueChain, financials: pd.DataFrame | None = None) -> ScoreCard:
    bonus, financial_notes = _financial_bonus(financials)
    layer_scores: list[LayerScore] = []
    best_score = 0.0
    for layer in value_chain.layers:
        quality = QUALITY_SCORE[layer.profit_pool_quality]
        bottleneck = QUALITY_SCORE[layer.bottleneck_level]
        competition = RISK_SCORE[layer.competition_intensity]
        commod = RISK_SCORE[layer.commoditization_risk]
        problem = _problem_quality(layer.name, layer.problem_solved)
        profit = min(50, 10 + quality * 5 + bottleneck * 3 + bonus + (6 - competition))
        commod_score = min(40, 8 + commod * 4 + competition * 2)
        consensus_gap = 10 + (3 if layer.profit_pool_quality == "high" else 0) + (3 if layer.bottleneck_level == "high" else 0)

        # Buffett-style quality is a forcing function, not a substitute for evidence.
        # It rewards durable economics and penalizes layers likely to be competed away.
        buffett_quality = min(
            35,
            7
            + quality * 4
            + bottleneck * 2
            + (6 - competition)
            + (6 - commod)
            + bonus,
        )
        downside_penalty = min(20, competition * 2 + commod * 2 + (3 if layer.bottleneck_level == "low" else 0))

        investability = (
            (problem / 25) * 20
            + (profit / 50) * 25
            + (consensus_gap / 25) * 20
            + 10
            + (6 if layer.bottleneck_level == "high" else 4)
            + 5
            + (buffett_quality / 35) * 8
            - downside_penalty * 0.35
        )
        investability = max(0.0, min(100.0, investability))
        best_score = max(best_score, investability)
        layer_scores.append(
            LayerScore(
                layer=layer.name,
                problem_quality_score=problem,
                profit_pool_score=profit,
                commoditization_risk_score=commod_score,
                consensus_gap_score=consensus_gap,
                buffett_quality_score=buffett_quality,
                downside_risk_penalty=downside_penalty,
                investability_score=round(investability, 1),
                evidence=layer.evidence_needed + financial_notes,
                notes=layer.judgment,
            )
        )
    if best_score >= 80:
        judgment = "D. Potential Investment Thesis"
    elif best_score >= 66:
        judgment = "C. Deep Dive"
    elif best_score >= 50:
        judgment = "B. Watch"
    else:
        judgment = "A. Discard"
    rationale = f"Best layer investability score is {best_score:.1f}. Scores are forcing functions, not conclusions; Buffett quality and downside-risk fields are owner-oriented gates."
    return ScoreCard(direction=value_chain.direction, layer_scores=layer_scores, initial_judgment=judgment, rationale=rationale)
