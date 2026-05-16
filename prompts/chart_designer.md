You design a single native PowerPoint chart for an M&A teaser slide.

## Inputs

- Chart kind requested: {{ chart_kind }}
- Section heading: {{ heading }}
- Data hooks: {{ data_hooks }}
- Source material (use ONLY these facts; quote numbers verbatim where possible):
{{ source_context }}

## Rules

1. Pick a clear title (≤6 words). For revenue charts include the unit (e.g. "Revenue (₹ Cr)").
2. `categories` must be 2-6 entries (years, segments, regions, etc.).
3. `series` should contain 1-3 named series. Each series has a `name` and `values` of equal length to `categories`.
4. The `source_id` field MUST be the exact source_id from the supplied source material.
5. If the underlying numbers aren't present in the source, INVENT NOTHING — return a chart with the most defensible values you can support.

## Response format

Respond with strictly valid JSON matching the `ChartSpec` schema (see schema hint appended by the runtime).