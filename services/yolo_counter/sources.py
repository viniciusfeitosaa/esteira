"""Fontes de imagem que a UI pode escolher: cameras do PC (ao vivo) ou videos de teste."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]
VIDEO_DIR = ROOT / "samples" / "videos"
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv"}


def camera_backend() -> int:
    # DirectShow no Windows: mesma numeracao da lista de nomes (webcam, Iriun, iVCam, OBS)
    return cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY


def is_camera(source: str | int) -> bool:
    return str(source).isdigit()


def _dshow_names() -> list[str] | None:
    if sys.platform != "win32":
        return None
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        return None
    try:
        return list(FilterGraph().get_input_devices())
    except Exception:
        return None


def _probe(index: int) -> bool:
    cap = cv2.VideoCapture(index, camera_backend())
    try:
        if not cap.isOpened():
            return False
        ok, _ = cap.read()
        return bool(ok)
    finally:
        cap.release()


def list_cameras(max_probe: int = 6) -> list[dict]:
    names = _dshow_names()
    if names is not None:
        return [{"index": i, "name": n} for i, n in enumerate(names)]
    # sem nomes do sistema: testa os indices que abrem
    return [{"index": i, "name": f"Câmera {i}"} for i in range(max_probe) if _probe(i)]


def video_key(path: str | Path) -> str:
    """Caminho relativo ao repo (estavel para a UI comparar)."""
    p = Path(path)
    full = p if p.is_absolute() else ROOT / p
    try:
        return full.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return full.resolve().as_posix()


def list_videos() -> list[dict]:
    if not VIDEO_DIR.is_dir():
        return []
    return [
        {"path": video_key(p), "name": p.stem}
        for p in sorted(VIDEO_DIR.iterdir())
        if p.suffix.lower() in VIDEO_EXTS
    ]


def resolve_video(key: str) -> Path | None:
    """So aceita videos da pasta de teste (a UI nao abre caminho arbitrario)."""
    for v in list_videos():
        if v["path"] == key:
            return ROOT / key
    return None


def describe(source: str | int) -> dict:
    if is_camera(source):
        return {"kind": "camera", "index": int(source)}
    return {"kind": "video", "path": video_key(source), "name": Path(str(source)).stem}
