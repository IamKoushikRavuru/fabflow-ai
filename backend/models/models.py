"""
models/models.py

SQLAlchemy ORM models for FabFlow AI.

Entity graph
------------
Machine  ─────────────────────────────────────────────────┐
  │ has many MaintenanceWindow                             │
  │ has many MachineFailure                                │
  │ is assigned to many Operation (via assigned_machine)  │
                                                           │
Lot ──────────────────────────────────────────────────────┘
  │ has ordered Operations
  │ has one ScheduleResult (per solver run, via FK)

Operation
  │ belongs to Lot
  │ optionally assigned to Machine
  │ references a Recipe (string key; full Recipe rows stored separately)

Recipe
  │ standalone lookup table (name, cycle_time_minutes, tool_type)

SetupTime
  │ sequence-dependent matrix: from_recipe → to_recipe on machine_type

ScheduleResult
  │ solver output snapshot: makespan, kpi JSON, gantt JSON

ScheduledOperation
  │ per-operation allocation within a ScheduleResult
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class LotPriority(str, enum.Enum):
    """Lot scheduling priority tier."""

    NORMAL = "NORMAL"
    HOT = "HOT"


class MachineStatus(str, enum.Enum):
    """Operational state of a machine."""

    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"
    OFFLINE = "OFFLINE"


class OperationStage(str, enum.Enum):
    """Fab process stage for an operation."""

    LITHOGRAPHY = "LITHOGRAPHY"
    ETCH = "ETCH"
    DEPOSITION = "DEPOSITION"
    CMP = "CMP"
    DIFFUSION = "DIFFUSION"
    INSPECTION = "INSPECTION"
    IMPLANT = "IMPLANT"
    CLEAN = "CLEAN"


class ScheduleStatus(str, enum.Enum):
    """Solver run outcome."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Machine
# ---------------------------------------------------------------------------


class Machine(Base):
    """
    Physical fab tool capable of processing one or more recipe types.

    ``candidate_recipe_types`` stores a JSON list of OperationStage values
    the machine can handle (e.g. ["LITHOGRAPHY", "ETCH"]).
    """

    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tool_type: Mapped[str] = mapped_column(String(64), nullable=False)          # e.g. "SCANNER"
    status: Mapped[MachineStatus] = mapped_column(
        Enum(MachineStatus), default=MachineStatus.ACTIVE, nullable=False
    )
    # Default processing speed multiplier (1.0 = nominal)
    speed_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    # Default setup time (minutes) when switching to a new recipe
    default_setup_time_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    # JSON list of OperationStage strings this machine supports
    candidate_stages: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # relationships
    maintenance_windows: Mapped[list[MaintenanceWindow]] = relationship(
        "MaintenanceWindow", back_populates="machine", cascade="all, delete-orphan"
    )
    failures: Mapped[list[MachineFailure]] = relationship(
        "MachineFailure", back_populates="machine", cascade="all, delete-orphan"
    )
    operations: Mapped[list[Operation]] = relationship(
        "Operation", back_populates="assigned_machine", foreign_keys="Operation.assigned_machine_id"
    )
    scheduled_operations: Mapped[list[ScheduledOperation]] = relationship(
        "ScheduledOperation", back_populates="machine"
    )

    def __repr__(self) -> str:
        return f"<Machine id={self.id} name={self.name!r} status={self.status}>"


# ---------------------------------------------------------------------------
# MaintenanceWindow
# ---------------------------------------------------------------------------


class MaintenanceWindow(Base):
    """
    Planned downtime interval for a machine.

    The scheduler treats this as a fixed blocked interval: no operation
    may start on the machine within [start_time, end_time].
    """

    __tablename__ = "maintenance_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    machine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurrence_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # every N days

    machine: Mapped[Machine] = relationship("Machine", back_populates="maintenance_windows")

    def __repr__(self) -> str:
        return (
            f"<MaintenanceWindow id={self.id} machine_id={self.machine_id} "
            f"start={self.start_time} end={self.end_time}>"
        )


# ---------------------------------------------------------------------------
# MachineFailure
# ---------------------------------------------------------------------------


