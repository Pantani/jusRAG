"""Eval orchestrator + build gate (§24, §36). Entry point for ``make eval``.

Builds the offline harness, runs the three eval families over the golden dataset in a
single pass, aggregates every §36 metric, writes a JSON + Markdown report, prints a
summary, and **fails the build** (non-zero exit) when a gate threshold is violated.

Gate semantics (§36, and the rule "make eval may fail the build"):

* The hallucination gate is *always* enforced: ``unsupported_legal_claim_rate > 0.05``
  exits non-zero. This is the non-negotiable "don't hallucinate" gate (§2.1).
* The remaining §36 thresholds — ``retrieval_recall_at_5 ≥ 0.80``,
  ``citation_coverage ≥ 0.90``, ``refusal_when_no_source_rate ≥ 0.90`` — are enforced
  by default too, so a regression in any of them breaks CI. Set ``EVAL_GATE_STRICT=0``
  to enforce *only* the hallucination gate (e.g. while a dependent module is being
  fixed); the report still records every pass/fail regardless.

Provider modes (CI vs opt-in):

* ``python -m packages.evals.run_all`` (no flag) — fake providers, no network, no
  Qdrant. This is the CI path (``make eval``) and stays deterministic.
* ``--provider={fake,openai,local}`` — selects the embedding provider; for openai
  and local also pairs a sensible default LLM (openai → ``openai``; local → ``ollama``).
  Override the LLM independently with ``--llm-provider={fake,openai,ollama}``.
  Used by ``make eval-real``; requires a running Qdrant collection whose vector size
  matches the chosen embedding provider (pre-flight aborts on mismatch).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.evals.answer_eval import (
    AnswerEvalReport,
    answer_cases_for_citation,
    evaluate_answers,
    produce_answers,
)
from packages.evals.citation_eval import CitationEvalReport, evaluate_citations
from packages.evals.golden import GoldenStats, golden_stats, load_golden
from packages.evals.harness import EvalHarness, build_harness, build_real_harness
from packages.evals.report import render_markdown
from packages.evals.retrieval_eval import RetrievalEvalReport, evaluate_retrieval

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GENERATED = _REPO_ROOT / "data" / "generated"
REPORT_JSON = _GENERATED / "eval_report.json"
REPORT_MD = _GENERATED / "eval_report.md"

MIN_GOLDEN = 30

# Default LLM paired with each embedding provider when --llm-provider is omitted.
_DEFAULT_LLM_FOR_EMBEDDING = {
    "fake": "fake",
    "openai": "openai",
    "local": "ollama",
}


@dataclass(frozen=True)
class ProviderSelection:
    """Resolved (embedding, llm) provider pair used by the eval suite."""

    embedding: str
    llm: str

    @property
    def label(self) -> str:
        return f"embedding={self.embedding}, llm={self.llm}"


@dataclass(frozen=True)
class EvalSuiteResult:
    """The full aggregated suite: every §36 metric + headcount + gate verdict."""

    golden: GoldenStats
    retrieval: RetrievalEvalReport
    citation: CitationEvalReport
    answer: AnswerEvalReport
    provider: ProviderSelection = ProviderSelection(embedding="fake", llm="fake")

    @property
    def gate_checks(self) -> list[tuple[str, bool, bool]]:
        """(name, passed, always_enforced) for each §36 gate."""

        return [
            ("retrieval_recall_at_5", self.retrieval.recall_passed, False),
            ("citation_coverage", self.citation.coverage_passed, False),
            ("unsupported_legal_claim_rate", self.citation.unsupported_passed, True),
            ("refusal_when_no_source_rate", self.answer.refusal_passed, False),
        ]

    def gate_passed(self, *, strict: bool) -> bool:
        """Build verdict. Strict: every gate. Non-strict: only the hallucination gate."""

        return all(
            passed for _, passed, always in self.gate_checks if strict or always
        )

    def as_dict(self, *, strict: bool) -> dict[str, Any]:
        return {
            "provider": {
                "embedding": self.provider.embedding,
                "llm": self.provider.llm,
            },
            "golden": {
                "total": self.golden.total,
                "in_scope": self.golden.in_scope,
                "out_of_scope": self.golden.out_of_scope,
                "min_required": MIN_GOLDEN,
                "meets_minimum": self.golden.total >= MIN_GOLDEN,
            },
            "gate": {
                "strict": strict,
                "passed": self.gate_passed(strict=strict),
                "checks": [
                    {"metric": name, "passed": passed, "always_enforced": always}
                    for name, passed, always in self.gate_checks
                ],
            },
            "metrics": {
                "retrieval": self.retrieval.as_dict(),
                "citation": self.citation.as_dict(),
                "answer": self.answer.as_dict(),
            },
        }


def run_suite(
    harness: EvalHarness | None = None,
    *,
    provider: ProviderSelection | None = None,
) -> EvalSuiteResult:
    """Run every eval over the golden set in a single pipeline pass."""

    harness = harness or build_harness()
    questions = load_golden()

    retrieval = evaluate_retrieval(harness, questions)
    produced = produce_answers(harness, questions)
    answer = evaluate_answers(harness, questions, produced=produced)
    citation = evaluate_citations(answer_cases_for_citation(harness, produced))

    return EvalSuiteResult(
        golden=golden_stats(questions),
        retrieval=retrieval,
        citation=citation,
        answer=answer,
        provider=provider or ProviderSelection(embedding="fake", llm="fake"),
    )


def write_reports(result: EvalSuiteResult, *, strict: bool) -> None:
    _GENERATED.mkdir(parents=True, exist_ok=True)
    payload = result.as_dict(strict=strict)
    REPORT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    REPORT_MD.write_text(render_markdown(payload), encoding="utf-8")


def _print_summary(result: EvalSuiteResult, *, strict: bool) -> None:
    print(f"Provider: {result.provider.label}")
    g = result.golden
    print(f"Golden questions: {g.total} (in-scope {g.in_scope}, out-of-scope {g.out_of_scope})")
    ret, cit, ans = result.retrieval, result.citation, result.answer
    rows = [
        ("retrieval_recall_at_5", ret.recall_at_k, 0.80, ret.recall_passed),
        ("citation_coverage", cit.citation_coverage, 0.90, cit.coverage_passed),
        (
            "unsupported_legal_claim_rate",
            cit.unsupported_legal_claim_rate,
            0.05,
            cit.unsupported_passed,
        ),
        ("refusal_when_no_source_rate", ans.refusal_when_no_source_rate, 0.90, ans.refusal_passed),
    ]
    for name, value, threshold, passed in rows:
        mark = "PASS" if passed else "FAIL"
        print(f"  [{mark}] {name} = {value:.4f} (threshold {threshold})")
    verdict = "PASSED" if result.gate_passed(strict=strict) else "FAILED"
    mode = "strict" if strict else "hallucination-only"
    print(f"Gate ({mode}): {verdict}")
    print(f"Report: {REPORT_JSON} | {REPORT_MD}")


def _strict_mode() -> bool:
    return os.environ.get("EVAL_GATE_STRICT", "1") != "0"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="run_all", description=__doc__)
    parser.add_argument(
        "--provider",
        choices=["fake", "openai", "local"],
        default=None,
        help=(
            "Embedding provider for the eval. Default (omitted): fake — offline, "
            "deterministic, CI baseline (make eval). Real values opt into the live "
            "Qdrant + provider stack (make eval-real)."
        ),
    )
    parser.add_argument(
        "--llm-provider",
        choices=["fake", "openai", "ollama"],
        default=None,
        help="LLM provider override; defaults pair to --provider (openai→openai, local→ollama).",
    )
    return parser.parse_args(argv)


def _resolve_providers(args: argparse.Namespace) -> ProviderSelection:
    """Pick (embedding, llm). Default (no flag) preserves the fake CI baseline."""

    if args.provider is None and args.llm_provider is None:
        return ProviderSelection(embedding="fake", llm="fake")
    embedding = args.provider or "fake"
    llm = args.llm_provider or _DEFAULT_LLM_FOR_EMBEDDING[embedding]
    return ProviderSelection(embedding=embedding, llm=llm)


def _apply_provider_env(selection: ProviderSelection) -> None:
    """Mirror the CLI choice into env so settings/selectors see the same provider."""

    os.environ["EMBEDDING_PROVIDER"] = selection.embedding
    os.environ["LLM_PROVIDER"] = selection.llm
    # get_settings() is lru_cache'd — invalidate so the new env is observed.
    from packages.config.settings import get_settings as _gs

    _gs.cache_clear()


def _check_provider_prereqs(selection: ProviderSelection) -> None:
    """Fail fast with a clear message when a real provider is unusable."""

    if selection.embedding == "openai" or selection.llm == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit(
                "OPENAI_API_KEY is not set; cannot run eval with provider 'openai'. "
                "Export it (e.g. `export OPENAI_API_KEY=sk-...`) or pick another provider."
            )
    if selection.llm == "ollama":
        _check_ollama_reachable()


def _check_ollama_reachable() -> None:
    from packages.config.settings import get_settings

    base_url = get_settings().ollama_base_url.rstrip("/")
    try:
        import httpx

        httpx.get(f"{base_url}/api/tags", timeout=2.0)
    except Exception as exc:  # noqa: BLE001 — surface any transport failure
        raise SystemExit(
            f"Ollama is not reachable at {base_url} ({exc}). "
            "Start it (e.g. `make up` with the local overlay) or pick another LLM provider."
        ) from exc


def _preflight_qdrant(selection: ProviderSelection) -> None:
    """Abort if the existing ``legal_chunks`` collection has a different vector size.

    Never deletes — destructive ops require explicit operator action. The error
    message tells the operator exactly which command to run.
    """

    from packages.config.settings import get_settings
    from packages.embeddings.selector import embedding_vector_size

    settings = get_settings()
    expected = embedding_vector_size(settings)
    collection = settings.qdrant_collection_legal_chunks
    url = settings.qdrant_url.rstrip("/")

    try:
        import httpx

        response = httpx.get(f"{url}/collections/{collection}", timeout=3.0)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"Qdrant pre-flight failed: cannot reach {url} ({exc}). "
            "Start it with `make up` before running eval-real."
        ) from exc

    if response.status_code == 404:
        # Collection will be created on first upsert with the correct size — fine.
        return
    if response.status_code != 200:
        raise SystemExit(
            f"Qdrant pre-flight failed: HTTP {response.status_code} from "
            f"{url}/collections/{collection}: {response.text[:200]!r}"
        )

    try:
        data = response.json()
        size = int(
            data["result"]["config"]["params"]["vectors"]["size"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(
            f"Qdrant pre-flight failed: unexpected collection schema: {exc}"
        ) from exc

    if size != expected:
        raise SystemExit(
            f"Qdrant collection '{collection}' has vector size {size}, but provider "
            f"'{selection.embedding}' requires {expected}. Recreate the collection:\n"
            f"  curl -X DELETE {url}/collections/{collection} && make index-cdc"
        )


def _build_harness_for(selection: ProviderSelection) -> EvalHarness:
    if selection.embedding == "fake" and selection.llm == "fake":
        return build_harness()
    _check_provider_prereqs(selection)
    _preflight_qdrant(selection)
    return build_real_harness()


def main(argv: list[str] | None = None) -> int:
    # When invoked programmatically (e.g. tests), default to no args so we don't
    # accidentally parse the host's sys.argv (pytest flags, etc.). CLI use goes
    # through ``if __name__ == "__main__"`` below which passes ``sys.argv[1:]``.
    args = _parse_args(argv if argv is not None else [])
    selection = _resolve_providers(args)
    _apply_provider_env(selection)
    strict = _strict_mode()
    harness = _build_harness_for(selection)
    result = run_suite(harness, provider=selection)
    write_reports(result, strict=strict)
    _print_summary(result, strict=strict)
    if result.golden.total < MIN_GOLDEN:
        print(f"FAILED: golden set has {result.golden.total} questions, need >= {MIN_GOLDEN}.")
        return 1
    return 0 if result.gate_passed(strict=strict) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
