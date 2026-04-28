from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..config import confidence_from_count
from ..io import normalize_records
from ..models import Consensus


STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "are",
    "will",
    "says",
    "after",
    "over",
    "into",
    "about",
}


def _phrases(text: str) -> list[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9+.-]{2,}", text) if w.lower() not in STOP]
    phrases: list[str] = []
    for size in (2, 3):
        for idx in range(0, max(0, len(words) - size + 1)):
            phrases.append(" ".join(words[idx : idx + size]))
    return phrases


def detect_consensus(news_payload: Any) -> Consensus:
    records = normalize_records(news_payload)
    titles = [str(row.get("title") or row.get("summary") or "") for row in records]
    text = "\n".join(titles)
    counts = Counter(_phrases(text))
    repeated = [phrase for phrase, count in counts.most_common(12) if count >= 2]
    company_counts = Counter()
    for row in records:
        for entity in row.get("entities") or []:
            company_counts[str(entity)] += 1
    beneficiaries = [name for name, _ in company_counts.most_common(8)]
    if repeated:
        consensus = "The market narrative appears to repeat: " + "; ".join(repeated[:5]) + "."
    elif titles:
        consensus = "Assumed consensus from available headlines: " + titles[0][:240]
    else:
        consensus = "Assumed consensus, pending source validation"
    return Consensus(
        consensus=consensus,
        crowded_layers=[],
        obvious_beneficiaries=beneficiaries,
        possible_blind_spots=["Layer-level margin capture", "Capacity normalization", "Customer bargaining power"],
        repeated_narratives=repeated,
        evidence=[row.get("id") or row.get("source_id") for row in records if row.get("id") or row.get("source_id")],
        confidence=confidence_from_count(len(repeated) or len(titles)),
    )
