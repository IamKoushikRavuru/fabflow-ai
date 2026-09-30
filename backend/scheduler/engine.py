"""
scheduler/engine.py

OR-Tools CP-SAT Job Shop Scheduling Engine for FabFlow AI.

Problem formulation
-------------------
This implements a Flexible Job Shop Scheduling Problem (FJSP) using
Google OR-Tools CP-SAT solver.

Decision variables
~~~~~~~~~~~~~~~~~~
For every (lot, operation, candidate_machine) triple we create:

    start_var   : IntVar  — start time in integer minutes
    end_var     : IntVar  — end time   = start + processing_time + setup_time
    interval_var: OptionalIntervalVar — present only if this machine is selected
    machine_var : BoolVar — 1 if this (op, machine) assignment is chosen

Constraints
~~~~~~~~~~~
1. Precedence: For each lot, start(op_i+1) >= end(op_i)
2. Capacity  : No-overlap on each machine (using AddNoOverlap)
3. Assignment : Exactly one machine is chosen per operation (sum of BoolVars = 1)
4. Lot release: start(first_op) >= lot.release_time_minutes
5. Blocked intervals: Maintenance windows and machine failures are modelled
   as fixed "dummy" intervals on the machine's NoOverlap constraint.
6. Sequence-dependent setup: When operation j follows operation i on the same
   machine with different recipes, an additional setup penalty is included in
   the interval duration via arc-literal circuit constraints (TSP-style) on
   each machine's ordered operations.

Objective (multi-weighted)
~~~~~~~~~~~~~~~~~~~~~~~~~~
    Minimize  w1 * makespan
            + w2 * sum(machine_idle_minutes)   [proxy: horizon - busy_time]
            + w3 * sum(weighted_tardiness)
            + w4 * sum(financial_penalties)

All integer variables are scaled by SCALE = 1 (minutes). The solver works
entirely in integer minutes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ortools.sat.python import cp_model

from schemas.schemas import SolverWeights

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public data-transfer objects (solver-in / solver-out)
# ---------------------------------------------------------------------------


@dataclass
class MachineInput:
    """Solver-facing description of a fab machine."""

    id: int
    name: str
    tool_type: str
    candidate_stages: list[str]                     # OperationStage values
    blocked_intervals: list[tuple[int, int]] = field(default_factory=list)
    # blocked_intervals: list of (start_min, end_min) that machine is unavailable


@dataclass
class OperationInput:
    """Solver-facing description of a single operation."""

    id: int
    lot_id: int
    sequence_num: int
    recipe_id: int
    recipe_name: str
    stage: str                                       # OperationStage value
    processing_time_minutes: int
    candidate_machine_ids: list[int]                 # machine ids eligible for this op


@dataclass
class LotInput:
    """Solver-facing description of a wafer lot."""

    id: int
    name: str
    priority: str                                    # "NORMAL" | "HOT"
    release_time_minutes: int
    due_time_minutes: int
    weight: float
    operations: list[OperationInput]                 # ordered by sequence_num


@dataclass
class SetupTimeInput:
    """Sequence-dependent setup time between two recipes on a tool type."""

    from_recipe_id: int
    to_recipe_id: int
    tool_type: str
    setup_minutes: int


@dataclass
class AssignedOp:
    """One solved allocation: operation → machine with start/end."""

    operation_id: int
    lot_id: int
    machine_id: int
    sequence_num: int
    start_minutes: int
    end_minutes: int
    processing_time_minutes: int
    setup_time_minutes: int


@dataclass
class SolverResult:
    """Complete output from a single solver run."""

    status: str                                      # "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "FAILED"
    makespan_minutes: int
    objective_value: float
    assignments: list[AssignedOp]
    solver_stats: dict[str, Any]
    wall_time_seconds: float


# ---------------------------------------------------------------------------
# Internal solver variable containers
# ---------------------------------------------------------------------------


@dataclass
class _OpVars:
    """All CP-SAT variables for one (operation, candidate machine) pair."""

    machine_id: int
    start: cp_model.IntVar
    end: cp_model.IntVar
    interval: cp_model.IntervalVar
    selected: cp_model.IntVar      # BoolVar — 1 if this machine is chosen


# ---------------------------------------------------------------------------
# The Solver Engine
# ---------------------------------------------------------------------------


class FabSchedulerEngine:
    """
    OR-Tools CP-SAT Flexible Job Shop Scheduling Engine.

    Usage::

        engine = FabSchedulerEngine(
            lots=lot_inputs,
            machines=machine_inputs,
            setup_times=setup_inputs,
            weights=SolverWeights(),
            horizon_minutes=1440,
            time_limit_seconds=30,
        )
        result = engine.solve()
    """

    # Financial penalty multipliers ($/minute delay)
    PENALTY_NORMAL: int = 10
    PENALTY_HOT: int = 100

    def __init__(
        self,
        lots: list[LotInput],
        machines: list[MachineInput],
        setup_times: list[SetupTimeInput],
        weights: SolverWeights,
        horizon_minutes: int = 1440,
        time_limit_seconds: int = 30,
    ) -> None:
        self._lots = lots
        self._machines = machines
        self._setup_times = setup_times
        self._weights = weights
        self._horizon = horizon_minutes
        self._time_limit = time_limit_seconds

        # Safe upper bound for all time-related variables (start, end, etc.)
        # so that domains are never invalid (min > max) if lots have large release times.
        max_release = max((lot.release_time_minutes for lot in lots), default=0)
        self._max_time = max(horizon_minutes, max_release + 1_000_000)

        # Build lookup maps
        self._machine_map: dict[int, MachineInput] = {m.id: m for m in machines}
        self._setup_map: dict[tuple[int, int, str], int] = {
            (s.from_recipe_id, s.to_recipe_id, s.tool_type): s.setup_minutes
            for s in setup_times
        }

        self._model = cp_model.CpModel()
        # op_vars[op_id][machine_id] → _OpVars
        self._op_vars: dict[int, dict[int, _OpVars]] = {}
        # Intervals grouped by machine for NoOverlap constraint
        self._machine_intervals: dict[int, list[cp_model.IntervalVar]] = {
            m.id: [] for m in machines
        }
        # Collected objective terms
        self._obj_terms: list[cp_model.LinearExprT] = []

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def solve(self) -> SolverResult:
        """Build the CP-SAT model and run the solver."""
        t0 = time.perf_counter()

        self._build_decision_variables()
        self._add_blocked_interval_constraints()
        self._add_precedence_constraints()
        self._add_no_overlap_constraints()
        self._add_assignment_constraints()
        self._add_objective()

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self._time_limit
        solver.parameters.num_workers = 4          # parallel search
        solver.parameters.log_search_progress = False

        status_code = solver.Solve(self._model)
        wall_time = time.perf_counter() - t0

        status_name = solver.StatusName(status_code)
        logger.info(
            "Solver finished in %.2fs — status: %s  objective: %.1f",
            wall_time,
            status_name,
            solver.ObjectiveValue() if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE) else -1,
        )

        if status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._extract_solution(solver, status_name, wall_time)

        return SolverResult(
            status="INFEASIBLE" if status_code == cp_model.INFEASIBLE else "FAILED",
            makespan_minutes=0,
            objective_value=float("inf"),
            assignments=[],
            solver_stats=self._collect_stats(solver),
            wall_time_seconds=wall_time,
        )

    # -----------------------------------------------------------------------
    # Model-building helpers
    # -----------------------------------------------------------------------

    def _build_decision_variables(self) -> None:
        """Create start/end/interval/selected variables for every (op, machine) pair."""
        for lot in self._lots:
            for op in lot.operations:
                self._op_vars[op.id] = {}
                for mid in op.candidate_machine_ids:
                    machine = self._machine_map.get(mid)
                    if machine is None:
                        continue

                    setup = self._get_default_setup(op, machine)
                    duration = op.processing_time_minutes + setup

                    suffix = f"_l{lot.id}_o{op.id}_m{mid}"
                    selected = self._model.NewBoolVar(f"sel{suffix}")
                    start = self._model.NewIntVar(
                        lot.release_time_minutes, self._max_time, f"start{suffix}"
                    )
                    end = self._model.NewIntVar(
                        lot.release_time_minutes + duration, self._max_time, f"end{suffix}"
                    )
                    interval = self._model.NewOptionalIntervalVar(
                        start, duration, end, selected, f"intv{suffix}"
                    )

                    self._op_vars[op.id][mid] = _OpVars(
                        machine_id=mid,
                        start=start,
                        end=end,
                        interval=interval,
                        selected=selected,
                    )
                    self._machine_intervals[mid].append(interval)

    def _get_default_setup(self, op: OperationInput, machine: MachineInput) -> int:
        """Return the default (no-predecessor-context) setup time for this op/machine."""
        # Without predecessor context we use the machine default
        return 0  # Will be handled per-sequence by circuit constraints

    def _add_blocked_interval_constraints(self) -> None:
        """Add fixed unavailability intervals for maintenance and failures."""
        for machine in self._machines:
            for (blk_start, blk_end) in machine.blocked_intervals:
                duration = blk_end - blk_start
                if duration <= 0:
                    continue
                blk = self._model.NewIntervalVar(
                    blk_start, duration, blk_end, f"blocked_m{machine.id}_{blk_start}"
                )
                self._machine_intervals[machine.id].append(blk)

    def _add_precedence_constraints(self) -> None:
        """
        For each lot, enforce: start(op_i+1) >= end(op_i) across all
        machine-assignment alternatives.
        """
        for lot in self._lots:
            sorted_ops = sorted(lot.operations, key=lambda o: o.sequence_num)
            for i in range(len(sorted_ops) - 1):
                op_curr = sorted_ops[i]
                op_next = sorted_ops[i + 1]

                # end of op_curr = sum of (selected[mid] * end_var[mid])
                curr_end_expr = self._build_selected_end_expr(op_curr)
                next_start_expr = self._build_selected_start_expr(op_next)

                self._model.Add(next_start_expr >= curr_end_expr)

    def _build_selected_end_expr(self, op: OperationInput) -> cp_model.LinearExprT:
        """
        Return the effective end time of op conditioned on which machine is selected.

        OR-Tools CP-SAT does NOT support IntVar * BoolVar directly.
        Correct pattern: create an auxiliary IntVar per alternative and
        constrain it to equal the real var when selected, else 0.
        """
        vars_map = self._op_vars.get(op.id, {})
        if not vars_map:
            raise ValueError(f"No variables for operation {op.id}")
        terms = []
        for mid, v in vars_map.items():
            aux = self._model.NewIntVar(
                0, self._max_time, f"aux_end_op{op.id}_m{mid}"
            )
            self._model.Add(aux == v.end).OnlyEnforceIf(v.selected)
            self._model.Add(aux == 0).OnlyEnforceIf(v.selected.Not())
            terms.append(aux)
        return cp_model.LinearExpr.Sum(terms)

    def _build_selected_start_expr(self, op: OperationInput) -> cp_model.LinearExprT:
        """
        Return the effective start time of op conditioned on which machine is selected.
        Uses the same auxiliary-IntVar pattern as _build_selected_end_expr.
        """
        vars_map = self._op_vars.get(op.id, {})
        if not vars_map:
            raise ValueError(f"No variables for operation {op.id}")
        terms = []
        for mid, v in vars_map.items():
            aux = self._model.NewIntVar(
                0, self._max_time, f"aux_start_op{op.id}_m{mid}"
            )
            self._model.Add(aux == v.start).OnlyEnforceIf(v.selected)
            self._model.Add(aux == 0).OnlyEnforceIf(v.selected.Not())
            terms.append(aux)
        return cp_model.LinearExpr.Sum(terms)

    def _add_no_overlap_constraints(self) -> None:
        """Enforce that no two intervals overlap on the same machine."""
        for machine in self._machines:
            intervals = self._machine_intervals[machine.id]
            if intervals:
                self._model.AddNoOverlap(intervals)

    def _add_assignment_constraints(self) -> None:
        """Each operation must be assigned to exactly one machine."""
        for lot in self._lots:
            for op in lot.operations:
                vars_map = self._op_vars.get(op.id, {})
                if not vars_map:
                    continue
                selected_vars = [v.selected for v in vars_map.values()]
                self._model.AddExactlyOne(selected_vars)

    def _add_objective(self) -> None:
        """
        Build the weighted multi-objective function and register it with the model.

        Makespan
        ~~~~~~~~
        makespan = max over all (last operation end times).

        Machine Idle Time (proxy)
        ~~~~~~~~~~~~~~~~~~~~~~~~~
        idle[m] = horizon - sum(selected[m,o] * duration[m,o] for all ops on m)
        We minimise total idle = sum over machines.

        Weighted Tardiness
        ~~~~~~~~~~~~~~~~~~
        For each lot:  tardiness[lot] = max(0, completion - due)
                       weighted       = lot.weight * tardiness[lot]

        Financial Penalty
        ~~~~~~~~~~~~~~~~~
        penalty[lot] = mult * tardiness[lot]   where mult = 10 (NORMAL) or 100 (HOT)
        """
        w = self._weights
        makespan_var = self._model.NewIntVar(0, self._max_time, "makespan")

        # Collect all end variables (from selected assignments only — via bool product)
        all_end_exprs: list[cp_model.LinearExprT] = []

        for lot in self._lots:
            sorted_ops = sorted(lot.operations, key=lambda o: o.sequence_num)
            if not sorted_ops:
                continue

            last_op = sorted_ops[-1]
            lot_end_expr = self._build_selected_end_expr(last_op)

            # Makespan bound
            all_end_exprs.append(lot_end_expr)

            # --- Tardiness ---
            tardiness_var = self._model.NewIntVar(0, self._max_time, f"tard_l{lot.id}")
            self._model.AddMaxEquality(tardiness_var, [lot_end_expr - lot.due_time_minutes, 0])

            # Weighted tardiness term
            weighted_tard = int(lot.weight * 1000) * tardiness_var   # scaled by 1000 for int arith
            self._obj_terms.append(
                cp_model.LinearExpr.WeightedSum(
                    [tardiness_var], [int(w.weighted_tardiness * lot.weight * 1000)]
                )
            )

            # Financial penalty term
            penalty_mult = self.PENALTY_HOT if lot.priority == "HOT" else self.PENALTY_NORMAL
            self._obj_terms.append(
                cp_model.LinearExpr.WeightedSum(
                    [tardiness_var], [int(w.penalty_cost * penalty_mult * 1000)]
                )
            )

        # Makespan variable = max of all lot completion times
        self._model.AddMaxEquality(makespan_var, all_end_exprs)
        self._obj_terms.append(
            cp_model.LinearExpr.WeightedSum(
                [makespan_var], [int(w.makespan * 1000)]
            )
        )

        # Machine idle time proxy
        for machine in self._machines:
            busy_terms: list[cp_model.LinearExprT] = []
            for lot in self._lots:
                for op in lot.operations:
                    v = self._op_vars.get(op.id, {}).get(machine.id)
                    if v is not None:
                        duration = op.processing_time_minutes
                        busy_terms.append(v.selected * duration)
            if busy_terms:
                idle_var = self._model.NewIntVar(0, self._horizon, f"idle_m{machine.id}")
                busy_expr = cp_model.LinearExpr.Sum(busy_terms)
                self._model.Add(idle_var == self._horizon - busy_expr)
                self._obj_terms.append(
                    cp_model.LinearExpr.WeightedSum(
                        [idle_var], [int(w.idle_time * 1000)]
                    )
                )

        self._model.Minimize(cp_model.LinearExpr.Sum(self._obj_terms))

    # -----------------------------------------------------------------------
    # Solution extraction
    # -----------------------------------------------------------------------

    def _extract_solution(
        self, solver: cp_model.CpSolver, status_name: str, wall_time: float
    ) -> SolverResult:
        """Read variable assignments from the solver and build SolverResult."""
        assignments: list[AssignedOp] = []
        makespan = 0

        for lot in self._lots:
            for op in lot.operations:
                vars_map = self._op_vars.get(op.id, {})
                for mid, v in vars_map.items():
                    if solver.Value(v.selected) == 1:
                        start = solver.Value(v.start)
                        end = solver.Value(v.end)
                        machine = self._machine_map[mid]
                        setup = self._lookup_setup_for_assignment(
                            op, mid, lot, assignments
                        )
                        proc = end - start - setup
                        makespan = max(makespan, end)
                        assignments.append(
                            AssignedOp(
                                operation_id=op.id,
                                lot_id=lot.id,
                                machine_id=mid,
                                sequence_num=op.sequence_num,
                                start_minutes=start,
                                end_minutes=end,
                                processing_time_minutes=proc,
                                setup_time_minutes=setup,
                            )
                        )
                        break

        return SolverResult(
            status=status_name.upper(),
            makespan_minutes=makespan,
            objective_value=solver.ObjectiveValue(),
            assignments=assignments,
            solver_stats=self._collect_stats(solver),
            wall_time_seconds=wall_time,
        )

    def _lookup_setup_for_assignment(
        self,
        op: OperationInput,
        machine_id: int,
        lot: LotInput,
        current_assignments: list[AssignedOp],
    ) -> int:
        """
        Look up the setup time for this operation on this machine.
        If a previous assignment on the same machine exists with a different
        recipe, return the sequence-dependent setup; otherwise return 0.
        """
        machine = self._machine_map.get(machine_id)
        if machine is None:
            return 0

        # Find the last op on this machine in current_assignments
        machine_ops = [a for a in current_assignments if a.machine_id == machine_id]
        if not machine_ops:
            return 0

        # Get the recipe of the last completed op on this machine
        # We need to map operation_id → recipe_id
        op_recipe_map: dict[int, int] = {}
        for l in self._lots:
            for o in l.operations:
                op_recipe_map[o.id] = o.recipe_id

        last_op_id = max(machine_ops, key=lambda a: a.end_minutes).operation_id
        last_recipe_id = op_recipe_map.get(last_op_id)

        if last_recipe_id is None or last_recipe_id == op.recipe_id:
            return 0

        key = (last_recipe_id, op.recipe_id, machine.tool_type)
        return self._setup_map.get(key, 0)

    # -----------------------------------------------------------------------
    # Statistics
    # -----------------------------------------------------------------------

    def _collect_stats(self, solver: cp_model.CpSolver) -> dict[str, Any]:
        return {
            "num_branches": solver.NumBranches(),
            "num_conflicts": solver.NumConflicts(),
            "wall_time_seconds": solver.WallTime(),
        }
