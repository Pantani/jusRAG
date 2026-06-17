"""Per-step traces for the agentic runtime (§3 observability, §23 acceptance).

The §13 state is normative and has no trace field, so traces are emitted out-of-band:
a structured log line per node plus an in-memory ``TraceCollector`` the graph factory
can attach for auditing/tests. Each entry records ``run_id``, ``step``, ``status`` and
a short human-readable note — enough to reconstruct the path a question took without
bloating the state.

The audit-retry counter is also threaded here as an internal marker convention: nodes
append ``RETRY_MARKER`` to ``state.errors`` when a synthesis is re-attempted, so the
router can count attempts while keeping the state exactly §13. ``visible_errors`` hides
the marker from any user-facing surface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("jusrag.agents")

# Internal sentinel appended to ``state.errors`` to count synthesis re-attempts
# without adding a non-§13 field. Filtered out of user-facing error views.
RETRY_MARKER = "__synthesis_retry__"


@dataclass(frozen=True)
class TraceStep:
    """A single auditable step in a graph run."""

    run_id: str
    step: str
    status: str
    note: str


@dataclass
class TraceCollector:
    """Collects :class:`TraceStep` for one or more runs (tests/observability)."""

    steps: list[TraceStep] = field(default_factory=list)

    def record(self, run_id: str, step: str, status: str, note: str) -> None:
        entry = TraceStep(run_id=run_id, step=step, status=status, note=note)
        self.steps.append(entry)
        logger.info(
            "agent_trace",
            extra={
                "run_id": run_id,
                "step": step,
                "status": status,
                "note": note,
            },
        )

    def for_run(self, run_id: str) -> list[TraceStep]:
        return [s for s in self.steps if s.run_id == run_id]


def retry_attempts(errors: list[str]) -> int:
    """How many synthesis re-attempts have been recorded so far."""

    return sum(1 for e in errors if e == RETRY_MARKER)


def visible_errors(errors: list[str]) -> list[str]:
    """Errors with internal retry markers filtered out (user-facing view)."""

    return [e for e in errors if e != RETRY_MARKER]
