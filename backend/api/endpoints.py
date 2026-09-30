"""
api/endpoints.py

REST API routers for FabFlow AI.

Router map
----------
/api/health                     GET  — liveness + DB ping
/api/machines                   GET  — list all machines
/api/machines                   POST — create machine
/api/machines/{id}              GET  — get machine by id
/api/machines/{id}              PATCH — update machine
/api/machines/{id}              DELETE — delete machine
/api/machines/{id}/maintenance  POST  — add maintenance window
/api/machines/{id}/failures     POST  — log machine failure
/api/recipes                    GET / POST
/api/recipes/{id}               GET / PATCH / DELETE
/api/setup-times                GET / POST
/api/jobs                       GET  — list lots (with operations)
/api/jobs                       POST — create lot + nested operations
/api/jobs/{id}                  GET / PATCH / DELETE
/api/schedule/run               POST — trigger solver
/api/schedule/{id}              GET  — retrieve saved schedule
/api/schedule                   GET  — list recent schedules
/api/analytics/{id}             GET  — KPI report for a schedule
/api/simulation/run             POST — Monte Carlo simulation
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from database.session import get_db, ping_db
from models.models import (
    Lot,
    Machine,
    MachineFailure,
    MaintenanceWindow,
    MachineStatus,
    Operation,
    Recipe,
    SetupTime,
)
from schemas.schemas import (
    HealthResponse,
    KPIResponse,
    LotCreate,
    LotResponse,
    LotUpdate,
    MachineCreate,
    MachineFailureCreate,
    MachineFailureResponse,
    MachineResponse,
    MachineUpdate,
    MaintenanceWindowCreate,
    MaintenanceWindowResponse,
    RecipeCreate,
    RecipeResponse,
    RecipeUpdate,
    ScheduleRequest,
    ScheduleResponse,
    SetupTimeCreate,
    SetupTimeResponse,
    SimulationRequest,
    SimulationResponse,
)
from services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)

router = APIRouter()


# ===========================================================================
# Health
# ===========================================================================


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Liveness and DB connectivity check",
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Return API status and whether the database is reachable."""
    return HealthResponse(
        status="ok",
        db_connected=ping_db(),
        version="1.0.0",
    )


# ===========================================================================
# Machines
# ===========================================================================

machines_router = APIRouter(prefix="/machines", tags=["Machines"])


@machines_router.get(
    "",
    response_model=list[MachineResponse],
    summary="List all fab machines",
)
def list_machines(
    status: MachineStatus | None = Query(None, description="Filter by machine status"),
    tool_type: str | None = Query(None, description="Filter by tool type"),
    db: Session = Depends(get_db),
) -> list[MachineResponse]:
    """Retrieve all machines, optionally filtered by status or tool type."""
    q = db.query(Machine)
    if status:
        q = q.filter(Machine.status == status)
    if tool_type:
        q = q.filter(Machine.tool_type == tool_type)
    machines = q.order_by(Machine.name).all()
    return [MachineResponse.model_validate(m) for m in machines]


@machines_router.post(
    "",
    response_model=MachineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new fab machine",
)
def create_machine(
    body: MachineCreate, db: Session = Depends(get_db)
) -> MachineResponse:
    """Register a new machine in the fab."""
    existing = db.query(Machine).filter(Machine.name == body.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Machine with name '{body.name}' already exists (id={existing.id})",
        )
    machine = Machine(**body.model_dump())
    db.add(machine)
    db.flush()
    db.refresh(machine)
    return MachineResponse.model_validate(machine)


@machines_router.get(
    "/{machine_id}",
    response_model=MachineResponse,
    summary="Get machine by ID",
)
def get_machine(machine_id: int, db: Session = Depends(get_db)) -> MachineResponse:
    """Fetch a single machine by its primary key."""
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    return MachineResponse.model_validate(machine)


@machines_router.patch(
    "/{machine_id}",
    response_model=MachineResponse,
    summary="Update machine fields",
)
def update_machine(
    machine_id: int, body: MachineUpdate, db: Session = Depends(get_db)
) -> MachineResponse:
    """Partially update a machine (only provided fields are changed)."""
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(machine, field, value)
    db.flush()
    db.refresh(machine)
    return MachineResponse.model_validate(machine)


@machines_router.delete(
    "/{machine_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a machine",
)
def delete_machine(machine_id: int, db: Session = Depends(get_db)) -> None:
    """Permanently delete a machine and all its related data."""
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    db.delete(machine)


@machines_router.post(
    "/{machine_id}/maintenance",
    response_model=MaintenanceWindowResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a maintenance window to a machine",
)
def add_maintenance_window(
    machine_id: int,
    body: MaintenanceWindowCreate,
    db: Session = Depends(get_db),
) -> MaintenanceWindowResponse:
    """Schedule a planned maintenance downtime window for a machine."""
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    mw = MaintenanceWindow(**body.model_dump())
    mw.machine_id = machine_id
    db.add(mw)
    db.flush()
    db.refresh(mw)
    return MaintenanceWindowResponse.model_validate(mw)


