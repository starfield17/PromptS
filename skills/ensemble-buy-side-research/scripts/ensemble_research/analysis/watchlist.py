from __future__ import annotations

from ..models import Thesis, ValueChain, WatchVariable, Watchlist


DEFAULT_VARIABLES = {
    "chip": ("Accelerator shipments / backlog", "Company filings / earnings calls", "Quarterly", "Backlog expands with stable margins", "Backlog weakens or margins compress"),
    "memory": ("HBM pricing and capacity", "Supplier calls / industry data", "Quarterly", "Tight supply and firm pricing", "Capacity glut or rapid ASP decline"),
    "packaging": ("Advanced packaging capacity", "Foundry / OSAT disclosures", "Quarterly", "Persistent constraint and paid capacity", "Rapid normalization without margin benefit"),
    "software": ("Paid conversion / retention", "Company metrics / customer checks", "Quarterly", "Rising paid usage and renewal", "Churn or price pressure"),
    "power": ("Data-center power availability", "Utility / data-center disclosures", "Quarterly", "Power constraints sustain infrastructure demand", "Deployment delays or weaker utilization"),
}


def generate_watchlist(thesis: Thesis | None = None, value_chain: ValueChain | None = None) -> Watchlist:
    items: list[WatchVariable] = []
    variables = thesis.variables if thesis and thesis.variables else []
    for variable in variables:
        items.append(
            WatchVariable(
                thesis_driver=thesis.statement if thesis else None,
                variable=variable,
                why_it_matters="Directly tests the stated thesis driver.",
                source="Source needed",
                frequency="Monthly / Quarterly",
                bullish_signal="Improves in line with thesis",
                bearish_signal="Deteriorates or fails to appear within the thesis horizon",
                current_reading="Source needed",
                confidence="low",
            )
        )
    if value_chain:
        for layer in value_chain.layers:
            lower = layer.name.lower()
            for key, spec in DEFAULT_VARIABLES.items():
                if key in lower and not any(item.variable == spec[0] for item in items):
                    variable, source, frequency, bullish, bearish = spec
                    items.append(
                        WatchVariable(
                            thesis_driver=layer.name,
                            variable=variable,
                            why_it_matters=f"Tests whether {layer.name} is a durable bottleneck or profit pool.",
                            source=source,
                            frequency=frequency,
                            bullish_signal=bullish,
                            bearish_signal=bearish,
                            current_reading="Source needed",
                            source_ids=value_chain.source_ids,
                            confidence="medium",
                        )
                    )
    if not items:
        items.append(
            WatchVariable(
                thesis_driver="Core thesis",
                variable="Revenue, margin, orders, capacity, and pricing evidence",
                why_it_matters="Minimum observable data needed to move from narrative to thesis.",
                source="Company filings / calls / industry data",
                frequency="Quarterly",
                bullish_signal="Demand growth appears with stable or improving economics",
                bearish_signal="Revenue grows but economics deteriorate",
                current_reading="Source needed",
                confidence="low",
            )
        )
    return Watchlist(
        items=items,
        status_rules={
            "upgrade_if": "Key variables improve for two reporting cycles and profit-pool evidence strengthens.",
            "downgrade_if": "Growth appears only in low-quality or commoditizing layers.",
            "abandon_if": "The observable variables fail to connect to margin, bargaining power, or cash-flow improvement.",
        },
    )
