"""
main.py

FabFlow AI — FastAPI Application Entry Point.

Startup sequence
----------------
1. Create all SQLAlchemy tables (idempotent).
2. Seed realistic semiconductor sample data if the DB is empty.
3. Mount all API routers under /api prefix.
4. Expose Swagger UI at /docs and ReDoc at /redoc.

Seed dataset (semiconductor fab scenario)
-----------------------------------------
Machines (10 total):
  - 3 × SCANNER (lithography)      → LITH-01 / LITH-02 / LITH-03
  - 2 × RIE_ETCHER (etch)          → ETCH-01 / ETCH-02
  - 2 × CVD_CHAMBER (deposition)   → DEP-01 / DEP-02
  - 1 × CMP_TOOL                   → CMP-01
  - 1 × ION_IMPLANTER              → IMP-01
  - 1 × INSPECTION_SEM             → INSP-01

Recipes (one per stage / tool-type combination):
  LITHO-248NM, LITHO-193NM, ETCH-SiO2, ETCH-Si3N4,
  DEP-PECVD, DEP-LPCVD, CMP-STI, IMPLANT-B, INSPECT-CD

Setup times (sequence-dependent matrix):
  Switching LITHO-248NM → LITHO-193NM on SCANNER: 30 min
  Switching ETCH-SiO2 → ETCH-Si3N4 on RIE_ETCHER: 20 min
  … (realistic values for all cross-recipe transitions)

Lots (15 total):
  - 12 NORMAL priority lots  (product types: LOGIC, MEMORY, ANALOG)
  - 3  HOT priority lots     (urgent customer orders)
  Each lot has 3 ordered operations: LITHO → ETCH → DEP (or IMPLANT → CMP → INSPECT)
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.endpoints import (
    analytics_router,
    jobs_router,
    machines_router,
    recipes_router,
    router as health_router,
    schedule_router,
    setup_router,
    simulation_router,
)
from database.session import Base, SessionLocal, engine
from models.models import (
    Lot,
    LotPriority,
    Machine,
    MachineStatus,
    OperationStage,
    Operation,
    Recipe,
    SetupTime,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("fabflow")


# ---------------------------------------------------------------------------
# Dataset seed helpers
# ---------------------------------------------------------------------------


def _seed_machines(db) -> dict[str, int]:
    """Insert machines and return name→id map."""
    machine_defs = [
        # Lithography scanners
        dict(name="LITH-01", tool_type="SCANNER", status=MachineStatus.ACTIVE,
             speed_factor=1.0, default_setup_time_minutes=30,
             candidate_stages=[OperationStage.LITHOGRAPHY.value]),
        dict(name="LITH-02", tool_type="SCANNER", status=MachineStatus.ACTIVE,
             speed_factor=0.95, default_setup_time_minutes=30,
             candidate_stages=[OperationStage.LITHOGRAPHY.value]),
        dict(name="LITH-03", tool_type="SCANNER", status=MachineStatus.ACTIVE,
             speed_factor=1.1, default_setup_time_minutes=25,
             candidate_stages=[OperationStage.LITHOGRAPHY.value]),
        # Etch tools
        dict(name="ETCH-01", tool_type="RIE_ETCHER", status=MachineStatus.ACTIVE,
             speed_factor=1.0, default_setup_time_minutes=20,
             candidate_stages=[OperationStage.ETCH.value]),
        dict(name="ETCH-02", tool_type="RIE_ETCHER", status=MachineStatus.ACTIVE,
             speed_factor=1.05, default_setup_time_minutes=20,
             candidate_stages=[OperationStage.ETCH.value]),
        # Deposition chambers
        dict(name="DEP-01", tool_type="CVD_CHAMBER", status=MachineStatus.ACTIVE,
             speed_factor=1.0, default_setup_time_minutes=15,
             candidate_stages=[OperationStage.DEPOSITION.value]),
        dict(name="DEP-02", tool_type="CVD_CHAMBER", status=MachineStatus.ACTIVE,
             speed_factor=0.9, default_setup_time_minutes=15,
             candidate_stages=[OperationStage.DEPOSITION.value]),
        # CMP
        dict(name="CMP-01", tool_type="CMP_TOOL", status=MachineStatus.ACTIVE,
             speed_factor=1.0, default_setup_time_minutes=10,
             candidate_stages=[OperationStage.CMP.value]),
        # Ion implanter
        dict(name="IMP-01", tool_type="ION_IMPLANTER", status=MachineStatus.ACTIVE,
             speed_factor=1.0, default_setup_time_minutes=25,
             candidate_stages=[OperationStage.IMPLANT.value]),
        # Inspection SEM
        dict(name="INSP-01", tool_type="INSPECTION_SEM", status=MachineStatus.ACTIVE,
             speed_factor=1.0, default_setup_time_minutes=5,
             candidate_stages=[OperationStage.INSPECTION.value]),
    ]
    name_to_id: dict[str, int] = {}
    for mdef in machine_defs:
        m = Machine(**mdef)
        db.add(m)
        db.flush()
        name_to_id[m.name] = m.id
    logger.info("Seeded %d machines", len(machine_defs))
    return name_to_id


def _seed_recipes(db) -> dict[str, int]:
    """Insert recipes and return name→id map."""
    recipe_defs = [
        # Lithography
        dict(name="LITHO-248NM", stage=OperationStage.LITHOGRAPHY,
             tool_type="SCANNER", nominal_cycle_time_minutes=45,
             description="248nm DUV lithography — polysilicon gate layer"),
        dict(name="LITHO-193NM", stage=OperationStage.LITHOGRAPHY,
             tool_type="SCANNER", nominal_cycle_time_minutes=60,
             description="193nm DUV lithography — metal interconnect layer"),
        dict(name="LITHO-193I", stage=OperationStage.LITHOGRAPHY,
             tool_type="SCANNER", nominal_cycle_time_minutes=55,
             description="193nm immersion lithography — critical dimension <65nm"),
        # Etch
        dict(name="ETCH-SiO2", stage=OperationStage.ETCH,
             tool_type="RIE_ETCHER", nominal_cycle_time_minutes=30,
             description="Reactive Ion Etch — silicon dioxide dielectric"),
        dict(name="ETCH-Si3N4", stage=OperationStage.ETCH,
             tool_type="RIE_ETCHER", nominal_cycle_time_minutes=35,
             description="Reactive Ion Etch — silicon nitride hard mask"),
        dict(name="ETCH-Al", stage=OperationStage.ETCH,
             tool_type="RIE_ETCHER", nominal_cycle_time_minutes=28,
             description="Metal etch — aluminium interconnect"),
        # Deposition
        dict(name="DEP-PECVD-SiO2", stage=OperationStage.DEPOSITION,
             tool_type="CVD_CHAMBER", nominal_cycle_time_minutes=50,
             description="PECVD silicon dioxide gap fill"),
        dict(name="DEP-LPCVD-Poly", stage=OperationStage.DEPOSITION,
             tool_type="CVD_CHAMBER", nominal_cycle_time_minutes=80,
             description="LPCVD polysilicon gate formation"),
        dict(name="DEP-ALD-HfO2", stage=OperationStage.DEPOSITION,
             tool_type="CVD_CHAMBER", nominal_cycle_time_minutes=120,
             description="ALD high-k gate dielectric — HfO2"),
        # CMP
        dict(name="CMP-STI", stage=OperationStage.CMP,
             tool_type="CMP_TOOL", nominal_cycle_time_minutes=40,
             description="CMP shallow trench isolation planarisation"),
        dict(name="CMP-ILD", stage=OperationStage.CMP,
             tool_type="CMP_TOOL", nominal_cycle_time_minutes=35,
             description="CMP interlayer dielectric planarisation"),
        # Implant
        dict(name="IMPLANT-BF2", stage=OperationStage.IMPLANT,
             tool_type="ION_IMPLANTER", nominal_cycle_time_minutes=25,
             description="BF2 p-type source/drain implant"),
        dict(name="IMPLANT-As", stage=OperationStage.IMPLANT,
             tool_type="ION_IMPLANTER", nominal_cycle_time_minutes=20,
             description="Arsenic n-type source/drain implant"),
        # Inspection
        dict(name="INSPECT-CD-SEM", stage=OperationStage.INSPECTION,
             tool_type="INSPECTION_SEM", nominal_cycle_time_minutes=15,
             description="Critical dimension SEM measurement"),
        dict(name="INSPECT-OVL", stage=OperationStage.INSPECTION,
             tool_type="INSPECTION_SEM", nominal_cycle_time_minutes=12,
             description="Overlay metrology after lithography"),
    ]
    name_to_id: dict[str, int] = {}
    for rdef in recipe_defs:
        r = Recipe(**rdef)
        db.add(r)
        db.flush()
        name_to_id[r.name] = r.id
    logger.info("Seeded %d recipes", len(recipe_defs))
    return name_to_id


def _seed_setup_times(db, recipe_map: dict[str, int]) -> None:
    """Insert sequence-dependent setup time matrix."""
    R = recipe_map
    setup_defs = [
        # Scanner: switching between lithography recipes
        dict(from_recipe_id=R["LITHO-248NM"], to_recipe_id=R["LITHO-193NM"],
             tool_type="SCANNER", setup_minutes=30),
        dict(from_recipe_id=R["LITHO-193NM"], to_recipe_id=R["LITHO-248NM"],
             tool_type="SCANNER", setup_minutes=30),
        dict(from_recipe_id=R["LITHO-248NM"], to_recipe_id=R["LITHO-193I"],
             tool_type="SCANNER", setup_minutes=35),
        dict(from_recipe_id=R["LITHO-193I"], to_recipe_id=R["LITHO-248NM"],
             tool_type="SCANNER", setup_minutes=35),
        dict(from_recipe_id=R["LITHO-193NM"], to_recipe_id=R["LITHO-193I"],
             tool_type="SCANNER", setup_minutes=10),
        dict(from_recipe_id=R["LITHO-193I"], to_recipe_id=R["LITHO-193NM"],
             tool_type="SCANNER", setup_minutes=10),
        # RIE Etcher: switching etch chemistry
        dict(from_recipe_id=R["ETCH-SiO2"], to_recipe_id=R["ETCH-Si3N4"],
             tool_type="RIE_ETCHER", setup_minutes=20),
        dict(from_recipe_id=R["ETCH-Si3N4"], to_recipe_id=R["ETCH-SiO2"],
             tool_type="RIE_ETCHER", setup_minutes=20),
        dict(from_recipe_id=R["ETCH-SiO2"], to_recipe_id=R["ETCH-Al"],
             tool_type="RIE_ETCHER", setup_minutes=25),
        dict(from_recipe_id=R["ETCH-Al"], to_recipe_id=R["ETCH-SiO2"],
             tool_type="RIE_ETCHER", setup_minutes=25),
        dict(from_recipe_id=R["ETCH-Si3N4"], to_recipe_id=R["ETCH-Al"],
             tool_type="RIE_ETCHER", setup_minutes=30),
        dict(from_recipe_id=R["ETCH-Al"], to_recipe_id=R["ETCH-Si3N4"],
             tool_type="RIE_ETCHER", setup_minutes=30),
        # CVD Chamber: purge / pre-conditioning between film types
        dict(from_recipe_id=R["DEP-PECVD-SiO2"], to_recipe_id=R["DEP-LPCVD-Poly"],
             tool_type="CVD_CHAMBER", setup_minutes=45),
        dict(from_recipe_id=R["DEP-LPCVD-Poly"], to_recipe_id=R["DEP-PECVD-SiO2"],
             tool_type="CVD_CHAMBER", setup_minutes=45),
        dict(from_recipe_id=R["DEP-PECVD-SiO2"], to_recipe_id=R["DEP-ALD-HfO2"],
             tool_type="CVD_CHAMBER", setup_minutes=60),
        dict(from_recipe_id=R["DEP-ALD-HfO2"], to_recipe_id=R["DEP-PECVD-SiO2"],
             tool_type="CVD_CHAMBER", setup_minutes=60),
        dict(from_recipe_id=R["DEP-LPCVD-Poly"], to_recipe_id=R["DEP-ALD-HfO2"],
             tool_type="CVD_CHAMBER", setup_minutes=60),
        dict(from_recipe_id=R["DEP-ALD-HfO2"], to_recipe_id=R["DEP-LPCVD-Poly"],
             tool_type="CVD_CHAMBER", setup_minutes=60),
        # CMP: slurry change
        dict(from_recipe_id=R["CMP-STI"], to_recipe_id=R["CMP-ILD"],
             tool_type="CMP_TOOL", setup_minutes=15),
        dict(from_recipe_id=R["CMP-ILD"], to_recipe_id=R["CMP-STI"],
             tool_type="CMP_TOOL", setup_minutes=15),
        # Ion Implanter: species change
        dict(from_recipe_id=R["IMPLANT-BF2"], to_recipe_id=R["IMPLANT-As"],
             tool_type="ION_IMPLANTER", setup_minutes=30),
        dict(from_recipe_id=R["IMPLANT-As"], to_recipe_id=R["IMPLANT-BF2"],
             tool_type="ION_IMPLANTER", setup_minutes=30),
    ]
    for sdef in setup_defs:
        st = SetupTime(**sdef)
        db.add(st)
    db.flush()
    logger.info("Seeded %d setup time entries", len(setup_defs))


def _seed_lots(
    db,
    recipe_map: dict[str, int],
    machine_map: dict[str, int],
) -> None:
    """Insert 15 realistic wafer lots (12 NORMAL + 3 HOT)."""

    # Helper to get a list of machine IDs by name prefix
    def mids(*names: str) -> list[int]:
        return [machine_map[n] for n in names if n in machine_map]

    # ---------------------------------------------------------------------------
    # Lot definitions: (name, priority, release, due, weight, product, customer, ops)
    # ops = list of (recipe_name, seq_num, proc_time_override, candidate_machine_names)
    # ---------------------------------------------------------------------------
    lot_specs = [
        # --- Standard LOGIC lots ---
        ("LOT-LOGIC-001", LotPriority.NORMAL, 0, 480, 1.0, "LOGIC-28NM", "TSMC-SIM",
         [("LITHO-193NM", 0, 60, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-SiO2",   1, 30, ["ETCH-01", "ETCH-02"]),
          ("DEP-PECVD-SiO2", 2, 50, ["DEP-01", "DEP-02"])]),

        ("LOT-LOGIC-002", LotPriority.NORMAL, 0, 500, 1.0, "LOGIC-28NM", "TSMC-SIM",
         [("LITHO-193I",  0, 55, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-Si3N4",  1, 35, ["ETCH-01", "ETCH-02"]),
          ("DEP-LPCVD-Poly", 2, 80, ["DEP-01", "DEP-02"])]),

        ("LOT-LOGIC-003", LotPriority.NORMAL, 30, 510, 1.2, "LOGIC-28NM", "INTEL-SIM",
         [("LITHO-248NM", 0, 45, ["LITH-01", "LITH-02"]),
          ("ETCH-SiO2",   1, 30, ["ETCH-01", "ETCH-02"]),
          ("DEP-PECVD-SiO2", 2, 50, ["DEP-01", "DEP-02"])]),

        ("LOT-LOGIC-004", LotPriority.NORMAL, 60, 550, 1.0, "LOGIC-14NM", "SAMSUNG-SIM",
         [("LITHO-193I",  0, 60, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-Al",     1, 28, ["ETCH-01", "ETCH-02"]),
          ("DEP-ALD-HfO2", 2, 120, ["DEP-01", "DEP-02"])]),

        ("LOT-LOGIC-005", LotPriority.NORMAL, 0, 520, 1.5, "LOGIC-14NM", "AMD-SIM",
         [("LITHO-193NM", 0, 60, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-Si3N4",  1, 35, ["ETCH-01", "ETCH-02"]),
          ("CMP-STI",     2, 40, ["CMP-01"])]),

        # --- MEMORY lots ---
        ("LOT-MEM-001", LotPriority.NORMAL, 0, 600, 0.8, "DRAM-DDR5", "MICRON-SIM",
         [("LITHO-248NM", 0, 45, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-SiO2",   1, 30, ["ETCH-01", "ETCH-02"]),
          ("IMPLANT-BF2", 2, 25, ["IMP-01"])]),

        ("LOT-MEM-002", LotPriority.NORMAL, 30, 620, 0.8, "DRAM-DDR5", "SK-HYNIX-SIM",
         [("LITHO-193NM", 0, 60, ["LITH-01", "LITH-02"]),
          ("ETCH-Si3N4",  1, 35, ["ETCH-01", "ETCH-02"]),
          ("IMPLANT-As",  2, 20, ["IMP-01"])]),

        ("LOT-MEM-003", LotPriority.NORMAL, 120, 700, 0.9, "NAND-3D", "SAMSUNG-SIM",
         [("LITHO-193I",  0, 55, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-Al",     1, 28, ["ETCH-01", "ETCH-02"]),
          ("CMP-ILD",     2, 35, ["CMP-01"])]),

        # --- ANALOG lots ---
        ("LOT-ANA-001", LotPriority.NORMAL, 0, 720, 0.7, "ANALOG-180NM", "TI-SIM",
         [("LITHO-248NM", 0, 45, ["LITH-01", "LITH-02"]),
          ("ETCH-SiO2",   1, 30, ["ETCH-01"]),
          ("DEP-LPCVD-Poly", 2, 80, ["DEP-01"])]),

        ("LOT-ANA-002", LotPriority.NORMAL, 60, 750, 0.7, "ANALOG-180NM", "NXP-SIM",
         [("LITHO-248NM", 0, 45, ["LITH-01", "LITH-03"]),
          ("ETCH-SiO2",   1, 30, ["ETCH-02"]),
          ("IMPLANT-BF2", 2, 25, ["IMP-01"])]),

        ("LOT-ANA-003", LotPriority.NORMAL, 0, 680, 1.0, "BIPOLAR-130NM", "ADI-SIM",
         [("LITHO-193NM", 0, 60, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-Si3N4",  1, 35, ["ETCH-01", "ETCH-02"]),
          ("DEP-ALD-HfO2", 2, 120, ["DEP-01", "DEP-02"])]),

        ("LOT-ANA-004", LotPriority.NORMAL, 90, 800, 0.6, "RF-CMOS-40NM", "QUALCOMM-SIM",
         [("LITHO-193I",  0, 55, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-Al",     1, 28, ["ETCH-01", "ETCH-02"]),
          ("INSPECT-CD-SEM", 2, 15, ["INSP-01"])]),

        # --- HOT lots (urgent, high penalty) ---
        ("LOT-HOT-001", LotPriority.HOT, 0, 240, 3.0, "LOGIC-7NM", "APPLE-SIM",
         [("LITHO-193I",  0, 55, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-Si3N4",  1, 35, ["ETCH-01", "ETCH-02"]),
          ("DEP-ALD-HfO2", 2, 120, ["DEP-01", "DEP-02"])]),

        ("LOT-HOT-002", LotPriority.HOT, 0, 300, 2.5, "LOGIC-5NM", "NVIDIA-SIM",
         [("LITHO-193NM", 0, 60, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-SiO2",   1, 30, ["ETCH-01", "ETCH-02"]),
          ("DEP-PECVD-SiO2", 2, 50, ["DEP-01", "DEP-02"])]),

        ("LOT-HOT-003", LotPriority.HOT, 15, 360, 2.0, "MEMORY-HBM3", "GOOGLE-SIM",
         [("LITHO-193I",  0, 55, ["LITH-01", "LITH-02", "LITH-03"]),
          ("ETCH-Al",     1, 28, ["ETCH-01", "ETCH-02"]),
          ("CMP-STI",     2, 40, ["CMP-01"])]),
    ]

    for (name, priority, release, due, weight, product, customer, ops_spec) in lot_specs:
        lot = Lot(
            name=name,
            priority=priority,
            release_time_minutes=release,
            due_time_minutes=due,
            weight=weight,
            wafer_count=25,
            product_type=product,
            customer=customer,
        )
        db.add(lot)
        db.flush()

        for (recipe_name, seq_num, proc_time, machine_names) in ops_spec:
            rid = recipe_map.get(recipe_name)
            if rid is None:
                logger.warning("Recipe %s not found during seeding — skipping op", recipe_name)
                continue
            candidate_ids = mids(*machine_names)
            op = Operation(
                lot_id=lot.id,
                recipe_id=rid,
                sequence_num=seq_num,
                processing_time_minutes=proc_time,
                candidate_machine_ids=candidate_ids,
            )
            db.add(op)

    db.flush()
    logger.info("Seeded 15 lots (12 NORMAL + 3 HOT) with operations")


def seed_sample_data() -> None:
    """
    Idempotent seed function — only runs if no machines exist.
    Called during application startup.
    """
    db = SessionLocal()
    try:
        if db.query(Machine).count() > 0:
            logger.info("Database already contains data — skipping seed")
            return

        logger.info("Seeding realistic semiconductor fab sample data …")
        machine_map = _seed_machines(db)
        recipe_map = _seed_recipes(db)
        _seed_setup_times(db, recipe_map)
        _seed_lots(db, recipe_map, machine_map)
        db.commit()
        logger.info("[OK] Sample data seed complete")
    except Exception as exc:
        db.rollback()
        logger.exception("Seed failed: %s", exc)
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown lifecycle hook."""
    logger.info("FabFlow AI -- initialising database ...")
    Base.metadata.create_all(bind=engine)
    seed_sample_data()
    logger.info("FabFlow AI -- ready [OK]")
    yield
    logger.info("FabFlow AI -- shutting down")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FabFlow AI",
    description=(
        "Intelligent Semiconductor Fab Scheduling & Optimization Platform.\n\n"
        "Solves a Flexible Job Shop Scheduling Problem using Google OR-Tools CP-SAT. "
        "Minimises makespan, machine idle time, weighted tardiness, and financial penalties "
        "(Normal lots: $10/min delay · Hot lots: $100/min delay)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "FabFlow AI Engineering",
        "url": "https://github.com/fabflow-ai",
    },
    license_info={"name": "MIT"},
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

API_PREFIX = "/api"

app.include_router(health_router)  # /health for Render & container healthchecks
app.include_router(health_router, prefix=API_PREFIX)  # /api/health
app.include_router(machines_router, prefix=API_PREFIX)
app.include_router(recipes_router, prefix=API_PREFIX)
app.include_router(setup_router, prefix=API_PREFIX)
app.include_router(jobs_router, prefix=API_PREFIX)
app.include_router(schedule_router, prefix=API_PREFIX)
app.include_router(analytics_router, prefix=API_PREFIX)
app.include_router(simulation_router, prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )

