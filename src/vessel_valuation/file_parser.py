"""CSV / Excel file upload parser — two-pass validation strategy.

**Files:** ``.csv``, ``.xlsx``, ``.xlsm``, ``.xls`` (see ``ACCEPTED_UPLOAD_EXTENSIONS``).

**Layout:** row 1 = header; rows 2+ = one vessel per row (blank rows are skipped).
Headers may be either
``VesselInputs`` field names (``vessel_name``, ``teu_size``, …) or case-study
Sample Data labels (``TEU Size``, ``Vessel Purchase Price``, …) — see
``UPLOAD_HEADER_ALIASES`` in ``excel_reference``. Excel prefers the
``Sample Data for Testing`` sheet when present; otherwise the first sheet.
The vertical Input & Output sheet layout is not supported.

Pass 1 — Structural (per-row):
    Header check: every required column present.
    Row check: sentinel string detection, type coercibility (Tier 1 rules).
    Rows that fail Pass 1 cannot be computed and are flagged with errors.

Pass 2 — Business rules (per-row, on coerced inputs):
    Tier 2 purchase-price÷TEU checks use medians from the **saved fleet**
  only (2+ vessels at the same exact TEU). When the database has no peer
    median for that TEU, case-study defaults from ``case_study_benchmarks``
    apply. Other rows in the same upload file are not used as PP÷TEU peers.

Public API
----------
    ACCEPTED_UPLOAD_EXTENSIONS       → frozenset of allowed filename suffixes
    REQUIRED_COLUMNS                 → VesselInputs field names after header normalisation
    peer_pp_teu_factor_benchmarks(...) → PP/TEU factor medians for upload / Calculate
    parse_dataframe(df, source_name) → ParseResult (one RowResult per non-blank data row)
    parse_upload(data, filename)     → ParseResult   (thin file-load wrapper)
"""

import dataclasses
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from vessel_valuation.excel_reference import SAMPLE_DATA_SHEET, UPLOAD_HEADER_ALIASES
from vessel_valuation.schema import ValidationThresholds, VesselInputs
from vessel_valuation.validation import (
    median_pp_teu_factor,
    tier2_warnings,
    validate,
    vessel_inputs_identity,
)

REQUIRED_COLUMNS: frozenset[str] = frozenset(f.name for f in dataclasses.fields(VesselInputs))

# Filename suffix selects CSV vs Excel reader in ``_load_dataframe``.
ACCEPTED_UPLOAD_EXTENSIONS: frozenset[str] = frozenset({'.csv', '.xlsx', '.xlsm', '.xls'})


@dataclass
class RowResult:
    """Validation outcome for a single row in the uploaded file."""

    row_number: int
    raw: dict[str, object]
    errors: list[str]
    warnings: list[str]
    inputs: VesselInputs | None

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


@dataclass
class ParseResult:
    """Outcome of parsing and validating an entire uploaded file."""

    filename: str
    header_errors: list[str]
    rows: list[RowResult]

    @property
    def ok(self) -> bool:
        """True when the file loaded successfully (headers valid)."""
        return not self.header_errors

    @property
    def error_count(self) -> int:
        """Number of rows with Tier 1 errors."""
        return sum(1 for r in self.rows if r.errors)

    @property
    def warning_count(self) -> int:
        """Number of Tier-1-clean rows that carry at least one Tier 2 warning."""
        return sum(1 for r in self.rows if not r.errors and r.warnings)

    @property
    def valid_inputs(self) -> list[VesselInputs]:
        """All VesselInputs instances from rows that passed Tier 1."""
        return [r.inputs for r in self.rows if r.inputs is not None]

    @property
    def batch_pp_teu_factor_benchmarks(self) -> dict[int, float]:
        """Median PP/TEU factors from valid rows in this upload (Pass 2)."""
        return median_pp_teu_factor(self.valid_inputs)


def _normalize_upload_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Map case-study display headers to VesselInputs names; pass through known field names."""
    renamed = {
        str(col).strip(): UPLOAD_HEADER_ALIASES.get(str(col).strip(), str(col).strip())
        for col in df.columns
    }
    return df.rename(columns=renamed)


def _check_headers(columns: list[str]) -> list[str]:
    """Return one error per required column absent after header normalisation."""
    present = frozenset(columns)
    missing = sorted(REQUIRED_COLUMNS - present)
    return [
        f"Missing required column: '{col}' "
        f'(use the manual form field name or the matching case-study header)'
        for col in missing
    ]


def _dataframe_with_required_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only VesselInputs columns, in stable order, after header validation."""
    ordered = [col for col in sorted(REQUIRED_COLUMNS) if col in df.columns]
    return df.reindex(columns=ordered)


def _is_blank_row(row: dict[str, object]) -> bool:
    """Return whether every cell is empty or null after normalisation."""
    for value in row.values():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return False
    return True


def _coerce_cell_for_raw(value: object) -> object:
    """Coerce spreadsheet cell values to JSON-safe Python types for stores and validation."""
    if value is None:
        return None
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _normalise_row(row: dict[str, object]) -> dict[str, object]:
    """Replace pandas NA / NaN / NaT with None; coerce types for JSON stores."""
    return {key: _coerce_cell_for_raw(value) for key, value in row.items()}


def peer_pp_teu_factor_benchmarks(
    inputs_list: list[VesselInputs],
    subject: VesselInputs,
) -> dict[int, float]:
    """Median PP/TEU factor of other vessels at the same exact TEU (D-014)."""
    subject_key = vessel_inputs_identity(subject)
    peers = [
        inp
        for inp in inputs_list
        if vessel_inputs_identity(inp) != subject_key and inp.teu_size == subject.teu_size
    ]
    return median_pp_teu_factor(peers)


