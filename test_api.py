import requests
import json
import time

BASE_URL = 'http://localhost:8000/api'

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def run_tests():
    try:
        # 1. Health Check
        print_header("1. API Health Check")
        r = requests.get(f"{BASE_URL}/health")
        r.raise_for_status()
        print(f"Status: {r.json()['status']} | DB Connected: {r.json()['db_connected']}")

        # 2. Check Jobs (Lots)
        print_header("2. Fetching SMT2020 Jobs (Lots) from Database")
        r = requests.get(f"{BASE_URL}/jobs")
        r.raise_for_status()
        lots = r.json()
        print(f"Found {len(lots)} active lots.")
        for lot in lots:
            print(f"  - Lot: {lot['name']:<20} | Priority: {lot['priority']:<6} | Due: {lot['due_time_minutes']} min | Total Operations: {len(lot['operations'])}")

        # 3. Check Machines
        print_header("3. Fetching Machine Data")
        r = requests.get(f"{BASE_URL}/machines?limit=5")
        r.raise_for_status()
        machines = r.json()
        print(f"Showing first 5 machines (out of 1400+ in dataset):")
        for m in machines:
            print(f"  - {m['name']:<15} | Type: {m['tool_type']:<15} | Status: {m['status']}")

        # 4. Run the Schedule - Scenario A: Standard
        print_header("4. Scenario A: Standard Production Run")
        lot_ids = [l['id'] for l in lots]
        
        payload_a = {
            "lot_ids": lot_ids,
            "max_ops_per_lot": 12,
            "horizon_minutes": 6000,
            "solver_time_limit_seconds": 10,
            "include_maintenance": False,
            "include_failures": False,
            "weights": {
                "makespan": 1.0,
                "idle_time": 0.3,
                "weighted_tardiness": 2.0,
                "penalty_cost": 3.0
            }
        }
        
        print("Sending scheduling request (Scenario A)...")
        r_a = requests.post(f"{BASE_URL}/schedule/run", json=payload_a)
        r_a.raise_for_status()
        sched_a = r_a.json()
        print(f"  Status: {sched_a['status']} | Makespan: {sched_a['makespan_minutes']} min")
        
        # 5. Run the Schedule - Scenario B: Disrupted Factory
        print_header("5. Scenario B: Disrupted (Machine Failures + New Priorities)")
        
        payload_b = {
            "lot_ids": lot_ids,
            "max_ops_per_lot": 12,
            "horizon_minutes": 6000,
            "solver_time_limit_seconds": 10,
            "include_maintenance": True,
            "include_failures": True, # The AI now has to route around broken machines!
            "weights": {
                "makespan": 0.5,
                "idle_time": 5.0,  # Force the AI to care heavily about keeping machines busy
                "weighted_tardiness": 1.0,
                "penalty_cost": 3.0
            }
        }
        
        print("Sending scheduling request (Scenario B)...")
        r_b = requests.post(f"{BASE_URL}/schedule/run", json=payload_b)
        r_b.raise_for_status()
        sched_b = r_b.json()
        print(f"  Status: {sched_b['status']} | Makespan: {sched_b['makespan_minutes']} min")

        # 6. Compare the Gantt Chart Assignments
        print_header("6. Comparison of First 8 Assignments")
        
        tasks_a = sched_a.get('gantt_data', {}).get('tasks', [])
        tasks_b = sched_b.get('gantt_data', {}).get('tasks', [])
        
        print(f"{'SCENARIO A (Standard)':<50} | {'SCENARIO B (Disrupted)':<50}")
        print("-" * 105)
        for i in range(8):
            ta = tasks_a[i] if i < len(tasks_a) else None
            tb = tasks_b[i] if i < len(tasks_b) else None
            
            str_a = f"{ta['start_minutes']:>3}m-{ta['end_minutes']:>4}m {ta['lot_name'][:12]} -> {ta['machine_name']}" if ta else ""
            str_b = f"{tb['start_minutes']:>3}m-{tb['end_minutes']:>4}m {tb['lot_name'][:12]} -> {tb['machine_name']}" if tb else ""
            
            print(f"{str_a:<50} | {str_b:<50}")

        print("\nNotice how Scenario B makes different routing choices to avoid breakdowns or optimize for idle time!")

    except requests.exceptions.RequestException as e:
        print(f"\n[ERROR] Could not connect to the API: {e}")
        print("Please ensure the FastAPI server is running with 'python main.py'")

if __name__ == '__main__':
    run_tests()
