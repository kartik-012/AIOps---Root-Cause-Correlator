"""Server entrypoint runner for AIOps Root Cause Correlator."""

import uvicorn
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print("=" * 60)
    print("   AIOps ROOT CAUSE CORRELATOR — FASTAPI SERVER")
    print("=" * 60)
    print(f"Server URL   : http://127.0.0.1:8001")
    print(f"Swagger Docs : http://127.0.0.1:8001/docs")
    print(f"WebSocket    : ws://127.0.0.1:8001/ws/incidents")
    print("-" * 60)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)
