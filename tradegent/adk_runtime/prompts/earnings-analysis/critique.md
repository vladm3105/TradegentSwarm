# Earnings Critique Prompt

Critique the earnings draft for scenario rigor, gate consistency, and v2.6 completeness.
Focus on event timing assumptions, implied move interpretation, and outcome logic.

Hard checks:

- Verify scoring, do_nothing_gate, and all required scenario branches are present.
- Verify scenario probabilities and expected move logic are internally consistent.
- Verify bull/base/bear argument quality and non-placeholder specificity.

Return JSON payload with this exact shape:

- section_scores: object
  - evidence: number (0-10)
  - consistency: number (0-10)
  - actionability: number (0-10)
- failed_sections: array of section names where score < 7.0
- failed_section_reasons: object mapping failed section name -> concise reason
- issues: array of issue objects
  - path: string
  - issue: string
  - severity: one of [low, medium, high]
  - fix_hint: string

Rules:

- If any section score is below 7.0, include it in failed_sections.
- Every failed section must have a failed_section_reasons entry.
- Avoid markdown; return structured JSON-style content only.
