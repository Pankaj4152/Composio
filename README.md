# Integration Intelligence for Composio

An evidence-first research agent for deciding which requested SaaS products can become reliable AI-agent toolkits today, which require commercial outreach, and which should be deprioritized.

The project turns the supplied 100-app assignment into a reproducible pipeline instead of a hand-maintained spreadsheet. It records claim-level official evidence, independently verifies it, retries only weak claims, and produces an auditable dataset and a self-contained case-study page.

## Submission deliverables

| Deliverable | Location | Purpose |
| --- | --- | --- |
| 100-app source list | `data/apps.input.json` | Editable input data: 100 unique apps across 10 categories. |
| Research pipeline | `src/composio_research/` | Official-first retrieval, structured extraction, verification, retry, and batch orchestration. |
| Evidence artifacts | `data/logs/` | Saved retrieval text, model outputs, verifier decisions, retry reasons, and terminal errors. |
| Frozen datasets | `data/pass1/`, `data/pass2/` | Pass-one and pass-two outputs are separate and never silently overwritten. |
| Human-audit workflow | `scripts/create_audit_sample.py`, `scripts/score_audit.py` | Stratified audit tasks and field-level accuracy measurement. |
| Analysis | `scripts/analyze.py`, `scripts/generate_insights.py` | Deterministic distributions, opportunity sets, and evidence-backed findings. |
| Case study | `report/index.html` | Self-contained, searchable static HTML report. |

## The workflow

```text
100-app source list
  -> official-first retrieval
  -> schema-constrained research extraction
  -> claim-level evidence verification
  -> targeted pass-two retry for weak claims
  -> read-only Composio catalog check
  -> independent human audit
  -> Product Ops analysis
  -> static HTML case study
```

### Research and evidence rules

- The supplied app hint is attempted before web search.
- Official documentation is ranked ahead of help pages, product pages, GitHub, and secondary sources.
- The extractor can cite only URLs that were fetched and saved in its source context.
- The verifier receives one claim and only that claim's cited source text; it cannot validate itself using the original research context.
- Unsupported, conflicting, unverifiable, or low-confidence critical claims generate field-specific retry queries.
- Pass one remains frozen. Pass two has separate retrieval and raw-model artifacts.

### Buildability decisions

Each record captures the app/category/one-liner, auth methods, credential access path, API surface and breadth, MCP status, buildability verdict, blocker, confidence, and claim-level evidence.

The decision states are operational rather than subjective:

- `build_now`: usable API and accessible path today.
- `build_with_friction`: technically workable, with practical setup friction.
- `outreach`: useful API exists but commercial, partner, admin, or approval work is required.
- `blocked`: no viable public agent-integration surface or a hard blocker.

## Requirements coverage

| Assignment requirement | Implementation |
| --- | --- |
| Research 100 heterogeneous apps with an agent | Resumable bounded-concurrency runner: `scripts/run_research.py`. |
| Capture auth, access/gating, API, MCP, buildability, and evidence | Strict Pydantic `AppRecord` schema and official-source extraction. |
| Find patterns, not only rows | Deterministic distributions, category matrices, and transparent opportunity sets. |
| Verify accuracy | Per-claim verifier, deterministic consistency checks, targeted retry, and independent audit scaffold. |
| Use Composio where appropriate | Current `composio` SDK read-only toolkit-catalog cross-check with conservative matching. |
| One self-explanatory case study | Static responsive report with summary, findings, matrices, workflow, and searchable evidence table. |

## Setup

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --all-groups
Copy-Item .env.example .env
```

Configure `.env`:

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5-mini
SEARCH_PROVIDER=serper
SEARCH_API_KEY=
COMPOSIO_API_KEY=
MAX_CONCURRENCY=5
```

- `OPENAI_API_KEY` is required for extraction and verification.
- `SEARCH_PROVIDER` and `SEARCH_API_KEY` are required for full official-first retrieval.
- `COMPOSIO_API_KEY` is optional enrichment. Missing or invalid catalog access is represented as `unknown`; coverage is never guessed.

## Run the project

```powershell
# Quality checks and current dataset completeness; no external calls.
uv run pytest
uv run python scripts/run_research.py --check-only

# Pilot the workflow on deliberately different apps.
uv run python scripts/retrieve_sample.py
uv run python scripts/research_pilot.py
uv run python scripts/verify_one.py 21
uv run python scripts/retry_one.py 21

# Read-only Composio catalog enrichment.
uv run python scripts/check_composio.py --app-id 61

# Full 100-app run. Safe to resume after interruption.
uv run python scripts/run_research.py

# Human audit, analysis, and case-study generation.
uv run python scripts/create_audit_sample.py
uv run python scripts/score_audit.py path\to\completed_audit.json
uv run python scripts/analyze.py
uv run python scripts/generate_insights.py
uv run python scripts/build_report.py
```

Open `report/index.html` after the final command.

## Auditability and limitations

- Generated data is intentionally not committed because source pages and model outputs change over time.
- The repository currently contains three frozen pilot records (Slack, Shopify, and GitHub), not a finished 100-app result. The report labels this as partial data; it does not claim 100-app conclusions.
- `scripts/run_research.py --check-only` is the authoritative completion check. A valid completed run has 100 pass-one records or explicit terminal-error records, plus pass two for flagged items.
- Human-audit templates intentionally have blank ground truth. Accuracy numbers appear only after an independent reviewer completes them.
- The currently configured Composio key was rejected by the live catalog API. Replace it with a valid project key before relying on Composio coverage enrichment.

## Quality gates

The repository currently has 72 automated tests covering source-data validation, serialization, retrieval ranking, strict Responses schemas, extraction constraints, verification, retry policy, Composio matching, batch completeness, audit metrics, analysis, insights, and report rendering.