class MachineFailure(Base):
    """
    Historical or simulated unplanned machine failure event.

    Used by the simulator to inject stochastic downtime and by the
    validator to flag schedule violations caused by unexpected outages.
    """

    __tablename__ = "machine_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    machine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_mode: Mapped[str | None] = mapped_column(String(128), nullable=True)  # e.g. "LASER_FAULT"
    mttr_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)       # mean time to repair
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    machine: Mapped[Machine] = relationship("Machine", back_populates="failures")

    def __repr__(self) -> str:
        return (
            f"<MachineFailure id={self.id} machine_id={self.machine_id} "
            f"start={self.start_time} duration={self.duration_minutes}min>"
        )


# ---------------------------------------------------------------------------
# Recipe
# ---------------------------------------------------------------------------


class Recipe(Base):
    """
    Process recipe definition.

    A recipe describes the processing steps and nominal cycle times for
    a specific fab operation type on a specific tool type.
    """

    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    stage: Mapped[OperationStage] = mapped_column(Enum(OperationStage), nullable=False)
    tool_type: Mapped[str] = mapped_column(String(64), nullable=False)       # must match Machine.tool_type
    nominal_cycle_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # relationships
    operations: Mapped[list[Operation]] = relationship("Operation", back_populates="recipe")
    setup_times_from: Mapped[list[SetupTime]] = relationship(
        "SetupTime", foreign_keys="SetupTime.from_recipe_id", back_populates="from_recipe"
    )
    setup_times_to: Mapped[list[SetupTime]] = relationship(
        "SetupTime", foreign_keys="SetupTime.to_recipe_id", back_populates="to_recipe"
    )

    def __repr__(self) -> str:
        return f"<Recipe id={self.id} name={self.name!r} stage={self.stage}>"


# ---------------------------------------------------------------------------
# SetupTime  (sequence-dependent setup matrix)
# ---------------------------------------------------------------------------


class SetupTime(Base):
    """
    Sequence-dependent setup time between two recipes on a given tool type.

    When a machine finishes processing recipe `from_recipe` and the next
    job requires `to_recipe`, it must idle for `setup_minutes` before
    processing begins.  A missing row implies zero additional setup.
    """

    __tablename__ = "setup_times"
    __table_args__ = (
        UniqueConstraint("from_recipe_id", "to_recipe_id", "tool_type", name="uq_setup_transition"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    from_recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    to_recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    tool_type: Mapped[str] = mapped_column(String(64), nullable=False)
    setup_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    from_recipe: Mapped[Recipe] = relationship(
        "Recipe", foreign_keys=[from_recipe_id], back_populates="setup_times_from"
    )
    to_recipe: Mapped[Recipe] = relationship(
        "Recipe", foreign_keys=[to_recipe_id], back_populates="setup_times_to"
    )

    def __repr__(self) -> str:
        return (
            f"<SetupTime from={self.from_recipe_id} to={self.to_recipe_id} "
            f"tool={self.tool_type!r} minutes={self.setup_minutes}>"
        )


# ---------------------------------------------------------------------------
# Lot
# ---------------------------------------------------------------------------


class Lot(Base):
    """
    A wafer lot (job) to be processed through a sequence of operations.

    ``priority`` determines the financial penalty multiplier:
      - NORMAL → 10 × delay minutes
      - HOT    → 100 × delay minutes
    """

    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    priority: Mapped[LotPriority] = mapped_column(
        Enum(LotPriority), default=LotPriority.NORMAL, nullable=False
    )
    release_time_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        doc="Minutes from schedule horizon start when this lot becomes available."
    )
    due_time_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False,
        doc="Minutes from schedule horizon start by which this lot must complete."
    )
    weight: Mapped[float] = mapped_column(
        Float, default=1.0, nullable=False,
        doc="Tardiness weight for multi-objective optimisation."
    )
    wafer_count: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    product_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # relationships
    operations: Mapped[list[Operation]] = relationship(
        "Operation", back_populates="lot", cascade="all, delete-orphan",
        order_by="Operation.sequence_num"
    )
    scheduled_operations: Mapped[list[ScheduledOperation]] = relationship(
        "ScheduledOperation", back_populates="lot"
    )

    def __repr__(self) -> str:
        return f"<Lot id={self.id} name={self.name!r} priority={self.priority}>"


