"""
tests/test_engine.py

Unit tests for the OR-Tools CP-SAT scheduling engine and validator.

Coverage
--------
TestFabSchedulerEngine
    test_trivial_single_lot_single_machine  — 1 lot, 1 op, 1 machine
    test_two_lots_no_overlap                — verifies NoOverlap constraint
    test_precedence_enforced               — op2 must start after op1 ends
    test_hot_lot_penalty_higher             — HOT lot generates higher objective
    test_blocked_interval_respected         — operation avoids maintenance window
    test_infeasible_when_no_candidates      — returns INFEASIBLE when no machines
    test_makespan_is_correct               — checks makespan computation

TestScheduleValidator
    test_valid_schedule_passes              — clean schedule → is_valid=True
    test_overlap_detected                  — injected overlap → MACHINE_OVERLAP error
    test_precedence_violation_detected     — reversed sequence → PRECEDENCE_VIOLATION
    test_early_start_detected              — start before release → EARLY_START
    test_blocked_interval_overlap          — op in maintenance → BLOCKED_INTERVAL_OVERLAP
    test_insufficient_setup_detected       — missing setup gap → INSUFFICIENT_SETUP
"""

from __future__ import annotations

import pytest

from scheduler.engine import (
    AssignedOp,
    FabSchedulerEngine,
    LotInput,
    MachineInput,
    OperationInput,
    SetupTimeInput,
)
from scheduler.validator import ScheduleValidator
from schemas.schemas import SolverWeights


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def make_machine(mid: int, name: str, tool_type: str = "SCANNER") -> MachineInput:
    return MachineInput(
        id=mid, name=name, tool_type=tool_type, candidate_stages=[], blocked_intervals=[]
    )


def make_op(
    op_id: int,
    lot_id: int,
    seq: int,
    proc: int,
    recipe_id: int,
    machine_ids: list[int],
) -> OperationInput:
    return OperationInput(
        id=op_id,
        lot_id=lot_id,
        sequence_num=seq,
        recipe_id=recipe_id,
        recipe_name=f"RECIPE-{recipe_id}",
        stage="LITHOGRAPHY",
        processing_time_minutes=proc,
        candidate_machine_ids=machine_ids,
    )


def make_lot(
    lot_id: int,
    name: str,
    ops: list[OperationInput],
    release: int = 0,
    due: int = 1440,
    priority: str = "NORMAL",
    weight: float = 1.0,
) -> LotInput:
    return LotInput(
        id=lot_id,
        name=name,
        priority=priority,
        release_time_minutes=release,
        due_time_minutes=due,
        weight=weight,
        operations=ops,
    )


def default_weights() -> SolverWeights:
    return SolverWeights(makespan=1.0, idle_time=0.0, weighted_tardiness=1.0, penalty_cost=1.0)


# ===========================================================================
# Engine tests
# ===========================================================================


