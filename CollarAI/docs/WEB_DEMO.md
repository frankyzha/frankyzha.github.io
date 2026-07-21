# CollarAI web demo boundary

The `/demo/` page is static and safe to publish on GitHub Pages. The browser worker is not. It owns
an authenticated PitchBook session and remains a separate, access-controlled service. For this POC,
Tailscale Funnel provides HTTPS ingress while the API enforces its own bearer key.

## Request path

```text
Browser → POST /api/query → Duke Gemma tool call → local schema validation
        → FinancingAnalysisRequest
        → BrowserService → Stagehand/PitchBook → typed result → Markdown response
```

`QueryRouter` is semantic, but its output boundary is deterministic. Gemma can select exactly one
declared capability; Pydantic rejects unknown tools, extra fields, invalid enum values, and malformed
arguments before browsing. The model can reject three classes:

- `irrelevant`: not a supported company-financing question;
- `incomplete`: missing a company, subject, or aggregate;
- `unsupported`: finance-related, but outside the demonstrated adapter.

The model receives the question and typed capability schemas—not a screenshot, DOM, password, or
arbitrary browser controls. The response contains an
aggregate, coverage counts, timing, and a run ID—not credentials or raw session state.

## Local proof of concept

Start the API:

```bash
uv run --no-editable collarai-api
```

Serve the Jekyll site at `http://127.0.0.1:4000` and open `/demo/`. The page automatically targets
`http://127.0.0.1:8787` on localhost.

## Private hosted proof of concept

Provision or resume the 128K Gemma worker on Duke. This creates one random inference token, stores it
in macOS Keychain and a mode-0600 remote file, copies the Slurm definition, and avoids duplicate jobs:

```bash
PYTHONPATH=src uv run --no-editable python scripts/provision_duke_inference.py
```

The Slurm job uses one A5000, binds its authenticated `llama.cpp` server to the compute-node network,
and requeues before its short backfill lease expires. Rotate the inference token only when necessary
with `--rotate-token`; rotation restarts that job.

Create the invitation key once. It is stored in the operating system vault and printed only in your
own terminal:

```bash
uv run --no-editable collarai-access create
```

Install Tailscale once:

```bash
brew install tailscale
```

The checked-in installer registers three per-user macOS services: the loopback API, a supervised SSH
tunnel to the active Duke Slurm worker, and a userspace Tailscale daemon. It stores runtime state and
logs under the ignored `.collarai/` directory; it does not place a Duke password, PitchBook cookie,
inference token, or demo access key in a plist.

```bash
uv run --no-sync python scripts/install_macos_services.py
```

If this is the machine's first run, the installer prints the exact `tailscale ... up` command. Open
its login link, authenticate in the browser, and run the installer once more. After that, launchd
restarts the local services automatically when needed. The tunnel discovers the node running the
`collarai-gemma` Slurm job and rediscovers it after a requeue.

Verify the public boundary without exposing the invitation key:

```bash
curl https://mac.tail986752.ts.net/health
curl -i -X POST https://mac.tail986752.ts.net/api/query \
  -H 'Content-Type: application/json' \
  --data '{"query":"What is Nvidia IPO amount?"}'
```

The second request must return `401`. Visitors paste the CollarAI invitation key—not a Tailscale
credential—into the page. The key is retained only in `sessionStorage` for that browser tab and sent
over HTTPS as a bearer token.

Rotate or revoke access without touching PitchBook authentication:

```bash
uv run --no-editable collarai-access rotate
uv run --no-editable collarai-access forget
```

## Publishing safely

1. Keep the browser worker bound to loopback. The CLI refuses a public bind unless it is explicitly
   overridden; Tailscale Funnel makes the outbound connection.
2. Require the separate CollarAI bearer key in addition to the HTTPS tunnel.
3. Restrict access to approved demo users and add rate, concurrency, and spend limits at the proxy.
4. Set `COLLAR_API_ORIGINS=https://frankyzha.github.io` on the API.
5. Set `collarai_api_url` in the website `_config.yml` to the protected HTTPS origin.
6. Verify authentication expiry, worker health, and an explicit revocation path before sharing it.

A static JavaScript token is not a secret. The invitation key must be entered by the visitor and
must never be placed in this repository or browser bundle. Never expose a PitchBook, Duke,
Tailscale, or API credential through GitHub Pages.
