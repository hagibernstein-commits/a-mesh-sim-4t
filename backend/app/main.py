"""FastAPI Backend Server & 20Hz WebSocket Telemetry Stream for A-Mesh Sim 4T."""

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .simulator import SwarmSimulator

simulator = SwarmSimulator()

STATIC_CANDIDATES: List[Path] = [
    Path("/app/static"),
    Path(__file__).resolve().parent.parent.parent / "frontend" / "dist",
]


def resolve_static_dir() -> Optional[Path]:
    for candidate in STATIC_CANDIDATES:
        if (candidate / "index.html").is_file():
            return candidate
    return None


class GeodeticOriginRequest(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="WGS84 Latitude in decimal degrees (-90 to 90)")
    lon: float = Field(..., ge=-180.0, le=180.0, description="WGS84 Longitude in decimal degrees (-180 to 180)")
    alt_asl: float = Field(default=335.0, description="Base site elevation ASL in meters")


class ControlRequest(BaseModel):
    action: str
    ew_jamming: Optional[bool] = None
    wind_speed_ms: Optional[float] = None
    ambient_lux: Optional[float] = None


class GimbalControlRequest(BaseModel):
    drone_id: str = "UAV-1"
    pitch_deg: Optional[float] = None
    yaw_deg: Optional[float] = None
    sensor_mode: Optional[str] = None
    thermal_palette: Optional[str] = None
    zoom_level: Optional[float] = None
    slew_to_entity_id: Optional[str] = None


class PinTargetRequest(BaseModel):
    drone_id: str = "UAV-1"


class JammingZoneRequest(BaseModel):
    x: float = 135.0
    z: float = -10.0
    radius_m: float = 115.0


class SarGridRequest(BaseModel):
    polygon_xz: List[List[float]] = Field(..., min_length=3)
    altitude_agl_m: float = Field(default=60.0, ge=20.0, le=250.0)
    sensor_mode: str = Field(default="THERMAL")
    sidelap_pct: float = Field(default=70.0, ge=20.0, le=90.0)
    sweep_angle_deg: float = Field(default=0.0, ge=0.0, le=180.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    running = True

    async def sim_loop():
        while running:
            simulator.step(0.05)
            await asyncio.sleep(0.05)

    task = asyncio.create_task(sim_loop())
    try:
        yield
    finally:
        running = False
        task.cancel()


app = FastAPI(
    title="A-Mesh Sim 4T Backend API",
    version="0.6.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/terrain")
async def get_terrain() -> Dict[str, Any]:
    return simulator.terrain.export_heightmap()


@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    return simulator.get_state_snapshot()


@app.get("/api/mission/origin")
async def get_mission_origin() -> Dict[str, Any]:
    return {
        "status": "ok",
        "geodetic_origin": simulator.get_geodetic_origin_summary(),
    }


@app.post("/api/mission/origin")
async def set_mission_origin(req: GeodeticOriginRequest) -> Dict[str, Any]:
    try:
        origin_summary = simulator.set_geodetic_origin(req.lat, req.lon, req.alt_asl)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "ok",
        "geodetic_origin": origin_summary,
        "sar_mission": simulator.mission_planner.get_state(),
    }


@app.post("/api/control")
async def post_control(req: ControlRequest) -> Dict[str, Any]:
    act = req.action.lower()
    if act == "pause":
        simulator.paused = True
    elif act == "resume":
        simulator.paused = False
    elif act == "toggle_pause":
        simulator.paused = not simulator.paused
    elif act == "reset":
        simulator.reset()
    elif act == "ew_jamming":
        simulator.ew_jamming_active = (
            bool(req.ew_jamming) if req.ew_jamming is not None else (not simulator.ew_jamming_active)
        )
    elif act == "environment":
        if req.wind_speed_ms is not None:
            simulator.wind_speed_ms = max(0.0, min(22.0, float(req.wind_speed_ms)))
        if req.ambient_lux is not None:
            simulator.ambient_lux = max(1.0, min(2000.0, float(req.ambient_lux)))
    elif act == "drop_jamming_zone":
        simulator.drop_jamming_zone()
    elif act == "valley_dome_wire_run":
        simulator.trigger_valley_dome_wire_scenario()
    return simulator.get_state_snapshot()


@app.post("/api/gimbal")
async def post_gimbal(req: GimbalControlRequest) -> Dict[str, Any]:
    drone = simulator.drones.get(req.drone_id)
    if drone is None:
        raise HTTPException(status_code=404, detail=f"Unknown drone_id: {req.drone_id}")
    if req.slew_to_entity_id:
        ent = next((e for e in simulator.terrain.thermal_entities if e.id == req.slew_to_entity_id), None)
        if ent is not None:
            import numpy as np

            drone.slew_gimbal_to_point(np.array([ent.x, ent.y, ent.z], dtype=float))
            drone.sensor_mode = "THERMAL"
    else:
        drone.set_gimbal(
            pitch_deg=req.pitch_deg,
            yaw_deg=req.yaw_deg,
            sensor_mode=req.sensor_mode,
            thermal_palette=req.thermal_palette,
            zoom_level=req.zoom_level,
        )
    return drone.to_telemetry(simulator.terrain)


@app.post("/api/pin-target")
async def post_pin_target(req: PinTargetRequest) -> Dict[str, Any]:
    pin = simulator.pin_lrf_target(req.drone_id)
    return {"status": "ok", "pin": pin, "pinned_targets": simulator.pinned_targets}


