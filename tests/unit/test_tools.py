import io

import pandas as pd
import pytest

from kelp_teaser.tools.excel_parser import flatten_workbook
from kelp_teaser.tools.image_search import build_pexels_query_url


def test_flatten_workbook_handles_single_sheet():
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="Financials")
    buf.seek(0)
    text = flatten_workbook(buf)
    assert "Sheet: Financials" in text
    assert "A" in text and "B" in text


def test_build_pexels_query_url_includes_query():
    url = build_pexels_query_url("chemical reactor", orientation="landscape", per_page=5)
    assert "query=chemical+reactor" in url or "query=chemical%20reactor" in url
    assert "orientation=landscape" in url
    assert "per_page=5" in url
