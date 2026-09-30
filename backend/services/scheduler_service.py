"""
services/scheduler_service.py

NOTE: Real-world datasets like SMT2020 have 300-500+ operations per lot.
Use max_ops_per_lot in ScheduleRequest to slice to the first N steps for
the CP-SAT solver (recommended: 5-15 for interactive use, 50+ for batch).

Orchestration layer for FabFlow AI.

This service mediates between:
  - The database (SQLAlchemy session)
  - The OR-Tools scheduling engine (FabSchedulerEngine)
  - The schedule validator (ScheduleValidator)
  - The KPI calculator (KPICalculator)
  - The discrete-event simulator (FabSimulator)

It is the single source of truth for any operation that crosses
multiple subsystem boundaries.  All API endpoint handlers import
only from this module — not directly from engine/validator/kpis.

Public methods
--------------
SchedulerService.run_schedule(request, db)
    → Reads lots + machines from DB
    → Calls FabSchedulerEngine
    → Validates output
    → Computes KPIs + Gantt
    → Persists ScheduleResult + ScheduledOperations
    → Returns ScheduleResponse

SchedulerService.get_schedule(schedule_id, db)
    → Loads ScheduleResult from DB
    → Returns ScheduleResponse

SchedulerService.get_kpis(schedule_id, db)
    → Reconstructs KPIs from saved assignments in DB
    → Returns KPIResponse

SchedulerService.run_simulation(request, db)
    → Loads saved schedule + lot/machine data
    → Runs FabSimulator
    → Returns SimulationResponse
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, selectinload

from analytics.kpis import KPICalculator
from database.session import get_db
from models.models import (
    Lot,
    Machine,
    MachineFailure,
    MaintenanceWindow,
    Operation,
    Recipe,
    ScheduleResult,
    ScheduledOperation,
    ScheduleStatus,
    SetupTime,
)
from scheduler.engine import (
    AssignedOp,
    FabSchedulerEngine,
    LotInput,
    MachineInput,
    OperationInput,
    SetupTimeInput,
)
from scheduler.validator import ScheduleValidator
from schemas.schemas import (
    KPIResponse,
    ScheduleRequest,
    ScheduleResponse,
    SimulationRequest,
    SimulationResponse,
)
from simulation.simulator import FabSimulator

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Application service orchestrating the full scheduling pipeline.

    All methods are stateless class-methods operating on an injected
    SQLAlchemy session, following the repository pattern.
    """

    # -----------------------------------------------------------------------
    # Run schedule
    # -----------------------------------------------------------------------

    @classmethod
    def run_schedule(
        cls, request: ScheduleRequest, db: Session
    ) -> ScheduleResponse:
        """
        Execute the full scheduling pipeline:
        load → solve → validate → compute KPIs → persist → return.
        """
        # 1. Load data from DB
        lots_input, machines_input, setup_input = cls._load_solver_inputs(request, db)

        if not lots_input:
            raise ValueError("No schedulable lots found. Please create lots with operations first.")
        if not machines_input:
            raise ValueError("No active machines found. Please create machines first.")

        logger.info(
            "Starting schedule run: %d lots, %d machines, horizon=%d min",
            len(lots_input),
            len(machines_input),
            request.horizon_minutes,
        )

        # 2. Create a pending ScheduleResult row
        schedule_result = ScheduleResult(
            status=ScheduleStatus.RUNNING,
            solver_params=request.model_dump(),
        )
        db.add(schedule_result)
        db.flush()  # get the auto-generated id without committing

        try:
            # 3. Run OR-Tools solver
            engine = FabSchedulerEngine(
                lots=lots_input,
                machines=machines_input,
                setup_times=setup_input,
                weights=request.weights,
                horizon_minutes=request.horizon_minutes,
                time_limit_seconds=request.solver_time_limit_seconds,
            )
            solver_result = engine.solve()

            # 4. Validate the solution
            setup_map = {
                (s.from_recipe_id, s.to_recipe_id, s.tool_type): s.setup_minutes
                for s in setup_input
            }
            validator = ScheduleValidator(
                assignments=solver_result.assignments,
                lots=lots_input,
                machines=machines_input,
                setup_map=setup_map,
                horizon_minutes=request.horizon_minutes,
            )
            validation_result = validator.validate()
            if not validation_result.is_valid:
                violation_summary = [
                    {"code": v.code, "message": v.message}
                    for v in validation_result.violations
                    if v.severity == "ERROR"
                ]
                logger.error("Schedule validation failed: %s", violation_summary)

            # 5. Compute KPIs and Gantt chart
            op_recipe_map, recipe_name_map, recipe_stage_map = cls._build_recipe_maps(
                lots_input, db
            )
            kpi_calc = KPICalculator(
                assignments=solver_result.assignments,
                lots=lots_input,
                machines=machines_input,
                horizon_minutes=request.horizon_minutes,
                schedule_result_id=schedule_result.id,
                op_recipe_map=op_recipe_map,
                recipe_name_map=recipe_name_map,
                recipe_stage_map=recipe_stage_map,
            )
            kpi_dict = kpi_calc.compute_kpi_dict()
            gantt_dict = kpi_calc.compute_gantt_dict()

            # 6. Determine final status
            status_str = solver_result.status
            if status_str in ("OPTIMAL", "FEASIBLE") and not validation_result.is_valid:
                status_str = "FEASIBLE"  # downgrade if validation errors exist

            try:
                db_status = ScheduleStatus(status_str)
            except ValueError:
                db_status = ScheduleStatus.FAILED

            # 7. Update ScheduleResult row
            schedule_result.status = db_status
            schedule_result.makespan_minutes = solver_result.makespan_minutes
            schedule_result.solver_wall_time_seconds = solver_result.wall_time_seconds
            schedule_result.objective_value = solver_result.objective_value
            schedule_result.kpi_data = kpi_dict
            schedule_result.gantt_data = gantt_dict
            schedule_result.solver_stats = solver_result.solver_stats

            # 8. Persist ScheduledOperation rows
            cls._persist_scheduled_operations(
                solver_result.assignments,
                schedule_result.id,
                op_recipe_map,
                db,
            )

            db.commit()
            db.refresh(schedule_result)
            logger.info(
                "Schedule run completed: id=%d status=%s makespan=%d min",
                schedule_result.id,
                schedule_result.status,
                schedule_result.makespan_minutes,
            )

        except Exception as exc:
            schedule_result.status = ScheduleStatus.FAILED
            db.commit()
            logger.exception("Schedule run failed: %s", exc)
            raise

        return ScheduleResponse.model_validate(schedule_result)

    # -----------------------------------------------------------------------
    # Retrieve schedule
    # -----------------------------------------------------------------------

    @classmethod
    def get_schedule(cls, schedule_id: int, db: Session) -> ScheduleResponse:
        """Load and return a saved ScheduleResult."""
        result = db.get(ScheduleResult, schedule_id)
        if result is None:
            raise LookupError(f"ScheduleResult {schedule_id} not found")
        return ScheduleResponse.model_validate(result)

    @classmethod
    def list_schedules(cls, db: Session, limit: int = 20) -> list[ScheduleResponse]:
        """Return the most recent schedule results."""
        results = (
            db.query(ScheduleResult)
            .order_by(ScheduleResult.created_at.desc())
            .limit(limit)
            .all()
        )
        return [ScheduleResponse.model_validate(r) for r in results]

    # -----------------------------------------------------------------------
    # KPI retrieval
    # -----------------------------------------------------------------------

    @classmethod
    def get_kpis(cls, schedule_id: int, db: Session) -> KPIResponse:
        """Return pre-computed KPIs stored in the ScheduleResult JSON column."""
        result = db.get(ScheduleResult, schedule_id)
        if result is None:
            raise LookupError(f"ScheduleResult {schedule_id} not found")
        if result.kpi_data is None:
            raise ValueError(f"ScheduleResult {schedule_id} has no KPI data")

        # Reconstruct KPIResponse from stored JSON (avoids re-computation)
        kpi_data = result.kpi_data
        kpi_data["status"] = result.status.value
        return KPIResponse(**kpi_data)

    # -----------------------------------------------------------------------
    # Simulation
    # -----------------------------------------------------------------------

    @classmethod
    def run_simulation(
        cls, request: SimulationRequest, db: Session
    ) -> SimulationResponse:
        """Load the base schedule and execute Monte Carlo simulation."""
        schedule_result = db.get(ScheduleResult, request.schedule_result_id)
        if schedule_result is None:
            raise LookupError(
                f"ScheduleResult {request.schedule_result_id} not found"
            )

        # Rebuild assignments from DB
        assignments = cls._load_assignments_from_db(request.schedule_result_id, db)

        # Load lots and machines
        lots_input, machines_input, _ = cls._load_solver_inputs_all(db)

        simulator = FabSimulator(
            assignments=assignments,
            lots=lots_input,
            machines=machines_input,
            request=request,
        )
        return simulator.run()

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @classmethod
    def _load_solver_inputs(
        cls, request: ScheduleRequest, db: Session
    ) -> tuple[list[LotInput], list[MachineInput], list[SetupTimeInput]]:
        """Load lots, machines, and setup times from DB, applying request filters."""
        from models.models import MachineStatus

        # Lots
        lot_query = (
            db.query(Lot)
            .options(selectinload(Lot.operations).selectinload(Operation.recipe))
        )
        if request.lot_ids:
            lot_query = lot_query.filter(Lot.id.in_(request.lot_ids))
        db_lots = lot_query.all()

        # Machines (active only)
        db_machines = (
            db.query(Machine)
            .filter(Machine.status == MachineStatus.ACTIVE)
            .options(
                selectinload(Machine.maintenance_windows),
                selectinload(Machine.failures),
            )
            .all()
        )

        # Setup times
        db_setups = db.query(SetupTime).all()

        lots_input = cls._convert_lots(db_lots, max_ops_per_lot=request.max_ops_per_lot)

        # ── KEY OPTIMISATION ─────────────────────────────────────────────────
        # SMT2020 has 1443 machines but a sliced schedule may use only ~50-200.
        # Passing all 1443 to CP-SAT creates a huge model that never solves.
        # Filter: keep only machines referenced in candidate_machine_ids.
        # ─────────────────────────────────────────────────────────────────────
        needed_machine_ids: set[int] = set()
        for lot in lots_input:
            for op in lot.operations:
                needed_machine_ids.update(op.candidate_machine_ids)

        db_machines_filtered = [m for m in db_machines if m.id in needed_machine_ids]
        logger.info(
            "Machine filter: %d total active → %d needed by scheduled ops",
            len(db_machines), len(db_machines_filtered),
        )

        machines_input = cls._convert_machines(
            db_machines_filtered, request, request.horizon_minutes
        )
        setup_input = [
            SetupTimeInput(
                from_recipe_id=s.from_recipe_id,
                to_recipe_id=s.to_recipe_id,
                tool_type=s.tool_type,
                setup_minutes=s.setup_minutes,
            )
            for s in db_setups
        ]
        return lots_input, machines_input, setup_input

    @classmethod
    def _load_solver_inputs_all(
        cls, db: Session
    ) -> tuple[list[LotInput], list[MachineInput], list[SetupTimeInput]]:
        """Load all lots and machines (no filter) — used by simulation."""
        from models.models import MachineStatus

        db_lots = (
            db.query(Lot)
            .options(selectinload(Lot.operations).selectinload(Operation.recipe))
            .all()
        )
        db_machines = (
            db.query(Machine)
            .options(
                selectinload(Machine.maintenance_windows),
                selectinload(Machine.failures),
            )
            .all()
        )
        db_setups = db.query(SetupTime).all()

        lots_input = cls._convert_lots(db_lots)
        machines_input = cls._convert_machines_simple(db_machines)
        setup_input = [
            SetupTimeInput(
                from_recipe_id=s.from_recipe_id,
                to_recipe_id=s.to_recipe_id,
                tool_type=s.tool_type,
                setup_minutes=s.setup_minutes,
            )
            for s in db_setups
        ]
        return lots_input, machines_input, setup_input

    @staticmethod
    def _convert_lots(
        db_lots: list[Lot],
        max_ops_per_lot: int | None = None,
    ) -> list[LotInput]:
        """Convert ORM Lot rows into solver LotInput DTOs.

        Args:
            db_lots: ORM Lot objects (must have operations + recipe loaded).
            max_ops_per_lot: If set, only the first N operations per lot are
                included. Critical for real-world datasets like SMT2020 where
                lots have 300-500+ steps that would overwhelm the CP-SAT solver.
        """
        result: list[LotInput] = []
        for lot in db_lots:
            sorted_ops = sorted(lot.operations, key=lambda o: o.sequence_num)

            # Apply operation slice for large real-world routes
            if max_ops_per_lot:
                sorted_ops = sorted_ops[:max_ops_per_lot]

            ops = []
            for op in sorted_ops:
                recipe = op.recipe
                proc_time = op.processing_time_minutes or recipe.nominal_cycle_time_minutes
                candidate_ids: list[int] = op.candidate_machine_ids or []

                # Skip operations with no eligible machines — solver would fail
                if not candidate_ids:
                    logger.warning(
                        "Op %d (lot=%d seq=%d recipe=%s) has no candidate machines — skipped",
                        op.id, lot.id, op.sequence_num, recipe.name,
                    )
                    continue

                ops.append(
                    OperationInput(
                        id=op.id,
                        lot_id=lot.id,
                        sequence_num=op.sequence_num,
                        recipe_id=recipe.id,
                        recipe_name=recipe.name,
                        stage=recipe.stage.value,
                        processing_time_minutes=max(1, proc_time),
                        candidate_machine_ids=candidate_ids,
                    )
                )

            if ops:
                logger.info(
                    "Lot %s (%s): %d ops scheduled (route has %d total)",
                    lot.name, lot.priority.value, len(ops), len(lot.operations),
                )
                result.append(
                    LotInput(
                        id=lot.id,
                        name=lot.name,
                        priority=lot.priority.value,
                        release_time_minutes=lot.release_time_minutes,
                        due_time_minutes=lot.due_time_minutes,
                        weight=lot.weight,
                        operations=ops,
                    )
                )
        return result


    @staticmethod
    def _convert_machines(
        db_machines: list[Machine],
        request: ScheduleRequest,
        horizon_minutes: int,
    ) -> list[MachineInput]:
        """Convert ORM Machine rows into solver MachineInput DTOs with blocked intervals."""
        result: list[MachineInput] = []
        for m in db_machines:
            blocked: list[tuple[int, int]] = []

            if request.include_maintenance:
                for mw in m.maintenance_windows:
                    # Convert datetime → horizon-relative minutes
                    # For simplicity: if maintenance is stored as absolute datetimes,
                    # we use a reference epoch or assume start=0.
                    # Here we treat them as horizon-relative minutes stored as epoch offsets.
                    blk_start = int(mw.start_time.timestamp() // 60) if mw.start_time else 0
                    blk_end = int(mw.end_time.timestamp() // 60) if mw.end_time else 0
                    if 0 <= blk_start < horizon_minutes and blk_end > blk_start:
                        blocked.append((blk_start, min(blk_end, horizon_minutes)))

            if request.include_failures:
                for f in m.failures:
                    blk_start = int(f.start_time.timestamp() // 60) if f.start_time else 0
                    blk_end = blk_start + f.duration_minutes
                    if 0 <= blk_start < horizon_minutes and blk_end > blk_start:
                        blocked.append((blk_start, min(blk_end, horizon_minutes)))

            result.append(
                MachineInput(
                    id=m.id,
                    name=m.name,
                    tool_type=m.tool_type,
                    candidate_stages=[s for s in (m.candidate_stages or [])],
                    blocked_intervals=blocked,
                )
            )
        return result

    @staticmethod
    def _convert_machines_simple(db_machines: list[Machine]) -> list[MachineInput]:
        """Convert machines without blocked intervals (used in simulation)."""
        return [
            MachineInput(
                id=m.id,
                name=m.name,
                tool_type=m.tool_type,
                candidate_stages=list(m.candidate_stages or []),
                blocked_intervals=[],
            )
            for m in db_machines
        ]

    @staticmethod
    def _build_recipe_maps(
        lots_input: list[LotInput], db: Session
    ) -> tuple[dict[int, int], dict[int, str], dict[int, str]]:
        """Return op→recipe_id, recipe_id→name, recipe_id→stage maps."""
        op_recipe_map: dict[int, int] = {}
        recipe_ids: set[int] = set()
        for lot in lots_input:
            for op in lot.operations:
                op_recipe_map[op.id] = op.recipe_id
                recipe_ids.add(op.recipe_id)

        db_recipes = db.query(Recipe).filter(Recipe.id.in_(recipe_ids)).all()
        recipe_name_map: dict[int, str] = {r.id: r.name for r in db_recipes}
        recipe_stage_map: dict[int, str] = {r.id: r.stage.value for r in db_recipes}
        return op_recipe_map, recipe_name_map, recipe_stage_map

    @staticmethod
    def _persist_scheduled_operations(
        assignments: list[AssignedOp],
        schedule_result_id: int,
        op_recipe_map: dict[int, int],
        db: Session,
    ) -> None:
        """Bulk-insert ScheduledOperation rows for the given schedule run."""
        for a in assignments:
            recipe_id = op_recipe_map.get(a.operation_id, -1)
            sop = ScheduledOperation(
                schedule_result_id=schedule_result_id,
                lot_id=a.lot_id,
                operation_id=a.operation_id,
                machine_id=a.machine_id,
                recipe_id=recipe_id,
                sequence_num=a.sequence_num,
                start_minutes=a.start_minutes,
                end_minutes=a.end_minutes,
                setup_time_minutes=a.setup_time_minutes,
            )
            db.add(sop)

    @staticmethod
    def _load_assignments_from_db(
        schedule_result_id: int, db: Session
    ) -> list[AssignedOp]:
        """Reconstruct AssignedOp list from persisted ScheduledOperation rows."""
        rows = (
            db.query(ScheduledOperation)
            .filter(ScheduledOperation.schedule_result_id == schedule_result_id)
            .all()
        )
        return [
            AssignedOp(
                operation_id=row.operation_id,
                lot_id=row.lot_id,
                machine_id=row.machine_id,
                sequence_num=row.sequence_num,
                start_minutes=row.start_minutes,
                end_minutes=row.end_minutes,
                processing_time_minutes=row.end_minutes - row.start_minutes - row.setup_time_minutes,
                setup_time_minutes=row.setup_time_minutes,
            )
            for row in rows
        ]