@machines_router.post(
    "/{machine_id}/failures",
    response_model=MachineFailureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a machine failure event",
)
def log_machine_failure(
    machine_id: int,
    body: MachineFailureCreate,
    db: Session = Depends(get_db),
) -> MachineFailureResponse:
    """Record an unplanned machine failure (actual or simulated)."""
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    failure = MachineFailure(**body.model_dump())
    failure.machine_id = machine_id
    db.add(failure)
    db.flush()
    db.refresh(failure)
    return MachineFailureResponse.model_validate(failure)


# ===========================================================================
# Recipes
# ===========================================================================

recipes_router = APIRouter(prefix="/recipes", tags=["Recipes"])


@recipes_router.get(
    "",
    response_model=list[RecipeResponse],
    summary="List all recipes",
)
def list_recipes(db: Session = Depends(get_db)) -> list[RecipeResponse]:
    """Return all process recipes registered in the system."""
    recipes = db.query(Recipe).order_by(Recipe.name).all()
    return [RecipeResponse.model_validate(r) for r in recipes]


@recipes_router.post(
    "",
    response_model=RecipeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new recipe",
)
def create_recipe(body: RecipeCreate, db: Session = Depends(get_db)) -> RecipeResponse:
    """Register a new process recipe."""
    existing = db.query(Recipe).filter(Recipe.name == body.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recipe '{body.name}' already exists",
        )
    recipe = Recipe(**body.model_dump())
    db.add(recipe)
    db.flush()
    db.refresh(recipe)
    return RecipeResponse.model_validate(recipe)


@recipes_router.get(
    "/{recipe_id}",
    response_model=RecipeResponse,
    summary="Get recipe by ID",
)
def get_recipe(recipe_id: int, db: Session = Depends(get_db)) -> RecipeResponse:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
    return RecipeResponse.model_validate(recipe)


@recipes_router.patch(
    "/{recipe_id}",
    response_model=RecipeResponse,
    summary="Update a recipe",
)
def update_recipe(
    recipe_id: int, body: RecipeUpdate, db: Session = Depends(get_db)
) -> RecipeResponse:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(recipe, field, value)
    db.flush()
    db.refresh(recipe)
    return RecipeResponse.model_validate(recipe)


@recipes_router.delete(
    "/{recipe_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a recipe",
)
def delete_recipe(recipe_id: int, db: Session = Depends(get_db)) -> None:
    recipe = db.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"Recipe {recipe_id} not found")
    db.delete(recipe)


# ===========================================================================
# Setup Times
# ===========================================================================

setup_router = APIRouter(prefix="/setup-times", tags=["Setup Times"])


@setup_router.get(
    "",
    response_model=list[SetupTimeResponse],
    summary="List all sequence-dependent setup times",
)
def list_setup_times(db: Session = Depends(get_db)) -> list[SetupTimeResponse]:
    """Return the full sequence-dependent setup time matrix."""
    setups = db.query(SetupTime).all()
    return [SetupTimeResponse.model_validate(s) for s in setups]


