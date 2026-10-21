# PHOENIX Architecture Specification

## Overview

**PHOENIX** (Predictive Heat Observation and Emergency Navigation Intelligence System) is a modular engineering prototype providing AI-based emergency decision support.

```
                    ┌─────────────────────┐
                    │     VIDEO SOURCE    │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │   YOLO PERCEPTION   │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │  TEMPORAL ANALYSIS  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ SPATIAL / HOMOGRAPHY│
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │    RISK ENGINE      │
                    └──────────┬──────────┘
                               ↓
              ┌────────────────┴────────────────┐
              ↓                                 ↓
      ┌───────────────┐                 ┌────────────────┐
      │ OCCUPANCY     │                 │ PREDICTION     │
      └───────┬───────┘                 └───────┬────────┘
              └────────────────┬────────────────┘
                               ↓
                    ┌─────────────────────┐
                    │ NETWORKX ROUTING    │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │        ETA          │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │   DOMAIN EVENTS     │
                    └───────┬─────┬───────┘
                            ↓     ↓
                     ┌───────┐ ┌──────────┐
                     │SQLite │ │WebSocket │
                     └───────┘ └────┬─────┘
                                    ↓
                            ┌───────────────┐
                            │   React UI    │
                            │   Dashboard   │
                            └───────────────┘
```

## Modular Monolith Structure

To balance architectural isolation, high maintainability, and rapid execution, PHOENIX follows a clean layered domain-driven design:

1. **Domain (`app/domain/`)**:
   - Pure domain models (`models.py`), enums (`enums.py`), events (`events.py`), and abstract interfaces (`interfaces.py`).
   - Zero dependencies on external presentation frameworks.

2. **Core (`app/core/`)**:
   - Configuration management (`config.py`), logging (`logging.py`), error hierarchy (`errors.py`), and security tokens (`security.py`).

3. **Perception (`app/perception/`)**:
   - Video ingestion (`frame_source.py`), YOLO adapter (`detector.py`), and multi-frame temporal smoke tracker (`temporal.py`).

4. **Spatial Intelligence (`app/spatial/`)**:
   - Homography projection matrix calculations (`homography.py`), camera calibration checks (`calibration.py`), and dynamic grid heatmaps (`heatmap.py`).

5. **Decision Intelligence (`app/decision/`)**:
   - Deterministic risk scoring (`risk.py`), occupancy estimation (`occupancy.py`), corridor blockage forecasting (`prediction.py`), Dijkstra/A* routing (`routing.py`), and travel time estimation (`eta.py`).

6. **Graph Representation (`app/graph/`)**:
   - NetworkX navigable topological graph (`navigation_graph.py`) representing rooms, corridors, stairwells, exits, and hazard zones.

7. **Platform & APIs (`app/api/`)**:
   - FastAPI REST endpoints, Pydantic schemas, dependency injection, and JWT-authenticated routes.

8. **Realtime Bus (`app/events/`)**:
   - In-memory event bus and WebSocket client publisher delivering structured event envelopes.

9. **Persistence (`app/db/`)**:
   - SQLite repositories with atomic transaction guarantees and idempotency keys.

10. **Frontend UI (`frontend/`)**:
    - Modern React web interface with role-tailored views (SuperAdmin, Building Manager, First Responder, Occupant), interactive floorplan rendering, live WebSocket updates, and HTTP polling fallback.

## Safety & Non-Goals

- **Decision-Support Only**: PHOENIX is not a life-safety certified alarm or automated suppression system.
- **Auditable Decisions**: Every evacuation route calculation contains an explicit breakdown of its cost components (distance, hazard, occupancy, prediction).
- **No LLM in Critical Path**: Routing decisions are computed deterministically via NetworkX and graph algorithms, never generated or modified by an LLM.
