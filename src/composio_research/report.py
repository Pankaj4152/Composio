"""Render a self-contained, data-honest HTML case-study report."""

from html import escape
from pathlib import Path
from typing import Any

from composio_research.config import REPORT_DIR
from composio_research.analysis import load_final_records
from composio_research.schema import AppRecord
from composio_research.serialization import read_json


def _label(value: str) -> str:
    return escape(value.replace("_", " ").title())


def _distribution_cards(distribution: dict[str, Any]) -> str:
    return "".join(
        f'<div class="metric"><strong>{escape(str(count))}</strong><span>{_label(str(name))}</span></div>'
        for name, count in sorted(distribution.items())
    ) or '<p class="muted">No data available.</p>'


def _matrix(matrix: dict[str, Any], title: str) -> str:
    keys = sorted({key for row in matrix.values() if isinstance(row, dict) for key in row})
    headers = "".join(f"<th>{_label(key)}</th>" for key in keys)
    rows = "".join(
        "<tr>" + f"<th>{escape(category)}</th>" + "".join(f"<td>{row.get(key, 0)}</td>" for key in keys) + "</tr>"
        for category, row in sorted(matrix.items()) if isinstance(row, dict)
    )
    return f"<section><h2>{escape(title)}</h2><div class=\"table-wrap\"><table><thead><tr><th>Category</th>{headers}</tr></thead><tbody>{rows}</tbody></table></div></section>"


def _record_table(records: tuple[AppRecord, ...]) -> str:
    rows = []
    for record in records:
        url = next((item.url for item in record.evidence), None)
        link = f'<a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">Source</a>' if url else "—"
        rows.append(f"<tr><td>{escape(record.app)}</td><td>{escape(record.category)}</td><td>{escape(', '.join(item.value for item in record.auth_methods))}</td><td>{_label(record.credential_access.value)}</td><td>{_label(record.api_surface.value)}</td><td>{_label(record.mcp_status.value)}</td><td>{_label(record.buildability_verdict.value)}</td><td>{record.overall_confidence:.2f}</td><td>{link}</td></tr>")
    return "".join(rows) or '<tr><td colspan="9">No frozen records available.</td></tr>'


def _scorecard_html(audit_dir: Path = Path("data/audit")) -> str:
    path = audit_dir / "scorecard.json"
    if not path.exists():
        return '<p class="muted">No completed human audit has been supplied yet. Field-level and paired pass-one/pass-two accuracy will appear here after independent review.</p>'
    try:
        data = read_json(path)
        metrics = data.get("metrics", [])
        if not metrics:
            return '<p class="muted">Scorecard data is empty.</p>'
        rows = "".join(
            f"<tr><td>{_label(m.get('sample_type', ''))}</td><td>{_label(m.get('field', ''))}</td><td>Pass {m.get('pass_number', 1)}</td><td>{m.get('correct', 0)} / {m.get('checked', 0)}</td><td><strong>{m.get('accuracy', 0)*100:.1f}%</strong></td></tr>"
            for m in metrics
        )
        return f'<div class="table-wrap"><table><thead><tr><th>Sample Type</th><th>Field</th><th>Pass</th><th>Correct / Checked</th><th>Accuracy</th></tr></thead><tbody>{rows}</tbody></table></div>'
    except Exception as err:
        return f'<p class="muted">Could not load scorecard: {escape(str(err))}</p>'


