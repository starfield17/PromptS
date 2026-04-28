from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "run_research.py"


def test_cli_offline_pipeline_steps(tmp_path: Path) -> None:
    fixture = ROOT / "tests" / "fixtures" / "news_pack.json"
    entities = tmp_path / "entities.json"
    value_chain = tmp_path / "value_chain.json"
    scores = tmp_path / "scores.json"
    watchlist = tmp_path / "watchlist.json"

    subprocess.run([sys.executable, str(CLI), "extract-entities", "--input", str(fixture), "--out", str(entities)], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(CLI), "build-value-chain", "--direction", "AI inference chips", "--entities", str(entities), "--out", str(value_chain)], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(CLI), "score-profit-pool", "--value-chain", str(value_chain), "--out", str(scores)], check=True, cwd=ROOT)
    subprocess.run([sys.executable, str(CLI), "generate-watchlist", "--value-chain", str(value_chain), "--out", str(watchlist)], check=True, cwd=ROOT)

    assert entities.exists()
    assert value_chain.exists()
    assert scores.exists()
    assert watchlist.exists()
