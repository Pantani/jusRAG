"""Quality evaluation suite for jus-rag-brasil (§35-37).

Pure, deterministic, offline metrics that turn the safety rules into a build gate.
Phase 5 ships the citation/hallucination side (:mod:`packages.evals.citation_eval`);
Phase 8 adds the golden dataset, retrieval/answer evals and ``run_all``.
"""
