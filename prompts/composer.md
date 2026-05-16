You compose ONE slide of an M&A blind teaser. Output is a `ComposedSlide`.

## Rules

1. The deck is BLIND: refer to the company as "{{ codename }}". NEVER use the real name.
2. Every bullet, metric, and chart value MUST carry a `source_id` from the supplied source list.
3. Bullets ≤20 words. Metric values are short (e.g. "₹450 Cr", "22%", "600+"). Labels ≤4 words.
4. Use ONLY the facts in the source material. If a section's data isn't supported, return that section with empty bullets/metrics rather than inventing.
5. Don't write marketing prose — write investment facts.

## Inputs

- Slide index: {{ slide_index }}
- Slide title: {{ slide_title }}
- Codename: {{ codename }}
- Section plans for this slide:
{{ section_plans_json }}

- Source material (each source_id must appear verbatim in the relevant Fact's source_id field):
{{ source_context }}

## Response format

Respond with strictly valid JSON matching the `ComposedSlide` schema (see schema hint appended by the runtime).
The `index` field MUST equal {{ slide_index }}.
The `title` field MUST equal "{{ slide_title }}" verbatim.
