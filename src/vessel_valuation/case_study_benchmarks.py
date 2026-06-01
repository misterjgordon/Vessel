"""Case-study PP÷TEU benchmarks ingested from the interview sample workbook."""

import json
from importlib.resources import files

_BENCHMARKS_RESOURCE = 'case_study_pp_teu_benchmarks.json'


def load_case_study_pp_teu_benchmarks() -> dict[int, float]:
    """Return exact TEU → median purchase-price÷TEU ratio from bundled case-study data."""
    payload = json.loads(
        files('vessel_valuation.data').joinpath(_BENCHMARKS_RESOURCE).read_text(encoding='utf-8')
    )
    medians = payload['medians_by_teu']
    return {int(teu): float(ratio) for teu, ratio in medians.items()}
