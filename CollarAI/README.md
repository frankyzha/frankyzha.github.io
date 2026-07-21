# CollarAI Browser MCP

A small Python service that turns high-level market-data questions into deterministic, auditable
browser workflows. Hermes sees four typed MCP tools—not arbitrary mouse and keyboard access—and
Stagehand v3 performs repeatable actions against a persistent signed-in Chrome profile.

The repository includes a complete login-gated synthetic market application so the whole path can
be tested without touching PitchBook. The PitchBook financing workflow is implemented from an
authorized human trace; company screening remains a separate workflow to demonstrate.

## Mental model

```text
User request
    ↓
Hermes + local model              reasoning, parameter translation
    ↓ MCP: analyze_financing_transactions(...)
CollarAI Browser MCP              typed contract, policy, session, evidence
    ↓
Site adapter                      reusable sequence for one platform
    ↓
Stagehand v3                      deterministic actions over direct CDP
    ↓ only when a known action fails and the local model is healthy
Stagehand observe                 semantic locator discovery and cached repair
    ↓
Persistent browser profile       cookies/session; human handles MFA/CAPTCHA
```

MCP is the tool protocol between Hermes and this service. It is analogous to a typed local API for
an agent: Python annotations generate JSON Schema, Hermes supplies validated arguments, and the
server returns structured output. It does not contain the browser implementation itself.

## Why this split

- The model reasons once at the boundary; it does not rediscover every click on every run.
- Stagehand executes known actions immediately after the page is ready.
- Each platform is isolated in a `SiteAdapter`; adding a site does not change the MCP contract.
- Stagehand also owns semantic recovery. Recovered actions are locally cached, while the common path
  remains model-free.
- A small CDP layer performs typed inspection, table extraction, cookies, accessibility snapshots,
  and screenshots. There is no Playwright dependency.
- Login state is kept in a per-platform Chromium profile. Passwords do not enter prompts or traces.
- Completed runs save `result.json`, `final.png`, and `stagehand.json` under
  `.collarai/runs/<run-id>/`; authentication is deliberately not traced.
- Returned rows are checked against the requested constraints before Hermes can cite them.

## Run the complete toy example

Requirements: Python 3.10+, `uv`, and Google Chrome or Chromium.

```bash
cd CollarAI
uv sync --extra dev --no-editable
```

Terminal 1 starts the authenticated synthetic data site:

```bash
uv run --no-editable collarai-toy
```

Terminal 2 runs the complete screen through a real headless Chromium session:

```bash
uv run --no-editable pytest tests/test_browser_e2e.py
```

The built-in credentials are `demo@collarai.local` / `demo`. The toy workflow runs this screen:

> Find US enterprise-software companies founded after 2020, with Series A or Series B funding and
> less than $50 million raised.

The adapter signs in, applies every typed filter, extracts the resulting rows, and checks them
against the request. The synthetic companies are test fixtures, not factual market-data claims.
The live PitchBook company screener remains intentionally unimplemented.

Run all checks, including the real headless-browser test:

```bash
uv run --no-editable ruff check .
uv run --no-editable pytest
```

## Run the query API and website demo

The web API keeps one browser service warm and rejects irrelevant, incomplete, or unsupported
questions before a browser session starts:

```bash
uv run --no-editable collarai-api
```

It listens on `http://127.0.0.1:8787` by default. The website's `/demo/` page automatically uses
that address during a localhost preview. Valid questions are routed into
`FinancingAnalysisRequest`; results are returned as structured fields plus safe Markdown and LaTeX.

GitHub Pages hosts only the static interface. A live deployment requires a separate authenticated
HTTPS proxy in front of this API and a `collarai_api_url` value in the website `_config.yml`.
Do not expose the Duke/PitchBook browser worker directly to the public internet. See
`docs/WEB_DEMO.md` for the deployment boundary.

The hosted POC uses a Tailscale Funnel HTTPS endpoint plus a bearer key stored in macOS Keychain.
Manage that invitation key locally with `collarai-access create|show|rotate|forget`; it is never
committed or embedded in the page.

## Connect Hermes

Hermes supports local stdio MCP servers and per-server tool allowlists. Merge the blocks from
`hermes.example.yaml` into `~/.hermes/config.yaml`, replace the absolute path, inference endpoint,
and exact `/v1/models` model ID, then run:

```bash
hermes mcp test collarai
hermes chat
```

If Hermes is already running, use `/reload-mcp`. A direct CLI alternative is:

```bash
hermes mcp add collarai --command /absolute/path/to/CollarAI/.venv/bin/collarai-mcp
```

The example declares a 131,072-token model window, medium reasoning as the default, and explicit
tool-use enforcement for the local Gemma model. The inference server and Hermes must agree on the
context window; configuring 128K in Hermes does not enlarge a server launched with a smaller limit.

The bundled Hermes skill in `skills/company-screening/SKILL.md` is thin by design: it teaches the
model how to map language such as “after 2020” to the schema and how to handle a human checkpoint.
Reusable speed and reliability live in Python, not in that prompt.

## MCP surface

