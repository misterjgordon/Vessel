"""Read inputs and golden outputs from the case study Excel model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

INPUT_OUTPUT_SHEET = 'Input & Output (Basic)'
SAMPLE_DATA_SHEET = 'Sample Data for Testing'


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
    """Load the multi-vessel sample inputs sheet (header row 0)."""
    return pd.read_excel(path, sheet_name=SAMPLE_DATA_SHEET, header=0)