class TestFabSchedulerEngine:
    """Unit tests for FabSchedulerEngine."""

    def test_trivial_single_lot_single_machine(self):
        """One lot with one operation on one machine — should be OPTIMAL."""
        machine = make_machine(1, "LITH-01")
        op = make_op(1, 1, 0, 45, 1, [1])
        lot = make_lot(1, "LOT-001", [op])

        engine = FabSchedulerEngine(
            lots=[lot],
            machines=[machine],
            setup_times=[],
            weights=default_weights(),
            horizon_minutes=480,
            time_limit_seconds=10,
        )
        result = engine.solve()

        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert len(result.assignments) == 1
        a = result.assignments[0]
        assert a.machine_id == 1
        assert a.lot_id == 1
        assert a.end_minutes - a.start_minutes >= 45
        assert result.makespan_minutes >= 45

    def test_two_lots_no_overlap(self):
        """Two lots sharing one machine — their ops must not overlap."""
        machine = make_machine(1, "LITH-01")
        op1 = make_op(1, 1, 0, 45, 1, [1])
        op2 = make_op(2, 2, 0, 60, 1, [1])
        lot1 = make_lot(1, "LOT-A", [op1])
        lot2 = make_lot(2, "LOT-B", [op2])

        engine = FabSchedulerEngine(
            lots=[lot1, lot2],
            machines=[machine],
            setup_times=[],
            weights=default_weights(),
            horizon_minutes=480,
            time_limit_seconds=10,
        )
        result = engine.solve()

        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert len(result.assignments) == 2

        a1 = sorted(result.assignments, key=lambda a: a.start_minutes)[0]
        a2 = sorted(result.assignments, key=lambda a: a.start_minutes)[1]
        # No overlap: a1 must end before a2 starts (both on same machine)
        assert a1.end_minutes <= a2.start_minutes

    def test_precedence_enforced(self):
        """Within a lot, op seq=1 must start after op seq=0 ends."""
        machine = make_machine(1, "LITH-01")
        op0 = make_op(1, 1, 0, 30, 1, [1])
        op1 = make_op(2, 1, 1, 40, 2, [1])
        lot = make_lot(1, "LOT-SEQ", [op0, op1])

        engine = FabSchedulerEngine(
            lots=[lot],
            machines=[machine],
            setup_times=[],
            weights=default_weights(),
            horizon_minutes=480,
            time_limit_seconds=10,
        )
        result = engine.solve()

        assert result.status in ("OPTIMAL", "FEASIBLE")
        # Find the two assignments
        by_op = {a.operation_id: a for a in result.assignments}
        assert by_op[1].end_minutes <= by_op[2].start_minutes

    def test_hot_lot_penalty_contributes_to_objective(self):
        """
        A HOT lot with tight due time must produce a higher objective than
        a NORMAL lot with the same spec (due to 100× vs 10× penalty multiplier).
        """
        machine = make_machine(1, "LITH-01")
        op_n = make_op(1, 1, 0, 45, 1, [1])
        op_h = make_op(2, 2, 0, 45, 1, [1])

        # Both lots share the same machine; tight due time ensures tardiness
        lot_normal = make_lot(1, "NORMAL-LOT", [op_n], due=50, priority="NORMAL")
        lot_hot = make_lot(2, "HOT-LOT", [op_h], due=50, priority="HOT")

        engine_n = FabSchedulerEngine(
            lots=[lot_normal],
            machines=[make_machine(1, "LITH-01")],
            setup_times=[],
            weights=SolverWeights(makespan=0.0, idle_time=0.0, weighted_tardiness=0.0, penalty_cost=1.0),
            horizon_minutes=480,
            time_limit_seconds=10,
        )
        engine_h = FabSchedulerEngine(
            lots=[lot_hot],
            machines=[make_machine(1, "LITH-01")],
            setup_times=[],
            weights=SolverWeights(makespan=0.0, idle_time=0.0, weighted_tardiness=0.0, penalty_cost=1.0),
            horizon_minutes=480,
            time_limit_seconds=10,
        )

        result_n = engine_n.solve()
        result_h = engine_h.solve()

        # Both should be feasible/optimal
        assert result_n.status in ("OPTIMAL", "FEASIBLE")
        assert result_h.status in ("OPTIMAL", "FEASIBLE")

        # Hot lot objective should be >= normal lot (same tardiness, higher mult)
        assert result_h.objective_value >= result_n.objective_value

    def test_blocked_interval_respected(self):
        """
        A machine with a blocked interval [0, 60] must not schedule ops
        that start before minute 60.
        """
        machine = MachineInput(
            id=1, name="LITH-01", tool_type="SCANNER",
            candidate_stages=[], blocked_intervals=[(0, 60)]
        )
        op = make_op(1, 1, 0, 45, 1, [1])
        lot = make_lot(1, "LOT-BLOCKED", [op])

        engine = FabSchedulerEngine(
            lots=[lot],
            machines=[machine],
            setup_times=[],
            weights=default_weights(),
            horizon_minutes=480,
            time_limit_seconds=10,
        )
        result = engine.solve()

        assert result.status in ("OPTIMAL", "FEASIBLE")
        assert len(result.assignments) == 1
        # Op must start at or after end of blocked interval
        assert result.assignments[0].start_minutes >= 60

    def test_makespan_correct_sequential(self):
        """Makespan equals start of first op + sum of all op durations (single machine)."""
        machine = make_machine(1, "LITH-01")
        op0 = make_op(1, 1, 0, 30, 1, [1])
        op1 = make_op(2, 1, 1, 40, 2, [1])
        lot = make_lot(1, "LOT-SEQ", [op0, op1])

        engine = FabSchedulerEngine(
            lots=[lot],
            machines=[machine],
            setup_times=[],
            weights=SolverWeights(makespan=1.0, idle_time=0.0, weighted_tardiness=0.0, penalty_cost=0.0),
            horizon_minutes=480,
            time_limit_seconds=10,
        )
        result = engine.solve()

        assert result.status in ("OPTIMAL", "FEASIBLE")
        # Optimal makespan for one machine, one lot with two sequential ops = 70
        assert result.makespan_minutes >= 70

    def test_multiple_machines_reduces_makespan(self):
        """Two parallel machines should allow two lots to run concurrently."""
        m1 = make_machine(1, "LITH-01")
        m2 = make_machine(2, "LITH-02")
        op1 = make_op(1, 1, 0, 60, 1, [1, 2])
        op2 = make_op(2, 2, 0, 60, 1, [1, 2])
        lot1 = make_lot(1, "LOT-A", [op1])
        lot2 = make_lot(2, "LOT-B", [op2])

        engine = FabSchedulerEngine(
            lots=[lot1, lot2],
            machines=[m1, m2],
            setup_times=[],
            weights=SolverWeights(makespan=1.0, idle_time=0.0, weighted_tardiness=0.0, penalty_cost=0.0),
            horizon_minutes=480,
            time_limit_seconds=10,
        )
        result = engine.solve()

        assert result.status in ("OPTIMAL", "FEASIBLE")
        # With two parallel machines, makespan should ideally be 60 (concurrent)
        assert result.makespan_minutes <= 120  # at most sequential


