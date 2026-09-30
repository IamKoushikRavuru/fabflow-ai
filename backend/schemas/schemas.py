"""
schemas/schemas.py

Pydantic v2 request / response schemas for FabFlow AI.

Naming convention
-----------------
- <Entity>Base      — shared fields (no id / timestamps)
- <Entity>Create    — body of POST requests
- <Entity>Update    — body of PUT / PATCH requests (all fields optional)
- <Entity>Response  — full DB-hydrated read response (includes id / timestamps)
- <Entity>          — re-exported alias used internally

All datetime fields are UTC-aware ISO-8601 strings in API responses.
All *_minutes integer fields represent offsets or durations in integer minutes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.models import LotPriority, MachineStatus, OperationStage, ScheduleStatus


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

class _OrmBase(BaseModel):
    """Base with ORM mode enabled for all response schemas."""

    model_config = ConfigDict(from_attributes=True)


# ===========================================================================
# Machine schemas
# ===========================================================================


class MachineBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, examples=["LITH-01"])
    tool_type: str = Field(..., min_length=1, max_length=64, examples=["SCANNER"])
    status: MachineStatus = MachineStatus.ACTIVE
    speed_factor: float = Field(default=1.0, ge=0.1, le=10.0)
    default_setup_time_minutes: int = Field(default=15, ge=0)
    candidate_stages: list[OperationStage] | None = None


class MachineCreate(MachineBase):
    """Body for POST /api/machines."""


class MachineUpdate(BaseModel):
    """Body for PATCH /api/machines/{id} — all fields optional."""

    name: str | None = Field(None, min_length=1, max_length=64)
    tool_type: str | None = None
    status: MachineStatus | None = None
    speed_factor: float | None = Field(None, ge=0.1, le=10.0)
    default_setup_time_minutes: int | None = Field(None, ge=0)
    candidate_stages: list[OperationStage] | None = None


class MachineResponse(_OrmBase, MachineBase):
    """Full machine read response."""

    id: int
    created_at: datetime
    updated_at: datetime


# ===========================================================================
# MaintenanceWindow schemas
# ===========================================================================


class MaintenanceWindowBase(BaseModel):
    machine_id: int
    start_time: datetime
    end_time: datetime
    reason: str | None = Field(None, max_length=256)
    is_recurring: bool = False
    recurrence_days: int | None = Field(None, ge=1)

    @model_validator(mode="after")
    def end_after_start(self) -> MaintenanceWindowBase:
        if self.end_time <= self.start_time:
            raise ValueError("`end_time` must be after `start_time`")
        return self


class MaintenanceWindowCreate(MaintenanceWindowBase):
    """Body for POST /api/machines/{id}/maintenance."""


class MaintenanceWindowResponse(_OrmBase, MaintenanceWindowBase):
    id: int


# ===========================================================================
# MachineFailure schemas
# ===========================================================================


class MachineFailureBase(BaseModel):
    machine_id: int
    start_time: datetime
    duration_minutes: int = Field(..., ge=1)
    failure_mode: str | None = Field(None, max_length=128)
    mttr_minutes: int | None = Field(None, ge=0)
    is_simulated: bool = False


class MachineFailureCreate(MachineFailureBase):
    """Body for POST /api/machines/{id}/failures."""


class MachineFailureResponse(_OrmBase, MachineFailureBase):
    id: int


# ===========================================================================
# Recipe schemas
# ===========================================================================


class RecipeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, examples=["LITH-248NM"])
    stage: OperationStage
    tool_type: str = Field(..., max_length=64, examples=["SCANNER"])
    nominal_cycle_time_minutes: int = Field(..., ge=1)
    description: str | None = None


class RecipeCreate(RecipeBase):
    """Body for POST /api/recipes."""


class RecipeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    nominal_cycle_time_minutes: int | None = Field(None, ge=1)
    description: str | None = None


class RecipeResponse(_OrmBase, RecipeBase):
    id: int


# ===========================================================================
# SetupTime schemas
# ===========================================================================


class SetupTimeBase(BaseModel):
    from_recipe_id: int
    to_recipe_id: int
    tool_type: str = Field(..., max_length=64)
    setup_minutes: int = Field(..., ge=0)

    @field_validator("to_recipe_id")
    @classmethod
    def not_same_recipe(cls, v: int, info: Any) -> int:
        if "from_recipe_id" in (info.data or {}) and v == info.data["from_recipe_id"]:
            raise ValueError("`from_recipe_id` and `to_recipe_id` must differ")
        return v


class SetupTimeCreate(SetupTimeBase):
    """Body for POST /api/setup-times."""


class SetupTimeResponse(_OrmBase, SetupTimeBase):
    id: int


# ===========================================================================
# Operation schemas
# ===========================================================================


class OperationBase(BaseModel):
    recipe_id: int
    sequence_num: int = Field(..., ge=0)
    processing_time_minutes: int | None = Field(None, ge=1)
    candidate_machine_ids: list[int] | None = None


class OperationCreate(OperationBase):
    """Body for creating an operation within a lot."""


class OperationResponse(_OrmBase, OperationBase):
    id: int
    lot_id: int
    assigned_machine_id: int | None


# ===========================================================================
# Lot schemas
# ===========================================================================


class LotBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, examples=["LOT-001"])
    priority: LotPriority = LotPriority.NORMAL
    release_time_minutes: int = Field(default=0, ge=0)
    due_time_minutes: int = Field(..., ge=1)
    weight: float = Field(default=1.0, ge=0.0)
    wafer_count: int = Field(default=25, ge=1, le=200)
    product_type: str | None = Field(None, max_length=64)
    customer: str | None = Field(None, max_length=128)

    @model_validator(mode="after")
    def due_after_release(self) -> LotBase:
        if self.due_time_minutes <= self.release_time_minutes:
            raise ValueError("`due_time_minutes` must be greater than `release_time_minutes`")
        return self


class LotCreate(LotBase):
    """Body for POST /api/jobs — includes nested operations."""

    operations: list[OperationCreate] = Field(..., min_length=1)


class LotUpdate(BaseModel):
    priority: LotPriority | None = None
    due_time_minutes: int | None = Field(None, ge=1)
    weight: float | None = Field(None, ge=0.0)
    customer: str | None = None


class LotResponse(_OrmBase, LotBase):
    id: int
    operations: list[OperationResponse]
    created_at: datetime
    updated_at: datetime


# ===========================================================================
# Schedule request / response schemas
# ===========================================================================


class SolverWeights(BaseModel):
    """Multi-objective weights for the CP-SAT objective function."""

    makespan: float = Field(default=1.0, ge=0.0, description="Weight on minimising makespan")
    idle_time: float = Field(default=0.5, ge=0.0, description="Weight on minimising machine idle time")
    weighted_tardiness: float = Field(default=2.0, ge=0.0, description="Weight on minimising weighted tardiness")
    penalty_cost: float = Field(default=3.0, ge=0.0, description="Weight on minimising financial penalty")


class ScheduleRequest(BaseModel):
    """Body for POST /api/schedule/run."""

    lot_ids: list[int] | None = Field(
        None,
        description="Subset of lot IDs to schedule. None = schedule all active lots.",
    )
    max_ops_per_lot: int | None = Field(
        None,
        ge=1,
        le=600,
        description=(
            "Limit to first N operations per lot. "
            "Essential for real-world datasets (e.g. SMT2020 has 300-500 ops/lot). "
            "Recommended: 10 for interactive demos, 50+ for overnight batch runs."
        ),
    )
    horizon_minutes: int = Field(
        default=1440,
        ge=60,
        le=43200,
        description="Schedule time horizon in minutes (default = 24 h).",
    )
    solver_time_limit_seconds: int = Field(
        default=30,
        ge=5,
        le=600,
        description="CP-SAT wall-clock time limit.",
    )
    weights: SolverWeights = Field(default_factory=SolverWeights)
    include_maintenance: bool = Field(
        default=True,
        description="If True, blocked maintenance windows are enforced.",
    )
    include_failures: bool = Field(
        default=False,
        description="If True, recorded machine failures are treated as blocked intervals.",
    )


# ---------------------------------------------------------------------------
# Gantt chart output
# ---------------------------------------------------------------------------


class GanttTask(BaseModel):
    """Single task bar in the Gantt chart output."""

    lot_id: int
    lot_name: str
    operation_id: int
    sequence_num: int
    machine_id: int
    machine_name: str
    recipe_id: int
    recipe_name: str
    stage: OperationStage
    is_hot: bool
    start_minutes: int
    end_minutes: int
    duration_minutes: int
    setup_time_minutes: int


class GanttChart(BaseModel):
    """Full Gantt chart JSON returned by the schedule endpoint."""

    schedule_result_id: int
    horizon_minutes: int
    makespan_minutes: int
    tasks: list[GanttTask]


# ---------------------------------------------------------------------------
# KPI / financial metrics
# ---------------------------------------------------------------------------


class MachineUtilization(BaseModel):
    machine_id: int
    machine_name: str
    busy_minutes: int
    idle_minutes: int
    utilization_pct: float


class LotTardiness(BaseModel):
    lot_id: int
    lot_name: str
    priority: LotPriority
    completion_minutes: int
    due_time_minutes: int
    delay_minutes: int          # max(0, completion - due)
    is_tardy: bool
    penalty_cost: float         # 10×delay or 100×delay


class KPIResponse(BaseModel):
    """Analytics KPI payload returned by GET /api/analytics/{schedule_id}."""

    schedule_result_id: int
    status: ScheduleStatus
    makespan_minutes: int
    total_idle_minutes: int
    avg_machine_utilization_pct: float
    total_weighted_tardiness: float
    total_penalty_cost: float
    normal_lot_penalty: float
    hot_lot_penalty: float
    machine_utilization: list[MachineUtilization]
    lot_tardiness: list[LotTardiness]


# ---------------------------------------------------------------------------
# Schedule result response
# ---------------------------------------------------------------------------


class ScheduleResponse(_OrmBase):
    """Full schedule result response (from DB)."""

    id: int
    status: ScheduleStatus
    makespan_minutes: int | None
    solver_wall_time_seconds: float | None
    objective_value: float | None
    kpi_data: dict[str, Any] | None
    gantt_data: dict[str, Any] | None
    solver_stats: dict[str, Any] | None
    solver_params: dict[str, Any] | None
    created_at: datetime


# ===========================================================================
# Simulation schemas
# ===========================================================================


class SimulationFailureConfig(BaseModel):
    """Configuration for stochastic machine failures in the simulator."""

    machine_id: int
    mean_time_between_failures_hours: float = Field(..., gt=0.0)
    mean_time_to_repair_minutes: float = Field(..., gt=0.0)
    failure_mode: str = Field(default="RANDOM", max_length=64)


class SimulationRequest(BaseModel):
    """Body for POST /api/simulation/run."""

    schedule_result_id: int = Field(..., description="Base schedule to simulate against.")
    simulation_horizon_minutes: int = Field(default=1440, ge=60)
    random_seed: int | None = Field(None, description="Seed for reproducible results.")
    failure_configs: list[SimulationFailureConfig] = Field(
        default_factory=list,
        description="Per-machine failure distributions. Empty = no failures injected.",
    )
    num_replications: int = Field(
        default=1, ge=1, le=50, description="Number of Monte Carlo replications."
    )


class SimulationRunStats(BaseModel):
    """Output from a single simulation replication."""

    replication: int
    actual_makespan_minutes: int
    schedule_disruptions: int         # operations that had to be rescheduled
    total_idle_time_added_minutes: int
    total_penalty_cost: float
    gantt_data: dict[str, Any] | None


class SimulationResponse(BaseModel):
    """Aggregated simulation response across all replications."""

    schedule_result_id: int
    num_replications: int
    avg_makespan_minutes: float
    max_makespan_minutes: int
    min_makespan_minutes: int
    avg_penalty_cost: float
    avg_disruptions: float
    replications: list[SimulationRunStats]


# ===========================================================================
# Health check
# ===========================================================================


class HealthResponse(BaseModel):
    status: str
    db_connected: bool
    version: str = "1.0.0"
