import pytest
from pydantic import ValidationError
from backend.schemas.briefing import BriefingPayload, Kpi, Section


def _valid_payload():
    return {
        "headline": "Revenue held",
        "deck": "Topline tracked.",
        "kpis": [
            {"label": "MRR", "value": "$13,816", "delta_vs_prev": "+0.3%", "delta_direction": "up"}
        ],
        "sections": [
            {"heading": "1. Champion lift", "prose": "Strong growth.", "widget_id": "chart_revenue"}
        ],
        "key_takeaways": ["one", "two", "three"],
    }


def test_valid_payload():
    p = BriefingPayload.model_validate(_valid_payload())
    assert p.headline == "Revenue held"
    assert len(p.key_takeaways) == 3


def test_kpis_max_three():
    data = _valid_payload()
    data["kpis"] = [{"label": "x", "value": "1"}] * 4
    with pytest.raises(ValidationError):
        BriefingPayload.model_validate(data)


def test_sections_min_one():
    data = _valid_payload()
    data["sections"] = []
    with pytest.raises(ValidationError):
        BriefingPayload.model_validate(data)


def test_key_takeaways_must_be_three():
    data = _valid_payload()
    data["key_takeaways"] = ["one", "two"]
    with pytest.raises(ValidationError):
        BriefingPayload.model_validate(data)


def test_section_widget_id_optional():
    data = _valid_payload()
    data["sections"][0].pop("widget_id")
    p = BriefingPayload.model_validate(data)
    assert p.sections[0].widget_id is None


def test_kpi_delta_direction_enum():
    with pytest.raises(ValidationError):
        Kpi.model_validate({"label": "x", "value": "1", "delta_direction": "sideways"})
