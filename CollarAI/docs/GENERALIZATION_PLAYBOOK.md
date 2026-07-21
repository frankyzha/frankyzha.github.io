# CollarAI Browser Generalization Playbook (经验)

Date: 2026-07-21

This note records what the PitchBook proof of concept actually demonstrated, how
the implementation was generalized, and which parts still require production
work. It is intended as a reusable guide for adding new website adapters.

## What the demonstration did—and did not do

The human demonstrated one concrete path:

1. Search for Nvidia.
2. Open the exact company profile.
3. Open the Deals tab.
4. Select Debt Financing and USD.
5. Leave the final transaction table visible.

The successful demonstration recorder captured clicks, changes, navigations,
semantic element metadata, the final accessibility tree, and a screenshot. It
redacted password-field values. The recording was observational evidence, not a
trained model, an executable macro, or sufficient code by itself. An earlier
Playwright-codegen file in the capture directory recorded only the failed
Cloudflare loop and was not used to build the adapter.

We used that evidence to implement a deterministic Stagehand v3 adapter. Then we
inspected the live category control and table structure to extend the adapter
beyond the demonstrated Nvidia/debt path. The resulting code accepted company,
financing category, metric, and optional exact deal types as data. It was then
tested against Apple, Nvidia, debt, equity, refinancing, and IPO cases.

## The abstraction we implemented

The public MCP operation for the generalized workflow is conceptually:

```text
analyze_financing_transactions(
    company_name,
    category,       # All Deals | Debt Financing | Equity Financing
    metric,         # sum/average Amount or latest/min/max/average Raised to Date
    deal_types=[],  # optional exact row-level Deal Type filters, such as IPO
) -> typed transactions + exact aggregate + evidence path
```

The execution path is:

```text
Hermes chooses a typed MCP tool
  -> BrowserService creates a run and evidence directory
  -> PitchBookAdapter establishes an authenticated page
  -> adapter opens the exact company and Deals surface
  -> adapter applies category and USD
  -> adapter exhausts pagination and returns typed rows
  -> pure Python filters and aggregates the rows
  -> service returns JSON plus screenshot/Stagehand-action evidence
```

The language model plans and supplies structured arguments. It does not read the
table screenshot or do arithmetic in this workflow. Stagehand performs browser
actions, a direct CDP layer reads the DOM, Pydantic validates records, and
deterministic Python performs the calculation.

## How to decompose a human trace into functions

Do not create one function per gesture and do not preserve the demonstration as
one giant macro. Group steps around stable state transitions and observable
postconditions. A boundary is useful when at least one of these is true:

- the step group has a reusable input;
- completion can be asserted from the page;
- it has a distinct retry or recovery policy;
- it crosses a security/session boundary;
- its output can be made typed;
- the work is pure computation and should be tested without a browser.

An illustrative 20-gesture demonstration decomposes as follows:

| Human gestures | Capability | Contract/postcondition |
|---|---|---|
| 1–3 | `ensure_authenticated` | PitchBook search shell is visible |
| 4–7 | `_open_company(company_name)` | Exactly one matching company profile is open |
| 8–9 | `_open_deals()` | URL and selected tab identify the Deals surface |
| 10–13 | `_apply_category(category)` | Requested category and USD are selected; expected table exists |
| 14–18 | `_extract_all_pages()` | All pages are exhausted and converted to typed rows without duplicates |
| 19–20 | filter + `aggregate_financing()` | Exact row subset and reproducible numeric result |

The gesture counts are illustrative; the contracts determine the boundaries.
Low-level methods remain private adapter helpers. Only durable user intents are
exposed as MCP tools.

## The actual MCP tools in this repository

`src/collarai/mcp_server.py` currently exposes four tools:

1. `screen_companies(screen)` — structured company discovery. The toy adapter
   works; the PitchBook company-screener workflow needs its own demonstration
   and implementation.
