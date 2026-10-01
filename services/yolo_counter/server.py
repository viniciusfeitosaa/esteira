"""FastAPI service: WebSocket state stream + JPEG frame + control endpoints."""

from __future__ import annotations

import asyncio
import json
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from .pipeline import YoloCountPipeline
from .sources import describe, list_cameras, list_videos, resolve_video

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PILL = ROOT / "models" / "pill-nano.pt"
DEFAULT_FALLBACK = "yolov8n.pt"

pipeline: Optional[YoloCountPipeline] = None
clients: set[WebSocket] = set()
_broadcast_task: Optional[asyncio.Task] = None
_broadcast_interval = 0.03
_jpeg_quality = 80


class ConfigBody(BaseModel):
    direction: Optional[str] = None
    line_pos: Optional[float] = Field(default=None, ge=0.05, le=0.95)
    conf: Optional[float] = Field(default=None, ge=0.05, le=0.95)
    roi: Optional[list[float]] = Field(default=None, min_length=4, max_length=4)


class SourceBody(BaseModel):
    # indice da camera (0, 1, 2…) ou caminho de um video de samples/videos (ver GET /sources)
    source: int | str


def _roi_tuple(v: Any) -> Optional[tuple[float, float, float, float]]:
    if not v or len(v) != 4:
        return None
    x0, y0, x1, y1 = (min(1.0, max(0.0, float(q))) for q in v)
    return (x0, y0, x1, y1)


def resolve_model(path: Optional[str]) -> tuple[str, Optional[str]]:
    if path:
        return path, None
    if DEFAULT_PILL.exists():
        return str(DEFAULT_PILL), None
    return DEFAULT_FALLBACK, (
        "models/pill-nano.pt ausente — usando yolov8n.pt (não é modelo de comprimido)"
    )


def create_app(
    source: str | int = 0,
    model: Optional[str] = None,
    direction: str = "rtl",
    line_pos: float = 0.5,
    conf: float = 0.3,
    lite: bool = False,
    roi: Optional[tuple[float, float, float, float]] = None,
    crop_belt: bool = False,
) -> FastAPI:
    global pipeline, _broadcast_interval, _jpeg_quality

    model_path, warning = resolve_model(model)
    _broadcast_interval = 0.08 if lite else 0.03
    _jpeg_quality = 55 if lite else 80

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        global pipeline, _broadcast_task
        pipeline = YoloCountPipeline(
            model_path=model_path,
            source=source,
            direction=direction,
            line_pos=line_pos,
            conf=conf,
            lite=lite,
            roi=roi,
            crop_belt=crop_belt,
        )
        pipeline.model_warning = warning
        try:
            pipeline.open()
        except RuntimeError as exc:
            # em outro PC o indice da camera muda: sobe num video de teste e a UI troca pelo botao Fonte
            videos = list_videos()
            if not videos:
                raise
            print(f"AVISO: {exc}. Usando o video de teste {videos[0]['name']}; escolha a camera no botao Fonte.")
            pipeline.source = str(ROOT / videos[0]["path"])
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
            "lite": bool(pipeline.lite) if pipeline else lite,
            "imgsz": pipeline.imgsz if pipeline else None,
            "source": describe(pipeline.source) if pipeline else None,
            "ended": bool(pipeline.ended) if pipeline else False,
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
            roi=_roi_tuple(body.roi) if body.roi is not None else None,
        )
        return pipeline._state()

    @app.get("/sources")
    async def sources():
        cams = await asyncio.to_thread(list_cameras)
        return {
            "current": describe(pipeline.source) if pipeline else None,
            "cameras": cams,
            "videos": list_videos(),
        }

    @app.post("/source")
    async def set_source(body: SourceBody):
        assert pipeline
        src: int | str = body.source
        if isinstance(src, str) and src.isdigit():
            src = int(src)
        if isinstance(src, str):
            video = resolve_video(src)
            if video is None:
                return JSONResponse(
                    {"error": f"Vídeo não está em samples/videos: {src}", "current": describe(pipeline.source)},
                    status_code=400,
                )
            src = str(video)
        try:
            await asyncio.to_thread(pipeline.switch_source, src)
        except RuntimeError as exc:
            return JSONResponse(
                {"error": f"Não abriu a fonte: {exc}", "current": describe(pipeline.source)},
                status_code=409,
            )
        return {"current": describe(pipeline.source), "total": pipeline.total}

    @app.post("/pause")
    def pause(paused: bool = True):
        assert pipeline
        pipeline.paused = paused
        return {"paused": pipeline.paused}

    @app.get("/frame.jpg")
    def frame_jpg(raw: bool = False):
        assert pipeline
        if pipeline.last_frame is None:
            return Response(status_code=404)
        frame = pipeline.last_frame.copy()
        if raw:
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), _jpeg_quality])
            if not ok:
                return Response(status_code=500)
            return Response(content=buf.tobytes(), media_type="image/jpeg")
        # draw line
        h, w = frame.shape[:2]
        pos = pipeline.counter.line_pos
        if pipeline.counter.direction in ("ltr", "rtl"):
            x = int(w * pos)
            cv2.line(frame, (x, 0), (x, h), (0, 220, 255), 2)
        else:
            y = int(h * pos)
            cv2.line(frame, (0, y), (w, y), (0, 220, 255), 2)
        if pipeline.roi:
            fx0, fy0, fx1, fy1 = pipeline.roi
            cv2.rectangle(
                frame, (int(fx0 * w), int(fy0 * h)), (int(fx1 * w), int(fy1 * h)), (255, 160, 0), 1
            )
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
        ok, buf = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), _jpeg_quality]
        )
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
                        roi=_roi_tuple(msg.get("roi")),
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
            try:
                state = await asyncio.to_thread(pipeline.step)
            except Exception:
                # uma falha num frame nao pode parar a contagem (a tela congelaria sem aviso)
                traceback.print_exc()
                await asyncio.sleep(0.5)
                continue
            dead = []
            payload = json.dumps(state)
            for ws in list(clients):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                clients.discard(ws)
        await asyncio.sleep(_broadcast_interval)
