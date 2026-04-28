from __future__ import annotations

from ..models import EntityPack, Players, ValueChain, ValueChainLayer


GENERIC_LAYERS = [
    ("raw materials", "Provides scarce or specialized inputs required by the direction."),
    ("specialized inputs", "Turns raw inputs into higher-spec materials, parts, or data inputs."),
    ("equipment / tools", "Enables production, deployment, testing, or scaling."),
    ("core components", "Delivers the core performance bottleneck of the system."),
    ("systems / integration", "Packages components into usable products or infrastructure."),
    ("software / control", "Improves utilization, control, automation, or workflow economics."),
    ("distribution / channels", "Owns customer access and commercial conversion."),
    ("customer application", "Monetizes the solution in end-user workflows."),
    ("services / aftermarket", "Captures recurring support, maintenance, data, or upgrade spend."),
]

AI_LAYERS = [
    ("accelerator chips", "Compute throughput, latency, and cost per token."),
    ("HBM / memory", "Feeds data to compute and reduces memory bottlenecks."),
    ("advanced packaging", "Connects compute and memory at high bandwidth."),
    ("networking", "Moves data across clusters and improves scale-out efficiency."),
    ("power and cooling", "Allows denser and more reliable data-center deployment."),
    ("software optimization", "Improves utilization, serving cost, and workload portability."),
    ("cloud service layer", "Packages inference capacity into customer-facing services."),
]

ROBOTICS_LAYERS = [
    ("actuators and motion control", "Converts power and control signals into precise movement."),
    ("sensors", "Provides perception, safety, and feedback data."),
    ("battery and power", "Determines endurance, weight, and duty cycle."),
    ("control software", "Coordinates perception, planning, and actuation."),
    ("system integration", "Turns components into reliable deployable robots."),
    ("application deployment", "Adapts robots to real workflows and service economics."),
]

SAAS_LAYERS = [
    ("core workflow software", "Owns the customer workflow and system of record."),
    ("payments / monetization", "Captures transaction economics attached to usage."),
    ("data integration", "Reduces switching friction and connects existing systems."),
    ("go-to-market", "Converts vertical customers efficiently."),
    ("support / compliance", "Handles local regulation, trust, and implementation."),
]


def choose_layers(direction: str, entities: EntityPack | None = None) -> list[tuple[str, str]]:
    lower = direction.lower()
    if any(term in lower for term in ["ai", "inference", "chip", "gpu", "accelerator"]):
        return AI_LAYERS
    if any(term in lower for term in ["robot", "humanoid", "机器人"]):
        return ROBOTICS_LAYERS
    if any(term in lower for term in ["saas", "software"]):
        return SAAS_LAYERS
    if entities and entities.possible_layers:
        return [(layer, f"Layer explicitly surfaced in sources for {direction}.") for layer in entities.possible_layers]
    return GENERIC_LAYERS


def _assign_players(layer: str, companies: list[str]) -> Players:
    layer_lower = layer.lower()
    global_players: list[str] = []
    regional_players: list[str] = []
    for company in companies:
        is_cn = any("\u4e00" <= ch <= "\u9fff" for ch in company) or company.endswith((".SS", ".SZ", ".HK"))
        target = regional_players if is_cn else global_players
        if len(target) < 8:
            target.append(company)
    if not global_players and not regional_players:
        if "chip" in layer_lower:
            global_players = ["Source needed: leading chip vendors and custom ASIC suppliers"]
        elif "memory" in layer_lower:
            global_players = ["Source needed: memory suppliers"]
        else:
            global_players = ["Source needed"]
    return Players(global_=global_players, regional=regional_players)


def build_value_chain(direction: str, entities: EntityPack | None = None, source_ids: list[str] | None = None) -> ValueChain:
    entities = entities or EntityPack()
    layers: list[ValueChainLayer] = []
    for name, problem in choose_layers(direction, entities):
        lower = name.lower()
        bottleneck = "high" if any(term in lower for term in ["chip", "memory", "packaging", "actuator", "core"]) else "medium"
        profit = "high" if bottleneck == "high" else "medium"
        commoditization = "high" if any(term in lower for term in ["distribution", "services", "application"]) else "medium"
        competition = "high" if any(term in lower for term in ["software", "application", "cloud"]) else "medium"
        layers.append(
            ValueChainLayer(
                name=name,
                problem_solved=problem,
                players=_assign_players(name, entities.companies),
                bottleneck_level=bottleneck,
                profit_pool_quality=profit,
                competition_intensity=competition,
                commoditization_risk=commoditization,
                judgment="Preliminary map; validate economics with filings, margins, customer concentration, and pricing evidence.",
                evidence_needed=[
                    "Layer-level gross margin or proxy margin",
                    "Customer concentration and switching-cost evidence",
                    "Capacity, pricing, or utilization data",
                ],
            )
        )
    return ValueChain(direction=direction, layers=layers, source_ids=source_ids or entities.source_ids)
