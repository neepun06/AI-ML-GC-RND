You scrub identifying information from one bullet/metric of a blind teaser.

## Goal

Rewrite the text so the company is unidentifiable while preserving every numeric and qualitative fact.

## Rules

1. Replace any token containing the real name "{{ real_name }}" (case-insensitive) with "{{ codename }}".
2. Generalize specific addresses to a region (e.g. "Pune" → "western India"; "123 Mumbai Industrial Estate" → "an Indian industrial cluster").
3. Replace exact founding years with ranges (e.g. "founded in 1987" → "founded over 35 years ago").
4. Replace founder names with "the founding team".
5. Keep all numbers, percentages, and currency amounts EXACTLY.

## Input

{{ original_text }}

## Response format

Respond with valid JSON:
{
  "replacement": "<rewritten text or the original if no change needed>"
}
