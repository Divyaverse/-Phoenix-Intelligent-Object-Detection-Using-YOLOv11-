# PHOENIX Deployment Guide

## Architecture Topology

PHOENIX runs as a modular monolith:
- **FastAPI Platform**: Serves REST APIs and manages WebSocket connections on port `8000`.
- **Streamlit Dashboard**: Provides web UI on port `8501`.
- **SQLite Database**: Local file storage (`phoenix.db`) for system state and audit logs.

## Local Execution

### 1. Set up Virtual Environment
```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch Backend Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Launch Dashboard
```bash
streamlit run dashboard/app.py --server.port 8501
```

## Container Deployment (Docker)

```bash
docker-compose up --build
```
