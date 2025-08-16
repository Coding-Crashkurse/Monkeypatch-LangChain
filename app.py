import logging
from collections import deque
from threading import Lock
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("autolog-server")

BUFFER_LOCK = Lock()
LOG_BUFFER = deque(maxlen=1000)


class LogEvent(BaseModel):
    run_id: str
    node_type: str
    name: str
    event: str
    t: float
    args: Optional[Any] = None
    kwargs: Optional[Any] = None
    duration_ms: Optional[int] = None
    output: Optional[Any] = None
    error: Optional[Any] = None


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/logs")
async def get_logs():
    with BUFFER_LOCK:
        return list(LOG_BUFFER)


@app.post("/api/log")
async def log_event(event: LogEvent):
    with BUFFER_LOCK:
        LOG_BUFFER.append(event.model_dump())
    log.info(
        f"POST /api/log -> event={event.event}, name={event.name}, total={len(LOG_BUFFER)}"
    )
    return {"ok": True}


app.mount("/assets", StaticFiles(directory="autolog-ui/dist/assets"), name="assets")


@app.get("/{full_path:path}")
async def serve_react_app(request: Request, full_path: str):
    return FileResponse("autolog-ui/dist/index.html")