`analyze_financing_transactions(request)` extracts a company's Debt Financing or Equity Financing
table, optionally filters exact deal types, and deterministically computes sum/average Amount or
latest/minimum/maximum/average Raised to Date. `screen_companies(screen)` performs structured
discovery. Both return one of these run states:

- `complete`: verified companies and evidence are available.
- `needs_human`: leave the browser open and ask the user to finish login/MFA/CAPTCHA.
- `needs_configuration`: the platform adapter needs an authenticated trace.
- `failed`: inspect the evidence screenshot and Stagehand action log.

`get_browser_session_status(platform)` inspects the persistent session.

`get_browser_run(run_id)` reloads an earlier result without browsing again.

No generic `click`, `type`, or `evaluate JavaScript` tool is exposed to Hermes. Those low-level
capabilities stay inside reviewed adapters.

## Native Stagehand v3 execution

`BrowserSessionManager` starts one local Stagehand server and keeps one session per platform warm.
For a known operation, adapters pass a structured Stagehand action containing an XPath, method,
arguments, and intent. No LLM call is made. Dynamic list items are first identified and validated
through CDP, marked with a run-scoped attribute, and then clicked by Stagehand.

If a known action fails, CollarAI checks the configured local model's `/models` endpoint. Only when
it is healthy does `Stagehand.observe()` semantically discover a replacement action; a successful
repair is cached. This avoids multi-second provider retries when Gemma is offline. Extraction and
arithmetic remain deterministic even when recovery found a locator.

## PitchBook authentication, capture, and replay

Store the Duke credential once in the operating system vault, without putting it in a project file,
environment variable, trace, or model prompt:

```bash
uv run --no-editable collarai-pitchbook credentials
```

Then authenticate:

```bash
uv run --no-editable collarai-pitchbook auth
```

The command opens a dedicated normal Google Chrome process at
`https://my.pitchbook.com/`. It enters the saved password only after verifying the page host is
exactly `shib.oit.duke.edu`. CAPTCHA, unexpected hosts, and MFA remain explicit checkpoints. Do not
send credentials in chat. Browser authentication remains in the permission-restricted
`.collarai/profiles/` directory, and the password remains in the OS vault. After a successful run,
PitchBook-scoped session cookies are also stored in that vault and can reuse a still-valid session
after a browser restart. PitchBook may still invalidate it server-side, in which case SSO runs again.
Duke SSO cookies are not copied. Leave Chrome open.

Remove the saved secret at any time with:

```bash
uv run --no-editable collarai-pitchbook forget-credentials
```

Then attach the local recorder to that same live Chrome process:

```bash
uv run --no-editable collarai-pitchbook capture
```

Chrome is not relaunched. Stagehand attaches to its loopback-only Chrome DevTools Protocol endpoint
and observes human interaction in the existing tab. This preserves the exact browser process that
passed Cloudflare; it does not disable or bypass the verification.

Open Nvidia, navigate to its recorded transactions, filter to Debt Refinancing, and expose every
matching row and amount. Wait until the final table is rendered, return to the terminal, and press
Enter. Do not close Chrome yourself. The recorder saves a structured event trace, final
accessibility snapshot, and screenshot with mode `0600` under `.collarai/captures/`, then detaches
while leaving the dedicated Chrome process and its session open.

The recorded Nvidia trace has been converted into a parameterized adapter. Replay the real workflow
against the saved profile with:

```bash
uv run --no-editable collarai-demo "What is Nvidia's IPO amount?"
```

The query router converts the supported intent to a typed request. The adapter searches for the
supplied company, validates the selected profile, opens Deals, applies the financing category and
USD currency, walks accessible pagination, parses the semantic table, and computes the aggregate in
Python. It does not use export or bulk download.

Run the ten live generalization checks through one warm Stagehand session:

```bash
uv run --no-editable python scripts/validate_pitchbook_queries.py
```

The script contains request schemas, not expected values or answer fixtures. Each question produces
a fresh evidence directory.

The trace teaches page structure and state transitions; it is not treated as a macro or executable
code. We turn it into reviewed adapter code that parameterizes company name and transaction type,
handles pagination, verifies the applied filter, and returns complete typed rows.

## Layout

```text
src/collarai/
  mcp_server.py       four typed tools and managed lifecycle
  web_api.py          narrow HTTP query boundary for the website demo
  query.py            deterministic language routing and answer presentation
  service.py          policy → session → adapter → evidence orchestration
  browser.py          warm native Stagehand sessions
  stagehand_browser.py Stagehand actions plus deterministic CDP inspection
  chrome.py           normal Chrome lifecycle and loopback-only CDP attachment
  adapters/           per-site deterministic workflows
  recording.py        human-action trace and final-page evidence capture
  evidence.py         atomic structured results and run artifacts
  toy/app.py          authenticated synthetic market application
tests/
  test_browser_e2e.py real Chromium login/screen/evidence test
scripts/
  validate_pitchbook_queries.py ten-query live regression runner
```

The MCP SDK is pinned to stable v1 (`mcp<2`) because v2 is still pre-release as of this project
version. The upper bound makes a future stable v2 migration deliberate instead of accidental.