@app.post("/api/jamming-zone")
async def post_jamming_zone(req: JammingZoneRequest) -> Dict[str, Any]:
    zone = simulator.drop_jamming_zone(req.x, req.z, req.radius_m)
    return {"status": "ok", "zone": zone, "jamming_zones": simulator.jamming_zones}


@app.post("/api/scenario/valley-dome")
async def post_valley_dome_scenario() -> Dict[str, Any]:
    return simulator.trigger_valley_dome_wire_scenario()


@app.get("/api/blackbox/summary")
async def get_blackbox_summary() -> Dict[str, Any]:
    return simulator.blackbox.get_summary()


@app.get("/api/blackbox/frame/{frame_index}")
async def get_blackbox_frame(frame_index: int) -> Dict[str, Any]:
    return simulator.blackbox.get_replay_snapshot(frame_index)


@app.post("/api/blackbox/clear")
async def clear_blackbox() -> Dict[str, Any]:
    simulator.blackbox.clear()
    return {"status": "ok", "total_frames": 0}


@app.get("/api/blackbox/export/csv")
async def export_blackbox_csv() -> Response:
    csv_data = simulator.blackbox.export_csv()
    return Response(
        content=csv_data.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="amesh_sim_4t_debrief.csv"'},
    )


@app.get("/api/blackbox/export/json")
async def export_blackbox_json() -> Response:
    json_data = simulator.blackbox.export_json()
    return Response(
        content=json_data.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="amesh_sim_4t_debrief.json"'},
    )


@app.post("/api/mission/sar-grid")
async def post_mission_sar_grid(req: SarGridRequest) -> Dict[str, Any]:
    try:
        state = simulator.mission_planner.generate_grid(
            polygon_xz=req.polygon_xz,
            altitude_agl_m=req.altitude_agl_m,
            sensor_mode=req.sensor_mode,
            sidelap_pct=req.sidelap_pct,
            sweep_angle_deg=req.sweep_angle_deg,
            batteries={uid: d.battery_pct for uid, d in simulator.drones.items()},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return state


@app.post("/api/mission/execute")
async def post_mission_execute() -> Dict[str, Any]:
    return simulator.execute_sar_mission()


@app.post("/api/mission/clear")
async def post_mission_clear() -> Dict[str, Any]:
    return simulator.clear_sar_mission()


@app.post("/api/mission/upload-kml")
async def post_mission_upload_kml(file: UploadFile = File(...)) -> Dict[str, Any]:
    raw_bytes = await file.read()
    filename = file.filename or "mission.kml"
    try:
        result = simulator.import_kml_kmz(raw_bytes, filename=filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.get("/api/mission/export-kml")
async def get_mission_export_kml(format: str = Query(default="kml")) -> Response:
    mission_id = simulator.mission_planner.mission_id
    if format.lower() in ("wpml_kmz", "kmz", "wpml"):
        kmz_bytes = simulator.export_mission_wpml_kmz()
        filename = f"amesh_sim_4t_{mission_id}_wpml.kmz"
        return Response(
            content=kmz_bytes,
            media_type="application/vnd.google-earth.kmz",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    kml_str = simulator.export_mission_kml()
    filename = f"amesh_sim_4t_{mission_id}.kml"
    return Response(
        content=kml_str.encode("utf-8"),
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.websocket("/ws/telemetry")
async def websocket_telemetry(ws: WebSocket) -> None:
    await ws.accept()
    try:
        while True:
            await ws.send_json(simulator.get_state_snapshot())
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=0.05)
                if isinstance(msg, dict):
                    mtype = msg.get("type", "")
                    if mtype == "set_origin":
                        simulator.set_geodetic_origin(
                            float(msg.get("lat", simulator.origin_lat)),
                            float(msg.get("lon", simulator.origin_lon)),
                            float(msg.get("alt_asl", simulator.origin_alt_asl)),
                        )
                    elif mtype == "gimbal":
                        d = simulator.drones.get(msg.get("drone_id", "UAV-1"))
                        if d is not None:
                            d.set_gimbal(
                                pitch_deg=msg.get("pitch_deg"),
                                yaw_deg=msg.get("yaw_deg"),
                                sensor_mode=msg.get("sensor_mode"),
                                thermal_palette=msg.get("thermal_palette"),
                                zoom_level=msg.get("zoom_level"),
                            )
                    elif mtype == "pin_target":
                        simulator.pin_lrf_target(msg.get("drone_id", "UAV-1"))
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        return


_initial_static_dir = resolve_static_dir()
if _initial_static_dir is not None and (_initial_static_dir / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_initial_static_dir / "assets")),
        name="assets",
    )


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa_fallback(full_path: str) -> Response:
    if full_path in ("api", "ws") or full_path.startswith(("api/", "ws/")):
        raise HTTPException(status_code=404, detail="Not Found")

    static_dir = resolve_static_dir()
    if static_dir is not None:
        if full_path:
            candidate = (static_dir / full_path).resolve()
            if str(candidate).startswith(str(static_dir.resolve())) and candidate.is_file():
                return FileResponse(str(candidate))
        index_html = static_dir / "index.html"
        if index_html.is_file():
            return FileResponse(str(index_html))

    return Response(
        content='{"status":"ok","service":"A-Mesh Sim 4T Backend API"}',
        media_type="application/json",
    )

