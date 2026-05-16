"""Excel workbook flattener."""
from __future__ import annotations

from typing import IO, Union

import pandas as pd


def flatten_workbook(source: Union[str, IO[bytes]]) -> str:
    """Read every sheet and return a single text dump suitable for LLM ingestion."""
    sheets: dict[str, pd.DataFrame] = pd.read_excel(source, sheet_name=None)
    parts: list[str] = []
    for name, df in sheets.items():
        parts.append(f"[Sheet: {name}]")
        parts.append(df.to_string())
        parts.append("")
    return "\n".join(parts)
