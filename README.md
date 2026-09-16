# Composio Toolkit Research

An evidence-backed, resumable research pipeline for deciding whether 100 software products are viable AI-agent toolkits. It researches official sources, extracts structured claims, verifies cited claims independently, retries weak evidence, and produces audit-ready analysis and a static case study.

## Pipeline

`source list → official-first retrieval → structured extraction → claim verification → targeted pass-two retry → Composio catalog check → human audit → analysis → HTML report`

Pass-one and pass-two files are frozen independently. A retry never overwrites pass-one evidence or predictions.

## Setup

```powershell
uv sync --all-groups
Copy-Item .env.example .env
```

Set these values in `.env`:

- `OPENAI_API_KEY` — required for extraction and verification.
- `SEARCH_PROVIDER` and `SEARCH_API_KEY` — required for official-first search (`serper` or `tavily`).
- `COMPOSIO_API_KEY` — optional read-only catalog enrichment. An unavailable or invalid key produces `unknown`, never an inferred coverage result.

## Commands

```powershell
uv run pytest
uv run python scripts/run_research.py --check-only
uv run python scripts/retrieve_sample.py
uv run python scripts/research_pilot.py
uv run python scripts/verify_one.py 21
uv run python scripts/retry_one.py 21
uv run python scripts/check_composio.py --app-id 61

# Full resumable run (external API usage)
uv run python scripts/run_research.py

uv run python scripts/create_audit_sample.py
uv run python scripts/score_audit.py path\to\completed_audit.json
uv run python scripts/analyze.py
uv run python scripts/generate_insights.py
uv run python scripts/build_report.py
```

## Output and caveats

Generated research data is intentionally ignored by Git because it may contain changing external-source results. The committed project includes a small pilot dataset only; it is not presented as a completed 100-app study. `scripts/run_research.py --check-only` is the authoritative completeness check.

Human audit templates are blank by design. Only independently completed `HumanAuditRecord` files can generate accuracy metrics.

The final static report is written to `report/index.html`; it exposes evidence links and labels partial data clearly.