2. `analyze_financing_transactions(request)` — the generalized financing-table
   tool used for the ten live questions.
3. `get_browser_session_status(platform)` — reports persistent-browser session
   state.
4. `get_browser_run(run_id)` — reloads a saved typed result and evidence path.

Historical results from the retired one-off debt-refinancing tool remain readable,
but that redundant operation is no longer exposed for new runs.

These are the MCP functions Hermes and its model can see. Methods such as
`_open_company`, `_open_deals`, and `_extract_all_pages` are implementation
details; exposing them would make the model micromanage fragile page gestures.

## What generalized in the live test

The original recording showed only Nvidia and Debt Financing. The implementation
subsequently handled:

- a different entity (Apple);
- a different category (Equity Financing);
- exact row-level deal types (Debt Refinancing, IPO, and Grant);
- all rows across pagination;
- six aggregates over Amount and Raised to Date;
- disclosed and missing values without treating missing as zero.

This was parameter generalization plus new live discovery—not evidence that one
trace automatically teaches every future site operation. A new page family such
as the company screener still needs discovery, an adapter contract, and tests.

## Stagehand v3 migration verification

The Playwright runtime was removed. Native Stagehand v3 now owns navigation and
interaction, while a small CDP client handles deterministic inspection and
evidence. `scripts/validate_pitchbook_queries.py` contains only the ten typed
requests—no expected answers or company-specific extraction shortcuts.

On 2026-07-21, all ten requests completed against live PitchBook data:

| # | Result | Coverage |
|---|---:|---|
| 1 | Apple Debt Refinancing sum: $0 | zero exact matching rows |
| 2 | Nvidia latest debt Raised to Date: $41.06B | 4/4 disclosed |
| 3 | Apple latest debt Raised to Date: $102.36B | 21/21 disclosed |
| 4 | Nvidia minimum debt Raised to Date: $2.06B | 4/4 disclosed |
| 5 | Nvidia maximum debt Raised to Date: $41.06B | 4/4 disclosed |
| 6 | Nvidia average debt Raised to Date: $17.56B | 4/4 disclosed |
| 7 | Nvidia average Debt Refinancing Amount: $9.25B | 4/4 disclosed |
| 8 | Nvidia total Equity Financing Amount: $4.06192B | 6 disclosed, 1 missing |
| 9 | Nvidia average Equity Financing Amount: $676,986,667 | 6 disclosed, 1 missing |
| 10 | Nvidia IPO Amount: $42M | one exact IPO row |

One warm session produced all ten evidence results in 10.6 seconds. The first
company/category loads took seconds; repeated calculations over an already
validated table took about 0.12 seconds each. This comes from retaining the
Stagehand session, checking page postconditions before navigating, extracting
the current table directly, and capturing only the visible viewport. It is not
an answer cache.

The later semantic-routing regression used Duke-hosted Gemma 4 26B-A4B with a
131,072-token server context. All ten original questions routed to the expected
typed requests. It also accepted “What is OpenAI total grant?”, routed it to All
Deals plus exact deal type Grant, and rejected irrelevant and incomplete prompts
without opening the browser. The live non-synthetic PitchBook run found two
disclosed Grant rows ($30M and $1B) and returned $1.03B under run ID
`8104369c-2bc9-4a87-bfcc-0a6abc63b717`.

## How the Nvidia IPO answer was obtained

The demonstration did not show IPO and did not contain enough information to
answer the IPO question. It supplied the route and table pattern. During the
generalization run, we inspected the live category options, selected Equity
Financing, extracted the complete table by column name, and found the row whose
Deal Type was exactly `IPO`.

The generalized request was:

```json
{
  "platform": "pitchbook",
  "company_name": "Nvidia",
  "category": "Equity Financing",
  "metric": "sum_amount",
  "deal_types": ["IPO"]
}
```

