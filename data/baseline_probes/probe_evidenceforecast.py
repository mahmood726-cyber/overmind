import sys, json
sys.path.insert(0, ".")
from evidence_forecast.representativeness import compute_representativeness
from evidence_forecast.constants import (
    SCHEMA_VERSION, FORECAST_HORIZON_MONTHS,
    PICO_REQUIRED_FIELDS, EFFECT_FIELDS, FLIP_FIELDS, REPRESENTATIVENESS_FIELDS,
    CARD_TOP_LEVEL_FIELDS,
)

# Fixed normalised weights — burden-weighted overlap is deterministic
trial_w  = {"USA": 0.50, "GBR": 0.30, "CAN": 0.20}
burden_w = {"IND": 0.40, "USA": 0.30, "GBR": 0.20, "CAN": 0.10}
res = compute_representativeness(trial_w, burden_w, source="aact")

# Empty trial weights → degenerate path
empty = compute_representativeness({}, burden_w)

print(json.dumps({
    "schema_version": SCHEMA_VERSION,
    "forecast_horizon_months": FORECAST_HORIZON_MONTHS,
    "n_pico_required": len(PICO_REQUIRED_FIELDS),
    "n_effect_fields": len(EFFECT_FIELDS),
    "n_flip_fields": len(FLIP_FIELDS),
    "n_card_top_level": len(CARD_TOP_LEVEL_FIELDS),
    "overlap_score": round(res.overlap_score, 6),
    "trial_country_count": res.trial_country_count,
    "burden_weighted": res.burden_weighted,
    "source_aact": res.source,
    "empty_overlap": empty.overlap_score,
    "empty_source": empty.source,
}))