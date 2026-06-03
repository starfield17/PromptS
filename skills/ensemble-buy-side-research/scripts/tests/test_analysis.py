from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ensemble_research.analysis.consensus import detect_consensus
from ensemble_research.analysis.entities import extract_entities_from_records, extract_entities_from_text
from ensemble_research.analysis.scoring import score_value_chain
from ensemble_research.analysis.trigger import classify_trigger
from ensemble_research.analysis.value_chain import build_value_chain
from ensemble_research.analysis.watchlist import generate_watchlist
from ensemble_research.rendering.markdown import build_memo, render_memo


def test_trigger_and_entity_extraction_handles_english_and_chinese() -> None:
    text = "Nvidia and Broadcom orders rise as AI inference chip capacity expands. 毛利率 and 产能 are key metrics."
    assert classify_trigger(text) in {"Demand", "Supply"}
    pack = extract_entities_from_text(text, ["source_1"])
    assert "Nvidia" in pack.companies
    assert "chip" in pack.products
    assert "毛利率" in pack.metrics
    assert pack.source_ids == ["source_1"]


def test_value_chain_scoring_watchlist_and_memo() -> None:
    fixture = json.loads((ROOT / "tests" / "fixtures" / "news_pack.json").read_text(encoding="utf-8"))
    entities = extract_entities_from_records(fixture["items"])
    chain = build_value_chain("AI inference chips", entities)
    assert any(layer.name == "advanced packaging" for layer in chain.layers)

    financials = pd.DataFrame(
        [
            {"ticker": "NVDA", "gross_margin": 0.72, "operating_margin": 0.55},
            {"ticker": "AVGO", "gross_margin": 0.68, "operating_margin": 0.45},
        ]
    )
    scorecard = score_value_chain(chain, financials)
    assert scorecard.layer_scores
    assert scorecard.initial_judgment in {"B. Watch", "C. Deep Dive", "D. Potential Investment Thesis"}

    consensus = detect_consensus(fixture)
    watchlist = generate_watchlist(value_chain=chain)
    assert watchlist.items
    memo = build_memo("AI inference chips", chain, consensus, watchlist, scorecard)
    rendered = render_memo(memo)
    assert "## Value Chain Map" in rendered
    assert "## Buffett Quality Lens" in rendered
    assert "## Falsification Conditions" in rendered
