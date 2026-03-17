# Earnings Draft Prompt

Generate a structured earnings analysis JSON object from available context and tool data.
Use evidence-first reasoning with explicit numeric support.
Do not use placeholders.

Required output depth:

- Include `summary`, `scoring`, and `do_nothing_gate`.
- Include all scenarios: `strong_beat`, `modest_beat`, `modest_miss`, `strong_miss`.
- Use explicit probabilities and ensure scenario logic is coherent.
- Provide at least 3 arguments in bull/base/bear case sections.
- Include implied-move context and tie it to scenario expectations.

Style constraints:

- Prefer concrete values over generic statements.
- When data is missing, mark the exact missing field instead of inventing values.
