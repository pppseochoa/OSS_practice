"""HTTP integration check using only Python stdlib; no server lifecycle ownership."""
import json
import sys
import time
from urllib.request import Request, urlopen

base = sys.argv[1].rstrip("/")
for attempt in range(60):
    try:
        with urlopen(base + "/health", timeout=2) as response:
            assert json.load(response)["status"] == "ok"
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(1)
for path in ("/", "/static/app.js", "/static/styles.css"):
    with urlopen(base + path, timeout=5) as response:
        assert response.status == 200
        content = response.read()
        assert content
        if path == "/":
            assert b'data-api-url="/"' in content, "Container must use same-origin API"
for kind, stats in (("batter", {"games": 120}), ("pitcher", {"wins": 10})):
    request = Request(base + "/api/v1/predict", data=json.dumps({"player_type": kind, "stats": stats}).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        data = json.load(response)
    assert type(data["suggested_salary_krw"]) is int and data["suggested_salary_krw"] > 0
    print(f"HTTP prediction OK: {kind}={data['suggested_salary_krw']} KRW")
print("Web/static/API HTTP checks passed")
