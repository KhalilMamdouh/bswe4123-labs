"""Health-check service for Assignment 1."""
import os
import time
from fastapi import FastAPI

app = FastAPI(title="Service Health")
STARTED_AT = time.time()
DEFAULT_DELAY = float(os.getenv("HEALTH_DELAY", "0"))

@app.get("/health")
def health():
    delay = max(0.0, DEFAULT_DELAY)
    if delay:
        time.sleep(delay)
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - STARTED_AT, 2)
    }