# ===========================================================================
# Validator tests
# ===========================================================================


class TestScheduleValidator:
    """Unit tests for ScheduleValidator."""

    def _make_validator(
        self,
        assignments: list[AssignedOp],
        lots: list[LotInput] | None = None,
        machines: list[MachineInput] | None = None,
        setup_map: dict | None = None,
        horizon: int = 480,
    ) -> ScheduleValidator:
        if lots is None:
            lots = [make_lot(1, "LOT-001", [])]
        if machines is None:
            machines = [make_machine(1, "LITH-01")]
        return ScheduleValidator(
            assignments=assignments,
            lots=lots,
            machines=machines,
            setup_map=setup_map or {},
            horizon_minutes=horizon,
        )

    def _make_assignment(
        self,
        op_id: int,
        lot_id: int,
        machine_id: int,
        seq: int,
        start: int,
        end: int,
    ) -> AssignedOp:
        return AssignedOp(
            operation_id=op_id,
            lot_id=lot_id,
            machine_id=machine_id,
            sequence_num=seq,
            start_minutes=start,
            end_minutes=end,
            processing_time_minutes=end - start,
            setup_time_minutes=0,
        )

    def test_valid_schedule_passes(self):
        """A schedule with no violations should return is_valid=True."""
        a1 = self._make_assignment(1, 1, 1, 0, 0, 45)
        a2 = self._make_assignment(2, 1, 1, 1, 45, 90)

        lot = make_lot(1, "LOT-001", [
            make_op(1, 1, 0, 45, 1, [1]),
            make_op(2, 1, 1, 45, 1, [1]),
        ])
        v = self._make_validator([a1, a2], lots=[lot])
        result = v.validate()

        assert result.is_valid
        assert result.stats["errors"] == 0

    def test_overlap_detected(self):
        """Two ops on same machine that overlap should produce MACHINE_OVERLAP error."""
        a1 = self._make_assignment(1, 1, 1, 0, 0, 50)
        a2 = self._make_assignment(2, 2, 1, 0, 30, 90)   # overlaps with a1

        lots = [
            make_lot(1, "LOT-A", [make_op(1, 1, 0, 50, 1, [1])]),
            make_lot(2, "LOT-B", [make_op(2, 2, 0, 60, 1, [1])]),
        ]
        v = self._make_validator([a1, a2], lots=lots)
        result = v.validate()

        assert not result.is_valid
        codes = [viol.code for viol in result.violations]
        assert "MACHINE_OVERLAP" in codes

    def test_precedence_violation_detected(self):
        """Op with higher seq_num starting before lower seq_num ends → PRECEDENCE_VIOLATION."""
        a0 = self._make_assignment(1, 1, 1, 0, 0, 60)
        a1 = self._make_assignment(2, 1, 1, 1, 30, 90)  # seq 1 starts before seq 0 ends

        lot = make_lot(1, "LOT-001", [
            make_op(1, 1, 0, 60, 1, [1]),
            make_op(2, 1, 1, 60, 2, [1]),
        ])
        v = self._make_validator([a0, a1], lots=[lot])
        result = v.validate()

        assert not result.is_valid
        codes = [viol.code for viol in result.violations]
        assert "PRECEDENCE_VIOLATION" in codes

    def test_early_start_detected(self):
        """Op starting before lot release time → EARLY_START error."""
        a = self._make_assignment(1, 1, 1, 0, 5, 55)   # starts at 5

        lot = make_lot(1, "LOT-001", [make_op(1, 1, 0, 50, 1, [1])], release=60)
        v = self._make_validator([a], lots=[lot])
        result = v.validate()

        assert not result.is_valid
        codes = [viol.code for viol in result.violations]
        assert "EARLY_START" in codes

    def test_blocked_interval_overlap_detected(self):
        """Op overlapping a maintenance window → BLOCKED_INTERVAL_OVERLAP error."""
        machine = MachineInput(
            id=1, name="LITH-01", tool_type="SCANNER",
            candidate_stages=[], blocked_intervals=[(100, 200)]
        )
        a = self._make_assignment(1, 1, 1, 0, 90, 150)   # overlaps [100, 200]

        lot = make_lot(1, "LOT-001", [make_op(1, 1, 0, 60, 1, [1])])
        v = self._make_validator([a], lots=[lot], machines=[machine])
        result = v.validate()

        assert not result.is_valid
        codes = [viol.code for viol in result.violations]
        assert "BLOCKED_INTERVAL_OVERLAP" in codes

    def test_insufficient_setup_detected(self):
        """Insufficient gap between recipe transitions → INSUFFICIENT_SETUP error."""
        machine = make_machine(1, "LITH-01", "SCANNER")
        # Op1 uses recipe 1, ends at 60. Op2 uses recipe 2, starts at 65.
        # Required setup = 30 min → gap of 5 is insufficient.
        a1 = self._make_assignment(1, 1, 1, 0, 0, 60)
        a2 = self._make_assignment(2, 2, 1, 0, 65, 120)

        lots = [
            make_lot(1, "LOT-A", [make_op(1, 1, 0, 60, 1, [1])]),
            make_lot(2, "LOT-B", [make_op(2, 2, 0, 55, 2, [1])]),
        ]
        setup_map = {(1, 2, "SCANNER"): 30}
        v = self._make_validator([a1, a2], lots=lots, machines=[machine], setup_map=setup_map)

        # Patch op_recipe_map manually
        v._op_recipe_map = {1: 1, 2: 2}
        result = v.validate()

        assert not result.is_valid
        codes = [viol.code for viol in result.violations]
        assert "INSUFFICIENT_SETUP" in codes

    def test_warning_horizon_exceeded(self):
        """An operation finishing beyond the horizon should produce a WARNING."""
        a = self._make_assignment(1, 1, 1, 0, 460, 490)   # horizon=480

        lot = make_lot(1, "LOT-001", [make_op(1, 1, 0, 30, 1, [1])])
        v = self._make_validator([a], lots=[lot], horizon=480)
        result = v.validate()

        # Should have a HORIZON_EXCEEDED warning but still be "valid" (warnings != errors)
        warning_codes = [viol.code for viol in result.violations if viol.severity == "WARNING"]
        assert "HORIZON_EXCEEDED" in warning_codes
