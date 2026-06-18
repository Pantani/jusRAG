"""Markdown renderer for the eval report (§24).

Turns the aggregated suite dict into a human-readable Markdown report with a
metric/threshold/pass-fail table and the ids of failing cases per family. Pure
string formatting — no I/O, no metric logic (those live in the eval modules).
"""

from __future__ import annotations

from typing import Any


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = ["# JusRAG Brasil — Eval Report", ""]
    lines += _provider_section(payload.get("provider"))
    lines += _golden_section(payload["golden"])
    lines += _gate_section(payload["gate"])
    lines += _metrics_table(payload)
    lines += _failures_section(payload["metrics"])
    lines.append("")
    return "\n".join(lines)


def _provider_section(provider: dict[str, Any] | None) -> list[str]:
    if not provider:
        return []
    return [
        "## Providers",
        "",
        f"- Embedding: **{provider.get('embedding', 'unknown')}**",
        f"- LLM: **{provider.get('llm', 'unknown')}**",
        "",
    ]


def _golden_section(golden: dict[str, Any]) -> list[str]:
    ok = "yes" if golden["meets_minimum"] else "NO"
    return [
        "## Golden dataset",
        "",
        f"- Total: **{golden['total']}** "
        f"(in-scope {golden['in_scope']}, out-of-scope {golden['out_of_scope']})",
        f"- Minimum required (v1): {golden['min_required']} — meets minimum: **{ok}**",
        "",
    ]


def _gate_section(gate: dict[str, Any]) -> list[str]:
    verdict = "PASSED" if gate["passed"] else "FAILED"
    mode = "strict (all §36 thresholds)" if gate["strict"] else "hallucination-only"
    return [
        "## Build gate (§36)",
        "",
        f"- Mode: **{mode}**",
        f"- Verdict: **{verdict}**",
        "",
    ]


_METRIC_LABELS = {
    "retrieval_recall_at_5": "retrieval_recall_at_5",
    "citation_coverage": "citation_coverage",
    "unsupported_legal_claim_rate": "unsupported_legal_claim_rate",
    "refusal_when_no_source_rate": "refusal_when_no_source_rate",
}


def _metrics_table(payload: dict[str, Any]) -> list[str]:
    metrics = payload["metrics"]
    rows = [
        metrics["retrieval"]["retrieval_recall_at_5"],
        metrics["citation"]["citation_coverage"],
        metrics["citation"]["unsupported_legal_claim_rate"],
        metrics["answer"]["refusal_when_no_source_rate"],
    ]
    names = list(_METRIC_LABELS.values())
    lines = [
        "## Metrics (§36 thresholds)",
        "",
        "| Metric | Value | Threshold | Result |",
        "| --- | --- | --- | --- |",
    ]
    for name, row in zip(names, rows, strict=True):
        result = "PASS" if row["passed"] else "FAIL"
        lines.append(f"| {name} | {row['value']:.4f} | {row['threshold']} | {result} |")
    lines += _heuristic_rows(metrics["answer"])
    lines.append("")
    return lines


def _heuristic_rows(answer: dict[str, Any]) -> list[str]:
    return [
        f"| answer_relevancy (heuristic) | {answer['answer_relevancy']['value']:.4f} | — | — |",
        f"| faithfulness (heuristic) | {answer['faithfulness']['value']:.4f} | — | — |",
    ]


def _failures_section(metrics: dict[str, Any]) -> list[str]:
    families = [
        ("Retrieval", metrics["retrieval"]["failing_case_ids"]),
        ("Citation", metrics["citation"]["failing_case_ids"]),
        ("Answer / refusal", metrics["answer"]["failing_case_ids"]),
    ]
    lines = ["## Failing cases", ""]
    any_fail = False
    for label, ids in families:
        if ids:
            any_fail = True
            lines.append(f"- **{label}**: {', '.join(ids)}")
    if not any_fail:
        lines.append("- None — all golden cases within thresholds.")
    lines.append("")
    return lines
