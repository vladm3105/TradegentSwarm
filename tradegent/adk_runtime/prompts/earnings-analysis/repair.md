# Earnings Repair Prompt

Repair the earnings analysis using critique findings.
Apply deterministic fixes for every failed section.

Requirements:

- Resolve each item in `failed_sections` with explicit payload updates.
- Preserve scoring, scenario structure, and do_nothing_gate coherence.
- Keep all required scenarios and case analyses complete.
- Use concrete numeric values when provided by context.

Return only the repaired payload structure without markdown.
