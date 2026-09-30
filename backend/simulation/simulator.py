"""
simulation/simulator.py

Discrete-Event Monte Carlo Simulator for FabFlow AI.

Architecture
------------
Uses SimPy (a discrete-event simulation library) as the simulation clock
and resource manager.  For each replication:

1. Each machine is modelled as a SimPy Resource (capacity=1).
2. Each lot is a SimPy process that sequentially requests machines for its
   operations in lot.sequence_num order (respecting precedence).
3. Stochastic machine failures are injected via separate processes that
   periodically preempt the machine resource according to:
       Time-Between-Failures ~ Exponential(mean = MTBF)
       Time-To-Repair        ~ Exponential(mean = MTTR)
4. When a machine fails during an active operation, the operation is
   interrupted and rescheduled (the remaining processing time is preserved).
5. KPIs (actual makespan, disruptions, idle time added, penalty) are
   collected at end of simulation.
6. Multiple Monte Carlo replications are aggregated into a
   SimulationResponse.

This module is pure-Python and has no DB access; all DB interaction
is handled in services/scheduler_service.py.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any

import simpy  # type: ignore[import]

from scheduler.engine import AssignedOp, LotInput, MachineInput
from schemas.schemas import (
    SimulationFailureConfig,
    SimulationRequest,
    SimulationResponse,
    SimulationRunStats,
)

logger = logging.getLogger(__name__)

# Financial penalty constants (match KPI calculator)
PENALTY_NORMAL: int = 10
PENALTY_HOT: int = 100


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class _OpTask:
    """Executable operation task for the simulator."""

    operation_id: int
    lot_id: int
    machine_id: int
    sequence_num: int
    processing_time_minutes: int
    recipe_id: int


@dataclass
class _SimLotResult:
    """Per-lot outcome from a single replication."""

    lot_id: int
    completion_time: float
    due_time: float
    priority: str
    weight: float


# ---------------------------------------------------------------------------
# SimPy Simulation Engine
# ---------------------------------------------------------------------------


class FabSimulator:
    """
    Monte Carlo Discrete-Event Simulator for fab scheduling.

    Parameters
    ----------
    assignments         : Solved schedule allocations (from OR-Tools engine).
    lots                : Original lot definitions (for due times and priorities).
    machines            : Machine definitions.
    request             : SimulationRequest (horizon, seeds, failure configs, replications).

    Usage::

        sim = FabSimulator(assignments, lots, machines, request)
        response = sim.run()
    """

    def __init__(
        self,
        assignments: list[AssignedOp],
        lots: list[LotInput],
        machines: list[MachineInput],
        request: SimulationRequest,
    ) -> None:
        self._assignments = assignments
        self._lots = lots
        self._machines = machines
        self._request = request

        self._lot_map: dict[int, LotInput] = {lot.id: lot for lot in lots}
        self._machine_map: dict[int, MachineInput] = {m.id: m for m in machines}

        # Group assignments by lot, ordered by sequence
        self._lot_ops: dict[int, list[AssignedOp]] = {}
        for a in sorted(assignments, key=lambda x: x.sequence_num):
            self._lot_ops.setdefault(a.lot_id, []).append(a)

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    def run(self) -> SimulationResponse:
        """Execute all Monte Carlo replications and return aggregated results."""
        replication_stats: list[SimulationRunStats] = []
        base_seed = self._request.random_seed or 42

        for rep in range(self._request.num_replications):
            seed = base_seed + rep
            stats = self._run_replication(rep + 1, seed)
            replication_stats.append(stats)
            logger.info(
                "Replication %d/%d — makespan=%d min  penalty=$%.2f  disruptions=%d",
                rep + 1,
                self._request.num_replications,
                stats.actual_makespan_minutes,
                stats.total_penalty_cost,
                stats.schedule_disruptions,
            )

        # Aggregate
        makespans = [s.actual_makespan_minutes for s in replication_stats]
        penalties = [s.total_penalty_cost for s in replication_stats]
        disruptions = [s.schedule_disruptions for s in replication_stats]

        return SimulationResponse(
            schedule_result_id=self._request.schedule_result_id,
            num_replications=self._request.num_replications,
            avg_makespan_minutes=float(sum(makespans) / len(makespans)),
            max_makespan_minutes=max(makespans),
            min_makespan_minutes=min(makespans),
            avg_penalty_cost=float(sum(penalties) / len(penalties)),
            avg_disruptions=float(sum(disruptions) / len(disruptions)),
            replications=replication_stats,
        )

    # -----------------------------------------------------------------------
    # Single replication
    # -----------------------------------------------------------------------

    def _run_replication(self, rep_number: int, seed: int) -> SimulationRunStats:
        """Run one SimPy replication and collect metrics."""
        rng = random.Random(seed)
        env = simpy.Environment()

        # Create one SimPy Resource per machine
        resources: dict[int, simpy.Resource] = {
            m.id: simpy.Resource(env, capacity=1) for m in self._machines
        }

        # Shared mutable state collected during simulation
        lot_results: list[_SimLotResult] = []
        disruption_count: list[int] = [0]
        extra_idle_minutes: list[float] = [0.0]

        # Failure config lookup
        failure_cfg_map: dict[int, SimulationFailureConfig] = {
            cfg.machine_id: cfg for cfg in self._request.failure_configs
        }

        # Launch failure injection processes
        for machine in self._machines:
            cfg = failure_cfg_map.get(machine.id)
            if cfg is not None:
                env.process(
                    self._failure_process(
                        env,
                        resources[machine.id],
                        cfg,
                        rng,
                        disruption_count,
                        extra_idle_minutes,
                    )
                )

        # Launch lot processes
        for lot in self._lots:
            ops = self._lot_ops.get(lot.id)
            if not ops:
                continue
            env.process(
                self._lot_process(
                    env,
                    lot,
                    ops,
                    resources,
                    lot_results,
                )
            )

        env.run(until=self._request.simulation_horizon_minutes)

        # Compute final metrics
        makespan = int(env.now) if lot_results else 0
        if lot_results:
            makespan = int(max(lr.completion_time for lr in lot_results))

        total_penalty = 0.0
        for lr in lot_results:
            delay = max(0.0, lr.completion_time - lr.due_time)
            mult = PENALTY_HOT if lr.priority == "HOT" else PENALTY_NORMAL
            total_penalty += mult * delay

        # Build minimal Gantt data for this replication (simplified)
        gantt_data: dict[str, Any] = {
            "replication": rep_number,
            "seed": seed,
            "lot_completions": [
                {
                    "lot_id": lr.lot_id,
                    "completion_minutes": round(lr.completion_time, 2),
                    "due_minutes": lr.due_time,
                    "delay_minutes": round(max(0.0, lr.completion_time - lr.due_time), 2),
                }
                for lr in lot_results
            ],
        }

        return SimulationRunStats(
            replication=rep_number,
            actual_makespan_minutes=makespan,
            schedule_disruptions=disruption_count[0],
            total_idle_time_added_minutes=int(extra_idle_minutes[0]),
            total_penalty_cost=round(total_penalty, 2),
            gantt_data=gantt_data,
        )

    # -----------------------------------------------------------------------
    # SimPy processes
    # -----------------------------------------------------------------------

    def _lot_process(
        self,
        env: simpy.Environment,
        lot: LotInput,
        ops: list[AssignedOp],
        resources: dict[int, simpy.Resource],
        lot_results: list[_SimLotResult],
    ):  # type: ignore[override]
        """SimPy generator: process a lot's operations sequentially."""
        # Wait until the lot is released
        if lot.release_time_minutes > 0:
            yield env.timeout(max(0, lot.release_time_minutes - env.now))

        for op in sorted(ops, key=lambda a: a.sequence_num):
            resource = resources.get(op.machine_id)
            if resource is None:
                continue

            proc_time = op.processing_time_minutes
            attempts = 0
            completed = False

            while not completed and attempts < 10:
                attempts += 1
                req = resource.request()
                yield req
                try:
                    yield env.timeout(proc_time)
                    completed = True
                except simpy.Interrupt:
                    # Machine failed mid-operation: release and retry
                    remaining = proc_time - (env.now - req.usage_since if hasattr(req, "usage_since") else proc_time)
                    proc_time = max(1, int(remaining))
                    resource.release(req)
                    continue
                finally:
                    if req in resource.users:
                        resource.release(req)

        lot_results.append(
            _SimLotResult(
                lot_id=lot.id,
                completion_time=env.now,
                due_time=lot.due_time_minutes,
                priority=lot.priority,
                weight=lot.weight,
            )
        )

    def _failure_process(
        self,
        env: simpy.Environment,
        resource: simpy.Resource,
        cfg: SimulationFailureConfig,
        rng: random.Random,
        disruption_count: list[int],
        extra_idle: list[float],
    ):  # type: ignore[override]
        """
        SimPy generator: inject random machine failures.

        Failure inter-arrival time ~ Exponential(MTBF in minutes)
        Repair time                ~ Exponential(MTTR in minutes)
        """
        mtbf_minutes = cfg.mean_time_between_failures_hours * 60.0
        mttr_minutes = cfg.mean_time_to_repair_minutes

        while True:
            # Time until next failure
            ttf = rng.expovariate(1.0 / mtbf_minutes)
            yield env.timeout(ttf)

            # Seize the machine to simulate it being down
            repair_time = rng.expovariate(1.0 / mttr_minutes)
            req = resource.request(priority=-1)  # type: ignore[call-arg]
            yield req
            extra_idle[0] += repair_time
            disruption_count[0] += 1
            logger.debug("Machine failure at t=%.1f, repair=%.1f min", env.now, repair_time)
            yield env.timeout(repair_time)
            resource.release(req)
