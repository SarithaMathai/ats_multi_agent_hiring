"""
Parse CSV seed data files into lists of dicts.
NaN values are converted to None. All values remain as strings/None
— type coercion happens in the connector layer.
"""

from pathlib import Path

import pandas as pd


def _load(filepath: Path) -> list[dict]:
    df = pd.read_csv(filepath, dtype=str)
    df = df.where(pd.notna(df), None)
    return df.to_dict(orient="records")


def parse_interviewers(filepath: Path) -> list[dict]:
    return _load(filepath)


def parse_candidates(filepath: Path) -> list[dict]:
    return _load(filepath)


def parse_stages(filepath: Path) -> list[dict]:
    return _load(filepath)


def parse_offers(filepath: Path) -> list[dict]:
    return _load(filepath)


def parse_rejections(filepath: Path) -> list[dict]:
    return _load(filepath)
