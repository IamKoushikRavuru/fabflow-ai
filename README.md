# 🏭 FabFlow AI — Intelligent Semiconductor Fab Scheduling & Optimization

> **Autonomous, multi-objective scheduling platform for semiconductor wafer fabrication using Google OR-Tools CP-SAT constraint programming, SimPy discrete-event simulation, and a modern responsive React control dashboard.**

---

## ⚡ Overview

**FabFlow AI** solves the **Flexible Job Shop Scheduling Problem (FJSSP)** specifically designed for the complexities of modern semiconductor wafer manufacturing:

- 🔬 **Complex Wafer Routings**: Multiple stages (Lithography, Etch, CVD Deposition, CMP, Ion Implantation, Metrology/Inspection).
- ⏱️ **Sequence-Dependent Setup Times**: Real-world changeover matrix between different process recipes (e.g. 248nm vs 193nm lithography, oxide vs nitride etch).
- 🚨 **Lot Priorities & Financial Penalties**: Objective optimization weighing makespan, machine idle time, weighted tardiness, and rush customer lot penalties ($100/min hot lot vs $10/min standard).
- 🛠️ **Disruption Simulation & Dynamic Rescheduling**: Machine breakdowns, scheduled maintenance windows, and automatic routing around downed equipment.
- 📊 **Interactive Web Dashboard**: React 19 + Vite + Tailwind CSS with Gantt timelines, machine health metrics, KPI analytics, and scenario modeling.

---

## 🏗️ Architecture

```
fabflow-ai/
├── backend/                  # FastAPI Application & Scheduling Engine
│   ├── analytics/            # Fab KPI calculations & throughput metrics
│   ├── api/                  # REST endpoints (machines, recipes, jobs, schedule, simulation, etc.)
│   ├── database/             # SQLAlchemy 2.0 database models & session management
│   ├── loaders/              # Dataset parsers & SMT2020 benchmark loaders
│   ├── models/               # Pydantic & SQLAlchemy ORM schemas
│   ├── scheduler/            # Google OR-Tools CP-SAT scheduling engine & validators
│   ├── simulation/           # SimPy discrete-event fab simulation engine
│   ├── tests/                # Pytest test suite (35 unit & integration tests)
│   ├── main.py               # Application entry point & realistic fab data seeder
│   └── requirements.txt      # Python dependencies
├── ui/                       # React 19 Frontend Dashboard
│   ├── src/                  # Components, pages, hooks, state, and API clients
│   ├── vite.config.ts        # Vite configuration with /api proxy to port 8000
│   └── package.json          # UI dependencies (Tailwind, Lucide, Recharts, Framer Motion)
├── test_api.py               # End-to-end verification script for standard vs disrupted scenarios
└── README.md
```

---

## 🚀 Quick Start Guide

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & **npm**

### 1. Backend Setup

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server (runs on http://localhost:8000)
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 2. Frontend Setup

In a new terminal:

```bash
cd ui

# Install UI dependencies
npm install

# Start Vite development server (runs on http://localhost:5174)
npm run dev
```

Open [http://localhost:5174](http://localhost:5174) in your browser to access the control center.

### 3. Run Automated Tests

To run the complete backend test suite (35 tests covering solver constraints, validators, and REST API):

```bash
cd backend
pytest
```

To run the end-to-end scheduling comparison script:

```bash
python test_api.py
```

---

## 🧪 Optimization Features

| Feature | Description |
| :--- | :--- |
| **CP-SAT Solver Engine** | Formulates exact non-overlapping interval constraints across heterogeneous toolsets |
| **Weighted Objectives** | Custom balancing for Makespan, Machine Idle Time, Weighted Tardiness, and Penalty Costs |
| **Maintenance Awareness** | Hard-blocks scheduled maintenance intervals to ensure zero job collision |
| **Dynamic Rescheduling** | Handles unexpected machine failures by dynamically routing queued lots to alternate tools |
| **Schedule Validator** | Rigorous post-solver verification ensuring zero temporal overlaps, precedence compliance, and valid recipe transitions |

---

## 📦 Docker Deployment

You can run the entire stack with PostgreSQL using Docker Compose:

```bash
cd backend
docker-compose up --build
```

---

## 📄 License

MIT License.
