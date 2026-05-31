from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASE_STUDY_XLSX = (
    ROOT
    / 'docs'
    / 'case_study'
    / ('Interview Case Study - Finance Solution Developer - Model.xlsx')
)
CASE_STUDY_PDF = (
    ROOT / 'docs' / 'case_study' / ('Interview Case Study - Finance Solution Developer.pdf')
)


@pytest.fixture
def case_study_xlsx() -> Path:
    assert CASE_STUDY_XLSX.is_file(), f'missing workbook: {CASE_STUDY_XLSX}'
    return CASE_STUDY_XLSX


@pytest.fixture
def case_study_pdf() -> Path:
    assert CASE_STUDY_PDF.is_file(), f'missing instructions: {CASE_STUDY_PDF}'
    return CASE_STUDY_PDF
