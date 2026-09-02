"""KpiWidget — lean KPI params -> full widget JSON.

Agent emits: label*, valueColumn*, aggregation?, prefix?, suffix?, trend params,
            connectionId*, sql*, sources?
Hydrates:    config{label,prefix,suffix,...}; mapping{type:"kpi", valueColumn, aggregation, ...}
"""
from .base import BaseWidget, _pick


class KpiWidget(BaseWidget):
    type = "kpi"
    has_data_source = True
    default_position = {"w": 3, "h": 2, "minW": 2, "minH": 2}
    params_doc = (
        "## KPI params\n"
        "- `label`* (string): card label (NOT 'title')\n"
        "- `valueColumn`* (string): SQL column holding the value\n"
        "- `aggregation` (sum|avg|count|countDistinct|min|max|first|last): "
        "ALWAYS set explicitly to match the KPI's purpose (sum, avg, countDistinct, last, ...); "
        "raw-row SQL (no GROUP BY / aggregate function) without it is rejected before save\n"
        "- `prefix`/`suffix` (string), `compactNumbers`/`roundValue` (bool), `decimalPlaces` (number)\n"
        "- `comparison` (object), `progressVisual` (bar|circle|none)\n"
        "- trend: `autoTrend` (bool), `periodLabel`, `trendDateColumn`, `trendValueColumn`\n"
        "- `connectionId`* (int), `sql`* (string), `sources` (string[])\n"
    )

    _CONFIG_KEYS = ("label", "prefix", "suffix", "roundValue", "decimalPlaces",
                    "compactNumbers", "comparison", "progressVisual")
    _MAPPING_KEYS = ("valueColumn", "aggregation", "autoTrend", "periodLabel",
                     "trendDateColumn", "trendValueColumn")

    def _config(self, params: dict) -> dict:
        return _pick(params, self._CONFIG_KEYS)

    def _mapping(self, params: dict) -> dict:
        return {"type": "kpi", **_pick(params, self._MAPPING_KEYS)}