@setup_router.post(
    "",
    response_model=SetupTimeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a setup time entry",
)
def create_setup_time(
    body: SetupTimeCreate, db: Session = Depends(get_db)
) -> SetupTimeResponse:
    """Register a new setup time between two recipes on a given tool type."""
    existing = (
        db.query(SetupTime)
        .filter(
            SetupTime.from_recipe_id == body.from_recipe_id,
            SetupTime.to_recipe_id == body.to_recipe_id,
            SetupTime.tool_type == body.tool_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup time entry already exists for this recipe transition",
        )
    setup = SetupTime(**body.model_dump())
    db.add(setup)
    db.flush()
    db.refresh(setup)
    return SetupTimeResponse.model_validate(setup)


# ===========================================================================
# Jobs (Lots)
# ===========================================================================

jobs_router = APIRouter(prefix="/jobs", tags=["Jobs (Lots)"])


@jobs_router.get(
    "",
    response_model=list[LotResponse],
    summary="List all wafer lots",
)
def list_lots(
    priority: str | None = Query(None, description="Filter by priority: NORMAL or HOT"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[LotResponse]:
    """Return all lots with their nested operations."""
    q = db.query(Lot).options(
        selectinload(Lot.operations).selectinload(Operation.recipe)
    )
    if priority:
        from models.models import LotPriority
        try:
            p = LotPriority(priority.upper())
            q = q.filter(Lot.priority == p)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")
    lots = q.order_by(Lot.name).limit(limit).all()
    return [LotResponse.model_validate(lot) for lot in lots]


@jobs_router.post(
    "",
    response_model=LotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new wafer lot with operations",
)
def create_lot(body: LotCreate, db: Session = Depends(get_db)) -> LotResponse:
    """
    Create a lot and its ordered operations in a single request.

    The `operations` list must be in processing order (ascending sequence_num).
    The standard fab flow is: LITHOGRAPHY → ETCH → DEPOSITION.
    """
    existing = db.query(Lot).filter(Lot.name == body.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lot '{body.name}' already exists",
        )

    lot_data = body.model_dump(exclude={"operations"})
    lot = Lot(**lot_data)
    db.add(lot)
    db.flush()

    for op_data in body.operations:
        # Validate recipe exists
        recipe = db.get(Recipe, op_data.recipe_id)
        if recipe is None:
            raise HTTPException(
                status_code=422,
                detail=f"Recipe id={op_data.recipe_id} not found",
            )
        op = Operation(lot_id=lot.id, **op_data.model_dump())
        db.add(op)

    db.flush()
    db.refresh(lot)
    lot_with_ops = (
        db.query(Lot)
        .options(selectinload(Lot.operations).selectinload(Operation.recipe))
        .filter(Lot.id == lot.id)
        .one()
    )
    return LotResponse.model_validate(lot_with_ops)


@jobs_router.get(
    "/{lot_id}",
    response_model=LotResponse,
    summary="Get lot by ID",
)
def get_lot(lot_id: int, db: Session = Depends(get_db)) -> LotResponse:
    lot = (
        db.query(Lot)
        .options(selectinload(Lot.operations).selectinload(Operation.recipe))
        .filter(Lot.id == lot_id)
        .first()
    )
    if lot is None:
        raise HTTPException(status_code=404, detail=f"Lot {lot_id} not found")
    return LotResponse.model_validate(lot)


@jobs_router.patch(
    "/{lot_id}",
    response_model=LotResponse,
    summary="Update lot fields",
)
def update_lot(
    lot_id: int, body: LotUpdate, db: Session = Depends(get_db)
) -> LotResponse:
    lot = db.get(Lot, lot_id)
    if lot is None:
        raise HTTPException(status_code=404, detail=f"Lot {lot_id} not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(lot, field, value)
    db.flush()
    lot_with_ops = (
        db.query(Lot)
        .options(selectinload(Lot.operations).selectinload(Operation.recipe))
        .filter(Lot.id == lot_id)
        .one()
    )
    return LotResponse.model_validate(lot_with_ops)


@jobs_router.delete(
    "/{lot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a lot",
)
def delete_lot(lot_id: int, db: Session = Depends(get_db)) -> None:
    lot = db.get(Lot, lot_id)
    if lot is None:
        raise HTTPException(status_code=404, detail=f"Lot {lot_id} not found")
    db.delete(lot)


# ===========================================================================
# Schedule
# ===========================================================================

schedule_router = APIRouter(prefix="/schedule", tags=["Schedule"])


@schedule_router.post(
    "/run",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run the OR-Tools CP-SAT scheduler",
)
def run_schedule(
    body: ScheduleRequest, db: Session = Depends(get_db)
) -> ScheduleResponse:
    """
    Trigger the OR-Tools CP-SAT Flexible Job Shop Scheduling engine.

    **Objective:** Minimises a weighted combination of:
    - Makespan
    - Total machine idle time
    - Weighted tardiness
    - Financial penalty (Normal: $10/min, Hot: $100/min of delay)

    Returns the full schedule result with Gantt JSON and KPI data.
    """
    try:
        return SchedulerService.run_schedule(body, db)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Schedule run error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal solver error. Check logs.")


@schedule_router.get(
    "",
    response_model=list[ScheduleResponse],
    summary="List recent schedule results",
)
def list_schedules(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ScheduleResponse]:
    """Return the most recent schedule results in descending order."""
    return SchedulerService.list_schedules(db, limit=limit)


@schedule_router.get(
    "/{schedule_id}",
    response_model=ScheduleResponse,
    summary="Get a schedule result by ID",
)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)) -> ScheduleResponse:
    """Retrieve a saved schedule result including Gantt chart and KPI data."""
    try:
        return SchedulerService.get_schedule(schedule_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ===========================================================================
# Analytics
# ===========================================================================

analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])


@analytics_router.get(
    "/{schedule_id}",
    response_model=KPIResponse,
    summary="Get KPI analytics for a schedule",
)
def get_analytics(
    schedule_id: int, db: Session = Depends(get_db)
) -> KPIResponse:
    """
    Return the full KPI report for a completed schedule run.

    Includes:
    - Makespan
    - Per-machine utilisation and idle time
    - Per-lot tardiness and financial penalty
    - Aggregate weighted tardiness
    - Total financial penalty (Normal: $10/min, Hot: $100/min)
    """
    try:
        return SchedulerService.get_kpis(schedule_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ===========================================================================
# Simulation
# ===========================================================================

simulation_router = APIRouter(prefix="/simulation", tags=["Simulation"])


@simulation_router.post(
    "/run",
    response_model=SimulationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Monte Carlo fab simulation",
)
def run_simulation(
    body: SimulationRequest, db: Session = Depends(get_db)
) -> SimulationResponse:
    """
    Execute a Monte Carlo discrete-event simulation based on a saved schedule.

    Stochastic machine failures are injected according to per-machine
    Exponential(MTBF) / Exponential(MTTR) distributions.

    Returns per-replication and aggregate statistics including:
    - Actual makespan across replications
    - Schedule disruptions caused by failures
    - Additional idle time injected
    - Revised financial penalties
    """
    try:
        return SchedulerService.run_simulation(body, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Simulation error: %s", exc)
        raise HTTPException(status_code=500, detail="Simulation failed. Check logs.")