def render_report(analysis: dict[str, Any], insights: dict[str, Any], *, records: tuple[AppRecord, ...] = ()) -> str:
    """Render only supplied computed values; no dataset-size or outcome is hard-coded."""
    count = int(analysis.get("record_count", 0))
    buildability = analysis.get("buildability_distribution", {})
    if not isinstance(buildability, dict):
        buildability = {}
    findings = insights.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    findings_html = "".join(
        "<article class=\"finding\">"
        f"<h3>{escape(str(item.get('headline', 'Untitled finding')))}</h3>"
        f"<p>{escape(str(item.get('detail', '')))}</p>"
        f"<small>Supporting app IDs: {escape(', '.join(map(str, item.get('supporting_app_ids', []))) or 'none')}</small>"
        "</article>"
        for item in findings if isinstance(item, dict)
    ) or '<p class="muted">Insights will appear after analysis runs.</p>'
    opportunity = analysis.get("opportunities", {})
    if not isinstance(opportunity, dict):
        opportunity = {}
    opportunity_html = "".join(
        f'<div class="metric"><strong>{len(opportunity.get(key, [])) if isinstance(opportunity.get(key, []), list) else 0}</strong><span>{label}</span></div>'
        for key, label in (
            ("easy_build", "Easy build"),
            ("strategic_outreach", "Strategic outreach"),
            ("investigate_or_deprioritize", "Investigate / deprioritize"),
            ("api_accessible_no_mcp", "Accessible API, no MCP"),
        )
    )
    completeness_note = (
        "This is a complete 100-app analysis." if count == 100
        else f"This is a partial analysis of {count} frozen records. It is not presented as a 100-app result."
    )
    scorecard_section = _scorecard_html()
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Integration Intelligence Case Study</title><style>
:root{{color-scheme:light;--ink:#172033;--muted:#62708a;--line:#dce3ef;--bg:#f7f9fc;--blue:#3157d5}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 Inter,system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:48px 24px 80px}}h1{{font-size:clamp(2.2rem,5vw,4rem);line-height:1.06;margin:.2em 0}}h2{{margin-top:42px}}.eyebrow{{color:var(--blue);font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-size:.78rem}}.muted,small{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}}.metric,.finding{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px}}.metric strong{{font-size:1.8rem;display:block}}.metric span{{color:var(--muted);font-size:.9rem}}.findings{{display:grid;gap:12px}}.finding h3{{margin:0 0 .4em}}.finding p{{margin:.2em 0}}.table-wrap{{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:12px}}table{{border-collapse:collapse;width:100%;min-width:640px}}th,td{{text-align:left;padding:12px;border-bottom:1px solid var(--line)}}th{{background:#f2f5fa}}.rule{{background:#edf2ff;border-left:4px solid var(--blue);padding:16px;border-radius:4px}}@media print{{body{{background:#fff}}main{{padding:20px}}}}</style></head>
<body><main><header><div class="eyebrow">Composio · Integration intelligence</div><h1>Evidence-backed build vs outreach map</h1><p class="muted">{escape(completeness_note)}</p></header>
<section><h2>Executive summary</h2><div class="grid"><div class="metric"><strong>{count}</strong><span>Frozen records analyzed</span></div>{_distribution_cards(buildability)}</div></section>
<section><h2>What the data says</h2><div class="findings">{findings_html}</div></section>
<section><h2>Opportunity sets</h2><p class="rule">Rules are deterministic: easy build requires a useful, moderate/broad API, self-serve access, and no hard blocker. Outreach requires a useful API plus a commercial or approval gate.</p><div class="grid">{opportunity_html}</div></section>
<section><h2>Category × buildability</h2>{_matrix(analysis.get('category_verdict_matrix', {}) if isinstance(analysis.get('category_verdict_matrix', {}), dict) else {}, 'Category × buildability')}</section>
<section><h2>Category × access</h2>{_matrix(analysis.get('category_access_matrix', {}) if isinstance(analysis.get('category_access_matrix', {}), dict) else {}, 'Category × access')}</section>
<section><h2>Evidence-backed app records</h2><input id="app-filter" type="search" placeholder="Search app, category, access, verdict…"><div class="table-wrap"><table id="app-table"><thead><tr><th>App</th><th>Category</th><th>Auth</th><th>Access</th><th>API</th><th>MCP</th><th>Verdict</th><th>Confidence</th><th>Evidence</th></tr></thead><tbody>{_record_table(records)}</tbody></table></div></section>
<section><h2>How the agent works</h2><p class="rule">Research → Evidence → Verify → Targeted retry → Human audit → Analysis. Automated steps preserve raw artifacts; human review is independent and does not overwrite frozen predictions.</p></section>
<section><h2>Verification proof</h2>{scorecard_section}</section>
<section><h2>Reproducibility</h2><p>Generate frozen data, then run <code>uv run python scripts/analyze.py</code>, <code>uv run python scripts/generate_insights.py</code>, and <code>uv run python scripts/build_report.py</code>.</p></section>
</main><script>const f=document.getElementById('app-filter');if(f)f.addEventListener('input',()=>{{const q=f.value.toLowerCase();document.querySelectorAll('#app-table tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));}});</script></body></html>"""


def build_report(
    analysis_path: Path = REPORT_DIR / "analysis.json",
    insights_path: Path = REPORT_DIR / "insights.json",
    output_path: Path = REPORT_DIR / "index.html",
) -> Path:
    analysis = read_json(analysis_path)
    insights = read_json(insights_path)
    if not isinstance(analysis, dict) or not isinstance(insights, dict):
        raise ValueError("Analysis and insight artifacts must both be JSON objects.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(analysis, insights, records=load_final_records()), encoding="utf-8")
    return output_path
