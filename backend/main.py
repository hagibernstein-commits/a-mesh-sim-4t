"""Entry point for running A-Mesh Sim 4T FastAPI server."""

from __future__ import annotations
import os
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles
from app.main import app, resolve_static_dir

_static_dir = resolve_static_dir() or (
    Path("/app/static")
    if Path("/app/static").is_dir()
    else Path(__file__).resolve().parent.parent / "frontend" / "dist"
)
if (_static_dir / "assets").is_dir() and not any(
    getattr(r, "path", None) == "/assets" for r in app.routes
):
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

