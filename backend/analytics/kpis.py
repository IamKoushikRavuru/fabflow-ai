"""
analytics/kpis.py

KPI Calculator and Financial Penalty Engine for FabFlow AI.

Computes the following metrics from a solved schedule:

Operational KPIs
----------------
- Makespan (minutes)              — total calendar span of the schedule
- Machine utilization (%)         — per machine and average
- Machine idle time (minutes)     — per machine and total
- Throughput rate (lots/hour)     — lots completed per hour of makespan

Tardiness KPIs
--------------
- Per-lot delay (minutes)         — max(0, completion - due)
- Per-lot tardiness flag          — bool
- Weighted tardiness              — lot.weight × delay
- Total weighted tardiness

Financial KPIs
--------------
Normal lots: penalty = PENALTY_NORMAL × delay_minutes  ($10/min)
Hot lots   : penalty = PENALTY_HOT   × delay_minutes  ($100/min)

Gantt Chart JSON
----------------
Builds the GanttChart Pydantic structure consumable by frontend charting
libraries (e.g. vis-timeline, Plotly, etc.).

All computation is pure Python/NumPy — no DB access.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from scheduler.engine import AssignedOp, LotInput, MachineInput
from schemas.schemas import (
    GanttChart,
    GanttTask,
    KPIResponse,
    LotTardiness,
    MachineUtilization,
    OperationStage,
)

logger = logging.getLogger(__name__)

# Financial penalty multipliers (cost per minute of delay)
PENALTY_NORMAL: int = 10
PENALTY_HOT: int = 100


class KPICalculator:
    """
    Compute all KPIs and build Gantt data from a solved schedule.

    Parameters
    ----------
    assignments     : List of AssignedOp from SolverResult.
    lots            : Original LotInput list (for due times, priorities, weights).
    machines        : MachineInput list (for names, tool types).
    horizon_minutes : Schedule horizon used by the solver.
    schedule_result_id : DB id of the ScheduleResult row being described.

    Usage::

        calc = KPICalculator(assignments, lots, machines, horizon, result_id)
        kpis = calc.compute_kpis()          # KPIResponse
        gantt = calc.build_gantt_chart()    # GanttChart
    """

    def __init__(
        self,
        assignments: list[AssignedOp],
        lots: list[LotInput],
        machines: list[MachineInput],
        horizon_minutes: int,
        schedule_result_id: int,
        # Additional context needed for Gantt labels
        op_recipe_map: dict[int, int] | None = None,          # op_id → recipe_id
        recipe_name_map: dict[int, str] | None = None,        # recipe_id → name
        recipe_stage_map: dict[int, str] | None = None,       # recipe_id → stage
    ) -> None:
        self._assignments = assignments
        self._lots = lots
        self._machines = machines
        self._horizon = horizon_minutes
        self._schedule_result_id = schedule_result_id
        self._op_recipe_map: dict[int, int] = op_recipe_map or {}
        self._recipe_name_map: dict[int, str] = recipe_name_map or {}
        self._recipe_stage_map: dict[int, str] = recipe_stage_map or {}

        # Build fast lookup maps
        self._lot_map: dict[int, LotInput] = {lot.id: lot for lot in lots}
        self._machine_map: dict[int, MachineInput] = {m.id: m for m in machines}
        self._by_lot: dict[int, list[AssignedOp]] = {}
        self._by_machine: dict[int, list[AssignedOp]] = {}
        for a in assignments:
            self._by_lot.setdefault(a.lot_id, []).append(a)
            self._by_machine.setdefault(a.machine_id, []).append(a)

    # -----------------------------------------------------------------------
    # Public interface
    # -----------------------------------------------------------------------

    def compute_kpis(self) -> KPIResponse:
        """Compute and return the full KPI response object."""
        makespan = self._compute_makespan()
        machine_util = self._compute_machine_utilization(makespan)
        lot_tard = self._compute_lot_tardiness()

        total_idle = sum(mu.idle_minutes for mu in machine_util)
        avg_util = float(np.mean([mu.utilization_pct for mu in machine_util])) if machine_util else 0.0
        total_wt = sum(lt.delay_minutes * self._lot_map[lt.lot_id].weight for lt in lot_tard)
        total_penalty = sum(lt.penalty_cost for lt in lot_tard)
        normal_penalty = sum(lt.penalty_cost for lt in lot_tard if lt.priority.value == "NORMAL")
        hot_penalty = sum(lt.penalty_cost for lt in lot_tard if lt.priority.value == "HOT")

        return KPIResponse(
            schedule_result_id=self._schedule_result_id,
            status="OPTIMAL",  # caller overrides with actual status
            makespan_minutes=makespan,
            total_idle_minutes=total_idle,
            avg_machine_utilization_pct=round(avg_util, 2),
            total_weighted_tardiness=round(total_wt, 4),
            total_penalty_cost=round(total_penalty, 2),
            normal_lot_penalty=round(normal_penalty, 2),
            hot_lot_penalty=round(hot_penalty, 2),
            machine_utilization=machine_util,
            lot_tardiness=lot_tard,
        )

    def build_gantt_chart(self) -> GanttChart:
        """Build the Gantt chart JSON structure."""
        tasks: list[GanttTask] = []

        for a in self._assignments:
            lot = self._lot_map.get(a.lot_id)
            machine = self._machine_map.get(a.machine_id)
            if lot is None or machine is None:
                continue

            recipe_id = self._op_recipe_map.get(a.operation_id, -1)
            recipe_name = self._recipe_name_map.get(recipe_id, f"RECIPE-{recipe_id}")
            stage_str = self._recipe_stage_map.get(recipe_id, "LITHOGRAPHY")

            try:
                stage = OperationStage(stage_str)
            except ValueError:
                stage = OperationStage.LITHOGRAPHY

            tasks.append(
                GanttTask(
                    lot_id=a.lot_id,
                    lot_name=lot.name,
                    operation_id=a.operation_id,
                    sequence_num=a.sequence_num,
                    machine_id=a.machine_id,
                    machine_name=machine.name,
                    recipe_id=recipe_id,
                    recipe_name=recipe_name,
                    stage=stage,
                    is_hot=lot.priority == "HOT",
                    start_minutes=a.start_minutes,
                    end_minutes=a.end_minutes,
                    duration_minutes=a.end_minutes - a.start_minutes,
                    setup_time_minutes=a.setup_time_minutes,
                )
            )

        # Sort by start time for frontend convenience
        tasks.sort(key=lambda t: (t.start_minutes, t.machine_id))
        makespan = self._compute_makespan()

        return GanttChart(
            schedule_result_id=self._schedule_result_id,
            horizon_minutes=self._horizon,
            makespan_minutes=makespan,
            tasks=tasks,
        )

    def compute_kpi_dict(self) -> dict[str, Any]:
        """Serialise KPIResponse to a plain dict for DB storage (JSON column)."""
        return self.compute_kpis().model_dump()

    def compute_gantt_dict(self) -> dict[str, Any]:
        """Serialise GanttChart to a plain dict for DB storage (JSON column)."""
        return self.build_gantt_chart().model_dump()

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _compute_makespan(self) -> int:
        """Return the max end time across all assignments."""
        if not self._assignments:
            return 0
        return max(a.end_minutes for a in self._assignments)

    def _compute_machine_utilization(self, makespan: int) -> list[MachineUtilization]:
        """Compute per-machine busy/idle/utilization."""
        results: list[MachineUtilization] = []
        effective_span = makespan if makespan > 0 else 1

        for machine in self._machines:
            ops = self._by_machine.get(machine.id, [])
            busy = sum(a.end_minutes - a.start_minutes for a in ops)
            idle = max(0, effective_span - busy)
            util_pct = round((busy / effective_span) * 100, 2)
            results.append(
                MachineUtilization(
                    machine_id=machine.id,
                    machine_name=machine.name,
                    busy_minutes=busy,
                    idle_minutes=idle,
                    utilization_pct=util_pct,
                )
            )

        return sorted(results, key=lambda m: m.utilization_pct, reverse=True)

    def _compute_lot_tardiness(self) -> list[LotTardiness]:
        """Compute per-lot tardiness and financial penalty."""
        results: list[LotTardiness] = []

        for lot in self._lots:
            ops = self._by_lot.get(lot.id, [])
            if not ops:
                # Lot was not scheduled — treat as maximally tardy
                completion = self._horizon
            else:
                completion = max(a.end_minutes for a in ops)

            delay = max(0, completion - lot.due_time_minutes)
            is_tardy = delay > 0
            mult = PENALTY_HOT if lot.priority == "HOT" else PENALTY_NORMAL
            penalty = mult * delay

            # Import the Pydantic enum for priority
            from models.models import LotPriority
            try:
                priority_enum = LotPriority(lot.priority)
            except ValueError:
                priority_enum = LotPriority.NORMAL

            results.append(
                LotTardiness(
                    lot_id=lot.id,
                    lot_name=lot.name,
                    priority=priority_enum,
                    completion_minutes=completion,
                    due_time_minutes=lot.due_time_minutes,
                    delay_minutes=delay,
                    is_tardy=is_tardy,
                    penalty_cost=float(penalty),
                )
            )

        return sorted(results, key=lambda lt: lt.penalty_cost, reverse=True)
