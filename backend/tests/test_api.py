"""
tests/test_api.py

Integration tests for the FabFlow AI REST API.

Uses FastAPI TestClient with an in-memory SQLite database (isolated per
test session via a module-scoped fixture).

Coverage
--------
TestHealthEndpoint
    test_health_ok            — GET /api/health returns 200

TestMachinesEndpoint
    test_create_machine        — POST /api/machines → 201
    test_list_machines         — GET /api/machines → 200 list
    test_get_machine_not_found — GET /api/machines/9999 → 404
    test_update_machine        — PATCH /api/machines/{id} → 200
    test_delete_machine        — DELETE /api/machines/{id} → 204
    test_duplicate_machine     — POST duplicate name → 409

TestRecipesEndpoint
    test_create_recipe         — POST /api/recipes → 201
    test_list_recipes          — GET /api/recipes → 200 list
    test_get_recipe_not_found  — GET /api/recipes/9999 → 404

TestJobsEndpoint
    test_create_lot            — POST /api/jobs → 201 with operations
    test_list_lots             — GET /api/jobs → 200 list
    test_get_lot_not_found     — GET /api/jobs/9999 → 404
    test_hot_lot_priority      — priority field correctly stored
    test_invalid_due_before_release — due <= release → 422

TestScheduleEndpoint
    test_run_schedule_empty_db — no lots → 422 (informative error)
    test_full_schedule_pipeline — create data + run schedule + verify response

TestAnalyticsEndpoint
    test_analytics_not_found   — GET /api/analytics/9999 → 404

TestSimulationEndpoint
    test_simulation_not_found  — POST /api/simulation/run bad id → 404
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.orm import sessionmaker

from database.session import Base, get_db
from main import app


# ---------------------------------------------------------------------------
# Test database: isolated in-memory SQLite per test session
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite:///./fabflow_test.db"

test_engine = sa_create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = sessionmaker(
    bind=test_engine, autocommit=False, autoflush=False, expire_on_commit=False
)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient with isolated test database."""
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def create_scanner(client: TestClient, name: str = "TEST-LITH-01") -> dict:
    resp = client.post("/api/machines", json={
        "name": name,
        "tool_type": "SCANNER",
        "status": "ACTIVE",
        "speed_factor": 1.0,
        "default_setup_time_minutes": 30,
        "candidate_stages": ["LITHOGRAPHY"],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_etcher(client: TestClient, name: str = "TEST-ETCH-01") -> dict:
    resp = client.post("/api/machines", json={
        "name": name,
        "tool_type": "RIE_ETCHER",
        "status": "ACTIVE",
        "speed_factor": 1.0,
        "default_setup_time_minutes": 20,
        "candidate_stages": ["ETCH"],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_dep(client: TestClient, name: str = "TEST-DEP-01") -> dict:
    resp = client.post("/api/machines", json={
        "name": name,
        "tool_type": "CVD_CHAMBER",
        "status": "ACTIVE",
        "speed_factor": 1.0,
        "default_setup_time_minutes": 15,
        "candidate_stages": ["DEPOSITION"],
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def create_recipe(client: TestClient, name: str, stage: str, tool_type: str, cycle: int) -> dict:
    resp = client.post("/api/recipes", json={
        "name": name,
        "stage": stage,
        "tool_type": tool_type,
        "nominal_cycle_time_minutes": cycle,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


# ===========================================================================
# Health
# ===========================================================================


class TestHealthEndpoint:
    def test_health_ok(self, client: TestClient):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["db_connected"], bool)
        assert "version" in data


# ===========================================================================
# Machines
# ===========================================================================


class TestMachinesEndpoint:
    def test_create_machine(self, client: TestClient):
        resp = client.post("/api/machines", json={
            "name": "API-LITH-01",
            "tool_type": "SCANNER",
            "status": "ACTIVE",
            "speed_factor": 1.0,
            "default_setup_time_minutes": 30,
            "candidate_stages": ["LITHOGRAPHY"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API-LITH-01"
        assert data["tool_type"] == "SCANNER"
        assert "id" in data

    def test_list_machines(self, client: TestClient):
        resp = client.get("/api/machines")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_machine_not_found(self, client: TestClient):
        resp = client.get("/api/machines/99999")
        assert resp.status_code == 404

    def test_update_machine(self, client: TestClient):
        machine = create_scanner(client, "UPD-LITH-01")
        mid = machine["id"]
        resp = client.patch(f"/api/machines/{mid}", json={"status": "MAINTENANCE"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "MAINTENANCE"

    def test_delete_machine(self, client: TestClient):
        machine = create_scanner(client, "DEL-LITH-01")
        mid = machine["id"]
        resp = client.delete(f"/api/machines/{mid}")
        assert resp.status_code == 204
        # Verify gone
        resp2 = client.get(f"/api/machines/{mid}")
        assert resp2.status_code == 404

    def test_duplicate_machine_name(self, client: TestClient):
        create_scanner(client, "DUP-LITH-01")
        resp = client.post("/api/machines", json={
            "name": "DUP-LITH-01",
            "tool_type": "SCANNER",
            "status": "ACTIVE",
            "speed_factor": 1.0,
            "default_setup_time_minutes": 30,
        })
        assert resp.status_code == 409


# ===========================================================================
# Recipes
# ===========================================================================


class TestRecipesEndpoint:
    def test_create_recipe(self, client: TestClient):
        resp = client.post("/api/recipes", json={
            "name": "TEST-LITHO-001",
            "stage": "LITHOGRAPHY",
            "tool_type": "SCANNER",
            "nominal_cycle_time_minutes": 45,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "TEST-LITHO-001"
        assert data["stage"] == "LITHOGRAPHY"

    def test_list_recipes(self, client: TestClient):
        resp = client.get("/api/recipes")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_recipe_not_found(self, client: TestClient):
        resp = client.get("/api/recipes/99999")
        assert resp.status_code == 404

    def test_duplicate_recipe_name(self, client: TestClient):
        client.post("/api/recipes", json={
            "name": "DUP-RECIPE-001",
            "stage": "ETCH",
            "tool_type": "RIE_ETCHER",
            "nominal_cycle_time_minutes": 30,
        })
        resp = client.post("/api/recipes", json={
            "name": "DUP-RECIPE-001",
            "stage": "ETCH",
            "tool_type": "RIE_ETCHER",
            "nominal_cycle_time_minutes": 30,
        })
        assert resp.status_code == 409


# ===========================================================================
# Jobs (Lots)
# ===========================================================================


class TestJobsEndpoint:
    def test_create_lot_with_operations(self, client: TestClient):
        # Set up prerequisites
        m_lith = create_scanner(client, "JOB-LITH-01")
        m_etch = create_etcher(client, "JOB-ETCH-01")
        m_dep = create_dep(client, "JOB-DEP-01")
        r_lith = create_recipe(client, "JOB-LITHO-R1", "LITHOGRAPHY", "SCANNER", 45)
        r_etch = create_recipe(client, "JOB-ETCH-R1", "ETCH", "RIE_ETCHER", 30)
        r_dep = create_recipe(client, "JOB-DEP-R1", "DEPOSITION", "CVD_CHAMBER", 50)

        resp = client.post("/api/jobs", json={
            "name": "LOT-TEST-001",
            "priority": "NORMAL",
            "release_time_minutes": 0,
            "due_time_minutes": 300,
            "weight": 1.0,
            "wafer_count": 25,
            "operations": [
                {"recipe_id": r_lith["id"], "sequence_num": 0, "candidate_machine_ids": [m_lith["id"]]},
                {"recipe_id": r_etch["id"], "sequence_num": 1, "candidate_machine_ids": [m_etch["id"]]},
                {"recipe_id": r_dep["id"],  "sequence_num": 2, "candidate_machine_ids": [m_dep["id"]]},
            ],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "LOT-TEST-001"
        assert data["priority"] == "NORMAL"
        assert len(data["operations"]) == 3

    def test_list_lots(self, client: TestClient):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_lot_not_found(self, client: TestClient):
        resp = client.get("/api/jobs/99999")
        assert resp.status_code == 404

    def test_hot_lot_priority_stored(self, client: TestClient):
        m = create_scanner(client, "HOT-LITH-01")
        r = create_recipe(client, "HOT-LITHO-R1", "LITHOGRAPHY", "SCANNER", 55)
        resp = client.post("/api/jobs", json={
            "name": "LOT-HOT-TEST",
            "priority": "HOT",
            "release_time_minutes": 0,
            "due_time_minutes": 200,
            "weight": 3.0,
            "wafer_count": 25,
            "operations": [
                {"recipe_id": r["id"], "sequence_num": 0, "candidate_machine_ids": [m["id"]]},
            ],
        })
        assert resp.status_code == 201
        assert resp.json()["priority"] == "HOT"

    def test_invalid_due_before_release(self, client: TestClient):
        """due_time_minutes <= release_time_minutes must be rejected with 422."""
        resp = client.post("/api/jobs", json={
            "name": "LOT-INVALID",
            "priority": "NORMAL",
            "release_time_minutes": 500,
            "due_time_minutes": 100,   # due < release → invalid
            "weight": 1.0,
            "wafer_count": 25,
            "operations": [],
        })
        assert resp.status_code == 422

    def test_delete_lot(self, client: TestClient):
        m = create_scanner(client, "DEL-LOT-LITH-01")
        r = create_recipe(client, "DEL-LOT-R1", "LITHOGRAPHY", "SCANNER", 45)
        lot_resp = client.post("/api/jobs", json={
            "name": "LOT-TO-DELETE",
            "priority": "NORMAL",
            "release_time_minutes": 0,
            "due_time_minutes": 300,
            "weight": 1.0,
            "wafer_count": 25,
            "operations": [
                {"recipe_id": r["id"], "sequence_num": 0, "candidate_machine_ids": [m["id"]]},
            ],
        })
        assert lot_resp.status_code == 201
        lot_id = lot_resp.json()["id"]
        del_resp = client.delete(f"/api/jobs/{lot_id}")
        assert del_resp.status_code == 204


# ===========================================================================
# Schedule pipeline
# ===========================================================================


class TestScheduleEndpoint:
    def test_run_schedule_no_lots(self, client: TestClient):
        """If no lots exist (or filtered out), expect 422."""
        resp = client.post("/api/schedule/run", json={
            "lot_ids": [999998, 999999],   # non-existent
            "horizon_minutes": 480,
            "solver_time_limit_seconds": 5,
        })
        assert resp.status_code == 422

    def test_full_schedule_pipeline(self, client: TestClient):
        """End-to-end: create machine+recipe+lot → run schedule → verify response."""
        # Create minimal fab setup
        m_lith = create_scanner(client, "SCH-LITH-01")
        m_etch = create_etcher(client, "SCH-ETCH-01")
        m_dep = create_dep(client, "SCH-DEP-01")
        r_lith = create_recipe(client, "SCH-LITHO-R1", "LITHOGRAPHY", "SCANNER", 30)
        r_etch = create_recipe(client, "SCH-ETCH-R1", "ETCH", "RIE_ETCHER", 25)
        r_dep = create_recipe(client, "SCH-DEP-R1", "DEPOSITION", "CVD_CHAMBER", 40)

        lot_resp = client.post("/api/jobs", json={
            "name": "LOT-SCH-001",
            "priority": "NORMAL",
            "release_time_minutes": 0,
            "due_time_minutes": 300,
            "weight": 1.0,
            "wafer_count": 25,
            "operations": [
                {"recipe_id": r_lith["id"], "sequence_num": 0, "candidate_machine_ids": [m_lith["id"]]},
                {"recipe_id": r_etch["id"], "sequence_num": 1, "candidate_machine_ids": [m_etch["id"]]},
                {"recipe_id": r_dep["id"],  "sequence_num": 2, "candidate_machine_ids": [m_dep["id"]]},
            ],
        })
        assert lot_resp.status_code == 201
        lot_id = lot_resp.json()["id"]

        # Run schedule
        schedule_resp = client.post("/api/schedule/run", json={
            "lot_ids": [lot_id],
            "horizon_minutes": 480,
            "solver_time_limit_seconds": 15,
            "weights": {
                "makespan": 1.0,
                "idle_time": 0.5,
                "weighted_tardiness": 2.0,
                "penalty_cost": 3.0,
            },
        })
        assert schedule_resp.status_code == 201
        sched = schedule_resp.json()
        assert sched["status"] in ("OPTIMAL", "FEASIBLE")
        assert sched["makespan_minutes"] is not None
        assert sched["makespan_minutes"] >= 30
        assert sched["gantt_data"] is not None
        assert sched["kpi_data"] is not None

        schedule_id = sched["id"]

        # Verify GET /api/schedule/{id}
        get_resp = client.get(f"/api/schedule/{schedule_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == schedule_id

        # Verify GET /api/schedule list
        list_resp = client.get("/api/schedule")
        assert list_resp.status_code == 200
        ids = [s["id"] for s in list_resp.json()]
        assert schedule_id in ids


# ===========================================================================
# Analytics
# ===========================================================================


class TestAnalyticsEndpoint:
    def test_analytics_not_found(self, client: TestClient):
        resp = client.get("/api/analytics/99999")
        assert resp.status_code == 404


# ===========================================================================
# Simulation
# ===========================================================================


class TestSimulationEndpoint:
    def test_simulation_not_found(self, client: TestClient):
        resp = client.post("/api/simulation/run", json={
            "schedule_result_id": 99999,
            "simulation_horizon_minutes": 480,
            "num_replications": 1,
        })
        assert resp.status_code == 404