# ---------------------------------------------------------------------------
# Operation
# ---------------------------------------------------------------------------


class Operation(Base):
    """
    A single processing step within a lot's route.

    ``sequence_num`` defines the mandatory precedence ordering within a lot:
        0 = LITHOGRAPHY → 1 = ETCH → 2 = DEPOSITION → …

    ``candidate_machine_ids`` is a JSON list of Machine.id values that are
    eligible to process this operation (flexible JSP).  If empty/None,
    any machine matching the recipe's tool_type is eligible.

    ``processing_time_minutes`` overrides the recipe's nominal cycle time
    when set (allows per-lot customisation).
    """

    __tablename__ = "operations"
    __table_args__ = (
        UniqueConstraint("lot_id", "sequence_num", name="uq_lot_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id"), nullable=False
    )
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # JSON list of eligible Machine.id values; None = any matching tool_type
    candidate_machine_ids: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    # Filled in by the solver
    assigned_machine_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("machines.id"), nullable=True, index=True
    )

    # relationships
    lot: Mapped[Lot] = relationship("Lot", back_populates="operations")
    recipe: Mapped[Recipe] = relationship("Recipe", back_populates="operations")
    assigned_machine: Mapped[Machine | None] = relationship(
        "Machine", back_populates="operations", foreign_keys=[assigned_machine_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Operation id={self.id} lot_id={self.lot_id} seq={self.sequence_num} "
            f"recipe_id={self.recipe_id}>"
        )


# ---------------------------------------------------------------------------
# ScheduleResult  (solver run output)
# ---------------------------------------------------------------------------


class ScheduleResult(Base):
    """
    Immutable snapshot of a single OR-Tools solver run.

    ``kpi_data`` stores the KPI dictionary (makespan, idle_time, tardiness, penalty).
    ``gantt_data`` stores the full Gantt JSON consumed by the frontend.
    ``solver_stats`` stores CP-SAT wall-clock time, number of branches, etc.
    """

    __tablename__ = "schedule_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus), default=ScheduleStatus.PENDING, nullable=False
    )
    makespan_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    solver_wall_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    objective_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON payloads
    kpi_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    gantt_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    solver_stats: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Solver parameters used for this run
    solver_params: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # relationships
    scheduled_operations: Mapped[list[ScheduledOperation]] = relationship(
        "ScheduledOperation", back_populates="schedule_result", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduleResult id={self.id} status={self.status} "
            f"makespan={self.makespan_minutes}min>"
        )


# ---------------------------------------------------------------------------
# ScheduledOperation  (per-operation allocation within a ScheduleResult)
# ---------------------------------------------------------------------------


class ScheduledOperation(Base):
    """
    Allocation of a single operation to a machine within a ScheduleResult.

    ``start_minutes`` and ``end_minutes`` are offsets from the schedule
    horizon start (integer minutes), matching the CP-SAT variable domain.
    """

    __tablename__ = "scheduled_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    schedule_result_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schedule_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lots.id"), nullable=False, index=True
    )
    operation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("operations.id"), nullable=False, index=True
    )
    machine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("machines.id"), nullable=False, index=True
    )
    recipe_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recipes.id"), nullable=False
    )
    sequence_num: Mapped[int] = mapped_column(Integer, nullable=False)
    start_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    setup_time_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # relationships
    schedule_result: Mapped[ScheduleResult] = relationship(
        "ScheduleResult", back_populates="scheduled_operations"
    )
    lot: Mapped[Lot] = relationship("Lot", back_populates="scheduled_operations")
    machine: Mapped[Machine] = relationship("Machine", back_populates="scheduled_operations")

    def __repr__(self) -> str:
        return (
            f"<ScheduledOperation id={self.id} lot_id={self.lot_id} "
            f"machine_id={self.machine_id} [{self.start_minutes}-{self.end_minutes}]>"
        )
