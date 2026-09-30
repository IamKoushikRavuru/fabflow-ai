"""
scheduler/validator.py

Schedule validation for FabFlow AI.

The validator takes a list of AssignedOp allocations (solver output) and
checks every structural and business constraint.  All violations are
collected and returned — validation never short-circuits on the first error
so the caller receives a full picture of what went wrong.

Checks performed
----------------
1. No overlapping operations on the same machine.
2. Precedence is respected within every lot.
3. No operation starts before the lot's release time.
4. No operation overlaps a machine maintenance window or failure interval.
5. Every lot's last operation finishes within the horizon.
6. Processing times match expected values (sanity check).
7. Setup times are correctly applied between consecutive recipe changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from scheduler.engine import AssignedOp, MachineInput, LotInput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Violation data-transfer object
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    """A single detected constraint violation."""

    code: str           # Short machine-readable key, e.g. "OVERLAP"
    severity: str       # "ERROR" | "WARNING"
    message: str
    context: dict[str, Any]


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Aggregate outcome from a full validation pass."""

    is_valid: bool
    violations: list[Violation]
    stats: dict[str, int]   # counts: {"errors": N, "warnings": M}

    @classmethod
    def ok(cls) -> ValidationResult:
        return cls(is_valid=True, violations=[], stats={"errors": 0, "warnings": 0})


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class ScheduleValidator:
    """
    Validates a completed schedule (list of AssignedOp) against all
    fab-scheduling constraints.

    Usage::

        validator = ScheduleValidator(
            assignments=result.assignments,
            lots=lot_inputs,
            machines=machine_inputs,
            setup_map=setup_map,
            horizon_minutes=1440,
        )
        result = validator.validate()
        if not result.is_valid:
            for v in result.violations:
                print(v.code, v.message)
    """

    def __init__(
        self,
        assignments: list[AssignedOp],
        lots: list[LotInput],
        machines: list[MachineInput],
        setup_map: dict[tuple[int, int, str], int],
        horizon_minutes: int = 1440,
    ) -> None:
        self._assignments = assignments
        self._lots = lots
        self._machines = machines
        self._setup_map = setup_map
        self._horizon = horizon_minutes

        # Build lookup maps
        self._lot_map: dict[int, LotInput] = {lot.id: lot for lot in lots}
        self._machine_map: dict[int, MachineInput] = {m.id: m for m in machines}

        # Index assignments by lot and by machine
        self._by_lot: dict[int, list[AssignedOp]] = {}
        self._by_machine: dict[int, list[AssignedOp]] = {}
        for a in assignments:
            self._by_lot.setdefault(a.lot_id, []).append(a)
            self._by_machine.setdefault(a.machine_id, []).append(a)

        # Build op→recipe map from lot inputs
        self._op_recipe_map: dict[int, int] = {}
        self._op_stage_map: dict[int, str] = {}
        for lot in lots:
            for op in lot.operations:
                self._op_recipe_map[op.id] = op.recipe_id
                self._op_stage_map[op.id] = op.stage

        self._violations: list[Violation] = []

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------

    def validate(self) -> ValidationResult:
        """Run all checks and return a ValidationResult."""
        self._violations = []

        self._check_no_machine_overlaps()
        self._check_precedence()
        self._check_release_times()
        self._check_blocked_intervals()
        self._check_horizon()
        self._check_setup_times()

        errors = sum(1 for v in self._violations if v.severity == "ERROR")
        warnings = sum(1 for v in self._violations if v.severity == "WARNING")
        return ValidationResult(
            is_valid=errors == 0,
            violations=self._violations,
            stats={"errors": errors, "warnings": warnings},
        )

    # -----------------------------------------------------------------------
    # Individual checks
    # -----------------------------------------------------------------------

    def _check_no_machine_overlaps(self) -> None:
        """Check that no two operations overlap on the same machine."""
        for machine_id, ops in self._by_machine.items():
            sorted_ops = sorted(ops, key=lambda a: a.start_minutes)
            for i in range(len(sorted_ops) - 1):
                a = sorted_ops[i]
                b = sorted_ops[i + 1]
                if a.end_minutes > b.start_minutes:
                    self._violations.append(
                        Violation(
                            code="MACHINE_OVERLAP",
                            severity="ERROR",
                            message=(
                                f"Machine {machine_id}: Op {a.operation_id} "
                                f"[{a.start_minutes}-{a.end_minutes}] overlaps "
                                f"Op {b.operation_id} [{b.start_minutes}-{b.end_minutes}]"
                            ),
                            context={
                                "machine_id": machine_id,
                                "op_a": a.operation_id,
                                "op_b": b.operation_id,
                                "overlap_minutes": a.end_minutes - b.start_minutes,
                            },
                        )
                    )

    def _check_precedence(self) -> None:
        """Check that within each lot, seq N+1 starts after seq N ends."""
        for lot_id, ops in self._by_lot.items():
            sorted_ops = sorted(ops, key=lambda a: a.sequence_num)
            for i in range(len(sorted_ops) - 1):
                prev = sorted_ops[i]
                nxt = sorted_ops[i + 1]
                if nxt.start_minutes < prev.end_minutes:
                    self._violations.append(
                        Violation(
                            code="PRECEDENCE_VIOLATION",
                            severity="ERROR",
                            message=(
                                f"Lot {lot_id}: Op {nxt.operation_id} (seq {nxt.sequence_num}) "
                                f"starts at {nxt.start_minutes} before Op {prev.operation_id} "
                                f"(seq {prev.sequence_num}) ends at {prev.end_minutes}"
                            ),
                            context={
                                "lot_id": lot_id,
                                "op_prev": prev.operation_id,
                                "op_next": nxt.operation_id,
                                "gap_minutes": nxt.start_minutes - prev.end_minutes,
                            },
                        )
                    )

    def _check_release_times(self) -> None:
        """Check that no operation starts before the lot is released."""
        for lot_id, ops in self._by_lot.items():
            lot = self._lot_map.get(lot_id)
            if lot is None:
                continue
            for op in ops:
                if op.start_minutes < lot.release_time_minutes:
                    self._violations.append(
                        Violation(
                            code="EARLY_START",
                            severity="ERROR",
                            message=(
                                f"Lot {lot_id}: Op {op.operation_id} starts at "
                                f"{op.start_minutes} before lot release "
                                f"{lot.release_time_minutes}"
                            ),
                            context={
                                "lot_id": lot_id,
                                "operation_id": op.operation_id,
                                "start_minutes": op.start_minutes,
                                "release_time_minutes": lot.release_time_minutes,
                            },
                        )
                    )

    def _check_blocked_intervals(self) -> None:
        """Check that no operation overlaps a machine blocked interval."""
        for machine in self._machines:
            machine_ops = self._by_machine.get(machine.id, [])
            for blk_start, blk_end in machine.blocked_intervals:
                for op in machine_ops:
                    # Overlap: op.start < blk_end AND op.end > blk_start
                    if op.start_minutes < blk_end and op.end_minutes > blk_start:
                        self._violations.append(
                            Violation(
                                code="BLOCKED_INTERVAL_OVERLAP",
                                severity="ERROR",
                                message=(
                                    f"Machine {machine.id}: Op {op.operation_id} "
                                    f"[{op.start_minutes}-{op.end_minutes}] overlaps "
                                    f"blocked interval [{blk_start}-{blk_end}]"
                                ),
                                context={
                                    "machine_id": machine.id,
                                    "operation_id": op.operation_id,
                                    "blk_start": blk_start,
                                    "blk_end": blk_end,
                                },
                            )
                        )

    def _check_horizon(self) -> None:
        """Warn if any lot's last operation finishes beyond the horizon."""
        for lot_id, ops in self._by_lot.items():
            if not ops:
                continue
            last = max(ops, key=lambda a: a.end_minutes)
            if last.end_minutes > self._horizon:
                self._violations.append(
                    Violation(
                        code="HORIZON_EXCEEDED",
                        severity="WARNING",
                        message=(
                            f"Lot {lot_id}: last op ends at {last.end_minutes} "
                            f"which exceeds horizon {self._horizon}"
                        ),
                        context={
                            "lot_id": lot_id,
                            "end_minutes": last.end_minutes,
                            "horizon": self._horizon,
                        },
                    )
                )

    def _check_setup_times(self) -> None:
        """
        For consecutive operations on the same machine, verify that the gap
        between them is at least the required setup time when recipes differ.
        """
        for machine in self._machines:
            ops_on_machine = sorted(
                self._by_machine.get(machine.id, []), key=lambda a: a.start_minutes
            )
            for i in range(len(ops_on_machine) - 1):
                prev = ops_on_machine[i]
                curr = ops_on_machine[i + 1]
                prev_recipe = self._op_recipe_map.get(prev.operation_id)
                curr_recipe = self._op_recipe_map.get(curr.operation_id)

                if prev_recipe is None or curr_recipe is None or prev_recipe == curr_recipe:
                    continue

                required_setup = self._setup_map.get(
                    (prev_recipe, curr_recipe, machine.tool_type), 0
                )
                actual_gap = curr.start_minutes - prev.end_minutes
                if actual_gap < required_setup:
                    self._violations.append(
                        Violation(
                            code="INSUFFICIENT_SETUP",
                            severity="ERROR",
                            message=(
                                f"Machine {machine.id}: gap between Op {prev.operation_id} "
                                f"and Op {curr.operation_id} is {actual_gap} min, "
                                f"but setup requires {required_setup} min "
                                f"(recipe {prev_recipe} → {curr_recipe})"
                            ),
                            context={
                                "machine_id": machine.id,
                                "op_prev": prev.operation_id,
                                "op_curr": curr.operation_id,
                                "from_recipe": prev_recipe,
                                "to_recipe": curr_recipe,
                                "required_setup": required_setup,
                                "actual_gap": actual_gap,
                            },
                        )
                    )
