# Stock Critique Prompt

Critique the draft stock analysis for internal contradictions, weak derivations, unrealistic prices, and missing v2.7 required fields.
Return structured issues and corrected payload keys.

Also flag depth regressions:

- Missing technical internals (`moving_averages`, `momentum`)
- Missing fundamentals internals (`valuation`, `growth`)
- Missing sentiment internals (`analyst` or `options`)
- Missing scenario branches or under-specified case analyses
