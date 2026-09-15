"""FastAPI service: WebSocket state stream + JPEG frame + control endpoints."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .pipeline import YoloCountPipeline

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PILL = ROOT / "models" / "pill-nano.pt"
DEFAULT_FALLBACK = "yolov8n.pt"

pipeline: Optional[YoloCountPipeline] = None
clients: set[WebSocket] = set()
_broadcast_task: Optional[asyncio.Task] = None


class ConfigBody(BaseModel):
    direction: Optional[str] = None
    line_pos: Optional[float] = Field(default=None, ge=0.05, le=0.95)
    conf: Optional[float] = Field(default=None, ge=0.05, le=0.95)


def resolve_model(path: Optional[str]) -> tuple[str, Optional[str]]:
    if path:
        return path, None
    if DEFAULT_PILL.exists():
        return str(DEFAULT_PILL), None
    return DEFAULT_FALLBACK, (
        "models/pill-nano.pt ausente — usando yolov8n.pt (não é modelo de comprimido)"
    )


def create_app(source: str | int = 0, model: Optional[str] = None) -> FastAPI:
    global pipeline

    model_path, warning = resolve_model(model)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global pipeline, _broadcast_task
        pipeline = YoloCountPipeline(model_path=model_path, source=source)
        pipeline.model_warning = warning
        pipeline.open()
        _broadcast_task = asyncio.create_task(_broadcast_loop())
        yield
        if _broadcast_task:
            _broadcast_task.cancel()
        if pipeline:
            pipeline.close()

    app = FastAPI(title="Esteira YOLO Counter", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "total": pipeline.total if pipeline else 0,
            "model": model_path,
            "warning": warning,
        }

    @app.post("/reset")
    def reset():
        assert pipeline
        pipeline.reset()
        return {"total": 0}

    @app.post("/config")
    def config(body: ConfigBody):
        assert pipeline
        pipeline.set_config(
            direction=body.direction,
            line_pos=body.line_pos,
            conf=body.conf,
        )
        return pipeline._state()

    @app.post("/pause")
    def pause(paused: bool = True):
        assert pipeline
        pipeline.paused = paused
        return {"paused": pipeline.paused}

    @app.get("/frame.jpg")
    def frame_jpg():
        assert pipeline
        if pipeline.last_frame is None:
            return Response(status_code=404)
        frame = pipeline.last_frame.copy()
        # draw line
        h, w = frame.shape[:2]
        pos = pipeline.counter.line_pos
        if pipeline.counter.direction in ("ltr", "rtl"):
            x = int(w * pos)
            cv2.line(frame, (x, 0), (x, h), (0, 220, 255), 2)
        else:
            y = int(h * pos)
            cv2.line(frame, (0, y), (w, y), (0, 220, 255), 2)
        for b in pipeline._boxes:
            x1, y1, x2, y2 = map(int, (b["x1"], b["y1"], b["x2"], b["y2"]))
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 80), 2)
            cv2.putText(
                frame,
                str(b["id"]),
                (x1, max(12, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            return Response(status_code=500)
        return Response(content=buf.tobytes(), media_type="image/jpeg")

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        clients.add(websocket)
        try:
            if pipeline:
                await websocket.send_text(json.dumps(pipeline._state()))
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("type") == "reset" and pipeline:
                    pipeline.reset()
                elif msg.get("type") == "config" and pipeline:
                    pipeline.set_config(
                        direction=msg.get("direction"),
                        line_pos=msg.get("line_pos"),
                        conf=msg.get("conf"),
                    )
                elif msg.get("type") == "pause" and pipeline:
                    pipeline.paused = bool(msg.get("paused", True))
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(websocket)

    return app


async def _broadcast_loop():
    while True:
        if pipeline:
            # run CV step in thread to avoid blocking event loop
            state = await asyncio.to_thread(pipeline.step)
            dead = []
            payload = json.dumps(state)
            for ws in list(clients):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                clients.discard(ws)
        await asyncio.sleep(0.03)
