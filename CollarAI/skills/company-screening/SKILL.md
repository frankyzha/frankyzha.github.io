---
name: company-screening
description: Run structured company screens through the CollarAI browser MCP.
---

# Company screening

Use these tools only for explicit market-data research. For unrelated requests, do not call them.
If a required company or ambiguous financial concept is missing, ask one focused clarification;
never guess it. Omit genuinely optional filters rather than inventing values.

For company-discovery constraints, use one `screen_companies` call. Use exact site-independent
fields; for “founded after 2020,” set `founded_year_min` to `2021`. Keep “less than” bounds strict.

For financing questions, call `analyze_financing_transactions` with the company, category, metric,
and any exact deal types. For example, debt-refinancing total uses category `Debt Financing`, metric
`sum_amount`, and deal type `Debt Refinancing`. Report the returned value, matched/disclosed/missing
counts, synthetic-data flag, and run ID; never ask the language model to calculate the aggregate.

If the result is `complete`, summarize only returned companies and retain the run ID as evidence.
If it is `needs_human`, tell the user exactly which login checkpoint is open and wait. If it is
`needs_configuration`, do not improvise UI actions or data; request the adapter-recording step.

Example arguments:

```json
{
  "screen": {
    "platform": "toy",
    "countries": ["United States"],
    "industries": ["Enterprise Software"],
    "founded_year_min": 2021,
    "funding_stages": ["Series A", "Series B"],
    "total_raised_usd_lt": 50000000,
    "limit": 25
  }
}
```
