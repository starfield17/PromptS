from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .config import SCHEMA_VERSION, now_utc


Confidence = Literal["high", "medium", "low", "unknown"]
Judgment = Literal[
    "A. Discard",
    "B. Watch",
    "C. Deep Dive",
    "D. Potential Investment Thesis",
]


class Artifact(BaseModel):
    schema_version: str = SCHEMA_VERSION
    generated_at: str = Field(default_factory=now_utc)


class StructuredError(BaseModel):
    status: Literal["error"] = "error"
    module: str
    message: str
    recoverable: bool = True
    missing_inputs: list[str] = Field(default_factory=list)


class Source(BaseModel):
    id: str
    title: str
    url: str | None = None
    type: Literal["filing", "transcript", "news", "policy", "database", "presentation", "social", "other"] = "other"
    publisher: str | None = None
    date: str | None = None
    reliability: int = Field(default=0, ge=0, le=5)
    relevant_claims: list[str] = Field(default_factory=list)
    linked_variables: list[str] = Field(default_factory=list)
    notes: str | None = None


class NewsItem(BaseModel):
    id: str
    title: str
    url: str | None = None
    publisher: str | None = None
    date: str | None = None
    summary: str | None = None
    text: str | None = None
    entities: list[str] = Field(default_factory=list)
    trigger_type: str = "Unknown"
    confidence: Confidence = "unknown"
    source_id: str | None = None


class SourcePack(Artifact):
    sources: list[Source] = Field(default_factory=list)
    errors: list[StructuredError] = Field(default_factory=list)


class NewsPack(Artifact):
    query: str
    items: list[NewsItem] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    errors: list[StructuredError] = Field(default_factory=list)


class EntityPack(Artifact):
    companies: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    possible_layers: list[str] = Field(default_factory=list)
    uncertain_terms: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = "unknown"


class Players(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    global_: list[str] = Field(default_factory=list, alias="global")
    regional: list[str] = Field(default_factory=list)


class ValueChainLayer(BaseModel):
    name: str
    problem_solved: str
    players: Players = Field(default_factory=Players)
    bottleneck_level: Literal["low", "medium", "high", "unknown"] = "unknown"
    profit_pool_quality: Literal["low", "medium", "high", "unknown"] = "unknown"
    competition_intensity: Literal["low", "medium", "high", "unknown"] = "unknown"
    commoditization_risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    judgment: str = "Source needed"
    evidence_needed: list[str] = Field(default_factory=list)


class ValueChain(Artifact):
    direction: str
    layers: list[ValueChainLayer]
    source_ids: list[str] = Field(default_factory=list)


class LayerScore(BaseModel):
    layer: str
    problem_quality_score: int = Field(default=0, ge=0, le=25)
    profit_pool_score: int = Field(default=0, ge=0, le=50)
    commoditization_risk_score: int = Field(default=0, ge=0, le=40)
    consensus_gap_score: int = Field(default=0, ge=0, le=25)
    buffett_quality_score: int = Field(default=0, ge=0, le=35)
    downside_risk_penalty: int = Field(default=0, ge=0, le=20)
    investability_score: float = Field(default=0, ge=0, le=100)
    evidence: list[str] = Field(default_factory=list)
    notes: str = ""


class ScoreCard(Artifact):
    direction: str | None = None
    layer_scores: list[LayerScore] = Field(default_factory=list)
    initial_judgment: Judgment = "B. Watch"
    rationale: str = ""


class Consensus(Artifact):
    consensus: str = "Assumed consensus, pending source validation"
    crowded_layers: list[str] = Field(default_factory=list)
    obvious_beneficiaries: list[str] = Field(default_factory=list)
    possible_blind_spots: list[str] = Field(default_factory=list)
    repeated_narratives: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence = "unknown"


class WatchVariable(BaseModel):
    thesis_driver: str | None = None
    variable: str
    why_it_matters: str
    source: str
    frequency: str
    bullish_signal: str
    bearish_signal: str
    current_reading: str | None = None
    next_check: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = "unknown"


class Watchlist(Artifact):
    items: list[WatchVariable] = Field(default_factory=list)
    status_rules: dict[str, str] = Field(default_factory=dict)


class Thesis(BaseModel):
    statement: str = ""
    consensus: str = ""
    variant_view: str = ""
    layer: str = ""
    time_horizon: str = "6-24 months"
    variables: list[str] = Field(default_factory=list)
    falsification: list[str] = Field(default_factory=list)
    buffett_quality_lens: dict[str, Any] = Field(default_factory=dict)
    judgment: Judgment = "B. Watch"
    next_action: str = ""


class ResearchMemo(Artifact):
    direction: str
    trigger: dict[str, Any] = Field(default_factory=dict)
    problem_solved: str = "Source needed"
    facts: list[dict[str, Any]] = Field(default_factory=list)
    value_chain: ValueChain | None = None
    profit_pool: dict[str, Any] = Field(default_factory=dict)
    buffett_quality_lens: dict[str, Any] = Field(default_factory=dict)
    commoditization_risk: list[dict[str, Any]] = Field(default_factory=list)
    market_consensus: str = "Assumed consensus, pending source validation"
    variant_view: str = "Source needed"
    key_variables: list[WatchVariable] = Field(default_factory=list)
    initial_judgment: Judgment = "B. Watch"
    falsification_conditions: list[str] = Field(default_factory=list)
    next_research_steps: list[str] = Field(default_factory=list)


class RunManifest(Artifact):
    direction: str
    regions: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    errors: list[StructuredError] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
