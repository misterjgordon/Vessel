"""Read inputs and golden outputs from the case study Excel model."""

from pathlib import Path
from typing import Any
from typing import cast

import pandas as pd

from vessel_valuation.validation import median_pp_teu_factor
from vessel_valuation.validation import validate

INPUT_OUTPUT_SHEET = 'Input & Output (Basic)'
SAMPLE_DATA_SHEET = 'Sample Data for Testing'

# Case-study Sample Data display headers → VesselInputs field names (also used by file_parser).
UPLOAD_HEADER_ALIASES: dict[str, str] = {
    'Input Field': 'vessel_name',
    'TEU Size': 'teu_size',
    'LWT': 'lw_tonnage',
    'Vessel Purchase Date': 'purchase_date',
    'Vessel Purchase Price': 'purchase_price',
    'Vessel Expect Life': 'vessel_life',
    'Vessel Residual Value': 'residual_value',
    'Revenue per Day': 'revenue_per_day',
    'Days of a Year': 'days_of_year',
    'Offhire Rate %': 'offhire_rate',
    'Operating Expense (OpEx) per Day': 'opex_per_day',
    'Drydock CapEx Cost': 'drydock_capex',
    'Drydock Frequency': 'drydock_frequency',
    'Upgrades CapEx Cost': 'upgrades_capex',
    'Inflation Rate Assumption': 'inflation_rate',
    'Discount Rate Assumption': 'discount_rate',
    'Engine': 'engine_type',
    'CO2 Carbon Factor': 'co2_carbon_factor',
}


def _field_value_map(df: pd.DataFrame) -> dict[str, Any]:
    """Map Input/Output Field column to Value column (first two columns)."""
    fields = df.iloc[:, 0].astype(str).str.strip()
    values = df.iloc[:, 1]
    return dict(zip(fields, values, strict=False))


def load_input_output_sheet(path: Path) -> pd.DataFrame:
    """Load the basic input/output sheet as a raw DataFrame."""
    return pd.read_excel(path, sheet_name=INPUT_OUTPUT_SHEET, header=None)


def read_basic_inputs(path: Path) -> dict[str, Any]:
    """Return case-study inputs from the basic sheet (rows labeled Input Field)."""
    df = load_input_output_sheet(path)
    inputs: dict[str, Any] = {}
    in_inputs = False
    for _, row in df.iterrows():
        label = row.iloc[0]
        if not isinstance(label, str):
            continue
        label = label.strip()
        if label == 'Input Field':
            in_inputs = True
            continue
        if label == 'Output Field':
            break
        if in_inputs:
            inputs[label] = row.iloc[1]
    return inputs


def read_basic_outputs(path: Path) -> dict[str, float]:
    """Return golden NPV and IRR from the basic sheet."""
    df = load_input_output_sheet(path)
    table = _field_value_map(df)
    npv = float(table['NPV'])
    irr = float(table['IRR'])
    return {'npv': npv, 'irr': irr}


def load_sample_vessels(path: Path) -> pd.DataFrame:
    """Load the multi-vessel sample sheet with headers renamed to VesselInputs names."""
    df = pd.read_excel(path, sheet_name=SAMPLE_DATA_SHEET, header=0)
    return df.rename(columns=UPLOAD_HEADER_ALIASES)


def build_pp_teu_benchmarks_from_workbook(path: Path) -> dict[int, float]:
    """Compute median purchase-price÷TEU ratios from a case-study sample sheet."""
    df = load_sample_vessels(path)
    inputs = []
    for _, row in df.iterrows():
        result = validate(cast('dict[str, object]', row.to_dict()))
        if result.inputs is not None:
            inputs.append(result.inputs)
    return median_pp_teu_factor(inputs)
