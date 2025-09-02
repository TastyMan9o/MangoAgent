import os
import importlib
from fastapi.testclient import TestClient


def test_health_endpoint():
    # Lazy import to avoid side effects at import time
    main = importlib.import_module("main")
    app = getattr(main, "app")
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json().get("ok") is True 