def valid_inputs_from_upload_store(upload_store: dict[str, object]) -> list[VesselInputs]:
    """Coerce Tier-1-valid rows from an upload ``dcc.Store`` payload."""
    rows = upload_store.get('rows')
    if not isinstance(rows, list):
        return []
    inputs: list[VesselInputs] = []
    for entry in rows:
        if not isinstance(entry, dict) or entry.get('errors'):
            continue
        raw = entry.get('raw')
        if not isinstance(raw, dict):
            continue
        result = validate(raw)
        if result.inputs is not None:
            inputs.append(result.inputs)
    return inputs


def pp_teu_factor_benchmarks_for_subject(
    fleet_peers: list[VesselInputs],
    subject: VesselInputs,
) -> dict[int, float]:
    """PP÷TEU medians from saved fleet at subject's TEU (leave-one-out), if 2+ peers exist."""
    return peer_pp_teu_factor_benchmarks(fleet_peers, subject)


def _read_excel_table(data: bytes | Path | io.BytesIO) -> pd.DataFrame:
    """Load a tabular Excel sheet; prefer case-study sample sheet when present."""
    workbook = pd.ExcelFile(data)
    sheet: str | int = SAMPLE_DATA_SHEET if SAMPLE_DATA_SHEET in workbook.sheet_names else 0
    return pd.read_excel(workbook, sheet_name=sheet, header=0)


def _load_dataframe(data: bytes | Path, filename: str) -> pd.DataFrame:
    """Load a DataFrame from file bytes or a Path, auto-detecting format."""
    ext = (Path(filename).suffix if filename else '').lower()
    if isinstance(data, Path):
        ext = data.suffix.lower()
        if ext == '.csv':
            return pd.read_csv(data)
        return _read_excel_table(data)
    buf = io.BytesIO(data)
    if ext == '.csv':
        return pd.read_csv(buf)
    return _read_excel_table(buf)


def parse_dataframe(
    df: pd.DataFrame,
    source_name: str = '',
    thresholds: ValidationThresholds | None = None,
    fleet_peer_inputs: list[VesselInputs] | None = None,
) -> ParseResult:
    """Parse and validate a DataFrame that has already been loaded.

    Headers are normalised via ``UPLOAD_HEADER_ALIASES`` (case-study labels) or
    accepted as ``VesselInputs`` field names already. Extra columns are dropped;
    missing columns produce ``header_errors`` and no row parsing.

    Parameters
    ----------
    df
        DataFrame with header row already consumed (``header=0``).
    source_name
        Human-readable label for error messages (e.g. the original filename).
    thresholds
        Tier 2 TEU benchmark warning bands passed through to validation.
    fleet_peer_inputs
        Saved fleet rows used for Tier 2 PP÷TEU peers (same TEU, leave-one-out).

    Returns
    -------
    ParseResult
        ``header_errors`` is non-empty if required columns are missing —
        parsing stops at that point. Otherwise, ``rows`` contains one
        ``RowResult`` per non-blank data row with Tier 1 errors and Tier 2 warnings.
        ``batch_pp_teu_factor_benchmarks`` aggregates upload-row PP/TEU factor medians.
    """
    df_normalized = _normalize_upload_headers(df)
    header_errors = _check_headers(df_normalized.columns.tolist())
    if header_errors:
        return ParseResult(filename=source_name, header_errors=header_errors, rows=[])

    df_required = _dataframe_with_required_columns(df_normalized)

    # Pass 1 — Tier 1 validation per non-blank row (spreadsheet row numbers preserved)
    pass1: list[tuple[int, dict[str, object], list[str], VesselInputs | None]] = []
    for df_index in range(len(df_required)):
        raw = _normalise_row(df_required.iloc[df_index].to_dict())
        if _is_blank_row(raw):
            continue
        row_num = df_index + 2
        result = validate(raw, thresholds=thresholds)
        pass1.append((row_num, raw, result.errors, result.inputs))

    fleet_peers = fleet_peer_inputs or []

    # Pass 2 — Tier 2 per row: DB fleet peers only, else case-study PP÷TEU defaults
    rows: list[RowResult] = []
    for row_num, raw, errors, inputs in pass1:
        if inputs is not None:
            peer_benchmarks = peer_pp_teu_factor_benchmarks(fleet_peers, inputs)
            warnings = tier2_warnings(inputs, peer_benchmarks or None, thresholds)
        else:
            warnings = []
        rows.append(
            RowResult(
                row_number=row_num,
                raw=raw,
                errors=errors,
                warnings=warnings,
                inputs=inputs,
            )
        )

    return ParseResult(filename=source_name, header_errors=[], rows=rows)


def parse_upload(
    data: bytes | Path,
    filename: str,
    thresholds: ValidationThresholds | None = None,
    fleet_peer_inputs: list[VesselInputs] | None = None,
) -> ParseResult:
    """Load a CSV or XLSX file and run two-pass validation.

    Parameters
    ----------
    data
        Raw file bytes (e.g. from a Dash upload callback) or a ``Path``
        to a local file.
    filename
        Original filename — used to detect the format (``.csv`` vs ``.xlsx``)
        and for error messages.
    thresholds
        Tier 2 TEU benchmark warning bands passed through to validation.
    fleet_peer_inputs
        Saved fleet rows included as Tier 2 peers (see ``parse_dataframe``).

    Returns
    -------
    ParseResult
        See ``parse_dataframe`` for full description.
    """
    df = _load_dataframe(data, filename)
    return parse_dataframe(
        df,
        source_name=filename,
        thresholds=thresholds,
        fleet_peer_inputs=fleet_peer_inputs,
    )
