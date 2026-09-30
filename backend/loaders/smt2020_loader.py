"""
loaders/smt2020_loader.py

SMT2020 Dataset Loader for FabFlow AI
======================================

Parses the official SMT2020 semiconductor fab benchmark dataset
(Kopp et al., 2020 — FernUni Hagen) and imports it into FabFlow AI's
PostgreSQL/SQLite database.

Supported files (General Data folder)
--------------------------------------
  dataset 1 → SMT_2020_Model_Data_-_HVLM.xlsx   (High Volume / Low Mix)
  dataset 2 → SMT_2020_Model_Data_-_LVHM.xlsx   (Low Volume / High Mix)
  dataset 3 → SMT_2020_Model_Data_-_HVLM_E.xlsx (HVLM Extended)
  dataset 4 → SMT_2020_Model_Data_-_LVHM_E.xlsx (LVHM Extended)

Excel sheets parsed
-------------------
  Toolgroups   → Machine rows         (maps to Machine table)
  PM           → Maintenance windows  (maps to MaintenanceWindow table)
  Breakdown    → Machine failures     (maps to MachineFailure table)
  Route_*      → Operations + Recipes (maps to Recipe + Operation tables)
  Lotrelease   → Lots                 (maps to Lot table)
  Setups       → Setup times          (maps to SetupTime table)

Usage
-----
    # From project root (backend/):
    python -m loaders.smt2020_loader \
        --file "C:/Users/ravur/Downloads/SMT2020/SMT_2020 - Final/General Data/dataset 1/SMT_2020_Model_Data_-_HVLM.xlsx" \
        --clear

    # Or from Python:
    from loaders.smt2020_loader import SMT2020Loader
    loader = SMT2020Loader(db_session, filepath)
    loader.load()
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import openpyxl

# Add backend root to path when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.session import Base, SessionLocal, engine
from models.models import (
    Lot,
    LotPriority,
    Machine,
    MachineFailure,
    MachineStatus,
    MaintenanceWindow,
    Operation,
    OperationStage,
    Recipe,
    ScheduleResult,
    ScheduledOperation,
    SetupTime,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")


# ---------------------------------------------------------------------------
# Stage mapping — SMT2020 "AREA" → our OperationStage enum
# ---------------------------------------------------------------------------

AREA_TO_STAGE: dict[str, OperationStage] = {
    # Lithography / photo
    "Photo":           OperationStage.LITHOGRAPHY,
    "Litho":           OperationStage.LITHOGRAPHY,
    "Lithography":     OperationStage.LITHOGRAPHY,
    # Etch
    "Dry_Etch":        OperationStage.ETCH,
    "Wet_Etch":        OperationStage.ETCH,
    "Etch":            OperationStage.ETCH,
    # Deposition / dielectric / diffusion
    "Diffusion":       OperationStage.DEPOSITION,
    "Dielectric":      OperationStage.DEPOSITION,
    "TF_Met":          OperationStage.DEPOSITION,
    "Thin_Films":      OperationStage.DEPOSITION,
    "Deposition":      OperationStage.DEPOSITION,
    # CMP
    "CMP":             OperationStage.CMP,
    # Implant
    "Implant":         OperationStage.IMPLANT,
    "Ion_Implant":     OperationStage.IMPLANT,
    # Inspection / metrology
    "Def_Met":         OperationStage.INSPECTION,
    "Defect_Met":      OperationStage.INSPECTION,
    "OPT_Met":         OperationStage.INSPECTION,
    "Metrology":       OperationStage.INSPECTION,
    "Inspection":      OperationStage.INSPECTION,
    # Clean
    "Wet_Clean":       OperationStage.CLEAN,
    "Clean":           OperationStage.CLEAN,
}


def _area_to_stage(area: str | None) -> OperationStage:
    """Map an SMT2020 AREA string to our OperationStage enum."""
    if area is None:
        return OperationStage.INSPECTION
    for key, stage in AREA_TO_STAGE.items():
        if key.lower() in area.lower():
            return stage
    # Fallback — log and return INSPECTION
    logger.debug("Unknown area '%s' — defaulting to INSPECTION", area)
    return OperationStage.INSPECTION


def _safe_int(v: Any, default: int = 1) -> int:
    try:
        return int(float(v)) if v is not None else default
    except (TypeError, ValueError):
        return default


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _read_sheet(ws) -> list[dict[str, Any]]:
    """Read all rows from a sheet into a list of dicts keyed by header."""
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(c).strip() if c is not None else f"_col{i}" for i, c in enumerate(rows[0])]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append(dict(zip(header, row)))
    return result


# ---------------------------------------------------------------------------
# Main loader class
# ---------------------------------------------------------------------------


class SMT2020Loader:
    """
    Loads one SMT2020 Excel file into FabFlow AI's database.

    Parameters
    ----------
    db        : SQLAlchemy Session
    filepath  : Path to the .xlsx file (HVLM or LVHM variant)
    clear     : If True, truncate all fab tables before loading
    max_lots  : Limit lot count (useful for quick testing; 0 = no limit)
    horizon_minutes : Schedule horizon to derive due times
    """

    def __init__(
        self,
        db: Session,
        filepath: str | Path,
        clear: bool = False,
        max_lots: int = 0,
        horizon_minutes: int = 2880,
    ) -> None:
        self.db = db
        self.filepath = Path(filepath)
        self.clear = clear
        self.max_lots = max_lots
        self.horizon = horizon_minutes

        # Internal maps built during loading
        self._toolgroup_to_machine_ids: dict[str, list[int]] = {}
        self._recipe_cache: dict[str, int] = {}  # recipe_name → db id
        self._setup_group_to_toolgroup: dict[str, str] = {}

    # -----------------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------------

    def load(self) -> None:
        """Parse the Excel file and import all data into the database."""
        if not self.filepath.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.filepath}")

        logger.info("Loading SMT2020 dataset: %s", self.filepath.name)

        wb = openpyxl.load_workbook(self.filepath, read_only=True, data_only=True)
        sheets = {name: _read_sheet(wb[name]) for name in wb.sheetnames}
        wb.close()

        if self.clear:
            self._clear_all_tables()

        # Order matters — respect FK constraints
        self._load_machines(sheets.get("Toolgroups", []))
        self._load_maintenance(sheets.get("PM", []))
        self._load_failures(sheets.get("Breakdown", []))
        self._load_routes_and_lots(sheets, max_lots=self.max_lots)
        self._load_setups(sheets.get("Setups", []), sheets.get("Setup_Matrix_Implant_Gas", []))

        self.db.commit()
        logger.info("✓ SMT2020 dataset loaded successfully")

    # -----------------------------------------------------------------------
    # Table clearing
    # -----------------------------------------------------------------------

    def _clear_all_tables(self) -> None:
        """Delete all fab data before a fresh import."""
        logger.warning("Clearing all existing fab data …")
        for model in [ScheduledOperation, ScheduleResult, Operation, Lot,
                      SetupTime, Recipe, MachineFailure, MaintenanceWindow, Machine]:
            self.db.query(model).delete(synchronize_session=False)
        self.db.flush()
        logger.info("All fab tables cleared")

    # -----------------------------------------------------------------------
    # Machines (Toolgroups sheet)
    # -----------------------------------------------------------------------

    def _load_machines(self, rows: list[dict]) -> None:
        """
        Each row in Toolgroups = one machine group (toolgroup).
        NUMBER OF TOOLS tells us how many physical tools are in the group.
        We create one Machine row per physical tool: TOOLGROUP-01, TOOLGROUP-02, ...
        """
        created = 0
        for row in rows:
            toolgroup = str(row.get("TOOLGROUP", "")).strip()
            area      = str(row.get("AREA", "")).strip()
            n_tools   = _safe_int(row.get("NUMBER OF TOOLS"), 1)
            load_time = _safe_float(row.get("LOADINGTIME"), 0.0)
            uload_time = _safe_float(row.get("UNLOADINGTIME"), 0.0)
            setup_min  = _safe_int(load_time + uload_time, 0)
            stage      = _area_to_stage(area)

            # Check if already exists (idempotent)
            existing = (
                self.db.query(Machine)
                .filter(Machine.name.like(f"{toolgroup}-%"))
                .all()
            )
            if existing:
                self._toolgroup_to_machine_ids[toolgroup] = [m.id for m in existing]
                continue

            ids: list[int] = []
            for i in range(1, n_tools + 1):
                name = f"{toolgroup}-{i:02d}"
                m = Machine(
                    name=name,
                    tool_type=toolgroup,
                    status=MachineStatus.ACTIVE,
                    speed_factor=1.0,
                    default_setup_time_minutes=max(setup_min, 0),
                    candidate_stages=[stage.value],
                )
                self.db.add(m)
                self.db.flush()
                ids.append(m.id)
                created += 1

            self._toolgroup_to_machine_ids[toolgroup] = ids

        logger.info("Machines: created %d tool instances across %d toolgroups",
                    created, len(self._toolgroup_to_machine_ids))

    # -----------------------------------------------------------------------
    # Maintenance windows (PM sheet)
    # -----------------------------------------------------------------------

    def _load_maintenance(self, rows: list[dict]) -> None:
        """
        PM sheet: planned maintenance events with MTBPM and TTR.
        We create one MaintenanceWindow per PM event using mean values.
        Reference epoch: 2018-01-01 00:00 UTC (matches SMT2020 start date).
        """
        epoch = datetime(2018, 1, 1, tzinfo=timezone.utc)
        created = 0

        for row in rows:
            type_name  = str(row.get("TYPE NAME", "")).strip()
            mtbpm      = _safe_float(row.get("MTBeforePM"), 30.0)
            mtbpm_unit = str(row.get("MTBPM UNITS", "day")).lower()
            ttr_mean   = _safe_float(row.get("MEAN"), 10.0)
            ttr_unit   = str(row.get("TTR UNITS", "hr")).lower()

            # Convert to minutes
            if "day" in mtbpm_unit:
                start_offset_min = mtbpm * 24 * 60
            elif "hr" in mtbpm_unit or "hour" in mtbpm_unit:
                start_offset_min = mtbpm * 60
            else:
                start_offset_min = mtbpm  # assume minutes

            if "hr" in ttr_unit or "hour" in ttr_unit:
                duration_min = ttr_mean * 60
            elif "day" in ttr_unit:
                duration_min = ttr_mean * 24 * 60
            else:
                duration_min = ttr_mean  # assume minutes

            machine_ids = self._toolgroup_to_machine_ids.get(type_name, [])
            if not machine_ids:
                continue

            from datetime import timedelta
            start_dt = epoch + timedelta(minutes=start_offset_min)
            end_dt   = start_dt + timedelta(minutes=duration_min)

            # Use first machine in toolgroup as representative
            for mid in machine_ids[:1]:
                mw = MaintenanceWindow(
                    machine_id=mid,
                    start_time=start_dt,
                    end_time=end_dt,
                    reason=row.get("PM EVENT NAME", "Scheduled PM"),
                    is_recurring=True,
                    recurrence_days=int(mtbpm) if "day" in mtbpm_unit else None,
                )
                self.db.add(mw)
                created += 1

        self.db.flush()
        logger.info("Maintenance windows: %d created", created)

    # -----------------------------------------------------------------------
    # Machine failures (Breakdown sheet)
    # -----------------------------------------------------------------------

    def _load_failures(self, rows: list[dict]) -> None:
        """
        Breakdown sheet: unplanned failure distributions per area.
        We create MachineFailure records using mean MTTF/MTTR values.
        """
        epoch = datetime(2018, 1, 1, tzinfo=timezone.utc)
        created = 0

        for row in rows:
            type_name  = str(row.get("TYPE NAME", "")).strip()
            mttf       = _safe_float(row.get("MTTF"), 10080.0)
            mttf_unit  = str(row.get("MTTF UNITS", "min")).lower()
            mttr       = _safe_float(row.get("MTTR"), 60.0)
            mttr_unit  = str(row.get("MTTR UNITS", "min")).lower()

            if "hr" in mttf_unit:
                mttf_min = mttf * 60
            elif "day" in mttf_unit:
                mttf_min = mttf * 1440
            else:
                mttf_min = mttf

            if "hr" in mttr_unit:
                mttr_min = int(mttr * 60)
            elif "day" in mttr_unit:
                mttr_min = int(mttr * 1440)
            else:
                mttr_min = int(mttr)

            # Find machines in this area (type_name maps to area/toolgroup prefix)
            matching_ids: list[int] = []
            for tg, ids in self._toolgroup_to_machine_ids.items():
                if type_name.lower() in tg.lower() or tg.lower() in type_name.lower():
                    matching_ids.extend(ids[:1])  # one representative per toolgroup

            from datetime import timedelta
            for mid in matching_ids:
                failure_start = epoch + timedelta(minutes=mttf_min)
                f = MachineFailure(
                    machine_id=mid,
                    start_time=failure_start,
                    duration_minutes=max(1, mttr_min),
                    failure_mode=row.get("DOWN EVENT NAME", "BREAKDOWN"),
                    mttr_minutes=mttr_min,
                    is_simulated=False,
                )
                self.db.add(f)
                created += 1

        self.db.flush()
        logger.info("Machine failures: %d records created", created)

    # -----------------------------------------------------------------------
    # Routes, Recipes, and Lots
    # -----------------------------------------------------------------------

    def _load_routes_and_lots(
        self, sheets: dict[str, list[dict]], max_lots: int = 0
    ) -> None:
        """
        Parse Route_* sheets → create Recipe rows (one per unique TOOLGROUP+AREA).
        Parse Lotrelease sheet → create Lot + Operation rows.
        """
        # Collect all route sheet names
        route_sheets = {k: v for k, v in sheets.items() if k.startswith("Route_")}
        lotrelease   = sheets.get("Lotrelease", [])

        # Step 1: Build recipe registry from all route steps
        recipe_registry: dict[str, dict] = {}  # key = toolgroup
        for sheet_name, rows in route_sheets.items():
            for row in rows:
                toolgroup = str(row.get("TOOLGROUP", "")).strip()
                area      = str(row.get("AREA", "")).strip()
                pt_mean   = _safe_float(row.get("MEAN"), 30.0)
                pt_unit   = str(row.get("PT UNITS", "min")).lower()
                if "hr" in pt_unit:
                    pt_min = int(pt_mean * 60)
                else:
                    pt_min = max(1, int(pt_mean))

                desc = str(row.get("STEP DESCRIPTION", toolgroup))
                if toolgroup not in recipe_registry:
                    recipe_registry[toolgroup] = {
                        "toolgroup": toolgroup,
                        "area": area,
                        "stage": _area_to_stage(area),
                        "nominal_cycle_time_minutes": pt_min,
                        "description": desc,
                    }

        # Step 2: Insert recipes
        recipe_count = 0
        for toolgroup, rdata in recipe_registry.items():
            recipe_name = f"RECIPE-{toolgroup}"
            if recipe_name in self._recipe_cache:
                continue
            existing = self.db.query(Recipe).filter(Recipe.name == recipe_name).first()
            if existing:
                self._recipe_cache[recipe_name] = existing.id
                continue
            r = Recipe(
                name=recipe_name,
                stage=rdata["stage"],
                tool_type=toolgroup,
                nominal_cycle_time_minutes=rdata["nominal_cycle_time_minutes"],
                description=rdata["description"][:200] if rdata["description"] else None,
            )
            self.db.add(r)
            self.db.flush()
            self._recipe_cache[recipe_name] = r.id
            recipe_count += 1

        logger.info("Recipes: %d created", recipe_count)

        # Step 3: Populate candidate_machine_ids for each toolgroup
        toolgroup_machine_ids: dict[str, list[int]] = self._toolgroup_to_machine_ids

        # Step 4: Create lots + operations from Lotrelease + Routes
        epoch = datetime(2018, 1, 1, tzinfo=timezone.utc)
        lot_count = 0
        op_count = 0

        for lot_row in lotrelease:
            if max_lots and lot_count >= max_lots:
                break

            product_name  = str(lot_row.get("PRODUCT NAME", "")).strip()
            route_name    = str(lot_row.get("ROUTE NAME", "")).strip()
            lot_type      = str(lot_row.get("LOT NAME/TYPE", "")).strip()
            priority_val  = _safe_int(lot_row.get("PRIORITY"), 10)
            is_hot_str    = str(lot_row.get("SUPERHOTLOT", "no")).lower()
            wafers        = _safe_int(lot_row.get("WAFERS PER LOT"), 25)
            release_dist  = _safe_float(lot_row.get("RELEASE INTERVAL"), 0.0)
            r_unit        = str(lot_row.get("R UNITS", "min")).lower()
            due_date_raw  = lot_row.get("DUE DATE")

            # Priority mapping: SUPERHOTLOT=yes → HOT, priority > 10 → HOT
            is_hot = is_hot_str == "yes" or priority_val > 10
            priority = LotPriority.HOT if is_hot else LotPriority.NORMAL

            # Release time in minutes from epoch
            if "hr" in r_unit:
                release_min = int(release_dist * 60)
            elif "day" in r_unit:
                release_min = int(release_dist * 1440)
            else:
                release_min = int(release_dist)

            # Due time in minutes from epoch
            if isinstance(due_date_raw, datetime):
                delta = due_date_raw.replace(tzinfo=timezone.utc) - epoch.replace(tzinfo=None).replace(tzinfo=timezone.utc)
                due_min = max(release_min + 60, int(delta.total_seconds() / 60))
            else:
                due_min = release_min + self.horizon

            # We create multiple lots per release (one lot per release event)
            # For simplicity, create the lot directly
            lot_num = lot_count + 1
            lot_name = f"{lot_type}-{lot_num:04d}"

            existing_lot = self.db.query(Lot).filter(Lot.name == lot_name).first()
            if existing_lot:
                lot_count += 1
                continue

            lot = Lot(
                name=lot_name,
                priority=priority,
                release_time_minutes=release_min,
                due_time_minutes=due_min,
                weight=3.0 if is_hot else 1.0,
                wafer_count=wafers,
                product_type=product_name,
                customer="SMT2020",
            )
            self.db.add(lot)
            self.db.flush()
            lot_count += 1

            # Get route steps from the corresponding route sheet
            route_rows = sheets.get(route_name, [])
            seq = 0
            for step_row in route_rows:
                toolgroup = str(step_row.get("TOOLGROUP", "")).strip()
                if not toolgroup:
                    continue
                recipe_name = f"RECIPE-{toolgroup}"
                recipe_id = self._recipe_cache.get(recipe_name)
                if recipe_id is None:
                    continue
                pt_mean = _safe_float(step_row.get("MEAN"), 30.0)
                pt_unit = str(step_row.get("PT UNITS", "min")).lower()
                pt_min  = max(1, int(pt_mean * 60 if "hr" in pt_unit else pt_mean))

                candidate_ids = toolgroup_machine_ids.get(toolgroup, [])

                op = Operation(
                    lot_id=lot.id,
                    recipe_id=recipe_id,
                    sequence_num=seq,
                    processing_time_minutes=pt_min,
                    candidate_machine_ids=candidate_ids,
                )
                self.db.add(op)
                seq += 1
                op_count += 1

        self.db.flush()
        logger.info("Lots: %d created | Operations: %d created", lot_count, op_count)

    # -----------------------------------------------------------------------
    # Setup times (Setups sheet)
    # -----------------------------------------------------------------------

    def _load_setups(
        self,
        setup_rows: list[dict],
        implant_matrix_rows: list[dict],
    ) -> None:
        """
        Parse both the Setups sheet (direct transitions) and the
        Setup_Matrix_Implant_Gas sheet (full implant gas change matrix).
        """
        created = 0

        # --- Standard Setups sheet ---
        for row in setup_rows:
            from_setup  = str(row.get("CURRENT SETUP", "")).strip()
            to_setup    = str(row.get("NEW SETUP", "")).strip()
            setup_min   = _safe_int(row.get("SETUP TIME"), 0)
            unit        = str(row.get("ST UNITS", "min")).lower()
            if "hr" in unit:
                setup_min = setup_min * 60

            # The setup names include the toolgroup (e.g. "DE_BE_13_1")
            # Extract toolgroup: everything up to last underscore+digit
            toolgroup = "_".join(from_setup.split("_")[:-1])
            from_recipe = f"RECIPE-{toolgroup}"
            to_recipe   = f"RECIPE-{toolgroup}"   # same tool, different config

            from_id = self._recipe_cache.get(from_recipe)
            to_id   = self._recipe_cache.get(to_recipe)

            if from_id is None or to_id is None or from_id == to_id:
                continue

            existing = (
                self.db.query(SetupTime)
                .filter(
                    SetupTime.from_recipe_id == from_id,
                    SetupTime.to_recipe_id == to_id,
                    SetupTime.tool_type == toolgroup,
                )
                .first()
            )
            if existing:
                continue

            st = SetupTime(
                from_recipe_id=from_id,
                to_recipe_id=to_id,
                tool_type=toolgroup,
                setup_minutes=setup_min,
            )
            self.db.add(st)
            created += 1

        self.db.flush()
        logger.info("Setup times: %d entries created", created)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import SMT2020 dataset into FabFlow AI database"
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the SMT2020 xlsx file (e.g. SMT_2020_Model_Data_-_HVLM.xlsx)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        default=False,
        help="Clear all existing fab data before importing",
    )
    parser.add_argument(
        "--max-lots",
        type=int,
        default=0,
        help="Max number of lots to import (0 = all)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=2880,
        help="Schedule horizon in minutes (default=2880 = 48h)",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        loader = SMT2020Loader(
            db=db,
            filepath=args.file,
            clear=args.clear,
            max_lots=args.max_lots,
            horizon_minutes=args.horizon,
        )
        loader.load()
        logger.info("Import complete. Run `python main.py` to start the API.")
    except Exception as exc:
        db.rollback()
        logger.exception("Import failed: %s", exc)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
