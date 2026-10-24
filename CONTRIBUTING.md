# 🤝 Contributing to AIOps Root Cause Correlator

Thank you for your interest in contributing to **AIOps Root Cause Correlator**! This project is designed as an autonomous distributed incident correlation and causal inference platform.

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- Python 3.12+
- Node.js 18+ & npm
- Docker (optional for containerized Kafka & Redis)

### 2. Backend Verification
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
python -m pytest tests/unit -v
```

### 3. Frontend Verification
```bash
cd aiops-frontend
npm install
npm run build
npm run dev
```

---

## ✅ Pre-Pull Request Checklist

Before submitting a Pull Request, please ensure:
1. **Tests Pass:** All unit tests pass cleanly (`python -m pytest tests/unit -q`).
2. **Frontend Builds:** `npm run build` succeeds with zero errors or warnings.
3. **No N+1 SQL Queries:** Database queries must use bulk eager loading / joins.
4. **Deterministic Causal Math:** Anomaly detection & correlation logic must remain deterministic and reproducible.
5. **Conventional Commits:** Use standard prefixes (`feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, `test:`, `chore:`).

---

## 🏛️ Code Architecture Boundaries
- `backend/app/engines/`: Pure deterministic domain algorithms (Fourier EWMA, MicroRCA++, OTel Trace Attribution, eBPF Probes, Thompson Sampling).
- `backend/app/api/v1/`: Thin asynchronous FastAPI route handlers with threadpool offloading.
- `backend/app/models/`: SQLAlchemy 2.0 models and Pydantic v2 schemas.
- `aiops-frontend/src/`: React 18, Three.js WebGL spatial topology, and Framer Motion glassmorphic UI.
