# PHOENIX

> **Predictive Heat Observation and Emergency Navigation Intelligence System**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ⚠️ Important Safety & Scope Boundary

**PHOENIX is an AI-based emergency decision-support research prototype.**
- It is **NOT** a certified life-safety system.
- It is **NOT** a replacement for fire alarms, emergency procedures, or trained responders.
- It **CANNOT** guarantee safe evacuation.
- Large Language Models (LLMs) are strictly barred from selecting or altering evacuation routes. All evacuation routes are computed deterministically.

---

## 🚀 Key Pipeline

```
Camera / Video Source
        ↓
YOLOv11 Detection (Fire, Smoke, Person)
        ↓
Temporal Analysis (Smoke-region Growth Rate Δarea/Δt)
        ↓
Spatial Mapping / Camera Homography
        ↓
Deterministic Risk Engine & Heatmap
        ↓
Occupancy Estimation & Predicted Corridor Blockage
        ↓
NetworkX Multi-Factor Evacuation Routing
        ↓
Deterministic ETA Estimation
        ↓
FastAPI Backend & WebSocket Realtime Broadcasts
        ↓
Role-Specific React Dashboard
```

---

## 📂 Project Structure

```
phoenix/
├── app/
│   ├── api/            # REST API endpoints, schemas, dependencies
│   ├── core/           # Config, logging, errors, security
│   ├── domain/         # Models, enums, events, abstract interfaces
│   ├── perception/     # YOLO adapter, frame source, temporal tracker
│   ├── spatial/        # Homography, calibration, risk heatmap
│   ├── decision/       # Risk scoring, occupancy, prediction, routing, ETA
│   ├── graph/          # NetworkX navigation graph representation
│   ├── incidents/      # Emergency incident lifecycle service
│   ├── db/             # SQLite database and repository implementations
│   └── events/         # Event publisher and WebSocket broadcast bus
├── configs/            # Configurable YAML parameters & thresholds
├── frontend/           # Modern React user interface
├── datasets/           # Datasets and sample videos
├── models/             # YOLO checkpoint weights
├── scenarios/          # Evaluation test scenarios
├── tests/              # Comprehensive test suites (unit, integration, failure, etc.)
└── docs/               # Architecture, API, and Evaluation documentation
```

---

## 🛠️ Quick Start

```bash
# 1. Install backend dependencies
pip install -r requirements.txt

# 2. Run test suite
python -m pytest

# 3. Launch backend API server
uvicorn app.main:app --reload

# 4. Launch React frontend
cd frontend
npm install
npm run dev
```