The saved non-synthetic result records one matching row dated 1999-01-22 with an
Amount of USD 42,000,000 and Raised to Date of USD 61,930,000. The question asks
for the IPO amount, so the answer uses `Amount`, not `Raised to Date`. The result
is preserved under run ID `85e1fd6d-0cd1-4d16-b75d-9c2338a5ca56`, together with
the final screenshot and Stagehand action log.

## Failures that improved the adapter

1. Stagehand v3's XPath parser mishandled a positional expression beginning with
   parentheses. The adapter now validates the intended autocomplete result,
   gives it a unique temporary attribute, and passes that stable XPath to
   Stagehand.
2. PitchBook can leave prior autocomplete results visible while fetching a new
   company. The adapter waits for an exact requested-company match rather than
   merely waiting for any result card.
3. Category options mount asynchronously. The adapter waits for the exact option
   before asking Stagehand to select it.
4. The UI category is `Debt Financing`, while a row-level type can be
   `Debt Refinancing`. The adapter models these as different concepts.
5. Expanded rows contained nested tables. Descendant `td` selection mixed nested
   cells into the parent row; `:scope > td` fixed extraction, and a regression
   test preserves the rule.
6. A saved PitchBook cookie became invalid server-side. Recovery discarded only
   invalid PitchBook/Morningstar state and reused the existing browser identity
   session; no password was included in the trace.
7. Apple returned no exact Debt Refinancing rows. Returning zero with zero
   matches proved that filtering used exact row semantics rather than relabeling
   all Debt Financing rows.

## Rules for adding another site or surface

1. Record one representative happy path and terminal state.
2. Identify semantic controls and inspect all important option domains; do not
   copy coordinates.
3. Write a site-independent input/output model before automation code.
4. Split the trace at state transitions with postconditions.
5. Extract typed raw records before computing answers.
6. Make pagination/completeness explicit.
7. Test at least one new entity, new option, empty result, missing value, and
   awkward case not present in the demonstration.
8. Save result, screenshot, and Stagehand action log for every run.
9. Promote a workflow to an MCP tool only when its schema represents a durable
   user intent. Keep page mechanics private.

## Context-window policy

Gemma 4 26B A4B supports a native 256K-token context, but CollarAI currently
configures Hermes for 128K (`131072`). Keep 128K as the default: the latest ten
result files total about 48 KB, and the operational data lives in evidence
storage rather than accumulating forever in one chat.

Use a fresh agent session for independent jobs. Evaluate a 256K profile only if
telemetry shows frequent context compression, P95 prompts approaching roughly
50K tokens, or a demonstrated accuracy gain on long research sessions. A larger
window increases KV-cache memory and prefill cost and must be enabled in both
Hermes and the inference server; changing only the Hermes YAML is insufficient.

## Production authentication policy

The proof of concept uses a human-owned Chrome profile, Duke SSO, scoped
PitchBook cookies in the operating-system keychain, and a local loopback CDP
connection. Its optional stored Duke username/password also lives in the
operating-system keychain, outside the model and project files. That is
appropriate only for the authorized POC.

For production, use this order of preference:

1. Vendor-supported API, scheduled data feed, or official AI connector under a
   commercial agreement.
2. For UI-only gaps, obtain explicit unattended-automation/RPA support and a
   dedicated non-human identity from the vendor.
3. Keep secrets and sessions in an authentication broker, outside the LLM. Give
   the model only opaque session handles.
4. Run an isolated browser worker/profile per customer or tenant, with encrypted
   storage, short-lived sessions, rotation, revocation, audit logs, rate limits,
   and health checks.
5. Treat CAPTCHA or repeated MFA as a stop/re-enrollment signal. Do not build a
   bypass. If the vendor offers no supported noninteractive identity, the surface
   is not suitable for millions of unattended jobs.

A university user SSO session is bound to a person and institutional entitlement;
it can expire or be revoked and is not a production service identity. Saving a
password in an environment variable does not fix that architecture and exposes
the credential to processes, diagnostics, and accidental logging.
